### Routing

**In simple words:** Routing matches the URL and HTTP method of a request to an endpoint, such as a controller action or a minimal API handler. Web APIs use attribute routing, like `[HttpGet("{id:int}")]`. Route constraints, like `:int`, reject wrong values early with a 404. Constraints help choose a route; they are not input validation.

**Real-life example:** At a post office, the address on a letter decides which delivery route it takes. A letter with a badly formed address never reaches a route.

**Interview question:** What is the difference between conventional and attribute routing?

**Simple answer:** Conventional routing uses one central pattern like `{controller}/{action}/{id?}`, mostly for MVC apps with views. Attribute routing puts routes on controllers and actions, which suits REST APIs. `[ApiController]` requires attribute routing.

```csharp
[Route("api/orders")]
public class OrdersController : ControllerBase
{
    [HttpGet("{id:int}")]            // GET api/orders/42
    public IActionResult Get(int id) => Ok();
}
```

### Controllers and `[ApiController]`

**In simple words:** A controller is a class whose public methods (actions) handle requests. For APIs, inherit from `ControllerBase`; `Controller` adds view support you do not need. The `[ApiController]` attribute turns on API-friendly rules. For example, invalid input returns 400 automatically, and complex parameters come from the JSON body.

**Real-life example:** A bank's business counter checks your documents before the clerk even starts. An incomplete form is returned at once.

**Interview question:** What does `[ApiController]` do?

**Simple answer:** It requires attribute routing and returns an automatic 400 with `ValidationProblemDetails` when the model is invalid. It infers where parameters come from: the body for complex types, and the route or query for simple ones. It also returns ProblemDetails bodies for error status codes like 404.

### Minimal APIs

**In simple words:** Minimal APIs let you create endpoints with `app.MapGet`, `app.MapPost` and so on, without controller classes. The handler is a lambda or a method, and its parameters come automatically from the route, query, body and DI. You can group endpoints with `MapGroup`, add endpoint filters, and return `TypedResults`. They need less code and work well with Native AOT.

**Real-life example:** A food truck serves the same food as a restaurant, but with less setup and fewer staff.

**Interview question:** What are minimal APIs, and when would you use them?

**Simple answer:** They are endpoints defined directly with `MapGet` or `MapPost` and a handler, without controllers. They have less code, start faster and work with Native AOT, so they fit microservices and small APIs. With route groups, endpoint filters and `TypedResults`, they are ready for production.

```csharp
var group = app.MapGroup("/api/products").RequireAuthorization();
group.MapGet("/{id:int}", async (int id, ShopDbContext db) =>
    await db.Products.FindAsync(id) is { } p ? Results.Ok(p) : Results.NotFound());
```

### Controllers vs Minimal APIs

**In simple words:** Both styles use the same routing, middleware, auth and DI, and you can mix them in one app. Controllers give automatic validation with `[ApiController]`, five filter types, rich model binding and content negotiation. Minimal APIs are lighter, faster to start and work with Native AOT. Since .NET 10, minimal APIs also have built-in validation.

**Real-life example:** A full restaurant has many staff and clear roles, good for a big menu. A food truck is quick and light, good for a small menu.

**Interview question:** Would you choose controllers or minimal APIs for a new project?

**Simple answer:** For a large API with a big team and existing conventions, I choose controllers. For microservices, small APIs or Native AOT, I choose minimal APIs. Both run on the same platform, so the choice is about structure and team habits.

### Model binding

**In simple words:** Model binding turns request data into your method parameters. Data can come from the route, query string, headers, body, form or the DI container. You can name the source with attributes like `[FromRoute]`, `[FromQuery]`, `[FromBody]` and `[FromHeader]`. Only one parameter can come from the body, because the body is a stream that is read once.

**Real-life example:** A post office clerk takes the name from the envelope, the date from the stamp and the letter from inside. Each piece goes into the right box.

**Interview question:** Where can model binding read data from, and what is the `[FromBody]` rule?

**Simple answer:** It reads from route values, the query string, headers, form fields, the request body and DI. With `[ApiController]`, complex types come from the body and simple types from the route or query. Only one `[FromBody]` parameter is allowed per action.

```csharp
public Task<IActionResult> Create(
    [FromRoute] Guid customerId,                          // /customers/{customerId}/orders
    [FromQuery] bool notify,                              // ?notify=true
    [FromHeader(Name = "Idempotency-Key")] string? key,
    [FromBody] CreateOrderRequest body)                   // JSON body
```

### Model validation

**In simple words:** Validation checks the bound input against rules, like "required" or "between 1 and 100". Errors go into `ModelState`, and with `[ApiController]` an invalid model returns 400 with a `ValidationProblemDetails` body automatically. Use DataAnnotations attributes for simple rules and `IValidatableObject` for rules across fields. FluentValidation suits complex or async rules.

**Real-life example:** At a bank, the clerk first checks that your form is complete. Then the manager checks business rules, such as whether you have enough money.

**Interview question:** How do you validate input in ASP.NET Core?

**Simple answer:** I put DataAnnotations like `[Required]` and `[Range]` on request DTOs, and `[ApiController]` returns 400 automatically. For complex or async rules, I use FluentValidation. Business rules live in the service and return 409 or 422, and database constraints are the last safety net.

```csharp
public class OrderLineRequest
{
    [Range(1, int.MaxValue)] public int ProductId { get; set; }
    [Range(1, 100)]          public int Quantity { get; set; }
}
```

### Action results

**In simple words:** An action returns a result that tells ASP.NET Core what to send back. For APIs, `ActionResult<T>` is the best default: it returns your data with 200, or an error like 404. Helpers like `Ok()`, `CreatedAtAction()`, `NoContent()` and `NotFound()` set the correct status code. Minimal APIs use `TypedResults` instead.

**Real-life example:** A delivery app shows clear statuses: "Delivered", "Out for delivery" or "Address not found". Each status tells you exactly what happened.

**Interview question:** Why use `ActionResult<T>` instead of `IActionResult`?

**Simple answer:** `ActionResult<T>` lets me return either a `T` (200 OK) or an error result like `NotFound()`. It also tells OpenAPI the success type, so the documentation is accurate. With `IActionResult`, I must add `[ProducesResponseType]` to describe the response.

```csharp
public async Task<ActionResult<OrderDto>> Get(int id)
{
    var order = await _service.GetAsync(id);
    if (order is null) return NotFound();   // 404
    return order;                           // 200 with body
}
```

### DTOs, ViewModels, and entities

**In simple words:** An entity is your database class, tracked by EF Core. A DTO (Data Transfer Object) is the shape of data your API sends or receives, and a ViewModel is data shaped for one UI page. Never bind or return entities directly in an API. Clients could set fields they should not (over-posting), and you could leak internal data.

**Real-life example:** A bank keeps a full internal record of your account (entity). You get a printed statement with only your details (DTO), and the ATM screen shows a layout made for that screen (ViewModel).

**Interview question:** What is over-posting, and how do you prevent it?

**Simple answer:** Over-posting is when a client sends extra fields, like `"isPaid": true`, and model binding writes them to the entity. I prevent it by binding to request DTOs that contain only allowed fields. Then I map them to the entity manually or with a source generator like Mapperly.

### REST principles and constraints

**In simple words:** REST is a style for designing web APIs. You expose resources (nouns) at URLs, like `/orders/42`, and use HTTP methods to act on them. Key rules are: stateless (each request carries everything needed), cacheable, and one uniform interface. Use plural nouns, put filters in the query string, and never change data with GET.

**Real-life example:** In a library, every book has a fixed shelf number, and the same actions work for any book: find, borrow, return. You show your card on every visit, because the desk does not remember you.

**Interview question:** What makes an API RESTful?

**Simple answer:** It exposes resources at clear URLs and uses HTTP methods and status codes correctly. It is stateless, so any server can handle any request, and responses can be cached. Most real APIs reach level 2 of the Richardson maturity model: proper verbs and status codes.

### HTTP methods: safe and idempotent

**In simple words:** A safe method, like GET, does not change data. An idempotent method leaves the same server state whether you send it once or many times. GET, HEAD, OPTIONS, PUT and DELETE are idempotent; POST is not, and PATCH is not guaranteed. PUT replaces the whole resource, while PATCH changes only some fields.

**Real-life example:** Pressing a lift button five times still brings one lift: idempotent. Putting coins in a vending machine five times buys five drinks: not idempotent.

**Interview question:** What is idempotency, and which HTTP methods are idempotent?

**Simple answer:** An operation is idempotent if repeating it has the same effect on server state as doing it once. GET, HEAD, OPTIONS, PUT and DELETE are idempotent; POST is not, and PATCH depends on the patch. It matters because clients retry after network errors, so I protect POST with an `Idempotency-Key`.

### HTTP status code cheat sheet

**In simple words:** Status codes tell the client what happened. 2xx means success: 200 OK, 201 Created, 202 Accepted and 204 No Content. 4xx means a client problem: 400 bad input, 401 not logged in, 403 not allowed, 404 not found, 409 conflict and 429 too many requests. 5xx means a server problem: 500 is a bug, and 503 means "try again later".

**Real-life example:** A delivery app says "Delivered", "Wrong address", "Too many orders today" or "Our van broke down". Each message tells you whose problem it is.

**Interview question:** What is the difference between 400 and 422, and between 401 and 403?

**Simple answer:** 400 means the request is malformed or fails basic validation; 422 means it is well formed but breaks a business rule. 401 means "we don't know who you are", and 403 means "we know you, but you may not do this". Many teams use 400 for both validation cases; the key is to be consistent.

### Request/response, headers, and parameters

**In simple words:** Use the route for the resource ID (`/orders/42`), the query string for filters, sorting and paging, and the body for data you create or update. Headers carry extra information, like `Content-Type`, `Accept`, `Authorization` and `Idempotency-Key`. With `ETag` and `If-None-Match`, the server can reply 304 Not Modified and save bandwidth. Never put secrets in the URL, because proxies and browsers log URLs.

**Real-life example:** A parcel has an address (route), delivery notes on the label (headers) and the items inside the box (body).

**Interview question:** How does an ETag help with caching and concurrency?

**Simple answer:** An ETag is a version tag for a resource. On GET, the client sends `If-None-Match`, and if nothing changed, the server returns 304 with no body. On update, the client sends `If-Match`, and if the version changed, the server returns 412, so nobody overwrites someone else's change.

### Content negotiation and custom formatters

**In simple words:** Content negotiation lets the client choose the response format. The client sends an `Accept` header, like `application/json` or `text/csv`, and ASP.NET Core picks a matching output formatter. JSON is the default, and an unsupported request body type returns 415. You can write a custom formatter, for example for CSV.

**Real-life example:** A tourist office gives you the city map in the language you ask for. If it does not have that language, it gives you English, or says "not available".

**Interview question:** What is content negotiation?

**Simple answer:** The server reads the `Accept` header and uses a matching output formatter to write the response. It reads the request body with the input formatter that matches `Content-Type`. With `ReturnHttpNotAcceptable = true`, an unsupported `Accept` returns 406 instead of falling back to JSON.

### JSON serialization: System.Text.Json vs Newtonsoft.Json

**In simple words:** ASP.NET Core uses System.Text.Json by default. It is faster, uses less memory, and supports source generators (code created at compile time) for Native AOT. Newtonsoft.Json is older and more flexible, and some old projects still need it. System.Text.Json is stricter, so check settings like enum handling when you migrate.

**Real-life example:** A new ticket gate is faster but accepts only one card format. The old gate is slower but accepts many kinds of cards.

**Interview question:** System.Text.Json or Newtonsoft.Json, and what changes when you migrate?

**Simple answer:** I use System.Text.Json by default for speed and AOT support. When migrating, enums become numbers unless I add `JsonStringEnumConverter`, and private setters are ignored unless I use `[JsonInclude]`. Controllers and minimal APIs have separate JSON options, so I configure both.

```csharp
builder.Services.AddControllers().AddJsonOptions(o =>
    o.JsonSerializerOptions.Converters.Add(new JsonStringEnumConverter()));
```

### Swagger / OpenAPI

**In simple words:** OpenAPI is a standard JSON or YAML file that describes your API: URLs, parameters, data shapes and security. Swagger UI is a web page that shows this file and lets you try the API. Since .NET 9, ASP.NET Core creates the document itself with `AddOpenApi()`. It includes no UI, so you add Swagger UI or Scalar.

**Real-life example:** A restaurant menu lists every dish, its price and what comes with it. Swagger UI is a menu where you can also taste a sample.

**Interview question:** Would you use Swashbuckle or the built-in OpenAPI support?

**Simple answer:** From .NET 9, the template uses `Microsoft.AspNetCore.OpenApi`, which creates the document at `/openapi/v1.json` but has no UI. I add Scalar or Swagger UI on top, or use Swashbuckle or NSwag if I need their extra features. I protect or disable the UI in production.

### API versioning

**In simple words:** Versioning lets you change your API without breaking old clients. The usual library is Asp.Versioning. The most common style is a version in the URL, like `/api/v2/orders`; a query string or header also works. Create a new version only for breaking changes, like removing or renaming a field.

**Real-life example:** A city changes a bus route a lot, so it starts route 12B. Route 12A keeps running for a few months with notices, then stops.

**Interview question:** How do you version a Web API?

**Simple answer:** I use the Asp.Versioning library with URL versions like `/api/v2/orders`, because they are clear and easy for gateways. I mark old versions as deprecated and send `Sunset` headers with a retirement date. Adding new optional fields is not a breaking change, so that stays in the same version.

### Rate limiting (built-in, .NET 7+)

**In simple words:** Rate limiting caps how many requests a client can send in a time window. Set the rejection code to 429 Too Many Requests, because the default is 503. There are four algorithms: fixed window, sliding window, token bucket and concurrency. Counters live in one server's memory, so three servers allow three times the limit.

**Real-life example:** An ATM lets you take out only a set amount per day. After that, it tells you to try again tomorrow.

**Interview question:** How do you add rate limiting, and what is its main limitation?

**Simple answer:** I call `AddRateLimiter` with named policies, add `UseRateLimiter()`, and apply a policy with `RequireRateLimiting` or `[EnableRateLimiting]`. The built-in limiter counts per instance, in memory. For a true global limit, I use an API gateway or a Redis-based limiter.

```csharp
builder.Services.AddRateLimiter(o =>
{
    o.RejectionStatusCode = StatusCodes.Status429TooManyRequests;
    o.AddFixedWindowLimiter("public", p =>
    { p.PermitLimit = 60; p.Window = TimeSpan.FromMinutes(1); });
});
```

### Error responses with ProblemDetails

**In simple words:** ProblemDetails is a standard JSON format for errors, defined in RFC 9457. It has fields like `type`, `title`, `status`, `detail` and `instance`, and you can add extras like `traceId`. Its content type is `application/problem+json`. Use one error format everywhere, so clients need only one error parser.

**Real-life example:** All hospitals use the same discharge form. Any doctor can read it quickly, because the fields are always in the same place.

**Interview question:** How do you return consistent error responses in ASP.NET Core?

**Simple answer:** I call `AddProblemDetails()`, `UseExceptionHandler()` and `UseStatusCodePages()`, so exceptions and empty error codes become ProblemDetails. `[ApiController]` already returns `ValidationProblemDetails` for invalid models. I add a `traceId` to every error, so support can find the matching log entry.

```json
{
  "title": "Insufficient stock",
  "status": 409,
  "detail": "Product 17 has 2 units left.",
  "traceId": "00-7d5f...-01"
}
```

### Pagination: offset vs keyset (cursor)

**In simple words:** Pagination returns a big list in small pages. Offset paging uses `page` and `pageSize` with `Skip` and `Take`; it can jump to any page, but deep pages get slow because the database still reads all skipped rows. Keyset (cursor) paging continues after the last row you saw, like `WHERE Id < lastId`. It stays fast with the right index and does not skip or repeat rows when data changes.

**Real-life example:** Offset is like finding page 500 by counting every page from the start. Keyset is like opening the book at your bookmark.

**Interview question:** How do you paginate a large table?

**Simple answer:** For admin grids with page numbers, I use offset paging with a stable `OrderBy` and a maximum page size. For large tables, feeds and public APIs, I use keyset paging with a matching index. Offset gets slower on deep pages and can skip or repeat rows when data changes.

### Sorting and filtering

**In simple words:** Filtering picks only some rows, like `?status=Paid`, and sorting orders them, like `?sortBy=total`. Both come from the query string. Allow only sort fields from a fixed list (a whitelist), and never put client text into SQL. Always add a unique tie-breaker, like `Id`, so the order of pages is stable.

**Real-life example:** An online shop lets you sort by price or rating from a dropdown. You cannot type your own command into it.

**Interview question:** How do you make sorting by a client-supplied column safe?

**Simple answer:** I map each allowed field name to a typed `OrderBy` with a `switch`. Unknown values fall back to a default or return 400. I never concatenate the string into SQL, and I always add `Id` as a tie-breaker.

```csharp
q = sortBy switch
{
    "total" => q.OrderBy(o => o.Total).ThenBy(o => o.Id),
    _       => q.OrderByDescending(o => o.CreatedAt).ThenByDescending(o => o.Id)
};
```

### API validation summary

**In simple words:** Validation happens in layers. Route constraints reject bad IDs, DTO validation returns 400 with field errors, and paging and sort values are limited. Business rules return 409 or 422, and database constraints catch rare race conditions. Always validate on the server, even if the web or mobile app already checks the input.

**Real-life example:** The airline app checks your bag size. The airport still checks it at the counter, because anyone can skip the app.

**Interview question:** If the frontend already validates input, why validate on the server?

**Simple answer:** The client is not a security boundary; anyone can call the API directly with Postman or a script. So the server checks the shape of the input, the business rules and the data constraints. Client validation is only for a better user experience.

### Idempotency keys for POST

**In simple words:** POST is not idempotent, so a retry after a timeout can create a second order or payment. To stop this, the client sends a unique `Idempotency-Key` header, usually a GUID. The server saves the first response for that key. If the same key comes again, it returns the saved response and does not run the action again.

**Real-life example:** You pay a bill and get a receipt number. If you show the same receipt again, the cashier says "already paid" and does not charge you twice.

**Interview question:** How do you prevent duplicate orders when a client retries a POST?

**Simple answer:** I require an `Idempotency-Key` header and store the first response under that key in Redis or a database table. Retries get the stored response. For two requests at the same moment, I use an atomic "in progress" marker or a unique index, so only one creates the order.

### Complete CRUD example: OrdersController

**In simple words:** CRUD means Create, Read, Update and Delete. A good controller is thin: it handles only HTTP details like routes, binding, status codes and headers. A service does the business logic and data access. Use DTOs in and out, return 201 with a `Location` header on create, and model actions like cancel as `POST /orders/{id}/cancel`.

**Real-life example:** In a restaurant, the waiter takes your order and brings the food. The cook does the real work, and the waiter never cooks.

**Interview question:** What makes a controller well structured?

**Simple answer:** It is thin and passes business logic to a service. It uses DTOs, `ActionResult<T>` with `[ProducesResponseType]`, and the right status codes: 200, 201 with `Location`, 204, 404 and 409. Errors become ProblemDetails through a global handler, and each request calls `SaveChangesAsync` once.

### The same API as minimal endpoints

**In simple words:** You can build the same orders API with minimal APIs. The service, DTOs and error handling stay the same; only the HTTP layer changes. You group endpoints with `MapGroup`, return `TypedResults`, and use union types like `Results<Ok<OrderDto>, NotFound>`. These types also describe all possible responses for OpenAPI.

**Real-life example:** The same kitchen serves both the dining room and the takeaway window. The food is the same; only the counter is different.

**Interview question:** How do you organise a minimal API so it stays clean?

**Simple answer:** I put endpoints in a static class with an extension method, like `MapOrderEndpoints`, and use `MapGroup` for the shared prefix, tags and authorization. Handlers return `TypedResults`, so unit tests can check the result type directly. Business logic stays in the same service the controllers use.

```csharp
var g = app.MapGroup("/api/v1/orders").RequireAuthorization();
g.MapGet("/{id:int}", async Task<Results<Ok<OrderDto>, NotFound>> (
        int id, IOrderService svc, CancellationToken ct) =>
    await svc.GetAsync(id, ct) is { } o ? TypedResults.Ok(o) : TypedResults.NotFound());
```
