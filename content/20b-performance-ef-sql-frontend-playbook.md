## EF Core Layer

**Definition.** EF Core translates LINQ into SQL and materialises results into tracked objects. Most "slow EF" problems are really *slow SQL*, *too many queries*, or *loading more than needed*.

**First step always:** see the SQL. Use `query.ToQueryString()`, `optionsBuilder.LogTo(Console.WriteLine, LogLevel.Information)` in development, or App Insights/Query Store in production.

### AsNoTracking and projection

Tracking creates snapshot copies and identity maps so `SaveChanges` can detect changes. For read-only endpoints that is wasted memory and CPU. Projection (`Select` into a DTO) also reduces the columns fetched and avoids loading whole graphs.

```csharp
// BEFORE: tracked entities, all columns, whole graph
var orders = await db.Orders
    .Include(o => o.Customer).Include(o => o.Items)
    .Where(o => o.CustomerId == id)
    .ToListAsync(ct);
return orders.Select(o => new OrderSummaryDto(o.Id, o.Customer.Name, o.Items.Count, o.Total));

// AFTER: no tracking, only the needed columns, computed in SQL
var summaries = await db.Orders
    .AsNoTracking()
    .Where(o => o.CustomerId == id)
    .OrderByDescending(o => o.CreatedAtUtc)
    .Select(o => new OrderSummaryDto(o.Id, o.Customer.Name, o.Items.Count, o.Total))
    .Take(50)
    .ToListAsync(ct);
```

*Expected impact (illustrative):* 3-10x less memory and noticeably lower latency on list endpoints, since SQL returns 4 columns instead of dozens plus child rows. Set `UseQueryTrackingBehavior(QueryTrackingBehavior.NoTracking)` as the default for read-heavy services and opt in with `.AsTracking()` where you update.

### N+1 queries, Include and split queries

**N+1:** one query for the list, then one query per row for related data. Looks fine with 10 rows in dev, kills you with 1,000 in production.

```csharp
// BEFORE: N+1 (1 query for orders + N queries for customers via lazy loading or a loop)
var orders = await db.Orders.Where(o => o.Status == OrderStatus.Open).ToListAsync();
foreach (var o in orders)
{
    var customer = await db.Customers.FindAsync(o.CustomerId);   // a query per order
    Console.WriteLine($"{o.Id} {customer!.Name}");
}

// AFTER (a): join in one query via projection
var rows = await db.Orders.AsNoTracking()
    .Where(o => o.Status == OrderStatus.Open)
    .Select(o => new { o.Id, CustomerName = o.Customer.Name })
    .ToListAsync();

// AFTER (b): batch the lookup when you must load entities
var ids = orders.Select(o => o.CustomerId).Distinct().ToList();
var customers = await db.Customers.Where(c => ids.Contains(c.Id))
                                  .ToDictionaryAsync(c => c.Id);   // 1 extra query, not N
```

**Cartesian explosion:** `Include` of two collections in one query joins them and multiplies rows (orders x items x payments). Fix with `AsSplitQuery()` (one query per collection) or by projecting only what you need.

```csharp
var order = await db.Orders
    .Include(o => o.Items)
    .Include(o => o.Payments)
    .AsSplitQuery()                         // or UseQuerySplittingBehavior globally
    .SingleAsync(o => o.Id == id, ct);
```

Split queries cost extra round trips and are not atomic without a transaction; use them when row multiplication is the problem. Avoid lazy-loading proxies in web APIs: they hide N+1 in innocent-looking property access.

### Indexes, compiled queries, set-based updates, batching

```csharp
// Indexes: declare them, then confirm in the execution plan that they are used
modelBuilder.Entity<Order>()
    .HasIndex(o => new { o.CustomerId, o.CreatedAtUtc })
    .IsDescending(false, true)
    .IncludeProperties(o => new { o.Status, o.Total });          // covering index (SQL Server)

// Compiled query: skip the expression-tree translation on a very hot query
private static readonly Func<AppDbContext, int, CancellationToken, Task<Product?>> ById =
    EF.CompileAsyncQuery((AppDbContext db, int id, CancellationToken _) =>
        db.Products.AsNoTracking().FirstOrDefault(p => p.Id == id));
var p = await ById(db, 42, ct);

// BEFORE: load 5,000 rows only to change one column, then SaveChanges
var stale = await db.Carts.Where(c => c.UpdatedAtUtc < cutoff).ToListAsync();
foreach (var c in stale) c.Status = CartStatus.Expired;
await db.SaveChangesAsync();

// AFTER: one UPDATE statement, nothing loaded (EF Core 7+)
await db.Carts.Where(c => c.UpdatedAtUtc < cutoff)
    .ExecuteUpdateAsync(s => s.SetProperty(c => c.Status, CartStatus.Expired), ct);
await db.Carts.Where(c => c.Status == CartStatus.Expired && c.UpdatedAtUtc < purge)
    .ExecuteDeleteAsync(ct);
```

- **Batching:** `SaveChanges` already groups inserts/updates into few round trips; add with `AddRange`, save once at the end (not per item). For 100K+ rows use `SqlBulkCopy` or a bulk library (EFCore.BulkExtensions); EF is not a bulk loader.
- **DbContext pooling:** `AddDbContextPool<AppDbContext>(...)` reuses context instances to cut allocation/setup per request (small win, real at high QPS). Do not keep per-request state in a pooled context's fields; use scoped services carefully (see the multi-tenant design).
- **Do not** put `ToList()` before `Where`, do not call `Count() > 0` instead of `Any()`, and avoid `Contains` with thousands of ids (big `IN` lists); use a temp table/TVP or join.

### Keyset pagination and avoiding blobs

```csharp
// BEFORE: OFFSET pagination: page 5,000 reads and discards 100,000 rows
var page = await db.Orders.OrderBy(o => o.Id).Skip(100_000).Take(20).ToListAsync();

// AFTER: keyset ("seek") pagination: uses the index to jump to the position
var next = await db.Orders.AsNoTracking()
    .Where(o => o.Id > lastSeenId)
    .OrderBy(o => o.Id)
    .Take(20)
    .ToListAsync();
// API returns "nextCursor": lastId. With composite sort: WHERE (CreatedAt, Id) < (@t, @id)
```

| | Offset (`Skip/Take`) | Keyset |
|---|---|---|
| Cost at deep pages | Grows linearly | Constant (index seek) |
| Jump to page N | Yes | No (next/previous only) |
| Stable under inserts | No (rows shift) | Yes |
| Needs unique, indexed sort key | No | Yes |

**Avoid loading blobs:** a `VARBINARY(MAX)` photo/PDF column read on every `Select *` dominates I/O. Project it away, move it to a separate table (table splitting/one-to-one) or, better, store files in Blob Storage and keep the URL in SQL. When you must read large values, stream them (`reader.GetStream`) instead of materialising byte arrays.

:::example Real-world example
`GET /orders` took 2.8 s with 40 SQL calls per request. Trace in Application Insights showed the same `SELECT ... FROM Customers WHERE Id = @p0` repeated 38 times. Replacing lazy loading with a projected `Select` collapsed it to 2 queries and 180 ms (illustrative numbers). The fix was found in the trace, not by guessing.
:::

## SQL Layer

### Execution plans and indexing

**Definition.** The optimizer picks a plan (how to read tables, join, sort). The **actual execution plan** shows what really happened: rows per operator, time, warnings.

Read plans like this:
1. Look for the thickest arrows and the most expensive operators (percent of cost is an estimate; check actual rows and time).
2. **Index Seek** (jumps to rows) is good; **Index/Table Scan** reads everything: fine for tiny tables, a red flag for big ones.
3. **Key Lookup** per row after a seek = the index does not cover the query. Add `INCLUDE` columns or narrow the select list.
4. Compare **estimated vs actual rows**: a large mismatch means stale statistics or parameter sniffing.
5. Warnings: missing index hint, implicit conversion, sort/hash **spill to tempdb**, no join predicate.

```sql
SET STATISTICS IO, TIME ON;                 -- logical reads and CPU per query

-- Covering index for: WHERE CustomerId = @id AND Status = 1 ORDER BY CreatedAtUtc DESC
CREATE NONCLUSTERED INDEX IX_Orders_Customer_Status_Date
  ON dbo.Orders (CustomerId, Status, CreatedAtUtc DESC)   -- equality columns first, then sort/range
  INCLUDE (Total);                                         -- avoids key lookups

-- Find the most expensive queries (current instance; Query Store gives history)
SELECT TOP 10 qs.total_worker_time / qs.execution_count AS avg_cpu_us,
       qs.execution_count, SUBSTRING(st.text, 1, 200) AS sql_text
FROM sys.dm_exec_query_stats qs CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) st
ORDER BY avg_cpu_us DESC;
```

Index rules: clustered index = the table's physical order (usually the PK or a narrow, ever-increasing key); non-clustered indexes are separate B-trees with pointers. Column order matters (leftmost prefix). Every extra index slows `INSERT/UPDATE/DELETE` and uses space, so index for real queries, drop unused ones (`sys.dm_db_index_usage_stats`). Filtered indexes help for hot subsets (`WHERE IsActive = 1`).

### SARGability: let the index be used

A predicate is **SARGable** (Search ARGument able) when the engine can seek the index. Wrapping the *column* in a function or mismatching types forces a scan.

| Non-SARGable (scan) | SARGable (seek) |
|---|---|
| `WHERE YEAR(CreatedAt) = 2026` | `WHERE CreatedAt >= '2026-01-01' AND CreatedAt < '2027-01-01'` |
| `WHERE LEFT(Name, 3) = 'Joh'` | `WHERE Name LIKE 'Joh%'` |
| `WHERE Name LIKE '%son'` | full-text search or a reversed/computed indexed column |
| `WHERE ISNULL(Discount,0) = 0` | `WHERE Discount = 0 OR Discount IS NULL` |
| `WHERE CAST(Id AS VARCHAR) = '42'` | `WHERE Id = 42` |
| `NVARCHAR` column compared to `VARCHAR` param (implicit conversion) | match the parameter type exactly (also a classic EF/Dapper gotcha with `AnsiString`) |

```sql
-- BEFORE: scan 40M rows
SELECT COUNT(*) FROM Orders WHERE DATEDIFF(day, CreatedAtUtc, GETUTCDATE()) < 7;
-- AFTER: seek on IX(CreatedAtUtc)
SELECT COUNT(*) FROM Orders WHERE CreatedAtUtc >= DATEADD(day, -7, GETUTCDATE());
```

### Statistics, parameter sniffing, scans and stored procedures

- **Statistics** describe value distribution; the optimizer uses them to estimate rows and pick plans. Stale statistics produce bad plans. Auto-update is on by default but large tables may need `UPDATE STATISTICS ... WITH FULLSCAN` or scheduled maintenance.
- **Parameter sniffing:** the first execution compiles a plan using that call's parameter values; the plan is cached and reused. If the next call has very different selectivity (`@CustomerId` with 5 rows vs 5 million rows) the plan is terrible for it. *Symptom:* "fast in SSMS, slow from the app" or "slow sometimes".

```sql
-- Fix options, from least to most invasive
OPTION (RECOMPILE)                         -- compile per execution (CPU cost, fine for reports)
OPTION (OPTIMIZE FOR UNKNOWN)              -- use average density statistics
-- split a proc into "small customer" and "huge customer" paths
-- Query Store: force the known-good plan; SQL Server 2022 Parameter Sensitive Plan optimization
-- helps automatically at compat level 160.
```

- **Avoid scans:** select only needed columns; `EXISTS` instead of `COUNT(*) > 0`; avoid `SELECT *`; avoid scalar UDFs and functions on columns in `WHERE`; replace cursors/loops with set-based statements; keep transactions short.
- **Stored procedures:** not faster by magic. Parameterised ad-hoc queries (EF, Dapper) also get plan caching. Procs help with centralised tuning, fewer round trips for multi-statement work, and permissions. Use `SET NOCOUNT ON`, schema-qualified names, `sp_executesql` for dynamic SQL, avoid parameter-sniffing-prone branching in one proc.
- **Temp tables vs table variables:** temp tables (`#t`) have statistics and can be indexed: use them for larger intermediate sets (thousands+ rows). Table variables (`@t`) have limited statistics (SQL Server 2019+ improves with deferred compilation), no per-statement recompile: fine for small sets. For passing sets from .NET use a **table-valued parameter**.
- **Blocking and locks:** enable `READ_COMMITTED_SNAPSHOT` (readers do not block writers), keep transactions short, access tables in a consistent order to avoid deadlocks.

### Partitioning and archiving

Keep hot data small. Partition big, time-based tables (orders, logs, events) by date so queries prune partitions and old data can be switched out in milliseconds (`ALTER TABLE ... SWITCH PARTITION`). Archive rows older than the business needs into cheaper storage or an archive table; delete in batches to avoid log growth and long locks.

```sql
-- Batched purge: small transactions, no lock escalation
WHILE 1 = 1
BEGIN
  DELETE TOP (5000) FROM dbo.AuditLog WHERE CreatedAtUtc < DATEADD(month, -12, SYSUTCDATETIME());
  IF @@ROWCOUNT = 0 BREAK;
  WAITFOR DELAY '00:00:01';
END
```

For analytics-style scans, a **columnstore** index compresses and speeds aggregations on large tables.

## Frontend Layer

### Core Web Vitals

| Metric | Measures | Good | Typical fixes |
|---|---|---|---|
| **LCP** (Largest Contentful Paint) | When the main content appears | <= 2.5 s | Optimise hero image, preload it, fast server response, CDN, less render-blocking JS/CSS |
| **INP** (Interaction to Next Paint) | Responsiveness to taps/clicks (replaced FID in 2024) | <= 200 ms | Break up long JS tasks, debounce, memoise, avoid heavy re-renders, web workers |
| **CLS** (Cumulative Layout Shift) | Visual stability | <= 0.1 | Set image/video width and height, reserve space for ads/banners, avoid inserting content above existing content |

Measure with Lighthouse (lab) and real-user monitoring (field data, `web-vitals` library, App Insights browser SDK).

### Lazy loading and code splitting, bundle size

```javascript
// BEFORE: everything in one bundle (2.4 MB), including admin charts nobody on this page needs
import ReportsPage from './pages/ReportsPage';

// AFTER: route-level code splitting; downloaded only when the route is visited
const ReportsPage = React.lazy(() => import('./pages/ReportsPage'));
<Suspense fallback={<Spinner />}>
  <Routes><Route path="/reports" element={<ReportsPage />} /></Routes>
</Suspense>
// Angular equivalent: { path: 'reports', loadComponent: () => import('./reports.component') }
```

*Expected impact (illustrative):* initial JS from 2.4 MB to ~600 KB, LCP and time-to-interactive improve proportionally on slow mobile networks.

Bundle size checklist: analyse with `source-map-explorer`/`webpack-bundle-analyzer`/`rollup-plugin-visualizer`; enable tree shaking (ES modules, `sideEffects: false`); replace heavy libraries (`moment` to `date-fns`/`dayjs`, import lodash per function); remove unused dependencies; compress with Brotli; load third-party scripts `async/defer`.

### Images, caching, service workers and CDN

```html
<!-- BEFORE: 3 MB JPEG, no dimensions: slow LCP and layout shift -->
<img src="/img/hero.jpg">

<!-- AFTER: modern format, responsive sizes, dimensions reserved, hero prioritised -->
<img src="/img/hero-800.avif" width="800" height="450"
     srcset="/img/hero-400.avif 400w, /img/hero-800.avif 800w, /img/hero-1600.avif 1600w"
     sizes="(max-width: 600px) 100vw, 800px" fetchpriority="high" alt="Summer sale">
<img src="/img/product.webp" width="300" height="300" loading="lazy" alt="Phone">  <!-- below the fold -->
```

- **HTTP caching:** fingerprinted assets (`app.4f9c2b.js`) get `Cache-Control: public, max-age=31536000, immutable`; `index.html` gets `no-cache` (revalidate) so new deploys are seen. APIs can use `ETag`/`304 Not Modified`.
- **CDN:** serve static assets and images from edge locations (Azure Front Door/CDN, Cloudflare); lower latency and offloads the origin.
- **Service worker (Workbox):** cache app shell and assets for instant repeat loads and offline; use stale-while-revalidate for API GETs that tolerate staleness. Version carefully, a bad service worker can serve stale code forever.

### API optimisation from the client

```javascript
// BEFORE: waterfall of dependent awaits and a request per keystroke
const user = await getUser(id);
const orders = await getOrders(id);
const recs = await getRecommendations(id);        // 3 sequential round trips

// AFTER: independent calls in parallel
const [user2, orders2, recs2] = await Promise.all([
  getUser(id), getOrders(id), getRecommendations(id)]);
```

- Add a **BFF/aggregation endpoint** (`GET /api/dashboard`) when a screen always needs the same 4 calls; or batch with GraphQL/OData `$expand`.
- Cache and de-duplicate requests client-side with TanStack Query/RTK Query/Angular `HttpClient` interceptors (`staleTime`, background refetch).
- Return only needed fields; paginate; compress; use `AbortController` to cancel obsolete requests.

### Pagination, infinite scroll, virtualisation, debounce and throttle

Render only what is visible: a list of 10,000 rows in the DOM freezes the page. Use pagination, infinite scroll with cursor APIs, and **virtualisation** (`@tanstack/react-virtual`, `react-window`, Angular CDK `cdk-virtual-scroll-viewport`) so only ~20 rows exist in the DOM at a time.

**Debounce** waits until the user stops (search box); **throttle** limits to once per interval (scroll/resize handlers).

```javascript
// BEFORE: API call on every keystroke, out-of-order responses overwrite newer ones
input.addEventListener('input', e => search(e.target.value));

// AFTER: debounce + cancel the previous request
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

let controller;
const search = debounce(async (q) => {
  controller?.abort();                                  // cancel the stale request
  controller = new AbortController();
  const res = await fetch(`/api/products?q=${encodeURIComponent(q)}`, { signal: controller.signal });
  render(await res.json());
}, 300);
input.addEventListener('input', e => search(e.target.value));
```

React rendering: memoise expensive derived data (`useMemo`), stable callbacks for memoised children (`useCallback` + `React.memo`), stable `key`s, lift state down not up, and profile with React DevTools Profiler before adding memoisation everywhere (it has its own cost).

## Performance Troubleshooting Playbook

### "The API is slow in production": step by step

**Rule:** mitigate first if users are hurt (rollback, scale out, disable a feature flag), then investigate, then prevent.

1. **Scope the problem.** Which endpoint(s)? All users or some (tenant, region, data size)? p50 or only p99? Since when? What changed (deployment, config, feature flag, data growth, traffic spike, dependency)? A graph with a sharp step at a deploy time points to a regression; a slow ramp points to data growth or a leak.
2. **Isolate the layer with APM.** In Application Insights open *Performance* for the operation, then a slow *end-to-end transaction*. The waterfall shows time in the API itself vs SQL vs HTTP dependencies vs cache. If time is *outside* the app (gateway, DNS, TLS, network) check Front Door/APIM/Load balancer metrics. If the app looks fast but users see slowness, it is the frontend or network.
3. **Database / slow query.** Dependency duration dominated by SQL? Open Query Store/`sys.dm_exec_query_stats` for the top queries by duration, CPU, reads. Get the actual plan: scan instead of seek, key lookups, spills, estimated vs actual mismatch. Check **blocking** (`sys.dm_os_waiting_tasks`, `sp_whoisactive`), deadlocks, and DB resource limits (DTU/vCore/IO at 100%).
4. **N+1 and chatty access.** Many identical small SQL/HTTP calls in one trace = N+1. Fix with projection/Include/batching/caching.
5. **Thread pool starvation.** Latency up on *every* endpoint, CPU low, requests queueing. `dotnet-counters`: `ThreadPool Queue Length` rising, thread count creeping. Find sync-over-async/blocking calls; fix; as a stop-gap raise min threads.
6. **GC and memory.** High `% Time in GC`, frequent gen2, LOH growth, memory climbing then restart (OOM kill in containers). Take `dotnet-gcdump`, compare snapshots, look for static caches, event handlers, large buffers. Reduce allocation rate (pooling, streaming); consider Server GC and container limits.
7. **External calls.** Dependency calls slow or timing out? Missing timeouts/circuit breakers, retry storms multiplying load, connection pool exhaustion (`HttpClient`, SQL pool), DNS or SNAT port exhaustion on App Service. Add timeouts, bulkheads, backoff.
8. **Cache.** Hit ratio dropped (key change, eviction, TTL too short)? Stampede after expiry? Redis latency or big keys? Serialization cost? Add single-flight, jittered TTLs, warm up.
9. **Infrastructure.** CPU throttling from container limits, autoscale lag, cold starts, noisy neighbour, undersized plan, single instance. Scale up/out, fix probes and limits.
10. **Fix, verify, prevent.** Reproduce with a load test, apply one change, re-measure p95/p99, add an alert on the symptom (p95 latency, queue length, DB DTU), add a regression load test or query-count assertion in CI, write the post-incident note.

| Symptom | Likely cause | Confirm with | Typical fix |
|---|---|---|---|
| High latency, low CPU, all endpoints | Thread pool starvation | `dotnet-counters` queue length | Async end to end |
| One endpoint slow, many tiny SQL calls | N+1 | Trace waterfall, EF log | Projection/Include/batch |
| Query fast on small data, slow in prod | Missing/unused index, non-SARGable predicate | Actual plan, STATISTICS IO | Index, rewrite predicate |
| Same query sometimes slow | Parameter sniffing / plan regression | Query Store plan history | Recompile hint, plan forcing |
| Memory climbs, restarts | Leak or LOH fragmentation | `dotnet-gcdump` diff | Fix retention, pool buffers |
| Spikes at deploy/restart | Cold start/JIT, cache empty | Timing vs deploy | Warm-up, ReadyToRun/AOT, pre-populate cache |
| Timeouts to a partner API | No timeout/retry limits, saturated pool | Dependency telemetry | Timeouts, circuit breaker, queue |
| Fast API, slow page | Large bundle, waterfall, images | Lighthouse, DevTools | Split code, parallelise, optimise images |

:::scenario Order list takes 3 seconds and gets worse with more orders
Application Insights shows one request with 41 SQL dependency calls, all `SELECT ... FROM Customers WHERE Id=@p0`. That is N+1 caused by a loop (or lazy loading) loading the customer per order. Fix: one query with `Select` projection (`o.Customer.Name`) or `Include`, plus `AsNoTracking` and paging. Add an integration test that asserts a maximum query count for the endpoint so it cannot regress.
:::

:::scenario API latency spikes every afternoon but CPU is only 15%
Low CPU with high latency suggests blocking, not computation. `dotnet-counters` shows `ThreadPool Queue Length` climbing during peaks. A dump or code search finds `.Result` on an HTTP call inside a hot controller. Convert it to `await`, add `CancellationToken`, and pass timeouts to `HttpClient`. Verify the queue length stays near zero under a load test. Raising `SetMinThreads` is only a temporary patch.
:::

:::scenario A report query was fine last year, now it times out
The query uses `WHERE YEAR(CreatedAtUtc) = @year`, which is non-SARGable, so the engine scans every row; data growth turned a tolerable scan into a timeout. Rewrite as a half-open date range and make sure an index leads with `CreatedAtUtc`. Check the actual plan for a seek, update statistics, and consider partitioning and archiving older data.
:::

:::scenario The stored procedure takes 50 ms in SSMS but 12 s from the application
Classic parameter sniffing combined with different `SET` options (for example `ARITHABORT`) giving the app its own cached plan, compiled for an unrepresentative parameter. Compare the cached plans in Query Store, then use `OPTION (RECOMPILE)` or `OPTIMIZE FOR UNKNOWN` for that statement, or split the procedure by data volume. On SQL Server 2022 test Parameter Sensitive Plan optimization.
:::

:::scenario Container restarts every few hours with OOMKilled
Memory growth with a restart pattern means a leak or runaway allocation. Collect `dotnet-gcdump` at two times and diff: a static `Dictionary` used as an unbounded cache, event handlers never unsubscribed, or LOH arrays from buffering uploads. Replace the dictionary with `MemoryCache` with size limits and expiry, stream uploads, use `ArrayPool`, and set a sensible memory limit with alerting before the OOM.
:::

:::scenario The dashboard page takes 8 seconds on mobile
Lighthouse shows a 3 MB JS bundle, 12 sequential API calls and an unoptimised hero image (LCP 7 s). Split code per route, preload the hero as AVIF with dimensions, run the independent API calls with `Promise.all` or add a BFF `/dashboard` endpoint, add HTTP caching and a CDN, and virtualise the long table. Re-measure LCP/INP with real-user monitoring.
:::

:::scenario A CSV export of 1M rows times out and takes the API down
The handler loads every row into a `List`, builds one giant string and returns it, spiking memory and holding a request thread. Make it a background job: enqueue, stream rows with `AsAsyncEnumerable` into a blob using a buffered writer, then notify the user with a download link. Rate limit export endpoints with a concurrency limiter so one tenant cannot starve the rest.
:::

:::scenario Database CPU hits 100% during a flash sale
Profile top queries first: probably hot product reads and inventory checks. Serve the catalog from CDN/output cache/Redis, route reads to a read replica, put inventory checks on an atomic conditional update (not read-then-write), move non-critical work (emails, analytics) to queues, and add rate limiting/admission control at the gateway. Scale the database tier as a stop-gap while tuning.
:::

## Quick-fire Q&A

:::q Where do you start when someone says "the app is slow"?
Measure, do not guess. Define the symptom (which endpoint, p95 or p99, since when), then use APM traces to find which layer owns the time: app, database, external call, cache, or network. Only then optimise, one change at a time, and re-measure.
:::

:::q What is the N+1 problem and how do you fix it in EF Core?
One query loads a list, then one extra query per item loads related data. Fix with a projected `Select`, `Include`/`AsSplitQuery`, or batching ids into one `Where(ids.Contains)`. Detect it by counting queries per request in logs or traces.
:::

:::q When do you use AsNoTracking?
For any read-only query. Tracking costs memory and CPU for change detection you will not use. It is often safe to make no-tracking the default and opt in for updates.
:::

:::q Offset vs keyset pagination?
Offset (`Skip/Take`) reads and discards earlier rows, so deep pages get slower and results shift during inserts. Keyset filters from the last seen key using an index, giving constant cost and stable pages, but only next/previous navigation.
:::

:::q What makes a SQL predicate SARGable?
The indexed column appears bare on one side of the comparison with a matching type. Functions on the column (`YEAR(col)`, `LEFT`, `CAST`), leading wildcards and implicit conversions stop index seeks and cause scans.
:::

:::q What is parameter sniffing?
SQL Server compiles and caches a plan using the first parameter values, then reuses it. If later values have very different row counts, that plan is bad. Mitigate with `OPTION (RECOMPILE)`, `OPTIMIZE FOR UNKNOWN`, splitting logic, or Query Store plan forcing.
:::

:::q Why is `.Result` dangerous in ASP.NET Core?
It blocks a thread-pool thread until the task finishes. Under load the pool runs out of threads, requests queue and latency explodes while CPU stays low (thread pool starvation). Use `await` all the way up.
:::

:::q Temp table or table variable?
Temp tables have statistics and indexes, so they suit larger sets and complex joins. Table variables suit very small sets; older versions assume one row, which can produce poor plans on larger data.
:::

:::q How do you reduce allocations in a hot path?
Profile first, then use `Span<T>`, `ArrayPool`, `ObjectPool`, `StringBuilder`, `stackalloc` for small buffers, avoid boxing, closures and LINQ in tight loops, pre-size collections, and consider `ValueTask` for frequently synchronous async methods.
:::

:::q Server GC or Workstation GC?
Server GC uses a heap and thread per core and favours throughput for multi-core web servers, at the cost of memory. Workstation favours low memory and responsiveness (desktop apps, small containers). Check `GCSettings.IsServerGC` and test with your workload.
:::

:::q What are the three Core Web Vitals?
LCP (loading, aim <= 2.5 s), INP (interactivity, <= 200 ms, replaced FID) and CLS (visual stability, <= 0.1).
:::

:::q Output caching vs response compression - which helps what?
Compression reduces bytes on the wire (network time, bandwidth) at some CPU cost. Output caching removes the work of producing the response at all (CPU, DB). They are complementary.
:::

:::q How do you prove your optimisation worked?
Before/after measurement under the same load: p50/p95/p99 latency, throughput, error rate, CPU, allocations, DB reads. A BenchmarkDotNet run for micro changes, a load test for system changes, and production telemetry after release.
:::
