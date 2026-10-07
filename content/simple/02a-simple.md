### Release model: LTS vs STS

**In simple words:** Microsoft releases a new major .NET version every November. Even numbers (6, 8, 10) are LTS (Long Term Support) and get 3 years of fixes. Odd numbers (7, 9) are STS (Standard Term Support) and now get 2 years. After support ends, you get no more security patches.

**Real-life example:** Think of two phone models. One gets security updates for 3 years, the other for 2 years, and after that it is no longer safe to use.

**Interview question:** Which .NET version would you choose for a new project, and why?

**Simple answer:** I would choose the latest LTS, which is .NET 10 today, because it has three years of support. I pick an STS version only if I need a specific feature and the team can upgrade within about a year. I also plan one upgrade per year, so we never run an unsupported version.

### .NET 6 (LTS, C# 10)

**In simple words:** .NET 6 brought the short startup style that every modern template uses. You set up the whole app in one `Program.cs` file with `WebApplication`, without a `Startup.cs` class. It also added minimal APIs, hot reload (code changes apply while the app runs) and C# 10. Its support ended in November 2024.

**Real-life example:** A bank replaced two long account-opening forms with one short form. You get the same account, with much less writing.

**Interview question:** What did .NET 6 introduce that we still use today?

**Simple answer:** It introduced the minimal hosting model: `WebApplication.CreateBuilder` and a single `Program.cs`. It added minimal APIs with `app.MapGet`, hot reload, and the `DateOnly` and `TimeOnly` types. C# 10 added global usings, file-scoped namespaces and `record struct`.

```csharp
var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();
app.MapGet("/hello", () => "Hello");
app.Run();
```

### .NET 7 (STS, C# 11)

**In simple words:** .NET 7 was a short-support release with useful web features. It added built-in rate limiting, output caching, `MapGroup` route groups and endpoint filters for minimal APIs. C# 11 added `required` properties, and EF Core 7 added `ExecuteUpdate` and `ExecuteDelete` for bulk changes. Its support ended in May 2024.

**Real-life example:** It is like a restaurant's seasonal menu. New dishes appear there first, and the good ones stay on the main menu.

**Interview question:** What are the key features of .NET 7 for API developers?

**Simple answer:** Built-in rate limiting, output caching, route groups, endpoint filters and `TypedResults` for minimal APIs. C# 11 `required` members make the compiler force callers to set them. EF Core 7 can update or delete many rows without loading them first.

```csharp
public class CreateOrderRequest
{
    public required Guid CustomerId { get; init; }  // must be set
}
```

### .NET 8 (LTS, C# 12)

**In simple words:** .NET 8 is a long-support release, and many production apps run on it today. C# 12 added primary constructors and collection expressions like `[1, 2, 3]`. It also added keyed services in DI, `TimeProvider` for testable time, `IExceptionHandler` for global errors and Native AOT (compiling to native machine code) for minimal APIs. Its support ends on 10 November 2026.

**Real-life example:** It is like the car model most taxi companies drive today. Every mechanic must know it well.

**Interview question:** What would you mention from .NET 8 for a Web API developer?

**Simple answer:** Primary constructors and collection expressions, keyed services, `TimeProvider` and `IExceptionHandler`. Also Native AOT for minimal APIs and EF Core 8 complex types. Support ends in November 2026, so I would plan the move to .NET 10.

```csharp
public class OrderService(IOrderRepository repo)   // primary constructor
{
    private static readonly string[] Open = ["Pending", "Paid"];
}
```

### .NET 9 (STS, C# 13)

**In simple words:** .NET 9 is a short-support release. It added built-in OpenAPI document generation with `AddOpenApi()` and `MapOpenApi()`, and Swashbuckle left the Web API template. It added `HybridCache`, which joins a fast in-memory cache with a shared distributed cache. Its support ends on 10 November 2026, the same day as .NET 8.

**Real-life example:** A phone update adds a built-in document scanner. You no longer need a separate scanner app, but you may still add a nicer viewer.

**Interview question:** What changed for API documentation in .NET 9?

**Simple answer:** The Web API template stopped using Swashbuckle. It uses the built-in `Microsoft.AspNetCore.OpenApi` package, which creates the JSON document at `/openapi/v1.json`. There is no UI included, so I add Scalar or Swagger UI on top of that JSON.

### .NET 10 (LTS, C# 14, released Nov 2025)

**In simple words:** .NET 10 is the current long-support release, supported until November 2028. C# 14 added the `field` keyword, extension members and null-conditional assignment (`a?.B = x`). Minimal APIs got built-in validation with `AddValidation()`, and OpenAPI 3.1 became the default. EF Core 10 added `LeftJoin` and named query filters.

**Real-life example:** It is the newest bus model, and the city will service it for three full years. A new route should use this bus.

**Interview question:** What are the main new features in .NET 10 and C# 14?

**Simple answer:** C# 14 adds the `field` keyword, so I can add logic to an auto-property without writing a backing field. It also adds extension members and null-conditional assignment. ASP.NET Core 10 validates minimal API input with `AddValidation()`, and EF Core 10 adds `LeftJoin`.

```csharp
public string Sku
{
    get;
    set => field = value.Trim().ToUpperInvariant();  // C# 14 'field'
}
```

### Version comparison cheat sheet

**In simple words:** This table compares .NET 6 to .NET 10 at a glance. LTS versions are 6, 8 and 10; STS versions are 7 and 9. Each .NET version pairs with a C# version, from C# 10 in .NET 6 up to C# 14 in .NET 10. Remember one or two headline features for each.

**Real-life example:** It is like a summary map of a train network. You do not need every stop, only the main stations of each line.

**Interview question:** Can you summarise .NET 6 to .NET 10 briefly?

**Simple answer:** .NET 6 brought minimal hosting and hot reload, and .NET 7 brought rate limiting and output caching. .NET 8 brought primary constructors, keyed DI and `IExceptionHandler`, and .NET 9 brought built-in OpenAPI and `HybridCache`. .NET 10 brought the `field` keyword, extension members and minimal API validation.

### .NET Framework vs modern .NET

**In simple words:** .NET Framework (last version 4.8) runs only on Windows and gets only security and reliability fixes. Modern .NET (.NET 5 and later, once called .NET Core) runs on Windows, Linux and macOS. It is open source, much faster, and gets a new version every year. Some old parts, like Web Forms and WCF server, are not available in it.

**Real-life example:** An old landline phone still works and gets repairs, but it stays in one room. A smartphone works anywhere and gets new features every year.

**Interview question:** What is the difference between .NET Framework and modern .NET, and why migrate?

**Simple answer:** .NET Framework is Windows-only and in maintenance mode. Modern .NET is cross-platform, open source, faster, and runs in small Linux containers. We migrate for performance, cheaper hosting, supported security patches and access to new libraries.

### Upgrading and migration approach

**In simple words:** You move an old app to modern .NET step by step, not all at once. First, check it with the .NET Upgrade Assistant and move shared libraries to `netstandard2.0` or multi-target them. Then put YARP (a reverse proxy that forwards requests) in front and move endpoints one by one. Old parts get replaced: `Global.asax` becomes `Program.cs`, and `web.config` becomes `appsettings.json`.

**Real-life example:** A hospital renovates one ward at a time while it stays open. Patients move into each new ward when it is ready.

**Interview question:** How would you migrate a big ASP.NET MVC 5 app without a big-bang rewrite?

**Simple answer:** I assess it with the Upgrade Assistant, move shared libraries first, and put YARP in front of the old app. Then I move endpoints to the new ASP.NET Core app one by one; this is the strangler fig pattern. I run the same tests against both versions and switch traffic gradually.

### Application startup and lifecycle

**In simple words:** An ASP.NET Core app is a console app that builds a host. First you register services; then `Build()` creates the DI container, and the list of services is frozen. Then you add middleware and endpoints, and `Run()` starts the web server. On shutdown, the app stops taking new requests, finishes the running ones and stops background services.

**Real-life example:** Before a restaurant opens, the manager hires staff and sets the tables. At closing time, no new guests come in, but seated guests finish their meal.

**Interview question:** What happens between `CreateBuilder` and `app.Run()`?

**Simple answer:** `CreateBuilder` sets up configuration, logging, Kestrel and the service collection. I register services, then `Build()` creates the service provider and freezes the registrations. I add middleware and map endpoints, and `Run()` starts hosted services and Kestrel and waits until shutdown.

### Hosting model and Kestrel

**In simple words:** Kestrel is the web server built into every ASP.NET Core app. It is fast and runs on Windows, Linux and macOS. It can face the internet directly, or sit behind a reverse proxy (a front server like nginx, YARP or IIS). The proxy handles things like HTTPS and load balancing, then forwards requests to Kestrel.

**Real-life example:** Kestrel is the waiter who serves your table. The reverse proxy is the receptionist who greets guests at the door and sends each one to a free waiter.

**Interview question:** What is Kestrel, and why would you put a reverse proxy in front of it?

**Simple answer:** Kestrel is the cross-platform web server that runs inside the ASP.NET Core process. A reverse proxy adds TLS termination, load balancing and protection at the edge. Behind a proxy, I enable forwarded headers, so the app sees the real client IP and the HTTPS scheme.

### Program.cs, fully annotated

**In simple words:** `Program.cs` is the one file that sets up your whole app. Before `Build()`, you register services: options, database, HTTP clients, auth, CORS and more. After `Build()`, you add middleware in the right order and map your endpoints. Finally, `app.Run()` starts everything.

**Real-life example:** It is like a recipe card. The top lists the ingredients, and the bottom lists the cooking steps, where the order matters.

**Interview question:** Walk me through a typical `Program.cs` for a Web API.

**Simple answer:** I create the builder, bind and validate options, and register the DbContext, HTTP clients, my services, controllers, ProblemDetails, CORS, authentication and rate limiting. After `Build()`, I add exception handling, HTTPS, CORS, rate limiting, authentication and authorization, in that order. Then I map controllers and health checks and call `Run()`.

### Configuration system

**In simple words:** Configuration is a set of key/value settings read from many sources and merged into one `IConfiguration`. The sources load in this order: `appsettings.json`, `appsettings.{Environment}.json`, user secrets (Development only), environment variables, then command-line arguments. A later source overrides an earlier one. Nested keys use `:`, and environment variables use `__` instead.

**Real-life example:** A school has national rules, school rules and class rules. When they disagree, the most specific rule, applied last, wins.

**Interview question:** Where do configuration values come from, and which one wins?

**Simple answer:** From `appsettings.json`, then the environment file, then user secrets in Development, then environment variables, then the command line. The last source wins, so the command line has the highest priority. I keep secrets out of files and use Key Vault or environment variables in production.

```bash
export Payment__Retries=5
dotnet run --Payment:Retries=7
```

### Options pattern

**In simple words:** The options pattern binds a config section to a typed C# class, so you stop reading raw strings from `IConfiguration`. `IOptions<T>` reads the value once and never reloads. `IOptionsSnapshot<T>` is scoped and gives a fresh value per request. `IOptionsMonitor<T>` is a singleton that sees changes live.

**Real-life example:** Instead of giving each worker the whole company handbook, you give each one a small card with only the settings they need.

**Interview question:** What is the difference between `IOptions`, `IOptionsSnapshot` and `IOptionsMonitor`?

**Simple answer:** `IOptions` is a singleton that reads the value once. `IOptionsSnapshot` is scoped, gives a fresh value per request, and cannot be injected into a singleton. `IOptionsMonitor` is a singleton with live values and change events; I also add `ValidateOnStart()` so bad config fails at startup.

```csharp
builder.Services.AddOptions<PaymentOptions>()
    .Bind(builder.Configuration.GetSection("Payment"))
    .ValidateDataAnnotations()
    .ValidateOnStart();
```

### User secrets and secret management

**In simple words:** User secrets keep a developer's passwords and keys outside the project folder, so they never reach git. You manage them with the `dotnet user-secrets` command. They are stored as plain text in your user profile and load only in the Development environment. In production, use Azure Key Vault or environment variables instead.

**Real-life example:** You keep your house key in your pocket, not taped to the front door where every visitor can see it.

**Interview question:** What are user secrets, and can you use them in production?

**Simple answer:** User secrets store development-only secrets in a JSON file outside the repository. They are not encrypted and load only in Development, so they are not for production. In production, I use Azure Key Vault with a managed identity, or secrets injected by the platform.

```bash
dotnet user-secrets init
dotnet user-secrets set "Payment:ApiKey" "sk_test_123"
```

### IHostedService and BackgroundService

**In simple words:** A hosted service runs background work for the whole life of the app. `BackgroundService` is a base class where you write one method, `ExecuteAsync`. Hosted services are singletons, so create a scope with `IServiceScopeFactory` to use a `DbContext`. By default, an unhandled exception in `ExecuteAsync` stops the whole app, so catch errors inside your loop.

**Real-life example:** A night guard walks around the building every hour while it is open. At closing time, the guard finishes the round and goes home.

**Interview question:** How do you write a background job in ASP.NET Core, and what are the pitfalls?

**Simple answer:** I inherit from `BackgroundService`, loop in `ExecuteAsync` with a `PeriodicTimer`, and pass the `stoppingToken` to every call. For scoped services like `DbContext`, I create a new scope in each iteration. I catch exceptions inside the loop, because an unhandled one stops the whole host.

### Dependency injection and lifetimes in ASP.NET Core (summary)

**In simple words:** ASP.NET Core has dependency injection built in. You register a service with a lifetime, and the framework creates and disposes it for you. Singleton means one object for the whole app, scoped means one per HTTP request, and transient means a new one every time.

**Real-life example:** In a hotel, every guest shares the lobby (singleton). Your room key works only for your stay (scoped), and a paper napkin is new each time you take one (transient).

**Interview question:** In one line each, what are `AddSingleton`, `AddScoped` and `AddTransient`?

**Simple answer:** Singleton gives one instance for the app's lifetime, which suits caches and config. Scoped gives one instance per HTTP request, which is why `DbContext` is scoped. Transient gives a new instance every time, which suits small stateless helpers.

### The request pipeline and middleware ordering

**In simple words:** Middleware is a small component that every request passes through, in the order you add it. Each one can do work before and after calling the next one. It can also stop the request early (short-circuit) by not calling `next`. The response travels back through the same components in reverse order.

**Real-life example:** At an airport you pass check-in, passport control, security and then the gate. If the gate checked you before passport control, it would not know who you are.

**Interview question:** Why does middleware order matter? Give an example.

**Simple answer:** Each middleware only sees what earlier ones did. The exception handler must come first to catch everything, and authentication must come before authorization, or every user looks anonymous. CORS must come before auth, so 401 responses still carry CORS headers.

```csharp
app.UseExceptionHandler();
app.UseHttpsRedirection();
app.UseCors("Frontend");
app.UseAuthentication();
app.UseAuthorization();
app.MapControllers();
```

### Creating custom middleware

**In simple words:** You can write middleware as an inline `app.Use` lambda, as a class, or as a class that implements `IMiddleware`. A normal class needs a constructor with `RequestDelegate next` and an `InvokeAsync(HttpContext)` method. It is created only once, so scoped services, like `DbContext`, go in `InvokeAsync` parameters. `IMiddleware` classes are created by DI for each request instead.

**Real-life example:** A shop has one door guard for the whole day. The guard does not keep one shopping basket for everyone; each customer gets their own basket.

**Interview question:** How do you write custom middleware, and how do you use a scoped service in it?

**Simple answer:** I write a class with a constructor taking `RequestDelegate next` and a public `InvokeAsync(HttpContext context)` method, then register it with `app.UseMiddleware<T>()`. Because it is created once, scoped services go into `InvokeAsync` parameters, not the constructor. The other option is `IMiddleware`, which I register in DI.

```csharp
public class TenantMiddleware(RequestDelegate next)
{
    public async Task InvokeAsync(HttpContext ctx, ITenantStore store) // scoped: OK here
    {
        await next(ctx);
    }
}
```

### Example 1: Exception middleware

**In simple words:** This middleware wraps the rest of the pipeline in a `try/catch`. When an error happens, it logs it once and picks the right status code: 404 for not found, 409 for conflict, 500 for unknown errors. It returns a standard ProblemDetails JSON body and never shows stack traces in production. Register it early, so it catches errors from everything after it.

**Real-life example:** A hospital has one central desk for emergencies from every ward. The family gets a clear, calm message, not the doctor's private notes.

**Interview question:** How do you handle exceptions globally in a Web API?

**Simple answer:** I use `AddProblemDetails()` with an `IExceptionHandler` and `app.UseExceptionHandler()`, or my own exception middleware placed first. It maps domain exceptions to 404, 409 or 422 and logs 500 errors with a trace ID. It returns RFC 9457 ProblemDetails and hides internal details outside Development.

### Example 2: Request/response logging middleware

**In simple words:** This middleware writes one log line per request with the method, path, status code and time taken. It can also log small JSON bodies by buffering the request and swapping the response stream. Body logging uses memory, breaks streaming, and can leak passwords or card numbers. Prefer the built-in `AddHttpLogging()`, which supports field lists and redaction (hiding sensitive values).

**Real-life example:** A shop's visitor book records the time, who came in and what they bought. It must never record their card PIN.

**Interview question:** How would you log requests and responses, and what are the risks?

**Simple answer:** I log method, path, status, duration, user ID and correlation ID for every request. Logging bodies uses memory, breaks streaming, and can leak passwords or card data. So I use the built-in HTTP logging with field lists and redaction, and log bodies only when really needed.

### Example 3: Correlation ID middleware

**In simple words:** A correlation ID is one unique ID for each request. The middleware reads it from the `X-Correlation-ID` header, or creates a new one. It adds the ID to every log line, to the response header and to calls made to other services. Then you can follow one user action across many services.

**Real-life example:** A parcel has one tracking number. Every post office scans it, so you can see the parcel's full journey.

**Interview question:** What is a correlation ID, and how do you implement it?

**Simple answer:** It is an ID that follows one request through all logs and services. Middleware reads or creates it, puts it in a logging scope, and adds it to the response header. A `DelegatingHandler` adds it to outgoing `HttpClient` calls; modern apps also use the W3C `traceparent` header with OpenTelemetry.

### Example 4: API-key authentication middleware

**In simple words:** Some APIs are called by other programs, not people, and they send a secret key in an `X-Api-Key` header. The middleware checks the key, creates a user (a `ClaimsPrincipal`) for that client, or returns 401. Store only hashes of the keys, and compare them in constant time so timing leaks nothing. In production, write an `AuthenticationHandler` instead, so `[Authorize]` works normally.

**Real-life example:** A delivery company's van has an access card for the warehouse gate. The card identifies the company, not a single driver.

**Interview question:** How would you protect machine-to-machine endpoints with API keys?

**Simple answer:** I write a custom `AuthenticationHandler`, so `[Authorize]` and policies work normally. I store SHA-256 hashes of the keys, compare them with `FixedTimeEquals`, rotate keys, and rate-limit each key. API keys identify an application; for real users, I use JWT bearer tokens.

### The five MVC filter types

**In simple words:** Filters run inside MVC after routing has picked a controller action. There are five types, in this order: Authorization, Resource, Action, Exception and Result. Model binding happens between the Resource and Action filters. Any filter can stop the rest by setting `context.Result`.

**Real-life example:** In a restaurant, a guard checks your booking, the host checks for a ready meal, and the waiter works before and after the cook. The manager handles kitchen accidents, and each plate is checked before serving.

**Interview question:** Explain the filter execution order.

**Simple answer:** Authorization filters run first, then Resource filters, then model binding, then Action filters around the action method. Exception filters run only if something threw, then Result filters run around writing the response. Within one type, global filters run first, then controller filters, then action filters.

### Sync vs async filters and custom filters

**In simple words:** Each filter type has a sync interface and an async interface. Implement only one; if you implement both, only the async one runs. Use async when you need `await`, for example to call a database. In an async action filter, code before `await next()` runs before the action, and code after it runs after.

**Real-life example:** A teacher can mark homework on the spot (sync), or take it home and return it tomorrow (async). They should not do both for the same homework.

**Interview question:** How do you write a custom async action filter?

**Simple answer:** I implement `IAsyncActionFilter` and its `OnActionExecutionAsync` method. I do the "before" work, call `await next()` to run the action, then do the "after" work. To skip the action, I set `context.Result` and do not call `next`.

```csharp
public class TimingFilter : IAsyncActionFilter
{
    public async Task OnActionExecutionAsync(
        ActionExecutingContext ctx, ActionExecutionDelegate next)
    {
        var sw = Stopwatch.StartNew();   // before
        await next();                    // the action runs here
    }
}
```

### Registering filters and DI (Global / Controller / Action)

**In simple words:** You can apply a filter globally, to one controller, or to one action. Global filters go in `AddControllers(o => o.Filters.Add<T>())`. Attributes accept only constant values, so a normal attribute cannot get services in its constructor. Use `[ServiceFilter]` or `[TypeFilter]` when a filter needs DI services.

**Real-life example:** `[ServiceFilter]` is like asking a hospital for a nurse already on the staff list. `[TypeFilter]` is like the hospital creating a new helper role for you, and you can add special notes.

**Interview question:** How do you inject a service into a filter attribute?

**Simple answer:** A normal attribute cannot receive DI services. I use `[ServiceFilter(typeof(MyFilter))]`, where the filter must be registered in DI, or `[TypeFilter(typeof(MyFilter))]`, where the framework builds it and resolves its dependencies. `TypeFilter` also lets me pass extra constant arguments.

### Filters vs middleware

**In simple words:** Middleware runs for every request, including static files and health checks, and sees only the raw `HttpContext`. Filters run only for MVC controller actions. They can see the chosen action, its arguments, `ModelState` and the result. For minimal APIs, the filter-like option is an endpoint filter.

**Real-life example:** Middleware is the main gate of an office building that everyone passes. A filter is a rule at one office door, met only by visitors to that office.

**Interview question:** When do you use middleware and when do you use a filter?

**Simple answer:** If the logic is global and does not need MVC details, I use middleware, for example for errors, CORS or correlation IDs. If it must know which action runs, or check its arguments or result, I use a filter. Per-action auditing and caching a few GET actions are good filter cases.
