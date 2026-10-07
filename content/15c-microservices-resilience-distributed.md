## Resilience

### Why resilience patterns exist

**Definition.** Resilience = the system keeps delivering acceptable service when dependencies are slow, failing or overloaded.

**Why it matters.** In a monolith a method call either returns or throws immediately. Over a network a call can be slow, lost, executed twice, or succeed while the reply is lost. The classic *fallacies of distributed computing*: the network is reliable, latency is zero, bandwidth is infinite, topology does not change. Without protection, one slow dependency makes threads and connections pile up and the failure **cascades** upstream.

| Pattern | Protects against | One-line idea |
|---|---|---|
| Timeout | hanging calls | never wait forever |
| Retry (+ backoff + jitter) | transient faults | try again, but politely |
| Circuit breaker | persistent failure | stop calling a dead dependency, fail fast |
| Bulkhead | resource exhaustion | isolate pools so one dependency cannot eat all threads/connections |
| Rate limiter / load shedding | overload | refuse excess work early |
| Fallback | any failure | degrade gracefully (cached/default value) |
| Hedging | tail latency | send a second request if the first is slow |

In .NET these are provided by **Polly v8** (`Polly.Core`, `ResiliencePipeline`) and the Microsoft packages built on it: `Microsoft.Extensions.Http.Resilience` (HttpClient) and `Microsoft.Extensions.Resilience` (generic, telemetry). Polly v8 replaced the v7 `Policy`/`PolicyWrap` API with composable *pipelines*. The old `Microsoft.Extensions.Http.Polly` package is legacy.

```text
Pipeline order matters: the first strategy added is the OUTERMOST.
Request -> [Rate limiter/Bulkhead] -> [Total timeout] -> [Retry] -> [Circuit breaker]
        -> [Attempt timeout] -> HTTP call
Retry wraps the breaker, so each attempt counts toward the breaker and a rejection
(BrokenCircuitException) is not retried blindly.
```

### Retry with exponential backoff and jitter

**Definition.** Re-execute a failed operation after a delay that grows exponentially (1s, 2s, 4s, 8s ...) with random jitter added.

**Why backoff.** A struggling server needs breathing room; immediate retries add load exactly when it is weakest.
**Why jitter.** If 1000 clients fail at the same moment and all retry after exactly 2s, they hit the server together again (*thundering herd*). Randomising each delay spreads them out.

**Retry only when it is safe:**
- Transient errors only: `HttpRequestException`, timeout, 408/429/5xx. Never 400/401/403/404/validation errors.
- Operation must be **idempotent** (GET/PUT/DELETE yes; POST only with an idempotency key). A retried "charge card" without a key double-charges.
- Respect `Retry-After` on 429/503.
- Cap attempts (3-5) and total time; remember retries multiply load (3 retries x 3 layers = 27 calls on the leaf service). Retry at **one** layer, usually the outermost caller.

### Timeout

Every remote call needs a timeout; the default `HttpClient.Timeout` is 100 seconds, which is far too long. Use two levels:
- **Attempt timeout** — one try (e.g., 2s).
- **Total timeout** — the whole operation including retries (e.g., 8s).

Make timeouts shorter as you go deeper: caller 8s, mid-tier 4s, leaf 2s, so the caller does not give up while the leaf is still working. Pass `CancellationToken` all the way to DB calls so abandoned work really stops.

### Circuit breaker

**Definition.** Tracks failures; after a threshold it *opens* and rejects calls immediately for a cool-down, then lets a probe through.

```text
              failure ratio >= threshold (in sampling window,
                  and >= minimum throughput)
   CLOSED -----------------------------------------> OPEN
 (normal; failures                                (all calls fail fast with
  are counted)                                     BrokenCircuitException)
     ^                                                  |
     | probe call succeeds                              | BreakDuration elapsed
     |                                                  v
     '------------------------------------------- HALF-OPEN
                  probe fails -> back to OPEN        (limited trial calls)
```

Benefits: the failing dependency gets time to recover, callers free their threads instantly, and you can return a fallback. Pitfalls: thresholds too sensitive (flapping), one breaker shared across unrelated endpoints/hosts, no alert when it opens.

### Bulkhead

Named after ship compartments. Give each dependency its own limited pool (concurrency + queue). If *Recommendations* hangs, only its 20 slots are consumed; checkout calls keep their own pool.

```csharp
// Polly v8 bulkhead = concurrency limiter strategy: max 20 parallel, 10 queued
pipeline.AddConcurrencyLimiter(permitLimit: 20, queueLimit: 10);
// beyond that => RateLimiterRejectedException (fail fast instead of piling up)
```

Other bulkhead forms: separate `HttpClient`/connection pools per dependency, separate thread/worker pools, separate queues per priority, separate K8s pods for critical vs batch workloads.

### Rate limiting

Two directions:
- **Server side (protect yourself):** ASP.NET Core `AddRateLimiter` (fixed window, sliding window, token bucket, concurrency) per IP/user/API key; return `429` + `Retry-After`. Also at the gateway.
- **Client side (protect the dependency / stay under a vendor quota):** a Polly rate-limiter strategy or `System.Threading.RateLimiting` limiter in front of the outgoing calls.

```csharp
// Server side
builder.Services.AddRateLimiter(o =>
{
    o.RejectionStatusCode = StatusCodes.Status429TooManyRequests;
    o.AddPolicy("per-user", ctx => RateLimitPartition.GetTokenBucketLimiter(
        partitionKey: ctx.User.Identity?.Name ?? ctx.Connection.RemoteIpAddress?.ToString() ?? "anon",
        factory: _ => new TokenBucketRateLimiterOptions
        {
            TokenLimit = 20, TokensPerPeriod = 10,
            ReplenishmentPeriod = TimeSpan.FromSeconds(1), QueueLimit = 0,
            AutoReplenishment = true
        }));
});
app.UseRateLimiter();
app.MapPost("/orders", PlaceOrder).RequireRateLimiting("per-user");
```

### Fallback and hedging

**Fallback** returns a degraded-but-useful result: cached prices, an empty recommendations list, "stock status unknown", or queueing the work for later. Decide per feature what "degraded" means; never fall back silently on money-moving operations.

**Hedging** sends a second (parallel) request if the first has not answered within a delay, and uses whichever returns first — it cuts p99 latency. Only for **idempotent, read-only** calls and when the downstream has spare capacity (it increases load). Needs multiple instances/endpoints to be useful.

### Complete setup with Microsoft.Extensions.Http.Resilience

#### The one-liner: standard resilience handler

`AddStandardResilienceHandler()` adds a sensible pipeline: rate limiter (1000 concurrent), total timeout (30s), retry (3 attempts, exponential, jitter, 2s base), circuit breaker (10% failure ratio over 30s, min 100 calls, 5s break), attempt timeout (10s). Tune it:

```csharp
builder.Services.AddHttpClient<IInventoryClient, InventoryClient>(c =>
        c.BaseAddress = new Uri("http://inventory/"))
    .AddStandardResilienceHandler(o =>
    {
        o.TotalRequestTimeout.Timeout = TimeSpan.FromSeconds(8);
        o.AttemptTimeout.Timeout      = TimeSpan.FromSeconds(2);

        o.Retry.MaxRetryAttempts = 3;
        o.Retry.BackoffType      = DelayBackoffType.Exponential;
        o.Retry.UseJitter        = true;
        o.Retry.Delay            = TimeSpan.FromMilliseconds(300);
        o.Retry.ShouldRetryAfterHeader = true;        // honour Retry-After
        o.Retry.DisableForUnsafeHttpMethods();        // do not auto-retry POST/PATCH/DELETE

        o.CircuitBreaker.SamplingDuration = TimeSpan.FromSeconds(10);  // must be >= 2 x attempt timeout
        o.CircuitBreaker.MinimumThroughput = 20;
        o.CircuitBreaker.FailureRatio      = 0.5;
        o.CircuitBreaker.BreakDuration     = TimeSpan.FromSeconds(15);
    });
```

Validation tips: the options are validated at startup. `SamplingDuration` must be at least double the `AttemptTimeout`, and `TotalRequestTimeout` should be larger than the attempt timeout (ideally larger than retries x attempt timeout), otherwise you get a validation error or retries that never get a chance to run.

#### Full custom pipeline: AddResilienceHandler

```csharp
builder.Services.AddHttpClient<IPaymentClient, PaymentClient>(c =>
        c.BaseAddress = new Uri("http://payments/"))
    .AddResilienceHandler("payments", (pipeline, context) =>
    {
        var logger = context.ServiceProvider.GetRequiredService<ILogger<PaymentClient>>();

        // 1) Bulkhead: outermost, protects our threads/sockets
        pipeline.AddConcurrencyLimiter(permitLimit: 50, queueLimit: 25);

        // 2) Total timeout across all attempts
        pipeline.AddTimeout(TimeSpan.FromSeconds(10));

        // 3) Retry with exponential backoff + jitter (only transient failures)
        pipeline.AddRetry(new HttpRetryStrategyOptions
        {
            MaxRetryAttempts = 3,
            BackoffType = DelayBackoffType.Exponential,
            UseJitter = true,
            Delay = TimeSpan.FromMilliseconds(500),
            ShouldHandle = args => ValueTask.FromResult(
                HttpClientResiliencePredicates.IsTransient(args.Outcome)),
            OnRetry = args =>
            {
                logger.LogWarning("Retry {Attempt} after {Delay} because {Reason}",
                    args.AttemptNumber + 1, args.RetryDelay,
                    args.Outcome.Exception?.Message ?? args.Outcome.Result?.StatusCode.ToString());
                return default;
            }
        });

        // 4) Circuit breaker (each attempt counts toward it)
        pipeline.AddCircuitBreaker(new HttpCircuitBreakerStrategyOptions
        {
            SamplingDuration = TimeSpan.FromSeconds(30),
            FailureRatio = 0.5,
            MinimumThroughput = 20,
            BreakDuration = TimeSpan.FromSeconds(20),
            OnOpened  = a => { logger.LogError("Payments circuit OPEN for {D}", a.BreakDuration); return default; },
            OnClosed  = a => { logger.LogInformation("Payments circuit CLOSED"); return default; },
            OnHalfOpened = a => { logger.LogInformation("Payments circuit HALF-OPEN"); return default; }
        });

        // 5) Per-attempt timeout (innermost)
        pipeline.AddTimeout(TimeSpan.FromSeconds(3));
    });
```

#### Non-HTTP pipelines (database, SDK calls) and fallback

```csharp
// Register a named pipeline (Polly.Extensions)
builder.Services.AddResiliencePipeline("sql-transient", pipeline => pipeline
    .AddRetry(new RetryStrategyOptions
    {
        ShouldHandle = new PredicateBuilder()
            .Handle<TimeoutException>()
            .Handle<SqlException>(ex => ex.Number is -2 or 1205 or 40501 or 40613),
        MaxRetryAttempts = 4,
        Delay = TimeSpan.FromMilliseconds(200),
        BackoffType = DelayBackoffType.Exponential,
        UseJitter = true
    })
    .AddTimeout(TimeSpan.FromSeconds(5)));

// Use it
public sealed class OrderRepository(ResiliencePipelineProvider<string> provider, OrdersDb db)
{
    private readonly ResiliencePipeline _pipeline = provider.GetPipeline("sql-transient");

    public ValueTask<Order?> GetAsync(Guid id, CancellationToken ct) =>
        _pipeline.ExecuteAsync(async token =>
            await db.Orders.AsNoTracking().FirstOrDefaultAsync(o => o.Id == id, token), ct);
}
```

```csharp
// Typed pipeline with fallback: price service down -> last known price from cache
var pipeline = new ResiliencePipelineBuilder<decimal?>()
    .AddFallback(new FallbackStrategyOptions<decimal?>
    {
        ShouldHandle = new PredicateBuilder<decimal?>()
            .Handle<HttpRequestException>()
            .Handle<BrokenCircuitException>()
            .Handle<TimeoutRejectedException>(),
        FallbackAction = _ => Outcome.FromResultAsValueTask<decimal?>(cache.GetLastKnownPrice(sku))
    })
    .Build();
var price = await pipeline.ExecuteAsync(
    async ct => await priceClient.GetPriceAsync(sku, ct), cancellationToken);
```

```csharp
// Hedging for idempotent reads: the standard hedging handler (replaces the standard handler)
builder.Services.AddHttpClient<ICatalogClient, CatalogClient>(c =>
        c.BaseAddress = new Uri("http://catalog/"))
    .AddStandardHedgingHandler();   // total timeout, hedged attempts, per-attempt breaker/timeout
```

Polly v8 emits metrics and logs automatically (`Polly` meter: `resilience.polly.strategy.events`, retries, breaker transitions), so they flow into OpenTelemetry — see Observability. Polly v8 also includes chaos strategies (`AddChaosFault`, `AddChaosLatency`) to test your pipelines.

:::warn Resilience anti-patterns
- Retrying non-idempotent POSTs without an idempotency key.
- Retries at every layer (retry storm) — amplification x N^layers.
- One shared circuit breaker for all hosts or all endpoints — one bad endpoint blocks healthy ones.
- Infinite or 100s timeouts; no timeout on DB calls.
- Swallowing `BrokenCircuitException` instead of returning a meaningful 503/fallback.
- Not testing it: use chaos/latency injection or WireMock/Toxiproxy in integration tests.
:::

:::scenario Service A is slow and takes down service B
**Situation.** Product-Details (A) starts taking 30s because its DB is saturated. Storefront (B) calls A on every page. B's request threads and outgoing connections are all stuck waiting; B's own health checks fail and Kubernetes restarts it; the whole site is down although only A had a problem.

**Why.** No timeout, no isolation: B's resources were shared with the slow dependency (cascading failure).

**Fix, in layers.**
1. **Timeout** 1-2s on calls to A, with the token propagated.
2. **Circuit breaker**: after ~50% failures, B stops calling A and fails fast.
3. **Bulkhead**: limit concurrent calls to A to e.g. 30; the rest are rejected immediately, B keeps serving other pages.
4. **Fallback**: show cached product data or hide the widget.
5. **Load shedding / autoscale A**, add a cache in front of A, and alert on breaker-open metrics.
6. Long term: stop calling A synchronously — B keeps a local read model fed by A's events.
:::

:::q Retry vs circuit breaker — do they conflict?
They complement each other. Retry handles *transient* blips; the breaker handles *persistent* failure by stopping retries from hammering a dead service. Order them with retry outside and the breaker inside, so each attempt is counted and, once the circuit is open, retries fail fast instead of waiting.
:::

:::q What does AddStandardResilienceHandler give you and what would you change?
It adds rate limiter, total timeout, retry with exponential backoff and jitter, circuit breaker and attempt timeout with sane defaults. I would tune timeouts to my SLOs, disable retries for unsafe methods unless there is an idempotency key, and raise/lower breaker thresholds based on real traffic.
:::

## Distributed Systems

### Distributed transactions and why 2PC is hard

**Definition.** A distributed transaction updates data in more than one independent resource (databases, services) as one atomic unit: all commit or all roll back.

**Two-Phase Commit (2PC).**

```text
Coordinator                 Participant A (Orders DB)     Participant B (Payments DB)
   | -- prepare ----------------> |                              |
   | -- prepare ------------------------------------------------>|
   | <-- vote YES (locks held) -- |                              |
   | <-- vote YES (locks held) ------------------------------------|
   | -- commit -----------------> |                              |
   | -- commit ------------------------------------------------->|
Phase 1 = vote (participants lock rows and promise)   Phase 2 = decision
```

Why it is avoided in microservices:
- **Blocking.** If the coordinator dies after "prepare", participants hold locks until it recovers.
- **Availability is the product of all participants.** One slow/down participant stalls everyone.
- **Latency and lock contention** — locks span network round trips.
- **Not supported** by most brokers, REST APIs, SaaS and cloud PaaS (Cosmos DB, Service Bus + SQL together, Stripe). In .NET, `TransactionScope` escalates to MSDTC (Windows only) — not available in Linux containers.
- Violates service autonomy (shared transaction coordinator).

**The dual-write problem.** The common bug that replaces 2PC in practice:

```csharp
await db.SaveChangesAsync();          // 1) order committed
await bus.Publish(new OrderPlaced()); // 2) process crashes here => event lost forever
```
Either order has a failure window where DB and broker disagree. Cures: **Outbox pattern** (atomic write of data + event in one local transaction), **Saga** for multi-service business transactions, and **idempotent consumers**.

### Eventual consistency

**Definition.** After an update, replicas/services may briefly disagree; if no new updates arrive, they all converge to the same state.

**Why it matters.** It is the price of independent services, async messaging, caches and read replicas. Design around it instead of fighting it.

How to live with it:
- Show **pending states** in the UI ("Order received, payment processing") rather than faking finality.
- **Read-your-writes**: after a write, read from the primary or return the written resource; route the user to the primary for a few seconds.
- **Idempotent, commutative or versioned updates** so out-of-order delivery is harmless (use `Version`/`UpdatedAt`, last-writer-wins or merge rules).
- **Compensating actions** instead of rollbacks (refund, release stock).
- Set SLOs for propagation lag and monitor it (consumer lag, outbox backlog).
- Choose strong consistency inside an aggregate/service (one DB transaction) and eventual consistency between services.

:::example Order status lag
User pays; Payments publishes `PaymentCaptured`; Orders consumes it 300ms later. If the user refreshes at 100ms, the order still says "Pending payment". The UI shows "Confirming your payment..." and polls/pushes (SignalR) until the status changes — no incorrect "failed" message is shown.
:::

### CAP theorem and PACELC

**CAP.** In a distributed data store, during a **network Partition** you must choose between **Consistency** (every read sees the latest write — linearizability) and **Availability** (every non-failing node answers). Partitions will happen, so the real choice is CP or AP *during a partition*. When there is no partition you can have both.

- **CP example**: a bank balance store, etcd/ZooKeeper, MongoDB with majority writes — a minority partition refuses writes/reads rather than return stale data.
- **AP example**: shopping cart in DynamoDB/Cassandra, DNS, social-media like counters — every node keeps answering, versions are reconciled later (last-write-wins, vector clocks, CRDTs).

**PACELC** extends it: if **P**artition, choose **A** or **C**; **E**lse (normal operation) choose **L**atency or **C**onsistency. Even without failures, replicating synchronously costs latency.

| System (typical default) | During partition | Normal operation | PACELC |
|---|---|---|---|
| DynamoDB, Cassandra (tunable) | Availability | Latency | PA/EL |
| MongoDB (majority concerns), HBase | Consistency | Consistency | PC/EC |
| Cosmos DB | tunable by consistency level (Strong ... Eventual) | tunable | configurable |
| SQL Server AG, sync commit | Consistency | Consistency (extra commit latency) | PC/EC |
| SQL Server AG, async commit / read replicas | Availability of reads | Latency (replica lag) | PA/EL |

Cosmos DB's five levels (Strong, Bounded staleness, Session, Consistent prefix, Eventual) are the best practical illustration: Session is the common default — you read your own writes, others may lag.

:::tip Say it in one sentence
"CAP says that when the network splits I must pick consistency or availability. PACELC adds that even when the network is fine I trade latency for consistency, which is why read replicas and caches are always slightly stale."
:::

### Idempotency

**Definition.** An operation is idempotent if performing it N times has the same effect as performing it once.

**Why it matters.** Retries, redelivered messages, double-clicks and gateway timeouts all create duplicates. Idempotency is the foundation of at-least-once systems.

- Naturally idempotent: `GET`, `PUT` (replace), `DELETE`, "set status = Paid", upserts.
- Not idempotent: `POST /payments`, "balance += 10", "send email".

**Techniques.**
1. **Idempotency key** — client generates a unique key per logical operation (`Idempotency-Key: <guid>`); the server stores the key with the result and returns the stored result on repeat. Used by Stripe, PayPal, Adyen.
2. **Natural/business key + unique constraint** — unique index on `(OrderId, PaymentAttempt)` or on `ExternalReference`; a duplicate insert fails.
3. **Inbox / dedup table** for message consumers — store processed `MessageId`s (see Outbox/Inbox).
4. **State-machine guards** — "if order.Status == Paid return" and optimistic concurrency (`rowversion`).
5. **Conditional updates** — `UPDATE ... WHERE Status = 'Pending'`; check affected rows.

```csharp
public class IdempotencyRecord
{
    public string Key { get; set; } = "";             // primary key
    public string RequestHash { get; set; } = "";     // detect key reuse with a different body
    public int? StatusCode { get; set; }
    public string? ResponseBody { get; set; }
    public DateTime CreatedUtc { get; set; }
}

public sealed class IdempotencyService(PaymentsDb db)
{
    public async Task<IResult> ExecuteAsync(string key, object request,
        Func<Task<(int Status, object Body)>> action, CancellationToken ct)
    {
        var hash = Convert.ToHexString(SHA256.HashData(JsonSerializer.SerializeToUtf8Bytes(request)));

        var existing = await db.IdempotencyRecords.AsNoTracking()
                               .FirstOrDefaultAsync(r => r.Key == key, ct);
        if (existing is not null)
        {
            if (existing.RequestHash != hash)
                return Results.UnprocessableEntity("Idempotency-Key reused with a different payload");
            if (existing.StatusCode is null)
                return Results.Conflict("A request with this key is still in progress");
            return Results.Content(existing.ResponseBody!, "application/json", null, existing.StatusCode);
        }

        db.IdempotencyRecords.Add(new IdempotencyRecord
            { Key = key, RequestHash = hash, CreatedUtc = DateTime.UtcNow });
        try { await db.SaveChangesAsync(ct); }          // PK on Key: the racing duplicate fails here
        catch (DbUpdateException) { return Results.Conflict("Duplicate request in progress"); }

        try
        {
            var (status, body) = await action();
            var rec = await db.IdempotencyRecords.FindAsync([key], ct);
            rec!.StatusCode = status;
            rec.ResponseBody = JsonSerializer.Serialize(body);
            await db.SaveChangesAsync(ct);
            return Results.Content(rec.ResponseBody, "application/json", null, status);
        }
        catch
        {
            await db.IdempotencyRecords.Where(r => r.Key == key).ExecuteDeleteAsync(ct); // allow retry
            throw;
        }
    }
}

app.MapPost("/payments", async (ChargeRequest req, [FromHeader(Name = "Idempotency-Key")] string? key,
    IdempotencyService idem, PaymentService payments, CancellationToken ct) =>
    string.IsNullOrWhiteSpace(key)
        ? Results.BadRequest("Idempotency-Key header is required")
        : await idem.ExecuteAsync(key, req, async () =>
          {
              var p = await payments.ChargeAsync(req, ct);
              return (StatusCodes.Status201Created, p);
          }, ct));
```

Expire idempotency records after 24-72 hours with a cleanup job. In production wrap the action and the "mark complete" step in one transaction when the business write is in the same database.

:::q Is PUT idempotent? Is POST?
PUT replaces the resource, so repeating it leaves the same state — idempotent. POST creates a new resource each time, so it is not, unless I add an idempotency key or a natural unique key so the server detects the repeat.
:::

:::q Why can't you just use a distributed transaction across services?
2PC blocks while locks are held across network calls, makes availability the product of all participants, and is not supported by brokers, HTTP APIs or most PaaS. Microservices use local transactions plus Saga with compensations, Outbox for atomic publish, and idempotent consumers for safe retries.
:::
