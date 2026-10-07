### How to run a system design interview

**In simple words:** High Level Design (HLD) shows the big parts of a system — clients, gateways, services, databases, queues, caches and CDNs — and how they work together. In the interview, your process matters more than a memorised diagram. Follow clear steps: requirements, estimation, API, high-level design, data model, deep dive, and finally bottlenecks and trade-offs. Ask questions before you draw, and say your trade-offs out loud.

**Real-life example:** An architect first asks how many people will live in the house and what the budget is. Then they draw the rooms. Only after that do they look at the plumbing details.

**Interview question:** How do you start a system design interview?

**Simple answer:** I clarify the functional and non-functional requirements and agree the scope. Then I estimate the scale: requests per second, storage and the read-to-write ratio. Only then do I propose APIs, a simple design and a data model. I deep-dive into the hardest part and state my trade-offs clearly.

### Requirements gathering: functional vs non-functional

**In simple words:** *Functional* requirements say what the system does, like "users can book a seat". *Non-functional* requirements (NFRs) say how well it does it: scale, latency, availability, consistency, durability, security and cost. Ask for numbers: daily users, peak load, latency targets, and whether old data is acceptable. Choose the top 3 features and write an "out of scope" list.

**Real-life example:** Ordering a birthday cake. "Chocolate with my name on it" is functional. "Serves 50 people, ready by 5 pm, no nuts" is non-functional.

**Interview question:** What is the difference between functional and non-functional requirements?

**Simple answer:** Functional requirements are the features, like booking a seat or viewing a feed. Non-functional ones are qualities, for example 10 million daily users, p99 reads under 200 ms, 99.95% availability and no double booking. NFRs drive most of the architecture, so I ask about them early.

### Back-of-the-envelope estimation

**In simple words:** Quick, rough maths tells you how big the system must be. One day is about 100,000 seconds (really 86,400), so 1 million requests a day is about 12 per second. Peak is usually 2–5 times the average. 1 KB × 1 million = 1 GB. These numbers drive the design: 50 requests per second fits one SQL Server, but 50,000 needs caching, replicas or sharding.

**Real-life example:** Before a party you estimate: 40 guests, 3 slices each, 8 slices per pizza — about 15 pizzas. You do not need the exact number, just the right size.

**Interview question:** How would you estimate the load for a news feed with 50 million daily users?

**Simple answer:** If each user opens the feed 10 times a day, that is 500 million reads, about 5,000 per second on average and 25,000 at a 5x peak. With half a post per user per day, writes are about 250 per second, so reads are 20 times more. That tells me to optimise reads with caching and precomputed feeds, and to serve images from blob storage through a CDN.

### Scalability: vertical vs horizontal

**In simple words:** Scalability means handling more load by adding resources. *Vertical* scaling (scale up) means a bigger machine with more CPU and RAM. It is simple, but it has a limit and is a single point of failure. *Horizontal* scaling (scale out) means more machines behind a load balancer. It has almost no limit, but the app must be *stateless* (keep no user data in server memory).

**Real-life example:** Vertical scaling is buying a bigger bus. Horizontal scaling is adding more buses on the same route.

**Interview question:** Vertical or horizontal scaling — which do you use?

**Simple answer:** I scale web and API tiers horizontally, because they can be stateless, and more instances also give fault tolerance. For a .NET API that means no in-memory sessions, no local files and shared Data Protection keys. Databases are harder, so I scale them up first, then add read replicas and caching, and shard only as a last step.

### Availability

**In simple words:** Availability is the percentage of time the system is up and working, counted in "nines". 99.9% allows about 8.8 hours of downtime a year; 99.99% allows about 52 minutes. Parts in a chain multiply: 99.95% × 99.99% is about 99.94%. Redundant copies improve it. An *SLO* is your internal target; an *SLA* is the contract with customers.

**Real-life example:** A hospital has backup generators. If the main power fails, the generator takes over and the lights stay on.

**Interview question:** What does 99.99% availability mean in practice?

**Simple answer:** About 52 minutes of downtime per year, or 4.4 minutes per month. To reach it I need redundancy across availability zones, automatic failover, safe deployments and fast detection. Because dependencies in a chain multiply, each one must be better than the overall target.

### Reliability

**In simple words:** Reliability means the system does the right thing every time, even when parts fail: no lost orders, no double charges and correct results. Availability means "it answers"; reliability means "it answers correctly and keeps data safe". Tools include backups with tested restores, idempotent operations, the outbox pattern, dead-letter queues with alerts and reconciliation jobs.

**Real-life example:** A shop that is always open but sometimes gives the wrong change is available, but not reliable.

**Interview question:** What is the difference between availability and reliability?

**Simple answer:** Availability is the share of time the system responds. Reliability is whether it behaves correctly over time, with correct results and no data loss. A system can answer quickly but lose orders; then it is available but unreliable.

### Performance: latency vs throughput, percentiles

**In simple words:** *Latency* is how long one request takes. *Throughput* is how many requests you handle per second. When a server gets close to 100% busy, queues form and latency jumps. Measure *percentiles*, not averages: p99 means 99% of requests are faster than this value. An average of 100 ms can hide a p99 of 3 seconds.

**Real-life example:** At a bank, latency is how long one customer waits, and throughput is how many customers are served per hour. The average wait can look fine while a few people wait an hour.

**Interview question:** Why care about p99 instead of average latency?

**Simple answer:** Averages hide the slow tail; p99 shows what the slowest 1% of requests experience. Fan-out makes it worse: if a page calls 20 services, about 18% of page loads hit at least one slow call. So I set SLOs and alerts on percentiles.

### Security in HLD

**In simple words:** Mention security in every design, briefly and concretely. At the edge: HTTPS, a WAF (web application firewall), DDoS protection and rate limits. For identity: OAuth2 or OpenID Connect with short-lived tokens, and managed identity between services. For data: encryption at rest and in transit, secrets in Key Vault, private endpoints and least-privilege database users. Add audit logs and monitoring too.

**Real-life example:** A bank has guards at the door, ID checks at the counter, a locked vault and cameras. There are several layers, not just one.

**Interview question:** How do you include security in a high-level design?

**Simple answer:** I go layer by layer. At the edge: TLS, WAF, DDoS protection and rate limiting. For identity: OAuth2/OIDC with Entra ID, and managed identity for services. For data: encryption, Key Vault, private endpoints and no public database access. Card data stays with a PCI-compliant payment provider.

### Load balancer, reverse proxy and forward proxy

**In simple words:** A *load balancer* spreads incoming traffic across healthy servers. A *reverse proxy* sits in front of servers and forwards client requests to them; it can also handle TLS, caching and routing. A *forward proxy* sits in front of clients and sends their requests out to the internet, like a company web filter. An L4 load balancer routes by IP and port; an L7 one understands HTTP paths and headers.

**Real-life example:** A reverse proxy is a hotel reception that sends guests to the right rooms. A forward proxy is a company mailroom that sends out every employee's letters.

**Interview question:** What is the difference between an L4 and an L7 load balancer?

**Simple answer:** L4 routes TCP or UDP connections by IP and port; it is very fast and works with any protocol. L7 understands HTTP, so it can route by path or host, end TLS, apply WAF rules and use sticky cookies. In Azure, Azure Load Balancer is L4, while Application Gateway and Front Door are L7.

### Load balancing algorithms

**In simple words:** The algorithm decides which server gets the next request. *Round robin* takes turns. *Weighted round robin* sends more to bigger servers. *Least connections* picks the least busy server. *IP hash* always sends one client to the same server. *Consistent hashing* places keys and servers on a ring, so adding a server moves only a small part of the keys.

**Real-life example:** At a supermarket, you either go to the next checkout in turn (round robin) or look for the shortest queue (least connections).

**Interview question:** Which load balancing algorithm would you choose?

**Simple answer:** Round robin when servers are the same and requests cost about the same. Least connections when request time varies, like reports or WebSockets. Consistent hashing for caches or sharded stateful services, because a server change moves only about 1/N of the keys.

### Sticky sessions vs stateless

**In simple words:** A *sticky session* pins a user to one server, because their session data lives in that server's memory. This causes uneven load, lost sessions when a server dies, and harder scaling and deploys. A *stateless* design keeps no user state in the server: use a JWT, or store the session in Redis. Then any server can handle any request.

**Real-life example:** Sticky: only the one bank clerk with your file on their desk can help you. Stateless: your file is in a shared system, so any clerk can help.

**Interview question:** Why are sticky sessions a problem?

**Simple answer:** They pin users to instances, so load becomes uneven, sessions are lost when an instance dies, and scaling in or deploying is harder. I prefer stateless services with tokens or a Redis session store. I use stickiness only for legacy apps, or for SignalR without a backplane.

### Health probes

**In simple words:** A load balancer regularly calls a health endpoint, like `/health/ready`. If an instance fails, it is taken out of rotation and added back when it is healthy. *Liveness* checks whether the process is alive; if not, it is restarted. *Readiness* checks whether it can serve traffic now, for example whether the database is reachable. Never put slow dependency checks in liveness.

**Real-life example:** A taxi dispatcher only sends jobs to drivers who pressed "available". A driver on a break is skipped, not fired.

**Interview question:** What is the difference between liveness and readiness?

**Simple answer:** Liveness asks "is the process alive?" and a failure triggers a restart. Readiness asks "can it serve traffic now?" and a failure only removes the instance from the load balancer. If a database check were in liveness, a short database problem would restart every instance.

### Where caching fits in a system design

**In simple words:** Caches exist at many layers: the browser, the CDN, the gateway or output cache, app memory (L1), Redis (L2) and the database's own memory. Layers closer to the user are faster and cheaper per request, but harder to invalidate. In a design, say what each layer caches and how it is refreshed: TTLs, versioned file names, tags or delete-on-write.

**Real-life example:** Water in a glass on your desk, a bottle in the fridge, a tank on the roof and the city reservoir. The closer it is, the faster you get it, but the harder it is to replace everywhere if the water goes bad.

**Interview question:** Where would you add caching in a system design?

**Simple answer:** The browser and CDN for static files and cacheable GETs, output caching for whole API responses, and Redis for shared objects and query results. Each layer has a clear invalidation plan, like TTLs, tags or delete-on-write. Decisions like checkout always read the database.

### CDN

**In simple words:** A CDN (Content Delivery Network) is a set of servers around the world that keep copies of your content near users. It cuts latency, takes load off your own server and absorbs DDoS attacks. Most CDNs "pull": the edge fetches content from your server on the first miss and caches it. Use fingerprinted file names like `app.3f9a1c.js` with a one-year cache, so deploys never need a purge.

**Real-life example:** A drinks company keeps stock in a warehouse in every city, so shops do not wait for delivery from the main factory.

**Interview question:** What is a CDN and when does it help?

**Simple answer:** It is a network of edge servers that cache content close to users. It helps with static files, images, video and cacheable GET APIs, and it absorbs DDoS traffic. I use versioned file names with long TTLs and never cache personalised responses at the edge.

### Database selection: SQL vs NoSQL

**In simple words:** SQL databases store rows in tables with a fixed schema, joins and ACID transactions; they suit orders, payments and inventory. NoSQL databases are built for specific access patterns and easy horizontal scaling: key-value (Redis), document (Cosmos DB, MongoDB), wide-column (Cassandra), graph (Neo4j) and search (Elasticsearch). Choose by access pattern, consistency need and scale. Using several stores in one system is normal (*polyglot persistence*).

**Real-life example:** SQL is a well-organised filing cabinet with linked folders and strict rules. NoSQL is a set of special boxes, each built to find one kind of thing very fast.

**Interview question:** SQL or NoSQL for a new system?

**Simple answer:** I start with a relational database for core transactional data, because I need integrity and transactions. I add special stores for special needs: Redis for caching, a search index for full text and blob storage for media. I choose NoSQL when access is simple by key and the scale or flexible schema goes beyond what one SQL server handles comfortably.

### Normalization vs denormalization

**In simple words:** *Normalization* splits data into related tables so each fact is stored only once. Updates are simple and data stays correct, but reads need joins. *Denormalization* copies data on purpose to make reads fast, for example storing the customer name on each order. A common rule: normalize the write model, and denormalize the read model where joins are proven slow.

**Real-life example:** Normalized: your address is stored once at the post office, and each letter looks it up. Denormalized: your address is printed on every letter — fast to read, but if you move, every copy must change.

**Interview question:** When would you denormalize?

**Simple answer:** When reads dominate and measurements show joins are too slow, for example in read models, reports or NoSQL documents. The cost is keeping the copies in sync. A snapshot like the price at purchase time on an order line is not duplication; it is history and should not change.

### Indexing in system design

**In simple words:** An index is a sorted structure that helps the database find rows fast, without scanning the whole table. It speeds up reads but slows writes and uses more storage. In a design, name the index your main query needs, for example `(UserId, CreatedAt DESC)` for a user's feed. A *covering index* includes extra columns, so the query does not touch the main table. Text search needs a search index.

**Real-life example:** The index at the back of a book lets you jump to the right page instead of reading the whole book.

**Interview question:** How do you talk about indexes in a system design interview?

**Simple answer:** I link each index to a main query. For example, a feed query by user and date needs a composite index on `(UserId, CreatedAt DESC)`, which turns it into a quick range seek. I avoid too many indexes on write-heavy tables, and I use a search index like Elasticsearch for full-text search.

### Replication and read replicas

**In simple words:** Replication keeps copies of the same data on several servers for availability, safety and read scaling. In *leader-follower* replication, all writes go to the leader, and followers copy its changes. Read replicas take reporting and browsing traffic. With async replication, replicas can be slightly behind (*replication lag*), so a user may not see their own change at once.

**Real-life example:** Head office updates the price list, and branch offices receive copies a bit later. A customer who asks a branch may briefly hear the old price.

**Interview question:** What is replication lag and how do you handle it?

**Simple answer:** Async replicas apply changes after the primary, so reads from them can be stale. I send reads that must be current, or a user's own recent writes, to the primary. I use replicas for reports, search and browsing, never for decisions like stock at checkout.

```csharp
builder.Services.AddDbContext<ShopReadDb>(o => o.UseSqlServer(
    primaryCs + ";ApplicationIntent=ReadOnly"));   // goes to a readable replica
```

### Partitioning and sharding

**In simple words:** *Partitioning* splits a large dataset into smaller pieces. *Sharding* splits rows across different database servers. You shard when one server cannot hold the data or handle the writes, but it is a last resort, because joins and transactions across shards become hard. The *shard key* is the main choice: it should have many values, spread evenly, and appear in most queries.

**Real-life example:** A big library splits books across buildings by the author's surname: A–F in one building, G–M in another. Finding one author is easy, but a search across all authors needs every building.

**Interview question:** How do you choose a shard key?

**Simple answer:** It needs high cardinality (many different values), an even spread, and it must be in most queries, so each query hits one shard. Examples are CustomerId for orders or TenantId for SaaS. I avoid always-increasing keys with range sharding, because the newest shard gets all the writes. Consistent hashing or many logical shards make resharding easier.

### Message queues in system design

**In simple words:** A queue stores messages between producers and consumers, so they do not need to run at the same time. It decouples services, absorbs traffic spikes, lets the API return `202 Accepted` quickly and do slow work later, and keeps messages safe if a consumer crashes. *Backpressure* means telling producers to slow down when consumers cannot keep up, for example with bounded queues or HTTP 429.

**Real-life example:** A restaurant's order ticket rail. Waiters add tickets at any speed, and the cooks take them one by one at their own pace.

**Interview question:** When would you add a message queue?

**Simple answer:** To decouple services, smooth traffic spikes, run slow work in the background and send one event to several consumers reliably. I also name the costs: eventual consistency, duplicates that need idempotent consumers, and dead-letter queues that must be monitored.

### Microservices and API gateway in HLD

**In simple words:** In a design answer, show a few services split by business capability, each with its own data store. Put them behind a load balancer and an API gateway that handles routing, auth, rate limiting and TLS. Use synchronous calls for queries and events for side effects. Keep the number of services small (3–6) and explain why each split exists.

**Real-life example:** A hotel has one front desk for guests, while housekeeping, the kitchen and the laundry each run their own area and pass notes to each other.

**Interview question:** How do you present microservices in a 45-minute design interview?

**Simple answer:** I show 3–6 services split by business capability, each owning its data, behind an API gateway and a load balancer. Queries are synchronous; side effects like emails go through events. I name the trade-off: independent scaling and deployment, against distributed complexity such as eventual consistency, sagas and tracing.

### Rate limiter design

**In simple words:** A rate limiter limits how many requests a client can make in a time window. It protects services from abuse and enforces plans like "free: 100 per minute". The most common algorithm is the *token bucket*: a bucket holds N tokens, refills at a fixed rate, and each request takes one token. With many gateway instances, keep the counters in Redis and update them atomically.

**Real-life example:** An arcade gives you 10 tokens and one new token every minute. When your tokens run out, you must wait.

**Interview question:** How would you design a rate limiter?

**Simple answer:** I use a token bucket per client key, like a user ID or API key. Counters live in Redis and are updated atomically with a Lua script, so all gateway instances share them. Rules are set per plan and endpoint. Rejected calls get 429 with `Retry-After`, and there is a local fallback if Redis is down.

### Consistency models

**In simple words:** A consistency model says what a reader may see after a write. *Strong*: every read sees the latest write. *Read-your-writes*: you always see your own changes. *Bounded staleness*: reads are at most a set time or number of versions behind. *Eventual*: all copies agree after a while if writes stop.

**Real-life example:** A shared online document with live editing is strong consistency. A printed newsletter that reaches everyone over the next few days is eventual consistency.

**Interview question:** Which consistency model would you choose?

**Simple answer:** I choose per feature. Payments, stock decrements and seat bookings need strong consistency at the moment of decision. Feeds, like counts, recommendations and search indexes are fine with eventual consistency. Cosmos DB's Session level gives read-your-writes, which suits most user-facing data.

### Idempotency in system design

**In simple words:** Any write API that may be retried must be *idempotent*: doing it twice gives the same result as doing it once. Retries come from mobile networks, gateway timeouts and at-least-once queues. Use idempotency keys from the client stored with the result, unique constraints on natural keys (like one booking per seat per show), conditional updates and idempotent consumers with an inbox table.

**Real-life example:** A ticket barrier reads your ticket once. Scanning the same ticket again does not let a second person through.

**Interview question:** How do you make write APIs safe to retry?

**Simple answer:** The client sends an idempotency key, and the server stores it with the result and returns the same result on a repeat. A unique constraint, like one booking per seat per show, blocks duplicates in the database. Message consumers use an inbox table, and payment providers require idempotency keys too.

### Monitoring and observability in HLD

**In simple words:** End every design with "how do we know it works?". Track the *golden signals*: latency (p50, p95, p99), traffic, errors and saturation (CPU, memory, queue depth). Also track business metrics like bookings per minute or payment success rate; they often show an outage first. Add distributed tracing, structured logs with correlation IDs, and alerts based on SLOs.

**Real-life example:** A car dashboard shows speed, fuel and warning lights, so the driver sees a problem before the engine stops.

**Interview question:** How do you add monitoring to a system design?

**Simple answer:** For each service I track the golden signals — latency percentiles, traffic, errors and saturation — plus business metrics like checkout success rate. I use OpenTelemetry for traces, structured logs with correlation IDs, dashboards per service and SLO burn-rate alerts instead of noisy thresholds.

### 1. Requirements

**In simple words:** In the movie ticket booking example, the first step is to agree what to build. In scope: browse shows, view the seat map, hold seats for 10 minutes, pay and confirm, get an e-ticket and cancel. Out of scope: reviews, recommendations and dynamic pricing. Key non-functional needs: no double booking, fast seat-map reads, 99.95% availability for booking, and surviving a huge rush for a blockbuster release.

**Real-life example:** Before building a cinema, the owner decides how many screens it needs, whether to sell food, and how big the opening-night crowd might be.

**Interview question:** What requirements would you list for a movie ticket booking system?

**Simple answer:** Functional: browse shows, see seats, hold seats for 10 minutes, pay and confirm, get an e-ticket and cancel. Non-functional: no double booking, so seats need strong consistency; seat-map p99 under 200 ms; 99.95% availability for booking; and handling a million users in the first minutes of a big release. Card data stays out of our servers.

### 2. Estimation

**In simple words:** Next come rough numbers. About 1 million bookings a day is roughly 12 per second on average and about 100 at peak. There are about 20 seat-map views per booking: around 230 per second normally, but up to 20,000 per second in a blockbuster spike. Each booking is about 1 KB, so about 365 GB a year, which one SQL database can hold. The conclusion: writes are modest; the hard parts are the read spike and seat contention.

**Real-life example:** A theatre manager counts the seats and the expected ticket sales to decide how many ticket counters to open.

**Interview question:** What do your estimates tell you about the booking system's design?

**Simple answer:** Writes are small — about 100 bookings per second at peak and a few hundred GB per year — so one SQL Server is fine at first. The real challenges are the seat-map read spike of up to 20,000 per second and many users fighting for the same seats. So I focus on caching seat maps and on safe seat holds.

### 3. API

**In simple words:** Define the main endpoints. `GET` endpoints list shows and return the seat map. `POST .../holds` holds seats and returns 409 Conflict if any seat is already taken. `POST /bookings` takes the hold ID and a payment token, and returns 202 Accepted with a Pending status. A webhook from the payment provider then confirms or fails the booking. Write calls carry an `Idempotency-Key` header.

**Real-life example:** A restaurant menu with clear order codes. Everyone knows exactly what to ask for and what they will get back.

**Interview question:** What APIs would you define for seat booking?

**Simple answer:** GET shows and GET seat map for browsing. POST holds, with an idempotency key, returns a hold ID and expiry time, or 409 if a seat is gone. POST bookings with the hold ID and payment token returns 202 Pending. A payment webhook moves it to Confirmed or Failed, and the client checks with GET booking.

```text
POST /v1/shows/{showId}/holds  { seatIds: [...] }             -> 201 { holdId, expiresAt } | 409
POST /v1/bookings              { holdId, paymentMethodToken } -> 202 { bookingId, Pending }
GET  /v1/bookings/{bookingId}                                 -> Confirmed | Failed
```

### 4. High-level design

**In simple words:** Users reach Azure Front Door (CDN plus WAF), then an API gateway that handles auth, rate limits and a *virtual waiting room* for hot shows. Behind it are a Catalog service with SQL and Redis, a Seat/Booking service on SQL Server with a Redis seat-map cache, and a Payment service that uses a provider like Stripe. Events like `BookingConfirmed` go through Service Bus to Notification and Analytics. A background worker releases expired holds.

**Real-life example:** A cinema hall with a queue manager at the door, separate counters for show info, seat sales and payment, and a messenger who tells the printing desk when to print tickets.

**Interview question:** Describe the high-level design for a movie booking system.

**Simple answer:** Clients go through Front Door to an API gateway with auth, rate limiting and a waiting room. The Catalog service uses SQL and Redis for read-heavy data. The Booking service keeps seats, holds and bookings in SQL Server, with a Redis seat-map cache. A Payment service uses a hosted payment provider, Service Bus events drive notifications and analytics, and a worker expires old holds.

### 5. Data model (SQL Server)

**In simple words:** The main table is `ShowSeat`, with one row per seat per show. Its primary key is `(ShowId, SeatId)`, and it stores the status (Available, Held, Booked), the hold ID, the hold expiry time and a `rowversion`. The `Booking` table has a unique `HoldId`, so one hold can create only one booking. A filtered index on hold expiry helps the worker find expired holds quickly.

**Real-life example:** A cinema seating chart where each seat for each show has a sticker: green (free), yellow (held until a set time) or red (sold).

**Interview question:** How would you model seats and bookings in SQL Server?

**Simple answer:** A `ShowSeat` table keyed by `(ShowId, SeatId)` holds the status, hold ID, hold expiry and a rowversion. A `Booking` table has a unique `HoldId`, which makes booking idempotent. I add a filtered index on `HoldExpiresUtc` for held seats, so the expiry worker is fast.

### 6. Deep dive: holding seats without double booking

**In simple words:** The key rule is "all my chosen seats become held by me, or none do". One atomic SQL `UPDATE` in a transaction sets the seats to Held, but only where they are still free or their hold has expired. If fewer rows changed than seats requested, the transaction rolls back and the API returns 409. The database's row locks make this safe, so no distributed lock is needed. The seat-map cache only shows availability; it never decides it.

**Real-life example:** Two people ask for the last two concert tickets at the same box office at the same moment. The clerk can give them to only one person; the other hears "sorry, sold out".

**Interview question:** How do you prevent double booking of the same seat?

**Simple answer:** The database decides, with one atomic conditional update inside a transaction: change the seat only where it is still available or its hold has expired. If not every requested row changed, I roll back and return 409. The API also uses an idempotency key, and the cache only displays seats; it never decides.

```sql
UPDATE ss SET Status = 1, HoldId = @HoldId,
       HoldExpiresUtc = DATEADD(MINUTE, 10, SYSUTCDATETIME())
FROM ShowSeat ss JOIN @SeatIds s ON s.SeatId = ss.SeatId
WHERE ss.ShowId = @ShowId
  AND (ss.Status = 0 OR (ss.Status = 1 AND ss.HoldExpiresUtc < SYSUTCDATETIME()));
-- if @@ROWCOUNT <> number of seats: ROLLBACK and return 409
```

### 7. Bottlenecks and trade-offs

**In simple words:** Finish by naming the weak points and your choices. One SQL database is fine for this write volume; add read replicas for browsing, and partition by city later. Seats choose consistency (reject rather than double-book), while the catalogue and seat maps choose availability (cached and slightly stale). If Redis is down, seat maps fall back to the database with rate limits, and holds still work. If the payment provider is slow, use a circuit breaker, extend holds and run a daily reconciliation.

**Real-life example:** Before a big outdoor event, organisers list the risks — rain, a power cut, too many guests — and a backup plan for each one.

**Interview question:** What bottlenecks and trade-offs would you mention for the booking system?

**Simple answer:** The single SQL database comes first: scale up and add read replicas, then partition by city, since shows never span cities. Seats are CP and catalogue data is AP. Failures of Redis or the payment provider are handled with fallbacks, circuit breakers and reconciliation. I would monitor the hold conflict rate, payment success rate, p99 of the hold API and DLQ depth.
