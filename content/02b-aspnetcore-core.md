## ASP.NET Core

### Application startup and lifecycle

**Definition.** An ASP.NET Core app is a console app that builds a **host**. The host owns configuration, logging, dependency injection, the web server (Kestrel) and background services. `WebApplication` (introduced in .NET 6) is the single type that is both the host and the request pipeline builder.

**Why it matters.** Almost every "explain Program.cs" or "what happens when a request arrives" question starts here. You must know the *build phase* (register services) versus the *run phase* (handle requests), because nothing in the DI container can be changed after `Build()`.

```text
dotnet run
 |
 |-- 1. WebApplication.CreateBuilder(args)
 |        config sources, logging, Kestrel defaults, DI container *builder*
 |-- 2. builder.Services.AddXxx(...)        REGISTER services (nothing is created yet)
 |-- 3. var app = builder.Build()           ServiceProvider built, registrations frozen
 |-- 4. app.UseXxx() / app.MapXxx()         compose middleware pipeline + endpoints
 |-- 5. app.Run()                           start hosted services, start Kestrel,
 |                                          BLOCK until shutdown
 |
 Request:  Kestrel -> middleware 1 -> 2 -> ... -> endpoint -> back out through them
 Shutdown: SIGTERM / Ctrl+C
           -> ApplicationStopping fires
           -> Kestrel stops accepting new connections, drains in-flight requests
           -> IHostedService.StopAsync (reverse registration order)
           -> ServiceProvider disposed (IDisposable singletons disposed)
           -> process exits
```

**What `CreateBuilder` configures for you:**

- **Kestrel** as the server (plus IIS in-process integration when hosted on IIS).
- **Configuration** from `appsettings.json`, `appsettings.{Environment}.json`, user secrets (Development), environment variables, command line.
- **Logging** providers: Console, Debug, EventSource (and EventLog on Windows), filtered by the `Logging` config section.
- **DI container** with *scope validation* and *build validation* turned on when the environment is Development.
- **Content root** = current directory, **web root** = `wwwroot`.

```csharp
// Hooks into the host lifetime
var app = builder.Build();

app.Lifetime.ApplicationStarted.Register(() =>
    app.Logger.LogInformation("App started, listening on {Urls}", string.Join(",", app.Urls)));
app.Lifetime.ApplicationStopping.Register(() =>
    app.Logger.LogInformation("Stopping: finishing in-flight requests..."));
app.Lifetime.ApplicationStopped.Register(() =>
    app.Logger.LogInformation("Stopped."));

app.Run();
```

#### Program.cs (minimal hosting) vs Startup.cs (old model)

| | `Startup.cs` (.NET Core 2/3, .NET 5) | `Program.cs` minimal hosting (.NET 6+) |
|---|---|---|
| Services | `ConfigureServices(IServiceCollection)` | `builder.Services.AddXxx()` |
| Pipeline | `Configure(IApplicationBuilder)` | `app.UseXxx()` / `app.MapXxx()` |
| Host type | `IHost` + `IWebHostBuilder` | `WebApplication` |
| Routing | Explicit `UseRouting()` + `UseEndpoints()` | Implicit (added automatically); call `UseRouting()` only to control its position |
| Boilerplate | Two classes | Top-level statements, one file |

The old `Startup` model still works (`UseStartup<T>()`), and many enterprise codebases still use it. Know both.

### Hosting model and Kestrel

**Definition.** **Kestrel** is the cross-platform, in-process web server built into ASP.NET Core. It can be the edge server or sit behind a reverse proxy.

| Hosting option | How it works | When to use |
|---|---|---|
| Kestrel standalone | Kestrel listens on the public port | Containers, Kubernetes ingress terminates TLS in front |
| Reverse proxy (nginx, YARP, Azure Front Door/App Gateway) | Proxy handles TLS, load balancing, static caching; forwards to Kestrel | Most Linux production setups |
| IIS **in-process** | App runs inside `w3wp.exe`, ASP.NET Core Module hands requests directly to the app (default since 3.0) | Windows/IIS, best IIS performance |
| IIS **out-of-process** | IIS proxies to a separate Kestrel process | When you need process isolation or run several apps in one app pool |
| HTTP.sys | Windows kernel-mode server | Windows-only features such as Windows auth with kernel mode, port sharing |

```csharp
// Kestrel tuning in code
builder.WebHost.ConfigureKestrel(k =>
{
    k.Limits.MaxRequestBodySize = 10 * 1024 * 1024;          // 10 MB
    k.Limits.KeepAliveTimeout   = TimeSpan.FromMinutes(2);
    k.AddServerHeader = false;                                // do not leak "Server: Kestrel"
});

// Behind a proxy: trust X-Forwarded-For / X-Forwarded-Proto so scheme/IP are correct
builder.Services.Configure<ForwardedHeadersOptions>(o =>
    o.ForwardedHeaders = ForwardedHeaders.XForwardedFor | ForwardedHeaders.XForwardedProto);
app.UseForwardedHeaders();      // must be FIRST in the pipeline
```

```json
{
  "Kestrel": {
    "Endpoints": {
      "Http": { "Url": "http://0.0.0.0:8080" }
    }
  }
}
```

:::tip Containers
Official .NET 8+ container images run as a non-root user and listen on port **8080** (`ASPNETCORE_HTTP_PORTS=8080`), not 80. Map the port in Docker/Kubernetes accordingly.
:::

### Program.cs, fully annotated

```csharp
using System.Threading.RateLimiting;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;

// (1) Builder: loads config (appsettings + env + args), logging, DI container builder.
var builder = WebApplication.CreateBuilder(args);

// (2) Strongly typed, validated configuration. Fail fast at startup if invalid.
builder.Services.AddOptions<PaymentOptions>()
    .Bind(builder.Configuration.GetSection("Payment"))
    .ValidateDataAnnotations()
    .ValidateOnStart();

// (3) Infrastructure
builder.Services.AddDbContext<ShopDbContext>(o =>
    o.UseSqlServer(builder.Configuration.GetConnectionString("ShopDb")));   // Scoped
builder.Services.AddMemoryCache();
builder.Services.AddHttpClient<IPaymentGateway, StripeGateway>((sp, http) =>
{
    var opt = sp.GetRequiredService<IOptions<PaymentOptions>>().Value;
    http.BaseAddress = new Uri(opt.BaseUrl);
    http.Timeout = TimeSpan.FromSeconds(opt.TimeoutSeconds);
});
builder.Services.AddHealthChecks().AddDbContextCheck<ShopDbContext>();

// (4) Application services (lifetimes matter: see Section 3)
builder.Services.AddScoped<IOrderService, OrderService>();
builder.Services.AddSingleton(TimeProvider.System);
builder.Services.AddHostedService<OutboxPublisher>();

// (5) Web concerns
builder.Services.AddControllers();
builder.Services.AddProblemDetails();                       // RFC 9457 error bodies
builder.Services.AddExceptionHandler<GlobalExceptionHandler>();
builder.Services.AddOpenApi();

builder.Services.AddCors(o => o.AddPolicy("Frontend", p => p
    .WithOrigins("https://shop.example.com")
    .AllowAnyHeader().AllowAnyMethod()));

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(o =>
    {
        o.Authority = builder.Configuration["Auth:Authority"];
        o.Audience  = builder.Configuration["Auth:Audience"];
    });
builder.Services.AddAuthorization();

builder.Services.AddRateLimiter(o =>
{
    o.RejectionStatusCode = StatusCodes.Status429TooManyRequests;
    o.GlobalLimiter = PartitionedRateLimiter.Create<HttpContext, string>(ctx =>
        RateLimitPartition.GetFixedWindowLimiter(
            ctx.User.Identity?.Name ?? ctx.Connection.RemoteIpAddress?.ToString() ?? "anon",
            _ => new FixedWindowRateLimiterOptions
            { PermitLimit = 100, Window = TimeSpan.FromMinutes(1) }));
});

// (6) Build: the container is now frozen and (in Development) validated.
var app = builder.Build();

// (7) Middleware pipeline: ORDER MATTERS (see the middleware section)
app.UseForwardedHeaders();
if (app.Environment.IsDevelopment())
    app.MapOpenApi();
else
{
    app.UseExceptionHandler();        // uses IExceptionHandler + ProblemDetails
    app.UseHsts();
}
app.UseHttpsRedirection();
app.UseCors("Frontend");              // after routing (implicit), before auth
app.UseRateLimiter();
app.UseAuthentication();              // who are you?
app.UseAuthorization();               // what may you do?

// (8) Endpoints
app.MapControllers();
app.MapHealthChecks("/health");

// (9) Run: start hosted services + Kestrel, block until shutdown
app.Run();

public partial class Program { }      // lets WebApplicationFactory<Program> see the entry point
```

### Configuration system

**Definition.** Configuration is a set of **key/value pairs** read from multiple *providers* and merged into one `IConfiguration`. Hierarchical keys use `:` (for example `Payment:TimeoutSeconds`). **Later providers override earlier ones.**

**Default precedence (lowest to highest) for `WebApplication.CreateBuilder`:**

| Order | Source | Notes |
|---|---|---|
| 1 | `appsettings.json` | Base values, committed to source control |
| 2 | `appsettings.{Environment}.json` | Overrides per environment (Development, Staging, Production) |
| 3 | **User secrets** | Only when environment is Development |
| 4 | **Environment variables** | Use `__` for `:` (`ConnectionStrings__ShopDb`). Best for containers |
| 5 | **Command-line arguments** | `--Payment:TimeoutSeconds=10`. Highest priority |

```json
{
  "ConnectionStrings": { "ShopDb": "Server=.;Database=Shop;Trusted_Connection=True;" },
  "Payment": { "BaseUrl": "https://api.pay.example.com", "TimeoutSeconds": 15, "Retries": 3 },
  "Logging": { "LogLevel": { "Default": "Information", "Microsoft.AspNetCore": "Warning" } }
}
```

```csharp
// Reading configuration
string cs   = builder.Configuration.GetConnectionString("ShopDb")!;
int timeout = builder.Configuration.GetValue<int>("Payment:TimeoutSeconds", 30);
var section = builder.Configuration.GetSection("Payment");
var opts    = section.Get<PaymentOptions>();                  // bind to POCO

// Add more providers; later = higher priority
builder.Configuration
    .AddJsonFile("featureflags.json", optional: true, reloadOnChange: true)
    .AddEnvironmentVariables(prefix: "SHOP_");               // SHOP_Payment__Retries=5
```

```bash
# Same key set three ways; the last one wins
#   appsettings.json:            "Payment": { "Retries": 3 }
export Payment__Retries=5                      # env var   -> 5
dotnet run --Payment:Retries=7                 # CLI       -> 7 (wins)
```

**Rules of thumb:**

- Non-secret defaults go in `appsettings.json`; per-environment differences in `appsettings.{Env}.json`; **secrets never go in either**.
- In Azure use App Service settings, Key Vault references, or `AddAzureKeyVault` with managed identity.
- Arrays merge by index across providers, which surprises people: `Cors:Origins:0` from one file and `Cors:Origins:0` from env vars overwrite each other, not append.

#### Environments and ASPNETCORE_ENVIRONMENT

| Variable | Used by |
|---|---|
| `ASPNETCORE_ENVIRONMENT` | Web apps (`Development`, `Staging`, `Production`, or custom) |
| `DOTNET_ENVIRONMENT` | Non-web generic host apps (workers) |

- If neither is set, the environment is **Production** (safe default).
- `launchSettings.json` sets `ASPNETCORE_ENVIRONMENT=Development` for `dotnet run`/F5 only. It is **not deployed**.
- Code: `app.Environment.IsDevelopment()`, `IsStaging()`, `IsProduction()`, `IsEnvironment("UAT")`.
- Development turns on: developer exception page, DI scope validation, user secrets, detailed errors. Never run Production with these.

### Options pattern

**Definition.** Bind a configuration section to a strongly typed class and inject it, instead of reading `IConfiguration["Payment:BaseUrl"]` everywhere.

**Why it matters.** Type safety, validation at startup, reload support, easy to test (`Options.Create(new PaymentOptions { ... })`).

```csharp
public class PaymentOptions
{
    public const string SectionName = "Payment";

    [Required, Url] public string BaseUrl { get; set; } = "";
    [Range(1, 120)] public int TimeoutSeconds { get; set; } = 30;
    [Range(0, 10)]  public int Retries { get; set; } = 3;
}

builder.Services.AddOptions<PaymentOptions>()
    .Bind(builder.Configuration.GetSection(PaymentOptions.SectionName))
    .ValidateDataAnnotations()
    .Validate(o => o.TimeoutSeconds * o.Retries < 300, "Total retry time too high")
    .ValidateOnStart();            // validate when the host starts, not on first use
```

| Interface | Lifetime | Reloads on change? | Use when |
|---|---|---|---|
| `IOptions<T>` | Singleton | No (value fixed at first read) | Settings never change at runtime. Safe in singletons |
| `IOptionsSnapshot<T>` | **Scoped** | Yes, once per request | Per-request fresh values. **Cannot be injected into singletons** |
| `IOptionsMonitor<T>` | Singleton | Yes, live + `OnChange` callback | Singletons/background services that need live values |

```csharp
public class CheckoutService(IOptionsSnapshot<PaymentOptions> opt)   // scoped service: OK
{
    public int Retries => opt.Value.Retries;
}

public class OutboxPublisher(IOptionsMonitor<PaymentOptions> opt)   // singleton: use Monitor
{
    public TimeSpan Timeout => TimeSpan.FromSeconds(opt.CurrentValue.TimeoutSeconds);
}
```

```csharp
// Custom validation with IValidateOptions (can use DI)
public class PaymentOptionsValidator : IValidateOptions<PaymentOptions>
{
    public ValidateOptionsResult Validate(string? name, PaymentOptions o) =>
        o.BaseUrl.StartsWith("https://")
            ? ValidateOptionsResult.Success
            : ValidateOptionsResult.Fail("Payment:BaseUrl must use HTTPS");
}
builder.Services.AddSingleton<IValidateOptions<PaymentOptions>, PaymentOptionsValidator>();

// Named options: several configs of the same type
builder.Services.Configure<PaymentOptions>("stripe", builder.Configuration.GetSection("Stripe"));
builder.Services.Configure<PaymentOptions>("paypal", builder.Configuration.GetSection("PayPal"));
// inject IOptionsMonitor<PaymentOptions> and call .Get("stripe")
```

:::warn Gotchas
Injecting `IOptionsSnapshot<T>` into a singleton throws "Cannot consume scoped service" under scope validation. `IOptions<T>` never refreshes, so changing the config file does nothing until restart. Without `ValidateOnStart()` a bad config only fails on first use, often in production at 2 a.m. .NET 8 added a source generator (`[OptionsValidator]`) for reflection-free, AOT-friendly validation.
:::

### User secrets and secret management

**Definition.** *User secrets* store developer-only secrets **outside the project folder** so they are never committed.

```bash
dotnet user-secrets init                       # adds <UserSecretsId> to the .csproj
dotnet user-secrets set "Payment:ApiKey" "sk_test_123"
dotnet user-secrets set "ConnectionStrings:ShopDb" "Server=.;Database=Shop;..."
dotnet user-secrets list
```

- Stored at `%APPDATA%\Microsoft\UserSecrets\<id>\secrets.json` (Windows) or `~/.microsoft/usersecrets/<id>/secrets.json`.
- They are **plain text on disk**, not encrypted. They are a convenience for local development only.
- Loaded automatically only when the environment is Development, and they sit above `appsettings*.json` in precedence.
- In production use environment variables injected by the platform, **Azure Key Vault** with managed identity, or Kubernetes Secrets (ideally from an external secret store).

### IHostedService and BackgroundService

**Definition.** A hosted service is a long-running component started and stopped by the host. `BackgroundService` is a base class that gives you one method, `ExecuteAsync`, running for the lifetime of the app.

```csharp
// Outbox publisher: polls the DB every 5 seconds and publishes pending events.
public class OutboxPublisher(
    IServiceScopeFactory scopeFactory,
    ILogger<OutboxPublisher> log) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(5));

        while (await timer.WaitForNextTickAsync(stoppingToken))
        {
            try
            {
                // Hosted services are SINGLETONS: create a scope per unit of work
                // to use scoped services such as DbContext.
                await using var scope = scopeFactory.CreateAsyncScope();
                var db  = scope.ServiceProvider.GetRequiredService<ShopDbContext>();
                var bus = scope.ServiceProvider.GetRequiredService<IMessageBus>();

                var pending = await db.OutboxMessages
                    .Where(m => m.ProcessedAt == null)
                    .OrderBy(m => m.Id).Take(50)
                    .ToListAsync(stoppingToken);

                foreach (var msg in pending)
                {
                    await bus.PublishAsync(msg.Type, msg.Payload, stoppingToken);
                    msg.ProcessedAt = DateTime.UtcNow;
                }
                await db.SaveChangesAsync(stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;                                   // normal shutdown
            }
            catch (Exception ex)
            {
                log.LogError(ex, "Outbox iteration failed");   // keep the loop alive
            }
        }
    }
}

builder.Services.AddHostedService<OutboxPublisher>();
```

**Behaviour to know:**

- Hosted services start in **registration order** and stop in **reverse order**. `StartAsync` must return quickly (heavy synchronous work before the first `await` blocks host startup; use `await Task.Yield()` first if needed).
- If `ExecuteAsync` throws an unhandled exception, the default (`BackgroundServiceExceptionBehavior.StopHost`, since .NET 6) is to **stop the whole host**. Catch exceptions inside the loop.
- .NET 8 added `IHostedLifecycleService` with `StartingAsync/StartedAsync/StoppingAsync/StoppedAsync` hooks.
- For queued work from requests use `System.Threading.Channels` or a real broker, not `Task.Run` fire-and-forget.

#### Graceful shutdown

```csharp
builder.Services.Configure<HostOptions>(o =>
    o.ShutdownTimeout = TimeSpan.FromSeconds(30));   // default 30s in .NET 6+
```

1. A signal arrives (SIGTERM from Kubernetes or Docker, Ctrl+C, IIS app-pool recycle).
2. `ApplicationStopping` fires; Kestrel stops accepting new connections and lets in-flight requests finish.
3. Each hosted service's `stoppingToken` is cancelled and `StopAsync` is awaited, within `ShutdownTimeout`.
4. After the timeout the host stops waiting and the process exits, so unfinished work is lost.

:::scenario Pods are killed mid-request during a rolling deployment
Symptoms: a few 502s on every deploy. Causes: the ingress still routes to a terminating pod, or in-flight requests exceed the grace period. Fix: handle SIGTERM (default in the host), set `terminationGracePeriodSeconds` greater than `HostOptions.ShutdownTimeout`, add a readiness probe that fails when `ApplicationStopping` fires, pass `HttpContext.RequestAborted` / the `stoppingToken` through all async calls, and make message handlers idempotent so a retry after a hard kill is safe.
:::

### Dependency injection and lifetimes in ASP.NET Core (summary)

ASP.NET Core has DI built in; the full treatment (registration APIs, captive dependencies, `DbContext` lifetime) is in the **Dependency Injection** section. The 20-second version:

| Lifetime | Created | Disposed | Typical use |
|---|---|---|---|
| **Singleton** | Once per app | At shutdown | Config, caches, `HttpClient` factory, `TimeProvider` |
| **Scoped** | Once per HTTP request (scope) | End of request | `DbContext`, unit of work, per-request services |
| **Transient** | Every time it is requested | End of the owning scope | Lightweight stateless helpers |

```csharp
app.MapGet("/ping", (IServiceProvider sp) =>
{
    // HttpContext.RequestServices is the per-request scope's provider
    return Results.Ok();
});
```

:::q What happens between `CreateBuilder` and `app.Run()`?
`CreateBuilder` creates the host builder and sets up configuration, logging and Kestrel defaults. I register services on `builder.Services`. `Build()` creates the service provider and freezes registrations; in Development it also validates scopes. Then I add middleware and map endpoints. `Run()` starts hosted services and Kestrel and blocks until the host shuts down.
:::

:::q Where do configuration values come from and which one wins?
From `appsettings.json`, then `appsettings.{Environment}.json`, then user secrets in Development, then environment variables, then command-line arguments. Later sources override earlier ones, so command line wins. I keep secrets out of files and use user secrets locally and Key Vault or env vars in production.
:::

:::q IOptions vs IOptionsSnapshot vs IOptionsMonitor?
`IOptions` is a singleton that reads once and never reloads. `IOptionsSnapshot` is scoped and gives a fresh value per request, but cannot go into singletons. `IOptionsMonitor` is a singleton with `CurrentValue` and `OnChange`, so it works in singletons and background services. I always add `ValidateDataAnnotations().ValidateOnStart()` so a bad config fails at startup.
:::
