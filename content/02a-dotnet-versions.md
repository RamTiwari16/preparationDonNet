## .NET Versions

### Release model: LTS vs STS

**Definition.** Modern .NET ships one major version every **November**. Even-numbered versions are **LTS** (Long Term Support, 3 years). Odd-numbered versions are **STS** (Standard Term Support, 2 years under the current policy).

**Why it matters.** Interviewers ask "which version would you start a new project on, and what happens when support ends?" After end of support you get **no security patches**. That is a compliance and audit problem, not just a technical one.

| .NET | Released | Type | C# | Support ends | Status (Oct 2026) |
|---|---|---|---|---|---|
| .NET 6 | Nov 2021 | LTS | 10 | 12 Nov 2024 | Out of support |
| .NET 7 | Nov 2022 | STS | 11 | 14 May 2024 | Out of support |
| .NET 8 | Nov 2023 | LTS | 12 | 10 Nov 2026 | Ends in weeks |
| .NET 9 | Nov 2024 | STS | 13 | 10 Nov 2026 | Ends in weeks |
| .NET 10 | Nov 2025 | LTS | 14 | 14 Nov 2028 | Current LTS |

> Dates come from the official support policy page (dotnet.microsoft.com/platform/support/policy/dotnet-core). .NET 7 got 18 months; the STS window was later extended to 24 months, which is why .NET 8 and .NET 9 end on the same day. Always re-check the policy page before quoting dates, and note that .NET 11 (STS) is expected in November 2026 — verify in the official release notes.

```text
Nov 2021   Nov 2022   Nov 2023   Nov 2024   Nov 2025   Nov 2026
 .NET 6     .NET 7     .NET 8     .NET 9     .NET 10    .NET 11
  LTS        STS        LTS        STS        LTS        STS
 (3 yrs)   (18 mo)    (3 yrs)    (2 yrs)    (3 yrs)    (2 yrs)
```

:::tip What interviewers look for
Say: "For production I target the current LTS (.NET 10 now). I move to STS only when I need a specific feature and I can commit to upgrading within a year. I keep one upgrade per year on the roadmap, because skipping versions makes the next upgrade harder."
:::

### .NET 6 (LTS, C# 10)

**Definition.** The release that unified the .NET 5 line (no more ".NET Core") and introduced the "minimal hosting model" that every modern template uses.

| Area | What arrived |
|---|---|
| Hosting | `WebApplication` / `WebApplicationBuilder`, no more `Startup.cs` by default |
| Minimal APIs | `app.MapGet/MapPost(...)` with lambdas, parameter binding from DI |
| C# 10 | File-scoped namespaces, global usings, implicit usings, `record struct`, constant interpolated strings, `with` on structs, lambda improvements |
| Tooling | **Hot Reload** (`dotnet watch`, Visual Studio), faster build |
| BCL | `DateOnly`, `TimeOnly`, `PriorityQueue<T,P>`, `Parallel.ForEachAsync`, `PeriodicTimer`, LINQ `Chunk`, `MinBy`/`MaxBy`, `ArgumentNullException.ThrowIfNull` |
| EF Core 6 | Temporal tables, compiled models, migration bundles, pre-convention configuration |
| JSON | `System.Text.Json` source generators, `IAsyncEnumerable` streaming |

```csharp
// .NET 6: top-level statements + WebApplication + minimal API
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddDbContext<ShopDb>(o =>
    o.UseSqlServer(builder.Configuration.GetConnectionString("Default")));

var app = builder.Build();

app.MapGet("/products/{id:int}", async (int id, ShopDb db) =>
    await db.Products.FindAsync(id) is { } product
        ? Results.Ok(product)
        : Results.NotFound());

app.Run();
```

```csharp
// C# 10 niceties
namespace Shop.Orders;                       // file-scoped namespace
public readonly record struct Money(decimal Amount, string Currency);

var price = new Money(10m, "USD");
var discounted = price with { Amount = 8m }; // 'with' now works on structs
```

### .NET 7 (STS, C# 11)

| Area | What arrived |
|---|---|
| ASP.NET Core | **Rate limiting middleware** (`AddRateLimiter`), **output caching** (`AddOutputCache`), `MapGroup` route groups, **endpoint filters** (`IEndpointFilter`), `[AsParameters]`, `TypedResults` |
| C# 11 | `required` members, raw string literals (`"""`), list patterns, generic math, `file` types, UTF-8 literals (`"abc"u8`) |
| BCL | Generic math interfaces (`INumber<T>`), `[GeneratedRegex]`, Native AOT for console apps |
| EF Core 7 | `ExecuteUpdate` / `ExecuteDelete` (bulk without loading), TPC inheritance, JSON columns on SQL Server |

```csharp
// .NET 7: built-in rate limiting (fixed window per client IP)
builder.Services.AddRateLimiter(o =>
{
    o.RejectionStatusCode = StatusCodes.Status429TooManyRequests;
    o.AddPolicy("per-ip", ctx => RateLimitPartition.GetFixedWindowLimiter(
        ctx.Connection.RemoteIpAddress?.ToString() ?? "unknown",
        _ => new FixedWindowRateLimiterOptions
        {
            PermitLimit = 100,
            Window = TimeSpan.FromMinutes(1),
            QueueLimit = 0
        }));
});

app.UseRateLimiter();
app.MapGet("/api/products", () => "ok").RequireRateLimiting("per-ip");
```

```csharp
// C# 11 required members: caller MUST set them in an object initializer
public class CreateOrderRequest
{
    public required Guid CustomerId { get; init; }
    public required List<OrderLineDto> Lines { get; init; }
}

var req = new CreateOrderRequest { CustomerId = id, Lines = lines };  // OK
// var bad = new CreateOrderRequest();   // compile error CS9035
```

```csharp
// .NET 7: route groups + endpoint filter + output cache
var orders = app.MapGroup("/api/orders")
                .RequireAuthorization()
                .AddEndpointFilter<ValidationFilter>();

orders.MapGet("/", GetOrders).CacheOutput(p => p.Expire(TimeSpan.FromSeconds(30)));
```

### .NET 8 (LTS, C# 12)

**Why it matters.** .NET 8 is the version most production systems run today, so expect detailed questions.

| Area | What arrived |
|---|---|
| C# 12 | **Primary constructors** for classes/structs, **collection expressions** `[1, 2, ..other]`, `ref readonly` params, default lambda params, alias any type |
| DI | **Keyed services** (`AddKeyedSingleton`, `[FromKeyedServices]`) |
| BCL | `TimeProvider` (+ `FakeTimeProvider` for tests), `FrozenDictionary`/`FrozenSet`, `SearchValues`, `Random.Shuffle`, `[InlineArray]` |
| ASP.NET Core | `IExceptionHandler`, **Native AOT** support (`CreateSlimBuilder`, `CreateEmptyBuilder`), Identity API endpoints, `Microsoft.Extensions.Http.Resilience` |
| Blazor | **Blazor Web App** full-stack model: static SSR, streaming rendering, enhanced navigation, per-component render modes (Server / WebAssembly / Auto) |
| EF Core 8 | **Complex types** (value objects), **primitive collections**, expanded JSON column support (JSON columns first appeared in EF 7 on SQL Server), `HierarchyId`, raw SQL for unmapped types, `DateOnly`/`TimeOnly` |
| Runtime | Dynamic PGO on by default, big GC/JIT gains |

```csharp
// C# 12 primary constructor + collection expression
public class OrderService(IOrderRepository repo, ILogger<OrderService> log)
{
    private static readonly string[] Open = ["Pending", "Paid"];   // collection expr

    public async Task<IReadOnlyList<Order>> GetOpenAsync(CancellationToken ct)
    {
        log.LogInformation("Loading open orders");
        return await repo.GetByStatusAsync(Open, ct);
    }
}

int[] a = [1, 2, 3];
int[] b = [..a, 4, 5];            // spread -> 1,2,3,4,5
```

```csharp
// Keyed services: several implementations of the same interface
builder.Services.AddKeyedScoped<IPaymentGateway, StripeGateway>("stripe");
builder.Services.AddKeyedScoped<IPaymentGateway, PayPalGateway>("paypal");

app.MapPost("/pay/stripe", ([FromKeyedServices("stripe")] IPaymentGateway gw) =>
    gw.ChargeAsync(10m));
```

```csharp
// TimeProvider: testable time (inject instead of DateTime.UtcNow)
public class CouponService(TimeProvider clock)
{
    public bool IsExpired(Coupon c) => c.ExpiresAt <= clock.GetUtcNow();
}
builder.Services.AddSingleton(TimeProvider.System);
// test: var fake = new FakeTimeProvider(); fake.Advance(TimeSpan.FromDays(2));

// FrozenDictionary: build once, read many times, fastest lookups
var countryByCode = countries.ToFrozenDictionary(c => c.Code);
```

```csharp
// IExceptionHandler: centralised, DI-friendly global exception handling
public class GlobalExceptionHandler(ILogger<GlobalExceptionHandler> log) : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(
        HttpContext ctx, Exception ex, CancellationToken ct)
    {
        log.LogError(ex, "Unhandled exception");
        ctx.Response.StatusCode = StatusCodes.Status500InternalServerError;
        await ctx.Response.WriteAsJsonAsync(new ProblemDetails
        {
            Status = 500, Title = "An unexpected error occurred"
        }, ct);
        return true;                 // handled, stop the chain
    }
}
builder.Services.AddExceptionHandler<GlobalExceptionHandler>();
builder.Services.AddProblemDetails();
app.UseExceptionHandler();
```

### .NET 9 (STS, C# 13)

| Area | What arrived |
|---|---|
| ASP.NET Core | **Built-in OpenAPI document generation** (`Microsoft.AspNetCore.OpenApi`: `AddOpenApi()` / `MapOpenApi()`). **Swashbuckle removed from the Web API template.** `MapStaticAssets()` (build-time compression + fingerprinting + ETags) |
| Caching | **`HybridCache`** (`Microsoft.Extensions.Caching.Hybrid`): L1 in-memory + L2 distributed, stampede protection, tags |
| C# 13 | `params` collections (`params ReadOnlySpan<T>`), new `System.Threading.Lock` type, `\e` escape, partial properties, `ref struct` interfaces |
| BCL / LINQ | `CountBy`, `AggregateBy`, `Index()`, `Task.WhenEach`, `Guid.CreateVersion7()`, `OrderedDictionary<K,V>`, `PriorityQueue.Remove`, `JsonSerializerOptions.Web` |
| System.Text.Json | Nullable annotations respected, JSON schema export (`JsonSchemaExporter`), indentation options |
| AI | `Microsoft.Extensions.AI` abstractions |
| Blazor | New Hybrid + Web app template, render-mode detection |

```csharp
// Built-in OpenAPI (no Swashbuckle needed for the document)
builder.Services.AddOpenApi();
var app = builder.Build();
if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();            // GET /openapi/v1.json
}
// UI is NOT built in: add Scalar, Swagger UI, or Redoc on top of the JSON.
```

```csharp
// HybridCache: one call, built-in stampede protection (only one factory runs per key)
builder.Services.AddHybridCache();

public class ProductService(HybridCache cache, ShopDb db)
{
    public ValueTask<ProductDto?> GetAsync(int id, CancellationToken ct) =>
        cache.GetOrCreateAsync($"product:{id}",
            async token => await db.Products
                .Where(p => p.Id == id)
                .Select(p => new ProductDto(p.Id, p.Name, p.Price))
                .FirstOrDefaultAsync(token),
            new HybridCacheEntryOptions { Expiration = TimeSpan.FromMinutes(10) },
            cancellationToken: ct);
}
```

```csharp
// System.Threading.Lock: faster, clearer than lock(object)
private readonly Lock _gate = new();
public void Add(Order o) { lock (_gate) { _orders.Add(o); } }   // uses Lock.EnterScope

// LINQ additions
var perStatus = orders.CountBy(o => o.Status);                      // KeyValuePair<Status,int>
var revenue   = orders.AggregateBy(o => o.CustomerId, 0m, (sum, o) => sum + o.Total);
foreach (var (i, o) in orders.Index()) Console.WriteLine($"{i}: {o.Id}");

// Task.WhenEach: process tasks in completion order
await foreach (var done in Task.WhenEach(calls))
{
    var quote = await done;   // already completed, no extra waiting
}

app.MapStaticAssets();        // replaces UseStaticFiles() for the build-time asset manifest
```

### .NET 10 (LTS, C# 14, released Nov 2025)

> Verified against Microsoft Learn "What's new" pages. For exact API names in new features always cross-check the official release notes.

| Area | What arrived |
|---|---|
| C# 14 | **`field` keyword** (field-backed properties), **extension members** (`extension` blocks: instance/static extension properties and methods), **null-conditional assignment** (`a?.B = x`), `nameof(List<>)`, user-defined compound assignment, partial constructors/events, implicit `Span<T>` conversions, lambda parameter modifiers |
| Minimal APIs | **Built-in validation** (`AddValidation()`, DataAnnotations on query/header/body, `.DisableValidation()`), Server-Sent Events (`TypedResults.ServerSentEvents`) |
| OpenAPI | **OpenAPI 3.1** default (JSON Schema 2020-12), YAML output, XML doc comments pulled into the document |
| Security | Passkey (WebAuthn) support in Identity, auth metrics; cookie auth returns 401/403 instead of redirects for API endpoints |
| Blazor | `[PersistentState]`, circuit state persistence, WebAssembly preloading |
| EF Core 10 | **`LeftJoin` / `RightJoin`** LINQ operators, **named query filters**, complex types mapped to JSON, SQL Server 2025 `vector` and `json` types, `ExecuteUpdateAsync` with a plain lambda, new parameterized-collection translation |
| Runtime | Better JIT inlining and devirtualization, more stack allocation (escape analysis), AVX10.2, Native AOT improvements |
| SDK | `dotnet test` with Microsoft.Testing.Platform, `dnx` one-shot tool runner, file-based apps |

```csharp
// C# 14: field keyword - add logic to an auto-property without a manual backing field
public class Product
{
    public string Sku
    {
        get;
        set => field = value?.Trim().ToUpperInvariant()
                       ?? throw new ArgumentNullException(nameof(value));
    }
}

// C# 14: extension members (properties + static members)
public static class OrderExtensions
{
    extension(IEnumerable<Order> orders)
    {
        public decimal Revenue => orders.Sum(o => o.Total);
        public IEnumerable<Order> Paid() => orders.Where(o => o.IsPaid);
    }
}
var total = myOrders.Paid().Revenue;

// C# 14: null-conditional assignment (assignment only runs if customer != null)
customer?.LastSeenUtc = DateTime.UtcNow;
```

```csharp
// .NET 10 minimal API validation: DataAnnotations are enforced automatically
builder.Services.AddValidation();

public record CreateProductRequest(
    [Required, StringLength(80)] string Name,
    [Range(0.01, 100_000)] decimal Price);

app.MapPost("/products", (CreateProductRequest req) => TypedResults.Created("/products/1", req));
// Invalid body -> 400 ProblemDetails (validation) without any manual code.
```

```csharp
// EF Core 10: LeftJoin (no more GroupJoin + SelectMany + DefaultIfEmpty dance)
var rows = await db.Customers
    .LeftJoin(db.Orders,
        c => c.Id, o => o.CustomerId,
        (c, o) => new { c.Name, OrderId = (int?)o.Id })
    .ToListAsync();

// EF Core 10: named query filters - disable only the one you need
modelBuilder.Entity<Order>()
    .HasQueryFilter("SoftDelete", o => !o.IsDeleted)
    .HasQueryFilter("Tenant", o => o.TenantId == _tenantId);

var withDeleted = await db.Orders.IgnoreQueryFilters(["SoftDelete"]).ToListAsync();
```

### Version comparison cheat sheet

| | .NET 6 | .NET 7 | .NET 8 | .NET 9 | .NET 10 |
|---|---|---|---|---|---|
| Type | LTS | STS | LTS | STS | LTS |
| C# | 10 | 11 | 12 | 13 | 14 |
| Headline | Minimal hosting, hot reload | Rate limiting, output cache, `required` | Primary ctors, keyed DI, AOT, Blazor Web App | Built-in OpenAPI, HybridCache, `Lock` | `field`, extension members, minimal validation, EF `LeftJoin` |
| DI | Constructor/factory | Same | **Keyed services** | Same | Same |
| API docs | Swashbuckle | Swashbuckle | Swashbuckle | **Built-in OpenAPI** | OpenAPI 3.1 |
| Error handling | Middleware | Middleware | **IExceptionHandler** | Same | Same |
| Caching | `IMemoryCache` | **Output cache** | Same | **HybridCache** | Same |

:::q Which .NET version would you choose for a new project today, and why?
The latest LTS, which is .NET 10. It has three years of support, so I do not have to upgrade for compliance reasons within that period. I would pick STS only for a specific feature and only if the team can upgrade within about a year. If the company is still on .NET 8, I would plan the .NET 10 upgrade now because .NET 8 support ends in November 2026.
:::

:::q What are the main things you would mention from .NET 8 for a Web API developer?
Primary constructors and collection expressions in C# 12, keyed services in DI, `TimeProvider` for testable time, `IExceptionHandler` for global exceptions, Native AOT support for minimal APIs, `FrozenDictionary` for read-heavy lookups, and EF Core 8 complex types and primitive collections.
:::

### .NET Framework vs modern .NET

**Definition.** *.NET Framework* (4.8 is the last version) is the Windows-only, closed-servicing runtime that ships with Windows. *Modern .NET* (".NET 5+", formerly .NET Core) is the cross-platform, open-source, side-by-side runtime that gets yearly releases.

| Aspect | .NET Framework 4.x | Modern .NET (6/8/10) |
|---|---|---|
| Platforms | Windows only | Windows, Linux, macOS, containers |
| Development | Closed servicing; only security/reliability fixes | Active; yearly releases, open source on GitHub |
| Web stack | ASP.NET (`System.Web`), MVC 5, Web API 2, IIS only | ASP.NET Core, Kestrel, runs behind IIS/nginx/YARP or standalone |
| Performance | Baseline | Much faster (Span, JIT, PGO, allocations), much lower memory |
| Deployment | Machine-wide install, one version per machine | Side by side, self-contained, single-file, AOT, trimming |
| Config | `web.config`, `app.config` | `appsettings.json`, env vars, user secrets, Key Vault |
| DI | Third-party (Autofac, Unity, Ninject) | Built in |
| Project files | Verbose `.csproj`, `packages.config` | SDK-style `.csproj`, `PackageReference` |
| Data access | EF6, ADO.NET | EF Core, ADO.NET (EF6 also runs on modern .NET) |
| Not available | | Web Forms, WCF server (use **CoreWCF**), .NET Remoting, most `System.Web`, WWF |
| Desktop | WinForms, WPF | WinForms, WPF (Windows only) still supported |
| Containers | Windows containers only | Small Linux images |

```text
.NET Standard 2.0  =  a contract (API surface) that BOTH Framework 4.6.1+ and modern .NET implement
                      -> use it for shared libraries during a migration
.NET 5+ unified    =  one BCL, one SDK for web, desktop, cloud, mobile
```

### Upgrading and migration approach

**Why it matters.** "How would you migrate a legacy ASP.NET MVC 5 / Web API 2 application to .NET 8/10?" is a very common scenario question.

1. **Inventory and assess.** List projects, NuGet packages, and Windows-only dependencies (COM, WCF, `System.Web`, `HttpContext.Current`, GAC, registry). Run **.NET Upgrade Assistant** in analyze mode and the **.NET API analyzer / platform compatibility analyzers** (for example CA1416 for platform-specific APIs).
2. **Get to the SDK-style project format and PackageReference.** Tools: Upgrade Assistant, and the older `try-convert` tool (now archived; prefer Upgrade Assistant or manual conversion). Update packages to versions that support `netstandard2.0` or `net8.0+`.
3. **Move shared libraries first.** Retarget class libraries (domain, data, utilities) to `netstandard2.0`, or multi-target `net48;net10.0`, so Framework and modern apps can both use them.
4. **Migrate the host incrementally.** Use the **strangler fig** pattern: put **YARP** (reverse proxy) in front, route migrated endpoints to the new ASP.NET Core app, leave the rest on the old app. For shared `HttpContext`/session code use `Microsoft.AspNetCore.SystemWebAdapters`.
5. **Replace the plumbing.** `Global.asax` -> `Program.cs`; `HttpModule`/`HttpHandler` -> middleware; `web.config` -> `appsettings.json`; `Web API 2 controllers` -> ASP.NET Core controllers; Unity/Autofac -> built-in DI; EF6 -> EF Core (or keep EF6 temporarily; it runs on modern .NET).
6. **Fix behavioural differences.** No synchronization context (no `.Result` deadlocks, but also no ambient `HttpContext.Current`), different model binding rules, `System.Text.Json` instead of Newtonsoft, case-sensitive routes and file paths on Linux, time zone IDs differ.
7. **Test, then cut over.** Contract tests against both versions, canary traffic with the proxy, performance baseline before and after.

```xml
<!-- Typical retarget for a shared library during migration -->
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFrameworks>net48;net10.0</TargetFrameworks>
    <Nullable>enable</Nullable>
    <LangVersion>latest</LangVersion>
  </PropertyGroup>
</Project>
```

```bash
# Upgrade a project between modern .NET versions
dotnet --list-sdks
dotnet list package --outdated
dotnet list package --vulnerable --include-transitive
# change <TargetFramework>net8.0</TargetFramework> -> net10.0, then:
dotnet build -warnaserror
dotnet test
```

> Tooling note: Microsoft has been moving upgrade guidance toward Visual Studio / GitHub Copilot modernization experiences alongside the .NET Upgrade Assistant. Tool names change, so verify the current recommendation in the official migration docs. The *strategy* (assess, share libraries, strangle, replace plumbing, test) stays the same.

:::scenario Upgrade from .NET 8 to .NET 10 breaks a few things in staging
Read the "breaking changes" list for each version you skip. Typical findings: a behaviour change in a default (for example cookie authentication now returns 401/403 instead of redirecting for API endpoints in .NET 10), obsolete APIs flagged as errors, and package versions pinned to the old target. Fix: upgrade the SDK and `TargetFramework`, update packages together (Microsoft.* packages share the major version), turn warnings into errors temporarily, run the full test suite, and roll out with a canary. Never upgrade runtime and refactor features in the same change.
:::

:::warn Common mistakes
Upgrading only the web project while class libraries still target `net6.0` (works, but you stay on old APIs). Mixing Microsoft.EntityFrameworkCore 10 with a `net8.0` app (EF Core 10 requires the .NET 10 runtime). Forgetting that Docker base images (`mcr.microsoft.com/dotnet/aspnet:10.0`) and CI SDK versions (`global.json`) must be upgraded too.
:::

:::q What is the difference between .NET Framework and .NET (Core)? Why migrate?
.NET Framework is Windows-only and in maintenance mode. Modern .NET is cross-platform, open source, much faster, runs in small Linux containers, supports side-by-side versions, and gets new features every year. We migrate for performance and cost (cheaper Linux hosting), container and cloud-native support, security patches on a supported runtime, and access to new libraries that no longer target Framework.
:::

:::q How would you migrate a big ASP.NET MVC 5 app without a big-bang rewrite?
Assess with the Upgrade Assistant and analyzers, move shared libraries to `netstandard2.0` or multi-target them, put YARP in front, and migrate the app endpoint by endpoint with the strangler fig pattern. Use the System.Web adapters for shared session and `HttpContext` code. Replace `Global.asax`, modules and `web.config` with `Program.cs`, middleware and `appsettings.json`. Test both versions with the same contract tests and switch traffic gradually.
:::
