### Join, GroupJoin and the left-join pattern

**In simple words:** `Join` connects two lists where the keys are equal, like orders and customers by customer ID. It is an inner join, so items with no match are dropped. `GroupJoin` gives each outer item together with a list of its matching items. To make a left join (keep items with no match), use `GroupJoin` with `DefaultIfEmpty`.

**Real-life example:** A teacher matches students to exam papers by roll number. An inner join lists only students who wrote the exam; a left join lists every student and shows "no paper" for those who were absent.

**Interview question:** How do you write a left join in LINQ?

**Simple answer:** I use `join … into g`, then `from x in g.DefaultIfEmpty()`. This keeps every item from the left side, and the right side is `null` when there is no match. .NET 10 also adds a built-in `LeftJoin` method. With EF Core, I usually use navigation properties, and EF writes the join for me.

```csharp
var left = from c in customers
           join o in orders on c.Id equals o.CustomerId into g
           from o in g.DefaultIfEmpty()
           select new { c.Name, OrderId = o?.Id };
```

### Set, partitioning and modern operators

**In simple words:** Set operators work like sets in maths. `Distinct` removes duplicates, and `Union`, `Intersect` and `Except` combine two lists. Partitioning operators take one part of a list: `Skip` and `Take` are used for paging. Newer .NET versions add useful operators like `DistinctBy`, `MaxBy`, `Chunk` (.NET 6) and `CountBy` (.NET 9).

**Real-life example:** A library catalogue shows 10 books per screen. To see screen 3, it skips the first 20 books and takes the next 10.

**Interview question:** How do you implement paging with LINQ?

**Simple answer:** I call `OrderBy` first, then `Skip((page - 1) * size).Take(size)`. The `OrderBy` is required, because without it the order is not guaranteed. For very deep pages, I prefer keyset paging, like `Where(p => p.Id > lastId).Take(size)`, because `Skip` still reads all the skipped rows.

```csharp
var page2 = products.OrderBy(p => p.Id).Skip(10).Take(10);
var priciest = products.MaxBy(p => p.Price); // the product, not just the price
```

### Deferred vs immediate execution

**In simple words:** Most LINQ queries do not run when you write them. They only describe the work. They run when you loop over them, or call methods like `ToList`, `Count` or `First`. This is called deferred execution. Each time you loop again, the query runs again.

**Real-life example:** A recipe card describes a dish, but no food exists until someone cooks it. If you cook from the card twice, you get two separate meals.

**Interview question:** What is deferred execution, and which operators run immediately?

**Simple answer:** Deferred means operators like `Where`, `Select` and `OrderBy` only build the query; it runs when it is enumerated (looped over). Methods that return a single value or a full collection run immediately — for example `ToList`, `ToArray`, `Count`, `Sum`, `First` and `Any`. If I need the result more than once, I call `ToList()` once, so the query does not run again.

```csharp
var nums = new List<int> { 1, 2, 3 };
var evens = nums.Where(n => n % 2 == 0);    // not run yet
nums.Add(4);
Console.WriteLine(string.Join(",", evens)); // 2,4
```

### LINQ to Objects vs LINQ to EF Core

**In simple words:** LINQ to Objects runs on lists in memory, using normal compiled C# code. LINQ to EF Core runs on `DbSet<T>`, which is an `IQueryable<T>`. Your lambda becomes an expression tree (the query stored as data) that EF Core turns into SQL. So inside an EF query, you can only use things EF knows how to translate.

**Real-life example:** Talking to a friend in your own language is like LINQ to Objects. Talking through a translator is like LINQ to EF Core — the translator can only pass on words they know.

**Interview question:** Why does my EF Core query throw "could not be translated"?

**Simple answer:** Part of the lambda calls something EF cannot turn into SQL, usually my own C# method inside `Where` or `OrderBy`. I fix it by rewriting the condition with simple properties or `EF.Functions`. Or I filter in the database first, load the smaller result with `ToListAsync()`, and finish the work in memory.

```csharp
db.Orders.Where(o => IsVip(o));      // throws: your method cannot become SQL
db.Orders.Where(o => o.Total > 500); // OK: becomes WHERE Total > 500
```

### Any() vs Count() > 0

**In simple words:** Both can check if a sequence has items, but `Any()` is better for this job. `Any()` stops at the first item it finds. `Count()` may go through everything, just to compare the number with zero. In EF Core, `Any()` becomes SQL `EXISTS`, and `Count()` becomes `COUNT(*)`.

**Real-life example:** To know if anyone is in the waiting room, you just open the door and look. You do not need to count every person.

**Interview question:** Why use `Any()` instead of `Count() > 0`?

**Simple answer:** `Any()` stops as soon as it finds one item, and in SQL it becomes `EXISTS`, which also stops early. `Count()` may read every item, or every row with `COUNT(*)`. For a `List<T>` or an array, I just use the `Count` or `Length` property, which is instant (O(1)).

```csharp
if (await db.Orders.AnyAsync(o => o.CustomerId == id)) { /* EXISTS */ }
if (list.Count > 0) { /* List<T>: property, instant */ }
```

### Classic LINQ interview exercises

**In simple words:** Interviewers often ask you to write small LINQ queries live. Common tasks are: customers with no orders, the highest order per customer, the second-highest value, duplicates in a list, and totals per group. Most answers combine `GroupBy`, `Select`, `Any`, `OrderBy` and `Skip`.

**Real-life example:** It is like a driving test. You already know the rules; now you must park, turn and reverse in front of the examiner.

**Interview question:** How do you find duplicate values in a list with LINQ?

**Simple answer:** I group the items by their own value, keep the groups with more than one item, and select the keys. For the second-highest value, I use `Distinct()`, sort in descending order, then call `Skip(1).FirstOrDefault()`. `Distinct` matters, because equal top values would give a wrong answer.

```csharp
var dups = new[] { "a", "b", "a", "c", "b" }
    .GroupBy(x => x).Where(g => g.Count() > 1).Select(g => g.Key); // a, b
var second = totals.Distinct().OrderByDescending(t => t).Skip(1).FirstOrDefault();
```

### try, catch, finally, throw

**In simple words:** An exception is an object that describes an error while the program runs. `try` wraps code that might fail. `catch` handles a specific type of error; put specific types before general ones. `finally` always runs for cleanup, with or without an error. `throw` raises an exception.

**Real-life example:** A chef tries a new recipe (try). If the food burns, they cook a backup dish (catch), and either way they clean the kitchen at the end (finally).

**Interview question:** Does `finally` always run?

**Simple answer:** Almost always — after normal completion, after a `return`, or after an exception. It does not run if the process is killed, for example by `Environment.FailFast`, a stack overflow or a power cut. Also, never throw from `finally`, because the new exception hides the original one.

```csharp
try { await SaveOrderAsync(order); }
catch (DbUpdateConcurrencyException ex) { throw new ConflictException("Changed", ex); }
catch (Exception ex) { _logger.LogError(ex, "Save failed"); throw; }
finally { _attempts++; } // always runs
```

### throw vs throw ex

**In simple words:** Inside a `catch` block, `throw;` raises the same exception again. It keeps the original stack trace (the list of method calls that led to the error). `throw ex;` raises it as if it started on the current line. That deletes the real place where the error happened.

**Real-life example:** A parcel's tracking history shows every stop it passed. `throw;` forwards the parcel with its full history, but `throw ex;` puts a new label on it, so you lose where it came from.

**Interview question:** What is the difference between `throw` and `throw ex`?

**Simple answer:** `throw;` keeps the original stack trace, so I can see where the error really happened. `throw ex;` resets the stack trace to the current line and hides the root cause. I always use `throw;`, or I wrap the error in a new exception and pass the original as the inner exception.

```csharp
catch (Exception ex)
{
    _logger.LogError(ex, "Payment failed");
    throw;  // good: keeps the stack trace
    // throw ex;  // bad: stack trace starts here
}
```

### Exception filters (when)

**In simple words:** An exception filter adds a condition to a `catch` block with `when`. The block catches the exception only if the condition is true. The filter runs before the stack is unwound (before .NET leaves the methods that failed). So exceptions that do not match are not touched, and all their details stay for debugging.

**Real-life example:** A hospital's emergency desk takes only urgent cases. Other patients are not taken in and sent out again; they simply go to the normal queue.

**Interview question:** Why use `catch … when` instead of a `catch` with an `if` and `throw;` inside?

**Simple answer:** With a filter, a non-matching exception is never caught, so there is no catch-and-rethrow cost. The original stack and local values stay complete for debuggers and crash dumps. The code is also cleaner — for example, catching only HTTP 429 errors to retry.

```csharp
catch (HttpRequestException ex) when (ex.StatusCode == HttpStatusCode.TooManyRequests)
{
    await Task.Delay(TimeSpan.FromSeconds(2), ct); // retry later
}
```

### using, IDisposable and IAsyncDisposable

**In simple words:** Some objects hold resources like files, database connections or network sockets. They implement `IDisposable`, which has a `Dispose()` method to release them. A `using` statement calls `Dispose()` for you, even if an exception happens. `await using` does the same for `IAsyncDisposable` objects, which clean up asynchronously.

**Real-life example:** You must return a library book even if you did not finish it. `using` is like a rule that returns the book for you when you leave, whatever happens.

**Interview question:** What does the `using` statement do?

**Simple answer:** It guarantees that `Dispose()` is called at the end of the block or scope. The compiler turns it into a `try`/`finally` that calls `Dispose()` in the `finally`. With dependency injection, the container disposes the objects it creates, so I do not dispose injected services myself.

```csharp
using var reader = new StreamReader(path); // disposed at end of scope
await using var tx = await db.Database.BeginTransactionAsync(ct);
```

### Custom exceptions

**In simple words:** A custom exception is your own exception class for a business error, like `InsufficientStockException`. It derives from `Exception`, and its name ends with "Exception". Callers can catch it specifically, and a global handler can map it to an HTTP status code. Create one only when someone needs to react to it differently.

**Real-life example:** A hospital uses different alarm codes for fire, medical emergency and security. Each code tells staff exactly how to respond.

**Interview question:** How do you create a custom exception, and when should you?

**Simple answer:** I derive from `Exception`, add the standard constructors — empty, message, and message plus inner exception — and add extra data as read-only properties. I create one only when code must catch it or map it to a status code, like `NotFoundException` to 404. A small set, like NotFound, Validation and Conflict, covers most APIs.

```csharp
public sealed class NotFoundException(string entity, object key)
    : Exception($"{entity} '{key}' was not found.");
```

### Global exception handling in ASP.NET Core

**In simple words:** Global exception handling means one central place catches every unhandled error in a web app. It logs the error and returns a clean, consistent HTTP response. So controllers do not need `try`/`catch` everywhere. In .NET 8 and later, you implement `IExceptionHandler` and return `ProblemDetails`, a standard JSON format for errors.

**Real-life example:** A big office has one help desk for all problems. Every complaint goes there, and the help desk records it and replies in a standard way.

**Interview question:** How do you implement global exception handling in ASP.NET Core?

**Simple answer:** On .NET 8+, I write a class that implements `IExceptionHandler` and register it with `AddExceptionHandler<T>()`. I also add `AddProblemDetails()` and call `app.UseExceptionHandler()` early in the pipeline. The handler maps exception types to status codes, logs once, and never sends stack traces to clients.

```csharp
builder.Services.AddProblemDetails();
builder.Services.AddExceptionHandler<GlobalExceptionHandler>();
var app = builder.Build();
app.UseExceptionHandler(); // first, so it wraps everything
```

### Logging exceptions

**In simple words:** When you log an exception, pass the exception object and a message template with named placeholders. This is structured logging: tools like Seq or Application Insights store each value separately, so you can search by `OrderId`. Log each error once, at the edge of the app. Never log passwords or card numbers.

**Real-life example:** A hospital fills a form with fixed fields — name, date, symptom — instead of writing a free story. Later, it is easy to find all patients with the same symptom.

**Interview question:** What is the correct way to log an exception with `ILogger`?

**Simple answer:** I call `_logger.LogError(ex, "Order {OrderId} failed", orderId)`. The exception goes first, so the full stack trace is saved, and the placeholders become searchable fields. I do not use string interpolation in the message, and I log once in the global handler, not in every layer.

```csharp
_logger.LogError(ex, "Failed to place order {OrderId}", orderId); // good
_logger.LogError($"Failed: {ex.Message}");                        // bad: no stack trace
```

### Best practices

**In simple words:** Catch only the exceptions you can really handle, and let the others reach the global handler. Rethrow with `throw;`, clean up with `using`, and log each error once. Do not use exceptions for normal outcomes like "out of stock"; return a result instead. Throwing an exception is much slower than returning a value.

**Real-life example:** A fire alarm is for real fires, not for telling people that lunch is ready. If it rings for everyday things, people stop paying attention.

**Interview question:** Why shouldn't you use exceptions for control flow?

**Simple answer:** Exceptions are slow, because the runtime captures the stack and unwinds it. They also make the code harder to follow and fill the logs with noise. For expected outcomes I use `TryParse`-style methods, return values or a Result type. I keep exceptions for truly unexpected problems, like the database being down.

### Thread vs ThreadPool vs Task

**In simple words:** A `Thread` is an operating-system worker that you create and manage yourself, and it is expensive to create. The `ThreadPool` is a shared group of ready workers that .NET reuses. A `Task` is an object that represents work that will finish in the future. Tasks usually run on pool threads, and an I/O task uses no thread while it waits.

**Real-life example:** A thread is a cook you hire just for yourself. The thread pool is the restaurant's team of cooks, and a task is an order ticket that any free cook can pick up.

**Interview question:** What is the difference between a Task and a Thread?

**Simple answer:** A thread is a low-level OS worker that I create and manage. A task is a higher-level object for an operation that finishes later. It runs on the thread pool and supports results, exceptions, cancellation and `await`. For I/O work, like a database call, a task does not hold any thread while it waits.

### How async/await really works

**In simple words:** `async`/`await` lets you write non-blocking code that reads like normal code. The compiler turns an `async` method into a state machine (a small object that remembers where it stopped). At an `await` on unfinished work, the method pauses and gives the thread back. When the work finishes, the method continues from the same point, maybe on a different thread.

**Real-life example:** You order food at a counter and get a buzzer. You sit down and do other things; when the buzzer rings, you go back and collect your food.

**Interview question:** How does async/await work without blocking a thread?

**Simple answer:** The compiler turns the method into a state machine. At an `await` on an unfinished task, it registers a continuation (the code to run next) and returns, so the thread is free for other work. The operating system finishes the I/O, and then .NET runs the continuation on a pool thread. No thread waits during the I/O.

### SynchronizationContext and ConfigureAwait

**In simple words:** A `SynchronizationContext` decides where your code continues after an `await`. In WPF or WinForms, it brings you back to the UI thread, so you can update controls. ASP.NET Core has no context, so code continues on any pool thread. `ConfigureAwait(false)` means "do not go back to the original context".

**Real-life example:** A context is like a bank rule: "come back to the same counter after the manager signs". `ConfigureAwait(false)` says "any free counter is fine".

**Interview question:** When should you use `ConfigureAwait(false)`?

**Simple answer:** In library code, like NuGet packages, I use it on every `await`. Then the library works safely for any caller and cannot cause a UI deadlock. In ASP.NET Core app code it is not needed, because there is no context. In UI event handlers, I do not use it before touching UI controls.

### async void and other async pitfalls

**In simple words:** An `async void` method cannot be awaited, so the caller never knows when it ends. If it throws, the caller cannot catch the error, and the app can crash. Use `async Task` instead, except for event handlers. Other common mistakes are blocking with `.Result` or `.Wait()`, and not passing the `CancellationToken`.

**Real-life example:** `async void` is like posting a letter with no return address. If something goes wrong, nobody can tell you about it.

**Interview question:** Why is `async void` bad, and when is it acceptable?

**Simple answer:** It cannot be awaited, and an unhandled exception inside it can crash the process, because there is no `Task` to hold the error. It is acceptable only for event handlers, where the signature must return `void`. Even then, I wrap the body in `try`/`catch`.

```csharp
async void Save() { await Task.Delay(10); throw new Exception(); }      // bad
async Task SaveAsync() { await Task.Delay(10); throw new Exception(); } // good
```

### Task.Run: CPU-bound vs I/O-bound

**In simple words:** I/O-bound work waits for something outside, like a database, a file or an HTTP call. For it, just `await` the real async method; no thread is needed while waiting. CPU-bound work keeps the processor busy, like resizing images. `Task.Run` moves CPU work to a pool thread, which keeps a UI app responsive.

**Real-life example:** Waiting for a pizza delivery is I/O-bound — you can do other things meanwhile. Washing a big pile of dishes is CPU-bound — someone has to actually do the work.

**Interview question:** Should you use `Task.Run` in ASP.NET Core?

**Simple answer:** Usually no. The request already runs on a pool thread, so `Task.Run` just moves the work to another pool thread and adds cost. Wrapping I/O in `Task.Run` is "fake async"; I call the real async API instead. For heavy CPU work in a web app, I send it to a background service.

```csharp
await Task.Run(() => File.ReadAllText(path));     // bad: fake async
var text = await File.ReadAllTextAsync(path, ct); // good: real async I/O
```

### Task.WhenAll, WhenAny, WhenEach and Delay

**In simple words:** `Task.WhenAll` waits until all tasks finish, so independent calls run at the same time. `Task.WhenAny` finishes when the first task finishes, which is useful for timeouts. `Task.WhenEach` (.NET 9) gives you each task as soon as it completes. `Task.Delay` waits without blocking a thread, unlike `Thread.Sleep`.

**Real-life example:** You order a pizza, a drink and a dessert at the same time. You wait only as long as the slowest item, not for all three one after another.

**Interview question:** What is the difference between `Task.WhenAll` and awaiting tasks one by one?

**Simple answer:** Awaiting one by one runs the calls in sequence, so the total time is the sum of all of them. `WhenAll` runs them at the same time, so the total time is the slowest one. On `await`, `WhenAll` rethrows only the first exception; the others are in the task's `Exception.InnerExceptions`.

```csharp
var priceTask = GetPriceAsync(id, ct);
var stockTask = GetStockAsync(id, ct);
await Task.WhenAll(priceTask, stockTask); // both run at the same time
```

### CancellationToken and CancellationTokenSource

**In simple words:** Cancellation in .NET is cooperative. A `CancellationTokenSource` sends the "stop" signal. A `CancellationToken` carries that signal into your methods. Your code must check the token, or pass it to async APIs, and then stop by itself. In ASP.NET Core, the request's token fires when the client disconnects.

**Real-life example:** A delivery app lets you cancel an order. The app sends the message, but the restaurant must check it and stop cooking.

**Interview question:** How does cancellation work in .NET?

**Simple answer:** I create a `CancellationTokenSource` and pass its `Token` down to every async method, like EF Core's `ToListAsync(ct)` and `HttpClient` calls. The work checks the token and throws `OperationCanceledException` when cancellation is requested. A cancelled task is not a failure, so I do not log it as an error.

```csharp
using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(5));
var products = await db.Products.ToListAsync(cts.Token);
```

### Parallel programming: Parallel, PLINQ, ForEachAsync

**In simple words:** Parallel programming splits work so that several CPU cores run it at the same time. `Parallel.For` and `Parallel.ForEach` suit CPU-heavy loops over data in memory. `Parallel.ForEachAsync` (.NET 6) suits async I/O work, with a limit on how many run at once. PLINQ (`AsParallel()`) runs LINQ queries in parallel.

**Real-life example:** Instead of one cashier serving a long line, a supermarket opens four checkouts. Customers are served faster, but only if there are enough customers to share.

**Interview question:** How do you run many async calls in parallel, but only N at a time?

**Simple answer:** I use `Parallel.ForEachAsync` with `MaxDegreeOfParallelism` set to N, and I pass the cancellation token. Another option is `SemaphoreSlim` with `Task.WhenAll`. I never pass an `async` lambda to `Parallel.ForEach`, because it becomes `async void` and nothing waits for it.

```csharp
await Parallel.ForEachAsync(orderIds,
    new ParallelOptions { MaxDegreeOfParallelism = 8, CancellationToken = ct },
    async (id, token) => await _client.SyncOrderAsync(id, token));
```

### Race conditions

**In simple words:** A race condition happens when the result depends on which thread runs first. It happens when threads read and change the same data at the same time. For example, `counter++` is three steps: read, add, write. Two threads can read the same value, and one update is lost.

**Real-life example:** Two bank tellers both see a balance of 100, and each pays out 80 to a different person. Both say "OK", and the bank pays 160 from an account that had only 100.

**Interview question:** How do you fix a race condition?

**Simple answer:** First, I try to remove shared data that changes. If I cannot, I make the update atomic (done as one step that cannot be split): `Interlocked` for a counter, `lock` for a block of code, `ConcurrentDictionary` for a shared map. For races between servers, like stock levels, I use the database: a row version, or `UPDATE … WHERE Stock >= @qty`.

```csharp
Parallel.For(0, 100_000, _ => counter++);                         // wrong total
Parallel.For(0, 100_000, _ => Interlocked.Increment(ref counter)); // always 100000
```

### lock, Monitor and System.Threading.Lock

**In simple words:** `lock` lets only one thread at a time run a block of code. Other threads wait until it is free. The compiler turns `lock` into `Monitor.Enter` and `Monitor.Exit` inside a `try`/`finally`. .NET 9 adds a special `System.Threading.Lock` type that is faster and makes the purpose clear.

**Real-life example:** A shop has one fitting room with a lock. Only one person can use it, and the others wait outside until the door opens.

**Interview question:** Why can't you use `await` inside a `lock`?

**Simple answer:** A lock belongs to the thread that took it. After an `await`, the code may continue on a different thread that does not own the lock, so the compiler stops you (error CS1996). For async code, I use `SemaphoreSlim(1, 1)` with `WaitAsync()`. I also lock only on a private readonly object, never on `this` or a string.

```csharp
private readonly Lock _lock = new(); // .NET 9
public void Add(OrderLine l) { lock (_lock) { _lines.Add(l); } }
```

### Deadlocks

**In simple words:** A deadlock happens when two or more threads wait for each other forever, so nothing moves. A common cause is blocking on async code with `.Result` or `.Wait()` on a UI thread. Another cause is two threads taking the same two locks in the opposite order.

**Real-life example:** Two cars meet on a narrow bridge from opposite sides. Each waits for the other to reverse, so neither can move.

**Interview question:** What is a deadlock and how do you prevent it?

**Simple answer:** It is threads waiting on each other forever. I prevent it by using `await` all the way instead of `.Result` or `.Wait()`, and by always taking locks in the same order. I also avoid nested locks, or use `Monitor.TryEnter` with a timeout. In ASP.NET Core, `.Result` does not deadlock, but it causes thread-pool starvation (no free threads) under load.

### Thread safety

**In simple words:** Code is thread-safe if it works correctly when many threads call it at the same time. The best way is to share nothing, or to share only immutable data (data that never changes). If you must share data that changes, use `Interlocked`, `lock` or concurrent collections. `List<T>`, `Dictionary` and `DbContext` are not thread-safe.

**Real-life example:** A printed menu can be read by many customers at once, because nobody changes it. A single order pad needs rules, or two waiters will write over each other.

**Interview question:** What thread-safety problems are common in ASP.NET Core?

**Simple answer:** A singleton service is shared by all requests, so any changing field in it must be thread-safe, and static fields are shared too. `DbContext` is not thread-safe, so I never run two queries at once on the same context; for parallel work I use `IDbContextFactory`. I prefer immutable data and state that belongs to one request.

### SemaphoreSlim for async throttling

**In simple words:** `SemaphoreSlim` limits how many callers can be inside a block of code at the same time. Unlike `lock`, it has `WaitAsync()`, so it works with `await`. You can use it to allow, for example, only 5 calls at a time to an outside API. With a limit of 1, it works as an async lock.

**Real-life example:** A parking lot with 5 spaces has a gate. When all spaces are full, new cars wait at the gate until one car leaves.

**Interview question:** How do you limit the number of concurrent calls to an external API?

**Simple answer:** I create a `SemaphoreSlim` with the limit, for example 5. Each call does `await WaitAsync()` before it starts, and `Release()` in a `finally` block, so the slot is always given back. Then I can start many tasks with `Task.WhenAll`, and only 5 run at once.

```csharp
private static readonly SemaphoreSlim _gate = new(5);
await _gate.WaitAsync(ct);
try { return await _http.GetStringAsync(url, ct); }
finally { _gate.Release(); }
```

### Concurrent collections, Channel and BlockingCollection

**In simple words:** Concurrent collections are safe to use from many threads at once. `ConcurrentDictionary` and `ConcurrentQueue` are the common ones. `Channel<T>` is the modern way to pass items from producers to consumers in async code. `BlockingCollection<T>` is older, and it blocks threads while it waits.

**Real-life example:** A channel is like a restaurant's order rail: waiters add order tickets, and cooks take them at their own speed. When the rail is full, waiters wait.

**Interview question:** What is `Channel<T>` and when do you use it?

**Simple answer:** `Channel<T>` is an async producer–consumer queue. For example, an API writes orders into it, and a `BackgroundService` reads and processes them. A bounded channel gives back-pressure (when it is full, writers wait). It replaces `BlockingCollection`, which blocks threads.

```csharp
var channel = Channel.CreateBounded<Order>(100);
await channel.Writer.WriteAsync(order, ct);              // producer
await foreach (var o in channel.Reader.ReadAllAsync(ct)) // consumer
    await ProcessAsync(o, ct);
```

### ValueTask and IAsyncEnumerable

**In simple words:** `ValueTask<T>` is a struct version of `Task<T>`. It avoids creating a `Task` object when the result is often ready at once, like a cache hit. `IAsyncEnumerable<T>` lets you stream items one by one with `await foreach`. You do not need to load everything into memory first.

**Real-life example:** `IAsyncEnumerable` is like a sushi conveyor belt: dishes arrive one at a time, and you eat as they come. You do not wait for the whole meal at once.

**Interview question:** When should you use `ValueTask` instead of `Task`?

**Simple answer:** Only on hot paths (code that runs very often) where the result is usually ready at once, and only after measuring. A `ValueTask` must be awaited only once, never from two places, and you must not read `.Result` before it completes. By default, I return `Task<T>`.

```csharp
public ValueTask<Product?> GetAsync(int id) =>
    _cache.TryGetValue(id, out var p)
        ? new ValueTask<Product?>(p)              // no allocation
        : new ValueTask<Product?>(LoadAsync(id));
```

### Singleton

**In simple words:** The Singleton pattern makes sure only one object of a class exists in the whole app, with one shared access point. It suits shared things like configuration, a cache or a clock. In modern .NET, you usually let the DI container do this with `AddSingleton`. That is easier to test than a hand-written singleton.

**Real-life example:** A school has one principal. Every teacher goes to the same person for approval.

**Interview question:** How do you implement a thread-safe Singleton in C#?

**Simple answer:** The simplest way is a private constructor and a `static readonly Lazy<T>` field, because `Lazy<T>` is thread-safe by default. In ASP.NET Core, I prefer `AddSingleton<IClock, SystemClock>()`, which is testable through the interface. A singleton must be thread-safe, and it must not hold a scoped service like `DbContext`.

```csharp
public sealed class AppSettings
{
    private static readonly Lazy<AppSettings> _instance = new(() => new AppSettings());
    public static AppSettings Instance => _instance.Value;
    private AppSettings() { }
}
```

### Factory Method

**In simple words:** A factory creates objects for you, so the calling code does not use `new ConcreteClass()` directly. The Factory Method pattern lets a subclass or a method decide which class to create. It is useful when the type depends on data at run time, like the payment method a customer picks. In .NET 8+, keyed services can do this through DI.

**Real-life example:** At a car rental desk, you ask for "an SUV" or "a small car". The desk decides which exact car you get; you just drive it.

**Interview question:** What is the Factory pattern, and where does .NET use it?

**Simple answer:** A factory hides object creation behind a method, so callers depend on an interface, not on concrete classes. .NET uses it in `IHttpClientFactory.CreateClient` and `ILoggerFactory.CreateLogger`. If the factory's `switch` keeps growing, I move to DI-registered strategies or keyed services.

```csharp
public static IPaymentProcessor Create(string method) => method switch
{
    "card" => new CardProcessor(),
    "upi"  => new UpiProcessor(),
    _      => throw new NotSupportedException(method)
};
```

### Abstract Factory

**In simple words:** An Abstract Factory creates a whole family of related objects that belong together. You swap the entire family at once. For example, an Azure factory creates Azure blob storage and an Azure queue. A local-dev factory creates file storage and an in-memory queue. So you can never mix parts from different families.

**Real-life example:** A furniture shop sells matching sets, like a "modern" set or a "classic" set. You pick a style, and the chair, table and sofa all match.

**Interview question:** What is the difference between Factory Method and Abstract Factory?

**Simple answer:** Factory Method creates one product. Abstract Factory creates a family of related products that must work together. A .NET example is `DbProviderFactory`, which creates a matching connection, command and parameter for SQL Server or PostgreSQL. The downside is that adding a new product type means changing every factory.

### Repository

**In simple words:** A repository hides data access behind a simple interface that feels like a collection. Your business code asks for `Order` objects, and the repository talks to EF Core or SQL. This keeps query code in one place. It also lets you use a fake repository in unit tests.

**Real-life example:** At a library desk, you ask the librarian for a book by its title. You do not care which shelf or storeroom it comes from.

**Interview question:** Is the Repository pattern still needed with EF Core?

**Simple answer:** `DbSet<T>` already works like a repository, so a generic wrapper often just forwards calls. I either use `DbContext` directly in application handlers, or I write specific repositories per aggregate (a group of objects saved together) with clear methods like `GetOpenOrdersForCustomer`. I never return `IQueryable` from a repository.

### Unit of Work

**In simple words:** A Unit of Work tracks all changes in one business operation and saves them together, as one transaction. Either everything is saved, or nothing is. For example, reducing stock and inserting an order must both succeed or both fail. In EF Core, `DbContext.SaveChanges` already does this.

**Real-life example:** At a supermarket checkout, all your items go on one bill. You pay once for everything, or the whole sale is cancelled.

**Interview question:** Isn't `DbContext` already a Unit of Work?

**Simple answer:** Yes. `DbContext` tracks the changes, and `SaveChanges` writes them all in one transaction. So I avoid a generic Unit of Work wrapper that only forwards calls. I add my own `IUnitOfWork` only when the domain layer must not depend on EF Core.

### Strategy

**In simple words:** The Strategy pattern puts different algorithms behind one interface, and you choose one at run time. It replaces long `if/else` or `switch` chains. To add a new rule, you add a new class and register it. You do not edit the existing code.

**Real-life example:** A map app lets you travel by car, by bus or on foot. The destination is the same; only the way of finding the route changes.

**Interview question:** How would you design discounts that change every week?

**Simple answer:** I use the Strategy pattern. Each discount rule is a class that implements `IDiscountStrategy` and is registered in DI, and a calculator picks the rule that applies. A new promotion is a new class plus one registration line, so the core code does not change. .NET itself uses this idea with `IComparer<T>`.

```csharp
public interface IDiscountStrategy
{
    bool AppliesTo(Customer c);
    decimal Apply(decimal total);
}
builder.Services.AddSingleton<IDiscountStrategy, VipDiscount>();
```

### Observer

**In simple words:** In the Observer pattern, one object (the subject) tells many subscribers when something happens. The subject does not need to know who the subscribers are. In C#, the simplest form is an `event`. For example, when an order is placed, the email service and the inventory service both react.

**Real-life example:** A school bell rings once, and every class reacts by starting or ending a lesson. The bell does not know which classes are listening.

**Interview question:** What problems can C# events (the Observer pattern) cause?

**Simple answer:** If a subscriber forgets to unsubscribe with `-=`, the subject keeps it alive, which causes a memory leak. Handlers run one by one on the raiser's thread, and if one throws, the rest do not run. For notifications between services, I use a message broker like Service Bus or Kafka.

```csharp
public event EventHandler<OrderPlacedEventArgs>? OrderPlaced;
OrderPlaced?.Invoke(this, new OrderPlacedEventArgs(order)); // notify all
orderService.OrderPlaced += (_, e) => email.SendConfirmation(e.Order);
```

### Adapter

**In simple words:** An Adapter wraps a class that has the wrong interface and makes it look like the interface your code expects. It translates between two APIs. It is common around third-party SDKs that you cannot change. Your code uses your own clean interface, and the adapter calls the vendor's methods.

**Real-life example:** A travel plug adapter lets your phone charger fit a foreign wall socket. The charger and the socket do not change; the adapter connects them.

**Interview question:** What is the difference between Adapter and Decorator?

**Simple answer:** An Adapter changes the interface: it makes a different API fit the one my code needs. A Decorator keeps the same interface and adds behaviour, like caching or logging. A .NET example of an adapter is `StreamReader`, which turns a byte `Stream` into text you can read.

### Decorator

**In simple words:** A Decorator wraps an object that has the same interface and adds extra behaviour, like caching, logging or retry. The original class does not change, and you do not need inheritance. You can stack several decorators. The built-in .NET DI container has no `Decorate` method, so you register it by hand or use the Scrutor library.

**Real-life example:** You order a coffee, then add milk, then add sugar. It is still a coffee, but each addition gives it something extra.

**Interview question:** How would you add caching to a repository without changing it?

**Simple answer:** I write a `CachedProductRepository` that implements the same `IProductRepository` interface. It checks the cache first, and on a miss it calls the real repository it wraps. Then I register the decorator in DI, so callers get caching with no code change.

```csharp
public sealed class CachedProductRepository(IProductRepository inner, IMemoryCache cache)
    : IProductRepository
{
    public Task<Product?> GetByIdAsync(int id, CancellationToken ct) =>
        cache.GetOrCreateAsync($"product:{id}", _ => inner.GetByIdAsync(id, ct));
}
```

### Dependency Injection (brief)

**In simple words:** Dependency Injection (DI) means a class gets the objects it needs from outside, usually through its constructor. It does not create them with `new`. A DI container, like the one in ASP.NET Core, builds these objects and manages how long they live. This makes code loosely coupled and easy to test with fakes.

**Real-life example:** A restaurant chef does not grow vegetables or make knives. Suppliers deliver them, and the chef just cooks with what arrives.

**Interview question:** What is the difference between DIP, DI and IoC?

**Simple answer:** DIP (Dependency Inversion Principle) is a design rule: depend on abstractions. DI is a technique: pass dependencies in, usually through the constructor. IoC (Inversion of Control) is the wider idea that a framework or container creates objects and calls your code. DIP says what to depend on; DI and IoC are how you connect it.

```csharp
public sealed class OrderService(IOrderRepository repo, ILogger<OrderService> log) { }
builder.Services.AddScoped<IOrderRepository, OrderRepository>();
```

### Mediator

**In simple words:** A Mediator is a middle object that passes messages between parts of the app, so they do not call each other directly. In .NET, it usually means a controller sends a request object, and the mediator finds the one handler for it. The MediatR library is popular for this, and it also supports pipeline steps like validation and logging.

**Real-life example:** At an airport, pilots do not talk to each other to decide who lands first. They all talk to the control tower, which coordinates everyone.

**Interview question:** What is the Mediator pattern, and what are its downsides?

**Simple answer:** Mediator separates the sender of a request from its handler: a controller sends `GetOrderQuery`, and the mediator finds `GetOrderHandler`. The downside is extra indirection, so it is harder to see who handles what, and it is too much for simple CRUD (create, read, update, delete) apps. MediatR also moved to a commercial license in 2025, so I check the terms first.

### CQRS

**In simple words:** CQRS (Command Query Responsibility Segregation) separates writing data from reading data. Commands change data, like `PlaceOrder`, and return nothing or just an ID. Queries read data, like `GetOrderById`, and never change anything. Reads can then use simple DTOs and fast queries, while writes use the full business rules.

**Real-life example:** In a bank, one counter handles deposits and withdrawals, and another only prints statements. Each counter is set up for its own job.

**Interview question:** What is CQRS, and when should you not use it?

**Simple answer:** CQRS splits the write model (commands) from the read model (queries). It can be simple — separate handlers on the same database — or advanced, with a separate read database updated by events. I avoid the advanced form for a simple CRUD app, because it adds more pieces to build and run, and reads can lag behind writes (eventual consistency).

### Pattern map

**In simple words:** Design patterns come in groups. Creational patterns are about how objects are created (Singleton, Factory). Structural patterns are about how objects are joined (Adapter, Decorator). Behavioural patterns are about how objects talk (Strategy, Observer, Mediator). Repository, Unit of Work, DI and CQRS are architectural patterns, not from the original "Gang of Four" book.

**Real-life example:** A cookbook groups recipes into starters, main courses and desserts. The groups help you quickly find the right recipe for the moment.

**Interview question:** Which design patterns do you see in .NET itself?

**Simple answer:** Singleton appears as `AddSingleton`, Factory as `IHttpClientFactory`, and Decorator as `BufferedStream` and `DelegatingHandler`. Strategy appears as `IComparer<T>`, Observer as C# `event`s, and Chain of Responsibility as the ASP.NET Core middleware pipeline. `DbSet<T>` and `DbContext.SaveChanges` act as Repository and Unit of Work.
