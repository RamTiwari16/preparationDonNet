## Dependency Injection Fundamentals

### What is Dependency Injection? (IoC vs DI vs DIP)

**Definition.** *Dependency Injection (DI)* is a technique where an object **receives** the objects it depends on (its *dependencies*) from the outside, instead of creating them itself with `new`. A **DI container** (in .NET: `IServiceCollection` + `IServiceProvider`) builds the object graph and manages lifetimes.

Three terms that interviewers expect you to separate cleanly:

| Term | What it is | Level | One-liner |
|---|---|---|---|
| **DIP** (Dependency Inversion Principle) | The "D" in SOLID. High-level modules should not depend on low-level modules; **both depend on abstractions** | Design *principle* | "Depend on `IPaymentGateway`, not on `StripeClient`." |
| **IoC** (Inversion of Control) | The framework calls your code and controls object creation and flow, not the other way round ("Hollywood principle: don't call us, we'll call you") | Broad *concept* | ASP.NET Core creates your controllers and calls your actions |
| **DI** (Dependency Injection) | One concrete way to achieve IoC for dependencies: pass them in (constructor/property/method) | *Technique/pattern* | `public OrderService(IPaymentGateway gw)` |
| **DI container** | Library that automates DI: registrations + lifetimes + resolution | *Tool* | `builder.Services.AddScoped<IOrderService, OrderService>()` |

```text
DIP  (principle: depend on abstractions)
  realised by
IoC  (concept: someone else controls creation/flow)
  implemented with
DI   (pattern: dependencies are passed in)
  automated by
Container (Microsoft.Extensions.DependencyInjection, Autofac, ...)
```

:::tip Say this
"DIP is the principle, IoC is the broader idea that the framework controls creation, DI is the pattern that implements it by passing dependencies in, and the container is the tool that automates it. You can do DI without a container by passing dependencies manually; that is called *pure DI*."
:::

### Why DI? Before and after

**Why it matters.** DI gives **loose coupling** (swap implementations without touching consumers), **testability** (replace real dependencies with fakes), **centralised lifetime management** (the container creates, shares and disposes objects correctly), and **single place for configuration** (the composition root, `Program.cs`).

```csharp
// BEFORE: tightly coupled. OrderService decides WHICH implementations it uses.
public class OrderService
{
    private readonly SqlOrderRepository _repo = new("Server=prod;Database=Shop;...");
    private readonly SmtpEmailSender _email = new("smtp.company.com", 587);

    public async Task PlaceOrderAsync(Order order)
    {
        if (order.Lines.Count == 0) throw new InvalidOperationException("Empty order");
        await _repo.AddAsync(order);                       // hits a REAL database
        await _email.SendAsync(order.CustomerEmail,        // sends a REAL email
            "Order confirmed", $"Order {order.Id} placed");
    }
}
// Problems: cannot unit test without SQL + SMTP; connection string hard-coded;
// switching to SendGrid means editing OrderService; who disposes SqlConnection?
```

```csharp
// AFTER: depend on abstractions, receive them via the constructor.
public interface IOrderRepository { Task AddAsync(Order order, CancellationToken ct = default); }
public interface IEmailSender { Task SendAsync(string to, string subject, string body); }

public class OrderService(IOrderRepository repo, IEmailSender email)
{
    public async Task PlaceOrderAsync(Order order, CancellationToken ct = default)
    {
        if (order.Lines.Count == 0) throw new InvalidOperationException("Empty order");
        await repo.AddAsync(order, ct);
        await email.SendAsync(order.CustomerEmail, "Order confirmed", $"Order {order.Id} placed");
    }
}

// Composition root (Program.cs) is the ONLY place that knows the concrete types
builder.Services.AddScoped<IOrderRepository, EfOrderRepository>();
builder.Services.AddSingleton<IEmailSender, SendGridEmailSender>();
builder.Services.AddScoped<OrderService>();
```

```csharp
// Unit test with hand-written fakes (xUnit). No database, no SMTP, runs in milliseconds.
public class FakeOrderRepository : IOrderRepository
{
    public List<Order> Saved { get; } = [];
    public Task AddAsync(Order order, CancellationToken ct = default)
    { Saved.Add(order); return Task.CompletedTask; }
}

public class FakeEmailSender : IEmailSender
{
    public List<(string To, string Subject)> Sent { get; } = [];
    public Task SendAsync(string to, string subject, string body)
    { Sent.Add((to, subject)); return Task.CompletedTask; }
}

public class OrderServiceTests
{
    [Fact]
    public async Task PlaceOrder_saves_order_and_sends_confirmation()
    {
        var repo = new FakeOrderRepository();
        var email = new FakeEmailSender();
        var sut = new OrderService(repo, email);
        var order = new Order { Id = 42, CustomerEmail = "ana@example.com",
                                Lines = [new OrderLine { ProductId = 1, Quantity = 2 }] };

        await sut.PlaceOrderAsync(order);

        Assert.Single(repo.Saved);
        Assert.Equal(("ana@example.com", "Order confirmed"), email.Sent.Single());
    }

    [Fact]
    public async Task PlaceOrder_with_no_lines_throws_and_sends_nothing()
    {
        var email = new FakeEmailSender();
        var sut = new OrderService(new FakeOrderRepository(), email);

        await Assert.ThrowsAsync<InvalidOperationException>(
            () => sut.PlaceOrderAsync(new Order { CustomerEmail = "x@y.z" }));
        Assert.Empty(email.Sent);
    }
}
// With a mocking library instead of fakes (Moq):
// var email = new Mock<IEmailSender>();
// email.Verify(e => e.SendAsync("ana@example.com", "Order confirmed", It.IsAny<string>()), Times.Once);
```

:::example Real-world payoff
The payment provider changes from Stripe to Adyen. Only a new `AdyenGateway : IPaymentGateway` class and one registration line change. `CheckoutService`, its tests, and the controllers are untouched. During the transition you can even register both as keyed services and choose per country.
:::

### Constructor, property, and method injection

| Type | How | Use when | Built-in container |
|---|---|---|---|
| **Constructor injection** | Dependencies are constructor parameters | **Required** dependencies (the default, 95% of cases) | **Yes** |
| **Property (setter) injection** | Container sets a public property after construction | Optional dependencies with a sensible default | **No** (needs Autofac etc.) |
| **Method injection** | Dependency passed as a parameter to the method that needs it | Dependency varies per call, or is only needed by one method | Yes in specific places: action parameters `[FromServices]`, minimal API handler parameters, middleware `InvokeAsync` parameters |

```csharp
// 1) Constructor injection (C# 12 primary constructor). Dependencies are explicit and required.
public class CheckoutService(IPaymentGateway payments, IOrderRepository orders,
                             ILogger<CheckoutService> log)
{
    public async Task CheckoutAsync(Order o, CancellationToken ct)
    {
        await payments.ChargeAsync(o.Total, ct);
        await orders.AddAsync(o, ct);
        log.LogInformation("Order {Id} checked out", o.Id);
    }
}

// 2) Property injection (manual / Autofac PropertiesAutowired). Optional dependency.
public class ReportGenerator
{
    public ILogger Logger { get; set; } = NullLogger.Instance;   // safe default
}

// 3) Method injection: the dependency is specific to this call
public class PriceCalculator
{
    public decimal Calculate(Order order, IDiscountPolicy policy) =>  // policy varies per call
        order.Lines.Sum(l => l.UnitPrice * l.Quantity) - policy.DiscountFor(order);
}

// Framework-supported "method injection" points
[HttpGet("report")]
public IActionResult Report([FromServices] IReportService reports) => Ok(reports.Build());

app.MapGet("/stats", (IStatsService stats) => stats.Get());     // inferred from DI

public class TenantMiddleware(RequestDelegate next)
{
    public Task InvokeAsync(HttpContext ctx, ITenantStore store) => next(ctx);   // per request
}
```

**Why does the built-in container only do constructor injection?** It is deliberately minimal. Constructor injection makes dependencies **explicit**, **required**, and **immutable**: the object can never exist in a half-initialised state, and missing registrations fail at resolution (or at build time with `ValidateOnBuild`). Property injection hides dependencies and allows `null` surprises.

**Constructor selection rules.** If a class has several public constructors, the container picks the one with the **most parameters it can resolve**. If two are equally good it throws an ambiguity exception. `[ActivatorUtilitiesConstructor]` marks the preferred one for `ActivatorUtilities`.

:::warn Primary constructor gotcha
Primary constructor parameters are captured as mutable hidden fields; you could accidentally reassign `payments = null` inside a method. If that matters, assign to a `private readonly` field: `private readonly IPaymentGateway _payments = payments;`.
:::

### How the container works

```text
Startup:  IServiceCollection  = list of ServiceDescriptor { ServiceType, ImplementationType |
                                 Factory | Instance, Lifetime }
Build():  IServiceProvider (root)  <- singletons live here
Request:  ASP.NET Core creates a scope per request
          HttpContext.RequestServices = scope.ServiceProvider  <- scoped instances live here
          Controller resolved from the scope -> constructor params resolved recursively
End:      scope disposed -> scoped + transient IDisposables created in it are disposed
```

```csharp
// Resolution APIs
var svc  = provider.GetService<IOrderService>();          // null if not registered
var svc2 = provider.GetRequiredService<IOrderService>();  // throws if not registered (prefer)
var all  = provider.GetServices<INotificationChannel>();  // every registration

using var scope = app.Services.CreateScope();              // manual scope (scripts, startup jobs)
var db = scope.ServiceProvider.GetRequiredService<ShopDbContext>();
```

### Service registration APIs

#### AddSingleton, AddScoped, AddTransient (all overloads)

```csharp
// Interface -> implementation (most common)
builder.Services.AddScoped<IOrderService, OrderService>();

// Concrete type only
builder.Services.AddTransient<PriceCalculator>();

// Existing instance (singleton only). NOT disposed by the container.
builder.Services.AddSingleton<IClock>(new SystemClock());

// Factory: full control, access to other services and config
builder.Services.AddScoped<IPaymentGateway>(sp =>
{
    var opts = sp.GetRequiredService<IOptions<PaymentOptions>>().Value;
    return opts.Provider == "Stripe"
        ? sp.GetRequiredService<StripeGateway>()
        : sp.GetRequiredService<AdyenGateway>();
});
builder.Services.AddScoped<StripeGateway>();
builder.Services.AddScoped<AdyenGateway>();

// One instance behind two interfaces ("forwarding")
builder.Services.AddSingleton<InMemoryCatalogCache>();
builder.Services.AddSingleton<ICatalogReader>(sp => sp.GetRequiredService<InMemoryCatalogCache>());
builder.Services.AddSingleton<ICatalogWriter>(sp => sp.GetRequiredService<InMemoryCatalogCache>());
// Registering AddSingleton<ICatalogReader, InMemoryCatalogCache>() twice would create TWO caches.
```

#### TryAdd, Replace, RemoveAll

```csharp
using Microsoft.Extensions.DependencyInjection.Extensions;

// TryAdd: register only if nothing is registered yet for that service type.
// Library authors use it so the app can override their defaults.
builder.Services.TryAddSingleton<IClock, SystemClock>();

// TryAddEnumerable: add to a multi-registration list, but not the same implementation twice
builder.Services.TryAddEnumerable(
    ServiceDescriptor.Scoped<INotificationChannel, EmailChannel>());

// Replace: swap an existing registration (great in tests)
builder.Services.Replace(ServiceDescriptor.Singleton<IClock, FixedClock>());

// RemoveAll: drop every registration of a type
builder.Services.RemoveAll<IEmailSender>();
```

#### Multiple implementations and IEnumerable<T>

```csharp
builder.Services.AddScoped<INotificationChannel, EmailChannel>();
builder.Services.AddScoped<INotificationChannel, SmsChannel>();
builder.Services.AddScoped<INotificationChannel, PushChannel>();

public class OrderNotifier(IEnumerable<INotificationChannel> channels)   // all three, in order
{
    public Task NotifyAsync(Order o) =>
        Task.WhenAll(channels.Select(c => c.SendAsync(o)));
}

public class Other(INotificationChannel channel) { }   // gets the LAST registered: PushChannel
```

#### Keyed services (.NET 8)

```csharp
builder.Services.AddKeyedScoped<IPaymentGateway, StripeGateway>("card");
builder.Services.AddKeyedScoped<IPaymentGateway, PayPalGateway>("paypal");

// Inject a specific one
public class RefundService([FromKeyedServices("card")] IPaymentGateway gateway) { }

// Choose at runtime by key
public class CheckoutService(IServiceProvider sp)
{
    public Task PayAsync(string method, decimal amount) =>
        sp.GetRequiredKeyedService<IPaymentGateway>(method).ChargeAsync(amount);
}
```

Keyed services replace the old "factory + dictionary" or "named registration" workarounds. (The runtime-key example uses `IServiceProvider`; keep that confined to a small factory class, see the Service Locator topic.)

#### Open generics

```csharp
public interface IRepository<T> where T : class
{
    Task<T?> GetAsync(int id, CancellationToken ct);
    void Add(T entity);
}
public class EfRepository<T>(ShopDbContext db) : IRepository<T> where T : class
{
    public Task<T?> GetAsync(int id, CancellationToken ct) => db.Set<T>().FindAsync([id], ct).AsTask();
    public void Add(T entity) => db.Set<T>().Add(entity);
}

// One line registers IRepository<Order>, IRepository<Product>, ...
builder.Services.AddScoped(typeof(IRepository<>), typeof(EfRepository<>));
```

#### Decoration (adding behaviour without changing the class)

```csharp
// Manual decorator: cache in front of the SQL repository
public class CachedProductRepository(IProductRepository inner, IMemoryCache cache)
    : IProductRepository
{
    public Task<Product?> GetAsync(int id, CancellationToken ct) =>
        cache.GetOrCreateAsync($"product:{id}", e =>
        {
            e.AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(5);
            return inner.GetAsync(id, ct);
        });
}

builder.Services.AddScoped<SqlProductRepository>();
builder.Services.AddScoped<IProductRepository>(sp => new CachedProductRepository(
    sp.GetRequiredService<SqlProductRepository>(),
    sp.GetRequiredService<IMemoryCache>()));

// With Scrutor: one line
// builder.Services.AddScoped<IProductRepository, SqlProductRepository>();
// builder.Services.Decorate<IProductRepository, CachedProductRepository>();
```

#### Grouping registrations: extension methods

```csharp
public static class OrderingModule
{
    public static IServiceCollection AddOrdering(this IServiceCollection services, IConfiguration cfg)
    {
        services.AddScoped<IOrderService, OrderService>();
        services.AddScoped<IOrderRepository, EfOrderRepository>();
        services.AddOptions<OrderingOptions>().Bind(cfg.GetSection("Ordering")).ValidateOnStart();
        return services;
    }
}
builder.Services.AddOrdering(builder.Configuration);
```

### Service lifetimes: Singleton, Scoped, Transient

| | **Singleton** | **Scoped** | **Transient** |
|---|---|---|---|
| Instances | One for the whole app | One per scope (per HTTP request) | New one on **every** resolve |
| Created | First request for it (or at registration if an instance is given) | First resolve inside the scope | Every resolve |
| Disposed | App shutdown | End of the scope/request | End of the scope that resolved it |
| Thread safety needed? | **Yes**, shared by all concurrent requests | No, one request (unless you parallelise) | No |
| Can depend on | Singletons only | Singletons + scoped | Anything (but inherits the shortest lifetime of its consumer) |
| Typical | Config, caches, `IHttpClientFactory`, `TimeProvider`, `ILogger<T>` | **`DbContext`**, unit of work, repositories, current user/tenant | Lightweight stateless helpers, validators, mappers |
| Register | `AddSingleton` | `AddScoped` | `AddTransient` |

**Lifetime rule.** A service must not depend on a service with a **shorter** lifetime. Singleton -> scoped is the classic bug (captive dependency).

| Consumer \ Dependency | Singleton | Scoped | Transient |
|---|---|---|---|
| **Singleton** | OK | **Captive (bug)** | Captive (becomes singleton) |
| **Scoped** | OK | OK | OK |
| **Transient** | OK | OK (within scope) | OK |

#### Lifetime demo: Guid per request

```csharp
public interface IOperation { Guid Id { get; } }
public interface ITransientOperation : IOperation { }
public interface IScopedOperation : IOperation { }
public interface ISingletonOperation : IOperation { }

public class Operation : ITransientOperation, IScopedOperation, ISingletonOperation
{
    public Guid Id { get; } = Guid.NewGuid();
}

builder.Services.AddTransient<ITransientOperation, Operation>();
builder.Services.AddScoped<IScopedOperation, Operation>();
builder.Services.AddSingleton<ISingletonOperation, Operation>();
builder.Services.AddScoped<OperationReporter>();

// A second consumer in the same request
public class OperationReporter(
    ITransientOperation transient, IScopedOperation scoped, ISingletonOperation singleton)
{
    public object Report() => new
    {
        transient = transient.Id.ToString()[..4],
        scoped = scoped.Id.ToString()[..4],
        singleton = singleton.Id.ToString()[..4]
    };
}

app.MapGet("/lifetimes", (ITransientOperation transient, IScopedOperation scoped,
                          ISingletonOperation singleton, OperationReporter reporter) => new
{
    endpoint = new
    {
        transient = transient.Id.ToString()[..4],
        scoped = scoped.Id.ToString()[..4],
        singleton = singleton.Id.ToString()[..4]
    },
    reporter = reporter.Report()
});
```

```text
Request 1:  GET /lifetimes
  endpoint  -> transient: a1f3   scoped: 7c20   singleton: e9b4
  reporter  -> transient: 5d88   scoped: 7c20   singleton: e9b4

Request 2:  GET /lifetimes
  endpoint  -> transient: 0b6e   scoped: 41aa   singleton: e9b4
  reporter  -> transient: c2d7   scoped: 41aa   singleton: e9b4

Transient: different for every consumer, every request.
Scoped:    same inside one request, different between requests.
Singleton: same everywhere, always.
```

### Captive dependency problem

**Definition.** A *captive dependency* happens when a longer-lived service (singleton) holds a shorter-lived one (scoped or transient). The short-lived object is "captured" and lives as long as the singleton.

```csharp
// BUG: a singleton cache captures a scoped DbContext
public class PriceCache(ShopDbContext db) : IPriceCache     // registered as Singleton
{
    public Task<decimal> GetPriceAsync(int productId) =>
        db.Products.Where(p => p.Id == productId).Select(p => p.Price).SingleAsync();
}
builder.Services.AddSingleton<IPriceCache, PriceCache>();
// Consequences without validation: ONE DbContext shared by all concurrent requests ->
// "A second operation was started on this context instance..." exceptions, stale data,
// an ever-growing change tracker (memory leak), and a connection held forever.
```

```text
// With scope validation (default in Development) you get, at startup or first resolve:
System.InvalidOperationException:
  Cannot consume scoped service 'ShopDbContext' from singleton 'IPriceCache'.
```

```csharp
// Turn validation on in EVERY environment (costs a little startup time)
builder.Host.UseDefaultServiceProvider(o =>
{
    o.ValidateScopes = true;    // scoped from root / singleton -> exception
    o.ValidateOnBuild = true;   // try to build every registration at Build(): missing deps fail fast
});
```

**Fixes (pick one):**

1. Make the consumer scoped too, if it does not need to be a singleton.
2. Inject `IServiceScopeFactory` and create a scope per operation (the pattern for background services).
3. Use `IDbContextFactory<T>` and create short-lived contexts on demand.
4. Pass the scoped value as a **method parameter** from the scoped caller.

```csharp
// Fix 2: singleton that creates a scope per unit of work
public class PriceCache(IServiceScopeFactory scopes, IMemoryCache cache) : IPriceCache
{
    public async Task<decimal> GetPriceAsync(int productId)
    {
        if (cache.TryGetValue(productId, out decimal price)) return price;

        await using var scope = scopes.CreateAsyncScope();
        var db = scope.ServiceProvider.GetRequiredService<ShopDbContext>();
        price = await db.Products.Where(p => p.Id == productId)
                                 .Select(p => p.Price).SingleAsync();
        cache.Set(productId, price, TimeSpan.FromMinutes(5));
        return price;
    }
}
```

:::warn What validation does NOT catch
`ValidateOnBuild` cannot validate open generic registrations, services you resolve manually via `IServiceProvider` at runtime, or factory lambdas' internal logic. A singleton that captures `IServiceProvider` (the root) and resolves a scoped service from it creates a scoped instance that lives forever, and with `ValidateScopes` off that silently leaks.
:::

### Transient IDisposable pitfalls

The container **tracks every `IDisposable`/`IAsyncDisposable` it creates** (including transients) so it can dispose them when **the scope that created them** is disposed.

- Transient disposables resolved inside a request are disposed at the **end of the request**, not when you stop using them.
- Transient disposables resolved from the **root provider** (`app.Services`, or from a singleton's factory) are held until **app shutdown**, which is a memory leak if done repeatedly.
- Instances you register yourself (`AddSingleton(new X())`) are **not** disposed by the container; you own them.
- Never call `Dispose()` on an injected service; the container owns it, and other consumers may still use it.

```csharp
// LEAK: every call creates a transient disposable tracked by the ROOT scope forever
public class ReportScheduler(IServiceProvider root)          // singleton
{
    public void Run()
    {
        var exporter = root.GetRequiredService<PdfExporter>(); // transient, IDisposable
        exporter.Export();                                     // never released until shutdown
    }
}

// FIX: resolve inside a short-lived scope (or create the object with a factory you dispose)
public class ReportSchedulerFixed(IServiceScopeFactory scopes)
{
    public void Run()
    {
        using var scope = scopes.CreateScope();
        scope.ServiceProvider.GetRequiredService<PdfExporter>().Export();
    }   // PdfExporter disposed here
}
```

### IServiceScopeFactory in BackgroundService

Hosted services are **singletons**, so they cannot take `DbContext` or other scoped services in their constructor. Create a scope per iteration (per message, per batch).

```csharp
public class AbandonedCartReminder(
    IServiceScopeFactory scopeFactory, ILogger<AbandonedCartReminder> log) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromMinutes(10));
        while (await timer.WaitForNextTickAsync(stoppingToken))
        {
            await using var scope = scopeFactory.CreateAsyncScope();     // fresh DbContext
            var db = scope.ServiceProvider.GetRequiredService<ShopDbContext>();
            var email = scope.ServiceProvider.GetRequiredService<IEmailSender>();

            var cutoff = DateTime.UtcNow.AddHours(-24);
            var carts = await db.Carts
                .Where(c => c.UpdatedAt < cutoff && !c.ReminderSent)
                .Take(100).ToListAsync(stoppingToken);

            foreach (var cart in carts)
            {
                await email.SendAsync(cart.CustomerEmail, "You left something behind", "...");
                cart.ReminderSent = true;
            }
            await db.SaveChangesAsync(stoppingToken);
            log.LogInformation("Sent {Count} reminders", carts.Count);
        }   // scope disposed each iteration -> DbContext + change tracker released
    }
}
```

### Built-in container vs Autofac / Scrutor

| Feature | Built-in (`Microsoft.Extensions.DependencyInjection`) | Scrutor (add-on) | Autofac |
|---|---|---|---|
| Constructor injection | Yes | Yes | Yes |
| Property injection | No | No | **Yes** (`PropertiesAutowired`) |
| Keyed/named services | **Yes (.NET 8)** | n/a | Yes |
| Assembly scanning | No | **Yes** (`Scan`) | Yes |
| Decorators | Manual factory | **Yes** (`Decorate`) | Yes |
| Modules | Extension methods | n/a | `Module` classes |
| Interception (AOP) | No | No | Yes (DynamicProxy) |
| Child/tagged scopes | No | n/a | Yes |
| Speed / AOT friendliness | **Fast, AOT-friendly** | Reflection at startup | Reflection |

```csharp
// Scrutor: scan + decorate on top of the built-in container
builder.Services.Scan(scan => scan
    .FromAssemblyOf<OrderService>()
    .AddClasses(c => c.Where(t => t.Name.EndsWith("Service")))
    .AsImplementedInterfaces()
    .WithScopedLifetime());
builder.Services.Decorate<IProductRepository, CachedProductRepository>();

// Autofac: replace the provider factory, keep using builder.Services as usual
builder.Host.UseServiceProviderFactory(new AutofacServiceProviderFactory());
builder.Host.ConfigureContainer<ContainerBuilder>(cb =>
{
    cb.RegisterType<ReportGenerator>().AsSelf().InstancePerLifetimeScope().PropertiesAutowired();
    cb.RegisterModule<InfrastructureModule>();
});
```

**Recommendation.** Stay on the built-in container (it covers keyed services, open generics, enumerables, factories) and add **Scrutor** for scanning/decoration. Bring in Autofac only for genuinely advanced needs (interception, tagged lifetime scopes, legacy modules).

### Service Locator anti-pattern

**Definition.** *Service Locator* means a class asks a global/injected container for its dependencies at runtime (`_provider.GetService<T>()`) instead of declaring them in its constructor.

```csharp
// ANTI-PATTERN: dependencies are hidden
public class InvoiceService(IServiceProvider provider)
{
    public async Task SendAsync(int orderId)
    {
        var repo = provider.GetRequiredService<IOrderRepository>();   // hidden dependency
        var pdf  = provider.GetRequiredService<IPdfRenderer>();       // hidden dependency
        var mail = provider.GetRequiredService<IEmailSender>();       // hidden dependency
        // ...
    }
}

// BETTER: explicit constructor dependencies
public class InvoiceServiceFixed(IOrderRepository repo, IPdfRenderer pdf, IEmailSender mail) { }
```

**Why it is bad:** the constructor lies about what the class needs; missing registrations fail at runtime deep in a code path instead of at startup; unit tests need a container or a mocked provider; it hides lifetime bugs (resolving scoped from root); and the class is coupled to the DI framework.

**Acceptable uses** (infrastructure only, not business logic): the composition root, factories that pick an implementation by runtime key (keyed services), middleware/filters needing per-request services, `BackgroundService` creating scopes via `IServiceScopeFactory`, and framework integration code.

:::q What is the difference between IoC, DI and DIP?
DIP is the SOLID principle: high-level code depends on abstractions, not concrete classes. IoC is the general idea that a framework controls object creation and flow instead of my code. DI is the pattern that implements IoC for dependencies by passing them in, usually through the constructor, and a DI container automates it.
:::

:::q Why is constructor injection preferred?
Dependencies are explicit in the signature, required, and can be readonly, so the object is always fully initialised and immutable in its dependencies. Missing registrations are found at startup with `ValidateOnBuild`. It is also the only style the built-in container supports, apart from method-style injection in actions, handlers and middleware.
:::

:::q What is a captive dependency and how do you detect it?
A longer-lived service holding a shorter-lived one, typically a singleton with a scoped `DbContext` in its constructor. The scoped object then lives forever and is shared across threads. ASP.NET Core detects it with `ValidateScopes` (on by default in Development) and `ValidateOnBuild`; I enable both in all environments. I fix it by changing the lifetime, using `IServiceScopeFactory`, or using `IDbContextFactory`.
:::

:::q How do you register multiple implementations and pick one?
Register them all and inject `IEnumerable<T>` to get every implementation (for example notification channels). Injecting `T` alone gives the last registered. To pick a specific one, use keyed services in .NET 8+ with `[FromKeyedServices("key")]` or `GetRequiredKeyedService<T>(key)`, or a small factory.
:::
