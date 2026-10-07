## Multithreading and Async

### Thread vs ThreadPool vs Task

**Definition.** A `Thread` is an OS thread you create and own. The `ThreadPool` is a shared set of reusable worker threads managed by the runtime. A `Task` is a *promise of a result or completion* — an object that represents an operation, which may run on a pool thread, or on **no thread at all** (pure I/O).

**Why it matters.** Web servers handle thousands of concurrent requests with a small number of threads. Understanding what blocks a thread and what does not is the core of scalable .NET code.

| | `Thread` | `ThreadPool` work item | `Task` |
|---|---|---|---|
| Cost to create | High (~1 MB stack reserved, OS call) | Low (threads reused) | Very low (object) |
| Returns a result | No (use shared state) | No | `Task<T>` |
| Exceptions | Crash the process if unhandled | Crash the process | Captured, rethrown on `await` |
| Cancellation | Manual flag | Manual | `CancellationToken` |
| Composition | `Join()` | None | `await`, `WhenAll`, `WhenAny`, continuations |
| Typical use | Dedicated long-lived loop, STA/UI thread, custom priority | Legacy fire-and-forget | **Default for everything** |

```csharp
var t = new Thread(() => ProcessQueue()) { IsBackground = true };   // you own it
t.Start();

ThreadPool.QueueUserWorkItem(_ => SendEmail());                      // legacy style

Task<int> task = Task.Run(() => HeavyCalculation());                 // CPU work on the pool
int result = await task;                         // result + exceptions flow back
```

**Task vs Thread in one line:** a thread is a *worker*; a task is a *unit of work*. Many tasks share few threads, and an I/O-bound task uses no thread while it waits.

:::q What is the difference between Task and Thread?
A `Thread` is an OS-level execution resource that I create and manage. A `Task` is a higher-level abstraction for an operation that will complete in the future; it is scheduled on the thread pool, supports return values, exception propagation, cancellation and composition (`await`, `WhenAll`). For I/O-bound work a task does not occupy any thread while waiting.
:::

### How async/await really works

**Definition.** `async`/`await` lets you write asynchronous code that reads like synchronous code. The compiler rewrites an `async` method into a **state machine** (an `IAsyncStateMachine` struct with a `MoveNext()` method) that can pause at each `await` and resume later via a **continuation**.

```csharp
public async Task<decimal> GetTotalAsync(int customerId)
{
    var orders = await _http.GetFromJsonAsync<List<Order>>($"orders/{customerId}"); // state 0 -> 1
    return orders!.Sum(o => o.Total);                                                // state 1
}
```

```text
Thread A: GetTotalAsync() -> sends request -> await (not complete) -> returns Task to caller
          Thread A is FREE and serves other requests
          ... request is on the wire; NO thread is blocked (OS completion port / epoll) ...
Thread B (any pool thread): I/O completes -> continuation = MoveNext() state 1
          -> computes Sum -> completes the Task -> caller's await continues
```

**Key facts**

- `async` does **not** create a thread. `await` on an incomplete task saves local state, registers a continuation and *returns to the caller*.
- If the awaited task is already complete, execution continues **synchronously** with no context switch.
- The code after `await` may run on a *different* thread than the code before it (unless a `SynchronizationContext` brings it back).
- Exceptions are stored in the returned `Task` and rethrown at the `await`.
- Return types: `Task`, `Task<T>`, `ValueTask<T>`; `void` only for event handlers.
- Cost: a state machine object (heap allocation when it actually suspends). Don't make trivial pass-through methods `async` — just return the task (unless inside `using`/`try`).

:::example Real-world example
An API endpoint calls the payment gateway (200 ms). With `await`, the request thread returns to the pool during those 200 ms and serves other requests; 10 threads can keep thousands of such requests in flight. With `.Result`, each request pins a thread for 200 ms and the server collapses at the thread count.
:::

### SynchronizationContext and ConfigureAwait

**Definition.** A `SynchronizationContext` decides *where* a continuation runs. By default `await` captures the current context (or `TaskScheduler`) and posts the continuation back to it.

| Environment | Context | Effect after `await` |
|---|---|---|
| WinForms / WPF / MAUI | UI context | Resumes on the UI thread (so you can touch controls) |
| Classic ASP.NET (.NET Framework) | Request context | Resumes inside the request context; deadlock-prone |
| **ASP.NET Core / console / worker** | **None** | Resumes on any thread-pool thread |

`ConfigureAwait(false)` says "do not resume on the captured context". Rules:

- **Library code** (NuGet packages, shared class libraries): use `ConfigureAwait(false)` on every await so it works for any caller and cannot deadlock a UI caller.
- **ASP.NET Core application code**: not needed (no context), most teams omit it.
- **UI event handlers**: do *not* use it before touching UI.
- .NET 8 added `ConfigureAwait(ConfigureAwaitOptions.SuppressThrowing | ForceYielding ...)` for rare advanced cases.

### async void and other async pitfalls

**async void** cannot be awaited, so the caller never knows when it finishes, and an exception thrown inside is raised on the synchronization context and **crashes the process** (it cannot be caught by the caller). Allowed only for event handlers.

```csharp
async void Save() { await Task.Delay(10); throw new Exception("boom"); }   // BAD
async Task SaveAsync() { await Task.Delay(10); throw new Exception("boom"); } // GOOD
```

| Pitfall | Consequence | Fix |
|---|---|---|
| `.Result`, `.Wait()`, `.GetAwaiter().GetResult()` | Deadlock (UI/old ASP.NET) or thread-pool starvation (ASP.NET Core) | `await`; async all the way up |
| Fire-and-forget `_ = DoAsync();` with no handling | Lost exceptions, work killed on shutdown | Queue to a `Channel` + `BackgroundService`, or catch/log inside |
| `await` in a `foreach` for independent calls | Sequential, N x latency | Start all, `await Task.WhenAll` (bounded) |
| `list.ForEach(async x => ...)` | It is `async void`; nothing awaits it | `foreach` + `await`, or `Parallel.ForEachAsync` |
| `return task;` inside `using`/`try` without `await` | Resource disposed / exception missed before task completes | `return await` there |
| Ignoring `CancellationToken` | Work continues after client disconnects | Accept and pass the token everywhere |
| Wrapping I/O in `Task.Run` | Fake async, burns a pool thread | Call the real async API |

### Task.Run: CPU-bound vs I/O-bound

- **I/O-bound** (HTTP, DB, file, queue): there is a real async API — just `await` it. No thread is needed while waiting.
- **CPU-bound** (image resize, hashing, big sort): needs a thread. In a **UI app** use `await Task.Run(() => Compute())` to keep the UI responsive. In **ASP.NET Core** the request already runs on a pool thread, so `Task.Run` merely adds a hop and steals another pool thread; for heavy CPU work, queue it to a background worker/service.

```csharp
await Task.Run(() => File.ReadAllText(path));        // BAD: fake async over blocking I/O
var text = await File.ReadAllTextAsync(path, ct);     // GOOD: real async I/O

var hash = await Task.Run(() => ComputeHash(bigBuffer));   // OK in a desktop/UI app
```

For a dedicated long-running loop, `Task.Factory.StartNew(..., TaskCreationOptions.LongRunning)` avoids occupying a pool thread (or just use a `BackgroundService`).

### Task.WhenAll, WhenAny, WhenEach and Delay

```csharp
// Sequential: 2 x latency
var price = await GetPriceAsync(1, ct);
var stock = await GetStockAsync(1, ct);

// Concurrent: max(latency)
var priceTask = GetPriceAsync(1, ct);
var stockTask = GetStockAsync(1, ct);
await Task.WhenAll(priceTask, stockTask);
var (p, s) = (await priceTask, await stockTask);      // already complete
// or: decimal[] prices = await Task.WhenAll(ids.Select(id => GetPriceAsync(id, ct)));

// WhenAny: first to finish wins (timeout / hedged requests)
var work = FetchAsync(ct);
if (await Task.WhenAny(work, Task.Delay(TimeSpan.FromSeconds(2), ct)) != work)
    throw new TimeoutException();
// Simpler since .NET 6:  await work.WaitAsync(TimeSpan.FromSeconds(2), ct);

// WhenEach (.NET 9): process results as they complete, not in input order
await foreach (var done in Task.WhenEach(tasks))
{
    var result = await done;                         // already complete
    Handle(result);
}
```

- `WhenAll` rethrows only the **first** exception on `await`; inspect `whenAllTask.Exception.InnerExceptions` for all.
- `Task.Delay` is a non-blocking timer; `Thread.Sleep` blocks a thread. Never `Thread.Sleep` in async code.
- `WhenAll` over thousands of tasks starts them **all at once** — throttle with `SemaphoreSlim` or `Parallel.ForEachAsync`.

### CancellationToken and CancellationTokenSource

**Definition.** Cancellation in .NET is **cooperative**: a `CancellationTokenSource` (the controller) issues a `CancellationToken` (the signal); the worker checks the token and stops itself.

```csharp
public async Task<List<Product>> SearchAsync(string term, CancellationToken ct = default)
{
    var result = new List<Product>();
    foreach (var batch in _repo.Batches(term))
    {
        ct.ThrowIfCancellationRequested();                 // cooperative checkpoint
        result.AddRange(await _repo.LoadAsync(batch, ct)); // pass it down to I/O
    }
    return result;
}

// Timeout + caller cancellation, linked together
using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(5));
using var linked  = CancellationTokenSource.CreateLinkedTokenSource(timeout.Token, requestCt);
try { await SearchAsync("laptop", linked.Token); }
catch (OperationCanceledException) when (timeout.IsCancellationRequested)
{ /* we timed out */ }
catch (OperationCanceledException)
{ /* the caller cancelled */ }
```

- In ASP.NET Core, add `CancellationToken ct` to an action/endpoint parameter; it is bound to `HttpContext.RequestAborted` (fires when the client disconnects). Pass it to EF Core (`ToListAsync(ct)`), `HttpClient`, etc.
- `TaskCanceledException` derives from `OperationCanceledException`; catch the base type.
- `cts.CancelAfter(delay)` sets a timeout later; `token.Register(callback)` runs code on cancel; **dispose** a CTS that has a timer or registrations.
- A cancelled task ends in the `Canceled` state, not `Faulted`; don't log it as an error.

### Parallel programming: Parallel, PLINQ, ForEachAsync

| Tool | Best for | Notes |
|---|---|---|
| `Parallel.For` / `Parallel.ForEach` | CPU-bound loops over in-memory data | Synchronous body; blocks the calling thread until done |
| `Parallel.ForEachAsync` (.NET 6) | I/O-bound loops with **bounded** concurrency | Async body `(item, ct) => ValueTask`; set `MaxDegreeOfParallelism` |
| PLINQ (`AsParallel()`) | CPU-heavy LINQ pipelines | Output unordered unless `AsOrdered()` |
| `Task.WhenAll` | A known, small set of independent async calls | Unbounded unless you throttle |

```csharp
Parallel.ForEach(images, new ParallelOptions { MaxDegreeOfParallelism = 4 },
                 img => Resize(img));                               // CPU-bound

await Parallel.ForEachAsync(orderIds,
    new ParallelOptions { MaxDegreeOfParallelism = 8, CancellationToken = ct },
    async (id, token) => await _client.SyncOrderAsync(id, token));  // 8 calls at a time

var primes = Enumerable.Range(2, 2_000_000).AsParallel().Where(IsPrime).ToList();
```

Parallelism has overhead — it helps only for substantial CPU work per item. Never mutate shared state from the body without synchronisation, and never pass an `async` lambda to `Parallel.ForEach` (it becomes `async void`).

### Race conditions

**Definition.** A *race condition* is when the result depends on the unpredictable timing of threads accessing shared mutable state. The classic is the non-atomic read-modify-write.

```csharp
int counter = 0;
Parallel.For(0, 100_000, _ => counter++);
Console.WriteLine(counter);   // Output: e.g. 87342 (varies every run; expected 100000)
```

`counter++` is three steps (read, add, write). Two threads read the same value and one increment is lost. Fixes:

```csharp
Parallel.For(0, 100_000, _ => Interlocked.Increment(ref counter));   // atomic, lock-free
// or
var gate = new object();
Parallel.For(0, 100_000, _ => { lock (gate) { counter++; } });       // mutual exclusion
// Output (both): 100000
```

Other shapes of the same bug: **check-then-act** (`if (!dict.ContainsKey(k)) dict[k] = Load(k);` — two threads both pass the check), **lost update in the database** (two requests read stock = 1 and both decrement — fix with an optimistic concurrency token / `rowversion` or an atomic `UPDATE ... WHERE Stock >= @qty`).

### lock, Monitor and System.Threading.Lock

**Definition.** `lock` gives mutual exclusion: only one thread at a time runs the guarded block. It compiles to `Monitor.Enter/Exit` in a `try/finally`.

```csharp
private readonly object _sync = new();
public void Add(OrderLine l) { lock (_sync) { _lines.Add(l); _total += l.Total; } }

// .NET 9 / C# 13: dedicated Lock type — faster, and the intent is explicit
private readonly Lock _lock = new();
public void Add2(OrderLine l) { lock (_lock) { _lines.Add(l); } }  // compiler uses EnterScope()
using (_lock.EnterScope()) { /* same thing, explicit */ }
```

**Rules.** Lock on a *private readonly* object — never `this`, `typeof(X)`, a string or a boxed value (others can lock the same thing → surprise deadlocks). Keep the critical section tiny. **You cannot `await` inside a `lock`** (compile error CS1996): the continuation may resume on a different thread, and locks are thread-affine. Use `SemaphoreSlim` for async mutual exclusion.

| Primitive | Use |
|---|---|
| `lock` / `Lock` / `Monitor` | In-process, synchronous critical sections |
| `Interlocked` | Single atomic counter/flag/swap, lock-free |
| `SemaphoreSlim` | Async-friendly; limit N concurrent callers |
| `ReaderWriterLockSlim` | Many readers, rare writers |
| `Mutex` | Cross-process (e.g. single app instance) |
| `Semaphore` | Cross-process counting semaphore (heavier kernel object) |

### Deadlocks

**Definition.** Two or more threads wait on each other forever. Needs: mutual exclusion, hold-and-wait, no pre-emption, circular wait.

**Classic 1 — sync-over-async on a context:**

```csharp
// WinForms/WPF handler (or classic ASP.NET): thread has a SynchronizationContext
private void Button_Click(object s, EventArgs e)
{
    var data = GetDataAsync().Result;      // blocks the UI thread waiting for the task...
}
private async Task<string> GetDataAsync()
{
    await Task.Delay(100);                 // ...but this continuation needs the UI thread
    return "x";                            // => DEADLOCK, UI frozen
}
```

Fix: make the handler `async` and `await` (async all the way). `ConfigureAwait(false)` in `GetDataAsync` also breaks the cycle but is a fragile workaround. In ASP.NET Core there is no context so it does not deadlock — but it blocks a pool thread, which causes **thread-pool starvation** under load.

**Classic 2 — lock ordering:**

```csharp
// Thread 1                       // Thread 2
lock (accountA) {                 lock (accountB) {
    lock (accountB) { ... }           lock (accountA) { ... }   // waits forever
}                                 }
```

Fixes: always acquire locks in one global order (e.g. by account Id), avoid nested locks, use `Monitor.TryEnter(obj, timeout)`, or redesign to a single lock/lock-free structure.

### Thread safety

**Definition.** Code is *thread-safe* if it behaves correctly when called from multiple threads at once.

Strategies, best first: **no shared state** → **immutability** (`record`, `readonly`, `ImmutableList`) → **confinement** (state owned by one thread/request) → **atomics** (`Interlocked`) → **locks** → **concurrent collections**.

**ASP.NET Core specifics**

- A **singleton** service is shared by all requests; any mutable field in it must be thread-safe. `static` mutable fields are shared across all requests.
- `List<T>`, `Dictionary<,>`, `StringBuilder` are **not** thread-safe; `HttpClient` and `ConcurrentDictionary` are.
- `DbContext` is **not** thread-safe: `await Task.WhenAll(db.A.ToListAsync(), db.B.ToListAsync())` on one context throws "A second operation was started on this context instance". Use one context per concurrent operation (e.g. `IDbContextFactory<T>`).
- `AsyncLocal<T>` flows with the async call chain; `[ThreadStatic]` does not (an `await` may move you to another thread).

### SemaphoreSlim for async throttling

**Definition.** `SemaphoreSlim` limits how many callers are inside a section at once and supports `WaitAsync()`, so it works with `await` (unlike `lock`).

```csharp
private static readonly SemaphoreSlim _gate = new(5);      // at most 5 concurrent calls

public async Task<string> FetchAsync(string url, CancellationToken ct)
{
    await _gate.WaitAsync(ct);
    try { return await _http.GetStringAsync(url, ct); }
    finally { _gate.Release(); }                            // always release
}

var pages = await Task.WhenAll(urls.Select(u => FetchAsync(u, ct)));   // 5 at a time

// async mutex: initial=1, max=1
private readonly SemaphoreSlim _mutex = new(1, 1);
```

Typical use: don't overwhelm a third-party API or the database with 1,000 concurrent calls; serialize access to a non-thread-safe resource from async code. `Semaphore` (non-slim) is a kernel object usable across processes.

### Concurrent collections, Channel and BlockingCollection

| Type | Notes |
|---|---|
| `ConcurrentDictionary<K,V>` | `TryAdd`, `GetOrAdd`, `AddOrUpdate` are atomic per key; the **factory delegate may run more than once** |
| `ConcurrentQueue<T>` / `ConcurrentStack<T>` | Lock-free FIFO / LIFO |
| `ConcurrentBag<T>` | Unordered, optimised for same-thread produce/consume |
| `BlockingCollection<T>` | Producer-consumer that **blocks threads** (sync); legacy |
| `Channel<T>` | Async producer-consumer with bounded back-pressure; **modern choice** |

```csharp
var cache = new ConcurrentDictionary<int, Lazy<Task<Product>>>();
// Lazy ensures the expensive load runs once even if the factory races
var product = await cache.GetOrAdd(id, i => new Lazy<Task<Product>>(() => LoadAsync(i))).Value;

// Channel: API enqueues, background worker processes at its own pace
var channel = Channel.CreateBounded<Order>(new BoundedChannelOptions(100)
    { FullMode = BoundedChannelFullMode.Wait });            // back-pressure when full

await channel.Writer.WriteAsync(order, ct);                 // producer (controller)

await foreach (var o in channel.Reader.ReadAllAsync(ct))    // consumer (BackgroundService)
    await ProcessAsync(o, ct);
// shutdown: channel.Writer.Complete();
```

Note `ContainsKey` followed by an indexer on a `ConcurrentDictionary` is *still* a race — use `GetOrAdd`/`TryAdd`.

### ValueTask and IAsyncEnumerable

**`ValueTask<T>`** is a struct that avoids allocating a `Task` when the result is usually available synchronously (cache hit, buffered read).

```csharp
public ValueTask<Product?> GetAsync(int id)
{
    if (_cache.TryGetValue(id, out var p)) return new ValueTask<Product?>(p);   // no allocation
    return new ValueTask<Product?>(LoadAsync(id));                              // slow path
}
```

Rules: await it **once**; never await it concurrently or call `.Result` before completion; call `.AsTask()` if you need a real `Task`. Default to `Task<T>`; use `ValueTask<T>` on hot paths after measuring.

**`IAsyncEnumerable<T>`** streams items asynchronously with `await foreach` — no need to buffer the whole result.

```csharp
public async IAsyncEnumerable<Order> StreamOrdersAsync(
    [EnumeratorCancellation] CancellationToken ct = default)
{
    await foreach (var o in _db.Orders.AsNoTracking().AsAsyncEnumerable().WithCancellation(ct))
        yield return o;                                     // producer pace, low memory
}

await foreach (var o in svc.StreamOrdersAsync(ct)) Export(o);
// Minimal API: streams the JSON array as items arrive
// app.MapGet("/orders", (OrderService s, CancellationToken ct) => s.StreamOrdersAsync(ct));
```

:::scenario API latency spikes under load while CPU stays low
Symptoms: p99 jumps from 80 ms to 8 s at 300 req/s, CPU at 20%, no DB slowness. Cause: sync-over-async — `var user = _client.GetUserAsync(id).Result;` in a hot path. Each request blocks a pool thread; the pool starts with few threads and injects about one per second (hill climbing), so requests queue (**thread-pool starvation**).
**Diagnose:** `dotnet-counters monitor` -> `ThreadPool Queue Length` and `ThreadPool Thread Count` rising. **Fix:** `await` all the way up; replace `Task.Run` over I/O; throttle outbound calls with `SemaphoreSlim`; do not just raise `SetMinThreads` (it hides the bug).
:::

:::scenario Two customers buy the last item
Stock = 1, two requests both read `Stock >= qty`, both decrement, stock goes to -1. It is a check-then-act race across *processes*, so `lock` doesn't help (it is in-process only). **Fix:** a database-level guard — `UPDATE Products SET Stock = Stock - @q WHERE Id = @id AND Stock >= @q` and check rows affected, or an EF Core concurrency token (`[Timestamp] byte[] RowVersion`) and retry on `DbUpdateConcurrencyException`.
:::

:::q How does async/await work without blocking a thread?
The compiler turns the method into a state machine. At an `await` on an incomplete task it registers a continuation and returns to the caller, freeing the thread. The operating system finishes the I/O (completion port / epoll) and the runtime schedules the continuation on a pool thread. While waiting there is no thread dedicated to that operation.
:::

:::q Why is async void bad and when is it acceptable?
It can't be awaited, so the caller can't know when it ends, and an unhandled exception inside crashes the process because there's no `Task` to hold it. The only acceptable use is event handlers, where the signature forces `void`; wrap the body in try/catch there.
:::

:::q What is a deadlock and how do you prevent it?
Threads waiting on each other forever. Common causes are blocking on async code with `.Result`/`.Wait()` on a thread whose context the continuation needs, and acquiring locks in inconsistent order. Prevent by going async all the way, using a consistent lock ordering, `TryEnter` with timeouts, or avoiding nested locks.
:::

:::q lock vs SemaphoreSlim vs Interlocked?
`Interlocked` is for a single atomic operation on one variable, no blocking. `lock` is mutual exclusion for synchronous sections in one process. `SemaphoreSlim` allows N concurrent holders and supports `WaitAsync`, so it's the right tool for async code and throttling; you cannot `await` inside `lock`.
:::
