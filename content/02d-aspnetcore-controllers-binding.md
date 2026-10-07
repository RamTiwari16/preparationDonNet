## ASP.NET Core: Routing, Controllers and Binding

### Routing

**Definition.** *Endpoint routing* maps an incoming URL and HTTP method to an **endpoint** (a controller action, a minimal API handler, a Razor Page, a health check). Routing runs in two steps: `UseRouting` selects the endpoint, then the endpoint executes at the end of the pipeline. With `WebApplication` both steps are added for you.

| | Conventional routing | Attribute routing |
|---|---|---|
| Where defined | One central pattern in `Program.cs` | On controllers/actions with `[Route]`, `[HttpGet]` |
| Typical use | MVC apps with views | **Web APIs** (REST resource URLs) |
| Flexibility | Same shape for all controllers | Any shape per action |
| Link generation | `Url.Action("Index", "Home")` | `CreatedAtAction`, route names |

```csharp
// Conventional (MVC with views)
app.MapControllerRoute(
    name: "default",
    pattern: "{controller=Home}/{action=Index}/{id?}");

// Attribute routing (APIs)
[ApiController]
[Route("api/[controller]")]                 // [controller] token -> "orders"
public class OrdersController : ControllerBase
{
    [HttpGet]                               // GET api/orders
    public IActionResult List() => Ok();

    [HttpGet("{id:int:min(1)}", Name = "GetOrder")]   // GET api/orders/42
    public IActionResult Get(int id) => Ok();

    [HttpGet("{orderId:guid}/lines/{lineNo:int}")]    // nested resource
    public IActionResult GetLine(Guid orderId, int lineNo) => Ok();

    [HttpPost("{id:int}/cancel")]           // action on a resource (POST verb endpoint)
    public IActionResult Cancel(int id) => NoContent();
}
```

**Route constraints** reject non-matching values *at routing time* (the request falls through to 404 instead of reaching your code with bad input):

| Constraint | Example | Matches |
|---|---|---|
| `int`, `long`, `double`, `decimal`, `bool`, `guid`, `datetime` | `{id:int}` | Value parses as that type |
| `min(n)`, `max(n)`, `range(a,b)` | `{page:int:min(1)}` | Numeric bounds |
| `length(n)`, `minlength`, `maxlength` | `{code:length(3)}` | String length |
| `alpha` | `{lang:alpha}` | Letters only |
| `regex(...)` | `{sku:regex(^[A-Z]{{3}}-\\d{{4}}$)}` | Pattern (braces doubled) |
| `required`, `file`, `nonfile` | `{name:required}` | Misc |

```csharp
app.MapGet("/files/{**path}", (string path) => path);     // catch-all segment
app.MapGet("/blog/{slug=latest}", (string slug) => slug); // default value
app.MapGet("/orders/{id:int?}", (int? id) => id);         // optional parameter
```

**Notes.** Routes are case-insensitive. Literal segments beat parameters (`/orders/recent` wins over `/orders/{id}`). Two endpoints matching equally throw `AmbiguousMatchException` (500), a classic bug. `LinkGenerator` and named routes build URLs so you never hand-concatenate them. Constraints are **not validation**: use them for routing disambiguation only; validate in the model.

### Controllers and `[ApiController]`

**Definition.** A *controller* is a class (`XxxController`, derived from `ControllerBase` for APIs or `Controller` for MVC with views) whose public methods are actions. `[ApiController]` turns on API-specific conventions.

**Behaviours `[ApiController]` adds:**

1. **Attribute routing is required** (conventional routes do not apply).
2. **Automatic HTTP 400** when `ModelState` is invalid, with a `ValidationProblemDetails` body. You do not write `if (!ModelState.IsValid)`.
3. **Binding source inference**: complex types -> `[FromBody]`; names matching route parameters -> `[FromRoute]`; simple types -> `[FromQuery]`; `IFormFile` -> `[FromForm]`; services registered in DI -> `[FromServices]` (.NET 7+).
4. **Multipart/form-data** request inference for `IFormFile` parameters.
5. **ProblemDetails for error status codes**: returning `NotFound()` produces an `application/problem+json` body.

```csharp
builder.Services.AddControllers()
    .ConfigureApiBehaviorOptions(o =>
    {
        // o.SuppressModelStateInvalidFilter = true;         // handle ModelState yourself
        o.InvalidModelStateResponseFactory = ctx =>
        {
            var problem = new ValidationProblemDetails(ctx.ModelState)
            {
                Status = StatusCodes.Status422UnprocessableEntity,
                Title = "Validation failed",
                Instance = ctx.HttpContext.Request.Path
            };
            return new UnprocessableEntityObjectResult(problem);
        };
    });
```

:::tip ControllerBase vs Controller
Use `ControllerBase` for APIs. `Controller` adds `View()`, `PartialView()` and `ViewData` (MVC views). Do not inherit `Controller` in a Web API: it drags in view support you do not need.
:::

### Minimal APIs

**Definition.** *Minimal APIs* declare endpoints directly with `app.MapXxx(pattern, handler)`, without controller classes. The handler can be a lambda, a local function, or a static method. Parameters are bound automatically from route, query, headers, body, and **DI services**.

**Why it matters.** Less ceremony, lower overhead, native AOT friendly, and great for microservices. Since .NET 7/8 they have route groups, endpoint filters, typed results, and validation (.NET 10), so they are production-grade.

```csharp
// Products module: static class with an extension method keeps Program.cs clean
public static class ProductEndpoints
{
    public static IEndpointRouteBuilder MapProductEndpoints(this IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/api/products")
                       .WithTags("Products")
                       .RequireAuthorization();          // applies to every endpoint in the group

        group.MapGet("/", GetAll);
        group.MapGet("/{id:int}", GetById).WithName("GetProduct");
        group.MapPost("/", Create).AddEndpointFilter<ValidationFilter<CreateProductRequest>>();
        group.MapDelete("/{id:int}", Delete).RequireAuthorization("AdminOnly");
        return app;
    }

    static async Task<Ok<List<ProductDto>>> GetAll(
        ShopDbContext db, [AsParameters] PagingQuery paging, CancellationToken ct)
    {
        var items = await db.Products.AsNoTracking()
            .OrderBy(p => p.Id)
            .Skip((paging.Page - 1) * paging.PageSize).Take(paging.PageSize)
            .Select(p => new ProductDto(p.Id, p.Name, p.Price))
            .ToListAsync(ct);
        return TypedResults.Ok(items);
    }

    // Union return type: documents BOTH outcomes for OpenAPI and makes unit tests easy
    static async Task<Results<Ok<ProductDto>, NotFound>> GetById(
        int id, ShopDbContext db, CancellationToken ct)
    {
        var p = await db.Products.AsNoTracking().FirstOrDefaultAsync(x => x.Id == id, ct);
        return p is null
            ? TypedResults.NotFound()
            : TypedResults.Ok(new ProductDto(p.Id, p.Name, p.Price));
    }

    static async Task<Created<ProductDto>> Create(
        CreateProductRequest req, ShopDbContext db, CancellationToken ct)
    {
        var entity = new Product { Name = req.Name, Price = req.Price };
        db.Products.Add(entity);
        await db.SaveChangesAsync(ct);
        return TypedResults.Created($"/api/products/{entity.Id}",
            new ProductDto(entity.Id, entity.Name, entity.Price));
    }

    static async Task<Results<NoContent, NotFound>> Delete(
        int id, ShopDbContext db, CancellationToken ct)
    {
        var rows = await db.Products.Where(p => p.Id == id).ExecuteDeleteAsync(ct);
        return rows == 0 ? TypedResults.NotFound() : TypedResults.NoContent();
    }
}

public record PagingQuery(int Page = 1, int PageSize = 20);

// Program.cs
app.MapProductEndpoints();
```

```csharp
// Endpoint filter: the minimal API equivalent of an action filter
public class ValidationFilter<T> : IEndpointFilter where T : class
{
    public async ValueTask<object?> InvokeAsync(
        EndpointFilterInvocationContext ctx, EndpointFilterDelegate next)
    {
        var arg = ctx.Arguments.OfType<T>().FirstOrDefault();
        var validator = ctx.HttpContext.RequestServices.GetService<IValidator<T>>();
        if (arg is not null && validator is not null)
        {
            var result = await validator.ValidateAsync(arg);
            if (!result.IsValid)
                return TypedResults.ValidationProblem(result.ToDictionary());
        }
        return await next(ctx);          // continue to the handler
    }
}
```

**Parameter binding rules (minimal APIs):**

| Parameter | Bound from |
|---|---|
| Name matches `{route}` token | Route |
| Simple type not in route | Query string |
| Complex type on POST/PUT/PATCH | JSON body (only one body parameter) |
| Registered service type | DI (inferred) |
| `HttpContext`, `HttpRequest`, `HttpResponse`, `ClaimsPrincipal`, `CancellationToken`, `Stream`, `PipeReader` | Special types |
| `[FromHeader]`, `[FromQuery]`, `[FromForm]`, `[FromKeyedServices]` | Explicit |
| `[AsParameters] T` | Flattens a record's properties into separate bound parameters |

You can add custom parsing with a static `TryParse(string, out T)` or `BindAsync(HttpContext)` on your type.

### Controllers vs Minimal APIs

| | Controllers (MVC) | Minimal APIs |
|---|---|---|
| Structure | Classes + attributes, convention-based | Delegates; organise by extension methods and groups |
| Validation | **Automatic** with `[ApiController]` (DataAnnotations) | Built in from **.NET 10** (`AddValidation()`); before that, filters/FluentValidation |
| Filters | 5 filter types | Endpoint filters |
| Model binding | Rich, extensible (custom binders, formatters) | Simpler; custom via `TryParse`/`BindAsync` |
| Content negotiation | Built in (formatters) | JSON by default; others by hand |
| Performance | Slightly more overhead | Faster startup/lower allocations; **AOT-friendly** |
| OpenAPI | Reflection + attributes | `Produces`, `TypedResults`, metadata |
| Best for | Large teams, many endpoints, existing conventions, MVC views | Microservices, small APIs, high performance, AOT |

Both run on the same routing, middleware, auth, DI, and options. You can mix them in one app.

### Model binding

**Definition.** *Model binding* converts request data (route, query string, headers, body, form, files) into .NET action parameters or model objects. **Model validation** then checks the result.

| Attribute | Source | Notes |
|---|---|---|
| `[FromRoute]` | URL path segment | `/orders/{id}` |
| `[FromQuery]` | Query string | `?status=Paid&page=2`; collections via repeated keys `?ids=1&ids=2` |
| `[FromBody]` | Request body (JSON by default via input formatter) | **Only one per action**; stream can be read once |
| `[FromHeader]` | HTTP header | `[FromHeader(Name = "X-Tenant-Id")]` |
| `[FromForm]` | `application/x-www-form-urlencoded` or `multipart/form-data` | Required for `IFormFile` uploads |
| `[FromServices]` | DI container | Action-level injection; `[FromKeyedServices("key")]` in .NET 8 |

```csharp
[HttpPost("{customerId:guid}/orders")]
public async Task<ActionResult<OrderDto>> Create(
    [FromRoute] Guid customerId,                       // /customers/{id}/orders
    [FromQuery] bool notify,                           // ?notify=true
    [FromHeader(Name = "Idempotency-Key")] string? key,
    [FromBody] CreateOrderRequest body,                // JSON
    [FromServices] IOrderService orders,               // DI (action injection)
    CancellationToken ct)                              // bound automatically
{
    var order = await orders.CreateAsync(customerId, body, key, ct);
    return CreatedAtAction(nameof(Get), new { id = order.Id }, order);
}

// Complex object from the query string
public class OrderFilter { public string? Status { get; set; } public int Page { get; set; } = 1; }
[HttpGet] public IActionResult List([FromQuery] OrderFilter f) => Ok(f);   // ?status=Paid&page=2

// File upload
[HttpPost("receipt")]
[RequestSizeLimit(5_000_000)]
public async Task<IActionResult> Upload([FromForm] IFormFile file, CancellationToken ct)
{
    if (file.Length == 0) return BadRequest();
    await using var stream = file.OpenReadStream();
    // ... save to blob storage
    return Accepted();
}
```

**Without attributes** (non-`[ApiController]`), MVC searches form values, then route values, then the query string. With `[ApiController]` the inference table above applies, which is why complex types need no `[FromBody]`.

:::warn Binding gotchas
Two `[FromBody]` parameters on one action is an error (the body is a forward-only stream). With `<Nullable>enable</Nullable>`, a non-nullable reference type property such as `string Name` is **implicitly `[Required]`**. JSON syntax errors give a 400 before your code runs. Property names bind case-insensitively. A missing `[FromQuery]` value silently gives `0`/`null` unless you validate it.
:::

### Model validation

**Definition.** Validation checks bound input against rules and records failures in `ModelState`. With `[ApiController]`, an invalid model automatically returns **400 with `ValidationProblemDetails`**.

#### DataAnnotations

```csharp
public class CreateOrderRequest : IValidatableObject
{
    [Required]
    public Guid? CustomerId { get; set; }

    [Required, MinLength(1, ErrorMessage = "At least one line is required")]
    public List<OrderLineRequest> Lines { get; set; } = [];

    [StringLength(200)]
    public string? Notes { get; set; }

    [Required, RegularExpression(@"^[A-Z]{2}\d{2}[A-Z0-9]{1,30}$")]
    public string? Iban { get; set; }

    public DateOnly? RequestedDelivery { get; set; }

    // Cross-field / business-level validation
    public IEnumerable<ValidationResult> Validate(ValidationContext ctx)
    {
        if (RequestedDelivery is { } d && d < DateOnly.FromDateTime(DateTime.UtcNow))
            yield return new ValidationResult(
                "Delivery date cannot be in the past.", [nameof(RequestedDelivery)]);

        if (Lines.Sum(l => l.Quantity) > 500)
            yield return new ValidationResult(
                "Too many items in one order.", [nameof(Lines)]);
    }
}

public class OrderLineRequest
{
    [Range(1, int.MaxValue)] public int ProductId { get; set; }
    [Range(1, 100)]          public int Quantity { get; set; }
}
```

Common attributes: `[Required]`, `[StringLength]`, `[MinLength]`, `[MaxLength]`, `[Range]`, `[RegularExpression]`, `[EmailAddress]`, `[Phone]`, `[Url]`, `[Compare]`, `[CreditCard]`. Custom: derive from `ValidationAttribute` and override `IsValid`.

```csharp
public class FutureDateAttribute : ValidationAttribute
{
    protected override ValidationResult? IsValid(object? value, ValidationContext ctx) =>
        value is DateOnly d && d > DateOnly.FromDateTime(DateTime.UtcNow)
            ? ValidationResult.Success
            : new ValidationResult("Date must be in the future.");
}
```

**Automatic 400 response:**

```json
{
  "type": "https://tools.ietf.org/html/rfc9110#section-15.5.1",
  "title": "One or more validation errors occurred.",
  "status": 400,
  "errors": {
    "Lines[0].Quantity": ["The field Quantity must be between 1 and 100."],
    "Iban": ["The Iban field is required."]
  },
  "traceId": "00-6b2f1c...-01"
}
```

#### FluentValidation (rules in code, not attributes)

```csharp
public class CreateOrderRequestValidator : AbstractValidator<CreateOrderRequest>
{
    public CreateOrderRequestValidator(IProductCatalog catalog)    // DI works
    {
        RuleFor(x => x.CustomerId).NotNull();
        RuleFor(x => x.Lines).NotEmpty().WithMessage("At least one line is required");
        RuleForEach(x => x.Lines).ChildRules(line =>
        {
            line.RuleFor(l => l.Quantity).InclusiveBetween(1, 100);
            line.RuleFor(l => l.ProductId)
                .MustAsync(async (id, ct) => await catalog.ExistsAsync(id, ct))
                .WithMessage("Product {PropertyValue} does not exist");
        });
        RuleFor(x => x.Notes).MaximumLength(200);
    }
}

builder.Services.AddValidatorsFromAssemblyContaining<CreateOrderRequestValidator>();

// Controller: validate explicitly (the auto-validation package is no longer recommended)
[HttpPost]
public async Task<IActionResult> Create(
    CreateOrderRequest req, IValidator<CreateOrderRequest> validator, CancellationToken ct)
{
    var result = await validator.ValidateAsync(req, ct);
    if (!result.IsValid)
        return ValidationProblem(new ValidationProblemDetails(result.ToDictionary()));
    // ...
    return Ok();
}
```

| | DataAnnotations | FluentValidation | `IValidatableObject` |
|---|---|---|---|
| Where rules live | Attributes on the model | Separate validator class | Method on the model |
| Conditional/cross-field | Awkward | **Excellent** (`When`, `Must`) | Good |
| Async / DI | No | **Yes** | No |
| Reuse across layers | Low | High | Low |
| Auto-integrated with `[ApiController]` | **Yes** | Manual or filter | Yes (runs after attributes pass) |

:::tip Validation layers
Validate in three places: (1) **syntax and shape** at the API edge (DTO attributes/FluentValidation: required, lengths, ranges); (2) **business rules** in the domain/service (stock available, order not already shipped) throwing domain exceptions mapped to 409/422; (3) **database constraints** (unique index, FK, check) as the last line of defence against races.
:::

### Action results

**Definition.** An action returns something that tells MVC how to write the response.

| Return type | Use when | Notes |
|---|---|---|
| `IActionResult` | Multiple different result kinds | No type info for OpenAPI; add `[ProducesResponseType]` |
| `ActionResult<T>` | **Default for APIs**: either a `T` or an error result | Infers 200 `T` for OpenAPI, implicit conversion from `T` |
| `T` / `Task<T>` | Always 200 with a body | Cannot express 404 |
| `IAsyncEnumerable<T>` | Streaming large result sets | Serialised incrementally |
| `TypedResults.*` / `Results<...>` | Minimal APIs | Compile-time typed, auto metadata, easy to unit test |

| Helper | Status | Typical use |
|---|---|---|
| `Ok(x)` | 200 | GET/PUT with body |
| `CreatedAtAction(...)` / `Created(uri, x)` | 201 + `Location` | POST created a resource |
| `Accepted(...)` | 202 | Work queued (async processing) |
| `NoContent()` | 204 | PUT/DELETE success, no body |
| `BadRequest(...)` / `ValidationProblem(...)` | 400 | Bad input |
| `Unauthorized()` / `Forbid()` | 401 / 403 | Not signed in / not allowed |
| `NotFound()` | 404 | Missing resource |
| `Conflict(...)` | 409 | State conflict, duplicate, concurrency |
| `UnprocessableEntity(...)` | 422 | Semantically invalid |
| `Problem(...)` | any | Custom ProblemDetails |
| `File(...)`, `PhysicalFile(...)` | 200 | Downloads |
| `StatusCode(code)` | any | Rare codes |

```csharp
[HttpGet("{id:int}")]
[ProducesResponseType<OrderDto>(StatusCodes.Status200OK)]
[ProducesResponseType(StatusCodes.Status404NotFound)]
public async Task<ActionResult<OrderDto>> Get(int id, CancellationToken ct)
{
    var order = await _service.GetAsync(id, ct);
    if (order is null) return NotFound();        // ActionResult
    return order;                                // implicit conversion: T -> 200 OK
}
```

### DTOs, ViewModels, and entities

**Definition.**

| Type | Purpose | Lives in |
|---|---|---|
| **Entity** | Persistence/domain object with identity; tracked by EF Core; mirrors the table | Domain/Data layer |
| **DTO** (Data Transfer Object) | Shape of data crossing a boundary (API request/response, message) | API/contract layer |
| **ViewModel** | Data shaped for a specific **UI view**, often including display strings, select lists, flags | MVC/Razor/Blazor presentation layer |

**Why not expose entities directly?**

- **Over-posting / mass assignment**: the client sets properties you never meant to expose.
- **Leaking internals**: password hashes, internal flags, navigation graphs, cycles that break serialization.
- **Coupling**: any DB change becomes a breaking API change.
- **Performance**: loads whole rows and graphs instead of projecting only needed columns.

```csharp
// Entity (never bound or returned directly)
public class Order
{
    public int Id { get; set; }
    public Guid CustomerId { get; set; }
    public decimal Total { get; set; }
    public bool IsPaid { get; set; }              // must NOT be client-controlled
    public string InternalNotes { get; set; } = "";
    public List<OrderLine> Lines { get; set; } = [];
}

// BAD: binds the entity. POST {"customerId":"...","isPaid":true,"total":0.01}
// public IActionResult Create(Order order) { _db.Add(order); ... }   // over-posting!

// GOOD: request DTO contains ONLY what the client may send
public record CreateOrderDto(Guid CustomerId, List<OrderLineDto> Lines);
public record OrderLineDto(int ProductId, int Quantity);

// Response DTO contains ONLY what the client may see
public record OrderDto(int Id, decimal Total, string Status, IReadOnlyList<OrderLineDto> Lines);
```

**Mapping options:**

```csharp
// 1) Manual mapping (explicit, fastest, easiest to debug) - my default
public static class OrderMappings
{
    public static OrderDto ToDto(this Order o) => new(
        o.Id, o.Total, o.IsPaid ? "Paid" : "Pending",
        o.Lines.Select(l => new OrderLineDto(l.ProductId, l.Quantity)).ToList());
}

// 2) EF projection: translated to SQL, selects only needed columns, no tracking
var dtos = await db.Orders.AsNoTracking()
    .Where(o => o.CustomerId == customerId)
    .Select(o => new OrderDto(o.Id, o.Total, o.IsPaid ? "Paid" : "Pending",
        o.Lines.Select(l => new OrderLineDto(l.ProductId, l.Quantity)).ToList()))
    .ToListAsync(ct);

// 3) Mapperly: source-generated, compile-time checked, no reflection
[Mapper]
public static partial class OrderMapper { public static partial OrderDto ToDto(Order o); }

// 4) AutoMapper: convention + profiles (reflection, runtime config errors)
public class OrderProfile : Profile
{
    public OrderProfile() => CreateMap<Order, OrderDto>()
        .ForMember(d => d.Status, m => m.MapFrom(s => s.IsPaid ? "Paid" : "Pending"));
}
// var dto = _mapper.Map<OrderDto>(order);   // or ProjectTo<OrderDto>(...)
```

| | Manual | EF `Select` | Mapperly | Mapster | AutoMapper |
|---|---|---|---|---|---|
| Speed | Fastest | Fast (SQL projection) | Fastest (generated) | Fast | Slower (reflection) |
| Compile-time safety | Yes | Yes | **Yes** | Partial | No (runtime) |
| Boilerplate | Most | Low | Low | Low | Low |
| Hidden magic | None | None | None | Some | **Yes** |

> AutoMapper moved to a commercial licensing model for newer major versions, so verify the licence terms before adding it to a company project. Many teams now choose manual mapping, EF projections, or a source generator like Mapperly.

```csharp
// ViewModel for an MVC/Razor page: UI shaping, not an API contract
public class OrderDetailsViewModel
{
    public int Id { get; init; }
    public string CustomerName { get; init; } = "";
    public string TotalDisplay { get; init; } = "";               // "$1,249.00"
    public string StatusBadgeCss { get; init; } = "badge-secondary";
    public IReadOnlyList<SelectListItem> ShippingMethods { get; init; } = [];
    public bool CanCancel { get; init; }
}
```

:::warn If you must bind an entity
`[Bind("Name,Price")]` (allow-list) or `[BindNever]` on sensitive properties limits over-posting, but it is easy to forget when the entity changes. A dedicated DTO is the safe default.
:::

:::q What is over-posting and how do you prevent it?
Over-posting (mass assignment) is when a client sends extra properties and model binding writes them to properties I did not intend to expose, for example setting `IsPaid` or `Role` on an entity. I prevent it by never binding entities directly. I bind to request DTOs that contain only allowed fields and map to the entity manually. `[Bind]` and `[BindNever]` are weaker fallbacks.
:::

:::q DTO vs ViewModel vs Entity?
The entity maps to the database. A DTO is the contract that crosses a boundary such as the API request/response. A ViewModel is shaped for one UI view and may contain display strings and dropdown lists. In a pure API I have entities and request/response DTOs; ViewModels are for MVC/Razor/Blazor pages.
:::

:::q What does `[ApiController]` do?
It requires attribute routing, returns an automatic 400 `ValidationProblemDetails` when `ModelState` is invalid, infers binding sources (complex types from the body, simple types from route/query), infers multipart for file params, and turns error status codes into ProblemDetails responses.
:::
