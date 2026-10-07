## Distributed Patterns

### Saga pattern

**Definition.** A saga is a business transaction made of a sequence of **local transactions**, one per service. Each step publishes an event/command that triggers the next step. If a step fails, the saga runs **compensating transactions** for the steps already completed (semantic undo — e.g., refund instead of "rollback").

**Why it matters.** It replaces 2PC. You get atomicity at the business level (all steps happen, or the effects are undone) without distributed locks.

Running example: **Order -> Payment -> Inventory**.

| Step | Service | Local transaction | Compensation |
|---|---|---|---|
| 1 | Orders | create Order = `Pending` | cancel order (`Cancelled`) |
| 2 | Payments | capture payment | refund payment |
| 3 | Inventory | reserve stock | release stock |
| 4 | Orders | mark `Confirmed` | (final step, no compensation) |

Design tip: put the **hardest-to-undo step last** (the *pivot*). Reserving stock is cheap to undo; charging a card is not, so many real systems reserve stock first, then charge. We keep the requested order to show a compensation.

#### Choreography (event-driven, no central coordinator)

```text
Orders        Payments            Inventory           Orders
  |-OrderCreated->|                    |                  |
  |               |-PaymentCompleted-->|                  |
  |               |                    |-StockReserved--->|  => Order Confirmed
  |               |                    |
  |               |<-StockReservationFailed (compensation path)
  |               |-- refund card ---> PaymentRefunded --> Orders: Order Cancelled
  |-PaymentFailed (from Payments) --------------------------> Orders: Order Cancelled
```

Each service subscribes to the events it cares about:

```csharp
// Payments service
public sealed class OrderCreatedConsumer(PaymentsDb db, IGateway gateway, IOutbox outbox)
    : IConsumer<OrderCreated>
{
    public async Task Consume(ConsumeContext<OrderCreated> ctx)
    {
        var m = ctx.Message;
        var result = await gateway.ChargeAsync(m.OrderId, m.Total, idempotencyKey: m.OrderId.ToString());
        if (result.Success)
            outbox.Add(new PaymentCompleted(m.OrderId, result.PaymentId));
        else
            outbox.Add(new PaymentFailed(m.OrderId, result.Reason));
        await db.SaveChangesAsync(ctx.CancellationToken);       // data + outbox atomically
    }
}

// Payments service: compensation
public sealed class StockReservationFailedConsumer(PaymentsDb db, IGateway gateway, IOutbox outbox)
    : IConsumer<StockReservationFailed>
{
    public async Task Consume(ConsumeContext<StockReservationFailed> ctx)
    {
        var payment = await db.Payments.SingleAsync(p => p.OrderId == ctx.Message.OrderId);
        if (payment.Status == PaymentStatus.Refunded) return;          // idempotent compensation
        await gateway.RefundAsync(payment.ExternalId, idempotencyKey: $"refund-{payment.Id}");
        payment.Status = PaymentStatus.Refunded;
        outbox.Add(new PaymentRefunded(payment.OrderId));
        await db.SaveChangesAsync(ctx.CancellationToken);
    }
}
```

`IOutbox` is a thin wrapper that adds a row to the outbox table of the *same* `DbContext`, so `SaveChangesAsync` stores the data change and the outgoing message atomically (full code in the Outbox topic below).

Pros: simple, loosely coupled, no single point of failure. Cons: the flow is implicit (scattered across services), cyclic dependencies creep in, hard to see "where is order 42 now?".

#### Orchestration (central saga coordinator)

```text
                     +---------------------+
   OrderSubmitted -->|  Order Saga         |--ChargePayment-->  Payments
                     |  (state machine)    |<-PaymentCompleted
                     |  state persisted    |--ReserveStock---> Inventory
                     |                     |<-StockReserved / StockReservationFailed
                     |                     |--RefundPayment--> Payments (compensation)
                     +---------------------+
```

Hand-written orchestrator (framework independent). State is **persisted**, handlers are **idempotent**, and unexpected messages in the wrong state are ignored:

```csharp
public enum SagaState { AwaitingPayment, AwaitingStock, Refunding, Completed, Cancelled }

public sealed class OrderSaga
{
    public Guid OrderId { get; set; }                 // correlation id = primary key
    public SagaState State { get; set; }
    public decimal Total { get; set; }
    public string? FailureReason { get; set; }
    public DateTime DeadlineUtc { get; set; }         // for timeouts
    public byte[] RowVersion { get; set; } = [];      // optimistic concurrency
}

public sealed class OrderSagaOrchestrator(SagaDb db, IOutbox outbox)
{
    public async Task On(OrderSubmitted m, CancellationToken ct)
    {
        if (await db.Sagas.AnyAsync(s => s.OrderId == m.OrderId, ct)) return;   // duplicate
        db.Sagas.Add(new OrderSaga { OrderId = m.OrderId, Total = m.Total,
            State = SagaState.AwaitingPayment, DeadlineUtc = DateTime.UtcNow.AddMinutes(15) });
        outbox.Add(new ChargePayment(m.OrderId, m.Total));
        await db.SaveChangesAsync(ct);
    }

    public async Task On(PaymentCompleted m, CancellationToken ct)
    {
        var s = await db.Sagas.FindAsync([m.OrderId], ct);
        if (s is null || s.State != SagaState.AwaitingPayment) return;          // out-of-state: ignore
        s.State = SagaState.AwaitingStock;
        outbox.Add(new ReserveStock(m.OrderId));
        await db.SaveChangesAsync(ct);          // RowVersion check rejects concurrent updates
    }

    public async Task On(PaymentFailed m, CancellationToken ct) =>
        await FinishAsync(m.OrderId, SagaState.AwaitingPayment, SagaState.Cancelled, m.Reason, ct);

    public async Task On(StockReserved m, CancellationToken ct)
    {
        var s = await db.Sagas.FindAsync([m.OrderId], ct);
        if (s is null || s.State != SagaState.AwaitingStock) return;
        s.State = SagaState.Completed;
        outbox.Add(new ConfirmOrder(m.OrderId));
        await db.SaveChangesAsync(ct);
    }

    public async Task On(StockReservationFailed m, CancellationToken ct)        // start compensation
    {
        var s = await db.Sagas.FindAsync([m.OrderId], ct);
        if (s is null || s.State != SagaState.AwaitingStock) return;
        s.State = SagaState.Refunding;
        s.FailureReason = m.Reason;
        outbox.Add(new RefundPayment(m.OrderId));
        await db.SaveChangesAsync(ct);
    }

    public async Task On(PaymentRefunded m, CancellationToken ct) =>
        await FinishAsync(m.OrderId, SagaState.Refunding, SagaState.Cancelled, null, ct);

    private async Task FinishAsync(Guid id, SagaState expected, SagaState next,
                                   string? reason, CancellationToken ct)
    {
        var s = await db.Sagas.FindAsync([id], ct);
        if (s is null || s.State != expected) return;
        s.State = next; s.FailureReason ??= reason;
        if (next == SagaState.Cancelled) outbox.Add(new CancelOrder(id, s.FailureReason));
        await db.SaveChangesAsync(ct);
    }
}
```

A background job scans `DeadlineUtc < now AND State IN (AwaitingPayment, AwaitingStock)` and starts compensation — otherwise a lost message leaves a saga stuck forever.

**MassTransit state machine** (Automatonymous merged into MassTransit): the same flow declaratively, with built-in persistence (EF Core, MongoDB, Redis), correlation, retries, timeouts (`Schedule`) and the outbox:

```csharp
public class OrderState : SagaStateMachineInstance
{
    public Guid CorrelationId { get; set; }     // = OrderId
    public string CurrentState { get; set; } = "";
    public decimal Total { get; set; }
}

public class OrderStateMachine : MassTransitStateMachine<OrderState>
{
    public State AwaitingPayment { get; private set; } = null!;
    public State AwaitingStock { get; private set; } = null!;
    public State Refunding { get; private set; } = null!;
    public Event<OrderSubmitted> OrderSubmitted { get; private set; } = null!;
    public Event<PaymentCompleted> PaymentCompleted { get; private set; } = null!;
    public Event<PaymentFailed> PaymentFailed { get; private set; } = null!;
    public Event<StockReserved> StockReserved { get; private set; } = null!;
    public Event<StockReservationFailed> StockReservationFailed { get; private set; } = null!;
    public Event<PaymentRefunded> PaymentRefunded { get; private set; } = null!;

    public OrderStateMachine()
    {
        InstanceState(x => x.CurrentState);
        Event(() => OrderSubmitted, e => e.CorrelateById(c => c.Message.OrderId));
        Event(() => PaymentCompleted, e => e.CorrelateById(c => c.Message.OrderId));
        Event(() => PaymentFailed, e => e.CorrelateById(c => c.Message.OrderId));
        Event(() => StockReserved, e => e.CorrelateById(c => c.Message.OrderId));
        Event(() => StockReservationFailed, e => e.CorrelateById(c => c.Message.OrderId));
        Event(() => PaymentRefunded, e => e.CorrelateById(c => c.Message.OrderId));

        Initially(When(OrderSubmitted)
            .Then(c => c.Saga.Total = c.Message.Total)
            .Publish(c => new ChargePayment(c.Saga.CorrelationId, c.Saga.Total))
            .TransitionTo(AwaitingPayment));

        During(AwaitingPayment,
            When(PaymentCompleted).Publish(c => new ReserveStock(c.Saga.CorrelationId))
                                  .TransitionTo(AwaitingStock),
            When(PaymentFailed).Publish(c => new CancelOrder(c.Saga.CorrelationId, "Payment"))
                               .Finalize());

        During(AwaitingStock,
            When(StockReserved).Publish(c => new ConfirmOrder(c.Saga.CorrelationId)).Finalize(),
            When(StockReservationFailed).Publish(c => new RefundPayment(c.Saga.CorrelationId))
                                        .TransitionTo(Refunding));

        During(Refunding,
            When(PaymentRefunded).Publish(c => new CancelOrder(c.Saga.CorrelationId, "No stock"))
                                 .Finalize());

        SetCompletedWhenFinalized();       // delete saga row when done
    }
}

builder.Services.AddMassTransit(x =>
{
    x.AddSagaStateMachine<OrderStateMachine, OrderState>()
     .EntityFrameworkRepository(r =>
     {
         r.ConcurrencyMode = ConcurrencyMode.Optimistic;
         r.AddDbContext<DbContext, SagaDbContext>((sp, o) => o.UseSqlServer(connStr));
     });
    x.UsingRabbitMq((ctx, cfg) => cfg.ConfigureEndpoints(ctx));
});
```

| | Choreography | Orchestration |
|---|---|---|
| Visibility of flow | scattered | one place, queryable state |
| Coupling | services know events | services know commands from orchestrator; orchestrator knows all steps |
| Risk | cyclic dependencies, hard to debug | orchestrator becomes a "god service" |
| Adding a step | touch several services | change orchestrator |
| Choose for | 2-4 steps, few branches | long, branching flows with compensation, timeouts, human steps |

:::warn Saga gotchas
- **No isolation (the "I" in ACID is missing).** Others can read the half-finished state (order `Pending`, money captured). Mitigate with explicit pending statuses, *semantic locks* (`Reserved` flag), and commutative updates.
- **Compensations must be idempotent, retryable and must not fail forever**; if a refund cannot succeed, raise an alert for manual handling.
- Every step needs an **idempotent handler** (duplicate messages) and every transition an **outbox** (no lost messages).
- **Timeouts** for every wait state.
- Not everything is compensable (email already sent) — put those steps last or make them "tentative then confirm".
:::

### Outbox pattern (and Inbox)

**Definition.** Instead of writing to the DB and publishing to the broker as two separate operations (dual write), write the event into an **outbox table in the same local transaction** as the business data. A separate *relay* publishes outbox rows to the broker and marks them sent. The consumer side uses an **inbox** (processed-message table) to ignore duplicates.

```text
Order API                         Relay (BackgroundService)            Broker
 BEGIN TX                            poll Outbox where Processed=NULL
  INSERT Orders      \                -> publish                       ---> consumers
  INSERT Outbox      / atomic         -> mark Processed
 COMMIT                               (crash after publish, before mark => duplicate
                                       => at-least-once => consumers need Inbox)
```

```csharp
public class OutboxMessage
{
    public Guid Id { get; set; } = Guid.NewGuid();     // also used as MessageId
    public string Type { get; set; } = "";             // e.g. "Shop.Contracts.OrderPlaced"
    public string Payload { get; set; } = "";          // JSON
    public DateTime OccurredOnUtc { get; set; } = DateTime.UtcNow;
    public DateTime? ProcessedOnUtc { get; set; }
    public int Attempts { get; set; }
    public string? Error { get; set; }
}

public class InboxMessage
{
    public Guid MessageId { get; set; }
    public string Consumer { get; set; } = "";
    public DateTime ProcessedOnUtc { get; set; }
}

public class OrdersDb(DbContextOptions<OrdersDb> options) : DbContext(options)
{
    public DbSet<Order> Orders => Set<Order>();
    public DbSet<OutboxMessage> Outbox => Set<OutboxMessage>();
    public DbSet<InboxMessage> Inbox => Set<InboxMessage>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<OutboxMessage>(e =>
        {
            e.ToTable("Outbox");
            e.HasIndex(x => x.OccurredOnUtc).HasFilter("[ProcessedOnUtc] IS NULL");
        });
        b.Entity<InboxMessage>(e =>
        {
            e.ToTable("Inbox");
            e.HasKey(x => new { x.MessageId, x.Consumer });     // unique => dedup
        });
    }

    // helper: serialise any event into the outbox (same DbContext => same transaction)
    public void Enqueue<T>(T message) where T : class => Outbox.Add(new OutboxMessage
    {
        Type = typeof(T).AssemblyQualifiedName!,
        Payload = JsonSerializer.Serialize(message)
    });
}
```

Writing the business change and the event atomically:

```csharp
public async Task<Guid> PlaceOrderAsync(PlaceOrder cmd, CancellationToken ct)
{
    var order = Order.Create(cmd.CustomerId, cmd.Lines);
    db.Orders.Add(order);
    db.Enqueue(new OrderPlaced(order.Id, order.CustomerId, order.Total, DateTime.UtcNow));
    await db.SaveChangesAsync(ct);          // one transaction: both rows or neither
    return order.Id;
}
```

The relay. `UPDLOCK, READPAST` lets several relay instances run without picking the same rows:

```csharp
public sealed class OutboxRelay(IServiceScopeFactory scopes, ILogger<OutboxRelay> log)
    : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stop)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(1));
        while (await timer.WaitForNextTickAsync(stop))
        {
            try { await RelayBatchAsync(stop); }
            catch (Exception ex) when (ex is not OperationCanceledException)
            { log.LogError(ex, "Outbox relay iteration failed"); }
        }
    }

    private async Task RelayBatchAsync(CancellationToken ct)
    {
        using var scope = scopes.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<OrdersDb>();
        var publisher = scope.ServiceProvider.GetRequiredService<IMessagePublisher>();

        await using var tx = await db.Database.BeginTransactionAsync(ct);
        var batch = await db.Outbox.FromSqlRaw("""
            SELECT TOP (50) * FROM Outbox WITH (UPDLOCK, READPAST, ROWLOCK)
            WHERE ProcessedOnUtc IS NULL
            ORDER BY OccurredOnUtc
            """).ToListAsync(ct);

        foreach (var m in batch)
        {
            try
            {
                await publisher.PublishAsync(m.Type, m.Payload, messageId: m.Id, ct);
                m.ProcessedOnUtc = DateTime.UtcNow;
            }
            catch (Exception ex)
            {
                m.Attempts++; m.Error = ex.Message;
                break;                          // keep ordering: stop at first failure
            }
        }
        await db.SaveChangesAsync(ct);
        await tx.CommitAsync(ct);
    }
}
```

Consumer with **Inbox** (idempotent receiver) — dedup row and business change commit together:

```csharp
public sealed class OrderPlacedConsumer(BillingDb db) : IConsumer<OrderPlaced>
{
    public async Task Consume(ConsumeContext<OrderPlaced> ctx)
    {
        var messageId = ctx.MessageId ?? throw new InvalidOperationException("No MessageId");
        await using var tx = await db.Database.BeginTransactionAsync(ctx.CancellationToken);

        db.Inbox.Add(new InboxMessage { MessageId = messageId,
            Consumer = nameof(OrderPlacedConsumer), ProcessedOnUtc = DateTime.UtcNow });
        try { await db.SaveChangesAsync(ctx.CancellationToken); }
        catch (DbUpdateException ex) when (ex.InnerException is SqlException { Number: 2627 or 2601 })
        {
            return;                             // already processed: duplicate, drop silently
        }

        db.Invoices.Add(Invoice.For(ctx.Message));          // the real work
        await db.SaveChangesAsync(ctx.CancellationToken);
        await tx.CommitAsync(ctx.CancellationToken);
    }
}
```

Variants and tips:
- **Polling publisher** (above) is simplest. **Log tailing / CDC** (Debezium reading the outbox table's WAL/CDC, Azure SQL change feed) gives lower latency without polling.
- MassTransit ships an EF Core **transactional outbox/inbox** (`AddEntityFrameworkOutbox<TDbContext>(o => { o.UseSqlServer(); o.UseBusOutbox(); })`) so `Publish` inside a handler is stored in the DB first. Wolverine and NServiceBus have equivalents.
- Clean up processed rows (retention 7 days); keep an index on unprocessed rows; monitor *outbox age* (oldest unprocessed message) as an SLI.
- Ordering: single relay per aggregate key or accept unordered delivery and make consumers tolerant.

:::q Outbox vs Saga — are they alternatives?
No, they solve different problems. The outbox guarantees that "state change + event" happen atomically in one service, so no event is lost. A saga coordinates a business process across many services. Real sagas use outboxes at every step.
:::

### Distributed locking

**Definition.** A lock shared across processes/instances so that only one holder runs a critical section at a time (e.g., one instance of the nightly invoice job, one writer for a resource).

**Why it is tricky.** In a single process, `lock` is reliable. Across machines the lock holder can crash, pause (GC, VM stall) or be partitioned while others think the lock expired. So: use TTLs, unique tokens, and prefer correctness guarantees from the **data store** (unique constraints, optimistic concurrency `rowversion`) over locks.

| Mechanism | How | Notes |
|---|---|---|
| Redis `SET key token NX PX ttl` | atomic set-if-absent with expiry | fast; single node is not safe through failover |
| **RedLock** | acquire on majority of N independent Redis masters | more tolerant of node failure, but still relies on bounded clock drift and pauses; critics (Kleppmann) say it is unsafe for correctness without fencing tokens. OK for efficiency locks (avoid duplicate work), not for protecting money |
| SQL Server `sp_getapplock` | named lock tied to a session/transaction | great when you already have SQL; automatically released when the session dies |
| Azure Blob lease | 15-60s (or infinite) exclusive lease on a blob, renewable | simple, strongly consistent (Azure Storage), no extra infra |
| ZooKeeper / etcd / Consul | ephemeral nodes / leases, CP stores | strongest option; also gives fencing tokens (revisions) |
| Kubernetes Lease | leader election API | for controllers / "single active instance" jobs |

**Fencing token.** The lock service issues an increasing number with each grant; the protected resource rejects writes carrying an older number. This protects against a paused ex-holder waking up and writing after its lock expired.

```csharp
// Redis lock with StackExchange.Redis (single-instance, efficiency lock)
public sealed class RedisLock : IAsyncDisposable
{
    private readonly IDatabase _db; private readonly string _key; private readonly string _token;
    private RedisLock(IDatabase db, string key, string token) => (_db, _key, _token) = (db, key, token);

    public static async Task<RedisLock?> TryAcquireAsync(IDatabase db, string resource, TimeSpan ttl)
    {
        var key = $"lock:{resource}";
        var token = Guid.NewGuid().ToString("N");              // owner id: only owner can release
        return await db.LockTakeAsync(key, token, ttl) ? new RedisLock(db, key, token) : null;
    }

    public async ValueTask DisposeAsync() => await _db.LockReleaseAsync(_key, _token);
}

// usage in a scheduled job running on many instances
await using var l = await RedisLock.TryAcquireAsync(redis.GetDatabase(), "invoice-job",
                                                    TimeSpan.FromMinutes(5));
if (l is null) return;              // another instance holds it
await RunInvoiceJobAsync(ct);       // must finish (or renew) within the TTL
```

SQL Server application lock (released automatically if the connection dies):

```csharp
await using var conn = new SqlConnection(cs);
await conn.OpenAsync(ct);
await using var cmd = new SqlCommand("""
    DECLARE @r int;
    EXEC @r = sp_getapplock @Resource = @res, @LockMode = 'Exclusive',
                            @LockOwner = 'Session', @LockTimeout = 0;
    SELECT @r;
    """, conn);
cmd.Parameters.AddWithValue("@res", "invoice-job");
var rc = (int)(await cmd.ExecuteScalarAsync(ct))!;       // 0 or 1 = granted, <0 = not granted
if (rc < 0) return;
try { await RunInvoiceJobAsync(ct); }                    // keep this connection open meanwhile
finally
{
    await using var rel = new SqlCommand(
        "EXEC sp_releaseapplock @Resource = @res, @LockOwner = 'Session'", conn);
    rel.Parameters.AddWithValue("@res", "invoice-job");
    await rel.ExecuteNonQueryAsync(ct);
}
```

Azure Blob lease:

```csharp
BlobClient blob = container.GetBlobClient("locks/invoice-job");   // blob must exist
BlobLeaseClient lease = blob.GetBlobLeaseClient();
try
{
    await lease.AcquireAsync(TimeSpan.FromSeconds(60));            // 15-60s or infinite
    // renew every ~20s in a loop while working: await lease.RenewAsync();
    await RunInvoiceJobAsync(ct);
}
catch (RequestFailedException ex) when (ex.Status == 409) { /* held by someone else */ }
finally { try { await lease.ReleaseAsync(); } catch (RequestFailedException) { } }
```

:::warn Locks are not a correctness tool by themselves
A lock with a TTL can expire while the holder is still working (long GC pause, slow call). Two holders then run at once. Use the lock to *reduce* duplicate work, and protect the data with optimistic concurrency (`rowversion`/ETag), unique constraints and idempotent operations — and use fencing tokens where correctness matters.
:::

:::scenario Two orders buy the last item at the same time (overselling)
**Situation.** Stock = 1. Two checkouts read `available = 1` and both reserve it.

**Fix options, best first.**
1. **Atomic conditional update in the Inventory service's DB** — no distributed lock needed: `UPDATE Stock SET Available = Available - @q WHERE Sku = @s AND Available >= @q` and check `rowsAffected == 1`.
2. **Optimistic concurrency** (`rowversion`) with retry on `DbUpdateConcurrencyException`.
3. **Serialise per SKU** — partition commands by SKU (Kafka key / Service Bus session) so one consumer handles one SKU at a time.
4. A Redis/SQL lock per SKU only if the above are impossible.

Overselling policy is also a business decision: some sellers allow backorders and compensate later.
:::
