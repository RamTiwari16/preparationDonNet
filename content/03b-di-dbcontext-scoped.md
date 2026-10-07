## DbContext Lifetime and Testing with DI

### Lifetime demo with a controller and a helper

**Goal.** Prove, with output you can predict, what Singleton, Scoped and Transient mean inside a real MVC request. Each service exposes a `Guid` created in its constructor. The controller and a helper class both receive all three.

```csharp
public interface IOperation { Guid Id { get; } }
public interface ISingletonOp : IOperation { }
public interface IScopedOp : IOperation { }
public interface ITransientOp : IOperation { }

public class Operation : ISingletonOp, IScopedOp, ITransientOp
{
    public Guid Id { get; } = Guid.NewGuid();      // new Guid per INSTANCE
    public override string ToString() => Id.ToString()[..4];
}

// Helper that ALSO depends on all three lifetimes
public class LifetimeHelper(ISingletonOp singleton, IScopedOp scoped, ITransientOp transient)
{
    public string Describe() => $"singleton={singleton} scoped={scoped} transient={transient}";
}

builder.Services.AddSingleton<ISingletonOp, Operation>();
builder.Services.AddScoped<IScopedOp, Operation>();
builder.Services.AddTransient<ITransientOp, Operation>();
builder.Services.AddTransient<LifetimeHelper>();

[ApiController, Route("api/lifetimes")]
public class LifetimesController(
    ISingletonOp singleton, IScopedOp scoped, ITransientOp transient,
    LifetimeHelper helper, ILogger<LifetimesController> log) : ControllerBase
{
    [HttpGet]
    public IActionResult Get()
    {
        var controller = $"singleton={singleton} scoped={scoped} transient={transient}";
        log.LogInformation("controller: {C} | helper: {H}", controller, helper.Describe());
        return Ok(new { controller, helper = helper.Describe() });
    }
}
```

```text
Request 1  GET /api/lifetimes
  controller: singleton=3f9a scoped=b71c transient=0d42
  helper:     singleton=3f9a scoped=b71c transient=e8a5

Request 2  GET /api/lifetimes
  controller: singleton=3f9a scoped=91d0 transient=5c17
  helper:     singleton=3f9a scoped=91d0 transient=a2b3
```

**How to explain the output:**

- **Singleton** `3f9a` is identical in both consumers and in both requests: one instance for the app's lifetime.
- **Scoped** is shared by the controller and the helper inside a request (`b71c`, then `91d0`), but each request gets a new one, because ASP.NET Core creates one DI scope per HTTP request.
- **Transient** differs between the controller and the helper even in the same request: every injection point gets a fresh instance.
- If `LifetimeHelper` were registered as a **singleton**, it would keep request 1's scoped `b71c` forever. That is a captive dependency, and scope validation would throw at startup.

### Why should DbContext be Scoped?

:::tip Say this (60-second answer)
"A `DbContext` is a unit of work: it tracks every entity loaded or changed during one business operation and saves them in one transaction with `SaveChanges`. In a web API one HTTP request is one business operation, so one context per request is the natural fit. Scoped means every repository and service in that request share the same context: they see the same tracked entities and commit atomically. Singleton breaks because `DbContext` is not thread-safe, so concurrent requests crash or mix each other's changes, and the change tracker grows forever. Transient breaks because each repository gets its own context, so there is no single transaction, entities from one context are unknown to another, and you open more connections. That is why `AddDbContext` registers it as Scoped by default."
:::

#### What a DbContext really holds

| Responsibility | Consequence for lifetime |
|---|---|
| **Unit of work**: collects inserts, updates and deletes; `SaveChanges` writes them in **one transaction** | Everything that belongs to one business operation must use the **same** instance |
| **Change tracker / identity map**: one tracked instance per primary key | Two repositories loading Customer 7 must get the **same object**, or changes conflict |
| **Connection management**: opens/closes a pooled `SqlConnection` per operation | Many contexts per request means more connections in use at once |
| **Not thread-safe**: one async operation at a time | Must never be shared across concurrent requests or parallel tasks |
| **Cheap to create**, meant to be **short-lived** | Create per request/operation, dispose quickly |

#### Real e-commerce example: checkout

`POST /api/orders/checkout` must, **atomically**: load the customer, check they are not blocked, load products, decrement stock, create the order and its lines, and add loyalty points. Three repositories are involved.

```text
HTTP request (one DI scope)
  OrdersController
    -> OrderService
         -> CustomerRepository  --\
         -> InventoryRepository ---+--> ONE ShopDbContext (scoped) --> ONE SaveChanges
         -> OrderRepository     --/                                    = ONE transaction
         -> IUnitOfWork (same ShopDbContext instance)
  scope disposed -> DbContext disposed -> connection back to the pool
```

```csharp
// ----- Data layer -----
public interface IUnitOfWork { Task<int> SaveChangesAsync(CancellationToken ct = default); }

public class ShopDbContext(DbContextOptions<ShopDbContext> options)
    : DbContext(options), IUnitOfWork          // DbContext already has SaveChangesAsync
{
    public DbSet<Customer> Customers => Set<Customer>();
    public DbSet<Product> Products => Set<Product>();
    public DbSet<Order> Orders => Set<Order>();
}

public class CustomerRepository(ShopDbContext db) : ICustomerRepository
{
    public Task<Customer?> GetAsync(int id, CancellationToken ct) =>
        db.Customers.FirstOrDefaultAsync(c => c.Id == id, ct);
}

public class InventoryRepository(ShopDbContext db) : IInventoryRepository
{
    public Task<List<Product>> GetProductsAsync(IReadOnlyCollection<int> ids, CancellationToken ct) =>
        db.Products.Where(p => ids.Contains(p.Id)).ToListAsync(ct);
}

public class OrderRepository(ShopDbContext db) : IOrderRepository
{
    public void Add(Order order) => db.Orders.Add(order);      // no SaveChanges here!
}
```

```csharp
// ----- Application layer -----
public record CartLine(int ProductId, int Quantity);

public class OrderService(
    ICustomerRepository customers,
    IInventoryRepository inventory,
    IOrderRepository orders,
    IUnitOfWork uow,
    TimeProvider clock) : IOrderService
{
    public async Task<int> CheckoutAsync(
        int customerId, IReadOnlyList<CartLine> lines, CancellationToken ct)
    {
        var customer = await customers.GetAsync(customerId, ct)
            ?? throw new NotFoundException($"Customer {customerId} not found");
        if (customer.IsBlocked)
            throw new ConflictException("Customer is blocked");

        var ids = lines.Select(l => l.ProductId).Distinct().ToList();
        var products = await inventory.GetProductsAsync(ids, ct);

        var order = new Order { Customer = customer, CreatedAt = clock.GetUtcNow().UtcDateTime };
        foreach (var line in lines)
        {
            var product = products.SingleOrDefault(p => p.Id == line.ProductId)
                ?? throw new NotFoundException($"Product {line.ProductId} not found");
            if (product.Stock < line.Quantity)
                throw new ConflictException($"Only {product.Stock} of product {product.Id} left");

            product.Stock -= line.Quantity;                  // tracked change (UPDATE)
            order.Lines.Add(new OrderLine
            { Product = product, Quantity = line.Quantity, UnitPrice = product.Price });
        }

        order.Total = order.Lines.Sum(l => l.UnitPrice * l.Quantity);
        customer.LoyaltyPoints += (int)order.Total;          // tracked change (UPDATE)
        orders.Add(order);                                   // INSERT order + lines

        // ONE SaveChanges = ONE database transaction:
        // INSERT Orders, INSERT OrderLines, UPDATE Products, UPDATE Customers
        await uow.SaveChangesAsync(ct);
        return order.Id;
    }
}

// ----- API layer -----
[ApiController, Route("api/orders"), Authorize]
public class OrdersController(IOrderService orders) : ControllerBase
{
    public record CheckoutRequest(int CustomerId, List<CartLine> Lines);

    [HttpPost("checkout")]
    public async Task<IActionResult> Checkout(CheckoutRequest req, CancellationToken ct)
    {
        var id = await orders.CheckoutAsync(req.CustomerId, req.Lines, ct);
        return CreatedAtAction(nameof(Get), new { id }, new { id });
    }

    [HttpGet("{id:int}")]
    public IActionResult Get(int id) => Ok(new { id });
}
```

```csharp
// ----- Registration: everything that touches the context is Scoped -----
builder.Services.AddDbContext<ShopDbContext>(o =>
    o.UseSqlServer(builder.Configuration.GetConnectionString("ShopDb")));   // Scoped by default
builder.Services.AddScoped<IUnitOfWork>(sp => sp.GetRequiredService<ShopDbContext>()); // SAME instance
builder.Services.AddScoped<ICustomerRepository, CustomerRepository>();
builder.Services.AddScoped<IInventoryRepository, InventoryRepository>();
builder.Services.AddScoped<IOrderRepository, OrderRepository>();
builder.Services.AddScoped<IOrderService, OrderService>();
builder.Services.AddSingleton(TimeProvider.System);
```

**Why Scoped makes this correct:**

1. **One unit of work per request.** The three repositories never call `SaveChanges`; the service calls it once, so the stock decrement, order insert and loyalty update succeed or fail **together**. If stock is insufficient for line 3, an exception is thrown before `SaveChanges`, and nothing is written.
2. **Identity map consistency.** Customer 7 loaded by `CustomerRepository` is the **same tracked object** that `order.Customer` points to. EF knows it already exists (state `Unchanged`, then `Modified` for the loyalty points), so it updates it instead of trying to insert it.
3. **One connection at a time.** The context opens a pooled connection per query and per `SaveChanges`, so a request never holds more than one.
4. **Clean slate per request.** The scope ends, the context is disposed, its change tracker and cached entities go away. No data leaks to the next request.

```csharp
// Identity map in action (same scope = same instance)
var c1 = await customers.GetAsync(7, ct);                    // CustomerRepository
var c2 = await db.Customers.FirstAsync(c => c.Id == 7, ct);  // anyone else in the request
Console.WriteLine(ReferenceEquals(c1, c2));                  // Output: True
```

#### What goes wrong with Singleton

```csharp
builder.Services.AddDbContext<ShopDbContext>(
    o => o.UseSqlServer(cs), ServiceLifetime.Singleton);       // DON'T
```

1. **Concurrency crash.** Two users check out at the same moment; both requests use the one context:

```text
System.InvalidOperationException: A second operation was started on this context instance
before a previous operation completed. This is usually caused by different threads
concurrently using the same instance of DbContext.
```

Worse, EF only detects *some* concurrent use. Undetected races can corrupt the change tracker's internal state.

2. **Cross-user data mixing.** Request A adds an order and is awaiting the payment gateway. Request B for a different user calls `SaveChanges`. B's `SaveChanges` **commits A's half-finished order** (it is in the shared tracker), even if A later fails. Or B fails validation and leaves tracked garbage that A then saves.
3. **Stale data.** Entities stay tracked forever. A query returns the cached tracked instance, not the price an admin changed in the database five minutes ago.
4. **Memory leak.** The change tracker grows with every entity ever loaded: memory climbs until the process is recycled, and `DetectChanges` gets slower on every save.
5. **Poisoned state.** After one failed `SaveChanges` (for example a unique key violation), the bad entity stays `Added` and every later save by any user fails with the same error.

#### What goes wrong with Transient

```csharp
builder.Services.AddDbContext<ShopDbContext>(
    o => o.UseSqlServer(cs), ServiceLifetime.Transient);       // DON'T (for this design)
```

Now `CustomerRepository`, `InventoryRepository`, `OrderRepository` and `IUnitOfWork` each get a **different** context.

1. **No single transaction.** `uow.SaveChangesAsync()` saves only its own (empty) context, so the stock and loyalty changes are **never saved**. If instead each repository saves its own context, the saves are **separate** transactions: stock is decremented, the order insert fails, and inventory is now wrong.
2. **Broken identity map.** `order.Customer = customer` points to an entity tracked by the *customer* context. The *order* context has never seen it; when you `Add(order)`, EF treats the reachable, untracked customer as **new** and tries to `INSERT` it (duplicate key error or a duplicate customer row), or you hit "instance is already being tracked" errors when attaching.
3. **Connection and memory overuse.** Four contexts per request, each possibly opening a connection; under load you exhaust the connection pool (default `Max Pool Size=100`) and requests time out waiting for a connection. Transient disposables are also only disposed at the **end of the request**, so they are not cheaper to hold.

| Lifetime | Thread safety | Transaction across repositories | Identity map | Memory | Verdict |
|---|---|---|---|---|---|
| **Singleton** | Broken under concurrent requests | Mixes users' changes | Global, stale | Grows forever | Never |
| **Scoped** | One request = one logical flow | **One `SaveChanges`** | Per request, consistent | Released per request | **Default for web apps** |
| **Transient** | OK | Split into many | Fragmented | More contexts + connections | Only for isolated, single-repository operations |

:::warn Scoped is not automatically thread-safe
Scoped protects you between requests, not inside one. `Task.WhenAll(repo.GetOrdersAsync(), repo.GetCustomersAsync())` on the same context throws the "second operation" exception. Await sequentially, or use `IDbContextFactory` to create one context per parallel task.
:::

#### Transactions with a scoped context

`SaveChanges` already wraps all pending changes in one transaction. You need an explicit `db.Database.BeginTransactionAsync()` only when **several** `SaveChanges` calls (or raw SQL) must be atomic. With `EnableRetryOnFailure`, wrap that transaction in `db.Database.CreateExecutionStrategy().ExecuteAsync(...)`. Because the context is scoped, every repository in the request automatically takes part in that transaction.

#### AddDbContextPool: the nuance

```csharp
builder.Services.AddDbContextPool<ShopDbContext>(
    o => o.UseSqlServer(cs), poolSize: 1024);           // 1024 is the default in modern EF Core
```

- Consumers still see it as **Scoped** (one per request); at scope end the instance is **reset and returned to the pool** instead of disposed. Worth it only for very high-throughput APIs; measure first.
- **Constraints:** the constructor runs once per pooled instance and takes only `DbContextOptions<T>`. Do **not** inject scoped services (current user, tenant) or keep per-request fields, because they would leak to the next renter. Per-tenant state must be set after renting and reset carefully.

#### IDbContextFactory: when one-per-request is the wrong unit

```csharp
builder.Services.AddDbContextFactory<ShopDbContext>(o => o.UseSqlServer(cs));
// or AddPooledDbContextFactory<ShopDbContext>(...)
// Recent EF Core versions also register ShopDbContext itself as scoped from the factory,
// so controllers can keep injecting the context (verify for your version).
```

| Situation | Why scoped is wrong | Use |
|---|---|---|
| **Blazor Server** | A DI scope lasts for the whole **circuit** (the user's session, minutes or hours) and UI events can overlap, so a scoped context is long-lived and concurrently used | Inject `IDbContextFactory<T>`, create a context **per operation** |
| **Background jobs / hosted services** | They are singletons; no request scope exists | Factory, or `IServiceScopeFactory` per unit of work |
| **Parallel work in one request** | One context cannot run two queries at once | One context per parallel task from the factory |
| Desktop apps (WPF/WinForms) | No request scope | Context per form/operation |

```csharp
// Parallel dashboard queries: one context per task
public class DashboardService(IDbContextFactory<ShopDbContext> factory)
{
    public async Task<DashboardDto> LoadAsync(CancellationToken ct)
    {
        async Task<T> Run<T>(Func<ShopDbContext, Task<T>> query)
        {
            await using var db = await factory.CreateDbContextAsync(ct);   // you own disposal
            return await query(db);
        }

        var sales    = Run(db => db.Orders.SumAsync(o => o.Total, ct));
        var buyers   = Run(db => db.Customers.CountAsync(ct));
        var lowStock = Run(db => db.Products.CountAsync(p => p.Stock < 5, ct));
        await Task.WhenAll(sales, buyers, lowStock);

        return new DashboardDto(await sales, await buyers, await lowStock);
    }
}
```

In a Blazor Server component the same idea applies: `@inject IDbContextFactory<ShopDbContext> DbFactory`, then `await using var db = await DbFactory.CreateDbContextAsync();` inside each event handler.

### DbContext in BackgroundService and hosted services

Hosted services are registered as **singletons**. Injecting `ShopDbContext` into their constructor is a captive dependency (and throws under scope validation). Create a **scope per unit of work** (per message, per batch, per tick) so each gets a fresh context and change tracker.

```csharp
// Order-placed queue consumer: one scope (and one DbContext) per message
public class OrderPlacedConsumer(
    Channel<OrderPlaced> queue,
    IServiceScopeFactory scopes,
    ILogger<OrderPlacedConsumer> log) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        await foreach (var msg in queue.Reader.ReadAllAsync(stoppingToken))
        {
            await using var scope = scopes.CreateAsyncScope();
            var db = scope.ServiceProvider.GetRequiredService<ShopDbContext>();
            var invoices = scope.ServiceProvider.GetRequiredService<IInvoiceService>();
            try
            {
                var order = await db.Orders.Include(o => o.Lines)
                    .FirstAsync(o => o.Id == msg.OrderId, stoppingToken);
                await invoices.CreateAsync(order, stoppingToken);   // same scoped context inside
                await db.SaveChangesAsync(stoppingToken);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                log.LogError(ex, "Failed to process order {OrderId}", msg.OrderId);
            }
        }   // scope disposed: context and tracked entities released per message
    }
}

builder.Services.AddSingleton(Channel.CreateUnbounded<OrderPlaced>());
builder.Services.AddHostedService<OrderPlacedConsumer>();
```

Rules: never reuse one context for the whole lifetime of a worker; never capture the request's `DbContext` in `Task.Run` fire-and-forget work (the scope is disposed when the response finishes, giving `ObjectDisposedException: Cannot access a disposed context instance`); hand work to a queue and let the worker create its own scope.

### Testing with DI

#### Unit tests: fakes and mocks

Because `OrderService` depends only on interfaces, it is unit-testable without a database.

```csharp
public class OrderServiceTests
{
    private readonly Mock<ICustomerRepository> _customers = new();
    private readonly Mock<IInventoryRepository> _inventory = new();
    private readonly Mock<IOrderRepository> _orders = new();
    private readonly Mock<IUnitOfWork> _uow = new();
    private readonly FakeTimeProvider _clock = new(new DateTimeOffset(2026, 10, 6, 9, 0, 0, TimeSpan.Zero));

    private OrderService CreateSut() =>
        new(_customers.Object, _inventory.Object, _orders.Object, _uow.Object, _clock);

    [Fact]
    public async Task Checkout_decrements_stock_and_saves_once()
    {
        var customer = new Customer { Id = 7 };
        var product = new Product { Id = 1, Price = 10m, Stock = 5 };
        _customers.Setup(r => r.GetAsync(7, It.IsAny<CancellationToken>())).ReturnsAsync(customer);
        _inventory.Setup(r => r.GetProductsAsync(It.IsAny<IReadOnlyCollection<int>>(),
                                                 It.IsAny<CancellationToken>()))
                  .ReturnsAsync([product]);

        await CreateSut().CheckoutAsync(7, [new CartLine(1, 2)], CancellationToken.None);

        Assert.Equal(3, product.Stock);
        Assert.Equal(20, customer.LoyaltyPoints);
        _orders.Verify(r => r.Add(It.Is<Order>(o => o.Total == 20m)), Times.Once);
        _uow.Verify(u => u.SaveChangesAsync(It.IsAny<CancellationToken>()), Times.Once);
    }

    // Negative case: Stock = 1, quantity 2 -> Assert.ThrowsAsync<ConflictException>
    // and _uow.Verify(u => u.SaveChangesAsync(...), Times.Never): nothing is saved.
}
```

**Mocks vs fakes.** Mocks (Moq, NSubstitute) verify interactions ("SaveChanges called once"). Hand-written fakes (an in-memory repository, a `FakeEmailSender` that records messages) are simpler to read and reuse. Do not mock `DbContext`/`DbSet` directly: it is brittle and does not test LINQ translation; test data access with a real database instead.

#### Integration tests: WebApplicationFactory + ConfigureTestServices

`WebApplicationFactory<Program>` boots the **real** app in memory (real pipeline, routing, DI, filters, serialization) and gives you an `HttpClient`. `ConfigureTestServices` runs **after** the app's own registrations, so it is where you replace services.

```csharp
public partial class Program { }   // in the API project: exposes the entry point to tests

public class ShopApiFactory : WebApplicationFactory<Program>, IAsyncLifetime
{
    private readonly SqliteConnection _connection = new("DataSource=:memory:");
    public FakeEmailSender Emails { get; } = new();

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Testing");
        builder.ConfigureTestServices(services =>
        {
            // 1) Replace the SQL Server DbContext with SQLite in-memory (real SQL, real constraints)
            services.RemoveAll<DbContextOptions<ShopDbContext>>();
            // EF Core 9+ also stores provider configuration separately; remove it as well
            // (verify for your EF version):
            services.RemoveAll<IDbContextOptionsConfiguration<ShopDbContext>>();
            services.AddDbContext<ShopDbContext>(o => o.UseSqlite(_connection));

            // 2) Replace external dependencies with fakes
            services.RemoveAll<IEmailSender>();
            services.AddSingleton<IEmailSender>(Emails);

            // 3) Fake authentication: every request is an authenticated test user
            services.AddAuthentication(TestAuthHandler.Scheme)
                    .AddScheme<AuthenticationSchemeOptions, TestAuthHandler>(
                        TestAuthHandler.Scheme, _ => { });
        });
    }

    public async Task InitializeAsync()
    {
        await _connection.OpenAsync();              // in-memory DB lives while connection is open
        using var scope = Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<ShopDbContext>();
        await db.Database.EnsureCreatedAsync();
        db.Customers.Add(new Customer { Id = 7, Name = "Ana" });
        db.Products.Add(new Product { Id = 1, Name = "Keyboard", Price = 10m, Stock = 5 });
        await db.SaveChangesAsync();
    }

    public new async Task DisposeAsync()
    {
        await _connection.DisposeAsync();
        await base.DisposeAsync();
    }
}

public class TestAuthHandler(IOptionsMonitor<AuthenticationSchemeOptions> o,
    ILoggerFactory l, UrlEncoder e) : AuthenticationHandler<AuthenticationSchemeOptions>(o, l, e)
{
    public const string Scheme = "Test";
    protected override Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        var identity = new ClaimsIdentity(
            [new Claim(ClaimTypes.NameIdentifier, "7"), new Claim(ClaimTypes.Role, "Customer")],
            Scheme);
        return Task.FromResult(AuthenticateResult.Success(
            new AuthenticationTicket(new ClaimsPrincipal(identity), Scheme)));
    }
}
```

```csharp
public class CheckoutApiTests(ShopApiFactory factory) : IClassFixture<ShopApiFactory>
{
    [Fact]
    public async Task Checkout_returns_201_and_updates_stock_in_one_transaction()
    {
        var client = factory.CreateClient();

        var response = await client.PostAsJsonAsync("/api/orders/checkout",
            new { customerId = 7, lines = new[] { new { productId = 1, quantity = 2 } } });

        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        Assert.NotNull(response.Headers.Location);

        using var scope = factory.Services.CreateScope();     // fresh context = fresh read
        var db = scope.ServiceProvider.GetRequiredService<ShopDbContext>();
        Assert.Equal(3, (await db.Products.SingleAsync(p => p.Id == 1)).Stock);
        Assert.Equal(1, await db.Orders.CountAsync());
    }
    // Same pattern: quantity = 99 -> assert 409 Conflict and that stock is unchanged.
}
```

| Test database option | Pros | Cons |
|---|---|---|
| EF Core **InMemory** provider | Fastest, zero setup | Not relational: no transactions, no constraints, LINQ that fails on SQL Server may pass. Avoid for integration tests |
| **SQLite in-memory** | Real SQL, constraints, fast | Different SQL dialect from SQL Server (some functions, `rowversion`) |
| **Testcontainers** (real SQL Server in Docker) | Highest fidelity, same engine as production | Slower, needs Docker in CI |

:::scenario "A second operation was started on this context instance" appears randomly in production
Root causes, in order of likelihood: (1) the context, or a repository/service holding it, is registered as **singleton**, or captured by a singleton (cache, hosted service); (2) parallel queries with `Task.WhenAll` on one context; (3) a missing `await` (fire-and-forget query while the next one starts); (4) `async void` handlers. Fix: keep `DbContext` and everything that uses it **scoped**; turn on `ValidateScopes` and `ValidateOnBuild` in all environments; await every EF call; use `IDbContextFactory` for genuine parallelism and in singletons.
:::

:::scenario Data from user A appears in user B's response
A long-lived context (singleton, or a static field) or a pooled context with custom per-request state (for example a `TenantId` field set in the constructor or not reset). Tracked entities and cached state cross request boundaries, so user B's query returns A's tracked instance or A's tenant filter. Fix: scoped context; no per-user state in a pooled context unless it is reset on every rent; tenant filters read from a scoped tenant provider; add an integration test that runs two users' requests concurrently and asserts isolation.
:::

:::scenario Memory grows steadily in a singleton cache of entities
A singleton `ProductCache` stores **tracked EF entities** (with navigation properties) loaded from a captured context, so the context, its change tracker and the whole object graph stay alive, and the tracker keeps growing as more entities are loaded. Fix: cache **DTOs** (immutable records) not entities; load with `AsNoTracking()` in a short-lived scope or factory-created context; set size limits and expirations on `IMemoryCache`; confirm with a memory dump (`dotnet-gcdump`) that `ChangeTracker`/`InternalEntityEntry` objects disappear.
:::

:::scenario Background email job throws ObjectDisposedException
The controller started `Task.Run(() => SendInvoiceAsync(order))` that used the request's `DbContext`. The response returned, the request scope was disposed, then the task touched the context: "Cannot access a disposed context instance." Fix: publish a message to a `Channel`/queue (or use the outbox pattern) and process it in a `BackgroundService` that creates its own scope per message via `IServiceScopeFactory`.
:::

## Quick-fire Q&A

:::q What is dependency injection in one sentence?
A class receives its dependencies from outside, usually through its constructor, instead of creating them with `new`, and a container builds and manages those objects. Say: "It turns `new SqlRepository()` inside my class into an `IRepository` parameter supplied by the container."
:::

:::q IoC vs DI vs DIP?
DIP is the SOLID principle (depend on abstractions). IoC is the broader idea that the framework controls creation and flow. DI is the pattern that implements IoC by passing dependencies in; the container automates it.
:::

:::q What are the three service lifetimes?
Singleton: one instance for the app. Scoped: one per request (scope). Transient: a new instance on every resolve. Disposal follows the same boundary: app shutdown, end of request, end of the scope that created the transient.
:::

:::q Why should DbContext be scoped?
It is a unit of work and identity map that is not thread-safe. Scoped gives one context per request, so all repositories share the tracked entities and commit with one `SaveChanges` in one transaction, then it is disposed. Singleton breaks under concurrency and leaks memory; transient splits the transaction and the identity map and uses more connections.
:::

:::q What happens if you inject a scoped service into a singleton?
It becomes a captive dependency: the scoped instance lives forever and is shared by all threads. With scope validation, which is on in Development, you get "Cannot consume scoped service ... from singleton ...". Fix it with `IServiceScopeFactory`, `IDbContextFactory`, or by changing lifetimes.
:::

:::q How do you use a DbContext inside a BackgroundService?
Inject `IServiceScopeFactory`, create an async scope per unit of work, and resolve the context from the scope, or inject `IDbContextFactory<T>` and create and dispose a context per operation. Never inject the context into the hosted service's constructor.
:::

:::q When do you use IDbContextFactory?
When there is no suitable request scope or you need several contexts: Blazor Server (circuit-long scopes), background jobs, parallel queries, desktop apps. You create the context with `CreateDbContextAsync` and must dispose it yourself.
:::

:::q What does AddDbContextPool change?
Context instances are reset and reused instead of being created and disposed per request, which reduces allocation overhead. Consumers still get one per scope. The context must not hold per-request state or inject scoped services, because the instance is reused by other requests.
:::

:::q Can you run two queries in parallel on the same DbContext?
No. A context supports one operation at a time and throws "A second operation was started on this context instance". Await sequentially, or create one context per task with `IDbContextFactory`.
:::

:::q Constructor vs property vs method injection?
Constructor for required dependencies (the default and the only one the built-in container supports). Property for optional dependencies with a default (needs Autofac). Method injection when a dependency varies per call; ASP.NET Core supports it via `[FromServices]`, minimal API parameters and middleware `InvokeAsync` parameters.
:::

:::q How do you register several implementations of one interface?
Register each; inject `IEnumerable<T>` to get all of them in registration order, or `T` to get the last one. Use keyed services (.NET 8+) with `[FromKeyedServices]` to choose a specific implementation.
:::

:::q What is TryAdd for?
`TryAddSingleton`/`TryAddScoped` register only if no registration exists yet, so libraries can provide defaults that applications override. `TryAddEnumerable` avoids adding the same implementation twice to a multi-registration.
:::

:::q Why is Service Locator considered an anti-pattern?
Dependencies are hidden inside method bodies instead of declared in the constructor. Missing registrations fail at runtime, tests need a container, and lifetime bugs are hidden. It is acceptable only in infrastructure code such as factories, middleware or scope creation in background services.
:::

:::q How do you replace a service in integration tests?
Use `WebApplicationFactory<Program>` and, in `ConfigureTestServices`, call `RemoveAll<T>()` then register the fake, for example SQLite or Testcontainers instead of SQL Server, a fake email sender, or a test authentication handler. `ConfigureTestServices` runs after the app's registrations, so the replacement wins.
:::

:::q Do transient services that implement IDisposable get disposed?
Yes, but only when the scope that created them is disposed, for example at the end of the request. If you resolve them from the root provider they are kept until app shutdown, which leaks memory. Never call `Dispose` on injected services yourself.
:::
