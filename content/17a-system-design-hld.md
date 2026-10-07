## HLD Interview Framework

### How to run a system design interview

**Definition.** High Level Design (HLD) describes a system's major components (clients, gateways, services, data stores, queues, caches, CDNs), how they interact, and how the system meets its scale, availability and latency goals. It is about *boxes and arrows and trade-offs*, not classes.

**Why it matters.** Interviewers grade the *process*: do you clarify, quantify, propose something simple, then evolve it while explaining trade-offs? A memorised diagram with no reasoning scores poorly.

A repeatable 45-minute structure (similar to the "RESHADED" mnemonic):

| Step | Time | What you do | Output |
|---|---|---|---|
| 1. **R**equirements | 5 min | clarify functional + non-functional; state assumptions; agree scope | bullet list, "out of scope" list |
| 2. **E**stimation | 3-5 min | users, QPS (avg/peak), storage, bandwidth, read:write ratio | numbers that drive design |
| 3. **S**ystem API | 3-5 min | main endpoints/events with request/response | `POST /bookings`, `GET /feed?cursor=` |
| 4. **H**igh-level design | 10 min | simplest design that works end to end | diagram: client -> LB -> services -> DB/cache/queue |
| 5. **D**ata model | 5 min | entities, keys, SQL vs NoSQL choice, access patterns | tables/collections, partition keys |
| 6. **E**valuate / deep dive | 10-15 min | the 1-2 hardest parts: hot path, consistency, concurrency | detailed flow, algorithms |
| 7. **D**istinctive bottlenecks & trade-offs | 5 min | SPOFs, scaling limits, failure modes, monitoring, what you'd do next | trade-off list |

:::tip What interviewers listen for
- You ask before you draw ("How many daily users? Is eventual consistency OK for the feed?").
- You state numbers and let them drive choices ("12k reads/s at peak, so a cache is required").
- You name trade-offs explicitly ("I choose availability over consistency for likes, but strong consistency for payments").
- You drive the conversation and check in ("Shall I deep-dive into seat locking or the notification path?").
:::

### Requirements gathering: functional vs non-functional

**Functional requirements** = what the system *does* (features): "users can book a seat", "users see a feed of followed accounts", "admins can cancel an event".

**Non-functional requirements (NFRs)** = how well it does it (qualities): scale, latency, availability, consistency, durability, security, compliance, cost.

| Category | Example questions | Example answer |
|---|---|---|
| Scale | DAU? peak multiplier? growth? | 10M DAU, 5x peak during sales |
| Latency | p99 target for reads/writes? | p99 read < 200 ms, write < 500 ms |
| Availability | SLA? which features are critical? | 99.95% for booking, 99.9% for search |
| Consistency | can users see stale data? double-booking allowed? | feed eventual; bookings strongly consistent |
| Durability | can we lose data? retention? | zero loss for payments, 7-year audit |
| Security/compliance | PII? PCI? GDPR? regions? | card data via PCI provider, EU data stays in EU |
| Cost/ops | budget, team size, cloud | Azure, small team: prefer PaaS |

Write the in-scope and out-of-scope lists on the board. Prioritise the top 3 functional requirements; you cannot design 15 features in 45 minutes.

### Back-of-the-envelope estimation

**Why.** Numbers decide architecture: 50 QPS fits one SQL Server; 50,000 QPS needs caching, replicas or sharding.

Handy conversions:
- 1 day ~ 86,400 s ~ **10^5 s** (round for speed).
- 1M requests/day ~ **12 QPS** average. 100M/day ~ 1,200 QPS.
- Peak ~ 2-5x average (or more for flash sales).
- 1 KB x 1M = 1 GB. 1 KB x 1B = 1 TB.

**Worked example: a news feed.**

```text
Assumptions: 50M DAU, each opens the feed 10x/day, posts 0.5x/day
             post = 1 KB text + metadata; 20% of posts have a 300 KB image

Reads  : 50M x 10 = 500M/day  -> 500M / 10^5 = 5,000 QPS avg, ~25,000 QPS peak (5x)
Writes : 50M x 0.5 = 25M/day  -> 250 QPS avg, ~1,250 QPS peak
Read:write ratio ~ 20:1  -> read-optimised design, caching, fan-out on write

Storage (text): 25M x 1 KB = 25 GB/day -> ~9 TB/year (x3 replication = ~27 TB)
Storage (media): 25M x 20% x 300 KB = 1.5 TB/day -> ~550 TB/year  -> blob storage + CDN
Bandwidth out : 25,000 QPS x 20 posts x 1 KB = ~500 MB/s text at peak (images via CDN)
Cache         : hot feeds for 20% of DAU x 200 post ids x 8 bytes = ~16 GB -> fits Redis cluster
```

Say the conclusions aloud: "reads dominate, so precompute feeds and cache; media goes to blob + CDN; text DB must shard within a couple of years."

**Latency numbers every engineer should know (orders of magnitude):**

| Operation | Approx. latency |
|---|---|
| L1 cache reference | 1 ns |
| Main memory reference | 100 ns |
| Compress 1 KB (fast codec) | 2-3 us |
| Read 1 MB sequentially from memory | ~10 us |
| SSD random read | ~16-100 us |
| Round trip within the same datacenter / AZ | ~0.5 ms |
| Redis GET over the network | ~0.2-1 ms |
| Read 1 MB sequentially from SSD | ~50-200 us (NVMe) to ~1 ms |
| Simple indexed SQL query (network included) | 1-5 ms |
| HDD disk seek | ~10 ms |
| Round trip between regions (EU <-> US) | 70-150 ms |

Takeaways: memory beats network beats disk; cross-region calls are expensive, so keep chatty calls inside a region.

## Quality Attributes (NFRs)

### Scalability: vertical vs horizontal

**Definition.** Scalability is the ability to handle more load by adding resources.

| | Vertical (scale up) | Horizontal (scale out) |
|---|---|---|
| How | bigger machine: more CPU/RAM/IOPS | more machines behind a load balancer |
| Limit | hardware ceiling, expensive at the top | practically unlimited |
| Downtime | often a restart to resize | none (add nodes live) |
| App changes | none | app must be **stateless** (or partitioned) |
| Fault tolerance | single point of failure | survives node loss |
| Good for | databases (first step), quick fixes | web/API tiers, workers, caches |

Making a .NET API horizontally scalable: no in-memory session (use tokens or Redis), no local file storage (use Blob), shared Data Protection keys, distributed cache/locks, idempotent background jobs, sticky sessions avoided. Databases are the hard part: scale up first, then read replicas, caching, partitioning, and finally sharding.

### Availability

**Definition.** The percentage of time the system is up and serving correctly. Expressed as "nines".

| Availability | Downtime per year | Per month | Per week |
|---|---|---|---|
| 99% | 3.65 days | 7.3 h | 1.68 h |
| 99.9% | 8.77 h | 43.8 min | 10.1 min |
| 99.95% | 4.38 h | 21.9 min | 5 min |
| 99.99% | 52.6 min | 4.4 min | 1 min |
| 99.999% | 5.26 min | 26 s | 6 s |

**Composite availability.** Components in **series** multiply: API 99.95% x DB 99.99% = 99.94%. Components in **parallel** (redundant) improve it: two instances of 99% -> 1 - (0.01 x 0.01) = 99.99%.

Techniques:
- **Redundancy**: N+1 instances, multiple availability zones, replicas for every stateful component; no single point of failure (SPOF).
- **Failover**: active-passive (standby promoted; RTO seconds-minutes) or active-active (all serve traffic; harder consistency). Automatic failover groups for Azure SQL, Redis replicas, Service Bus geo-DR.
- **Health checks**: liveness/readiness probes; load balancers stop routing to unhealthy nodes.
- **Graceful degradation**: turn off non-critical features (recommendations) to keep the core (checkout).
- **Deployment safety**: rolling/blue-green/canary deploys, feature flags, fast rollback — most outages are self-inflicted changes.
- **RTO/RPO**: Recovery Time Objective (how fast back) and Recovery Point Objective (how much data you can lose). Drives backup and replication choices.

SLA (contract with customers, with penalties) vs **SLO** (internal target, e.g., 99.95% of requests succeed in 30 days) vs **SLI** (the measured indicator, e.g., success ratio). Error budget = 1 - SLO.

### Reliability

**Definition.** The system does the *right thing* consistently, including under faults: no lost orders, no double charges, correct results. Availability = "it answers"; reliability = "it answers correctly and keeps data safe".

Practices: replication and backups (tested restores), idempotent operations and retries, outbox for no lost events, checksums, validations, chaos testing, DLQs with alerting, reconciliation jobs, well-defined failure modes (timeouts, circuit breakers), and postmortems.

### Performance: latency vs throughput, percentiles

- **Latency** = time for one request (ms). **Throughput** = requests handled per unit time (RPS). They interact: as utilisation approaches 100%, queueing makes latency explode.
- Measure **percentiles**, not averages: p50 (median user), p95, **p99** (1 in 100 requests: the tail, often your most active users who make many calls). An average of 100 ms can hide a p99 of 3 s.
- Fan-out amplifies the tail: if a page calls 20 services, each with p99 = 1 s, then ~18% of page loads hit at least one slow call (1 - 0.99^20).
- Levers: caching, CDN, async processing, connection pooling, indexing, pagination, compression, batching, avoiding N+1 calls, hedged requests for tail latency, moving compute closer to users.

### Security in HLD

Mention security in every design, briefly but concretely:
- **Edge**: TLS everywhere, WAF + DDoS protection (Front Door), rate limiting, bot protection.
- **Identity**: OAuth2/OIDC (Entra ID), short-lived JWTs, scopes/roles, service-to-service via managed identity or client credentials, mTLS inside.
- **Data**: encryption at rest (TDE, storage SSE) and in transit, secrets in Key Vault, least-privilege DB users, PII minimisation, tokenisation for cards (PCI scope reduction), data residency.
- **Network**: private endpoints, VNet isolation, no public DB endpoints.
- **App**: input validation, parameterised queries, output encoding, CORS, CSRF for cookies, dependency scanning.
- **Audit and monitoring**: audit logs, anomaly alerts, Defender for Cloud.

## Load Balancing

### Load balancer, reverse proxy and forward proxy

**Definition.** A *load balancer* distributes incoming traffic across multiple healthy instances. A *reverse proxy* sits in front of servers and forwards client requests to them (TLS termination, caching, compression, routing). A *forward proxy* sits in front of **clients** and forwards their outbound requests to the internet (corporate egress filtering, anonymity).

```text
Forward proxy:   [Clients] -> [Proxy] -> Internet servers    (protects/controls clients)
Reverse proxy:   Internet clients -> [Proxy/LB] -> [Server 1..N]  (protects/scales servers)
```

| | L4 (transport) load balancer | L7 (application) load balancer |
|---|---|---|
| Sees | IP + port (TCP/UDP) | HTTP: path, host, headers, cookies |
| Routing | by connection | by request content (`/api/orders` -> orders pool) |
| TLS | passes through (or terminates) | terminates, can re-encrypt |
| Features | very fast, protocol-agnostic | WAF, path routing, header rewrite, sticky cookies, compression |
| Azure | Azure Load Balancer | Application Gateway (regional), Front Door (global), APIM |
| Others | AWS NLB, HAProxy (TCP mode) | NGINX, Envoy, YARP, AWS ALB, Traefik |

Global load balancing (Front Door, Traffic Manager/DNS) routes users to the nearest healthy region; regional L7 routes to instances.

### Load balancing algorithms

| Algorithm | How | When |
|---|---|---|
| Round robin | rotate through instances | identical instances, similar request cost |
| Weighted round robin | bigger servers get more | mixed instance sizes, canary 5% |
| Least connections / least requests | pick the instance with fewest active requests | long or uneven requests (WebSockets, reports) |
| Least response time | fastest recent responder | latency-sensitive |
| IP hash | hash(client IP) -> instance | crude stickiness (breaks with NAT/proxies) |
| **Consistent hashing** | hash(key) on a ring; adding a node moves only ~1/N keys | caches, sharded stateful services |
| Random / power of two choices | pick 2 random, choose less loaded | large fleets, simple and effective |

### Sticky sessions vs stateless

Sticky sessions (session affinity via cookie) pin a user to one instance because state lives in its memory. Problems: uneven load, lost sessions when the instance dies, harder scale-in and deploys. **Prefer stateless services**: JWT or a session in Redis, so any instance can serve any request. Use stickiness only for legacy apps or SignalR without a backplane (or use Azure SignalR Service / Redis backplane).

### Health probes

The load balancer periodically calls `/health/ready`; failing instances are removed from rotation and re-added when healthy. Distinguish **liveness** (process alive; restart if not) from **readiness** (can serve traffic now: DB reachable, warm-up done). Never put slow dependency checks in liveness — a DB blip would restart every pod.

:::q How would you scale a stateful service horizontally?
Remove the state from instances where possible (Redis, DB, Blob). If state must stay in the service (cache, game rooms, WebSockets), partition it: route by key with consistent hashing so each key always reaches the same instance, and rebalance only a fraction of keys when nodes join or leave.
:::

## Caching Layers and CDN

### Where caching fits in a system design

```text
Browser cache -> CDN (edge) -> API Gateway/output cache -> App L1 (memory) -> Redis (L2)
   -> DB buffer pool -> Disk
Each layer closer to the user is faster and cheaper per request but harder to invalidate.
```

| Layer | Caches | Invalidation |
|---|---|---|
| Browser | static assets, GET responses (`Cache-Control`, ETag) | versioned file names, short max-age |
| CDN | images, JS/CSS, video, cacheable API GETs | TTL, purge by path/tag |
| Gateway / output cache | whole responses | tags, TTL |
| Application (L1/L2) | objects, query results, sessions | delete on write, events, TTL |
| Database | pages in buffer pool, plan cache | automatic |

For the deep treatment (patterns, stampede, penetration, avalanche, HybridCache) see Section 16.

### CDN

**Definition.** A Content Delivery Network is a globally distributed set of edge servers that cache content near users.

**Why.** Cuts latency (a user in Mumbai gets assets from a Mumbai PoP, not East US), offloads origin bandwidth and compute, absorbs DDoS, terminates TLS at the edge.

- **Push CDN**: you upload content to the CDN (good for large static files that rarely change).
- **Pull CDN**: the edge fetches from the origin on first miss and caches by TTL (most common).
- Use **fingerprinted file names** (`app.3f9a1c.js`) with a 1-year `immutable` cache, so deploys never need purges.
- Dynamic acceleration: even uncacheable API calls benefit from optimised routes and TLS termination at the edge (Front Door).
- Video: HLS/DASH segments cached at the edge.
- Private content: signed URLs/tokens (SAS for Blob, signed cookies).

:::example Image-heavy product catalogue
Product images (500 KB each) stored in Azure Blob Storage, served through Azure Front Door with a 30-day TTL and resized variants (`/img/42_400w.webp`). The API only returns URLs. Origin egress drops by ~95% and page load improves from 2.5 s to 0.8 s for users far from the region.
:::

:::q What is the difference between availability and reliability?
Availability is the fraction of time the system responds. Reliability is whether it behaves correctly over time — correct results, no data loss. A system can be available but unreliable (it answers quickly with wrong or lost data).
:::
