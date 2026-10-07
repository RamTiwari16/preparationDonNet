### BenchmarkDotNet example

**In simple words:** BenchmarkDotNet is a library that measures how fast one method is and how much memory it uses. It runs the code many times, warms it up first and does the statistics for you. A simple `Stopwatch` test is not reliable, because the first runs are slower and the machine adds noise. Always run benchmarks in Release mode, and add `[MemoryDiagnoser]` to see allocations.

**Real-life example:** To know your real running speed, you do not time one run on a cold morning. You warm up, run ten times and take a fair average.

**Interview question:** How do you compare the speed of two ways to write the same method?

**Simple answer:** I use BenchmarkDotNet in Release mode, not a Stopwatch. It handles warm-up and repeats the runs, so the result is statistically fair. With `[MemoryDiagnoser]` I also see how many bytes each version allocates.

```csharp
[MemoryDiagnoser]
public class JoinBench
{
    [Benchmark] public string Join() => string.Join(',', _items);
}
// BenchmarkRunner.Run<JoinBench>();  dotnet run -c Release
```

### Async/await for I/O and avoiding sync-over-async

**In simple words:** I/O means waiting for something outside your code, like a database, an HTTP call or a disk. With `async/await`, the thread goes back to the pool while it waits, so it can serve other requests. *Sync-over-async* means blocking on a task with `.Result` or `.Wait()`. Under load this holds threads that do nothing, requests queue up, and the app becomes slow while CPU stays low. This is called *thread pool starvation*.

**Real-life example:** A waiter takes your order, gives it to the kitchen, and serves other tables while the food cooks. A blocking waiter stands at the kitchen door doing nothing until your dish is ready.

**Interview question:** Why is calling `.Result` on a task dangerous in ASP.NET Core?

**Simple answer:** `.Result` blocks a thread pool thread until the task finishes. Under load all threads get blocked, the pool adds new threads slowly, and requests wait in a queue. I use `await` all the way, pass a `CancellationToken`, and run independent calls together with `Task.WhenAll`.

### Reducing allocations: Span, stackalloc, ArrayPool, ObjectPool

**In simple words:** Every time you create an object with `new`, it uses heap memory that the garbage collector (GC) must clean later. In code that runs very often, many allocations mean many GC runs and slower responses. `Span<T>` lets you work on a part of a string or array without copying it. `stackalloc` gives a small temporary buffer on the stack. `ArrayPool` and `ObjectPool` let you borrow and return objects instead of creating new ones each time.

**Real-life example:** A library lends books. You borrow a book, read it and return it, so the library does not print a new copy for every reader.

**Interview question:** How do you reduce allocations in a hot path?

**Simple answer:** First I profile to prove it is a hot path (code that runs very often). Then I use `Span<T>` to slice data without copying and `ArrayPool` to rent big buffers, always returning them in `finally`. I also use `ObjectPool` for expensive objects like `StringBuilder`, and `stackalloc` only for small buffers.

```csharp
byte[] buf = ArrayPool<byte>.Shared.Rent(81920);
try { /* use buf */ }
finally { ArrayPool<byte>.Shared.Return(buf); }
```

### struct vs class, boxing, LINQ, closures

**In simple words:** A struct is a value type that is copied when you pass it. Use it for small, immutable data, like a `Money` value. Use a class for large, changing or shared objects. *Boxing* happens when a value type is stored as `object`, which creates a hidden heap object. LINQ and *closures* (lambdas that capture local variables) also create small objects on each call. This is fine in normal code, but it matters in very hot loops.

**Real-life example:** Writing a short phone number on a sticky note to give a friend is cheap. Copying a whole thick folder every time you hand it over is expensive. Small data copies well; big data should be shared.

**Interview question:** When would you choose a struct over a class, and when should you avoid LINQ?

**Simple answer:** I use a struct for small (around 16 bytes or less), immutable, short-lived values, and a class for everything else. LINQ is fine for readable code almost everywhere. I replace it with a plain loop only when the profiler shows a hot path, and I use `static` lambdas to avoid hidden closure allocations.

### ValueTask

**In simple words:** `ValueTask<T>` is like `Task<T>`, but it can avoid creating an object when the result is already ready. This helps methods that often return at once, for example on a cache hit. It has rules: await it only once, and never call `.Result` on it before it finishes. If you need `Task.WhenAll`, convert it with `.AsTask()` first.

**Real-life example:** At a shop, if the item is on the shelf, you get it at once with no paperwork. Only if it is out of stock does the shop create an order form for you.

**Interview question:** Task vs ValueTask — when do you use ValueTask?

**Simple answer:** I use `ValueTask` for hot methods that usually complete synchronously, like cache lookups, so no `Task` object is allocated. It has limits: await it once, do not block on it, and use `AsTask()` for `WhenAll`. For all other cases I stay with `Task`, because it is simpler and safer.

```csharp
public ValueTask<Product?> GetAsync(int id) =>
    _cache.TryGetValue(id, out Product? p)
        ? new ValueTask<Product?>(p)          // no allocation
        : new ValueTask<Product?>(LoadAsync(id));
```

### Collections: choose and pre-size

**In simple words:** Picking the right collection can turn slow code into fast code. `List.Contains` checks items one by one, while `HashSet` and `Dictionary` find a key almost instantly. If you know how many items you will add, give the size at creation. Then the collection does not have to grow and copy itself again and again. For lookup tables built once and read many times, .NET 8 offers `FrozenDictionary`.

**Real-life example:** Finding a word in a dictionary book is fast because it is sorted by letter. Finding it in a random pile of pages means reading every page.

**Interview question:** How can the choice of collection affect performance?

**Simple answer:** Looking up an item in a `List` is O(n), meaning it checks every item, but a `HashSet` or `Dictionary` is O(1), close to instant. So for repeated lookups I convert the list to a `HashSet` first. I also pre-size lists and dictionaries when I know the count, and use `Channel<T>` or concurrent collections for multi-threaded code.

```csharp
var blocked = blockedIds.ToHashSet();          // O(1) lookups
var list = new List<OrderDto>(orders.Count);   // pre-sized
```

### GC modes, LOH and disposal

**In simple words:** The garbage collector (GC) has modes. Workstation GC uses less memory and suits desktop apps. Server GC uses one heap per CPU core and gives more throughput for busy web servers, but uses more memory. Objects of 85,000 bytes or more go to the *Large Object Heap* (LOH), which is cleaned less often and can get fragmented. Objects that hold resources, like connections and streams, must be disposed with `using`.

**Real-life example:** Server GC is like a big restaurant with a cleaner for each section. Workstation GC is a small café with one cleaner. Very large furniture (LOH) is moved only during a big clean-up.

**Interview question:** Server GC or Workstation GC — which one and why?

**Simple answer:** Server GC favours throughput on multi-core web servers but uses more memory. Workstation GC favours low memory, so it suits desktop apps and small containers. I check what really runs with `GCSettings.IsServerGC`, avoid repeated large allocations by using `ArrayPool` or streaming, and dispose connections and streams with `using`.

### Static caching of Regex and HttpClient

**In simple words:** Some objects are expensive to create and should be reused. Creating a new `Regex` on every call parses the pattern every time. Creating a new `HttpClient` per request can use up all network sockets (*socket exhaustion*). Use the `[GeneratedRegex]` source generator, which builds the regex code at compile time. Use `IHttpClientFactory`, which reuses connections and still picks up DNS changes.

**Real-life example:** You do not buy a new car for each trip to the shop. You keep one car and service it now and then.

**Interview question:** Why should you not create a new HttpClient for every request?

**Simple answer:** Each new `HttpClient` opens new connections, and old sockets stay busy for a while after closing. Under load the server runs out of sockets. I use `IHttpClientFactory` with typed clients, which pools connections and refreshes them so DNS changes are seen. For regex I use `[GeneratedRegex]` or a static instance.

```csharp
[GeneratedRegex(@"^[A-Z]{3}-\d{4}$")]
public static partial Regex Sku();
builder.Services.AddHttpClient<IPaymentsClient, PaymentsClient>();
```

### Response compression, response caching and output caching

**In simple words:** *Compression* makes the response smaller (Brotli or Gzip), so it travels faster over the network. *Response caching* uses HTTP headers like `Cache-Control` so browsers and proxies can keep a copy. *Output caching* (.NET 7+) stores the whole response on the server and returns it without running your code again. Output caching supports policies, tags for removal, and sharing one result between identical requests that arrive together.

**Real-life example:** Compression is like vacuum-packing clothes so the parcel is smaller. Output caching is like a bakery that bakes popular bread in the morning and sells it from the shelf.

**Interview question:** What is the difference between response compression, response caching and output caching?

**Simple answer:** Compression reduces the bytes sent over the network, at some CPU cost. Response caching follows HTTP headers and lets clients and proxies reuse responses. Output caching keeps whole responses on the server with clear policies and tags, so the database is not hit again. I never output-cache per-user data unless the key includes the user.

### Pagination, connection pooling and rate limiting

**In simple words:** *Pagination* means returning data in small pages, never the whole table, with a maximum page size. *Connection pooling* keeps open database connections ready to reuse, because opening a new one is slow. Open a connection late and close it early with `using`. *Rate limiting* (built in since .NET 7) limits how many requests a caller can make, and returns HTTP 429 when they go over.

**Real-life example:** A bank has a fixed number of counters (pool). Each customer uses one and leaves quickly. A guard at the door lets only so many people in per minute (rate limit).

**Interview question:** What happens if you leak database connections, and how does rate limiting help?

**Simple answer:** The ADO.NET pool has a limit, 100 by default. If code holds connections too long, new requests wait and fail with "max pool size was reached". I open connections late and dispose them quickly. Rate limiting with `AddRateLimiter` protects the app from overload and noisy callers by rejecting extra requests with 429.

### Middleware ordering

**In simple words:** Middleware are steps that every request passes through, in the order you add them. Put cheap steps that can stop early (static files, rate limiting) before expensive ones (authentication, database work). Wrong order causes bugs and wasted work. For example, output caching must come after authorization, or cached data may reach users who are not allowed to see it.

**Real-life example:** At an airport, ticket check happens before security, and security before the gate. If you swap them, people waste time or the wrong people get through.

**Interview question:** Why does middleware order matter for performance?

**Simple answer:** Each request goes through the pipeline in order, so early steps run for every request. I put exception handling first, then compression, static files, routing, rate limiting, authentication and authorization, then output caching. This way cheap checks stop bad or simple requests before expensive work starts.

### Minimal APIs, Native AOT and JSON source generation

**In simple words:** Minimal APIs are a lighter way to write endpoints, with less overhead than MVC controllers. *Native AOT* (ahead-of-time compilation) builds your app into a native program before it runs. It starts very fast and uses less memory, but it cannot use runtime reflection, and some libraries do not support it. *JSON source generation* creates serializer code at build time, so no reflection is needed. It is required for AOT.

**Real-life example:** A normal app is like a cook who reads the recipe while cooking. An AOT app is like a ready meal that was cooked earlier, so you only heat it up.

**Interview question:** Why is Native AOT not always turned on?

**Simple answer:** AOT gives fast startup and lower memory, which is great for serverless and containers. But dynamic features like reflection-based serializers and some ORM or DI libraries break. I must use source generators, fix trimming warnings, and accept that peak speed can be slightly lower because there is no runtime JIT tuning.

### Streaming with IAsyncEnumerable

**In simple words:** When an API returns a large result, loading all rows into a list first uses a lot of memory. The client also waits until everything is loaded. With `IAsyncEnumerable<T>`, you send rows to the client as you read them. Memory stays flat and the first data arrives quickly.

**Real-life example:** A water tap gives you water as it flows. You do not have to wait for a whole tank to fill before you drink.

**Interview question:** How do you return a very large result set without high memory use?

**Simple answer:** I return an `IAsyncEnumerable<T>` and read the rows with EF Core's `AsAsyncEnumerable()`. ASP.NET Core writes each row to the response as it arrives. I also pass the `CancellationToken`, so the work stops if the client disconnects.

```csharp
app.MapGet("/orders/export", (AppDbContext db) =>
    db.Orders.AsNoTracking()
      .Select(o => new OrderRow(o.Id, o.Total))
      .AsAsyncEnumerable());
```

### Kestrel, HTTP/2 and HTTP/3, thread pool health

**In simple words:** Kestrel is the web server built into ASP.NET Core. You can set limits, like the maximum body size and timeouts. HTTP/2 sends many requests over one connection at the same time. HTTP/3 runs on QUIC (a protocol over UDP), which avoids the delay TCP causes when a packet is lost. Thread pool health means watching queue length and thread count, to catch blocking code early.

**Real-life example:** HTTP/1.1 is a single-lane road. HTTP/2 is a multi-lane highway on one road. HTTP/3 is a highway where one broken-down car does not stop the other lanes.

**Interview question:** How do you know if your app has thread pool starvation?

**Simple answer:** I watch `dotnet-counters`. If `ThreadPool Queue Length` grows, thread count rises slowly, CPU stays low and all endpoints get slow, it is starvation. Then I search for blocking calls like `.Result`, `.Wait()` and `GetAwaiter().GetResult()` and make them async.

### AsNoTracking and projection

**In simple words:** By default, EF Core *tracks* loaded entities, keeping a copy so `SaveChanges` can find changes. For read-only queries, this wastes memory and CPU. `AsNoTracking()` turns tracking off. *Projection* means using `Select` to load only the columns you need into a DTO (a simple data object), not whole entities.

**Real-life example:** If you only want a phone number, you look it up in the contact list. You do not photocopy the person's whole file.

**Interview question:** When do you use AsNoTracking?

**Simple answer:** I use it for every read-only query, because change tracking costs memory and CPU I do not need. I combine it with `Select` into a DTO, so SQL returns only a few columns. For read-heavy services I make no-tracking the default and use `AsTracking()` only where I update.

```csharp
var list = await db.Orders.AsNoTracking()
    .Where(o => o.CustomerId == id)
    .Select(o => new OrderDto(o.Id, o.Total))
    .ToListAsync(ct);
```

### N+1 queries, Include and split queries

**In simple words:** *N+1* means one query loads a list, then one extra query runs for each row. With 10 rows in development it looks fine. With 1,000 rows in production it is very slow. Fix it with projection, `Include`, or loading all related rows in one batch. When you `Include` two collections, rows can multiply (*cartesian explosion*); `AsSplitQuery()` loads each collection in its own query.

**Real-life example:** A delivery driver who goes back to the shop for each parcel makes N+1 trips. A smart driver loads all parcels at once.

**Interview question:** What is the N+1 problem and how do you fix it in EF Core?

**Simple answer:** One query loads the list and then one more query runs per item for related data. I fix it with a `Select` projection that joins in one query, with `Include`, or by batching ids into one `Where(ids.Contains(...))`. I find it by counting SQL calls per request in traces, and I avoid lazy loading in web APIs.

### Indexes, compiled queries, set-based updates, batching

**In simple words:** An *index* helps the database find rows fast, like the index in a book. A *compiled query* skips the LINQ-to-SQL translation step for a very hot query. *Set-based updates* (`ExecuteUpdateAsync`, `ExecuteDeleteAsync` in EF Core 7+) change many rows with one SQL statement, without loading them. *Batching* means saving many changes together; for very large loads, use `SqlBulkCopy`.

**Real-life example:** To change the price of all red shirts, a shop manager announces "all red shirts 10% off". They do not walk to each shirt and relabel it one by one.

**Interview question:** How do you update thousands of rows efficiently with EF Core?

**Simple answer:** I use `ExecuteUpdateAsync` or `ExecuteDeleteAsync`, which send one SQL statement and load nothing into memory. For inserts I add all items and call `SaveChanges` once, because EF batches them. For 100,000+ rows I use `SqlBulkCopy` or a bulk library.

```csharp
await db.Carts.Where(c => c.UpdatedAtUtc < cutoff)
    .ExecuteUpdateAsync(s => s.SetProperty(c => c.Status, CartStatus.Expired), ct);
```

### Keyset pagination and avoiding blobs

**In simple words:** *Offset pagination* (`Skip/Take`) reads and throws away all earlier rows, so deep pages get slower. *Keyset pagination* says "give me rows after the last id I saw", so it uses the index and stays fast. The trade-off: you can only go next or previous, not jump to page 500. Also, do not load big binary columns (photos, PDFs) in normal queries; store files in Blob Storage and keep only the URL.

**Real-life example:** Offset is like counting 1,000 pages from the start of a book every time. Keyset is like using a bookmark to open the book where you stopped.

**Interview question:** Offset vs keyset pagination — what is the difference?

**Simple answer:** Offset skips rows, so cost grows with the page number and pages shift when new rows are inserted. Keyset filters from the last seen key with an index seek, so cost stays constant and pages are stable. It needs a unique, indexed sort key and supports only next and previous.

```csharp
var next = await db.Orders.Where(o => o.Id > lastSeenId)
    .OrderBy(o => o.Id).Take(20).ToListAsync();
```

### Execution plans and indexing

**In simple words:** An *execution plan* shows how SQL Server runs your query: which indexes it uses, how it joins and how many rows each step reads. An *Index Seek* jumps straight to the rows, which is good. A *Scan* reads everything, which is bad for big tables. A *Key Lookup* means the index does not cover all needed columns. Every extra index speeds up reads but slows down inserts and updates.

**Real-life example:** The execution plan is like a GPS route. It shows which roads the database chose and where the traffic jams are.

**Interview question:** How do you read an execution plan to find a slow query?

**Simple answer:** I get the actual plan and look for the most expensive operators. Scans on big tables, key lookups, and spills to tempdb are red flags. I also compare estimated and actual row counts; a big difference means stale statistics or parameter sniffing. Then I add a covering index with `INCLUDE` columns or rewrite the query.

### SARGability: let the index be used

**In simple words:** A filter is *SARGable* (Search ARGument able) when SQL Server can use an index to seek. If you wrap the column in a function, like `YEAR(CreatedAt) = 2026`, the index cannot be used and SQL scans every row. Write it as a range on the bare column instead. Type mismatches (for example `NVARCHAR` vs `VARCHAR`) also break index use.

**Real-life example:** A phone book is sorted by surname. Finding names that start with "Joh" is fast. Finding names that end with "son" means reading the whole book.

**Interview question:** What makes a SQL predicate SARGable?

**Simple answer:** The indexed column must appear bare on one side of the comparison, with a matching data type. Functions on the column, leading wildcards like `LIKE '%son'`, and implicit type conversions cause scans. For example, I replace `YEAR(CreatedAt) = 2026` with a date range.

```sql
-- Bad:  WHERE YEAR(CreatedAt) = 2026
WHERE CreatedAt >= '2026-01-01' AND CreatedAt < '2027-01-01'
```

### Statistics, parameter sniffing, scans and stored procedures

**In simple words:** *Statistics* tell SQL Server how values are spread in a column, so it can guess row counts and pick a plan. Old statistics lead to bad plans. *Parameter sniffing* means SQL Server builds a plan for the first parameter value and reuses it. If the next value returns millions of rows instead of five, that plan is bad. Stored procedures are not faster by magic; parameterized queries from EF or Dapper also reuse plans.

**Real-life example:** A taxi driver plans a route for a small car and then uses the same route for a large truck. The truck gets stuck on narrow roads.

**Interview question:** What is parameter sniffing and how do you fix it?

**Simple answer:** SQL Server compiles a plan using the first parameter values and caches it. If later values have very different row counts, the cached plan is slow for them. A common sign is "fast in SSMS, slow from the app". I fix it with `OPTION (RECOMPILE)`, `OPTIMIZE FOR UNKNOWN`, splitting the logic, or forcing a good plan with Query Store.

### Partitioning and archiving

**In simple words:** Keep the data you use often small. *Partitioning* splits a big table into parts, usually by date, so queries read only the parts they need. Old partitions can be moved out almost instantly. *Archiving* moves old rows to cheaper storage. When deleting many rows, delete in small batches to avoid long locks and a huge transaction log.

**Real-life example:** An office keeps this year's files on the desk and moves old years' files to the basement storage room.

**Interview question:** How do you keep a fast-growing table, like an audit log, fast?

**Simple answer:** I partition it by date so queries skip old partitions, and old data can be switched out quickly. I archive or purge old rows in small batches, for example 5,000 at a time, to keep locks short. For reporting scans I consider a columnstore index.

### Core Web Vitals

**In simple words:** Core Web Vitals are three Google metrics for how a page feels to real users. *LCP* (Largest Contentful Paint) is when the main content appears; aim for 2.5 seconds or less. *INP* (Interaction to Next Paint) is how fast the page reacts to a click; aim for 200 ms or less. *CLS* (Cumulative Layout Shift) is how much the page jumps around while loading; aim for 0.1 or less.

**Real-life example:** In a restaurant: how fast your main dish arrives (LCP), how fast the waiter responds when you call (INP), and whether the table stays still while you eat (CLS).

**Interview question:** What are the three Core Web Vitals?

**Simple answer:** LCP measures loading, with a target of 2.5 seconds or less. INP measures responsiveness, with a target of 200 ms or less, and it replaced FID in 2024. CLS measures visual stability, with a target of 0.1 or less. I measure them with Lighthouse and real-user monitoring.

### Lazy loading and code splitting, bundle size

**In simple words:** A *bundle* is the JavaScript file the browser downloads for your app. If it is too big, the page loads slowly, especially on mobile. *Code splitting* breaks it into smaller parts. *Lazy loading* downloads a part only when the user opens that page. You can also shrink the bundle by removing unused libraries and replacing heavy ones.

**Real-life example:** A travel bag with only what you need today is light. You pick up the rest later only if you need it.

**Interview question:** How do you reduce the JavaScript bundle size of a React or Angular app?

**Simple answer:** I split code per route with `React.lazy` or Angular `loadComponent`, so each page loads only its own code. I analyse the bundle with a tool like `webpack-bundle-analyzer`, remove unused packages and replace heavy ones, like `moment` with `date-fns`. I also enable tree shaking (removing unused code) and compress with Brotli.

```javascript
const ReportsPage = React.lazy(() => import('./pages/ReportsPage'));
```

### Images, caching, service workers and CDN

**In simple words:** Images are often the biggest files on a page. Use modern formats (AVIF, WebP), the right size for each screen, set width and height, and lazy-load images below the visible area. *HTTP caching* lets the browser keep files; files with a hash in the name can be cached for a year. A *CDN* (content delivery network) serves files from servers near the user. A *service worker* (a background script in the browser) can cache files for fast repeat visits and offline use.

**Real-life example:** A CDN is like a chain of local shops. You buy milk from the shop on your street, not from the factory far away.

**Interview question:** How do you make images and static files load faster?

**Simple answer:** I use modern formats with responsive sizes, set image dimensions to avoid layout shift, and lazy-load images below the fold. I give fingerprinted files a long cache time and keep `index.html` on `no-cache`. I serve static files from a CDN, and use a service worker for repeat visits when it fits.

### API optimisation from the client

**In simple words:** The browser should not make API calls one after another when they do not depend on each other. Run them in parallel with `Promise.all`. If a screen always needs the same several calls, add one combined endpoint (a *BFF*, Backend For Frontend). Cache responses on the client, ask only for needed fields, and cancel old requests with `AbortController`.

**Real-life example:** At a food court, you order from three stalls at the same time and wait once. You do not wait for the first dish before ordering the second.

**Interview question:** How can the frontend reduce the time spent on API calls?

**Simple answer:** I run independent calls in parallel with `Promise.all` instead of awaiting each one in turn. For screens that always need the same data, I add a BFF endpoint that returns it in one call. I also cache and de-duplicate requests with tools like TanStack Query, and paginate and cancel stale requests.

```javascript
const [user, orders] = await Promise.all([getUser(id), getOrders(id)]);
```

### Pagination, infinite scroll, virtualisation, debounce and throttle

**In simple words:** Showing 10,000 rows in the page at once freezes the browser. Use pagination, infinite scroll, or *virtualisation*, which keeps only the visible rows (about 20) in the page. *Debounce* waits until the user stops typing before calling the API. *Throttle* lets a function run at most once per time period, which is useful for scroll or resize events.

**Real-life example:** Debounce is like a lift that waits a few seconds for more people before closing its doors. Throttle is like a bus that leaves every 10 minutes, no matter how many people arrive.

**Interview question:** What is the difference between debounce and throttle?

**Simple answer:** Debounce runs the function only after the user stops for a set time, so it suits a search box. Throttle runs the function at most once per interval, so it suits scroll or resize handlers. For search I also cancel the previous request, so an old answer cannot overwrite a newer one.

### "The API is slow in production": step by step

**In simple words:** This is a calm, step-by-step way to fix a slow API. If users are hurt, first reduce the damage: roll back, scale out, or turn off a feature flag. Then find out which endpoint is slow, since when, and what changed. Use APM (Application Performance Monitoring, like Application Insights) traces to see which layer takes the time: your code, SQL, an external call, cache or network. Fix one thing, measure again, and add an alert so it does not happen again.

**Real-life example:** A doctor first stops the bleeding, then runs tests to find the cause, and only then gives the right treatment.

**Interview question:** Someone says "the API is slow in production". What do you do?

**Simple answer:** I mitigate first if users are affected. Then I scope it: which endpoint, p95 or p99, and since when. I open a slow trace in Application Insights to see where the time goes. Next, I check the usual causes: slow SQL, N+1 queries, thread pool starvation, GC pressure, slow external calls or cache misses. I change one thing, re-measure under load, and add an alert and a regression test.
