## Caching Fundamentals

### Why caching?

**Definition.** A cache stores copies of data that is expensive to fetch or compute in a faster, closer place, so repeated requests are served without repeating the work.

**Why it matters.** Three wins at once:
- **Latency** — Redis/memory answers in 0.1-2 ms; a SQL query over the network takes 5-100+ ms; a remote API call 100+ ms.
- **Load** — the database sees a fraction of the reads, so it can serve more users or be a smaller tier.
- **Cost** — fewer DTUs/vCores, fewer paid third-party API calls, less egress.

**Hit ratio maths.** Average latency = `h x Tcache + (1 - h) x (Tcache + Tsource)`.

```text
Tcache = 1 ms, Tsql = 40 ms
hit ratio 0%  -> 41 ms     DB sees 100% of reads
hit ratio 90% -> 5 ms      DB sees 10%   (8x faster, 10x less DB load)
hit ratio 99% -> 1.4 ms    DB sees 1%
```

Caching is also a *source of bugs* (stale data, inconsistency, stampedes). Interviewers want to hear the trade-off: **"There are only two hard things: cache invalidation and naming things."**

### Request flow: Client -> API -> Redis -> SQL Server

```text
Cache HIT
 1. Client  --GET /products/42-->  API
 2. API     --GET product:42-->    Redis
 3. Redis   --value (1 ms)------>  API
 4. API     --200 JSON-------->    Client           (SQL Server not touched)

Cache MISS (cache-aside)
 1. Client  --GET /products/42-->  API
 2. API     --GET product:42-->    Redis
 3. Redis   --nil (miss)------->   API
 4. API     --SELECT ... WHERE Id=42--> SQL Server
 5. SQL     --row (30 ms)------>   API
 6. API     --SET product:42 EX 600--> Redis        (populate; TTL 10 min)
 7. API     --200 JSON-------->    Client

Write (update price)
 1. Client  --PUT /products/42-->  API
 2. API     --UPDATE Products...--> SQL Server      (source of truth first)
 3. API     --DEL product:42-->    Redis            (invalidate; next read repopulates)
 4. API     --204-------------->   Client
```

### What to cache (and what not to)

| Cache it | Do not cache it (or be very careful) |
|---|---|
| Read-heavy, rarely changing data: catalogue, categories, countries, currencies, config | Data that must be exactly current: account balance, stock at checkout, payment status |
| Expensive computations/aggregations: dashboards, reports, recommendations | Write-heavy data with low read reuse (hit ratio too low to pay off) |
| Results of slow external calls: exchange rates, geo lookups | Large blobs better served by a CDN/blob storage |
| User session, JWT validation results, permissions (short TTL) | Per-user private data in a shared key without user id in the key (data leak!) |
| Rate-limit counters, idempotency keys, locks (Redis as a store) | Authorisation decisions with long TTLs (revocation delay is a security risk) |
| Rendered fragments / full responses (output cache) | Anything cheaper to recompute than to fetch from the cache |

Rule: *cache data that is read much more often than it changes and where being a few seconds/minutes stale is acceptable.* Decide the acceptable staleness (the TTL) with the business.

## In-Memory Caching

### IMemoryCache

**Definition.** `IMemoryCache` is a cache inside your process's memory (heap). Fastest possible (no network, no serialization — you get the same object reference), but **per instance**: two pods have two different caches, and a restart empties it.

```csharp
// Program.cs
builder.Services.AddMemoryCache(o =>
{
    o.SizeLimit = 10_000;                  // abstract "units"; entries must declare Size
    o.CompactionPercentage = 0.25;         // when full, evict 25% (lowest priority first)
    o.ExpirationScanFrequency = TimeSpan.FromMinutes(1);
    o.TrackStatistics = true;              // enables cache.GetCurrentStatistics() (.NET 7+)
});

public sealed class ProductService(IMemoryCache cache, IProductRepository repo)
{
    public Task<ProductDto?> GetAsync(int id, CancellationToken ct) =>
        cache.GetOrCreateAsync($"product:{id}", async entry =>
        {
            entry.AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(10); // hard upper bound
            entry.SlidingExpiration = TimeSpan.FromMinutes(2);                 // extended on each read
            entry.Size = 1;                                                    // required with SizeLimit
            entry.Priority = CacheItemPriority.Normal;                         // eviction order
            entry.RegisterPostEvictionCallback((key, _, reason, _) =>
                Console.WriteLine($"{key} evicted: {reason}"));                // Expired, Capacity, Removed...
            return await repo.GetByIdAsync(id, ct);       // null results are cached too
        });

    public void Invalidate(int id) => cache.Remove($"product:{id}");
}
```

**Expiration types.**

| | Absolute | Sliding |
|---|---|---|
| Meaning | expires at a fixed time after creation | expires if *not accessed* for the window; each access resets it |
| Risk | stale until it expires | a hot item **never expires** (stays stale forever) |
| Use | most data | sessions, "recently used" data |

Always combine sliding with an absolute cap (sliding must be <= absolute).

**Size limits and eviction.** `IMemoryCache` has **no default size limit** — a cache that is not bounded can eat all RAM (a common production incident). With `SizeLimit` set, every entry must set `Size` (else `InvalidOperationException`), and when the limit is hit the cache *compacts*: expired entries first, then by priority (`Low` -> `Normal` -> `High`; `NeverRemove` is skipped), then by least-recently/soonest-expiring. It does **not** evict automatically on OS memory pressure. Beware: one `MemoryCache` per `AddMemoryCache()`; do not use `string` keys that include unbounded user input.

:::warn In-memory cache gotchas
- **Mutable cached objects.** You receive the *same reference* as every other caller. If one request mutates it, everyone sees the change. Cache immutable DTOs/records.
- **Multi-instance inconsistency.** Pod A invalidates, pod B still serves the old value until TTL. Use short TTLs, a distributed cache, or pub/sub invalidation.
- **`GetOrCreateAsync` is not atomic.** Under concurrency the factory may run several times (stampede). See below.
- **Unbounded keys.** `cache.Set($"search:{query}")` with free text grows without limit.
:::

### Stampede protection (single flight)

**Problem.** A hot key expires; 500 concurrent requests all miss and all hit the database at once.

**Fix.** Allow only **one** caller per key to compute; others wait and reuse the result. A striped array of `SemaphoreSlim` avoids a dictionary that grows forever:

```csharp
public sealed class SingleFlightCache(IMemoryCache cache)
{
    private static readonly SemaphoreSlim[] Gates =
        Enumerable.Range(0, 128).Select(_ => new SemaphoreSlim(1, 1)).ToArray();

    public async Task<T> GetOrCreateAsync<T>(string key,
        Func<CancellationToken, Task<T>> factory, TimeSpan ttl, CancellationToken ct) where T : class
    {
        if (cache.TryGetValue(key, out T? hit) && hit is not null) return hit;   // fast path

        var gate = Gates[(uint)key.GetHashCode() % Gates.Length];                // per-key stripe
        await gate.WaitAsync(ct);
        try
        {
            if (cache.TryGetValue(key, out hit) && hit is not null) return hit;  // double-check
            var value = await factory(ct);                                       // only one runs
            cache.Set(key, value, new MemoryCacheEntryOptions
                { AbsoluteExpirationRelativeToNow = ttl, Size = 1 });
            return value;
        }
        finally { gate.Release(); }
    }
}
```

Alternative: cache a `Lazy<Task<T>>` per key so concurrent callers await the same task (remove it from the cache if the task faults). In .NET 9, **HybridCache** does this for you (below).

## Distributed Caching

### IDistributedCache

**Definition.** A cache shared by all instances, stored outside the app process (Redis, SQL Server, NCache). Values are **bytes**, so you serialise. Survives app restarts and keeps all pods consistent with each other.

```csharp
public interface IDistributedCache      // Microsoft.Extensions.Caching.Distributed
{
    byte[]? Get(string key);                      Task<byte[]?> GetAsync(string key, CancellationToken t = default);
    void Set(string key, byte[] v, DistributedCacheEntryOptions o);
    Task SetAsync(string key, byte[] v, DistributedCacheEntryOptions o, CancellationToken t = default);
    void Refresh(string key);                     Task RefreshAsync(string key, CancellationToken t = default);
    void Remove(string key);                      Task RemoveAsync(string key, CancellationToken t = default);
}
```

Helper extensions with `System.Text.Json`:

```csharp
public static class DistributedCacheJson
{
    public static async Task<T?> GetJsonAsync<T>(this IDistributedCache cache,
        string key, CancellationToken ct = default)
    {
        byte[]? bytes = await cache.GetAsync(key, ct);
        return bytes is null ? default : JsonSerializer.Deserialize<T>(bytes);
    }

    public static Task SetJsonAsync<T>(this IDistributedCache cache, string key, T value,
        TimeSpan ttl, CancellationToken ct = default) =>
        cache.SetAsync(key, JsonSerializer.SerializeToUtf8Bytes(value),
            new DistributedCacheEntryOptions { AbsoluteExpirationRelativeToNow = ttl }, ct);
}
```

| | In-memory (`IMemoryCache`) | Distributed (`IDistributedCache`/Redis) |
|---|---|---|
| Speed | ns-us, no serialization | 0.2-2 ms network + serialization |
| Scope | per process | shared by all instances |
| Consistency across pods | none (each has its own) | single copy |
| Survives restart | no | yes (Redis with persistence, SQL) |
| Capacity | process RAM (competes with app) | separate memory, can be large |
| Failure mode | none | cache outage/network blips must be handled |
| Best for | tiny, hot, per-instance reference data | sessions, shared lookups, anything that must be consistent across pods |

Implementations: **Redis** (`AddStackExchangeRedisCache`), **SQL Server** (`AddDistributedSqlServerCache`), NCache, Cosmos DB; `AddDistributedMemoryCache()` is only an in-process stand-in for dev/tests (it is *not* distributed).

### Redis

**Definition.** Redis is an in-memory data-structure server: single-threaded command execution (so each command is atomic), sub-millisecond latency, optional persistence, replication and clustering. Much more than a key-value cache: counters, queues, leaderboards, locks, pub/sub, streams.

#### Data structures with StackExchange.Redis

```csharp
// Register ONE multiplexer per app: it is thread-safe and expensive to create
builder.Services.AddSingleton<IConnectionMultiplexer>(_ =>
    ConnectionMultiplexer.Connect("redis:6379,abortConnect=false,connectRetry=3"));

public sealed class RedisDemo(IConnectionMultiplexer mux)
{
    private readonly IDatabase _db = mux.GetDatabase();

    public async Task RunAsync()
    {
        // STRING: cache value with TTL, counters
        await _db.StringSetAsync("product:42", "{\"id\":42,\"price\":19.99}", TimeSpan.FromMinutes(10));
        RedisValue json = await _db.StringGetAsync("product:42");        // json.HasValue == false on miss
        long views = await _db.StringIncrementAsync("views:product:42"); // atomic counter

        // HASH: object fields (shopping cart: sku -> qty)
        await _db.HashSetAsync("cart:u1",
            new[] { new HashEntry("sku-1", 2), new HashEntry("sku-2", 1) });
        await _db.HashIncrementAsync("cart:u1", "sku-1", 1);
        HashEntry[] cart = await _db.HashGetAllAsync("cart:u1");

        // LIST: recent activity (keep last 10)
        await _db.ListLeftPushAsync("recent:u1", "product:42");
        await _db.ListTrimAsync("recent:u1", 0, 9);
        RedisValue[] recent = await _db.ListRangeAsync("recent:u1", 0, 9);

        // SET: unique members, intersections (tags, followers)
        await _db.SetAddAsync("tag:red", new RedisValue[] { "p1", "p2", "p3" });
        await _db.SetAddAsync("tag:sale", new RedisValue[] { "p2", "p3", "p9" });
        RedisValue[] both = await _db.SetCombineAsync(SetOperation.Intersect, "tag:red", "tag:sale");

        // SORTED SET: leaderboard / top-N / time-ordered index
        await _db.SortedSetAddAsync("bestsellers", "p42", 1200);
        await _db.SortedSetIncrementAsync("bestsellers", "p42", 5);
        SortedSetEntry[] top = await _db.SortedSetRangeByRankWithScoresAsync(
            "bestsellers", 0, 9, Order.Descending);

        // TTL on any key
        await _db.KeyExpireAsync("recent:u1", TimeSpan.FromDays(7));
    }
}
```

| Type | Typical use |
|---|---|
| String | cached JSON/page, counters, flags, distributed lock (`SET NX PX`) |
| Hash | object with fields; cart; partial updates without rewriting a blob |
| List | queue/stack, recent items (`LPUSH` + `LTRIM`) |
| Set | uniqueness, tags, set math (intersect/union) |
| Sorted set | leaderboard, rate-limiting sliding window, scheduled jobs (score = timestamp) |
| Stream, Bitmap, HyperLogLog, Geo | event log with consumer groups, daily-active flags, approximate unique counts, nearby search |

#### TTL, persistence, eviction

- **TTL**: `EXPIRE key seconds` / `SET key v EX 600`. Expired keys are removed lazily on access plus an active sampling cycle.
- **Persistence.** *RDB* = periodic point-in-time snapshots (compact, fast restart, can lose the last minutes). *AOF* = append-only log of writes, `fsync` always/every second/never (more durable, bigger, slower restart). Many setups use both. For a **pure cache**, persistence is often disabled — a restart just means a cold cache.
- **Eviction** when `maxmemory` is reached is controlled by `maxmemory-policy`:

| Policy | Behaviour | Use |
|---|---|---|
| `noeviction` (default) | writes fail with OOM error | Redis as a database |
| `allkeys-lru` | evict least recently used among all keys | **general-purpose cache (common choice)** |
| `allkeys-lfu` | evict least frequently used | skewed hot/cold access |
| `volatile-lru` / `volatile-lfu` | only keys that have a TTL | mixed: cache keys with TTL + permanent keys |
| `volatile-ttl` | evict nearest expiry first | |
| `allkeys-random` / `volatile-random` | random | rarely |

```text
redis.conf:   maxmemory 2gb
              maxmemory-policy allkeys-lru
```

#### Pub/Sub (e.g., cross-node cache invalidation)

Fire-and-forget: subscribers connected at publish time receive the message; no persistence or replay (use Streams for durable messaging).

```csharp
ISubscriber sub = mux.GetSubscriber();
await sub.SubscribeAsync(RedisChannel.Literal("product-changed"), (channel, message) =>
{
    localCache.Remove($"product:{message}");     // drop the L1 copy on every node
});

// publisher (after writing to the database)
await sub.PublishAsync(RedisChannel.Literal("product-changed"), "42");
```

#### High availability and scale

- **Replication**: primary + replicas (async), replicas serve reads, can be promoted.
- **Sentinel**: monitors a primary/replica set and automates failover; clients discover the current primary. No sharding — dataset limited to one node's memory.
- **Redis Cluster**: shards data across nodes by **16384 hash slots** (`CRC16(key) mod 16384`), each shard with replicas. Multi-key commands must hit the same slot: use hash tags, e.g. `{user:1}:cart` and `{user:1}:profile`.
- **Azure Cache for Redis**: managed Redis with tiers (Basic: single node, no SLA, dev/test; Standard: primary + replica; Premium: clustering, persistence, VNet; Enterprise: Redis Enterprise modules like RediSearch/Bloom). Microsoft is positioning **Azure Managed Redis** as the successor service — check the current offering and retirement timeline before choosing. Use TLS (port 6380), access keys in Key Vault or Entra ID auth, and patch windows.

:::warn Redis in production
- One `ConnectionMultiplexer` per app, never per request.
- Always set a TTL on cache keys, or memory fills forever.
- Avoid `KEYS *` (blocks the server); use `SCAN`. Avoid huge values (>100 KB) and giant collections (`big keys` block the single thread).
- Redis is not a durable database unless you configured persistence and replication; do not treat the cache as the only copy of important data.
:::

### ASP.NET Core: AddStackExchangeRedisCache

```csharp
builder.Services.AddStackExchangeRedisCache(o =>
{
    o.Configuration = builder.Configuration.GetConnectionString("Redis");
    // "myredis.redis.cache.windows.net:6380,password=...,ssl=True,abortConnect=False"
    o.InstanceName = "shop:";          // prefix: keys become "shop:product:42"
});

public sealed class PriceController(IDistributedCache cache, IPriceRepository repo) : ControllerBase
{
    [HttpGet("prices/{sku}")]
    public async Task<ActionResult<PriceDto>> Get(string sku, CancellationToken ct)
    {
        var key = $"price:{sku}";
        var cached = await cache.GetJsonAsync<PriceDto>(key, ct);
        if (cached is not null) return cached;

        var price = await repo.GetAsync(sku, ct);
        if (price is null) return NotFound();
        await cache.SetJsonAsync(key, price, TimeSpan.FromMinutes(5), ct);
        return price;
    }
}
```

**SQL Server as a distributed cache** (when you already have SQL and low volume; slower than Redis):

```bash
dotnet tool install --global dotnet-sql-cache
dotnet sql-cache create "Server=.;Database=CacheDb;Trusted_Connection=True;TrustServerCertificate=True" dbo AppCache
```

```csharp
builder.Services.AddDistributedSqlServerCache(o =>
{
    o.ConnectionString = builder.Configuration.GetConnectionString("CacheDb");
    o.SchemaName = "dbo";
    o.TableName = "AppCache";
    o.ExpiredItemsDeletionInterval = TimeSpan.FromMinutes(30);   // background cleanup
});
```

Session state in ASP.NET Core also uses `IDistributedCache`: `AddSession()` + a registered distributed cache gives sticky-free sessions.

### HybridCache (.NET 9)

**Definition.** `HybridCache` (package `Microsoft.Extensions.Caching.Hybrid`) is a two-level cache with one API: **L1** = in-process memory, **L2** = any registered `IDistributedCache` (e.g., Redis). It adds what people hand-wrote on top of `IMemoryCache` + `IDistributedCache`.

**Why it matters.**
- **Stampede protection built in**: concurrent requests for the same key share one factory call (within a process; cross-node dedup relies on L2).
- **L1 + L2 in one call**: hot reads served from memory (no network); L2 keeps instances consistent and survives restarts.
- **Serialization handled** (System.Text.Json by default; `string` and `byte[]` special-cased; pluggable serializers).
- **Tags** for group invalidation.

```csharp
// Program.cs
builder.Services.AddStackExchangeRedisCache(o => o.Configuration = "redis:6379");  // L2 (optional)
builder.Services.AddHybridCache(o =>
{
    o.MaximumPayloadBytes = 1024 * 1024;         // bigger values are not cached
    o.MaximumKeyLength = 512;
    o.DefaultEntryOptions = new HybridCacheEntryOptions
    {
        Expiration = TimeSpan.FromMinutes(10),          // L2 TTL
        LocalCacheExpiration = TimeSpan.FromMinutes(1)  // L1 TTL (keep short: see warning)
    };
});

public sealed class ProductQueries(HybridCache cache, IProductRepository repo)
{
    public ValueTask<ProductDto?> GetAsync(int id, CancellationToken ct = default) =>
        cache.GetOrCreateAsync(
            $"product:{id}",
            async token => await repo.GetByIdAsync(id, token),   // runs once per key on a miss
            tags: ["products", $"product:{id}"],
            cancellationToken: ct);

    // avoid closure allocations on hot paths: pass state explicitly
    public ValueTask<ProductDto?> GetFastAsync(int id, CancellationToken ct = default) =>
        cache.GetOrCreateAsync($"product:{id}", (repo, id),
            static async (state, token) => await state.repo.GetByIdAsync(state.id, token),
            cancellationToken: ct);

    public async Task OnPriceChangedAsync(int id, CancellationToken ct)
    {
        await cache.RemoveAsync($"product:{id}", ct);      // one key (L2 + this node's L1)
    }

    public ValueTask OnCatalogReloadedAsync(CancellationToken ct) =>
        cache.RemoveByTagAsync("products", ct);            // everything tagged "products"
}
```

Other notes:
- With **no L2 registered**, HybridCache works as L1 only (still gives stampede protection).
- Per-call options: `new HybridCacheEntryOptions { Expiration = ..., Flags = HybridCacheEntryFlags.DisableDistributedCache }`.
- Tag invalidation is *logical* (entries are treated as stale), supported by the default implementation.
- `SetAsync` exists to write a value directly.

:::warn HybridCache and multiple nodes
`RemoveAsync` clears L2 and the **current node's** L1. Other nodes keep their L1 copy until `LocalCacheExpiration` elapses (as of .NET 9 there is no built-in cross-node L1 invalidation backplane; verify the current release notes). Keep L1 TTL short (seconds to a minute) for data that changes, or publish an invalidation message yourself (Redis pub/sub).
:::

:::q IMemoryCache vs IDistributedCache vs HybridCache — what do you pick?
`IMemoryCache` for tiny, hot, per-instance data where small inconsistency is fine. `IDistributedCache` (Redis) when all instances must share one copy or the cache must survive restarts. On .NET 9+ I prefer `HybridCache` because it gives me both levels, stampede protection and serialization with one API, and I only drop to the lower-level interfaces for special needs.
:::

:::q Redis is single-threaded — how is it still fast?
Everything is in memory, commands are tiny O(1)/O(log n) operations, I/O is multiplexed with an event loop, and there is no lock contention. The trade-off is that one slow command (`KEYS *`, huge `SMEMBERS`, big Lua script) blocks everyone, so I avoid O(N) commands on big keys.
:::
