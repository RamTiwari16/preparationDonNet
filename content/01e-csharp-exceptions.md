## Exception Handling

### try, catch, finally, throw

**Definition.** An *exception* is an object (derived from `System.Exception`) that represents a runtime error and unwinds the call stack until a matching `catch` block handles it. `try` guards code, `catch` handles a specific exception type, `finally` runs cleanup, `throw` raises (or re-raises) an exception.

**Why it matters.** It separates the happy path from error handling, and guarantees cleanup of connections, files and locks. Interviewers use it to test whether you understand *stack unwinding*, `throw` vs `throw ex`, and where to handle errors in a layered API.

**How it works.** When `throw` executes, the CLR searches up the call stack for a compatible `catch`. `catch` blocks are tested **top to bottom**, so put specific types first (a general `catch (Exception)` before a specific one is compile error CS0160). `finally` runs whether the `try` completed normally, returned, or threw.

```csharp
public async Task<Order> PlaceOrderAsync(OrderRequest req, CancellationToken ct)
{
    ArgumentNullException.ThrowIfNull(req);              // guard clause (.NET 6+)
    await using var tx = await _db.Database.BeginTransactionAsync(ct);
    try
    {
        var order = await _orders.CreateAsync(req, ct);
        await _db.SaveChangesAsync(ct);
        await tx.CommitAsync(ct);
        return order;
    }
    catch (DbUpdateConcurrencyException ex)              // specific first
    {
        throw new ConflictException("Order was modified by someone else.", ex);
    }
    catch (OperationCanceledException)                   // not an error: let it flow
    {
        throw;
    }
    catch (Exception ex)                                 // last resort, then rethrow
    {
        _logger.LogError(ex, "PlaceOrder failed for customer {CustomerId}", req.CustomerId);
        throw;
    }
    finally
    {
        _metrics.OrderAttempts.Add(1);                   // always runs
    }
}
```

**Rules to remember**

- `try` needs at least one `catch` or a `finally`; `try/finally` with no `catch` is valid and common.
- `finally` does **not** run if the process dies (`Environment.FailFast`, stack overflow, power loss, `Environment.Exit` in most cases). A `StackOverflowException` cannot be caught.
- Never `return`/`throw` from `finally` — an exception thrown in `finally` *replaces* the one in flight and hides the root cause.
- Expected failures that are cheap to test (`null`, parse, dictionary lookup) should use the *Try-pattern* (`int.TryParse`, `dict.TryGetValue`), not exceptions.

| Exception | Throw it when |
|---|---|
| `ArgumentNullException` / `ArgumentException` / `ArgumentOutOfRangeException` | A parameter is invalid (use `ThrowIfNull`, `ThrowIfNegative`, `ThrowIfNullOrEmpty` helpers) |
| `InvalidOperationException` | The object is in the wrong state for this call |
| `NotSupportedException` | The operation is intentionally unsupported |
| `KeyNotFoundException` | A key lookup fails (indexer on `Dictionary`) |
| `ObjectDisposedException` | Using an object after `Dispose` (`ObjectDisposedException.ThrowIf`) |
| `OperationCanceledException` | Cancellation was requested (see async section) |
| `NotImplementedException` | Placeholder only — never ship it |

The hierarchy is `Exception` → `SystemException` (CLR/BCL errors) and `Exception` → your own types. `ApplicationException` is a legacy base class; derive custom exceptions from `Exception`.

### throw vs throw ex

**Definition.** Inside a `catch`, `throw;` re-raises the *same* exception and keeps its original stack trace. `throw ex;` re-raises it as if thrown from *this line*, destroying the original stack trace.

```csharp
try { ProcessPayment(); }
catch (Exception ex)
{
    _logger.LogError(ex, "Payment failed");
    throw;            // GOOD: stack trace still points to ProcessPayment internals
    // throw ex;      // BAD:  stack trace now starts at this catch block
}

try { ProcessPayment(); }
catch (Exception ex)
{
    throw new PaymentException("Card was declined.", ex);   // GOOD: ex kept as InnerException
}
```

```text
throw;     -> at PaymentGateway.Charge() <- at OrderService.Pay() <- at Controller.Post()
throw ex;  -> at OrderService.Pay()      <- at Controller.Post()      (root cause lost)
```

To rethrow an exception *outside* its `catch` (e.g. after a thread hop or storing it), use `ExceptionDispatchInfo.Capture(ex).Throw()`, which preserves the original stack. This is what `await` does internally.

:::q What is the difference between throw and throw ex?
`throw;` rethrows the current exception preserving its stack trace. `throw ex;` resets the stack trace to the current line so you lose where it really originated. I always use `throw;`, or wrap it in a new exception passing the original as `innerException`.
:::

### Exception filters (when)

**Definition.** A `catch ... when (condition)` clause only catches the exception if the condition is true. The filter runs **before the stack is unwound**.

```csharp
try { await _http.GetAsync(url, ct); }
catch (HttpRequestException ex) when (ex.StatusCode == HttpStatusCode.TooManyRequests)
{
    await Task.Delay(TimeSpan.FromSeconds(2), ct);        // only for 429
}
catch (SqlException ex) when (ex.Number is 1205 or -2)    // deadlock victim or timeout
{
    // retry
}
catch (Exception ex) when (Log(ex))                       // Log returns false: never catches
{ }
```

**Why better than `catch` + `if` + `throw;`:** no catch/rethrow cost, the original stack and locals stay intact for debuggers and crash dumps, and non-matching exceptions are simply not caught.

### using, IDisposable and IAsyncDisposable

**Definition.** `using` guarantees `Dispose()` is called, even when an exception is thrown. It compiles to `try { ... } finally { resource.Dispose(); }`.

```csharp
using (var conn = new SqlConnection(cs)) { ... }          // classic block

using var reader = new StreamReader(path);                // C# 8: disposed at end of scope
await using var tx = await db.Database.BeginTransactionAsync(ct);   // IAsyncDisposable

public sealed class ReportExporter : IDisposable
{
    private readonly Stream _stream = File.Create("report.csv");
    private bool _disposed;
    public void Dispose()
    {
        if (_disposed) return;
        _stream.Dispose();
        _disposed = true;
    }
}
```

Implement `IDisposable` when your class *owns* unmanaged resources or other disposables. You rarely need a finalizer — wrap native handles in `SafeHandle`. With DI, the container disposes instances **it** creates; do not `Dispose` things it injected.

### Custom exceptions

**Definition.** A custom exception is a domain-specific type deriving from `Exception`, so callers can `catch` it specifically and your global handler can map it to an HTTP status.

**Rules.** Name ends with `Exception`; provide the standard constructor set (parameterless, message, message + inner); add extra data as read-only properties; do not add the old serialization constructor (obsolete since .NET 8, `SYSLIB0051`).

```csharp
public class OrderException : Exception
{
    public OrderException() { }
    public OrderException(string message) : base(message) { }
    public OrderException(string message, Exception inner) : base(message, inner) { }
}

public sealed class InsufficientStockException : OrderException
{
    public int ProductId { get; }
    public int Requested { get; }
    public int Available { get; }

    public InsufficientStockException(int productId, int requested, int available)
        : base($"Product {productId}: requested {requested}, only {available} left.")
        => (ProductId, Requested, Available) = (productId, requested, available);
}

public sealed class NotFoundException(string entity, object key)
    : Exception($"{entity} '{key}' was not found.");      // C# 12 primary constructor
public sealed class ConflictException(string message, Exception? inner = null)
    : Exception(message, inner);
```

Create a custom type only when someone needs to *react differently* to it (catch it, or map it to a status code). A tiny set (`NotFound`, `Validation`, `Conflict`, `Forbidden`) covers most APIs; a 40-class hierarchy is noise.

### Global exception handling in ASP.NET Core

**Definition.** One central place that catches every unhandled exception from the pipeline, logs it, and converts it into a consistent HTTP response, so controllers contain no `try/catch` boilerplate.

```text
Request -> [ExceptionHandler middleware] -> Routing -> Auth -> Controller/Endpoint
                  ^                                                |
                  +--------------- exception propagates -----------+
          -> IExceptionHandler chain -> ProblemDetails JSON (status 4xx/5xx)
```

| Approach | Scope | Use when |
|---|---|---|
| `IExceptionHandler` (.NET 8+) | Whole pipeline, DI-friendly, chainable | **Default choice** in new code |
| Custom middleware (`try { await next(ctx); } catch`) | Whole pipeline | Pre-.NET 8 apps, full control of the response |
| `UseExceptionHandler("/error")` / lambda | Whole pipeline | Quick, re-executes to an error endpoint |
| MVC `IExceptionFilter` | Only MVC actions | Controller-specific behaviour |
| `UseDeveloperExceptionPage` | Whole pipeline | Development only (auto-on in Development) |

#### IExceptionHandler + ProblemDetails (.NET 8+)

```csharp
public sealed class GlobalExceptionHandler(
    ILogger<GlobalExceptionHandler> logger,
    IProblemDetailsService problemDetails) : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(
        HttpContext ctx, Exception ex, CancellationToken ct)
    {
        var (status, title) = ex switch
        {
            NotFoundException   => (StatusCodes.Status404NotFound, "Resource not found"),
            ValidationException => (StatusCodes.Status400BadRequest, "Validation failed"),
            ConflictException   => (StatusCodes.Status409Conflict, "Conflict"),
            _                   => (StatusCodes.Status500InternalServerError, "Server error")
        };

        if (status >= 500) logger.LogError(ex, "Unhandled exception on {Path}", ctx.Request.Path);
        else logger.LogWarning("Handled {Type} on {Path}: {Message}",
                               ex.GetType().Name, ctx.Request.Path, ex.Message);

        ctx.Response.StatusCode = status;
        return await problemDetails.TryWriteAsync(new ProblemDetailsContext
        {
            HttpContext = ctx,
            Exception = ex,
            ProblemDetails = new ProblemDetails
            {
                Status = status,
                Title = title,
                // never leak internals for 5xx
                Detail = status >= 500 ? null : ex.Message
            }
        });
    }
}

// Program.cs
builder.Services.AddProblemDetails();
builder.Services.AddExceptionHandler<GlobalExceptionHandler>();   // order = invocation order
var app = builder.Build();
app.UseExceptionHandler();      // register FIRST so it wraps everything
```

Notes: handlers run in registration order; returning `true` means "handled, stop"; `false` falls through to the next handler or the default. Handlers are **singletons**, so inject `IServiceProvider` (create a scope) rather than scoped services such as `DbContext`.

#### Classic exception middleware

```csharp
public sealed class ExceptionMiddleware(RequestDelegate next,
                                        ILogger<ExceptionMiddleware> logger)
{
    public async Task InvokeAsync(HttpContext ctx)
    {
        try { await next(ctx); }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            logger.LogError(ex, "Unhandled exception");
            if (ctx.Response.HasStarted) throw;          // too late to change the response
            ctx.Response.StatusCode = ex is NotFoundException ? 404 : 500;
            ctx.Response.ContentType = "application/problem+json";
            await ctx.Response.WriteAsJsonAsync(new ProblemDetails
            {
                Status = ctx.Response.StatusCode,
                Title = "An error occurred",
                Instance = ctx.Request.Path
            });
        }
    }
}
// Program.cs: app.UseMiddleware<ExceptionMiddleware>();   // first in the pipeline
```

#### ProblemDetails (RFC 7807, now RFC 9457)

`ProblemDetails` is the standard JSON error shape (`application/problem+json`) so every client can parse errors the same way.

```json
{
  "type": "https://tools.ietf.org/html/rfc9110#section-15.5.5",
  "title": "Resource not found",
  "status": 404,
  "detail": "Order '42' was not found.",
  "instance": "/api/orders/42",
  "traceId": "00-4bf92f3577b34da6a3ce929d0e0e4736-00"
}
```

| Field | Meaning |
|---|---|
| `type` | URI identifying the problem category |
| `title` | Short, human-readable summary (same for all instances of the type) |
| `status` | HTTP status code |
| `detail` | Explanation of *this* occurrence (omit for 5xx) |
| `instance` | URI of the failing request/resource |
| extensions | Extra members such as `traceId`, `errors` (`ValidationProblemDetails`) |

```csharp
builder.Services.AddProblemDetails(o =>
    o.CustomizeProblemDetails = c =>
        c.ProblemDetails.Extensions["correlationId"] =
            c.HttpContext.Request.Headers["X-Correlation-Id"].ToString());
```

`[ApiController]` already converts 4xx results and model-validation failures into `ProblemDetails`/`ValidationProblemDetails`. In minimal APIs use `Results.Problem(...)` / `TypedResults.Problem(...)`.

:::warn Never leak internals
Returning `ex.ToString()`, stack traces, SQL text or connection strings to clients is an information-disclosure vulnerability. Log the detail server-side; return a generic message and a `traceId` the user can quote to support.
:::

### Logging exceptions

**Definition.** Structured logging records the message *template* and its named values separately, so log systems (Seq, Application Insights, ELK) can query by property, e.g. all failures for `OrderId = 42`.

```csharp
// GOOD: exception first, named placeholders (not string interpolation)
_logger.LogError(ex, "Failed to place order {OrderId} for customer {CustomerId}",
                 orderId, customerId);

// BAD: loses the stack trace, destroys the template, allocates every call
_logger.LogError($"Failed: {ex.Message}");

// Correlate every log line in a request
using (_logger.BeginScope(new Dictionary<string, object> { ["OrderId"] = orderId }))
{ ... }

// High-throughput path: source-generated, zero-allocation when level disabled
public static partial class Log
{
    [LoggerMessage(EventId = 1001, Level = LogLevel.Error,
                   Message = "Order {OrderId} failed")]
    public static partial void OrderFailed(this ILogger logger, Exception ex, int orderId);
}
```

- **Log once, at the boundary** (global handler). Log-and-rethrow in every layer produces five copies of the same error.
- Level by meaning: `Warning` for expected (not found, validation), `Error` for unexpected, `Critical` for the app cannot continue. Do not log `OperationCanceledException` as an error.
- Never log secrets, tokens, card numbers or PII. Always include a correlation / trace id.

### Best practices

| Do | Don't |
|---|---|
| Catch **specific** exceptions you can actually handle | `catch (Exception) { }` — swallowing hides bugs |
| Rethrow with `throw;` or wrap with `inner` | `throw ex;` |
| Validate inputs with guard clauses early | Use exceptions for normal control flow (e.g. "user not found" in a login loop) |
| Use `using`/`finally` for cleanup | Rely on the GC/finalizers to release resources |
| Handle centrally; log once | Log + throw at every layer |
| Return `ProblemDetails` with a trace id | Return stack traces to clients |
| Use `Try*` methods or the **Result pattern** for expected failures | Catch `NullReferenceException` instead of fixing the null |
| Pass `CancellationToken`; treat `OperationCanceledException` as normal | Catch `Exception` and swallow cancellation |

**Exceptions are expensive.** Throwing and catching costs microseconds to tens of microseconds (about 2–4x faster in .NET 9's managed implementation, but still orders of magnitude slower than returning a value). For *expected* outcomes like "insufficient stock" in a hot path, return a result instead:

```csharp
public readonly record struct Result<T>(T? Value, string? Error)
{
    public bool IsSuccess => Error is null;
    public static Result<T> Ok(T value) => new(value, null);
    public static Result<T> Fail(string error) => new(default, error);
}

public Result<Order> Place(Cart cart) =>
    cart.Items.Any(i => i.Qty > i.Stock)
        ? Result<Order>.Fail("Insufficient stock")
        : Result<Order>.Ok(Order.From(cart));
// Controller: result.IsSuccess ? Ok(result.Value) : Conflict(result.Error)
```

Libraries such as ErrorOr, FluentResults and OneOf provide richer versions. Use exceptions for the *truly exceptional* (DB down, programmer error); use results for business outcomes.

**Async-specific exception traps**

- `await Task.WhenAll(a, b)` rethrows only the **first** exception; the rest are in `task.Exception.InnerExceptions` of the `WhenAll` task.
- `.Wait()` / `.Result` wrap the real error in `AggregateException`; `await` unwraps it.
- An exception in an `async void` method cannot be caught by the caller and can crash the process.
- An exception escaping `BackgroundService.ExecuteAsync` stops the host by default (`BackgroundServiceExceptionBehavior.StopHost`, .NET 6+); catch and log inside the loop.

:::scenario Orders silently disappear in production
Customers complain that some orders are never saved but the API returns `200 OK`. Code review finds `catch (Exception) { return null; }` around `SaveChangesAsync` in the repository and a controller that treats `null` as success.
**Diagnosis:** the exception (a unique-index violation) was swallowed; nothing was logged. **Fix:** remove the blanket catch; let `DbUpdateException` propagate (or catch only `DbUpdateException` with a filter on the SQL error number and throw a `ConflictException`); let the global `IExceptionHandler` log it once and return a `409` ProblemDetails with a `traceId`. Add an integration test that posts a duplicate and asserts `409`.
:::

:::scenario The API returns an HTML error page / stack trace to mobile clients
In production a failing endpoint returns the default error page or, worse, a developer exception page. **Fix:** make sure `UseDeveloperExceptionPage` runs only in Development, register `AddProblemDetails()` + `AddExceptionHandler<T>()` + `UseExceptionHandler()` at the top of the pipeline, return `application/problem+json` with a generic `detail` for 5xx and the `traceId` for support correlation.
:::

:::q Does finally always execute?
Almost always: after normal completion, `return`, `break` or a thrown exception. It will not run if the process is terminated (`Environment.FailFast`, stack overflow, killed process, power loss). A `finally` that throws replaces the original exception, so keep it simple.
:::

:::q How do you implement global exception handling in ASP.NET Core?
On .NET 8+ I implement `IExceptionHandler`, register it with `AddExceptionHandler<T>()`, add `AddProblemDetails()` and call `app.UseExceptionHandler()` first in the pipeline. The handler maps exception types to status codes, logs once with `ILogger`, and writes an RFC 7807/9457 `ProblemDetails` response. On older versions I write a custom middleware with the same try/catch around `next(ctx)`.
:::

:::q Why shouldn't you use exceptions for control flow?
They are slow (stack capture and unwinding), they make code harder to read because the flow is non-local, and they pollute logs and debugger break-on-exception. For expected outcomes use `TryParse`-style methods, return values, or a Result type.
:::
