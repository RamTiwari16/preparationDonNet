### Why caching?

**In simple words:** A cache keeps a copy of data in a faster, closer place, so you do not repeat slow work. Redis or memory answers in about 1 ms, while a SQL query over the network can take 5–100 ms or more. Caching makes responses faster, lowers database load and saves money. But it also brings bugs: stale (old) data, inconsistency and stampedes.

**Real-life example:** A shop keeps the best-selling items at the front counter, so staff do not walk to the back store room for every customer.

**Interview question:** Why use a cache, and what are the risks?

**Simple answer:** A cache cuts latency, database load and cost by serving repeated reads from fast memory. The risks are stale data, differences between servers, stampedes when hot keys expire, and the cache itself becoming a new point of failure. A good cache has a TTL (time to live), invalidation on write and a safe fallback to the database.

### Request flow: Client -> API -> Redis -> SQL Server

**In simple words:** On a read, the API first asks Redis for the key. On a *hit*, Redis returns the value in about 1 ms and SQL Server is not touched. On a *miss*, the API reads from SQL Server, stores the result in Redis with a TTL, and returns it. On a write, the API updates SQL Server first, then deletes the Redis key, so the next read loads fresh data.

**Real-life example:** A waiter checks the pastry display first. If the cake is there, you get it at once. If not, the waiter asks the kitchen, puts one slice in the display for the next customer, and serves you.

**Interview question:** Describe the request flow when your API uses Redis in front of SQL Server.

**Simple answer:** For a read, I check Redis; on a hit I return the cached value. On a miss I query SQL Server, save the result in Redis with a TTL like 10 minutes, and return it. For an update, I write to SQL Server first and then delete the cache key. The database is always the source of truth.

### What to cache (and what not to)

**In simple words:** Cache data that is read much more often than it changes, where being a little out of date is fine. Good examples are product catalogues, countries, config, reports and slow external API results. Do not cache data that must be exactly current at decision time, like an account balance, stock at checkout or payment status. Never cache private user data under a key without the user ID.

**Real-life example:** A restaurant prints the menu once a week, but it checks the fridge live before saying "yes, we have fish today".

**Interview question:** How do you decide what to cache?

**Simple answer:** I cache read-heavy, rarely changing data where some staleness is acceptable, and I agree the TTL with the business. I avoid caching data that must be exact for a decision, like balances or checkout stock. I also avoid write-heavy data with little reuse, because the hit ratio would be too low to help.

### IMemoryCache

**In simple words:** `IMemoryCache` stores data inside your app's own memory. It is the fastest cache: no network and no serialization — you get the same object back. But each server has its own copy, and a restart empties it. It has no size limit by default, so set `SizeLimit`. Use *absolute* expiration (fixed time) and, if needed, *sliding* expiration (resets on each read), always with an absolute cap.

**Real-life example:** Notes on your own desk. They are very quick to read, but your colleague at another desk cannot see them, and they are thrown away when you move desks.

**Interview question:** What is the difference between absolute and sliding expiration?

**Simple answer:** Absolute expiration removes the item at a fixed time after it was created. Sliding expiration removes it only if nobody reads it within the window, and each read resets the timer. Sliding alone can keep a hot item forever, so it becomes stale. I combine sliding with an absolute cap and cache immutable objects only.

```csharp
var product = await cache.GetOrCreateAsync($"product:{id}", async entry =>
{
    entry.AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(10);
    entry.SlidingExpiration = TimeSpan.FromMinutes(2);
    return await repo.GetByIdAsync(id, ct);
});
```

### Stampede protection (single flight)

**In simple words:** A *stampede* happens when a popular key expires and hundreds of requests miss at the same moment. They all hit the database together. *Single flight* means only one request per key loads the data, and the others wait and reuse its result. You can do this with a `SemaphoreSlim` per key. In .NET 9, `HybridCache` does it for you.

**Real-life example:** When the coffee pot is empty, one person makes a new pot. The others wait a minute instead of all making their own pots at once.

**Interview question:** How do you stop many requests from loading the same expired key at once?

**Simple answer:** I let only one caller per key load the data. The others wait and then read the cached result. I use a per-key lock, like a striped array of `SemaphoreSlim`, with a double-check after the wait. On .NET 9 I prefer `HybridCache`, which has this protection built in.

### IDistributedCache

**In simple words:** `IDistributedCache` is a cache shared by all your app servers, stored outside the app, usually in Redis or SQL Server. Values are stored as bytes, so you must serialize them, for example to JSON. It is slower than memory (about 0.2–2 ms) but all servers see the same copy, and it survives app restarts. `AddDistributedMemoryCache()` is only an in-process stand-in for tests.

**Real-life example:** A shared whiteboard in the office corridor. Everyone sees the same notes, but you must walk there to read it.

**Interview question:** When do you use `IMemoryCache` and when `IDistributedCache`?

**Simple answer:** `IMemoryCache` for small, very hot data where a little difference between servers is fine. `IDistributedCache` with Redis when all instances must share one copy, or when the cache must survive restarts, for example for sessions. With the distributed cache I must serialize values and handle network errors.

### Redis

**In simple words:** Redis is an in-memory data server. It runs commands on one thread, so each command is atomic (cannot be interrupted), and responses take under a millisecond. Besides strings, it has hashes, lists, sets and sorted sets, used for carts, counters, leaderboards and locks. Always set a TTL, set `maxmemory` with an eviction policy like `allkeys-lru`, and use one `ConnectionMultiplexer` per app.

**Real-life example:** A very fast librarian who handles one request at a time. Because each request is tiny, the queue still moves very quickly.

**Interview question:** Redis is single-threaded — how is it still fast?

**Simple answer:** All data is in memory, most commands are tiny O(1) or O(log n) operations, and it uses an event loop for network I/O with no lock contention. The downside is that one slow command, like `KEYS *` or a huge value, blocks everyone. So I use `SCAN` and avoid big keys.

```csharp
await db.StringSetAsync("product:42", json, TimeSpan.FromMinutes(10));
long views = await db.StringIncrementAsync("views:product:42");
await db.SortedSetIncrementAsync("bestsellers", "p42", 1);
```

### ASP.NET Core: AddStackExchangeRedisCache

**In simple words:** `AddStackExchangeRedisCache` registers Redis as the `IDistributedCache` in ASP.NET Core. You give it the connection string and an `InstanceName` prefix, so all keys start with something like `shop:`. Then you inject `IDistributedCache` and use get and set with a TTL. ASP.NET Core session state can also use it, so you do not need sticky sessions. SQL Server can be a distributed cache too, but it is slower.

**Real-life example:** Plugging a shared printer into the office network. Once it is set up, every computer can use it in the same way.

**Interview question:** How do you add Redis caching to an ASP.NET Core API?

**Simple answer:** I call `AddStackExchangeRedisCache` with the connection string and an instance name prefix. Then I inject `IDistributedCache` and use the cache-aside pattern: try to get the key, load from the database on a miss, and set it with a TTL. Connection details live in configuration or Key Vault.

```csharp
builder.Services.AddStackExchangeRedisCache(o =>
{
    o.Configuration = builder.Configuration.GetConnectionString("Redis");
    o.InstanceName = "shop:";
});
```

### HybridCache (.NET 9)

**In simple words:** `HybridCache` is a two-level cache with one API. Level 1 (L1) is fast in-process memory; level 2 (L2) is a distributed cache like Redis. It has stampede protection built in, handles serialization, and supports *tags* to remove groups of entries. One catch: removing a key clears L2 and only the current server's L1, so keep the L1 TTL short.

**Real-life example:** You keep a few files on your desk (L1) and the full set in the shared office cabinet (L2). If the file is not on your desk, you fetch it from the cabinet.

**Interview question:** When would you use HybridCache?

**Simple answer:** On .NET 9 and later, whenever I would otherwise combine `IMemoryCache` and `IDistributedCache`. It gives L1 memory plus L2 Redis, stampede protection, serialization and tag invalidation in one call. I keep the L1 TTL short, because other servers' L1 copies are not cleared automatically.

```csharp
var product = await cache.GetOrCreateAsync(
    $"product:{id}",
    async token => await repo.GetByIdAsync(id, token),
    tags: ["products"],
    cancellationToken: ct);
```

### Cache-aside (lazy loading)

**In simple words:** In cache-aside, your app controls the cache. On a read, it checks the cache; on a miss, it loads from the database and stores the result with a TTL. On a write, it updates the database first and then *deletes* the cache key. If the cache is down, the app still works, only slower. It is the default pattern with ASP.NET Core and Redis.

**Real-life example:** A student keeps a notebook of answers. If the answer is not in the notebook, they look it up in the textbook and write it down. If the textbook changes, they cross out that note.

**Interview question:** Why delete the cache key on update instead of overwriting it?

**Simple answer:** Overwriting is a dual write: two updates at the same time can leave the older value in the cache. Deleting is safe to repeat, and the next read loads fresh data from the database. A small race can still happen, so I keep a TTL as a safety net.

### Read-through, write-through, write-behind, refresh-ahead

**In simple words:** These patterns move loading or writing into the cache layer. *Read-through*: the cache loads from the database on a miss. *Write-through*: each write goes to the cache and the database at once, so they match. *Write-behind*: the cache saves fast and writes to the database later in batches; it is fast but can lose data on a crash. *Refresh-ahead*: hot keys are reloaded before they expire.

**Real-life example:** Write-behind is like a waiter who writes orders on a notepad and gives them to the kitchen every few minutes. It is fast, but if the notepad is lost, the orders are lost.

**Interview question:** Cache-aside vs write-through — how do you choose?

**Simple answer:** Cache-aside is my default: simple, resilient and controlled by the app. I use write-through when readers must see a write immediately and my cache layer supports it, accepting slower writes. I use write-behind only for high-volume data where small losses are fine, like view counters.

### Cache expiration vs invalidation

**In simple words:** *Expiration* removes data after a set time (TTL), even if nothing changed. *Invalidation* removes data *because* the source changed. Real systems use both: invalidation keeps data fresh, and the TTL is a safety net for missed invalidations. Other tools are versioned keys (change a version number to drop a whole group) and tags.

**Real-life example:** Milk has a "best before" date (expiration). But if the shop hears about a problem with a batch, it removes that milk at once (invalidation).

**Interview question:** How do you invalidate the cache across several app instances?

**Simple answer:** I use a shared cache like Redis, so one delete is seen by every server. For local L1 caches, I publish an invalidation event with Redis pub/sub or Service Bus that each server handles, or I keep L1 TTLs very short. Versioned keys or tags let me drop a whole group at once.

### Cache stampede (thundering herd / dog-piling)

**In simple words:** A stampede happens when a popular key expires and many requests miss at the same time. They all recompute the same expensive result and overload the database. Fixes are single-flight loading (one loader per key), serving slightly old data while one task refreshes, adding random *jitter* to TTLs, and warming the cache after a deploy.

**Real-life example:** A shop opens its doors in the morning and the whole crowd rushes to one counter at the same second.

**Interview question:** How do you prevent a cache stampede?

**Simple answer:** I make one caller load the data while others wait or get the stale value. I use a per-key lock, a Redis `SET NX` lock or `HybridCache`. I also use stale-while-revalidate or refresh-ahead for hot keys, and TTL jitter so keys do not all expire together.

### Cache penetration

**In simple words:** Cache penetration happens when requests ask for data that does not exist, like random IDs from an attacker or a bug. Nothing is ever cached for them, so every request goes to the database. Fixes are checking the input, caching the "not found" result for a short time, and using a *Bloom filter* (a compact structure that can say "definitely not present").

**Real-life example:** Someone keeps calling a library asking for a book it never had. If the librarian searches the shelves every time, they waste the whole day; a note saying "we do not have this book" stops it.

**Interview question:** What is cache penetration and how do you fix it?

**Simple answer:** It is when requests for missing data always miss the cache and hit the database. I validate input, cache null results with a short TTL like 30 seconds, and can add a Bloom filter of valid IDs. I also rate-limit abusive clients.

### Cache avalanche

**In simple words:** A cache avalanche happens when many keys expire at the same moment, or the whole cache goes down. Then the database is flooded with requests. Fixes are adding random jitter to TTLs, warming the cache in stages, running Redis with replicas and failover, keeping a small L1 cache, and protecting the database with rate limits and circuit breakers.

**Real-life example:** If every streetlight in a city were set to switch off at the same second, the power company would see a huge sudden change. Staggering them avoids the shock.

**Interview question:** What is the difference between penetration, avalanche and stampede?

**Simple answer:** Penetration: requests for keys that do not exist always reach the database; fix with null caching, a Bloom filter and validation. Avalanche: many keys expire at once or the cache dies; fix with jitter, high availability and database protection. Stampede: many requests miss one hot key together; fix with single flight.

### Hot key

**In simple words:** A *hot key* is one key that gets far more traffic than others, like a celebrity product or the home page config. In a Redis cluster, each key lives on one shard (one node), so that node's CPU or network gets overloaded, even if you add more nodes. Fixes are a short-TTL L1 cache in each app server, copying the key to several keys, or caching the HTTP response in a CDN.

**Real-life example:** In a supermarket with ten checkouts, everyone queues at the one that sells lottery tickets.

**Interview question:** How do you handle a hot key in Redis?

**Simple answer:** First I add an in-process L1 cache with a short TTL, for example with HybridCache, so most reads never reach Redis. I can also copy the value to several keys, like `product:42#0` to `#7`, and read a random one. For full HTTP responses, a CDN or output cache takes the load.

### Stale data and inconsistency

**In simple words:** Stale data means the cache shows an older value than the database. Causes include missed invalidations, a race between a read and a write, replica lag, per-server L1 caches and long TTLs. Fix it with invalidation on write plus a TTL, invalidation events across servers, and version numbers on values. For decisions like checkout, always read the real source.

**Real-life example:** A train station board still shows the old platform after a last-minute change, so some passengers go to the wrong place.

**Interview question:** A price changed, but some users still see the old one. What do you do?

**Simple answer:** I check every layer: Redis, L1 memory caches, output cache, CDN and the browser. The admin write path must delete the key or publish a `PriceChanged` event to all servers, and purge the CDN. I shorten TTLs for price data, and checkout always reads the price from the database.

### HTTP caching: Cache-Control, ETag, response caching, output caching, CDN

**In simple words:** HTTP lets browsers, proxies and CDNs reuse responses. `Cache-Control: max-age=60` allows reuse for 60 seconds; `no-store` means do not store at all. An *ETag* is a version tag: if the client's copy still matches, the server replies `304 Not Modified` with no body. *Output caching* (.NET 7+) is a server-side cache you control with policies and tags. A *CDN* caches content in locations close to users.

**Real-life example:** A newspaper stand near your home keeps today's paper, so you do not travel to the printing press. If you already have today's edition, the seller just says "you already have the latest".

**Interview question:** What does `Cache-Control: no-cache` mean?

**Simple answer:** It does not mean "do not cache". The response may be stored, but it must be checked with the server before reuse, using an ETag and `If-None-Match`; an unchanged response returns 304. `no-store` is the one that forbids storing. Output caching does not cache authenticated responses by default, and I keep it that way.

```csharp
builder.Services.AddOutputCache(o =>
    o.AddPolicy("Products", b => b.Expire(TimeSpan.FromMinutes(5)).Tag("products")));
app.UseOutputCache();
app.MapGet("/products", GetProducts).CacheOutput("Products");
```

### Cache key design

**In simple words:** A good key includes everything that changes the value: tenant, user ID for private data, culture, currency, page and filters. A common pattern is `app:entity:version:id`, like `shop:product:v2:42:en-US`. The version part means a new deploy does not read old data in an old format. Keep keys short, hash very long ones, and never put personal data or secrets in keys.

**Real-life example:** A post office address needs the country, city, street and house number. If you skip one part, the letter goes to the wrong home.

**Interview question:** How do you design cache keys?

**Simple answer:** I use a consistent prefix like `shop:product:v2:{id}`, and I add every input that changes the result, such as user, tenant or culture. A schema version in the key protects me when the cached shape changes. Missing the user ID in a private key is a real security bug, because users could see each other's data.

### Serialization

**In simple words:** A distributed cache stores bytes, so objects must be serialized (turned into bytes). `System.Text.Json` is built in, readable and handles added fields well. MessagePack or Protobuf are smaller and faster but need extra setup. Compress only large values. Never use `BinaryFormatter`, because it is insecure and removed. Cache simple DTOs, not EF Core entities.

**Real-life example:** Packing a bed so it fits in a delivery van: you take it apart and pack it flat (serialize), then build it again at the new home (deserialize).

**Interview question:** Which serializer do you use for cached values, and what do you cache?

**Simple answer:** By default I use `System.Text.Json`, ideally with source generation for speed. For very hot or large data I may choose MessagePack and compress big values. I cache small DTOs or records, not EF entities, because entities have navigation cycles and tracking state.

### Monitoring the hit ratio

**In simple words:** The *hit ratio* is hits divided by (hits plus misses). It shows how often the cache saves a database call. A low ratio can mean TTLs are too short, keys are too specific, invalidation is too broad, or memory is too small and keys get evicted. Watch it per cache and per key prefix, along with evictions, memory use and latency.

**Real-life example:** A shop counts how often a customer finds the item at the front counter versus how often staff must go to the store room.

**Interview question:** How do you measure whether your cache is effective?

**Simple answer:** I track the hit ratio per cache and key prefix, plus evictions, memory, latency and database load. Redis `INFO stats` shows hits and misses, Azure Monitor has cache metrics, and I add OpenTelemetry counters in the app. I alert if the hit ratio drops below a target like 80%.

```bash
redis-cli INFO stats    # keyspace_hits, keyspace_misses, evicted_keys
```
