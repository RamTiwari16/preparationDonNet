## Asynchronous & Event-Driven Communication

### Events vs commands vs queries

**Definition.** Services can communicate by *messages* instead of waiting for replies. There are three kinds:

| | Command | Event | Query |
|---|---|---|---|
| Meaning | "Do this" (intent) | "This happened" (fact) | "Tell me this" |
| Naming | imperative: `ReserveStock`, `ChargePayment` | past tense: `OrderPlaced`, `PaymentCaptured` | `GetOrderStatus` |
| Receivers | exactly one | zero to many (publisher does not know) | one |
| Can be rejected? | yes | no — it already happened | n/a |
| Coupling | sender knows the receiver's capability | publisher knows nothing about subscribers | caller knows the provider |
| Pattern | point-to-point (queue) | publish/subscribe (topic) | request/response |

```text
Point-to-point (command)            Publish/subscribe (event)
 Orders --ReserveStock--> [queue] -> Inventory      Orders --OrderPlaced--> [topic]
 (one consumer; competing consumers                                         |-> Billing
  share the queue for scale)                                                |-> Inventory
                                                                            |-> Email
                                                                            '-> Analytics
```

**Why it matters.** Events remove temporal coupling (the consumer can be down), allow adding consumers without touching the publisher (open/closed at architecture level), and absorb traffic spikes in a queue. The price: eventual consistency, harder debugging, and duplicate/out-of-order messages you must handle.

**Two event styles.**
- **Event notification** — thin event (`OrderPlaced { OrderId }`); consumers call back for details. Small, but creates a sync dependency again.
- **Event-carried state transfer** — fat event with the data consumers need (`OrderPlaced { OrderId, Lines, Total, ShippingAddress }`). Consumers stay autonomous but contracts are bigger.

**Choreography vs orchestration** (full treatment in the Saga topic).

| | Choreography | Orchestration |
|---|---|---|
| Control | each service reacts to events, no central brain | a central orchestrator sends commands, tracks state |
| Coupling | loose, but flow is implicit and hard to see | services depend on orchestrator; flow explicit |
| Debugging | trace events across services | read one state machine |
| Best for | simple flows (2-4 steps) | complex flows, many branches, compensation |

:::example Order placed
`Orders` publishes `OrderPlaced`. `Billing` charges the card, `Inventory` reserves stock, `Notifications` sends the confirmation, `Analytics` records the sale. Adding a new `Loyalty` service that awards points needs zero change to `Orders` — it just subscribes.
:::

## Messaging Brokers

### Broker comparison: RabbitMQ vs Kafka vs Azure Service Bus

| | RabbitMQ | Apache Kafka | Azure Service Bus |
|---|---|---|---|
| Model | smart broker: exchanges route to queues | distributed commit log of partitions | managed enterprise broker: queues + topics/subscriptions |
| Queues | yes (classic, quorum, streams) | no — topics are logs | yes |
| Topics / pub-sub | exchange types (fanout/topic/direct/headers) + one queue per subscriber | topic; every consumer group reads independently | topic + subscriptions (with SQL/correlation filters) |
| Partitions | none in classic/quorum (streams and consistent-hash exchange exist) | core scaling unit: parallelism = partitions | partitioned entities (service-level), sessions for grouping |
| Consumer scaling | competing consumers on a queue | **consumer group**: each partition read by one consumer in the group | competing consumers per queue/subscription |
| Ordering | per queue, lost with several consumers or requeue | **guaranteed per partition** (use key to co-locate) | FIFO only with **sessions** (per session id) |
| Retention | message deleted after ack (streams keep) | time/size based (days-forever), log compaction | until consumed or TTL; DLQ keeps failures |
| Replay | no (except streams) | yes: reset offset | no (can keep via peek/scheduled copies) |
| Delivery | at-least-once (acks + publisher confirms) | at-least-once; exactly-once inside Kafka with idempotent producer + transactions | at-least-once (peek-lock); at-most-once (receive-and-delete); duplicate detection by `MessageId` |
| Dead-lettering | DLX (dead-letter exchange) | none built in: DLT topic by convention | built-in DLQ, `MaxDeliveryCount` (default 10) |
| Throughput | tens of thousands msg/s per node | millions msg/s (sequential disk I/O) | thousands to tens of thousands per unit |
| Extras | flexible routing, priorities, TTL | stream processing, Kafka Connect, exactly-once semantics | sessions, scheduled delivery, transactions, auto-forward, Entra ID/managed identity |
| Ops | self-managed or CloudAMQP | self-managed, Confluent, Event Hubs (Kafka API) | fully managed PaaS |
| Pick when | rich routing, task queues, moderate scale | event streaming, huge volume, replay, analytics, event sourcing | Azure-native business messaging, ordering via sessions, minimal ops |

**Rule of thumb.** Work queue or complex routing: RabbitMQ. Event log, high volume, replay, multiple independent consumers of the same stream: Kafka. Azure shop wanting a reliable managed broker for business workflows: Service Bus. (Azure Event Hubs is the Kafka-like streaming service; Service Bus is the transactional business broker.)

:::tip Interview framing
Do not recite features. Say: "Kafka is a log — consumers pull and track their own offset, so replay and fan-out are free, but there is no per-message ack or priority. RabbitMQ and Service Bus are brokers — the broker tracks per-message state, so they fit task/command processing."
:::

### MassTransit (abstraction over brokers)

MassTransit gives one programming model over RabbitMQ, Azure Service Bus, Amazon SQS, etc.: consumers, retries, outbox, sagas. Note: **v8 is Apache-2.0 open source; v9 moved to a commercial license** — check current terms before adopting; alternatives are Wolverine, NServiceBus (commercial), Rebus, Brighter, or the raw client libraries.

```csharp
// Shared contracts (records, immutable, no behaviour)
namespace Shop.Contracts;
public sealed record OrderPlaced(Guid OrderId, Guid CustomerId, decimal Total,
                                 DateTime PlacedAtUtc);

// Publisher: Orders API
public sealed class PlaceOrderHandler(OrdersDb db, IPublishEndpoint bus)
{
    public async Task<Guid> HandleAsync(PlaceOrder cmd, CancellationToken ct)
    {
        var order = Order.Create(cmd.CustomerId, cmd.Lines);
        db.Orders.Add(order);
        await db.SaveChangesAsync(ct);
        await bus.Publish(new OrderPlaced(order.Id, order.CustomerId, order.Total,
                                          DateTime.UtcNow), ct);   // see Outbox: do it atomically
        return order.Id;
    }
}

// Consumer: Billing service
public sealed class OrderPlacedConsumer(IBillingService billing, ILogger<OrderPlacedConsumer> log)
    : IConsumer<OrderPlaced>
{
    public async Task Consume(ConsumeContext<OrderPlaced> ctx)
    {
        log.LogInformation("Charging order {OrderId}", ctx.Message.OrderId);
        await billing.ChargeAsync(ctx.Message.OrderId, ctx.Message.Total, ctx.CancellationToken);
    }
}

// Program.cs
builder.Services.AddMassTransit(x =>
{
    x.AddConsumer<OrderPlacedConsumer>();
    x.UsingRabbitMq((context, cfg) =>
    {
        cfg.Host("rabbitmq", "/", h => { h.Username("shop"); h.Password("secret"); });
        cfg.UseMessageRetry(r => r.Exponential(5, TimeSpan.FromSeconds(1),
                                    TimeSpan.FromSeconds(30), TimeSpan.FromSeconds(2)));
        cfg.ConfigureEndpoints(context);    // queue per consumer, topic per message type
    });
});
```

When retries are exhausted MassTransit moves the message to the `<queue>_error` queue (its dead-letter queue) with the exception in headers; messages with no matching consumer go to `<queue>_skipped`.

### RabbitMQ essentials

```text
Publisher -> [Exchange] --binding(routing key)--> [Queue] -> Consumer (ack)
             types: direct (exact key) | topic (patterns: orders.*.eu) |
                    fanout (all bound queues) | headers
             Queue properties: durable, quorum (replicated, Raft), TTL, max-length,
                               x-dead-letter-exchange, x-delivery-limit (quorum)
```

- **Publisher confirms** — broker acknowledges that the message is persisted/replicated.
- **Consumer ack/nack** — manual ack after processing; unacked messages are redelivered if the channel dies. `prefetch` (QoS) limits in-flight messages per consumer, which is your backpressure knob.
- **Durability needs three things:** durable exchange, durable/quorum queue, persistent messages.
- **Ordering** — preserved per queue with one consumer; broken by multiple consumers and by requeue after a nack.

### Kafka essentials

```text
Topic orders.placed (3 partitions, replication factor 3)
 P0: [0][1][2][3][4]...  <- key hash(CustomerId) % 3 decides the partition
 P1: [0][1][2]...                          (same key => same partition => ordered)
 P2: [0][1][2][3]...
Consumer group "billing" (3 consumers): C1<-P0, C2<-P1, C3<-P2   (max parallelism = 3)
Consumer group "analytics" (1 consumer): C1<-P0,P1,P2           (independent offsets)
```

- **Offset** = position in a partition. The consumer commits offsets (after processing = at-least-once).
- **Consumer group rebalance** happens when consumers join/leave; processing pauses briefly.
- **Retention** is by time/size (`retention.ms`) or **log compaction** (keep last value per key — good for state/changelog topics).
- **Producer settings for safety:** `acks=all`, `enable.idempotence=true`, topic `min.insync.replicas=2`, replication factor 3.
- **Ordering** only within a partition; choose the key carefully (e.g., `OrderId` for order lifecycle events). Hot keys cause hot partitions.

```csharp
// Producer (Confluent.Kafka) — one long-lived instance per app (thread-safe)
var producer = new ProducerBuilder<string, string>(new ProducerConfig
{
    BootstrapServers = "kafka:9092",
    Acks = Acks.All,
    EnableIdempotence = true,           // no duplicates from producer retries
    CompressionType = CompressionType.Lz4,
    LingerMs = 5                        // small batching delay for throughput
}).Build();

var evt = new OrderPlaced(orderId, customerId, 99.5m, DateTime.UtcNow);
var delivery = await producer.ProduceAsync("orders.placed", new Message<string, string>
{
    Key = orderId.ToString(),                       // partition key => per-order ordering
    Value = JsonSerializer.Serialize(evt),
    Headers = new Headers { { "event-type", Encoding.UTF8.GetBytes("OrderPlaced") } }
});
// Output: delivery.Partition / delivery.Offset tell where it landed
```

```csharp
// Consumer as a BackgroundService: manual commit after successful processing
public sealed class OrderPlacedKafkaConsumer(IServiceScopeFactory scopes,
    ILogger<OrderPlacedKafkaConsumer> log) : BackgroundService
{
    protected override Task ExecuteAsync(CancellationToken stop) =>
        Task.Run(() => RunAsync(stop), stop);      // Consume() blocks a thread

    private async Task RunAsync(CancellationToken stop)
    {
        var cfg = new ConsumerConfig
        {
            BootstrapServers = "kafka:9092", GroupId = "billing",
            AutoOffsetReset = AutoOffsetReset.Earliest,
            EnableAutoCommit = false                // we commit ourselves
        };
        using var consumer = new ConsumerBuilder<string, string>(cfg).Build();
        consumer.Subscribe("orders.placed");
        try
        {
            while (!stop.IsCancellationRequested)
            {
                var cr = consumer.Consume(stop);
                using var scope = scopes.CreateScope();
                var handler = scope.ServiceProvider.GetRequiredService<IOrderPlacedHandler>();
                await handler.HandleAsync(cr.Message.Key, cr.Message.Value, stop); // idempotent!
                consumer.Commit(cr);                // at-least-once
            }
        }
        catch (OperationCanceledException) { }
        finally { consumer.Close(); }               // leaves the group cleanly
    }
}
```

:::warn Kafka consumer pitfalls
Auto-commit before processing = message loss on crash. Slow processing longer than `max.poll.interval.ms` = consumer kicked out, rebalance storm. More consumers than partitions = idle consumers. A poison message blocks its partition forever unless you route it to a dead-letter topic.
:::

### Azure Service Bus essentials

- **Queue** — point-to-point. **Topic + subscriptions** — pub/sub; each subscription is a virtual queue with optional filters.
- **Peek-lock** (default): message is locked for `LockDuration` (30s default, max 5 min); you `Complete` it, `Abandon` it, or `DeadLetter` it; on lock expiry it is redelivered and `DeliveryCount` increments. At `MaxDeliveryCount` (default 10) it moves to the **dead-letter queue** (`<entity>/$deadletterqueue`).
- **Sessions** — messages with the same `SessionId` are delivered in order to one receiver (FIFO per entity such as an order).
- **Duplicate detection** — set `RequiresDuplicateDetection`; broker drops repeats of the same `MessageId` within the window.
- **Scheduled delivery** and **TTL**, **auto-forwarding**, **transactions**, **Entra ID auth** (use managed identity, not connection strings).

```csharp
await using var client = new ServiceBusClient("shop.servicebus.windows.net",
                                              new DefaultAzureCredential());

// Send an event to a topic
ServiceBusSender sender = client.CreateSender("order-events");
await sender.SendMessageAsync(new ServiceBusMessage(BinaryData.FromObjectAsJson(evt))
{
    MessageId = evt.OrderId.ToString(),        // used for duplicate detection
    Subject = "OrderPlaced",
    CorrelationId = correlationId,
    SessionId = evt.OrderId.ToString(),        // only if the entity has sessions enabled
    ApplicationProperties = { ["schemaVersion"] = 1 }
});

// Receive with a processor (handles concurrency, lock renewal, retries on the client side)
ServiceBusProcessor processor = client.CreateProcessor("order-events", "billing",
    new ServiceBusProcessorOptions
    {
        MaxConcurrentCalls = 8,
        AutoCompleteMessages = false,                    // we decide
        MaxAutoLockRenewalDuration = TimeSpan.FromMinutes(5)
    });

processor.ProcessMessageAsync += async args =>
{
    try
    {
        var evt = args.Message.Body.ToObjectFromJson<OrderPlaced>();
        await billing.ChargeAsync(evt.OrderId, evt.Total, args.CancellationToken);
        await args.CompleteMessageAsync(args.Message);           // success
    }
    catch (ValidationException ex)                               // permanent failure
    {
        await args.DeadLetterMessageAsync(args.Message,
            deadLetterReason: "InvalidPayload", deadLetterErrorDescription: ex.Message);
    }
    catch (HttpRequestException)                                 // transient failure
    {
        await args.AbandonMessageAsync(args.Message);            // redelivered, DeliveryCount++
    }
};
processor.ProcessErrorAsync += args =>
{
    log.LogError(args.Exception, "SB error {Source}", args.ErrorSource);
    return Task.CompletedTask;
};
await processor.StartProcessingAsync();
```

### Delivery guarantees

| Guarantee | Meaning | How you get it |
|---|---|---|
| At-most-once | may lose, never duplicates | ack/commit *before* processing; fire-and-forget |
| **At-least-once** | never lose, may duplicate | ack/commit *after* processing — the practical default |
| Exactly-once *processing* | effect happens once | at-least-once delivery **+ idempotent consumer** (inbox/dedup table) |

"Exactly-once delivery" across a network and two systems is not achievable in general. Kafka's exactly-once covers read-process-write *inside Kafka* with transactions; as soon as your consumer writes to SQL Server, you need idempotency again.

### Message contracts and versioning

A message contract is a public API. Treat it like one.

```json
{
  "messageId": "5b0a6d32-3c1b-4a8e-9a2f-1d5a0f4b7c11",
  "type": "OrderPlaced",
  "version": 2,
  "occurredAtUtc": "2025-06-01T10:15:30Z",
  "correlationId": "c8d1f3a0-...",
  "causationId": "a14b...",
  "tenantId": "acme",
  "data": {
    "orderId": "d2b4...", "customerId": "77aa...",
    "total": 99.50, "currency": "USD",
    "lines": [ { "sku": "SKU-1", "qty": 2, "unitPrice": 49.75 } ]
  }
}
```

Rules:
1. **Add, never remove or repurpose.** New optional fields only. Consumers ignore unknown fields (*tolerant reader*).
2. **Breaking change = new message type/version** (`OrderPlacedV2`), publish both until all consumers migrate, then retire the old one.
3. **Never reuse a Protobuf field number or Avro field name with a new meaning.**
4. Include metadata: `messageId` (dedup), `correlationId` (trace the business flow), `causationId`, `occurredAtUtc`, `type`, `version`.
5. Use a **schema registry** (Confluent Schema Registry with Avro/Protobuf/JSON Schema) to enforce compatibility modes (backward, forward, full) in CI.
6. Share contracts through a versioned NuGet package or contract repository; consumers pin versions. Avoid sharing domain classes.
7. Put the partition/session key in the contract's design (e.g., `OrderId`) — it determines ordering.

### Dead-letter queues and poison messages

**Definition.** A *poison message* can never be processed successfully (bad payload, missing reference data, bug). If you retry it forever, it blocks the queue (or its Kafka partition) and burns CPU. A **dead-letter queue (DLQ)** parks it for inspection so the flow continues.

```text
message -> consumer -- ok --------------------------------> ack
              |
              '-- fail -> immediate retry (x3)
                         -> delayed retry (1m, 5m, 30m: scheduled message / retry topic)
                            -> still failing? -> DLQ  + alert
                                                 |
                       fix bug / data  <---------'  -> replay from DLQ (redrive)
```

Practical design:
- Classify failures: **transient** (timeout, 503, deadlock) retry with backoff; **permanent** (validation, deserialization, business rule) dead-letter immediately.
- Keep the reason and exception in headers/properties; keep the original message untouched.
- **Alert on DLQ depth > 0.** An unmonitored DLQ is a silent data-loss bug.
- Provide a *redrive* tool (re-publish to the original queue) after the fix. Handlers must be idempotent because a redriven message can repeat work.
- Kafka: no built-in DLQ — publish to `orders.placed.DLT` (and retry topics `.retry-5m`) from the consumer, then commit the offset so the partition moves on.
- RabbitMQ: set `x-dead-letter-exchange` on the queue (and `x-delivery-limit` on quorum queues) so rejected/expired messages are routed to a DLQ.

:::scenario Duplicate messages: a customer is charged twice
**Situation.** The broker redelivered `OrderPlaced` because the Billing consumer crashed after charging the card but before acking. The customer sees two charges.

**Why.** At-least-once delivery means duplicates are normal, not exceptional.

**Fix.** Make the handler idempotent: (1) use the `MessageId`/`OrderId` as an idempotency key in an *inbox* table with a unique index, inserted in the same DB transaction as the business change; (2) pass the idempotency key to the payment provider (Stripe `Idempotency-Key`); (3) enable broker-side duplicate detection (Service Bus) as an extra layer. See the Idempotency and Inbox topics.
:::

:::scenario A poison message blocks the queue
**Situation.** One malformed `OrderPlaced` makes the consumer throw; with commit-after-success the offset never advances, so it is retried forever, and orders behind it in the same Kafka partition stall (consumer lag grows).

**Fix.** Separate transient from permanent errors; bounded retries with backoff; after N attempts publish the record plus error metadata to a dead-letter topic and commit the offset; alert on DLT traffic and consumer lag; fix and replay.
:::

:::q RabbitMQ vs Kafka — when would you choose each?
RabbitMQ when I need flexible routing and task/command queues with per-message ack, priorities and moderate scale. Kafka when I need a durable, replayable event stream with very high throughput and several independent consumer groups reading the same data. Kafka gives per-partition ordering and replay but no per-message ack/DLQ; RabbitMQ gives the opposite.
:::

:::q How do you guarantee ordering?
Ordering is only guaranteed within a unit: a Kafka partition, a Service Bus session, a single RabbitMQ queue with one consumer. I choose a key (OrderId) so related messages land in the same unit, process them serially per key, and design handlers to tolerate out-of-order arrival using version numbers or timestamps anyway.
:::
