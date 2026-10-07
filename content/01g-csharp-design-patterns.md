## Design Patterns

**What they are.** A design pattern is a named, proven solution to a recurring design problem — a shared vocabulary, not a library. The GoF (Gang of Four) catalogue groups them as **creational** (how objects are made), **structural** (how objects are composed) and **behavioural** (how objects interact). Repository, Unit of Work, DI and CQRS are *architectural/enterprise* patterns, not GoF — say so in the interview.

**What interviewers want.** The intent in one sentence, a small code sample, *when you would use it*, *where .NET already uses it*, and the downside. All examples below use an e-commerce domain.

### Singleton

**Definition.** Exactly one instance of a class exists for the application, with a global access point.

**Why / when.** Shared, expensive-to-create or stateless-but-global services: clock, configuration, cache, connection multiplexers (`ConnectionMultiplexer` for Redis), a shared `HttpClient`.

```csharp
// Classic: thread-safe lazy singleton (Lazy<T> is thread-safe by default)
public sealed class AppSettingsProvider
{
    private static readonly Lazy<AppSettingsProvider> _instance =
        new(() => new AppSettingsProvider());
    public static AppSettingsProvider Instance => _instance.Value;
    private AppSettingsProvider() { /* load once */ }
}

// Modern .NET: let the DI container own the lifetime
builder.Services.AddSingleton<IClock, SystemClock>();
```

| | `static` / classic Singleton | DI `AddSingleton` |
|---|---|---|
| Testability | Poor (hidden global, hard to mock) | Good (inject a fake) |
| Lifetime control | Process lifetime, you manage disposal | Container creates and disposes it |
| Coupling | Callers depend on the concrete class | Callers depend on an interface |

**.NET example.** `ILoggerFactory`, `IMemoryCache`, `IOptions<T>` are DI singletons. **Pitfalls:** mutable state must be thread-safe (all requests share it); a singleton must not capture a scoped service such as `DbContext` (captive dependency) — inject `IServiceScopeFactory` instead; avoid the double-checked-locking boilerplate, use `Lazy<T>` or a static initializer.

### Factory Method

**Definition.** Define an interface for creating an object but let a subclass/method decide *which* class to instantiate. Callers depend on the abstraction, not `new ConcreteClass()`.

**When.** The concrete type depends on runtime data (payment method, file format, tenant).

```csharp
public interface IPaymentProcessor
{ Task<bool> ChargeAsync(decimal amount, CancellationToken ct); }
public sealed class CardProcessor : IPaymentProcessor { /* ... */ }
public sealed class UpiProcessor  : IPaymentProcessor { /* ... */ }

// GoF Factory Method: subclasses override the creation step
public abstract class CheckoutHandler
{
    protected abstract IPaymentProcessor CreateProcessor();       // the factory method
    public async Task<bool> PayAsync(decimal amt, CancellationToken ct)
        => await CreateProcessor().ChargeAsync(amt, ct);
}
public sealed class CardCheckout : CheckoutHandler
{ protected override IPaymentProcessor CreateProcessor() => new CardProcessor(); }

// Pragmatic "simple factory" (what most codebases actually write)
public static IPaymentProcessor Create(string method) => method switch
{
    "card" => new CardProcessor(),
    "upi"  => new UpiProcessor(),
    _      => throw new NotSupportedException($"Unknown method '{method}'")
};

// DI-native (.NET 8+): keyed services
builder.Services.AddKeyedScoped<IPaymentProcessor, CardProcessor>("card");
builder.Services.AddKeyedScoped<IPaymentProcessor, UpiProcessor>("upi");
// public Checkout([FromKeyedServices("card")] IPaymentProcessor p) { ... }
```

**.NET example.** `IHttpClientFactory.CreateClient`, `ILoggerFactory.CreateLogger`, `Encoding.GetEncoding`, `Task.FromResult`. **Pitfall:** a growing `switch` violates Open/Closed — move to DI-registered strategies or keyed services.

### Abstract Factory

**Definition.** An interface for creating **families of related objects** without specifying their concrete classes, so the whole family can be swapped together.

```csharp
public interface IStorageFactory                       // one family = one cloud
{
    IBlobStore CreateBlobStore();
    IMessageQueue CreateQueue();
}
public sealed class AzureStorageFactory : IStorageFactory
{
    public IBlobStore CreateBlobStore() => new AzureBlobStore();
    public IMessageQueue CreateQueue()  => new ServiceBusQueue();
}
public sealed class LocalDevStorageFactory : IStorageFactory
{
    public IBlobStore CreateBlobStore() => new FileSystemBlobStore();
    public IMessageQueue CreateQueue()  => new InMemoryQueue();
}
// Compose root picks ONE factory; consumers can never mix Azure blobs with an in-memory queue.
builder.Services.AddSingleton<IStorageFactory>(env.IsDevelopment()
    ? new LocalDevStorageFactory() : new AzureStorageFactory());
```

**Factory Method vs Abstract Factory:** one product vs a family of compatible products. **.NET example.** `DbProviderFactory` (`CreateConnection`, `CreateCommand`, `CreateParameter` for SQL Server, Npgsql, SQLite). **Pitfall:** adding a new product type to the family means changing every factory.

### Repository

**Definition.** A collection-like abstraction over data access: the domain asks for `Order` objects, the repository hides EF Core/SQL.

```csharp
public interface IOrderRepository
{
    Task<Order?> GetByIdAsync(int id, CancellationToken ct);
    Task<IReadOnlyList<Order>> GetByCustomerAsync(int customerId, CancellationToken ct);
    Task AddAsync(Order order, CancellationToken ct);
}
public sealed class OrderRepository(AppDbContext db) : IOrderRepository
{
    public Task<Order?> GetByIdAsync(int id, CancellationToken ct) =>
        db.Orders.Include(o => o.Lines).FirstOrDefaultAsync(o => o.Id == id, ct);
    public async Task<IReadOnlyList<Order>> GetByCustomerAsync(int cid, CancellationToken ct) =>
        await db.Orders.AsNoTracking().Where(o => o.CustomerId == cid).ToListAsync(ct);
    public async Task AddAsync(Order order, CancellationToken ct) =>
        await db.Orders.AddAsync(order, ct);        // no SaveChanges here: that is Unit of Work
}
```

**Why.** Unit-testing business logic with a fake repository; one place for query logic; swap data stores. **Pitfalls:** a *generic* `IRepository<T>` with `GetAll()` returning `IQueryable<T>` leaks EF into every caller and adds nothing over `DbSet<T>`. Prefer **one repository per aggregate root** with intent-revealing methods (`GetOpenOrdersForCustomer`).

### Unit of Work

**Definition.** Tracks all changes made during a business transaction and commits them **together** (or not at all).

```csharp
public interface IUnitOfWork
{
    IOrderRepository Orders { get; }
    IProductRepository Products { get; }
    Task<int> SaveChangesAsync(CancellationToken ct);
}
public sealed class UnitOfWork(AppDbContext db, IOrderRepository o, IProductRepository p)
    : IUnitOfWork
{
    public IOrderRepository Orders => o;
    public IProductRepository Products => p;
    public Task<int> SaveChangesAsync(CancellationToken ct) => db.SaveChangesAsync(ct);
}

// Place order: reduce stock + insert order = ONE database transaction
var product = await uow.Products.GetByIdAsync(id, ct);
product!.Reserve(qty);
await uow.Orders.AddAsync(Order.Create(customerId, product, qty), ct);
await uow.SaveChangesAsync(ct);                        // single atomic commit
```

**The debate: "DbContext already *is* a Unit of Work and a Repository."** `DbSet<T>` behaves like a repository and `DbContext.SaveChanges` is the unit of work (change tracker + one transaction). Wrapping it in another generic repository + UoW often just forwards calls.

| Position | Argument |
|---|---|
| Use `DbContext` directly (in handlers/services) | Less code, full LINQ/`Include`/projections, EF is already the abstraction; test with SQLite/Testcontainers |
| Wrap with Repository/UoW | Hide EF from the domain layer, mock in unit tests, central query rules, swap persistence |

My answer: *no generic repository wrapper over EF*; either use `DbContext` directly from application-layer handlers, or write **specific** aggregate repositories when the domain layer must stay persistence-ignorant. **.NET example.** `DbContext.SaveChanges`, `TransactionScope`, ADO.NET `SqlTransaction`.

### Strategy

**Definition.** Define a family of interchangeable algorithms behind an interface and pick one at runtime — replaces `if/else` or `switch` chains.

```csharp
public interface IDiscountStrategy
{
    bool AppliesTo(Customer c);
    decimal Apply(decimal total);
}
public sealed class VipDiscount : IDiscountStrategy
{
    public bool AppliesTo(Customer c) => c.IsVip;
    public decimal Apply(decimal total) => total * 0.90m;
}
public sealed class FirstOrderDiscount : IDiscountStrategy
{
    public bool AppliesTo(Customer c) => c.OrderCount == 0;
    public decimal Apply(decimal total) => total - 5m;
}

public sealed class PriceCalculator(IEnumerable<IDiscountStrategy> strategies)
{
    public decimal Calculate(Customer c, decimal total) =>
        strategies.FirstOrDefault(s => s.AppliesTo(c))?.Apply(total) ?? total;
}
builder.Services.AddSingleton<IDiscountStrategy, VipDiscount>();
builder.Services.AddSingleton<IDiscountStrategy, FirstOrderDiscount>(); // no edits elsewhere
```

**.NET example.** `IComparer<T>` / `IEqualityComparer<T>` passed to `Sort`/`Dictionary`, `IPasswordHasher<T>`, ASP.NET Core authentication handlers, EF Core `ValueConverter`. **Why:** Open/Closed — add a new strategy class, change nothing else. **Pitfall:** overkill for two stable branches; a `switch` is fine there.

### Observer

**Definition.** A subject notifies a list of subscribers when its state changes, without knowing who they are (publish/subscribe in-process).

```csharp
public sealed record OrderPlacedEventArgs(Order Order);

public sealed class OrderService
{
    public event EventHandler<OrderPlacedEventArgs>? OrderPlaced;     // the subject

    public async Task PlaceAsync(Order order)
    {
        await SaveAsync(order);
        OrderPlaced?.Invoke(this, new OrderPlacedEventArgs(order));   // notify all
    }
}
// Subscribers
orderService.OrderPlaced += (_, e) => email.SendConfirmation(e.Order);
orderService.OrderPlaced += (_, e) => inventory.Reserve(e.Order);
orderService.OrderPlaced -= handler;      // ALWAYS unsubscribe long-lived subjects
```

**Push-based alternative:** `IObservable<T>` / `IObserver<T>` (built into the BCL, rich operators in Reactive Extensions): `subject.Subscribe(order => ...)` returns an `IDisposable` to unsubscribe.

**.NET example.** C# `event`s, `INotifyPropertyChanged` (WPF/MAUI binding), `IObservable<T>`, `IOptionsMonitor<T>.OnChange`, `FileSystemWatcher`, change tokens. For *cross-service* notification use a message broker (Service Bus, Kafka) — same idea, distributed. **Pitfalls:** forgotten `-=` keeps subscribers alive (memory leak); one handler throwing stops the rest; handlers run synchronously on the raiser's thread; `async void` handlers lose exceptions.

### Adapter

**Definition.** Wraps an incompatible class so it exposes the interface your code expects — a translator between two APIs.

```csharp
public interface ISmsSender { Task SendAsync(string phone, string text, CancellationToken ct); }

// Third-party SDK we cannot change
public class LegacyGatewayClient
{
    public int Dispatch(string[] recipients, string payload, bool unicode)
    { /* ... */ return 0; }
}

public sealed class LegacyGatewayAdapter(LegacyGatewayClient client) : ISmsSender
{
    public Task SendAsync(string phone, string text, CancellationToken ct)
    {
        var code = client.Dispatch([phone], text, unicode: true);
        return code == 0 ? Task.CompletedTask
                         : throw new InvalidOperationException($"Gateway error {code}");
    }
}
```

**.NET example.** `StreamReader`/`StreamWriter` adapt a byte `Stream` to text; `Serilog.Extensions.Logging` adapts Serilog to `ILogger<T>`. In architecture terms this is the **anti-corruption layer** around an external system. **Pitfall:** don't let the vendor's types leak past the adapter.

### Decorator

**Definition.** Wrap an object that implements the same interface to add behaviour (caching, logging, retry, metrics) without modifying it or subclassing.

```csharp
public interface IProductRepository
{ Task<Product?> GetByIdAsync(int id, CancellationToken ct); }

public sealed class CachedProductRepository(IProductRepository inner, IMemoryCache cache)
    : IProductRepository
{
    public async Task<Product?> GetByIdAsync(int id, CancellationToken ct) =>
        await cache.GetOrCreateAsync($"product:{id}", e =>
        {
            e.AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(5);
            return inner.GetByIdAsync(id, ct);              // delegate to the real one
        });
}

// DI wiring without libraries
builder.Services.AddScoped<ProductRepository>();
builder.Services.AddScoped<IProductRepository>(sp => new CachedProductRepository(
    sp.GetRequiredService<ProductRepository>(), sp.GetRequiredService<IMemoryCache>()));

// With Scrutor (NuGet): one line, and decorators stack
builder.Services.AddScoped<IProductRepository, ProductRepository>();
builder.Services.Decorate<IProductRepository, CachedProductRepository>();
```

**.NET example.** `GZipStream`/`BufferedStream`/`CryptoStream` wrap any `Stream`; `DelegatingHandler` in the `HttpClient` pipeline. **Adapter vs Decorator:** an adapter *changes* the interface; a decorator *keeps* it and adds behaviour. **Pitfall:** the built-in container has no `Decorate` — use manual factory registration or Scrutor.

### Dependency Injection (brief)

**Definition.** A class receives its collaborators from outside (usually via the constructor) instead of creating them with `new`. *IoC* is the principle, *DI* is the technique, a *container* automates it. The full treatment (lifetimes, captive dependencies, keyed services) is in the dedicated DI section.

```csharp
public sealed class OrderService(
    IOrderRepository repo, IPaymentProcessor pay, ILogger<OrderService> log) { }

builder.Services.AddScoped<IOrderRepository, OrderRepository>();   // per request
builder.Services.AddTransient<IPaymentProcessor, CardProcessor>();  // new each time
builder.Services.AddSingleton<IClock, SystemClock>();               // one for the app
```

**Why it matters.** Loose coupling, testability (inject fakes), and central lifetime management. It is the enabler for Strategy, Decorator and Factory in modern .NET. **Pitfalls:** service locator (`GetService` all over), captive dependencies, constructors with 8+ parameters (a design smell).

### Mediator

**Definition.** An object that centralises communication between components so they talk to the mediator, not to each other. In .NET apps it usually means an **in-process request dispatcher**: controller sends a request object; the mediator finds the one handler.

```csharp
public interface IRequest<TResponse> { }
public interface IRequestHandler<TRequest, TResponse> where TRequest : IRequest<TResponse>
{ Task<TResponse> Handle(TRequest request, CancellationToken ct); }

public interface IMediator
{
    Task<TResponse> Send<TResponse>(
        IRequest<TResponse> request, CancellationToken ct = default);
}

public sealed class Mediator(IServiceProvider sp) : IMediator
{
    public Task<TResponse> Send<TResponse>(
        IRequest<TResponse> request, CancellationToken ct = default)
    {
        var handlerType = typeof(IRequestHandler<,>)
            .MakeGenericType(request.GetType(), typeof(TResponse));
        dynamic handler = sp.GetRequiredService(handlerType);   // dynamic keeps it short
        return handler.Handle((dynamic)request, ct);
    }
}

public sealed record GetOrderQuery(int Id) : IRequest<OrderDto?>;
public sealed class GetOrderHandler(AppDbContext db) : IRequestHandler<GetOrderQuery, OrderDto?>
{
    public Task<OrderDto?> Handle(GetOrderQuery q, CancellationToken ct) =>
        db.Orders.AsNoTracking().Where(o => o.Id == q.Id)
          .Select(o => new OrderDto(o.Id, o.Total)).FirstOrDefaultAsync(ct);
}
// registration:
//   services.AddScoped<IRequestHandler<GetOrderQuery, OrderDto?>, GetOrderHandler>();
// endpoint:
//   app.MapGet("/orders/{id}", (int id, IMediator m, CancellationToken ct)
//       => m.Send(new GetOrderQuery(id), ct));
```

**MediatR.** The popular library adds pipeline behaviours (validation, logging, transactions), notifications (one-to-many) and assembly-scanning registration. **Licensing:** in 2025 MediatR (and AutoMapper) moved from Apache-2.0 to a commercial/dual-license model with a free community tier for small organisations — check current terms before adopting it in a commercial product. Alternatives: a hand-rolled mediator like above, source-generator based libraries (e.g. `Mediator`), or plain handler classes injected directly.

**Pitfalls:** indirection hides the call flow ("who handles this?"), and it is overkill for simple CRUD where a service class is clearer.

### CQRS

**Definition.** *Command Query Responsibility Segregation*: separate the model that **changes** state (commands) from the model that **reads** state (queries). A command returns nothing (or an id); a query returns data and changes nothing.

| | Command | Query |
|---|---|---|
| Intent | Do something (`PlaceOrder`) | Ask something (`GetOrderById`) |
| Side effects | Yes | None |
| Model | Rich domain/entities, validation, transactions | Flat DTOs, `AsNoTracking`/Dapper projections |
| Returns | Id / `Result` | Data |

```csharp
public sealed record PlaceOrderCommand(int CustomerId, List<OrderLineDto> Lines)
    : IRequest<int>;

public sealed class PlaceOrderHandler(AppDbContext db) : IRequestHandler<PlaceOrderCommand, int>
{
    public async Task<int> Handle(PlaceOrderCommand cmd, CancellationToken ct)
    {
        var order = Order.Create(cmd.CustomerId, cmd.Lines);       // domain rules inside
        db.Orders.Add(order);
        await db.SaveChangesAsync(ct);
        return order.Id;
    }
}

public sealed record GetOrderSummariesQuery(int CustomerId)
    : IRequest<IReadOnlyList<OrderSummary>>;
// Handler reads with Dapper or EF projection -> no tracking, no domain objects
```

**Three levels, adopt the smallest that works:**

1. Same database and model, but commands and queries are separate handlers (most projects stop here).
2. Same database, **separate read model** (views, Dapper queries, denormalised tables) for fast reads.
3. Separate read store (read replica, Elasticsearch, Redis) updated from events published by the command side — **eventual consistency**; often combined with Event Sourcing.

**Pitfalls:** extra moving parts and read-after-write lag at level 3; do not introduce it for a CRUD app. Commands and queries pair naturally with the mediator pipeline (validation, logging, transaction behaviours).

:::scenario "How would you design discounts that change every week?"
Hard-coded `if (customer.IsVip) ... else if (promo == "DIWALI")` in `OrderService` means every promotion edits and redeploys core code. Use **Strategy**: each rule is an `IDiscountStrategy` registered in DI; the calculator picks the applicable ones. Add **Decorator** for cross-cutting concerns (log every applied discount). New promo = new class + one `AddSingleton` line, nothing else changes. If rules come from the database, load them into a strategy list per request instead.
:::

### Pattern map

| Pattern | Category | Where you see it in .NET |
|---|---|---|
| Singleton | Creational | `AddSingleton<T>()`, `Lazy<T>`, `ILoggerFactory` |
| Factory Method | Creational | `IHttpClientFactory.CreateClient`, `ILoggerFactory.CreateLogger`, `Encoding.GetEncoding` |
| Abstract Factory | Creational | `DbProviderFactory` (connection + command + parameter family) |
| Builder (bonus) | Creational | `WebApplication.CreateBuilder`, `StringBuilder`, `HostBuilder` |
| Adapter | Structural | `StreamReader` over `Stream`, `Serilog.Extensions.Logging` |
| Decorator | Structural | `GZipStream`/`BufferedStream`, `DelegatingHandler`, Scrutor `Decorate` |
| Strategy | Behavioural | `IComparer<T>`, `IEqualityComparer<T>`, `IPasswordHasher<T>` |
| Observer | Behavioural | `event`, `IObservable<T>`, `INotifyPropertyChanged`, `IOptionsMonitor.OnChange` |
| Mediator | Behavioural | MediatR-style dispatcher, in-process handler pipeline |
| Chain of Responsibility (bonus) | Behavioural | ASP.NET Core middleware pipeline, `DelegatingHandler` chain |
| Repository, Unit of Work | Enterprise (PoEAA/DDD) | `DbSet<T>` and `DbContext.SaveChanges` |
| Dependency Injection | Architectural | `Microsoft.Extensions.DependencyInjection` |
| CQRS | Architectural | Command/query handlers, separate read models |

## Quick-fire Q&A: LINQ, Exceptions, Async & Patterns

:::q What is deferred execution in LINQ?
A query like `Where`/`Select` only describes the work; it runs when you enumerate it (`foreach`, `ToList`, `Count`, `First`). Each enumeration re-runs the query, so changes to the source after definition are visible, and re-enumerating a database query hits the DB again. Materialise with `ToList()` when you need a snapshot.
:::

:::q First vs Single vs FirstOrDefault vs SingleOrDefault?
`First` throws if empty and returns the first match otherwise. `FirstOrDefault` returns `default` if empty. `Single` throws if there are zero *or* more than one matches; `SingleOrDefault` returns `default` for zero but still throws for more than one. Use `Single*` when uniqueness is a rule you want enforced.
:::

:::q IEnumerable vs IQueryable?
`IEnumerable<T>` runs delegates in memory; `IQueryable<T>` captures expression trees that EF Core translates to SQL so filtering, sorting and paging happen in the database. Calling `ToList()` or `AsEnumerable()` too early drags the whole table into memory and moves the rest of the query client-side.
:::

:::q Why use Any() instead of Count() > 0?
`Any()` stops at the first element and becomes `EXISTS` in SQL; `Count()` may scan everything and becomes `COUNT(*)`. For a `List<T>` use the `Count` property, which is O(1).
:::

:::q throw vs throw ex?
`throw;` preserves the original stack trace; `throw ex;` resets it to the current line and hides the root cause. Wrap with `new XException("...", ex)` if you need to add context.
:::

:::q How do you handle exceptions globally in ASP.NET Core?
Implement `IExceptionHandler` (.NET 8+), register it with `AddExceptionHandler<T>()`, add `AddProblemDetails()` and call `UseExceptionHandler()` early in the pipeline. Map exception types to status codes, log once with structured `ILogger`, and return RFC 7807/9457 `ProblemDetails` without leaking stack traces. On older versions use custom middleware wrapping `next(ctx)` in try/catch.
:::

:::q What goes wrong with catch (Exception) { }?
It swallows errors: no log, no retry, the caller continues with bad state. Catch only exceptions you can handle, log or rethrow the rest, and let a global handler produce the response.
:::

:::q Task vs Thread, and what does await do?
A `Thread` is an OS worker; a `Task` is a unit of work or promise that is scheduled on the thread pool and supports results, exceptions and cancellation. `await` registers a continuation and returns the thread to the pool; the state machine resumes later, possibly on another thread. No thread is blocked during async I/O.
:::

:::q Why is .Result / .Wait() dangerous?
On a thread with a `SynchronizationContext` (UI, legacy ASP.NET) it can deadlock because the continuation needs the thread you blocked. In ASP.NET Core it blocks pool threads and causes thread-pool starvation under load. Use `await` and go async all the way.
:::

:::q Task.WhenAll vs sequential awaits, and what about exceptions?
`WhenAll` runs independent operations concurrently so total time is the slowest, not the sum. `await` rethrows only the first exception; the others are on the `WhenAll` task's `Exception.InnerExceptions`. Throttle large fan-outs with `SemaphoreSlim` or `Parallel.ForEachAsync`.
:::

:::q How do you fix a race condition?
Remove shared mutable state if possible; otherwise make the operation atomic: `Interlocked` for a counter, `lock` (or `System.Threading.Lock` in .NET 9) for a critical section, `SemaphoreSlim` in async code, `ConcurrentDictionary` for shared maps. For cross-process races such as stock levels use database concurrency (rowversion or an atomic conditional `UPDATE`).
:::

:::q Why can't you await inside a lock?
`lock` is thread-affine, and after an `await` the code may resume on a different thread that does not own the lock; the compiler rejects it (CS1996). Use `SemaphoreSlim(1,1)` with `WaitAsync()` for async mutual exclusion.
:::

:::q Singleton vs static class, and the DI singleton?
A static class cannot implement interfaces, be injected or mocked and carries hidden global state. A DI singleton gives one shared instance with the same lifetime benefit but is testable and replaceable. It must be thread-safe and must not depend on scoped services.
:::

:::q Is the Repository pattern still needed with EF Core?
`DbContext` is already a unit of work and `DbSet<T>` is already a repository, so a generic wrapper just forwards calls. I either use `DbContext` directly from application handlers, or write specific aggregate repositories when the domain layer must not reference EF. Never expose `IQueryable` from a repository.
:::

:::q Strategy vs Decorator vs Adapter?
Strategy swaps an algorithm behind an interface (choose one). Decorator wraps the same interface to add behaviour such as caching or logging (stack many). Adapter wraps a *different* interface to make it fit the one you need. Mediator and CQRS are separate ideas: Mediator decouples senders from handlers; CQRS separates the write model from the read model.
:::
