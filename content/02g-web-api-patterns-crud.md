### Pagination: offset vs keyset (cursor)

**Definition.** Pagination returns a large collection in pages so the API never loads or sends millions of rows at once. Two main techniques: **offset** (`page`/`pageSize` -> `OFFSET/FETCH`) and **keyset/cursor** (`WHERE key < last seen key`).

| | Offset (`?page=3&pageSize=20`) | Keyset / cursor (`?cursor=eyJ...`) |
|---|---|---|
| SQL | `ORDER BY ... OFFSET 40 ROWS FETCH NEXT 20` | `WHERE (CreatedAt, Id) < (@c, @id) ORDER BY ... FETCH NEXT 20` |
| Deep pages | **Slow**: DB still reads and skips all previous rows | **Constant** speed with the right index |
| Jump to page N | Yes | No (next/previous only) |
| Total count | Easy (extra `COUNT(*)` query) | Usually omitted |
| Rows inserted/deleted while paging | Duplicates or skipped rows | Stable |
| Best for | Admin grids with page numbers, small tables | Feeds, infinite scroll, exports, large tables, public APIs |

```csharp
public record PagedResult<T>(IReadOnlyList<T> Items, int Page, int PageSize, int TotalCount)
{
    public int TotalPages => (int)Math.Ceiling(TotalCount / (double)PageSize);
    public bool HasNext => Page < TotalPages;
}

// Offset pagination (always with a deterministic ORDER BY incl. a unique tie-breaker)
public static class OrderPaging
{
public static async Task<PagedResult<OrderSummaryDto>> PageAsync(
    IQueryable<Order> query, int page, int pageSize, CancellationToken ct)
{
    page = Math.Max(page, 1);
    pageSize = Math.Clamp(pageSize, 1, 100);            // never let clients ask for 1,000,000

    var total = await query.CountAsync(ct);
    var items = await query
        .Skip((page - 1) * pageSize)
        .Take(pageSize)
        .Select(o => new OrderSummaryDto(o.Id, o.CreatedAt, o.Total, o.Status.ToString()))
        .ToListAsync(ct);

    return new PagedResult<OrderSummaryDto>(items, page, pageSize, total);
}
}
```

```csharp
// Keyset (cursor) pagination: newest first, cursor = last row's (CreatedAt, Id)
public record CursorPage<T>(IReadOnlyList<T> Items, string? NextCursor);
internal record OrderCursor(DateTime CreatedAt, int Id);

public async Task<CursorPage<OrderSummaryDto>> GetFeedAsync(
    string? cursor, int pageSize, CancellationToken ct)
{
    pageSize = Math.Clamp(pageSize, 1, 100);
    IQueryable<Order> q = _db.Orders.AsNoTracking();

    if (!string.IsNullOrEmpty(cursor))
    {
        var c = JsonSerializer.Deserialize<OrderCursor>(WebEncoders.Base64UrlDecode(cursor))
                ?? throw new DomainValidationException(
                       new Dictionary<string, string[]> { ["cursor"] = ["Invalid cursor"] });
        q = q.Where(o => o.CreatedAt < c.CreatedAt ||
                        (o.CreatedAt == c.CreatedAt && o.Id < c.Id));
    }

    var rows = await q.OrderByDescending(o => o.CreatedAt).ThenByDescending(o => o.Id)
        .Take(pageSize + 1)                              // fetch one extra to know if more exist
        .Select(o => new OrderSummaryDto(o.Id, o.CreatedAt, o.Total, o.Status.ToString()))
        .ToListAsync(ct);

    string? next = null;
    if (rows.Count > pageSize)
    {
        rows.RemoveAt(pageSize);
        var last = rows[^1];
        next = WebEncoders.Base64UrlEncode(
            JsonSerializer.SerializeToUtf8Bytes(new OrderCursor(last.CreatedAt, last.Id)));
    }
    return new CursorPage<OrderSummaryDto>(rows, next);
}
```

```sql
-- The index that makes keyset pagination fast
CREATE INDEX IX_Orders_CreatedAt_Id ON dbo.Orders (CreatedAt DESC, Id DESC)
    INCLUDE (Total, Status);
```

**Returning paging metadata.** Either in the body (`{ items, page, pageSize, totalCount, nextCursor }`, simplest for SPAs) or in headers: `X-Pagination: {"page":2,"pageSize":20,"totalCount":431,"totalPages":22}` and/or RFC 8288 `Link: <.../orders?page=3>; rel="next"`. Browsers can only read custom headers listed in CORS `WithExposedHeaders("X-Pagination", "Link")`.

### Sorting and filtering

**Definition.** Filtering narrows the collection (`?status=Paid&from=2026-01-01`); sorting orders it (`?sortBy=total&desc=true`). Both come from the **query string** and must be **whitelisted**: never pass a client string into dynamic SQL/LINQ (SQL injection, or sorting on an unindexed column that kills the database).

```csharp
public class OrderQueryParameters
{
    public OrderStatus? Status { get; set; }
    public Guid? CustomerId { get; set; }
    public DateTime? From { get; set; }
    public DateTime? To { get; set; }
    [Range(0, double.MaxValue)] public decimal? MinTotal { get; set; }
    [StringLength(50)] public string? Search { get; set; }     // order number / customer email
    public string SortBy { get; set; } = "createdAt";
    public bool Desc { get; set; } = true;
    [Range(1, int.MaxValue)] public int Page { get; set; } = 1;
    [Range(1, 100)] public int PageSize { get; set; } = 20;
}

public static class OrderQueryExtensions
{
    public static IQueryable<Order> ApplyFilters(this IQueryable<Order> q, OrderQueryParameters p)
    {
        if (p.Status is { } s)       q = q.Where(o => o.Status == s);
        if (p.CustomerId is { } c)   q = q.Where(o => o.CustomerId == c);
        if (p.From is { } from)      q = q.Where(o => o.CreatedAt >= from);
        if (p.To is { } to)          q = q.Where(o => o.CreatedAt < to);
        if (p.MinTotal is { } min)   q = q.Where(o => o.Total >= min);
        if (!string.IsNullOrWhiteSpace(p.Search))
            q = q.Where(o => o.OrderNumber.StartsWith(p.Search));   // parameterised, index-friendly
        return q;
    }

    // Whitelist: unknown sort keys fall back to a safe default (or return 400)
    public static IQueryable<Order> ApplySorting(this IQueryable<Order> q, OrderQueryParameters p) =>
        (p.SortBy.ToLowerInvariant(), p.Desc) switch
        {
            ("total", false)     => q.OrderBy(o => o.Total).ThenBy(o => o.Id),
            ("total", true)      => q.OrderByDescending(o => o.Total).ThenByDescending(o => o.Id),
            ("status", false)    => q.OrderBy(o => o.Status).ThenBy(o => o.Id),
            ("status", true)     => q.OrderByDescending(o => o.Status).ThenByDescending(o => o.Id),
            ("createdat", false) => q.OrderBy(o => o.CreatedAt).ThenBy(o => o.Id),
            _                    => q.OrderByDescending(o => o.CreatedAt).ThenByDescending(o => o.Id)
        };
}
// GET /api/v1/orders?status=Paid&from=2026-01-01&sortBy=total&desc=true&page=2&pageSize=20
```

:::warn Sorting/filtering pitfalls
`Skip/Take` without `OrderBy` gives random pages (SQL has no default order). `Contains(search)` becomes `LIKE '%x%'` and cannot use an index. Dynamic LINQ libraries that accept raw strings can expose any column. Always add a unique tie-breaker (`Id`) to the sort so pages are deterministic.
:::

### API validation summary

API validation is layered (covered in detail under Model validation): route constraints reject malformed identifiers; DTO validation (DataAnnotations/FluentValidation, or .NET 10 minimal API validation) returns **400 `ValidationProblemDetails`**; query parameters are clamped/whitelisted (page size, sort fields); business rules return **409/422 ProblemDetails**; database constraints catch races. Validate on the server even if the React/Angular client already validates: the client is not a security boundary.

### Idempotency keys for POST

**Definition.** The client sends a unique `Idempotency-Key` header (a GUID) with a non-idempotent request (create order, charge card). The server stores the first response for that key and **replays it** for any retry, so a timeout-and-retry never creates a duplicate order or double charge. Stripe and most payment APIs work this way.

```csharp
public record IdempotentResponse(int StatusCode, string Body);

public sealed class IdempotencyFilter(IDistributedCache cache) : IAsyncActionFilter
{
    private const string Header = "Idempotency-Key";

    public async Task OnActionExecutionAsync(
        ActionExecutingContext ctx, ActionExecutionDelegate next)
    {
        var http = ctx.HttpContext;
        if (!http.Request.Headers.TryGetValue(Header, out var key) || !Guid.TryParse(key, out _))
        {
            ctx.Result = new BadRequestObjectResult(new ProblemDetails
            { Status = 400, Title = "A GUID Idempotency-Key header is required." });
            return;
        }

        // Scope the key per user and endpoint so keys cannot collide across clients
        var user = http.User.FindFirstValue(ClaimTypes.NameIdentifier) ?? "anonymous";
        var cacheKey = $"idem:{user}:{http.Request.Method}:{http.Request.Path}:{key}";

        var cached = await cache.GetStringAsync(cacheKey, http.RequestAborted);
        if (cached is not null)
        {
            var snap = JsonSerializer.Deserialize<IdempotentResponse>(cached)!;
            http.Response.Headers["Idempotent-Replayed"] = "true";
            ctx.Result = new ContentResult
            { StatusCode = snap.StatusCode, Content = snap.Body, ContentType = "application/json" };
            return;                                           // action does NOT run again
        }

        var executed = await next();

        if (executed.Exception is null &&
            executed.Result is ObjectResult { StatusCode: >= 200 and < 300 } ok)
        {
            var body = JsonSerializer.Serialize(ok.Value, JsonSerializerOptions.Web);
            await cache.SetStringAsync(cacheKey,
                JsonSerializer.Serialize(new IdempotentResponse(ok.StatusCode ?? 200, body)),
                new DistributedCacheEntryOptions
                { AbsoluteExpirationRelativeToNow = TimeSpan.FromHours(24) },
                http.RequestAborted);
        }
    }
}

builder.Services.AddStackExchangeRedisCache(o => o.Configuration = "localhost:6379");
builder.Services.AddScoped<IdempotencyFilter>();
// [ServiceFilter(typeof(IdempotencyFilter))] on POST actions
```

:::warn Production gaps in the simple version
Two concurrent requests with the same key both miss the cache and both execute. Close the race with an atomic "in progress" marker (Redis `SET key value NX`) returning 409 to the second caller, **or** a unique index on an `IdempotencyKey` column in the `Orders` table so the database rejects the duplicate. Also store the `Location` header for 201 replays, and reject a reused key whose request body differs (hash the body and compare).
:::

### Complete CRUD example: OrdersController

A well-structured controller is **thin**: HTTP concerns only (routing, binding, status codes, headers). Business logic lives in a service; data access via `DbContext` inside it. Errors become ProblemDetails via the global exception handler. It uses the `CreateOrderRequest`/`OrderLineRequest` DTOs from the validation topic.

```csharp
// ---------- Contracts (DTOs) ----------
public record OrderLineDto(int ProductId, string ProductName, int Quantity, decimal UnitPrice);
public record OrderDto(int Id, string OrderNumber, Guid CustomerId, string Status,
                       decimal Total, DateTime CreatedAt, IReadOnlyList<OrderLineDto> Lines);
public record OrderSummaryDto(int Id, DateTime CreatedAt, decimal Total, string Status);
public record UpdateOrderRequest([StringLength(200)] string? Notes,
                                 [Required, StringLength(300)] string ShippingAddress);

// ---------- Service abstraction ----------
public interface IOrderService
{
    Task<PagedResult<OrderSummaryDto>> ListAsync(OrderQueryParameters q, CancellationToken ct);
    Task<OrderDto?> GetAsync(int id, CancellationToken ct);
    Task<OrderDto> CreateAsync(CreateOrderRequest req, CancellationToken ct);
    Task<bool> UpdateAsync(int id, UpdateOrderRequest req, CancellationToken ct);
    Task<bool> CancelAsync(int id, CancellationToken ct);      // throws ConflictException
    Task<bool> DeleteAsync(int id, CancellationToken ct);
}

// ---------- Controller ----------
[ApiController]
[Route("api/v1/orders")]
[Authorize]
[Produces("application/json")]
public sealed class OrdersController(IOrderService orders, ILogger<OrdersController> logger)
    : ControllerBase
{
    /// <summary>List orders with filtering, sorting and paging.</summary>
    [HttpGet]
    [ProducesResponseType<PagedResult<OrderSummaryDto>>(StatusCodes.Status200OK)]
    public async Task<ActionResult<PagedResult<OrderSummaryDto>>> List(
        [FromQuery] OrderQueryParameters query, CancellationToken ct)
    {
        var page = await orders.ListAsync(query, ct);
        Response.Headers["X-Pagination"] = JsonSerializer.Serialize(
            new { page.Page, page.PageSize, page.TotalCount, page.TotalPages });
        return Ok(page);
    }

    [HttpGet("{id:int}", Name = "GetOrderById")]
    [ProducesResponseType<OrderDto>(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<OrderDto>> Get(int id, CancellationToken ct)
    {
        var order = await orders.GetAsync(id, ct);
        if (order is null) return NotFound();
        return order;
    }

    [HttpPost]
    [ServiceFilter(typeof(IdempotencyFilter))]
    [ProducesResponseType<OrderDto>(StatusCodes.Status201Created)]
    [ProducesResponseType<ValidationProblemDetails>(StatusCodes.Status400BadRequest)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status409Conflict)]
    public async Task<ActionResult<OrderDto>> Create(
        CreateOrderRequest request, CancellationToken ct)        // [FromBody] inferred
    {
        var created = await orders.CreateAsync(request, ct);
        logger.LogInformation("Order {OrderId} created", created.Id);
        // 201 + Location: /api/v1/orders/{id} + body
        return CreatedAtRoute("GetOrderById", new { id = created.Id }, created);
    }

    [HttpPut("{id:int}")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> Update(
        int id, UpdateOrderRequest request, CancellationToken ct) =>
        await orders.UpdateAsync(id, request, ct) ? NoContent() : NotFound();

    [HttpPost("{id:int}/cancel")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status409Conflict)]
    public async Task<IActionResult> Cancel(int id, CancellationToken ct) =>
        await orders.CancelAsync(id, ct) ? NoContent() : NotFound();

    [HttpDelete("{id:int}")]
    [Authorize(Roles = "Admin")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> Delete(int id, CancellationToken ct) =>
        await orders.DeleteAsync(id, ct) ? NoContent() : NotFound();
}
```

```csharp
// ---------- Service implementation (scoped, owns the unit of work) ----------
public sealed class OrderService(ShopDbContext db, TimeProvider clock) : IOrderService
{
    public Task<PagedResult<OrderSummaryDto>> ListAsync(OrderQueryParameters q, CancellationToken ct) =>
        OrderPaging.PageAsync(db.Orders.AsNoTracking().ApplyFilters(q).ApplySorting(q),
                              q.Page, q.PageSize, ct);

    public Task<OrderDto?> GetAsync(int id, CancellationToken ct) =>
        db.Orders.AsNoTracking()
            .Where(o => o.Id == id)
            .Select(o => new OrderDto(o.Id, o.OrderNumber, o.CustomerId, o.Status.ToString(),
                o.Total, o.CreatedAt,
                o.Lines.Select(l => new OrderLineDto(
                    l.ProductId, l.Product.Name, l.Quantity, l.UnitPrice)).ToList()))
            .FirstOrDefaultAsync(ct);

    public async Task<OrderDto> CreateAsync(CreateOrderRequest req, CancellationToken ct)
    {
        var ids = req.Lines.Select(l => l.ProductId).Distinct().ToList();
        var products = await db.Products.Where(p => ids.Contains(p.Id))
                                        .ToDictionaryAsync(p => p.Id, ct);

        var order = new Order
        {
            OrderNumber = $"ORD-{clock.GetUtcNow():yyyyMMdd}-{Guid.NewGuid().ToString("N")[..6]}",
            CustomerId = req.CustomerId!.Value,
            CreatedAt = clock.GetUtcNow().UtcDateTime,
            Status = OrderStatus.Pending
        };

        foreach (var line in req.Lines)
        {
            if (!products.TryGetValue(line.ProductId, out var p))
                throw new NotFoundException($"Product {line.ProductId} not found");
            if (p.Stock < line.Quantity)
                throw new ConflictException($"Product {p.Id} has only {p.Stock} in stock");

            p.Stock -= line.Quantity;                         // tracked: same DbContext
            order.Lines.Add(new OrderLine
            { ProductId = p.Id, Product = p, Quantity = line.Quantity, UnitPrice = p.Price });
        }
        order.Total = order.Lines.Sum(l => l.UnitPrice * l.Quantity);

        db.Orders.Add(order);
        await db.SaveChangesAsync(ct);         // ONE transaction: stock + order + lines
        return new OrderDto(order.Id, order.OrderNumber, order.CustomerId,
            order.Status.ToString(), order.Total, order.CreatedAt,
            order.Lines.Select(l => new OrderLineDto(
                l.ProductId, l.Product.Name, l.Quantity, l.UnitPrice)).ToList());
    }

    public async Task<bool> UpdateAsync(int id, UpdateOrderRequest req, CancellationToken ct)
    {
        var order = await db.Orders.FirstOrDefaultAsync(o => o.Id == id, ct);
        if (order is null) return false;
        order.Notes = req.Notes;
        order.ShippingAddress = req.ShippingAddress;
        try { await db.SaveChangesAsync(ct); }
        catch (DbUpdateConcurrencyException)                  // RowVersion mismatch
        { throw new ConflictException("The order was modified by someone else."); }
        return true;
    }

    public async Task<bool> CancelAsync(int id, CancellationToken ct)
    {
        var order = await db.Orders.FirstOrDefaultAsync(o => o.Id == id, ct);
        if (order is null) return false;
        if (order.Status is OrderStatus.Shipped or OrderStatus.Delivered)
            throw new ConflictException($"Order {id} is already {order.Status}.");
        order.Status = OrderStatus.Cancelled;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> DeleteAsync(int id, CancellationToken ct) =>
        await db.Orders.Where(o => o.Id == id).ExecuteDeleteAsync(ct) > 0;
}

// Program.cs
builder.Services.AddScoped<IOrderService, OrderService>();
```

**Why this is "well-structured":** thin controller; DTOs in and out (no over-posting); `CancellationToken` everywhere; `ActionResult<T>` + `ProducesResponseType` for accurate OpenAPI; `CreatedAtRoute` gives 201 + `Location`; non-CRUD command as `POST /{id}/cancel`; domain errors are exceptions mapped centrally to 404/409 ProblemDetails; validation is automatic via `[ApiController]`; idempotent POST; optimistic concurrency via `RowVersion`; one `SaveChangesAsync` per request = one transaction.

### The same API as minimal endpoints

```csharp
public static class OrderEndpoints
{
    public static RouteGroupBuilder MapOrderEndpoints(this IEndpointRouteBuilder app)
    {
        var g = app.MapGroup("/api/v1/orders").WithTags("Orders").RequireAuthorization();

        g.MapGet("/", async ([AsParameters] OrderQueryParameters q,
                             IOrderService svc, HttpResponse res, CancellationToken ct) =>
        {
            var page = await svc.ListAsync(q, ct);
            res.Headers["X-Pagination"] = JsonSerializer.Serialize(
                new { page.Page, page.PageSize, page.TotalCount, page.TotalPages });
            return TypedResults.Ok(page);
        });

        g.MapGet("/{id:int}", async Task<Results<Ok<OrderDto>, NotFound>> (
                int id, IOrderService svc, CancellationToken ct) =>
            await svc.GetAsync(id, ct) is { } o ? TypedResults.Ok(o) : TypedResults.NotFound())
         .WithName("GetOrder");

        g.MapPost("/", async (CreateOrderRequest req, IOrderService svc, CancellationToken ct) =>
            {
                var o = await svc.CreateAsync(req, ct);
                return TypedResults.CreatedAtRoute(o, "GetOrder", new { id = o.Id });
            })
         .AddEndpointFilter<ValidationFilter<CreateOrderRequest>>()   // or AddValidation() in .NET 10
         .ProducesValidationProblem()
         .ProducesProblem(StatusCodes.Status409Conflict);

        g.MapPut("/{id:int}", async Task<Results<NoContent, NotFound>> (
                int id, UpdateOrderRequest req, IOrderService svc, CancellationToken ct) =>
            await svc.UpdateAsync(id, req, ct) ? TypedResults.NoContent() : TypedResults.NotFound());

        g.MapPost("/{id:int}/cancel", async Task<Results<NoContent, NotFound>> (
                int id, IOrderService svc, CancellationToken ct) =>
            await svc.CancelAsync(id, ct) ? TypedResults.NoContent() : TypedResults.NotFound());

        g.MapDelete("/{id:int}", async Task<Results<NoContent, NotFound>> (
                int id, IOrderService svc, CancellationToken ct) =>
            await svc.DeleteAsync(id, ct) ? TypedResults.NoContent() : TypedResults.NotFound())
         .RequireAuthorization(p => p.RequireRole("Admin"));

        return g;
    }
}

// Program.cs
app.MapOrderEndpoints();
```

Same service, same DTOs, same exception-to-ProblemDetails mapping; only the HTTP layer differs. Unit testing a handler is easy because `TypedResults` can be asserted directly (`Assert.IsType<Ok<OrderDto>>(result.Result)`).

## Quick-fire Q&A

:::q What is middleware in ASP.NET Core?
A component in the request pipeline that receives `HttpContext` and a `next` delegate. It can act before and after the rest of the pipeline or short-circuit it. Examples: exception handling, HTTPS redirection, CORS, authentication, authorization, logging.
:::

:::q How do you write custom middleware?
A class with a constructor taking `RequestDelegate next` and a public `InvokeAsync(HttpContext context)` method, registered with `app.UseMiddleware<T>()`. Scoped services go on `InvokeAsync` parameters, not the constructor, because the middleware is created once. Alternatively implement `IMiddleware` and register it in DI for per-request instances.
:::

:::q Middleware vs filters?
Middleware runs for every request and only sees `HttpContext`. Filters run inside MVC after an action is selected and can see action arguments, `ModelState` and the action result. Global concerns go in middleware; action-aware concerns like auditing or result shaping go in filters.
:::

:::q What is the correct order of the main middleware?
Exception handler, HSTS, HTTPS redirection, static files, routing, CORS, rate limiting, authentication, authorization, custom middleware, then endpoints. Authentication must come before authorization, and CORS before both.
:::

:::q AddSingleton vs AddScoped vs AddTransient in one line each?
Singleton: one instance for the app lifetime. Scoped: one instance per HTTP request. Transient: a new instance every time it is resolved. `DbContext` is scoped.
:::

:::q What does `[ApiController]` give you?
Attribute routing requirement, automatic 400 `ValidationProblemDetails` for invalid models, binding source inference, multipart inference for files, and ProblemDetails bodies for error status codes.
:::

:::q 401 vs 403?
401 means not authenticated: no token, or the token is invalid or expired. 403 means authenticated but not permitted. Say: "401 is who are you, 403 is you can't do this."
:::

:::q What should a POST that creates a resource return?
201 Created with a `Location` header pointing to the new resource and usually the resource in the body: `CreatedAtAction` or `CreatedAtRoute`. If processing is asynchronous, return 202 Accepted with a status URL.
:::

:::q How do you implement pagination for a large table?
Offset (`Skip/Take` with a stable `OrderBy` and a capped page size) for admin grids with page numbers. Keyset/cursor pagination (`WHERE (CreatedAt, Id) < cursor`) with a matching index for large tables, feeds and public APIs, because offset gets slower on deep pages and is unstable under inserts.
:::

:::q How do you make sorting by a client-supplied column safe?
Whitelist the allowed fields and map each to a typed `OrderBy` expression with a switch, falling back to a default or returning 400 for unknown values. Never concatenate the string into SQL or pass it to an unrestricted dynamic LINQ parser, and always add `Id` as a tie-breaker.
:::

:::q How do you handle exceptions globally in a Web API?
`AddProblemDetails()` plus an `IExceptionHandler` and `app.UseExceptionHandler()` (or custom exception middleware). Map domain exceptions to 404/409/422, log 5xx with the trace ID, return RFC 9457 ProblemDetails, and never leak stack traces outside Development.
:::

:::q What is content negotiation?
The server chooses the response format from the client's `Accept` header using output formatters, and reads the request with the input formatter matching `Content-Type`. JSON is the default; with `ReturnHttpNotAcceptable = true` an unsupported `Accept` gives 406, and an unsupported request type gives 415.
:::

:::q How does the options pattern work, and how do you validate config?
Bind a section to a class with `AddOptions<T>().Bind(section)` and inject `IOptions<T>`, `IOptionsSnapshot<T>` (scoped, per request) or `IOptionsMonitor<T>` (live, singleton-safe). Add `ValidateDataAnnotations().ValidateOnStart()` so the app fails at startup on bad config.
:::

:::q What changed for API documentation in .NET 9?
The Web API template dropped Swashbuckle and uses the built-in `Microsoft.AspNetCore.OpenApi` (`AddOpenApi()` and `MapOpenApi()` at `/openapi/v1.json`). It produces the document only, so you add a UI such as Scalar or Swagger UI. .NET 10 defaults to OpenAPI 3.1.
:::

:::q How do you prevent duplicate orders when a client retries a POST?
Require an `Idempotency-Key` header, store the first response under that key (Redis or a DB table with a unique index) and replay it for retries. Handle concurrent duplicates with an atomic "in progress" marker or a unique constraint so only one request creates the order.
:::
