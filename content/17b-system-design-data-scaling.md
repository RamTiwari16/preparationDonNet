## Database Design

### Database selection: SQL vs NoSQL

**Definition.** *Relational (SQL)* databases store rows in tables with a fixed schema, joins and ACID transactions (SQL Server, PostgreSQL, Azure SQL). *NoSQL* is a family of non-relational stores optimised for specific access patterns, flexible schemas and horizontal scale.

**Why it matters.** "Which database and why?" is asked in every HLD round. Choose from **access patterns, consistency needs and scale** — not fashion.

| | SQL (relational) | NoSQL |
|---|---|---|
| Schema | fixed, enforced | flexible / schema-on-read |
| Relationships | joins, foreign keys | denormalised, embedded, or app-side joins |
| Transactions | multi-row/multi-table ACID | usually single-document/partition (some support more) |
| Scaling | vertical first; read replicas; sharding is manual/hard | horizontal by design (partition key) |
| Query flexibility | ad-hoc SQL, aggregations | fast for designed access paths, weak for ad-hoc |
| Consistency | strong | tunable (often eventual by default) |
| Best for | orders, payments, inventory, anything relational with integrity rules | huge scale, simple access by key, flexible/nested data, high write rates |

**NoSQL families decision table:**

| Type | Data model | Examples | Great for | Not for |
|---|---|---|---|---|
| Key-value | key -> blob | Redis, DynamoDB, Azure Table | cache, sessions, carts, counters, feature flags | queries by value, relationships |
| Document | JSON documents | Cosmos DB (NoSQL API), MongoDB | catalogues, user profiles, content, per-aggregate storage | many-to-many joins, cross-document transactions at scale |
| Wide-column | rows with dynamic columns grouped by partition | Cassandra, ScyllaDB, HBase, Bigtable | time-series, IoT, messaging, write-heavy at huge scale | ad-hoc queries, strong multi-row consistency |
| Graph | nodes + edges | Neo4j, Cosmos DB Gremlin | social graphs, recommendations, fraud rings | bulk analytics, simple CRUD |
| Search | inverted index | Elasticsearch, Azure AI Search | full-text, faceted search, logs | primary store of record |
| Time-series | timestamped points | InfluxDB, Azure Data Explorer, TimescaleDB | metrics, telemetry | transactional data |

**Polyglot persistence** in one system is normal: SQL for orders, Redis for carts, Cosmos DB for catalogue, Elasticsearch for search, Blob for media.

:::tip The safe default answer
"I start with a relational DB for the core transactional data because I need integrity and transactions. I add specialised stores for specific access patterns: Redis for caching, a search index for full text, blob storage for media, and a NoSQL store when a single partition key fits the access pattern and scale exceeds what one SQL server can handle."
:::

### Normalization vs denormalization

**Normalization** removes redundancy by splitting data into related tables (1NF: atomic values; 2NF: no partial dependency on a composite key; 3NF: no transitive dependency). Benefits: one place to update, integrity, smaller writes. Cost: joins on read.

**Denormalization** deliberately duplicates data to make reads fast: storing `CustomerName` on `Orders`, precomputed `OrderCount`, a JSON document with embedded lines, materialised/indexed views, read models.

| | Normalized | Denormalized |
|---|---|---|
| Writes | simple, one place | must update copies (or accept staleness) |
| Reads | joins | single lookup |
| Integrity | enforced by FKs | app/event responsibility |
| Fits | OLTP, write-heavy, correctness | read-heavy, analytics (star schema), NoSQL, CQRS read side |

Rule of thumb: normalise the write model (to ~3NF), denormalise the read model where measurements show joins hurt. Snapshots that *should not* change (price at purchase time on an order line) are not redundancy — they are history.

### Indexing in system design

Indexes trade write cost and storage for read speed. For HLD say: "Queries by `UserId` and `CreatedAt` need a composite index `(UserId, CreatedAt DESC)`; that turns the feed query into a range seek." Mention covering indexes (INCLUDE columns), avoiding over-indexing on write-heavy tables, secondary indexes in NoSQL (Cosmos DB indexes everything by default, DynamoDB GSIs are eventually consistent), and search indexes for text. (Deep dive in the SQL Server section.)

### Replication and read replicas

**Definition.** Keeping copies of the same data on multiple nodes for availability, durability and read scaling.

| Model | How | Pros | Cons |
|---|---|---|---|
| **Leader-follower** (primary-replica) | all writes to the leader; followers replay its log | simple, read scaling, failover | leader is the write bottleneck; replication lag |
| **Multi-leader** | several nodes accept writes (often one per region) | local writes in each region, survives region loss | **write conflicts** (last-writer-wins, merge, CRDTs) |
| **Leaderless** (Dynamo-style) | client writes to N replicas, quorum W, reads R; W + R > N for overlap | high availability, no failover | complex consistency, read repair |

**Synchronous vs asynchronous replication.** Sync: commit waits for the replica (no data loss on failover, higher latency). Async: commit returns immediately (fast, but recent writes may be lost on failover and replicas lag).

**Read replicas** (Azure SQL geo-replicas/read scale-out, SQL Server Always On readable secondaries, PostgreSQL replicas) offload reporting and read-heavy queries. **Replication lag** causes anomalies:
- *Read-your-writes violation*: user updates their profile, refreshes, sees the old one. Fix: read from the primary for that user for a few seconds after a write, or use session consistency tokens.
- *Monotonic reads violation*: two refreshes hit different replicas and data "goes back in time". Fix: pin a user to one replica.
- Never read from a replica for a decision that must be current (stock at checkout).

```csharp
// EF Core: route read-only queries to a replica (Azure SQL read scale-out)
builder.Services.AddDbContext<ShopDb>(o => o.UseSqlServer(primaryCs));
builder.Services.AddDbContext<ShopReadDb>(o => o.UseSqlServer(
    primaryCs + ";ApplicationIntent=ReadOnly")                 // goes to a readable secondary
    .UseQueryTrackingBehavior(QueryTrackingBehavior.NoTracking));
```

### Partitioning and sharding

**Definition.** *Partitioning* splits a large table/dataset into smaller pieces. *Vertical partitioning* splits columns (hot columns vs large blobs) or tables into different databases. *Horizontal partitioning* splits rows. When horizontal partitions live on **different servers**, it is called **sharding**. (SQL Server *table partitioning* splits rows within one database for maintenance and partition elimination — it does not add servers.)

**Why shard?** One server cannot hold the data or handle the write throughput. Sharding is the last resort because it costs joins, cross-shard transactions and operational complexity.

| Strategy | How | Pros | Cons |
|---|---|---|---|
| **Range** | `CustomerId 1-1M -> shard 1`, by date | range queries easy; simple | hot shards (new IDs/today's dates all on the last shard) |
| **Hash** | `hash(key) % N` | even distribution | range queries scatter; changing N reshuffles almost everything |
| **Consistent hashing** | key and nodes on a hash ring | adding a shard moves only ~1/N keys | more complex; needs virtual nodes for balance |
| **Directory / lookup** | a lookup table maps key -> shard | flexible, move tenants individually | lookup service is a dependency/SPOF; must be cached |
| **Geo / tenant** | by region or tenant id | data residency, tenant isolation | uneven tenant sizes |

**Choosing the shard key** is the key decision: high cardinality, even distribution, and present in most queries (so queries hit one shard). For an e-commerce order store, `CustomerId` keeps "my orders" on one shard; for a multi-tenant SaaS, `TenantId`.

**Problems:** hot shards (a celebrity, a big tenant — split it or add a random suffix), cross-shard queries (scatter-gather or a separate read model/search index), cross-shard transactions (avoid; sagas), unique constraints across shards (globally unique IDs: GUID v7 / Snowflake IDs), and **resharding** (consistent hashing, logical shards much more than physical — e.g., 1024 logical shards mapped onto 8 servers, so you move whole logical shards).

```text
Consistent hashing ring (with virtual nodes)
            0
     B#2 .  |  . A#1
   .        |        .            key k -> hash(k) -> walk clockwise -> first node
 C#1        |         B#1         adding node D only takes keys between D and its
   .        |        .            predecessor; other keys stay where they are
     A#2 .  |  . C#2
```

```csharp
public sealed class ConsistentHashRing(int virtualNodes = 150)
{
    private readonly SortedDictionary<uint, string> _ring = new();
    private uint[] _positions = [];

    public void AddNode(string node)
    {
        for (var i = 0; i < virtualNodes; i++) _ring[Hash($"{node}#{i}")] = node;
        _positions = _ring.Keys.ToArray();
    }

    public void RemoveNode(string node)
    {
        for (var i = 0; i < virtualNodes; i++) _ring.Remove(Hash($"{node}#{i}"));
        _positions = _ring.Keys.ToArray();
    }

    public string GetNode(string key)
    {
        if (_positions.Length == 0) throw new InvalidOperationException("Ring is empty");
        var idx = Array.BinarySearch(_positions, Hash(key));
        if (idx < 0) idx = ~idx;                    // first position clockwise
        if (idx == _positions.Length) idx = 0;      // wrap around
        return _ring[_positions[idx]];
    }

    private static uint Hash(string s) =>
        BitConverter.ToUInt32(MD5.HashData(Encoding.UTF8.GetBytes(s)), 0);   // stable, not crypto use
}
// var ring = new ConsistentHashRing(); ring.AddNode("redis-a"); ring.AddNode("redis-b");
// ring.GetNode("cart:42")  // Output: "redis-a" or "redis-b", stable across processes
```

Managed options do this for you: Cosmos DB (partition key), Azure SQL Hyperscale/Elastic Database tools (shard map manager), Citus for PostgreSQL, Vitess for MySQL, Redis Cluster (hash slots), Kafka (partitions).

:::q What is the difference between partitioning and sharding?
Partitioning is splitting data into pieces; sharding is horizontal partitioning across separate database servers. SQL Server table partitioning stays on one server (helps maintenance and partition elimination), while sharding adds servers to scale storage and writes, at the cost of cross-shard queries and transactions.
:::

## Building Blocks

### Message queues in system design

**Definition.** A queue/broker stores messages between producers and consumers so they do not need to be available at the same time.

Why add one:
- **Decoupling** — producer does not know/care who consumes; consumers can be added freely.
- **Buffering / load levelling** — absorb spikes (10,000 orders/min during a sale) and process at a steady rate; the DB is not flooded.
- **Async processing** — return `202 Accepted` quickly; send emails, generate invoices, resize images in the background.
- **Reliability** — messages survive consumer crashes; retries and DLQs.
- **Fan-out** — one event, many independent consumers.

**Backpressure** is how a system tells producers to slow down when consumers cannot keep up: bounded queues (reject or block when full), `429` with `Retry-After` at the API, prefetch limits, autoscaling consumers on queue length (KEDA), shedding low-priority work. Without it, queues grow until memory/latency limits break. In .NET, `System.Threading.Channels.Channel.CreateBounded<T>(capacity)` gives in-process backpressure.

See Section 15 for RabbitMQ vs Kafka vs Service Bus, delivery guarantees and DLQs.

### Microservices and API gateway in HLD

In an HLD answer, show services split by business capability, each with its own store, behind an **API gateway** (routing, auth, rate limiting, TLS) and a **load balancer**, communicating synchronously for queries and asynchronously via events for side effects. Name the trade-off: independent scaling and deployment vs distributed-systems complexity (eventual consistency, sagas, observability). For a 45-minute interview, keep the number of services small (3-6) and justify each split. Details in Section 15.

### Rate limiter design

**Definition.** Limits how many requests a client (user, API key, IP) can make in a time window, to protect services from abuse and overload and to enforce plans/quotas.

| Algorithm | How | Pros | Cons |
|---|---|---|---|
| **Fixed window counter** | count per client per minute window | simple, cheap | burst at window edges (2x limit across the boundary) |
| **Sliding window log** | store timestamps of each request; count those in the last 60 s | exact | memory per request |
| **Sliding window counter** | weighted mix of current and previous window counts | accurate enough, cheap | approximation |
| **Token bucket** | bucket of N tokens refilled at rate r; each request takes one | allows controlled bursts; most common (APIs, AWS, Stripe) | two parameters to tune |
| **Leaky bucket** | requests queue and drain at a constant rate | smooth output rate | adds latency; bursts queued/dropped |
| **Concurrency limit** | max N in-flight requests | protects slow resources | not time-based |

Design points:
- **Where**: at the gateway/edge (cheapest rejection), and per service for internal protection.
- **Key**: user id > API key > IP (IPs are shared behind NAT).
- **Distributed state**: counters in Redis so all gateway instances share them; use an atomic Lua script (or `INCR` + `EXPIRE`) to avoid race conditions; local in-memory limits as a fallback if Redis is down (fail open for availability or fail closed for security, decide per API).
- **Response**: `429 Too Many Requests` with `Retry-After` and `X-RateLimit-Limit/Remaining/Reset` headers.
- **Rules**: per plan (free 100/min, pro 1,000/min), per endpoint (login stricter), configurable without deploys.

```csharp
// Distributed token bucket in Redis (atomic Lua script) - used by a gateway middleware
public sealed class RedisTokenBucket(IConnectionMultiplexer mux)
{
    private const string Script = """
        local tokens_key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local refill_per_sec = tonumber(ARGV[2])
        local now_ms = tonumber(ARGV[3])
        local data = redis.call('HMGET', tokens_key, 'tokens', 'ts')
        local tokens = tonumber(data[1]) or capacity
        local ts = tonumber(data[2]) or now_ms
        tokens = math.min(capacity, tokens + (now_ms - ts) / 1000 * refill_per_sec)
        local allowed = 0
        if tokens >= 1 then tokens = tokens - 1; allowed = 1 end
        redis.call('HSET', tokens_key, 'tokens', tokens, 'ts', now_ms)
        redis.call('PEXPIRE', tokens_key, math.ceil(capacity / refill_per_sec * 1000) + 1000)
        return allowed
        """;

    public async Task<bool> TryAcquireAsync(string clientId, int capacity, double refillPerSec)
    {
        var result = await mux.GetDatabase().ScriptEvaluateAsync(Script,
            new RedisKey[] { $"rl:{clientId}" },
            new RedisValue[] { capacity, refillPerSec, DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() });
        return (int)result == 1;
    }
}
```

For a single service, ASP.NET Core's built-in `AddRateLimiter` (fixed/sliding window, token bucket, concurrency) is enough; it is per instance, so divide limits by instance count or use the Redis approach for global limits.

### Consistency models

| Model | Guarantee | Example |
|---|---|---|
| **Strong (linearizable)** | every read sees the latest committed write | single SQL primary, Cosmos DB Strong, etcd |
| **Sequential** | all nodes see operations in the same order (not necessarily real-time) | ordered logs |
| **Causal** | causally related operations are seen in order (reply after the post) | some geo-replicated DBs, comment threads |
| **Read-your-writes** | a client always sees its own writes | Cosmos DB Session level; read from primary after write |
| **Monotonic reads** | a client never sees data go back in time | sticky replica per session |
| **Bounded staleness** | reads lag by at most K versions or T seconds | Cosmos DB Bounded Staleness |
| **Eventual** | replicas converge if writes stop | DNS, Cassandra default, read replicas, caches |

Choose per feature: payments, inventory decrement and seat booking need strong consistency at the point of decision; feeds, like counts, recommendations and search indexes are fine with eventual.

### Idempotency in system design

Every write API that may be retried (mobile networks, gateway timeouts, at-least-once queues) must be idempotent: client-generated **idempotency keys** stored with the result, **unique constraints** on natural keys (one booking per seat per show), conditional updates, and idempotent consumers with an inbox table. Payment providers require it. (Implementation in Section 15.)

### Monitoring and observability in HLD

End every design with "how do we know it works?":
- **Golden signals**: latency (p50/p95/p99), traffic (RPS), errors (rate), saturation (CPU, memory, connection pools, queue depth, consumer lag).
- **RED** for services (Rate, Errors, Duration), **USE** for resources (Utilisation, Saturation, Errors).
- **Business metrics**: bookings/min, payment success rate, checkout conversion — often the fastest outage signal.
- Distributed tracing (OpenTelemetry), structured logs with correlation ids, dashboards per service, **SLO-based alerts** (burn rate) instead of noisy threshold alerts, synthetic probes from several regions, on-call runbooks.

## Worked Example: Movie Ticket Booking API

### 1. Requirements

**Functional (in scope):** browse shows for a movie/city; view seat map for a show; select seats and **hold** them for 10 minutes; pay and confirm booking; receive e-ticket; cancel (refund by policy).
**Out of scope:** reviews, recommendations, dynamic pricing, food add-ons.

**Non-functional:** no double booking (strong consistency on seats); seat-map reads p99 < 200 ms; booking p99 < 1 s excluding the payment provider; 99.95% availability for booking; handle a hot release (a blockbuster opening: 1M users in the first 10 minutes); PCI scope minimised.

### 2. Estimation

```text
Users: 20M MAU, 2M DAU. Normal day: 1M bookings/day -> ~12 bookings/s avg, 100/s peak
Seat-map views: ~20 views per booking -> 20M/day -> 230 QPS avg; blockbuster spike 20,000 QPS
Shows: 5,000 cinemas x 5 screens x 5 shows/day = 125k shows/day, ~200 seats each
Seat rows: 125k x 200 = 25M seat-show rows/day (purge/archive after the show)
Storage: booking ~1 KB -> 1 GB/day -> ~365 GB/year: one SQL database is fine (sharding not
         needed initially; partition by date or city later)
Conclusion: writes are modest; the hard parts are the read spike and seat contention.
```

### 3. API

```text
GET  /v1/movies/{movieId}/shows?city=pune&date=2025-06-01      -> list of shows
GET  /v1/shows/{showId}/seats                                  -> seat map + status
POST /v1/shows/{showId}/holds        { seatIds: [...] }        -> 201 { holdId, expiresAt }
                                     Idempotency-Key header      409 if any seat taken
POST /v1/bookings                    { holdId, paymentMethodToken }  Idempotency-Key
                                                               -> 202 { bookingId, status: Pending }
GET  /v1/bookings/{bookingId}                                  -> status Confirmed/Failed
DELETE /v1/bookings/{bookingId}                                -> cancel + refund
Webhook: POST /v1/payments/webhook (from payment provider)     -> confirm/fail booking
```

### 4. High-level design

```text
 Mobile / Web
     |
 [Front Door: CDN + WAF]  ---- static assets, posters (Blob)
     |
 [API Gateway (YARP/APIM): auth, rate limit, virtual waiting room for hot shows]
     |
     +--> Catalog Service (movies, cinemas, shows) --> SQL + Redis cache (read-heavy)
     |
     +--> Seat/Booking Service ----------------------> SQL Server (seats, holds, bookings)
     |        |   \                                    (strong consistency, unique keys)
     |        |    '--> Redis: seat-map cache per show (short TTL, updated on change)
     |        |
     |        '--publishes--> [Service Bus: BookingConfirmed, HoldExpired, BookingCancelled]
     |
     +--> Payment Service --> Payment provider (Stripe/Adyen, hosted fields: no card data
     |        ^                 touches our servers)  <-- webhook
     |        '-- idempotency keys, outbox
     |
     Consumers of events: Notification (email/SMS e-ticket), Analytics, Search index
     Background: Hold-expiry worker (releases expired holds)
```

### 5. Data model (SQL Server)

```sql
CREATE TABLE ShowSeat (
    ShowId      BIGINT       NOT NULL,
    SeatId      INT          NOT NULL,          -- e.g. row F seat 12
    Status      TINYINT      NOT NULL,          -- 0 Available, 1 Held, 2 Booked
    HoldId      UNIQUEIDENTIFIER NULL,
    HoldExpiresUtc DATETIME2 NULL,
    BookingId   UNIQUEIDENTIFIER NULL,
    RowVer      ROWVERSION,
    CONSTRAINT PK_ShowSeat PRIMARY KEY (ShowId, SeatId)
);
CREATE TABLE Booking (
    BookingId   UNIQUEIDENTIFIER PRIMARY KEY,
    HoldId      UNIQUEIDENTIFIER NOT NULL UNIQUE,  -- one booking per hold (idempotent)
    UserId      BIGINT NOT NULL,
    ShowId      BIGINT NOT NULL,
    Amount      DECIMAL(10,2) NOT NULL,
    Status      TINYINT NOT NULL,                  -- Pending, Confirmed, Failed, Cancelled
    CreatedUtc  DATETIME2 NOT NULL
);
CREATE INDEX IX_ShowSeat_HoldExpiry ON ShowSeat (HoldExpiresUtc) WHERE Status = 1;
```

### 6. Deep dive: holding seats without double booking

The critical section is "these 3 seats become Held by me, or none do". One **atomic conditional update** in a transaction:

```sql
-- @SeatIds as a table-valued parameter; all-or-nothing
BEGIN TRAN;
UPDATE ss SET Status = 1, HoldId = @HoldId,
              HoldExpiresUtc = DATEADD(MINUTE, 10, SYSUTCDATETIME())
FROM ShowSeat ss
JOIN @SeatIds s ON s.SeatId = ss.SeatId
WHERE ss.ShowId = @ShowId
  AND (ss.Status = 0 OR (ss.Status = 1 AND ss.HoldExpiresUtc < SYSUTCDATETIME()));

IF @@ROWCOUNT <> (SELECT COUNT(*) FROM @SeatIds)
    ROLLBACK;            -- someone else got at least one seat -> 409 Conflict
ELSE
    COMMIT;              -- 201 Created { holdId, expiresAt }
```

Why this works: the `WHERE` re-checks availability under the row locks taken by the `UPDATE`, so two concurrent holds cannot both succeed; no distributed lock is needed. Expired holds are reusable immediately (the condition treats them as free) and a background worker also resets them and publishes `HoldExpired` to refresh caches.

**Payment and confirmation:**
1. `POST /bookings` with `holdId` + `Idempotency-Key` -> insert `Booking(Pending)` (unique `HoldId` prevents duplicates), create a payment intent with the provider using the booking id as idempotency key, return `202`.
2. Provider webhook (or client confirmation) -> Payment service verifies signature, publishes `PaymentSucceeded` via outbox.
3. Booking service: in one transaction, if the hold is still valid set seats `Booked` and booking `Confirmed`; publish `BookingConfirmed` (outbox) -> Notification sends the e-ticket.
4. If the hold expired before payment completed (slow payment) -> automatic refund (compensation) or extend holds while a payment is in progress (`Status = PaymentPending` prevents expiry).

**Seat-map reads (20k QPS spike):** cache the seat map per show in Redis (one hash per show: `seat -> status`) updated on each hold/booking event and with a 1-2 s TTL fallback; clients poll every few seconds or receive SignalR pushes. The seat map can be slightly stale — the **hold** call is the source of truth and returns `409` if a seat was taken.

**Hot release / flash crowd:** a **virtual waiting room** at the gateway admits users at a rate the booking service can handle (token per user in Redis, queue position shown), per-user rate limits, autoscaling of stateless services, pre-warmed caches, and CDN for everything static.

### 7. Bottlenecks and trade-offs

- **Single SQL database**: fine for writes at this scale; scale up + read replicas for browsing queries; future partitioning by city/region (shows never span cities, so cross-shard transactions are not needed).
- **Consistency vs availability**: seats are CP (we reject rather than double-book); catalogue and seat maps are AP (cached, eventually consistent).
- **Redis down**: seat map falls back to the DB with rate limiting; holds still work (they never depended on Redis).
- **Payment provider slow/down**: circuit breaker, show "try again", holds extended during in-flight payments, reconciliation job compares provider settlements to bookings daily.
- **Monitoring**: hold success/conflict ratio, hold-to-booking conversion, payment success rate, p99 of hold API, waiting-room queue length, Service Bus DLQ depth.
- **Next steps if asked**: multi-region active-passive with geo-replication for DR (RPO seconds), dynamic pricing service, fraud checks.

:::tip How to present this in the interview
Spend most time on the seat hold (the correctness problem) and the hot-release spike (the scale problem). Those are the two things the interviewer is testing; the catalogue is CRUD and needs one sentence.
:::

## Quick-fire Q&A

:::q How do you start a system design interview?
Clarify functional and non-functional requirements, agree scope, then estimate scale (QPS, storage, read/write ratio). Only then propose APIs, a simple high-level design, the data model, and deep-dive into the hardest parts while stating trade-offs.
:::

:::q Vertical vs horizontal scaling?
Vertical adds CPU/RAM to one machine: simple but capped and a single point of failure. Horizontal adds machines behind a load balancer: near-unlimited and fault-tolerant, but needs stateless services or partitioned state. I scale app tiers horizontally and databases vertically first, then with replicas and sharding.
:::

:::q What does 99.99% availability mean in practice?
About 52 minutes of downtime per year, or 4.4 minutes per month. Reaching it needs redundancy across zones, automatic failover, safe deployments and fast detection; also, components in series multiply, so every dependency must be better than the target.
:::

:::q L4 vs L7 load balancer?
L4 routes TCP/UDP connections by IP and port, very fast and protocol-agnostic. L7 understands HTTP, so it can route by path/host/header, terminate TLS, apply WAF rules and sticky cookies. Azure Load Balancer is L4; Application Gateway and Front Door are L7.
:::

:::q Why are sticky sessions a problem?
They pin users to instances, so load becomes uneven, sessions are lost when an instance dies, and scaling in or deploying is harder. I prefer stateless services with tokens or a session store in Redis.
:::

:::q SQL or NoSQL for a new system?
Relational for transactional data with relationships and integrity rules (orders, payments). NoSQL when the access pattern is simple by key and the scale or schema flexibility exceeds what a relational DB handles comfortably, such as catalogues, sessions, telemetry. Often both, each for its access pattern.
:::

:::q What is replication lag and how do you handle it?
Asynchronous replicas apply changes after the primary, so reads from them can be stale. I route reads that must be current (or the user's own recent writes) to the primary, use session consistency, and keep replicas for reports, search and browsing.
:::

:::q How do you choose a shard key?
High cardinality, even distribution, and present in most queries so each query hits one shard: CustomerId for orders, TenantId for SaaS. Avoid monotonically increasing keys with range sharding (hot last shard) and plan for resharding with consistent hashing or many logical shards.
:::

:::q What is consistent hashing?
Keys and nodes are hashed onto a ring; each key belongs to the next node clockwise. Adding or removing a node moves only about 1/N of the keys instead of nearly all, and virtual nodes keep the distribution even. Used by distributed caches, Cassandra and DynamoDB.
:::

:::q When would you add a message queue?
To decouple services, absorb traffic spikes (load levelling), process slow work asynchronously, and fan one event out to several consumers reliably. I mention the costs: eventual consistency, duplicates (idempotent consumers) and the need for DLQ monitoring.
:::

:::q How would you design a rate limiter?
Token bucket per client key (user or API key), counters in Redis updated atomically by a Lua script so all gateway instances share state, rules per plan and endpoint, `429` with `Retry-After`, and a local fallback if Redis is down. Enforce at the gateway first.
:::

:::q p99 vs average latency — why care?
Averages hide the tail. p99 shows what the slowest 1% experience, and with fan-out many user requests hit at least one slow call. SLOs and alerts should be on percentiles.
:::

:::q How do you prevent double booking of the same seat?
Make the database decide: an atomic conditional update (`UPDATE ... WHERE status = Available`) or a unique constraint on (show, seat) in one transaction, with an idempotency key on the API. Caches only show availability; they never decide it.
:::

:::q What is a CDN and when does it help?
A network of edge servers caching content close to users. It cuts latency and origin load for static assets, media and cacheable GET APIs, and absorbs DDoS. Use versioned file names with long TTLs and never cache personalised responses at the edge.
:::
