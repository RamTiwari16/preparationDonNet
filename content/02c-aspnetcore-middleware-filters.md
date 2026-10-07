## Middleware

### The request pipeline and middleware ordering

**Definition.** *Middleware* is a component in the HTTP request pipeline. Each one receives the `HttpContext` and a `next` delegate. It can do work **before** calling `next`, call the rest of the pipeline, and do work **after** it returns. It can also **short-circuit** by not calling `next`.

**Why it matters.** Cross-cutting behaviour (errors, HTTPS, CORS, authentication, logging, rate limiting) lives here. The most common production bug is **wrong order**: for example `UseAuthorization` before `UseAuthentication`, or CORS after the endpoint.

```text
            +--------------------------------------------------------------+
Request --> | ExceptionHandler -> HTTPS -> StaticFiles -> Routing -> CORS  |
            |   -> RateLimiter -> Authentication -> Authorization          |
            |   -> custom middleware -> Endpoint (controller / minimal API)|
Response <- | <---------------- same components, reverse order ----------- |
            +--------------------------------------------------------------+
Code after `await next()` runs on the way OUT (response phase).
```

**Recommended order** (from the official guidance, adapted):

| # | Middleware | Why here |
|---|---|---|
| 1 | `UseForwardedHeaders` | Fix scheme/IP before anything reads them |
| 2 | `UseExceptionHandler` / custom exception middleware, `UseHsts` | Must wrap everything below to catch its exceptions |
| 3 | `UseHttpsRedirection` | Redirect HTTP to HTTPS early |
| 4 | `UseStaticFiles` / `MapStaticAssets` | Short-circuits static requests before routing and auth |
| 5 | `UseRouting` (implicit with `WebApplication`) | Selects the endpoint, so later middleware can read endpoint metadata |
| 6 | `UseCors` | After routing, **before** auth, so preflight and error responses get CORS headers |
| 7 | `UseRateLimiter`, `UseOutputCache` | After routing so per-endpoint policies work |
| 8 | `UseAuthentication` | Builds `HttpContext.User` |
| 9 | `UseAuthorization` | Checks `[Authorize]` using the user and endpoint metadata |
| 10 | Custom middleware that needs the user | Correlation ID can be earlier; tenant resolution after auth |
| 11 | `MapControllers` / `MapGet` ... | Terminal endpoints |

:::warn Ordering bugs interviewers love
`UseAuthorization` before `UseAuthentication`: every request is anonymous, so `[Authorize]` always returns 401. `UseCors` after `UseAuthorization`: the 401/403 has no CORS headers, so the browser shows a confusing CORS error instead of the real one. `UseExceptionHandler` registered late: exceptions from earlier middleware escape.
:::

#### Use, Run, Map, UseWhen, MapWhen

```csharp
// Use: can call next (pass-through)
app.Use(async (context, next) =>
{
    // before
    await next();
    // after (response phase)
});

// Run: TERMINAL, never calls next. Always last in its branch.
app.Run(async context => await context.Response.WriteAsync("end of line"));

// Map: branch by PATH. The branch does NOT rejoin the main pipeline.
app.Map("/internal", branch =>
    branch.Run(async ctx => await ctx.Response.WriteAsync("internal only")));

// UseWhen: conditional middleware that REJOINS the main pipeline afterwards.
app.UseWhen(ctx => ctx.Request.Path.StartsWithSegments("/api"),
    branch => branch.UseMiddleware<ApiKeyMiddleware>());

// MapWhen: branch on any predicate, does NOT rejoin.
app.MapWhen(ctx => ctx.Request.Headers.ContainsKey("X-Debug"),
    branch => branch.Run(async ctx => await ctx.Response.WriteAsync("debug")));

// Short-circuit example: cheap liveness probe, skips everything below it
app.Use(async (ctx, next) =>
{
    if (ctx.Request.Path == "/ping") { await ctx.Response.WriteAsync("pong"); return; }
    await next();
});
```

### Creating custom middleware

Three ways, same pipeline concept:

| | Inline `app.Use` | Convention-based class | `IMiddleware` (factory-based) |
|---|---|---|---|
| Shape | Lambda | Class with ctor `(RequestDelegate next, ...)` and `InvokeAsync(HttpContext, ...)` | Class implementing `IMiddleware.InvokeAsync(HttpContext, RequestDelegate)` |
| Instantiated | Once | **Once** (like a singleton) | **Per request** from DI |
| Ctor dependencies | Closure | Singleton-safe services only | Any lifetime, including scoped |
| Scoped services | `ctx.RequestServices` | Add as **parameters of `InvokeAsync`** | Constructor |
| Registration | none | `app.UseMiddleware<T>()` | `services.AddTransient<T>()` **and** `app.UseMiddleware<T>()` |
| Best for | Tiny things, demos | Most real middleware | Middleware that needs scoped services in the constructor, or per-request state |

```csharp
// Convention-based: the shape the runtime looks for
public class MyMiddleware(RequestDelegate next /* + singleton services */)
{
    public async Task InvokeAsync(HttpContext context, IScopedThing scoped /* per request */)
    {
        // before
        await next(context);
        // after
    }
}

// IMiddleware: resolved from DI for every request
public class TenantMiddleware(ShopDbContext db) : IMiddleware   // scoped dependency OK
{
    public async Task InvokeAsync(HttpContext context, RequestDelegate next)
    {
        var tenant = context.Request.Headers["X-Tenant-Id"].ToString();
        context.Items["Tenant"] = await db.Tenants.FindAsync(tenant);
        await next(context);
    }
}
builder.Services.AddScoped<TenantMiddleware>();    // registration is mandatory
app.UseMiddleware<TenantMiddleware>();
```

:::warn Constructor injection of scoped services in convention middleware
The middleware instance lives for the whole app. Injecting `DbContext` in its constructor creates a **captive dependency** (and throws under scope validation). Put scoped services on `InvokeAsync` parameters, or use `IMiddleware`.
:::

### Example 1: Exception middleware

**Goal.** Catch every unhandled exception, log it once with context, map known domain exceptions to proper HTTP codes, and return an RFC 9457 `application/problem+json` body without leaking internals.

```csharp
// Domain exceptions the API throws deliberately
public class NotFoundException(string message) : Exception(message);
public class ConflictException(string message) : Exception(message);
public class DomainValidationException(IDictionary<string, string[]> errors)
    : Exception("One or more validation errors occurred.")
{
    public IDictionary<string, string[]> Errors { get; } = errors;
}

public sealed class ExceptionHandlingMiddleware(
    RequestDelegate next,
    ILogger<ExceptionHandlingMiddleware> logger,
    IHostEnvironment env)
{
    public async Task InvokeAsync(HttpContext context)
    {
        try
        {
            await next(context);
        }
        catch (OperationCanceledException) when (context.RequestAborted.IsCancellationRequested)
        {
            // Client went away. Not an application error. 499 = "client closed request".
            logger.LogInformation("Request cancelled by client: {Path}", context.Request.Path);
            context.Response.StatusCode = 499;
        }
        catch (Exception ex) when (!context.Response.HasStarted)
        {
            // If the response already started we cannot change status/body; let it propagate
            await HandleAsync(context, ex);
        }
    }

    private async Task HandleAsync(HttpContext context, Exception ex)
    {
        var (status, title) = ex switch
        {
            DomainValidationException => (StatusCodes.Status400BadRequest, "Validation failed"),
            NotFoundException         => (StatusCodes.Status404NotFound, "Resource not found"),
            ConflictException         => (StatusCodes.Status409Conflict, "Conflict"),
            UnauthorizedAccessException => (StatusCodes.Status403Forbidden, "Forbidden"),
            _                         => (StatusCodes.Status500InternalServerError,
                                          "An unexpected error occurred")
        };

        var traceId = Activity.Current?.Id ?? context.TraceIdentifier;

        if (status >= 500)
            logger.LogError(ex, "Unhandled exception. TraceId={TraceId}", traceId);
        else
            logger.LogWarning("Handled {ExceptionType}: {Message}. TraceId={TraceId}",
                ex.GetType().Name, ex.Message, traceId);

        // Never leak internals for 500s outside Development
        var detail = status >= 500 && !env.IsDevelopment() ? null : ex.Message;

        var extensions = new Dictionary<string, object?> { ["traceId"] = traceId };
        if (ex is DomainValidationException v) extensions["errors"] = v.Errors;

        // Response has not started (checked in the catch filter), so status/body can still change
        await Results.Problem(
                statusCode: status,
                title: title,
                detail: detail,
                instance: context.Request.Path,
                extensions: extensions)
            .ExecuteAsync(context);
    }
}

// Registration: early, so it wraps everything below
app.UseMiddleware<ExceptionHandlingMiddleware>();
```

**Modern alternative (recommended for new apps).** Use the built-in `UseExceptionHandler` with an `IExceptionHandler` (.NET 8, shown in the .NET versions topic) plus `AddProblemDetails()`. It integrates with diagnostics and the `IProblemDetailsService`. Hand-written exception middleware is still the standard interview question, and is common in existing codebases.

### Example 2: Request/response logging middleware

**Goal.** Log one structured line per request (method, path, status, duration) and, for small JSON bodies, the request and response payloads. Redact sensitive paths.

```csharp
public sealed class RequestResponseLoggingMiddleware(
    RequestDelegate next,
    ILogger<RequestResponseLoggingMiddleware> logger)
{
    private const int MaxBodyChars = 4096;
    private static readonly string[] SensitivePaths = ["/api/auth", "/api/payments"];

    public async Task InvokeAsync(HttpContext context)
    {
        var sw = Stopwatch.StartNew();
        var request = context.Request;
        var sensitive = SensitivePaths.Any(p => request.Path.StartsWithSegments(p));

        // ---- request body (rewindable) ----
        string? requestBody = null;
        if (!sensitive && IsText(request.ContentType) && request.ContentLength is > 0)
        {
            request.EnableBuffering();                       // buffer so MVC can read it again
            requestBody = await ReadAsync(request.Body);
            request.Body.Position = 0;                       // rewind for the real consumer
        }

        // ---- capture response by swapping the body stream ----
        var originalBody = context.Response.Body;
        await using var buffer = new MemoryStream();
        context.Response.Body = buffer;

        try
        {
            await next(context);
        }
        finally
        {
            sw.Stop();

            string? responseBody = null;
            buffer.Position = 0;
            if (!sensitive && IsText(context.Response.ContentType))
                responseBody = await ReadAsync(buffer);

            buffer.Position = 0;
            await buffer.CopyToAsync(originalBody);          // MUST copy back to the client
            context.Response.Body = originalBody;

            var status = context.Response.StatusCode;
            logger.Log(
                status >= 500 ? LogLevel.Error : status >= 400 ? LogLevel.Warning : LogLevel.Information,
                "HTTP {Method} {Path} -> {StatusCode} in {ElapsedMs} ms | req={RequestBody} res={ResponseBody}",
                request.Method, request.Path.Value, status, sw.ElapsedMilliseconds,
                requestBody, responseBody);
        }
    }

    private static bool IsText(string? contentType) =>
        contentType is not null &&
        (contentType.Contains("json", StringComparison.OrdinalIgnoreCase) ||
         contentType.StartsWith("text/", StringComparison.OrdinalIgnoreCase));

    private static async Task<string> ReadAsync(Stream stream)
    {
        using var reader = new StreamReader(stream, Encoding.UTF8,
            detectEncodingFromByteOrderMarks: false, bufferSize: 1024, leaveOpen: true);
        var chars = new char[MaxBodyChars];
        var read = await reader.ReadBlockAsync(chars, 0, chars.Length);
        return new string(chars, 0, read);                   // truncated to MaxBodyChars
    }
}
```

:::warn Body logging is dangerous
It buffers whole responses in memory, breaks streaming/SSE/file downloads, can log passwords, tokens and card data (PII/PCI), and costs latency. In production log metadata only (method, path, status, duration, user id, correlation id) and enable body logging per request via a flag. The built-in `AddHttpLogging()` + `UseHttpLogging()` does this with `HttpLoggingFields`, header allow-lists and redaction, so prefer it over hand-rolled body capture.
:::

### Example 3: Correlation ID middleware

**Goal.** Give every request one ID that appears in **every log line**, in the **response header**, and is **forwarded to downstream HTTP calls**, so you can trace one user action across services.

```csharp
public sealed class CorrelationIdMiddleware(
    RequestDelegate next, ILogger<CorrelationIdMiddleware> logger)
{
    public const string HeaderName = "X-Correlation-ID";
    public const string ItemKey = "CorrelationId";

    public async Task InvokeAsync(HttpContext context)
    {
        var correlationId = GetOrCreate(context);

        context.Items[ItemKey] = correlationId;       // for DelegatingHandlers, filters, services
        context.TraceIdentifier = correlationId;      // ProblemDetails traceId matches

        // Add the header just before the response starts (works even if an exception is handled later)
        context.Response.OnStarting(() =>
        {
            context.Response.Headers[HeaderName] = correlationId;
            return Task.CompletedTask;
        });

        // Every log written inside this scope carries CorrelationId
        using (logger.BeginScope(new Dictionary<string, object>
               { ["CorrelationId"] = correlationId }))
        {
            await next(context);
        }
    }

    private static string GetOrCreate(HttpContext ctx)
    {
        if (ctx.Request.Headers.TryGetValue(HeaderName, out var values))
        {
            var candidate = values.ToString();
            if (IsSafe(candidate)) return candidate;       // trust but validate (log injection)
        }
        return Guid.NewGuid().ToString("N");
    }

    private static bool IsSafe(string s) =>
        s.Length is > 0 and <= 64 &&
        s.All(c => char.IsAsciiLetterOrDigit(c) || c is '-' or '_');
}

public static class CorrelationIdExtensions
{
    public static IApplicationBuilder UseCorrelationId(this IApplicationBuilder app) =>
        app.UseMiddleware<CorrelationIdMiddleware>();
}
```

```csharp
// Propagate the ID to outgoing HttpClient calls
public sealed class CorrelationIdHandler(IHttpContextAccessor accessor) : DelegatingHandler
{
    protected override Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request, CancellationToken ct)
    {
        if (accessor.HttpContext?.Items[CorrelationIdMiddleware.ItemKey] is string id &&
            !request.Headers.Contains(CorrelationIdMiddleware.HeaderName))
        {
            request.Headers.Add(CorrelationIdMiddleware.HeaderName, id);
        }
        return base.SendAsync(request, ct);
    }
}

// Program.cs
builder.Services.AddHttpContextAccessor();
builder.Services.AddTransient<CorrelationIdHandler>();
builder.Services.AddHttpClient<IInventoryClient, InventoryClient>(c =>
        c.BaseAddress = new Uri("https://inventory.internal"))
    .AddHttpMessageHandler<CorrelationIdHandler>();

builder.Logging.AddSimpleConsole(o => o.IncludeScopes = true);   // so the scope prints

app.UseCorrelationId();            // right after forwarded headers, before exception handling
```

```text
// Console output with scopes:
info: OrderService[0]
      => CorrelationId:9f1c2a4b...
      Order 1042 created
```

**Notes.** Serilog users do `using (LogContext.PushProperty("CorrelationId", id))` instead of `BeginScope`. .NET also ships `Microsoft.AspNetCore.HeaderPropagation` (`AddHeaderPropagation`, `UseHeaderPropagation`, `AddHeaderPropagation()` on the HttpClient) for the forwarding part. Modern tracing uses the W3C `traceparent` header and `Activity` (ASP.NET Core creates one automatically; OpenTelemetry propagates it), and many teams log `Activity.Current.TraceId` instead of a custom header.

### Example 4: API-key authentication middleware

**Goal.** Protect machine-to-machine endpoints with an `X-Api-Key` header. Compare in constant time, store only hashes, build a `ClaimsPrincipal`, and honour `[AllowAnonymous]`.

```csharp
public class ApiKeyOptions
{
    public List<ApiClient> Clients { get; set; } = [];
}
public record ApiClient(string Id, string Name, string KeySha256Hex, string[] Roles);

public sealed class ApiKeyMiddleware(
    RequestDelegate next, IOptionsMonitor<ApiKeyOptions> options)
{
    public const string HeaderName = "X-Api-Key";

    public async Task InvokeAsync(HttpContext context)
    {
        // Endpoint metadata is available because routing already ran.
        var endpoint = context.GetEndpoint();
        if (endpoint?.Metadata.GetMetadata<IAllowAnonymous>() is not null)
        {
            await next(context);
            return;
        }

        if (!context.Request.Headers.TryGetValue(HeaderName, out var provided) ||
            provided.Count != 1)
        {
            await Reject(context, "API key is missing.");
            return;
        }

        var client = Find(provided.ToString());
        if (client is null)
        {
            await Reject(context, "API key is invalid.");
            return;
        }

        var claims = new List<Claim>
        {
            new(ClaimTypes.NameIdentifier, client.Id),
            new(ClaimTypes.Name, client.Name)
        };
        claims.AddRange(client.Roles.Select(r => new Claim(ClaimTypes.Role, r)));

        context.User = new ClaimsPrincipal(new ClaimsIdentity(claims, authenticationType: "ApiKey"));
        await next(context);
    }

    private ApiClient? Find(string rawKey)
    {
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(rawKey));
        foreach (var c in options.CurrentValue.Clients)
        {
            var stored = Convert.FromHexString(c.KeySha256Hex);
            if (CryptographicOperations.FixedTimeEquals(hash, stored))   // no timing leak
                return c;
        }
        return null;
    }

    private static Task Reject(HttpContext ctx, string detail)
    {
        ctx.Response.Headers.WWWAuthenticate = "ApiKey";
        return Results.Problem(statusCode: 401, title: "Unauthorized", detail: detail)
                      .ExecuteAsync(ctx);
    }
}

app.UseMiddleware<ApiKeyMiddleware>();   // after routing, before UseAuthorization
app.UseAuthorization();
```

**The "proper" version** is an authentication *handler*, because then `[Authorize]`, policies and `AuthenticateAsync` all work uniformly:

```csharp
public class ApiKeyAuthHandler(
    IOptionsMonitor<AuthenticationSchemeOptions> opt, ILoggerFactory logger, UrlEncoder enc,
    IApiKeyValidator validator) : AuthenticationHandler<AuthenticationSchemeOptions>(opt, logger, enc)
{
    protected override async Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        if (!Request.Headers.TryGetValue("X-Api-Key", out var key))
            return AuthenticateResult.NoResult();              // let other schemes try

        var principal = await validator.ValidateAsync(key.ToString());
        return principal is null
            ? AuthenticateResult.Fail("Invalid API key")
            : AuthenticateResult.Success(new AuthenticationTicket(principal, Scheme.Name));
    }
}

builder.Services.AddAuthentication("ApiKey")
    .AddScheme<AuthenticationSchemeOptions, ApiKeyAuthHandler>("ApiKey", null);
```

:::tip Say this in the interview
"I would write middleware to show the concept, but in production I implement an `AuthenticationHandler` so that `[Authorize]` and policies work. I store only SHA-256 hashes of keys, compare with `FixedTimeEquals`, rotate keys, and use per-key rate limits. For user-facing APIs I use JWT bearer instead; API keys identify an application, not a person."
:::

:::q Difference between `app.Use`, `app.Run`, `app.Map`?
`Use` adds middleware that can call `next` and so continues the pipeline. `Run` adds terminal middleware that never calls `next`. `Map` branches the pipeline on a path prefix and the branch does not rejoin the main pipeline. `UseWhen` is the conditional version that does rejoin.
:::

:::q Why does middleware order matter? Give an example.
Each middleware only sees what earlier ones produced and wraps what comes after. The exception handler must be first to catch everything. Authentication must precede authorization or every `[Authorize]` call fails. CORS must precede auth so that 401 responses still carry CORS headers.
:::

## Filters

### The five MVC filter types

**Definition.** *Filters* run **inside** the MVC / Web API action invocation pipeline, after routing has chosen a controller action. They have access to MVC concepts that middleware does not: action arguments, `ModelState`, `ActionDescriptor`, the `IActionResult`.

| Filter type | Interfaces (sync / async) | Runs | Typical use | Short-circuit by |
|---|---|---|---|---|
| **Authorization** | `IAuthorizationFilter` / `IAsyncAuthorizationFilter` | First | Custom permission/tenant checks | `context.Result = ...` |
| **Resource** | `IResourceFilter` / `IAsyncResourceFilter` | After authz, **before model binding**; wraps everything after | Response caching, feature flags, skip expensive binding | `context.Result` |
| **Action** | `IActionFilter` / `IAsyncActionFilter` | Right **before and after the action method**, after model binding | Logging, timing, argument validation, idempotency | `context.Result` in executing |
| **Exception** | `IExceptionFilter` / `IAsyncExceptionFilter` | When action, action filters or binding throw | Map domain exceptions to responses | `context.ExceptionHandled = true` |
| **Result** | `IResultFilter` / `IAsyncResultFilter` | Before/after the **result executes** (serialisation) | Add headers, wrap payloads | `context.Cancel = true` |

```text
Request
 -> Routing picks the action
    -> [1] Authorization filters
       -> [2] Resource filters   OnResourceExecuting
          -> Model binding + model validation ([ApiController] 400 happens here)
             -> [3] Action filters   OnActionExecuting
                   ACTION METHOD
                [3] Action filters   OnActionExecuted      (reverse order)
             -> [4] Exception filters   (only if something above threw)
             -> [5] Result filters   OnResultExecuting
                   Result executes (e.g. JSON serialised to the response)
                [5] Result filters   OnResultExecuted
          [2] Resource filters   OnResourceExecuted
Response
```

**Short-circuiting:**

- An authorization filter that sets `context.Result` (usually 401/403): nothing after it runs.
- A resource filter that sets `context.Result` (for example a cache hit): model binding, action and action filters are skipped; ordinary result filters are skipped too (only `IAlwaysRunResultFilter` ones run), and the outer resource filters' "executed" side still runs.
- An action filter that sets `context.Result` in `OnActionExecuting`: the action is skipped; result filters still run.
- An exception filter that sets `ExceptionHandled = true` and a `Result`: the exception is swallowed and that result is executed.
- Exception filters do **not** catch exceptions thrown in resource filters, result filters or result execution. Middleware does.

#### Order within one filter type: scopes

Filters run in the order **Global -> Controller -> Action** on the way in, and reverse on the way out (an onion). The `Order` property (lower runs first) overrides scope order.

```text
Global filter A   (registered in AddControllers)
Global filter B
Controller filter C   ([MyFilter] on the class)
Action filter D       ([MyFilter] on the method)

A.OnActionExecuting
  B.OnActionExecuting
    C.OnActionExecuting
      D.OnActionExecuting
          [ Action method ]
      D.OnActionExecuted
    C.OnActionExecuted
  B.OnActionExecuted
A.OnActionExecuted
```

### Sync vs async filters and custom filters

Implement **either** the sync or the async interface of the same filter type, not both. If both exist, only the async one is called. Use async when you need `await` (database, cache, HTTP).

```csharp
// Action filter: timing + audit. Created via DI, so it can take any services.
public sealed class AuditActionFilter(
    ILogger<AuditActionFilter> logger, IAuditStore store) : IAsyncActionFilter
{
    public async Task OnActionExecutionAsync(
        ActionExecutingContext context, ActionExecutionDelegate next)
    {
        var sw = Stopwatch.StartNew();
        var action = context.ActionDescriptor.DisplayName;
        var user = context.HttpContext.User.Identity?.Name ?? "anonymous";

        // BEFORE the action: model binding is done, arguments are available
        if (context.ActionArguments.TryGetValue("request", out var arg) && arg is null)
        {
            context.Result = new BadRequestObjectResult("Body is required"); // short-circuit
            return;
        }

        ActionExecutedContext executed = await next();       // runs the action (and inner filters)

        // AFTER the action
        sw.Stop();
        var status = (executed.Result as ObjectResult)?.StatusCode
                     ?? (executed.Result as StatusCodeResult)?.StatusCode;
        logger.LogInformation("{Action} by {User} took {Ms} ms (status {Status})",
            action, user, sw.ElapsedMilliseconds, status);

        if (executed.Exception is null)
            await store.WriteAsync(user, action, sw.ElapsedMilliseconds);

        context.HttpContext.Response.Headers["X-Elapsed-Ms"] =
            sw.ElapsedMilliseconds.ToString();               // result not yet written: safe
    }
}
```

```csharp
// Authorization filter: custom check, never throw, set Result
[AttributeUsage(AttributeTargets.Class | AttributeTargets.Method)]
public sealed class RequireTenantHeaderAttribute : Attribute, IAuthorizationFilter
{
    public void OnAuthorization(AuthorizationFilterContext context)
    {
        if (!context.HttpContext.Request.Headers.ContainsKey("X-Tenant-Id"))
            context.Result = new BadRequestObjectResult(
                new ProblemDetails { Status = 400, Title = "X-Tenant-Id header is required" });
    }
}

// Exception filter: map domain exceptions in MVC only
public sealed class DomainExceptionFilter(ILogger<DomainExceptionFilter> log) : IExceptionFilter
{
    public void OnException(ExceptionContext context)
    {
        if (context.Exception is not ConflictException ex) return;   // not ours: bubble up
        log.LogWarning(ex, "Conflict");
        context.Result = new ObjectResult(
            new ProblemDetails { Status = 409, Title = "Conflict", Detail = ex.Message })
        { StatusCode = 409 };
        context.ExceptionHandled = true;
    }
}

// Resource filter: skip the whole action on a cache hit
public sealed class CacheResourceFilter(IMemoryCache cache) : IAsyncResourceFilter
{
    public async Task OnResourceExecutionAsync(
        ResourceExecutingContext context, ResourceExecutionDelegate next)
    {
        var key = context.HttpContext.Request.Path + context.HttpContext.Request.QueryString;
        if (cache.TryGetValue(key, out IActionResult? hit) && hit is not null)
        {
            context.Result = hit;                            // short-circuit: no binding, no action
            return;
        }
        var executed = await next();
        if (executed.Result is ObjectResult { StatusCode: null or 200 } ok)
            cache.Set(key, ok, TimeSpan.FromSeconds(30));
    }
}

// Result filter: add a header to every result
public sealed class ApiVersionHeaderFilter : IResultFilter
{
    public void OnResultExecuting(ResultExecutingContext context) =>
        context.HttpContext.Response.Headers["X-Api-Version"] = "1.0";
    public void OnResultExecuted(ResultExecutedContext context) { }
}
```

### Registering filters and DI (Global / Controller / Action)

```csharp
// Global: all controllers
builder.Services.AddControllers(o =>
{
    o.Filters.Add<DomainExceptionFilter>();        // type filter: built per use, deps from DI
    o.Filters.Add(new ApiVersionHeaderFilter());   // an instance (shared, no dependencies)
});
builder.Services.AddSingleton<IAuditStore, SqlAuditStore>();
builder.Services.AddScoped<AuditActionFilter>();   // needed for [ServiceFilter]

// Controller / action scope
[ApiController, Route("api/orders")]
[ServiceFilter(typeof(AuditActionFilter))]         // whole controller
public class OrdersController : ControllerBase
{
    [HttpGet("{id}")]
    [RequireTenantHeader]                          // one action
    [TypeFilter(typeof(CacheResourceFilter))]
    public IActionResult Get(int id) => Ok();
}
```

| | `[ServiceFilter(typeof(T))]` | `[TypeFilter(typeof(T))]` | Filter instance as attribute |
|---|---|---|---|
| Who creates the filter | DI container | `ObjectFactory` (activator) | You, via `new` / attribute |
| Must `T` be registered in DI? | **Yes** | No (its *dependencies* are resolved from DI) | n/a |
| Lifetime | Follows the registration (can be singleton/scoped) | New instance per use (unless `IsReusable`) | Cached for the app (attributes are instantiated once) |
| Extra constructor args | No | **Yes**, `Arguments = new object[] { ... }` | Constants only |
| Use when | Filter needs DI and you want lifetime control | Filter needs DI **and** static args | Filter has no dependencies |

```csharp
[TypeFilter(typeof(AuditFilter), Arguments = new object[] { "Orders" })]
```

Attributes can only take compile-time constants, so a normal `[MyFilter]` attribute **cannot** receive DI services through its constructor. That is exactly why `ServiceFilter`/`TypeFilter` (or `IFilterFactory`) exist.

### Filters vs middleware

| | Middleware | Filters |
|---|---|---|
| Scope | **Every** request (static files, minimal APIs, SignalR, health checks) | Only requests handled by MVC controllers / Razor Pages |
| Position | Before routing/MVC, outer layer | Inside MVC after routing |
| Sees | `HttpContext` (raw request/response) | `HttpContext` + `ModelState`, action arguments, `ActionDescriptor`, `IActionResult` |
| Granularity | Whole app or a branch | Global, controller or single action via attributes |
| Order control | Registration order | Scope + `Order` property |
| Typical use | Exceptions, CORS, auth, logging, correlation ID, rate limiting | Per-action auditing, validation, result shaping, caching, idempotency |

**Rule of thumb.** If it does not need MVC context, write middleware. If it must know *which action* is running or inspect arguments/results, write a filter. For minimal APIs the equivalent of an action filter is an **endpoint filter** (`IEndpointFilter`, `AddEndpointFilter`), covered in the minimal API topic.

:::scenario Every action needs the same audit log, but only some need caching
Use a **global** async action filter for audit (it needs `ActionDescriptor` and the user), and a `[TypeFilter]`/`[ServiceFilter]` resource filter attribute on the few read-heavy GET actions. Do not put audit in middleware if you need the action name; do not put caching in an action filter, because by then model binding has already run. The resource filter can skip it.
:::

:::q Explain the filter execution order.
Authorization, then Resource (before), then model binding, then Action (before), the action, Action (after), Exception filters if something threw, Result (before), result execution, Result (after), Resource (after). Within a type, filters run Global then Controller then Action on the way in and reverse on the way out. Setting `context.Result` in a filter short-circuits the rest.
:::

:::q When would you use an exception filter instead of exception middleware?
Almost never for new code. An exception filter only sees exceptions thrown inside MVC action execution, not from other middleware or minimal APIs, and it does not have the full diagnostics integration. I use `IExceptionHandler` or exception middleware globally, and an exception filter only when I need to map an exception differently depending on the controller or action.
:::

:::q How do you inject a service into a filter attribute?
Attributes cannot take DI parameters in their constructors. Use `[ServiceFilter(typeof(MyFilter))]` (filter registered in DI) or `[TypeFilter(typeof(MyFilter))]` (the framework builds it and resolves its dependencies, and you can pass extra arguments), or implement `IFilterFactory`.
:::
