## Caching Patterns

### Cache-aside (lazy loading)

**Definition.** The application owns the logic: read cache, on miss read the database and populate the cache; on write update the database and **invalidate** (delete) the cache key.

**Why it matters.** It is the default pattern for ASP.NET Core + Redis: simple, works with any cache, and a cache outage only costs speed (the app can still read the DB).

Complete example as a decorator over an EF Core repository (fail-open, null caching, TTL jitter, single-flight, invalidate on write):

```csharp
public sealed record Product(int Id, string Name, decimal Price);

public interface IProductRepository
{
    Task<Product?> GetByIdAsync(int id, CancellationToken ct);
    Task UpdatePriceAsync(int id, decimal newPrice, CancellationToken ct);
}

// The real repository: the source of truth
public sealed class EfProductRepository(ShopDb db) : IProductRepository
{
    public async Task<Product?> GetByIdAsync(int id, CancellationToken ct) =>
        await db.Products.AsNoTracking().Where(p => p.Id == id)
                .Select(p => new Product(p.Id, p.Name, p.Price)).FirstOrDefaultAsync(ct);

    public Task UpdatePriceAsync(int id, decimal newPrice, CancellationToken ct) =>
        db.Products.Where(p => p.Id == id)
                   .ExecuteUpdateAsync(s => s.SetProperty(p => p.Price, newPrice), ct);
}

// The caching decorator
public sealed class CachedProductRepository(
    IProductRepository inner, IDistributedCache cache, ILogger<CachedProductRepository> log)
    : IProductRepository
{
    private static readonly TimeSpan Ttl = TimeSpan.FromMinutes(10);
    private static readonly TimeSpan NullTtl = TimeSpan.FromSeconds(30);   // negative caching
    private static readonly byte[] NullMarker = "__null__"u8.ToArray();
    private static readonly SemaphoreSlim[] Gates =
        Enumerable.Range(0, 64).Select(_ => new SemaphoreSlim(1, 1)).ToArray();

    private static string Key(int id) => $"shop:product:v1:{id}";    // app:entity:version:id

    public async Task<Product?> GetByIdAsync(int id, CancellationToken ct)
    {
        var key = Key(id);

        var bytes = await TryGetAsync(key, ct);                       // 1. cache lookup
        if (bytes is not null) return Decode(bytes);

        var gate = Gates[(uint)key.GetHashCode() % Gates.Length];     // 2. one loader per key
        await gate.WaitAsync(ct);
        try
        {
            bytes = await TryGetAsync(key, ct);                       // double-check after waiting
            if (bytes is not null) return Decode(bytes);

            var product = await inner.GetByIdAsync(id, ct);           // 3. source of truth
            await TrySetAsync(key,
                product is null ? NullMarker : JsonSerializer.SerializeToUtf8Bytes(product),
                product is null ? NullTtl : WithJitter(Ttl), ct);     // 4. populate
            return product;
        }
        finally { gate.Release(); }
    }

    public async Task UpdatePriceAsync(int id, decimal newPrice, CancellationToken ct)
    {
        await inner.UpdatePriceAsync(id, newPrice, ct);               // 1. DB first (truth)
        try { await cache.RemoveAsync(Key(id), ct); }                 // 2. then DELETE the key
        catch (Exception ex) when (ex is not OperationCanceledException)
        { log.LogError(ex, "Cache invalidation failed for product {Id}", id); } // TTL is the safety net
    }

    private static Product? Decode(byte[] bytes) =>
        bytes.AsSpan().SequenceEqual(NullMarker) ? null : JsonSerializer.Deserialize<Product>(bytes);

    private static TimeSpan WithJitter(TimeSpan ttl, double percent = 0.2) =>   // +/- 20%
        ttl * (1 + (Random.Shared.NextDouble() * 2 - 1) * percent);

    // the cache must never take the application down: treat errors as misses
    private async Task<byte[]?> TryGetAsync(string key, CancellationToken ct)
    {
        try { return await cache.GetAsync(key, ct); }
        catch (Exception ex) when (ex is not OperationCanceledException)
        { log.LogWarning(ex, "Cache read failed for {Key}", key); return null; }
    }

    private async Task TrySetAsync(string key, byte[] value, TimeSpan ttl, CancellationToken ct)
    {
        try
        {
            await cache.SetAsync(key, value,
                new DistributedCacheEntryOptions { AbsoluteExpirationRelativeToNow = ttl }, ct);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        { log.LogWarning(ex, "Cache write failed for {Key}", key); }
    }
}

// Program.cs: decorate without a library
builder.Services.AddScoped<EfProductRepository>();
builder.Services.AddScoped<IProductRepository>(sp => new CachedProductRepository(
    sp.GetRequiredService<EfProductRepository>(),
    sp.GetRequiredService<IDistributedCache>(),
    sp.GetRequiredService<ILogger<CachedProductRepository>>()));
```

**Why delete on write instead of update the cache?** Updating two stores is a dual write; concurrent writers can leave the cache with an older value than the DB. Deleting is idempotent and the next read repopulates from the truth. A small race still exists (a reader loads the old row, a writer updates + deletes, then the reader stores the old value) — the TTL bounds the damage; for stricter needs use short TTLs, a delayed second delete, or versioned values.

### Read-through, write-through, write-behind, refresh-ahead

| | Read-through | Write-through | Write-behind (write-back) | Refresh-ahead |
|---|---|---|---|---|
| Who talks to the DB | **cache layer** loads on miss (app only sees the cache) | cache layer writes to DB **synchronously** with the cache | cache acknowledges, **flushes to DB later** (async/batched) | cache **reloads hot keys before TTL expires** |
| Typical impl. | NCache/Redis Enterprise providers, `HybridCache.GetOrCreateAsync` (from the caller's view) | cache provider with a "writer" | Redis + background worker | scheduled/background refresher |
| Consistency | like cache-aside | strong (cache == DB after write) | **eventual; data loss possible** | fresh for hot keys |
| Read latency | first miss slow | fast | fast | consistently fast (no miss spikes) |
| Write latency | n/a | slower (two writes) | **fastest** | n/a |
| Risk | cold start | writes cached data nobody reads; cache is on the write path | cache crash before flush loses writes; ordering; complexity | wasted refreshes of keys no longer used |
| Best for | read-heavy, simple app code | data that must be fresh right after write | high-volume counters, likes, telemetry, view counts | hot dashboards, home page, price lists |

Cache-aside vs read-through: same behaviour, different owner of the loading code. In .NET, `HybridCache.GetOrCreateAsync(key, factory)` feels like read-through even though your factory is the loader.

**Write-behind sketch** — product view counters in Redis, flushed to SQL every 30 seconds (losing a few seconds of counts on a crash is acceptable here):

```csharp
// hot path: O(1), no database
public Task RecordViewAsync(int productId) =>
    _redis.HashIncrementAsync("views:pending", productId, 1);

// background flusher
public sealed class ViewCountFlusher(IConnectionMultiplexer mux, IServiceScopeFactory scopes)
    : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stop)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(30));
        while (await timer.WaitForNextTickAsync(stop))
        {
            var redis = mux.GetDatabase();
            var pending = await redis.HashGetAllAsync("views:pending");
            if (pending.Length == 0) continue;

            using var scope = scopes.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<ShopDb>();
            foreach (var e in pending)
            {
                var id = (int)e.Name; var delta = (long)e.Value;
                await db.Products.Where(p => p.Id == id)
                    .ExecuteUpdateAsync(s => s.SetProperty(p => p.Views, p => p.Views + delta), stop);
                await redis.HashDecrementAsync("views:pending", e.Name, delta);  // subtract flushed amount
            }
        }
    }
}
```

**Refresh-ahead / stale-while-revalidate sketch** — serve the cached value and refresh in the background when it is *soft-expired*:

```csharp
public sealed record Cached<T>(T Value, DateTime SoftExpiresUtc);

public async Task<T> GetAsync<T>(string key, Func<CancellationToken, Task<T>> load, CancellationToken ct)
{
    var entry = await _cache.GetJsonAsync<Cached<T>>(key, ct);
    if (entry is null) return await RefreshAsync(key, load, ct);          // cold: load inline

    if (entry.SoftExpiresUtc < DateTime.UtcNow)                           // stale but usable
        _ = Task.Run(() => RefreshAsync(key, load, CancellationToken.None)); // fire-and-forget refresh
    return entry.Value;                                                   // always fast
}

private async Task<T> RefreshAsync<T>(string key, Func<CancellationToken, Task<T>> load, CancellationToken ct)
{
    var value = await load(ct);
    await _cache.SetJsonAsync(key, new Cached<T>(value, DateTime.UtcNow.AddMinutes(1)),
                              TimeSpan.FromMinutes(10), ct);               // hard TTL 10 min, soft 1 min
    return value;
}
```
(Guard the background refresh with a per-key lock so a hundred requests do not start a hundred refreshes.)

:::q Cache-aside vs write-through — how do you choose?
Cache-aside is my default: simple, resilient, the app controls caching. I pick write-through when readers must see their own write immediately and I have a cache layer that supports it, accepting extra write latency. Write-behind only for high-volume, loss-tolerant data like counters and telemetry.
:::

## Expiration and Invalidation

### Cache expiration vs invalidation

**Definition.** *Expiration* removes data after a time (TTL) regardless of changes. *Invalidation* removes or refreshes data **because the source changed**. Production caches use both: invalidation for freshness, TTL as the safety net for missed invalidations.

| Strategy | How | Staleness | Complexity | Notes |
|---|---|---|---|---|
| **TTL (absolute)** | key expires N minutes after creation | up to N min | trivial | add jitter to avoid synchronized expiry |
| **Sliding TTL** | resets on access | unbounded for hot keys | low | always pair with an absolute cap |
| **Write-path invalidation** | delete key right after DB write | tiny (race window) | low | needs to know all keys affected by a write |
| **Event-based invalidation** | domain event / CDC / Service Bus message triggers deletes in every cache | seconds | medium | decouples writers from caches; works across services |
| **Versioned keys** | key contains a version/namespace number; bump it to invalidate a whole group | none after bump | low | old keys die by TTL; no key scanning |
| **Tag-based** | entries tagged (`products`, `category:7`); evict by tag | none after evict | medium | `HybridCache.RemoveByTagAsync`, Output cache `EvictByTagAsync`, CDN surrogate keys |
| **Stale-while-revalidate** | serve stale, refresh in background | bounded | medium | great for latency, accepts brief staleness |

```csharp
// Versioned keys: invalidate "all product list pages" with one INCR
public sealed class VersionedKeys(IConnectionMultiplexer mux)
{
    private readonly IDatabase _db = mux.GetDatabase();

    public async Task<string> KeyAsync(string group, string suffix)
    {
        RedisValue v = await _db.StringGetAsync($"ver:{group}");
        return $"{group}:v{(v.HasValue ? (long)v : 0)}:{suffix}";     // products:v7:page=2&cat=5
    }

    public Task InvalidateGroupAsync(string group) =>
        _db.StringIncrementAsync($"ver:{group}");                      // old keys are now unreachable
}
```

```csharp
// Event-based: any service/instance that changes a product publishes; all API nodes subscribe
await subscriber.SubscribeAsync(RedisChannel.Literal("product-changed"), async (_, id) =>
{
    await hybridCache.RemoveAsync($"product:{id}");               // L1 + L2
    await hybridCache.RemoveByTagAsync("product-lists");         // list pages containing it
});
```

:::tip Pick the TTL with the business
"How stale can this be?" Prices on a listing page: 1-5 minutes. Country list: 24 hours. Stock count on the product page: 10-30 seconds, but **never** for the checkout decision. Write the number next to the code.
:::

## Cache Problems and Fixes

### Cache stampede (thundering herd / dog-piling)

A popular key expires and many concurrent requests miss simultaneously, all recomputing the same expensive result.

Fixes:
1. **Single flight / per-key lock** — one loader, others wait (`SemaphoreSlim`, Redis `SET lock NX PX`, `HybridCache`).
2. **Stale-while-revalidate / refresh-ahead** — serve slightly old data while one background task refreshes.
3. **Probabilistic early expiration** (XFetch) — each reader may refresh *slightly before* TTL with rising probability.
4. **TTL jitter** — so keys do not all expire together.
5. **Warm the cache** after deploy/restart (pre-load top-N).

### Cache penetration

Requests for data that **does not exist** (random IDs, attackers, bugs) never populate the cache, so every request hits the DB.

Fixes: validate input (`id > 0`, GUID format); **cache the null result** with a short TTL (done above); put a **Bloom filter** of valid IDs in front (a "no" is certain, a "yes" is probable); rate-limit abusive clients.

```csharp
// Redis Stack / RedisBloom module: BF.ADD / BF.EXISTS
public async Task<bool> MightExistAsync(int productId)
{
    var result = await _db.ExecuteAsync("BF.EXISTS", "bf:products", productId.ToString());
    return (bool)result;        // false => definitely not in DB => return 404 immediately
}
```

### Cache avalanche

Many keys expire at the same instant (e.g., everything loaded at startup with a 10-minute TTL) or the whole cache goes down; the database is flooded.

Fixes: **TTL jitter** (`ttl * random(0.8..1.2)`); staggered warm-up; replicated/HA cache (Redis replicas + Sentinel/Cluster); a second layer (L1 in-process); **protect the DB** with rate limiting, bulkheads and circuit breakers so a cold cache degrades instead of killing it.

### Hot key

One key receives a disproportionate load (a celebrity product, the home-page config). It lives on **one** Redis shard, saturating its CPU/network no matter how many nodes you have.

Fixes: L1 in-process cache in front (HybridCache) with a short TTL; **key replication** (`product:42#0 ... #7`, read a random replica key); client-side caching (Redis tracking); CDN/output caching for the HTTP response; split the value.

### Stale data and inconsistency

Causes: missed invalidations, the read/write race described above, replica lag, per-instance L1 caches, long TTLs. Mitigations: invalidate on write **and** keep a TTL; event-based invalidation across nodes; versioned values (`rowversion`, `UpdatedAt`) so an old write cannot overwrite a newer cached value; read-your-writes by bypassing the cache for the writer's next read; show "as of" timestamps in UIs.

:::warn Never cache these mistakes
- A cache key without the user/tenant/culture for per-user data: user A receives user B's data (a security incident).
- Caching error responses (a transient 500 cached for 10 minutes).
- Caching `null` forever when the row simply was not yet created.
- A cache with no TTL and no memory limit.
- Letting a cache failure throw: always degrade to the database.
:::

## HTTP and Edge Caching

### HTTP caching: Cache-Control, ETag, response caching, output caching, CDN

**Definition.** HTTP defines caching so browsers, proxies and CDNs can reuse responses without hitting your server at all (or with a cheap revalidation).

| Header / directive | Meaning |
|---|---|
| `Cache-Control: max-age=60` | any cache may reuse for 60 s |
| `public` / `private` | shared caches (CDN) allowed / only the user's browser |
| `s-maxage=300` | TTL for shared caches (CDN) only |
| `no-cache` | may store, but **must revalidate** before every reuse |
| `no-store` | do not store at all (sensitive data) |
| `must-revalidate` | do not serve stale after expiry |
| `stale-while-revalidate=30` | serve stale for 30 s while refreshing |
| `immutable` | never changes (fingerprinted assets) |
| `ETag` / `If-None-Match` | validator; server replies **304 Not Modified** with no body if unchanged |
| `Last-Modified` / `If-Modified-Since` | time-based validator |
| `Vary: Accept-Encoding, Accept-Language` | cache separate copies per header value |

```csharp
// Conditional GET with ETag: saves bandwidth and serialization; still hits the DB cheaply
app.MapGet("/products/{id:int}", async (int id, HttpContext http, ShopDb db, CancellationToken ct) =>
{
    var p = await db.Products.AsNoTracking().FirstOrDefaultAsync(x => x.Id == id, ct);
    if (p is null) return Results.NotFound();

    var etag = $"\"{Convert.ToBase64String(p.RowVersion)}\"";         // rowversion as validator
    if (http.Request.Headers.IfNoneMatch.Contains(etag))
        return Results.StatusCode(StatusCodes.Status304NotModified);

    http.Response.Headers.ETag = etag;
    http.Response.Headers.CacheControl = "public, max-age=60, stale-while-revalidate=30";
    return Results.Ok(new ProductDto(p.Id, p.Name, p.Price));
});
```

**Controller attribute** (sets headers; does not by itself cache on the server):

```csharp
[HttpGet("categories")]
[ResponseCache(Duration = 3600, Location = ResponseCacheLocation.Any, VaryByHeader = "Accept-Language")]
public IActionResult Categories() => Ok(_categories);
```

**Response Caching middleware** (`AddResponseCaching()` / `UseResponseCaching()`) stores responses on the server but follows HTTP rules (client headers like `Cache-Control: no-cache` can bypass it, no authorisation-aware logic, no programmatic eviction). Rarely the best choice today.

**Output caching (.NET 7+)** — server-side cache with *policies, tags and eviction*, you control it, not the client:

```csharp
builder.Services.AddOutputCache(o =>
{
    o.AddBasePolicy(b => b.Expire(TimeSpan.FromSeconds(10)));                 // default for GETs
    o.AddPolicy("Products", b => b
        .Expire(TimeSpan.FromMinutes(5))
        .SetVaryByQuery("category", "page")                                    // separate entries
        .Tag("products"));                                                     // for eviction
});
// multi-instance: put entries in Redis (.NET 8+, Microsoft.AspNetCore.OutputCaching.StackExchangeRedis)
// builder.Services.AddStackExchangeRedisOutputCache(o => o.Configuration = "redis:6379");

var app = builder.Build();
app.UseOutputCache();                                                          // after auth/CORS

app.MapGet("/products", GetProducts).CacheOutput("Products");

app.MapPost("/products", async (ProductDto dto, IOutputCacheStore store, ShopDb db, CancellationToken ct) =>
{
    // ... save ...
    await store.EvictByTagAsync("products", ct);                               // invalidate list pages
    return Results.Created();
});
```

Defaults: only `GET`/`HEAD` with `200` are cached, and responses to **authenticated** requests or with `Set-Cookie` are *not* cached unless you explicitly opt in — never override that without varying by user.

| | Response caching | Output caching |
|---|---|---|
| Controlled by | HTTP headers from client/server | server policies |
| Eviction | no | yes (tags, store API) |
| Vary | headers/query keys | headers, query, route, custom, per-policy |
| Stampede protection | no | yes (resource locking) |
| Distributed store | no | yes (Redis) |

**CDN (Azure Front Door/CDN, Cloudflare, CloudFront).** Caches responses at edge locations near users: static assets (fingerprinted file names + `Cache-Control: public, max-age=31536000, immutable`), and cacheable API GETs using `s-maxage`. Mind the **cache key** (query string handling, `Vary`), **never cache `Set-Cookie`/personalised responses on the edge**, and purge by path or surrogate key on changes. A CDN also absorbs DDoS and offloads TLS.

```csharp
app.UseStaticFiles(new StaticFileOptions
{
    OnPrepareResponse = ctx =>
        ctx.Context.Response.Headers.CacheControl = "public,max-age=31536000,immutable"
});
```

## Operating a Cache

### Cache key design

Pattern: `{app}:{entity}:{schemaVersion}:{id}[:{variant}]` e.g. `shop:product:v2:42:en-US`.

- Include everything that changes the value: tenant, user id (for private data), culture, currency, page and sort/filter options (normalise: sorted query params).
- Put a **schema version** in the key so a deploy that changes the cached shape does not deserialise old bytes.
- Keep keys short and ASCII; hash long ones (SHA-256 of a filter JSON). No PII or secrets in keys (they appear in logs and `SCAN`).
- A consistent prefix lets you `SCAN` for a namespace and apply per-prefix monitoring.
- Different TTLs per prefix, not one global value.

### Serialization

| Format | Pros | Cons |
|---|---|---|
| `System.Text.Json` (use source-gen) | readable, built in, tolerant of added fields | larger, slower than binary |
| MessagePack / Protobuf | compact, fast | needs contracts/attributes, not human-readable |
| Compressed JSON (Brotli/GZip) | big payload savings | CPU cost; only for values over a few KB |
| `BinaryFormatter` | **do not use** (removed/insecure) | |

Cache DTOs, not EF entities (navigation cycles, lazy-loading proxies, change-tracker state). Remember values are copied in a distributed cache but shared references in `IMemoryCache`.

### Monitoring the hit ratio

Hit ratio = hits / (hits + misses). Watch it per cache and per key prefix. A drop means TTL too short, keys too specific (unbounded cardinality), invalidation too aggressive, evictions due to memory pressure, or a deploy that changed key format.

```text
redis-cli INFO stats      -> keyspace_hits, keyspace_misses, evicted_keys, expired_keys
redis-cli INFO memory     -> used_memory, maxmemory, mem_fragmentation_ratio
redis-cli --latency       -> round-trip latency
Azure Monitor (Azure Cache for Redis): Cache Hits, Cache Misses, Server Load,
  Used Memory Percentage, Evicted Keys, Connected Clients, Cache Latency
```

```csharp
// Application-level metrics (OpenTelemetry-friendly, .NET 8 IMeterFactory)
public sealed class CacheMetrics
{
    private readonly Counter<long> _hits, _misses;

    public CacheMetrics(IMeterFactory factory)
    {
        var meter = factory.Create("Shop.Cache");
        _hits = meter.CreateCounter<long>("cache.hits");
        _misses = meter.CreateCounter<long>("cache.misses");
    }

    public void Hit(string cache) => _hits.Add(1, new KeyValuePair<string, object?>("cache", cache));
    public void Miss(string cache) => _misses.Add(1, new KeyValuePair<string, object?>("cache", cache));
}
```

Alert on: hit ratio below the target (e.g. <80%), evicted keys rising, memory above 80%, p99 cache latency, connection errors. Also keep an eye on **DB load when the cache is cold**.

## Scenarios

:::scenario Product price changed but users still see the old price
**Situation.** Marketing updates a price in the admin tool. The product page still shows the old price for ~10 minutes; some users see the new one.

**Diagnose.** Several layers can hold the old value: Redis (TTL 10 min, no invalidation on the admin write path), per-instance L1 `IMemoryCache`/HybridCache, output cache, browser/CDN (`max-age=600`). Different nodes/users hit different layers, so behaviour is inconsistent.

**Fix.**
1. The write path (admin API) must **invalidate** the key after the DB commit, or publish a `PriceChanged` event that every API node/the CDN listens to (Redis pub/sub or Service Bus); evict the output-cache tag and purge the CDN path/surrogate key.
2. Shorten L1 and CDN TTLs for price data (e.g., 30-60 s), use `stale-while-revalidate`.
3. **Checkout must always re-read the price from the database** (or the authoritative service) — caches are for display only.
4. Keep the TTL as a safety net and add a "price as of" timestamp; add an integration test that updates a price and asserts the next read is fresh.
:::

:::scenario Redis is down: what happens?
**Situation.** The Redis instance fails over or is unreachable. Dashboards show API p99 jumping from 80 ms to 30 s, then the SQL Server CPU hits 100%.

**Why.** (a) Calls to the dead cache wait for the default timeouts (5 s sync/async) on every request. (b) All reads now fall through to SQL at once. (c) Retries make it worse.

**Fix (design it before it happens).**
- **Fail open**: wrap cache calls in try/catch and treat errors as misses (as in the decorator above). The cache is an optimisation, never a hard dependency.
- **Short timeouts** (e.g., 100-200 ms `AsyncTimeout`/`ConnectTimeout`) and `abortConnect=false` so the app starts and reconnects automatically.
- **Circuit breaker around the cache**: after N failures skip Redis entirely for 30 s instead of paying a timeout on every call.
- **Protect the database**: rate limiting/bulkhead on the expensive queries, single-flight loaders, and an L1 in-process cache (HybridCache) that continues to serve hot data.
- **HA for Redis**: replicas + automatic failover (Sentinel, Cluster, Azure Standard/Premium tier); zone redundancy.
- Alert on cache connection errors; run a game-day that kills Redis.
- Sessions/rate-limit counters in Redis are *not* optional state: decide behaviour (fail open vs closed) per use case.
:::

:::scenario Latency spikes at the top of every hour
**Situation.** A "top products" query takes 3 s. Its cache entry has a 60-minute TTL, set by a job at the top of the hour. Every hour 2,000 concurrent users miss and the DB spikes.

**Fix.** That is a stampede on a hot key. Use single-flight loading (`HybridCache`/lock), refresh-ahead (a background job refreshes the entry at minute 55 and swaps it), add jitter to TTLs, and serve stale-while-revalidate. Pre-warm after deploys.
:::

:::scenario Memory grows until the API pod is OOM-killed
**Situation.** Memory climbs steadily and Kubernetes restarts the pod nightly. Heap dump shows millions of entries in `MemoryCache`.

**Fix.** `IMemoryCache` is unbounded by default. Keys included free-text search terms (unbounded cardinality) and entries had no expiration. Set `SizeLimit` and `Entry.Size`, absolute expirations, cap key cardinality (do not cache long-tail searches), move big data to Redis, and watch `GetCurrentStatistics()` (entries, estimated size, hits/misses).
:::

:::scenario Users sometimes see someone else's data
**Situation.** `/api/me/orders` is wrapped with output caching / a shared Redis key `orders:recent`. A customer reports another person's orders.

**Fix.** Per-user data was cached under a non-user-specific key (or the response was cached despite `Authorization`). Include the user id in the key (`orders:{userId}`), use `private` caching or no caching for personalised endpoints, never override the output-cache default of skipping authenticated requests, add tests that call the endpoint as two users, and purge the poisoned entries.
:::

:::scenario Hit ratio is only 30%
**Situation.** Redis is installed but the DB load barely dropped.

**Diagnose.** Keys too specific (timestamp or raw query string in the key), TTL too short, cached data rarely re-read (low reuse), invalidation too broad (flushing everything on each write), evictions from `maxmemory`, different pods using different key formats, caching write-heavy data. **Fix.** Normalise keys, raise TTL where staleness allows, cache the right things (hot read-mostly data), size the cache properly, measure hits/misses per prefix.
:::

## Quick-fire Q&A

:::q Why use a cache and what are the risks?
It cuts latency, DB load and cost by serving repeated reads from fast memory. The risks are stale data, inconsistency between nodes, stampedes when hot keys expire, extra operational complexity, and a new failure mode (the cache itself). Good caches have a TTL, invalidation on write and fail-open behaviour.
:::

:::q Explain the cache-aside pattern.
Read: check the cache; on a miss load from the DB, store it in the cache with a TTL and return. Write: update the DB, then delete the cache key. The app owns the logic, so a cache outage only slows things down.
:::

:::q Why delete the cache key on update instead of overwriting it?
Overwriting is a dual write; two concurrent updates can leave the cache with the older value. Deleting is idempotent and the next read repopulates from the source of truth. A TTL still bounds any remaining race.
:::

:::q What is the difference between absolute and sliding expiration?
Absolute expires at a fixed time after creation; sliding expires if the item is not accessed within the window and resets on every access. Sliding alone lets hot items live forever and go stale, so combine it with an absolute cap.
:::

:::q How do you prevent a cache stampede?
Make one caller load while others wait or serve stale: per-key lock/`SemaphoreSlim`, Redis `SET NX` lock, `HybridCache` (built-in), stale-while-revalidate or refresh-ahead, plus TTL jitter so keys do not expire together.
:::

:::q Cache penetration vs avalanche vs stampede?
Penetration: requests for non-existent keys always reach the DB (fix: cache nulls, Bloom filter, validation). Avalanche: many keys expire at once or the cache dies (fix: jitter, HA, protect the DB). Stampede: concurrent misses for one hot key (fix: single flight).
:::

:::q What are Redis eviction policies and which do you use for a cache?
They decide what to remove when `maxmemory` is reached: `noeviction`, `allkeys-lru/lfu`, `volatile-lru/lfu/ttl`, random variants. For a pure cache I use `allkeys-lru` (or `allkeys-lfu` for skewed access) with a `maxmemory` limit.
:::

:::q Redis persistence: RDB vs AOF?
RDB takes periodic snapshots (compact, fast restart, may lose the last minutes). AOF logs every write with configurable fsync (more durable, larger files, slower recovery). A pure cache usually needs neither; a Redis used as a primary store needs AOF (often with RDB).
:::

:::q When would you use HybridCache?
On .NET 9+ whenever I would otherwise combine `IMemoryCache` and `IDistributedCache`: it gives an L1 in-memory plus L2 Redis cache, stampede protection, serialization and tag invalidation in one API. I keep L1 TTL short because other nodes' L1 is not invalidated automatically.
:::

:::q What is the difference between response caching and output caching?
Response caching follows HTTP headers and is controlled by clients too; it has no eviction. Output caching (.NET 7+) is server-controlled with policies, tags, programmatic eviction, locking against stampedes and a Redis store, so it is the better server-side choice.
:::

:::q What does `Cache-Control: no-cache` mean?
It does not mean "do not cache". The response may be stored but must be revalidated with the server (ETag/If-None-Match, 304) before reuse. `no-store` is the one that forbids storing.
:::

:::q What is an ETag and how does it help?
A validator representing a version of the resource. The client sends `If-None-Match: "<etag>"`; if unchanged the server returns `304 Not Modified` with no body, saving bandwidth and serialization, while the data is still always fresh.
:::

:::q How do you invalidate the cache across several app instances?
Use a shared cache (Redis) so one delete is seen by all; for local L1 caches publish an invalidation event (Redis pub/sub, Service Bus) that every node handles, or keep L1 TTLs very short. Version keys or tags can invalidate groups at once.
:::

:::q How do you measure cache effectiveness?
Hit ratio (hits/(hits+misses)) per cache and key prefix, evictions, memory use, latency percentiles and the DB load with and without cache. Redis `INFO stats`, Azure Monitor metrics and custom OpenTelemetry counters give these numbers.
:::

:::q What happens to your API if the cache is unavailable?
It must degrade, not fail: cache calls are wrapped so errors count as misses, timeouts are short, a circuit breaker skips the cache while it is down, and the database is protected with rate limiting and single-flight loaders. Redis itself runs with replicas and failover.
:::
