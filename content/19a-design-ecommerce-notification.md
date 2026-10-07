## System Design Interview Approach

**Definition.** A system design round asks you to design a product-scale system on a whiteboard in about 45 minutes. There is no single right answer. The interviewer scores *how you think*: clarifying, estimating, choosing trade-offs, and going deep where it is hard.

**Why it matters.** For 2-5 years of experience the bar is not "invent Netflix". It is: can you break a vague problem into requirements, pick sensible .NET/Azure building blocks, and explain failure handling. The same 8-step template below is used for all seven designs in this section.

| Step | Minutes | What you say / draw |
|---|---|---|
| 1. Requirements | 5 | Ask clarifying questions. List functional + non-functional (scale, latency, availability, consistency). |
| 2. Capacity estimation | 3-5 | DAU, QPS (avg and peak), storage per year. Show the arithmetic. |
| 3. API design | 5 | 4-6 REST endpoints with request/response JSON. |
| 4. Data model | 5 | Tables/collections, keys, indexes. Say SQL vs NoSQL and why. |
| 5. High-level design | 8-10 | Boxes and arrows. Walk one request end to end. |
| 6. Deep dives | 10-12 | The 2 hardest parts, with code-level detail. |
| 7. Scale, failures, trade-offs | 5 | Bottlenecks, SPOFs, what you would do at 10x. |
| 8. Wrap-up | 1-2 | Summarise, mention what you skipped and why. |

:::warn Numbers in this section are illustrative
All QPS and storage figures here are back-of-envelope assumptions to teach the method. In an interview, state your assumptions aloud ("let's assume 1M DAU") and let the interviewer correct them. Round aggressively: 1 day is about 100,000 seconds (86,400), peak is usually 3-10x average.
:::

#### Estimation cheat sheet

```text
1 day            = 86,400 s  (~100K s for quick maths)
1M req/day       = ~12 req/s average
100M req/day     = ~1,200 req/s average
Peak factor      = 3x - 10x average (flash sale: 50x+)
1 KB x 1M rows   = ~1 GB
1 char (UTF-8)   = 1 byte (ASCII) ... 4 bytes
Reads : writes   = browse sites 100:1, chat 1:1, logging 1:100
```

## Design 1: E-Commerce System

Running flow from the outline: *User -> API Gateway -> Auth Service -> Product Service -> Order Service -> Payment Service -> Database*.

### 1. Requirements

**Clarifying questions to ask.** B2C or marketplace (multi-seller)? Which regions and currencies? Do we need search with filters? Guest checkout? Is stock tracked per warehouse? Expected peak events (flash sale, Black Friday)? Which payment gateway?

**Functional requirements**
- Browse and search products, view product detail.
- Cart (add/update/remove), checkout, place order.
- Pay for an order (card/UPI/wallet through a gateway).
- Order history, status tracking, cancellation.
- Inventory decrement without overselling.
- Notifications (order confirmed, shipped).

**Non-functional requirements**
- Availability 99.9%+ for browse, *correctness over availability* for checkout/inventory.
- Browse latency p95 < 200 ms, search < 500 ms.
- Scale: 1M DAU, 10x spikes on sale days.
- Orders must never be lost or double-charged. Strong consistency inside a service, eventual consistency between services.
- Secure: PCI scope minimised (card data never touches our servers), JWT-based auth.

### 2. Capacity estimation (illustrative)

| Item | Assumption | Result |
|---|---|---|
| DAU | 1M users, 20 product views/day | 20M views/day = ~230 QPS avg, ~1,200 QPS peak |
| Search | 5M searches/day | ~58 QPS avg, ~300 peak |
| Orders | 100K orders/day | ~1.2 orders/s avg, ~12/s peak (flash sale: 5,000 checkout attempts/s for a few minutes) |
| Catalog | 1M SKUs x 5 KB | ~5 GB in DB, images 1M x 5 x 500 KB = ~2.5 TB in Blob + CDN |
| Orders storage | 100K/day x 2 KB | ~200 MB/day = ~73 GB/year |

Conclusion to say aloud: *reads dominate 100:1, so cache catalog aggressively; writes are small, so one SQL primary per service is fine; flash sales are the real scaling problem.*

### 3. API design

```text
GET  /api/v1/products?category=phones&q=iphone&page=1&pageSize=20
GET  /api/v1/products/{id}
PUT  /api/v1/cart/items/{productId}     (auth)
GET  /api/v1/cart                        (auth)
POST /api/v1/checkout                    (auth, Idempotency-Key header)
GET  /api/v1/orders/{orderId}            (auth)
POST /api/v1/orders/{orderId}/cancel     (auth)
```

```json
// POST /api/v1/checkout   Idempotency-Key: 6f1c...  (client-generated GUID)
{ "cartId": "c-123", "shippingAddressId": "a-9", "paymentMethodToken": "tok_abc" }

// 202 Accepted  (saga runs asynchronously; client polls or gets a push)
{ "orderId": "o-7788", "status": "PendingPayment",
  "links": { "self": "/api/v1/orders/o-7788" } }

// GET /api/v1/orders/o-7788 -> 200
{ "orderId": "o-7788", "status": "Confirmed", "total": 1499.00, "currency": "INR",
  "items": [ { "productId": 42, "sku": "PH-42", "qty": 1, "unitPrice": 1499.00 } ] }
```

### 4. Data model

Each service owns its database (database-per-service). Cart lives in Redis (fast, TTL), not SQL.

```sql
-- Catalog DB
CREATE TABLE Products (
  ProductId   BIGINT IDENTITY PRIMARY KEY,
  Sku         NVARCHAR(40)  NOT NULL UNIQUE,
  Name        NVARCHAR(200) NOT NULL,
  CategoryId  INT           NOT NULL,
  Price       DECIMAL(18,2) NOT NULL,
  Currency    CHAR(3)       NOT NULL,
  IsActive    BIT           NOT NULL DEFAULT 1
);
CREATE INDEX IX_Products_Category ON Products (CategoryId, IsActive)
  INCLUDE (Name, Price);                  -- covering index for listing pages

-- Inventory DB
CREATE TABLE Inventory (
  ProductId  BIGINT PRIMARY KEY,
  OnHand     INT NOT NULL CHECK (OnHand   >= 0),
  Reserved   INT NOT NULL CHECK (Reserved >= 0),
  RowVersion ROWVERSION                    -- optimistic concurrency token
);
CREATE TABLE InventoryReservations (
  ReservationId UNIQUEIDENTIFIER PRIMARY KEY,
  OrderId       UNIQUEIDENTIFIER NOT NULL,
  ProductId     BIGINT NOT NULL,
  Quantity      INT NOT NULL,
  Status        TINYINT NOT NULL,          -- 0 Held, 1 Committed, 2 Released
  ExpiresAtUtc  DATETIME2 NOT NULL
);
CREATE INDEX IX_Res_Expiry ON InventoryReservations (Status, ExpiresAtUtc);

-- Order DB
CREATE TABLE Orders (
  OrderId        UNIQUEIDENTIFIER PRIMARY KEY,
  CustomerId     BIGINT NOT NULL,
  Status         TINYINT NOT NULL,
  Total          DECIMAL(18,2) NOT NULL,
  Currency       CHAR(3) NOT NULL,
  IdempotencyKey UNIQUEIDENTIFIER NOT NULL,
  CreatedAtUtc   DATETIME2 NOT NULL,
  CONSTRAINT UQ_Orders_Idem UNIQUE (CustomerId, IdempotencyKey)
);
CREATE INDEX IX_Orders_Customer ON Orders (CustomerId, CreatedAtUtc DESC);
CREATE TABLE OrderItems (
  OrderId UNIQUEIDENTIFIER, LineNo INT, ProductId BIGINT, Sku NVARCHAR(40),
  UnitPrice DECIMAL(18,2), Quantity INT,
  PRIMARY KEY (OrderId, LineNo)           -- price snapshot: never join to live price
);
CREATE TABLE OutboxMessages (             -- transactional outbox
  Id UNIQUEIDENTIFIER PRIMARY KEY, Type NVARCHAR(200), Payload NVARCHAR(MAX),
  CreatedAtUtc DATETIME2, ProcessedAtUtc DATETIME2 NULL
);
```

Search is a separate read model: Azure AI Search or Elasticsearch, fed from catalog change events.

### 5. High-level architecture

```text
 Browser / Mobile
       |
   CDN (images, static)          Azure Front Door / WAF
       |
  API Gateway (YARP / APIM)  --- rate limit, JWT validation
       |
 +-----+--------+--------------+---------------+----------------+
 |              |              |               |                |
Auth/Identity  Catalog       Cart           Order/Checkout    Payment
 (IdP)         Service       Service        (saga orchestr.)  Service
 |              |  \          |                |   |             |
 |          SQL + Redis   Azure AI Search     Redis  \          Gateway
 |          (cache-aside)  (search model)  (cart)   SQL (Orders) (Stripe/Razorpay)
 |                                                    |
 |                                          Service Bus topic: order-events
 |                                    +---------+---------+----------+
 |                                    |         |         |          |
 |                               Inventory  Notification Shipping  Search
 |                               Service    Service      Service   indexer
 |                               (SQL)
```

**Walk one request.** `POST /checkout` hits the gateway, JWT is validated, Order service creates the order (`Pending`) and writes an outbox row in one SQL transaction. The saga reserves stock, charges payment, confirms the order, and publishes `OrderConfirmed`. Notification, shipping and search react to events.

### 6. Deep dives

#### 6a. Preventing overselling

Two stock levels: `OnHand` (physical) and `Reserved` (held by pending checkouts). Available = `OnHand - Reserved`. The classic bug is *read, check in C#, then write* (two requests both read 1 and both succeed).

**Option 1: single atomic conditional UPDATE (best for hot rows).**

```csharp
public async Task<bool> TryReserveAsync(long productId, int qty, CancellationToken ct)
{
    // Check and change in ONE statement. SQL Server takes a row lock, so two
    // concurrent callers are serialised; the second sees the updated value.
    int rows = await _db.Database.ExecuteSqlInterpolatedAsync($@"
        UPDATE Inventory
           SET Reserved = Reserved + {qty}
         WHERE ProductId = {productId}
           AND OnHand - Reserved >= {qty}", ct);
    return rows == 1;                       // 0 rows => insufficient stock
}
```

**Option 2: optimistic concurrency with EF Core (`rowversion`).** Good when contention is low.

```csharp
public class InventoryItem
{
    public long ProductId { get; set; }
    public int OnHand { get; set; }
    public int Reserved { get; set; }
    [Timestamp] public byte[] RowVersion { get; set; } = default!;
}

public async Task<bool> ReserveOptimisticAsync(long id, int qty, CancellationToken ct)
{
    for (int attempt = 0; attempt < 3; attempt++)
    {
        var item = await _db.Inventory.SingleAsync(i => i.ProductId == id, ct);
        if (item.OnHand - item.Reserved < qty) return false;
        item.Reserved += qty;
        try { await _db.SaveChangesAsync(ct); return true; }
        catch (DbUpdateConcurrencyException)
        {
            _db.Entry(item).State = EntityState.Detached;   // reload and retry
        }
    }
    return false;
}
```

**Reservation with TTL.** A held reservation expires (e.g. 10 min) so abandoned checkouts free stock. A background `BackgroundService` runs `UPDATE ... SET Status=2` for expired `Held` rows and decrements `Reserved`. Stock moves `Reserved -> OnHand decrement` only when payment succeeds (commit).

| Strategy | Pros | Cons |
|---|---|---|
| Conditional UPDATE | Simple, correct, fast | Hot row contention on one SKU |
| Optimistic (`rowversion`) | No locks held | Retry storms under high contention |
| Pessimistic (`UPDLOCK`) | Predictable | Blocks, deadlock risk, low throughput |
| Redis atomic counter + async DB sync | Very high throughput | Two sources of truth; reconcile |

#### 6b. Checkout saga (orchestration)

There is no distributed transaction across Inventory, Payment and Order. A *saga* is a sequence of local transactions with a *compensating action* for each step. Orchestrated sagas are easier to reason about and to monitor than choreography for a 3-5 step flow. In production use MassTransit state machines, NServiceBus, or Durable Functions; the logic is the same as below. (See the *Microservices* section for saga theory.)

```csharp
public sealed class CheckoutSaga(
    IInventoryClient inventory, IPaymentClient payments,
    IOrderRepository orders, ILogger<CheckoutSaga> log)
{
    public async Task<OrderStatus> RunAsync(
        Order order, string payToken, CancellationToken ct)
    {
        var undo = new Stack<Func<Task>>();              // compensations, LIFO
        try
        {
            await inventory.ReserveAsync(order.Id, order.Lines, ct);
            undo.Push(() => inventory.ReleaseAsync(order.Id, CancellationToken.None));

            var pay = await payments.ChargeAsync(order.Id, order.Total, payToken, ct);
            undo.Push(() => payments.RefundAsync(pay.PaymentId, CancellationToken.None));

            await orders.MarkConfirmedAsync(order.Id, ct);   // + outbox: OrderConfirmed
            await inventory.CommitAsync(order.Id, ct);
            return OrderStatus.Confirmed;
        }
        catch (Exception ex)
        {
            log.LogWarning(ex, "Checkout failed for {OrderId}, compensating", order.Id);
            while (undo.TryPop(out var compensate))
                await compensate();                         // must be idempotent + retried
            await orders.MarkFailedAsync(order.Id, ex.Message, CancellationToken.None);
            return OrderStatus.Failed;
        }
    }
}
```

Rules for sagas: every step and every compensation must be **idempotent** (keyed by `OrderId`), saga state must be **persisted** (so a crash resumes), and messages are published through the **transactional outbox** so "update DB" and "publish event" cannot diverge.

#### 6c. Flash-sale handling

Problem: 100K users hit one SKU with 500 units. SQL row contention melts the DB and 99.5% of requests are doomed anyway.

1. **Pre-warm** stock into Redis `stock:{sku}` before the sale; serve the product page from CDN/Redis.
2. **Admission control** at the gateway: rate limit per user/IP; optional *virtual waiting room* (queue token) so only N users per second proceed.
3. **Atomic decrement in Redis** (Lua) to reject fast when sold out; only winners reach the saga.
4. **Queue the orders** (Service Bus / Kafka) and process at the DB's pace; return `202 Accepted`.
5. **Reconcile** Redis vs SQL after the sale.

```csharp
private static readonly LuaScript TakeStock = LuaScript.Prepare(@"
    local stock = tonumber(redis.call('GET', @key))
    if stock == nil or stock < tonumber(@qty) then return -1 end
    return redis.call('DECRBY', @key, @qty)");

public async Task<bool> TryTakeAsync(string sku, int qty)
{
    var result = (long)await _redis.GetDatabase().ScriptEvaluateAsync(
        TakeStock, new { key = (RedisKey)$"stock:{sku}", qty });
    return result >= 0;      // -1 = sold out -> respond 409 immediately
}
```

### 7. Scaling, failure modes, trade-offs

| Concern | Approach |
|---|---|
| Catalog reads | CDN + Redis cache-aside + read replicas; invalidate on product-updated event |
| Search | Dedicated search index (not SQL `LIKE`); eventually consistent |
| Order DB growth | Partition by month, archive old orders to cheap storage |
| Payment gateway down | Circuit breaker; keep order `PendingPayment`; retry later; never double-charge (idempotency key) |
| Service crash mid-saga | Persisted saga state + outbox + idempotent steps; a recovery job resumes stuck sagas |
| Price changed mid-checkout | Snapshot price into `OrderItems`; re-validate at checkout start |
| Cart | Redis with TTL; merge guest cart on login |

**Trade-offs to state.** Microservices give independent scaling but add distributed-transaction complexity; for a small team a *modular monolith* with the same module boundaries is a legitimate first answer. Eventual consistency between catalog and search is acceptable; inventory-at-checkout is not.

:::tip How to present this in 45 minutes
Spend the first 5 minutes agreeing scope ("I'll skip returns and recommendations"). Draw the happy path first, then spend your deep-dive time on **overselling + saga + flash sale**, because those separate candidates. Always say "database per service, events through an outbox". Name the consistency choice for each boundary.
:::

:::q Follow-up 1: How do you handle a payment that succeeds but the order service crashes before saving?
The payment call carries the `OrderId` as an idempotency key, and the saga state is persisted before the call. On restart a recovery job finds the order in `PendingPayment`, queries the gateway by `OrderId`, sees the charge succeeded, and moves the order forward. A nightly reconciliation job catches anything missed.
:::

:::q Follow-up 2: How would you support multiple warehouses?
Inventory key becomes `(ProductId, WarehouseId)`. An allocation step picks warehouses (nearest-first or split shipment) and reserves per warehouse. The reservation row stores the warehouse. The same conditional-UPDATE pattern applies per row.
:::

:::q Follow-up 3: How do you keep search results in sync with the catalog?
Catalog publishes `ProductChanged` events through the outbox. A search-indexer consumer upserts into Azure AI Search or Elasticsearch. It is eventually consistent (seconds), and a periodic full reindex repairs drift. Price and stock are re-read from the source of truth at add-to-cart and checkout.
:::

## Design 2: Notification Service

Channels from the outline: Email, SMS, Push, with Queue, Retry, Dead-letter queue.

### 1. Requirements

**Clarifying questions.** Who are the producers (internal services only, or public API)? Transactional (OTP, receipt) vs marketing/bulk? Which channels and providers? Do users set preferences and quiet hours? Required delivery guarantee: at-least-once (duplicates tolerated with dedup) is the realistic answer. Multi-language templates?

**Functional**
- Producers send a notification request (user, template, data, channels, priority).
- Deliver over Email/SMS/Push (extensible to WhatsApp, in-app).
- Templates with variables and locales; user channel preferences and opt-out.
- Retry transient failures; dead-letter permanent ones; track delivery status.
- Schedule/delay and bulk campaigns.

**Non-functional**
- OTP latency < 5 s end to end; marketing can lag minutes.
- Throughput: absorb campaign bursts without hurting OTPs (separate priority queues).
- At-least-once delivery + deduplication; no user receives the same OTP twice.
- Provider failures must not lose messages.

### 2. Capacity estimation (illustrative)

50M notifications/day, split: 10M transactional, 40M marketing. Average = 50M / 86,400 = ~580/s. Peak campaign burst 10x = ~6,000/s. Provider limits (e.g. 100 msg/s per SMS account) become the true bottleneck, so the queue acts as a shock absorber. Storage: 50M x 500 B status rows = 25 GB/day; keep 30 days hot (750 GB), archive after.

### 3. API design

```json
// POST /api/v1/notifications        Idempotency-Key: ord-7788-confirmed
{
  "userId": "u-42",
  "templateId": "order-confirmed",
  "locale": "en-IN",
  "channels": ["email", "push"],
  "priority": "high",
  "data": { "orderId": "o-7788", "total": "1,499.00" },
  "sendAfterUtc": null
}
// 202 Accepted
{ "notificationId": "n-9f3a", "status": "Queued" }

// GET /api/v1/notifications/n-9f3a
{ "notificationId": "n-9f3a",
  "deliveries": [
    { "channel": "email", "status": "Delivered", "providerId": "sg-123" },
    { "channel": "push",  "status": "Failed", "reason": "DeviceTokenInvalid" } ] }

// PUT /api/v1/users/u-42/preferences
{ "email": true, "sms": false, "push": true,
  "quietHours": { "from": "22:00", "to": "07:00" } }

// POST /webhooks/providers/sendgrid     (provider -> us; signature verified)
```

### 4. Data model

```sql
CREATE TABLE Templates (
  TemplateId NVARCHAR(60), Channel TINYINT, Locale NVARCHAR(10), Version INT,
  Subject NVARCHAR(200) NULL, Body NVARCHAR(MAX), IsActive BIT,
  PRIMARY KEY (TemplateId, Channel, Locale, Version)
);
CREATE TABLE UserPreferences (
  UserId BIGINT PRIMARY KEY, EmailOn BIT, SmsOn BIT, PushOn BIT,
  QuietFrom TIME NULL, QuietTo TIME NULL, TimeZone NVARCHAR(50)
);
CREATE TABLE Notifications (
  NotificationId UNIQUEIDENTIFIER PRIMARY KEY, UserId BIGINT, TemplateId NVARCHAR(60),
  DedupKey NVARCHAR(100) NOT NULL, CreatedAtUtc DATETIME2,
  CONSTRAINT UQ_Notif_Dedup UNIQUE (DedupKey)
);
CREATE TABLE Deliveries (
  DeliveryId UNIQUEIDENTIFIER PRIMARY KEY, NotificationId UNIQUEIDENTIFIER,
  Channel TINYINT, Status TINYINT, Attempts INT, ProviderMessageId NVARCHAR(100),
  LastError NVARCHAR(500), UpdatedAtUtc DATETIME2
);
CREATE INDEX IX_Deliv_Notif ON Deliveries (NotificationId);
CREATE TABLE DeviceTokens (UserId BIGINT, Token NVARCHAR(300), Platform TINYINT,
  PRIMARY KEY (UserId, Token));
```

Status/history tables are write-heavy and time-series-like: Cosmos DB or partitioned SQL tables work. Templates/preferences are small and cacheable.

### 5. High-level architecture

```text
 Producer services (Order, Auth, Billing)
        |  POST /notifications  or  event on Service Bus
        v
 +-----------------------+      +-------------------+
 | Notification API      |----->| Redis: dedup keys,|
 | validate, dedup,      |      | preference cache  |
 | resolve prefs, render |      +-------------------+
 +----------+------------+
            | one message per (notification, channel)
            v
  Service Bus queues:  email-high | email-bulk | sms-high | push-high ...
            |
   +--------+---------+---------------+
   v                  v               v
 Email worker      SMS worker      Push worker      (BackgroundService /
 (SendGrid/ACS)    (Twilio/ACS)    (FCM/APNs/ANH)    Container Apps, scale on queue)
   |   retry w/ backoff + jitter, rate limit per provider
   |
   +--> success: Deliveries = Sent        failure: abandon -> redeliver
   |                                      max deliveries -> Dead-letter queue
   +<-- provider webhooks: Delivered / Bounced / Complained / Opened
                                          |
                                DLQ processor: alert + manual replay tool
```

### 6. Deep dives

#### 6a. Channel strategy (Strategy pattern)

Adding WhatsApp must not touch existing code. Each channel implements one interface, registered in DI by key.

```csharp
public interface INotificationChannel
{
    ChannelType Channel { get; }
    Task<SendResult> SendAsync(RenderedMessage message, CancellationToken ct);
}

public sealed class EmailChannel(IEmailProvider provider) : INotificationChannel
{
    public ChannelType Channel => ChannelType.Email;
    public async Task<SendResult> SendAsync(RenderedMessage m, CancellationToken ct)
    {
        try
        {
            var id = await provider.SendAsync(m.To, m.Subject!, m.Body, ct);
            return SendResult.Ok(id);
        }
        catch (ProviderRateLimitedException) { return SendResult.Transient("429"); }
        catch (InvalidRecipientException ex) { return SendResult.Permanent(ex.Message); }
    }
}

// DI: builder.Services.AddSingleton<INotificationChannel, EmailChannel>(); ...
public sealed class ChannelRouter(IEnumerable<INotificationChannel> channels)
{
    private readonly Dictionary<ChannelType, INotificationChannel> _map =
        channels.ToDictionary(c => c.Channel);
    public INotificationChannel For(ChannelType t) => _map[t];
}
```

The key design choice is the **transient vs permanent** classification: retry the first, dead-letter the second immediately.

#### 6b. Queue consumer: retry with backoff, jitter and DLQ

Azure Service Bus gives per-message delivery count and a built-in dead-letter sub-queue. A simple robust pattern: on transient failure, *schedule a copy with a delay* (exponential backoff + jitter) and complete the original; on permanent failure or too many attempts, dead-letter with a reason.

```csharp
public sealed class EmailWorker(ServiceBusClient bus, ChannelRouter router,
    IDeliveryStore store, ILogger<EmailWorker> log) : BackgroundService
{
    private const int MaxAttempts = 6;

    protected override async Task ExecuteAsync(CancellationToken stop)
    {
        var processor = bus.CreateProcessor("email-high", new ServiceBusProcessorOptions
        {
            MaxConcurrentCalls = 16, AutoCompleteMessages = false
        });
        processor.ProcessMessageAsync += HandleAsync;
        processor.ProcessErrorAsync += e =>
        { log.LogError(e.Exception, "SB error"); return Task.CompletedTask; };
        await processor.StartProcessingAsync(stop);
        await Task.Delay(Timeout.Infinite, stop).ContinueWith(_ => { });
        await processor.StopProcessingAsync();
    }

    private async Task HandleAsync(ProcessMessageEventArgs args)
    {
        var msg = args.Message.Body.ToObjectFromJson<RenderedMessage>();
        if (await store.IsSentAsync(msg.DeliveryId))                 // idempotent consumer
        { await args.CompleteMessageAsync(args.Message); return; }

        var result = await router.For(ChannelType.Email)
            .SendAsync(msg, args.CancellationToken);

        if (result.Success)
        {
            await store.MarkSentAsync(msg.DeliveryId, result.ProviderId);
            await args.CompleteMessageAsync(args.Message);
        }
        else if (result.IsPermanent || msg.Attempt >= MaxAttempts)
        {
            await store.MarkFailedAsync(msg.DeliveryId, result.Error);
            await args.DeadLetterMessageAsync(args.Message,
                deadLetterReason: result.IsPermanent ? "Permanent" : "MaxAttempts",
                deadLetterErrorDescription: result.Error);
        }
        else
        {
            // exponential backoff 2^n seconds, capped, with full jitter
            var delay = TimeSpan.FromSeconds(Math.Min(300, Math.Pow(2, msg.Attempt))
                                             * Random.Shared.NextDouble());
            var next = msg with { Attempt = msg.Attempt + 1 };
            var retry = new ServiceBusMessage(BinaryData.FromObjectAsJson(next))
            { MessageId = $"{args.Message.MessageId}:{next.Attempt}" };
            await using var sender = bus.CreateSender("email-high");
            await sender.ScheduleMessageAsync(retry, DateTimeOffset.UtcNow + delay);
            await args.CompleteMessageAsync(args.Message);
        }
    }
}
```

Why jitter: if a provider blips and 10,000 messages all retry at exactly +2 s, you create a thundering herd. DLQ handling: an alert fires when DLQ depth > 0; an admin tool lists DLQ messages and replays them after the cause is fixed.

#### 6c. Templates, preferences, deduplication

```csharp
// Template rendering with Scriban (or Razor/Handlebars). Cache parsed templates.
// Body example: "Hi {{ name }}, order {{ order_id }} is confirmed"
var template = Template.Parse(row.Body);
string body = await template.RenderAsync(new { name = user.Name, order_id = data.OrderId });

// Preference + quiet hours check before enqueuing
bool Allowed(UserPrefs p, ChannelType c, DateTime utcNow, Priority prio)
{
    if (prio == Priority.Critical) return true;     // OTP/security bypass quiet hours
    if (!p.IsOn(c)) return false;
    var local = TimeZoneInfo.ConvertTimeFromUtc(utcNow, p.TimeZone);
    return !p.InQuietHours(TimeOnly.FromDateTime(local)); // else delay to end of quiet hrs
}

// Deduplication: first writer wins. Key = idempotency key from producer.
bool first = await redis.StringSetAsync(
    $"dedup:{key}", "1", TimeSpan.FromHours(24), When.NotExists);
if (!first) return Results.Accepted(existingStatusUrl);   // duplicate request, same answer
```

Dedup in layers: producer `Idempotency-Key` (Redis `SET NX`), unique constraint on `DedupKey` in SQL as the source of truth, Service Bus duplicate detection on `MessageId`, and an idempotent consumer (check `Deliveries.Status` before sending). OTPs and marketing use *different queues*, so a campaign never delays an OTP.

### 7. Scaling, failure modes, trade-offs

- **Scale workers on queue length** (KEDA / Azure Container Apps scaling rule). One queue per channel and priority.
- **Provider limits:** token-bucket per provider in the worker (`System.Threading.RateLimiting`); fail over to a secondary provider (SendGrid -> Azure Communication Services) via circuit breaker.
- **At-least-once means duplicates are possible** (worker crashes after provider send, before `Complete`). Mitigate with provider-side idempotency keys where available plus the Deliveries check. True exactly-once to a user's phone is not achievable; say so.
- **Poison messages** go to DLQ after `MaxDeliveryCount`; never block the queue.
- **Bulk sends:** fan-out job reads a segment in pages and enqueues in batches (`ServiceBusMessageBatch`), not one giant message.
- **Push:** remove invalid tokens when FCM returns `UNREGISTERED`.
- **Compliance:** unsubscribe link, consent records, PII minimised in logs.

:::tip How to present this in 45 minutes
Open with "at-least-once + idempotent consumers" and "transient vs permanent errors". Draw the queue per channel/priority. Deep-dive: retry/backoff/DLQ and dedup. Mention webhooks for delivery status; many candidates forget that "provider accepted" is not "user received".
:::

:::q Follow-up 1: How do you guarantee an OTP is not delayed by a marketing campaign?
Separate queues and separate worker pools per priority, with their own provider quotas. Marketing is rate limited at the producer fan-out job and consumed by lower-priority workers. OTPs also skip quiet-hour checks.
:::

:::q Follow-up 2: A provider is down for 30 minutes. What happens?
Workers get transient errors, the circuit breaker opens, and messages are rescheduled with backoff, or the router fails over to the secondary provider. Queue depth rises and absorbs the outage; nothing is lost. After recovery the backlog drains at the rate limit.
:::

:::q Follow-up 3: How do you replay dead-lettered messages safely?
Fix the root cause first, then a replay tool reads the DLQ, resets the attempt counter, and resubmits to the main queue. Because consumers are idempotent (`DeliveryId` check), replaying a message that actually succeeded earlier does no harm.
:::

