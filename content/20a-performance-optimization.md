## Measure First: Performance Mindset and Tools

**Definition.** Performance optimisation is changing a system so it meets a latency, throughput or cost target. The target comes first; the change comes last.

**Why it matters.** Most "obvious" optimisations do nothing because the bottleneck is elsewhere (usually the database or an external call, rarely a `for` loop). The senior answer to "the API is slow" is never "add caching"; it is "let me measure where the time goes".

**The loop:** define the goal (for example p95 < 300 ms at 200 req/s) -> measure a baseline under realistic load -> find the bottleneck -> change **one** thing -> re-measure -> keep or revert. Use **percentiles (p50/p95/p99)**, not averages, because averages hide the slow tail that users feel.

| Layer | Tool | What it tells you |
|---|---|---|
| Whole system | Application Insights / OpenTelemetry (traces, dependency durations) | Which hop (API, SQL, HTTP, cache) takes the time |
| .NET runtime (live) | `dotnet-counters` | CPU, GC count and pause, allocation rate, thread pool queue length, requests/s |
| .NET CPU hot spots | `dotnet-trace`, Visual Studio Profiler, PerfView, JetBrains dotTrace | Which methods burn CPU (flame graphs) |
| Memory | `dotnet-gcdump`, `dotnet-dump`, VS Memory Usage, dotMemory | What objects are alive, who holds them, LOH growth |
| Micro-benchmark | **BenchmarkDotNet** | Time and allocations of one method, statistically sound |
| Production profiling | Application Insights **Profiler** (sampling traces of slow requests), **Snapshot Debugger** | Hot code path of real slow requests without redeploying |
| Database | Query Store, `SET STATISTICS IO, TIME ON`, actual execution plan, DMVs | Slow queries, scans, missing indexes, waits |
| Load | k6, NBomber, JMeter, Azure Load Testing | Behaviour at 10x traffic; find the knee of the curve |
| Browser | Chrome DevTools, Lighthouse, WebPageTest | LCP/INP/CLS, bundle size, waterfall |

```bash
# Live runtime counters (no restart needed)
dotnet-counters monitor --process-id 1234 System.Runtime Microsoft.AspNetCore.Hosting
# Collect a CPU trace for 30 s, then open in PerfView/VS/speedscope
dotnet-trace collect --process-id 1234 --duration 00:00:30 --profile cpu-sampling
# Heap snapshot for leak hunting
dotnet-gcdump collect --process-id 1234
```

### BenchmarkDotNet example

Never judge a micro-optimisation with `Stopwatch` in a console app (JIT warm-up, tiering, noise). Use BenchmarkDotNet in **Release**, with `[MemoryDiagnoser]` to see allocations.

```csharp
[MemoryDiagnoser]
public class JoinBenchmarks
{
    private readonly string[] _items = Enumerable.Range(0, 1000).Select(i => $"item-{i}").ToArray();

    [Benchmark(Baseline = true)]
    public string Concatenate()
    {
        string s = "";
        foreach (var i in _items) s += i + ",";          // allocates a new string every loop
        return s;
    }

    [Benchmark]
    public string StringBuilderJoin()
    {
        var sb = new StringBuilder(_items.Length * 8);
        foreach (var i in _items) sb.Append(i).Append(',');
        return sb.ToString();
    }

    [Benchmark]
    public string StringJoin() => string.Join(',', _items);
}
// Program.cs:  BenchmarkRunner.Run<JoinBenchmarks>();     dotnet run -c Release
// Illustrative result (your numbers will differ):
// | Method            | Mean      | Ratio | Allocated |
// | Concatenate       | 180 us    | 1.00  | 2,100 KB  |
// | StringBuilderJoin | 9 us      | 0.05  | 28 KB     |
// | StringJoin        | 6 us      | 0.03  | 14 KB     |
```

:::warn Numbers in this section are illustrative
Every timing/impact figure in this section is an *illustrative order of magnitude* to show direction, not a promise. Your hardware, data and load decide the real numbers. In an interview, say "I would expect roughly X, and I would verify with a benchmark/load test".
:::

## C# Layer

### Async/await for I/O and avoiding sync-over-async

**Definition.** `async/await` frees the thread while it waits for I/O (database, HTTP, disk). **Sync-over-async** means blocking on a task (`.Result`, `.Wait()`, `.GetAwaiter().GetResult()`).

**Why it matters.** Under load a blocked request holds a thread pool thread doing nothing. The pool injects new threads slowly (about 1-2 per second beyond the minimum), so requests queue: latency explodes while CPU stays low. This is **thread pool starvation** and it is the #1 self-inflicted ASP.NET Core outage.

```csharp
// BEFORE: blocks a thread per request, sequential calls
[HttpGet("{id}")]
public OrderDetailsDto Get(int id)
{
    var order    = _orders.GetAsync(id).Result;              // blocks
    var customer = _customers.GetAsync(order.CustomerId).Result;
    var shipping = _shipping.GetAsync(id).Result;
    return Map(order, customer, shipping);                   // ~ 100 + 100 + 100 ms
}

// AFTER: async all the way, independent calls run concurrently
[HttpGet("{id}")]
public async Task<ActionResult<OrderDetailsDto>> Get(int id, CancellationToken ct)
{
    var orderTask    = _orders.GetAsync(id, ct);
    var shippingTask = _shipping.GetAsync(id, ct);           // does not depend on customer
    var order = await orderTask;
    var customerTask = _customers.GetAsync(order.CustomerId, ct);
    await Task.WhenAll(customerTask, shippingTask);
    return Map(order, await customerTask, await shippingTask);   // ~ 100 + 100 ms
}
```

*Expected impact (illustrative):* latency drops by the overlapped calls (300 ms to about 200 ms here) and, more importantly, the app sustains many times more concurrent requests with the same threads.

Rules of thumb:
- `async` for I/O; **do not** wrap I/O in `Task.Run` in ASP.NET Core (it just moves work to another pool thread). Use `Task.Run` for CPU-bound work in desktop/UI code, rarely in web code.
- Pass `CancellationToken` (request aborted = stop work).
- ASP.NET Core has no `SynchronizationContext`, so `ConfigureAwait(false)` is unnecessary in app code; still use it in reusable libraries.
- Avoid `async void` (except event handlers) and `lock` around `await` (use `SemaphoreSlim.WaitAsync`).
- Do not use `Task.WhenAll` for hundreds of unbounded calls; bound the parallelism (`Parallel.ForEachAsync` with `MaxDegreeOfParallelism`).

### Reducing allocations: Span, stackalloc, ArrayPool, ObjectPool

**Definition.** Every `new` of a reference type is a heap allocation the GC must later reclaim. In hot paths (per request, per item, per byte) allocation rate drives GC frequency and p99 latency.

```csharp
// BEFORE: Split + Substring allocate an array and several strings per line
static (int Id, string Code) Parse(string line)           // "1042,IN-KA"
{
    var parts = line.Split(',');
    return (int.Parse(parts[0]), parts[1]);
}

// AFTER: slice the original memory, allocate only the final string we keep
static (int Id, string Code) ParseFast(ReadOnlySpan<char> line)
{
    int comma = line.IndexOf(',');
    return (int.Parse(line[..comma]), new string(line[(comma + 1)..]));
}
```

| Tool | Use for | Rule |
|---|---|---|
| `Span<T>` / `ReadOnlySpan<T>` | Slicing arrays/strings/stack memory with no copy | Ref struct: cannot be a field of a class, cannot cross `await` or `yield` |
| `Memory<T>` | Same idea but storable and usable with async | Use for async I/O APIs |
| `stackalloc` | Small temporary buffers (< ~1 KB) | `Span<byte> b = stackalloc byte[256];` never in loops with large sizes (stack overflow) |
| `ArrayPool<T>.Shared` | Temporary large buffers (stream copy, serialization) | `Rent` and always `Return` in `finally`; rented array may be larger than asked; clear if sensitive |
| `ObjectPool<T>` (`Microsoft.Extensions.ObjectPool`) | Reusing expensive objects (`StringBuilder`, parsers) | Reset state before return; not for cheap objects |
| `StringBuilder` | Building strings in loops (> ~4-5 concatenations) | Pre-size capacity; reuse via pool |
| `string.Create` / interpolated string handlers | Building a string once without intermediates | `$"..."` already lowers to `DefaultInterpolatedStringHandler` in modern C# |

```csharp
// ArrayPool: copy a stream without allocating an 80 KB buffer per call
public static async Task CopyAsync(Stream src, Stream dst, CancellationToken ct)
{
    byte[] buffer = ArrayPool<byte>.Shared.Rent(81920);
    try
    {
        int n;
        while ((n = await src.ReadAsync(buffer.AsMemory(), ct)) > 0)
            await dst.WriteAsync(buffer.AsMemory(0, n), ct);
    }
    finally { ArrayPool<byte>.Shared.Return(buffer); }
}

// ObjectPool for StringBuilder
var pool = new DefaultObjectPoolProvider().CreateStringBuilderPool();
var sb = pool.Get();
try { sb.Append("Order ").Append(id); return sb.ToString(); }
finally { pool.Return(sb); }                 // pool clears it
```

:::warn Logging with string interpolation
`_logger.LogInformation($"Order {id} shipped")` builds the string even if Information is disabled, and destroys structured data. Use templates (`"Order {OrderId} shipped", id`) or the `[LoggerMessage]` source generator, which avoids boxing and parsing the template on every call. See the Observability section.
:::

### struct vs class, boxing, LINQ, closures

```csharp
// Boxing: value type -> object allocation
object o = 42;                          // boxed
string s = string.Format("{0}", 42);    // boxes 42 (older overloads); prefer interpolation
ArrayList list = new(); list.Add(1);    // boxes; use List<int>
IEnumerable<int> seq = new List<int>(); // foreach via interface boxes the struct enumerator

// BEFORE: LINQ + closure in a hot path (iterator objects + closure class per call)
decimal TotalFor(IReadOnlyList<Order> orders, OrderStatus status) =>
    orders.Where(o => o.Status == status).Select(o => o.Total).Sum();

// AFTER: plain loop, no allocations
decimal TotalFor2(IReadOnlyList<Order> orders, OrderStatus status)
{
    decimal total = 0;
    for (int i = 0; i < orders.Count; i++)
        if (orders[i].Status == status) total += orders[i].Total;
    return total;
}

// static lambda: compiler error if it captures, so no hidden closure allocation
var names = items.Select(static i => i.Name);
```

- **struct** when small (about <= 16 bytes), immutable, short-lived and numerous (`readonly struct Money`, `record struct`). **class** when large, mutated, shared or polymorphic. Large structs get copied on every pass; use `in`/`ref readonly`.
- LINQ is fine for readability almost everywhere. Replace it only in proven hot paths (profiler says so) or inside tight loops.
- **Closures** that capture locals allocate a display class each call; avoid in hot paths or use `static` lambdas / pass state explicitly.

### ValueTask

`Task<T>` always allocates when it completes asynchronously and when created for a cached result. `ValueTask<T>` avoids the allocation when the result is already available (cache hit, buffered read).

```csharp
public ValueTask<Product?> GetAsync(int id)
{
    if (_cache.TryGetValue(id, out Product? hit))
        return new ValueTask<Product?>(hit);                 // synchronous path: no allocation
    return new ValueTask<Product?>(LoadAndCacheAsync(id));   // async path
}
```

Rules: await a `ValueTask` **once**; never `.Result`/`.GetAwaiter().GetResult()` before it completes; do not await it twice or `WhenAll` it directly (call `.AsTask()` first). Default to `Task`; use `ValueTask` only for hot, frequently-synchronous APIs.

### Collections: choose and pre-size

| Need | Use | Why |
|---|---|---|
| Ordered, index access | `List<T>` | `new List<T>(capacity)` avoids repeated resize/copy |
| Fast membership / lookup by key | `HashSet<T>`, `Dictionary<K,V>` | O(1) vs O(n) `List.Contains` |
| Read-mostly lookup table built once | `FrozenDictionary`/`FrozenSet` (.NET 8) | Faster reads than `Dictionary` after one-time build cost |
| Thread-safe shared | `ConcurrentDictionary`, `Channel<T>` | Avoid your own `lock` bugs |
| Fixed-size small | arrays / `ImmutableArray<T>` | No resizing overhead |
| Queue/FIFO with producers+consumers | `Channel<T>` | Async-friendly back-pressure |

```csharp
// BEFORE: O(n*m)
var active = customers.Where(c => blockedIds.Contains(c.Id));       // blockedIds is a List<int>
// AFTER: O(n + m)
var blocked = blockedIds.ToHashSet();
var active2 = customers.Where(c => blocked.Contains(c.Id));
// Pre-size when you know the size
var result = new List<OrderDto>(orders.Count);
var lookup = new Dictionary<int, Product>(products.Count);
var countries = codes.ToFrozenDictionary(c => c.Iso, c => c);      // using System.Collections.Frozen
```

### GC modes, LOH and disposal

- **Workstation vs Server GC:** Workstation = one heap, lower memory, UI/desktop-friendly. **Server** = a heap and GC thread per core, higher throughput for many parallel requests, higher memory. **Concurrent (background) GC** runs gen2 marking alongside your threads to reduce pauses.
- Configure in the project file or `runtimeconfig`; verify what you actually run with `GCSettings.IsServerGC` instead of assuming.

```xml
<PropertyGroup>
  <ServerGarbageCollector>true</ServerGarbageCollector>
  <ConcurrentGarbageCollection>true</ConcurrentGarbageCollection>
  <TieredPGO>true</TieredPGO>                 <!-- on by default in .NET 8+ -->
</PropertyGroup>
```

- **Containers:** the GC respects cgroup CPU/memory limits; a 1-core container effectively runs Workstation-like behaviour. Set memory limits deliberately; `GCHeapHardLimit`/`GCHeapAffinitizeMask` exist for fine control.
- **Large Object Heap (LOH):** objects >= 85,000 bytes (big arrays, large strings) go to the LOH, which is collected only with gen2 and is not compacted by default. Repeated large allocations cause fragmentation and gen2 storms. Use `ArrayPool`, stream instead of buffering whole files, avoid `ToArray()`/`ToList()` on huge sequences.
- **IDisposable:** dispose anything holding unmanaged resources (`DbConnection`, `Stream`, `HttpResponseMessage`) with `using`/`await using`. Finalizers delay reclamation and add GC work. Do not dispose DI-injected singletons yourself.

### Static caching of Regex and HttpClient

```csharp
// BEFORE: Regex constructed (and parsed) per call; HttpClient per request -> socket exhaustion
public bool IsSku(string s) => new Regex(@"^[A-Z]{3}-\d{4}$").IsMatch(s);
public async Task<string> Get() { using var c = new HttpClient(); return await c.GetStringAsync(url); }

// AFTER: compile at build time with the source generator (.NET 7+); inject typed clients
public static partial class Patterns
{
    [GeneratedRegex(@"^[A-Z]{3}-\d{4}$", RegexOptions.CultureInvariant)]
    public static partial Regex Sku();
}
bool ok = Patterns.Sku().IsMatch(s);

builder.Services.AddHttpClient<IPaymentsClient, PaymentsClient>(c =>
    c.BaseAddress = new Uri("https://psp.example.com"))
    .ConfigurePrimaryHttpMessageHandler(() => new SocketsHttpHandler
    {
        PooledConnectionLifetime = TimeSpan.FromMinutes(5),    // respect DNS changes
        MaxConnectionsPerServer = 100
    });
```

Creating an `HttpClient` per request leaves sockets in `TIME_WAIT` (socket exhaustion); a single static `HttpClient` never sees DNS changes unless `PooledConnectionLifetime` is set. `IHttpClientFactory` solves both. *Expected impact (illustrative):* removes connect/TLS handshake per call and sporadic `SocketException` under load.

:::example Real-world example
A report endpoint allocated about 400 MB per call by loading 500K order rows into a `List<Order>` and then `ToList()`-ing a LINQ chain. Streaming rows with `AsAsyncEnumerable`, summing in a loop and returning a DTO cut the allocation to a few MB, gen2 GCs vanished from `dotnet-counters`, and p99 dropped from 4 s to under 1 s (illustrative).
:::

:::q What is thread pool starvation and how do you fix it?
It happens when pool threads are blocked (`.Result`, `.Wait()`, `Thread.Sleep`, synchronous I/O) so new work queues while CPU stays low; the pool adds threads slowly. Symptoms: latency spikes, low CPU, growing `ThreadPool Queue Length`. Fix by making the code async end to end, removing blocking calls, and using `ThreadPool.SetMinThreads` only as a stop-gap.
:::

:::q Task vs ValueTask - when do you use ValueTask?
Use `ValueTask` for hot APIs that often complete synchronously (cache hits, buffered reads) to avoid allocating a `Task`. The cost is restrictions: await only once, do not block on it, convert with `AsTask()` for `WhenAll`. For everything else stay with `Task`.
:::

## ASP.NET Core Layer

### Response compression, response caching and output caching

- **Compression** shrinks text payloads (JSON, HTML, JS, CSS) 70-90% at some CPU cost. Brotli compresses better, Gzip is more widely supported. In production prefer compressing at the reverse proxy/CDN; in-app compression is fine for simple setups. For HTTPS, enabling compression can expose secrets reflected in responses (BREACH): do not compress responses mixing secrets with attacker-controlled input.
- **Response caching** (`[ResponseCache]`, `UseResponseCaching`) is header-driven (`Cache-Control`) and honours client directives; limited control.
- **Output caching** (`AddOutputCache`, .NET 7+) is *server-side*, policy-driven, supports vary-by-query/header, tags for eviction, and request coalescing (one execution serves concurrent identical requests).

```csharp
builder.Services.AddResponseCompression(o =>
{
    o.EnableForHttps = true;
    o.Providers.Add<BrotliCompressionProvider>();
    o.Providers.Add<GzipCompressionProvider>();
});
builder.Services.Configure<BrotliCompressionProviderOptions>(o => o.Level = CompressionLevel.Fastest);

builder.Services.AddOutputCache(o =>
{
    o.AddPolicy("Products", b => b.Expire(TimeSpan.FromMinutes(5))
        .SetVaryByQuery("category", "page").Tag("products"));
});

app.UseResponseCompression();
app.UseOutputCache();
app.MapGet("/api/products", GetProducts).CacheOutput("Products");
// when a product changes:  await store.EvictByTagAsync("products", ct);   // IOutputCacheStore
```

*Expected impact (illustrative):* a 200 KB JSON list drops to ~25 KB on the wire; a cached catalog endpoint serves from memory in under 2 ms instead of 80 ms plus a DB query. Never output-cache per-user data without varying by user, and keep tenant/user in the cache key.

### Pagination, connection pooling and rate limiting

- **Pagination:** never return unbounded lists; clamp `pageSize` (for example max 100); prefer keyset pagination for deep pages (see EF Core section).
- **SQL connection pooling:** ADO.NET pools by connection string (default `Max Pool Size=100`). Open late, close early (`using`), never hold a connection across slow external calls. Symptom of leaks: `Timeout expired... max pool size was reached`.
- **HttpClient pooling:** via `SocketsHttpHandler` (above). **Redis:** one shared `ConnectionMultiplexer` per process, not per request.
- **Rate limiting** (built in since .NET 7) protects the app from overload and noisy callers.

```csharp
builder.Services.AddRateLimiter(o =>
{
    o.RejectionStatusCode = 429;
    o.AddFixedWindowLimiter("api", opt => { opt.PermitLimit = 100; opt.Window = TimeSpan.FromMinutes(1);
                                            opt.QueueLimit = 0; });
    o.AddConcurrencyLimiter("reports", opt => { opt.PermitLimit = 4; opt.QueueLimit = 10; });
});
app.UseRateLimiter();
app.MapGet("/api/reports/sales", GetSalesReport).RequireRateLimiting("reports");
```

### Middleware ordering

Each request walks the pipeline in order, so put **cheap, short-circuiting** middleware first and expensive middleware later. Order mistakes cause both bugs and wasted work.

```csharp
app.UseExceptionHandler("/error");   // 1 catch everything below
app.UseHsts(); app.UseHttpsRedirection();
app.UseResponseCompression();        // 2 before anything that writes bodies
app.UseStaticFiles();                // 3 short-circuit static files before auth/routing work
app.UseRouting();
app.UseCors();                       // after routing, before auth
app.UseRateLimiter();                // reject abusive traffic early (before expensive auth lookups)
app.UseAuthentication();
app.UseAuthorization();
app.UseOutputCache();                // after auth so cached responses are not served to unauthorised callers
app.MapControllers();
```

Avoid: heavy work in custom middleware that runs for every request (including health probes and static files), reading `Request.Body` into memory for all routes, and logging bodies globally.

### Minimal APIs, Native AOT and JSON source generation

- **Minimal APIs** have lower per-request overhead than MVC controllers (no filter/model-binding machinery you do not use). For most CRUD APIs the difference is small; the biggest wins are I/O, not framework overhead.
- **Native AOT** (`PublishAot`) compiles to a self-contained native binary: very fast startup (tens of ms), lower memory, no JIT. Constraints: no runtime reflection/dynamic code, trimming warnings, limited library support (check each dependency; EF Core's AOT support is limited, so verify current status). Best for serverless/containers with frequent cold starts. Use `WebApplication.CreateSlimBuilder` or `CreateEmptyBuilder`.
- **System.Text.Json source generation** removes reflection at runtime, speeds startup and serialization, and is **required** for AOT.

```csharp
[JsonSerializable(typeof(OrderDto))]
[JsonSerializable(typeof(List<OrderDto>))]
[JsonSourceGenerationOptions(PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase)]
internal partial class AppJsonContext : JsonSerializerContext;

builder.Services.ConfigureHttpJsonOptions(o =>
    o.SerializerOptions.TypeInfoResolverChain.Insert(0, AppJsonContext.Default));
```

### Streaming with IAsyncEnumerable

For large result sets, stream rows to the client as they are read instead of buffering the whole list in memory.

```csharp
// BEFORE: materialise 500K rows (memory spike, time to first byte = total time)
app.MapGet("/orders/export", async (AppDbContext db) =>
    await db.Orders.AsNoTracking().Select(o => new OrderRow(o.Id, o.Total)).ToListAsync());

// AFTER: stream; memory stays flat, first bytes arrive immediately
app.MapGet("/orders/export", (AppDbContext db, CancellationToken ct) =>
    Stream(db, ct));

static async IAsyncEnumerable<OrderRow> Stream(AppDbContext db,
    [EnumeratorCancellation] CancellationToken ct)
{
    await foreach (var row in db.Orders.AsNoTracking()
        .Select(o => new OrderRow(o.Id, o.Total)).AsAsyncEnumerable().WithCancellation(ct))
        yield return row;
}
```

### Kestrel, HTTP/2 and HTTP/3, thread pool health

```csharp
builder.WebHost.ConfigureKestrel(k =>
{
    k.Limits.MaxConcurrentConnections = 10_000;
    k.Limits.MaxRequestBodySize = 10 * 1024 * 1024;          // default is ~30 MB; shrink it
    k.Limits.KeepAliveTimeout = TimeSpan.FromMinutes(2);
    k.Limits.RequestHeadersTimeout = TimeSpan.FromSeconds(15);
    k.ListenAnyIP(443, lo =>
    {
        lo.Protocols = HttpProtocols.Http1AndHttp2AndHttp3;   // HTTP/3 needs QUIC (msquic) + TLS
        lo.UseHttps();
    });
});
```

| Protocol | Benefit | Caveat |
|---|---|---|
| HTTP/1.1 | Universal | One request per connection at a time; head-of-line blocking; many connections |
| HTTP/2 | Multiplexed streams on one connection, header compression (HPACK) | TCP head-of-line blocking on packet loss |
| HTTP/3 | QUIC over UDP, no TCP HOL blocking, faster reconnect on mobile networks | Needs UDP open, QUIC library on the host, still maturing in some proxies |

**Thread pool health.** Watch `ThreadPool Queue Length`, `ThreadPool Thread Count` and `Monitor Lock Contention Count` in `dotnet-counters`. You can also log them:

```csharp
// Diagnostic snippet: log every 10 s
_logger.LogInformation("ThreadPool threads={Threads} pending={Pending} completed={Done}",
    ThreadPool.ThreadCount, ThreadPool.PendingWorkItemCount, ThreadPool.CompletedWorkItemCount);
```

Starvation signature: queue length grows, thread count climbs slowly, CPU stays low, latency rises for *all* endpoints. Find blockers with `dotnet-stack`/dump analysis or by searching for `.Result`, `.Wait()`, `GetAwaiter().GetResult()`, and sync-over-async inside constructors, `lock`s and static initialisers.

:::q Output caching vs response caching vs distributed caching?
Response caching follows HTTP cache headers and is mostly about clients/proxies. Output caching stores whole responses on the server with policies, tags and coalescing. Distributed caching (Redis) stores *data* objects shared by many instances. They stack: CDN, output cache, then Redis, then the database.
:::

:::q Why is Native AOT not simply "always on"?
AOT removes the JIT and reflection, so startup and memory improve, but dynamic features break: reflection-based serializers, some DI/ORM libraries, plugins. You must use source generators (JSON, regex, logging), check trimming warnings, and accept slightly lower peak throughput in some workloads because there is no tiered JIT/PGO. Great for serverless; not a free upgrade for a large monolith.
:::
