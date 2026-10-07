## Web API

### REST principles and constraints

**Definition.** REST (Representational State Transfer) is an architectural style for networked systems described by Roy Fielding. A "RESTful API" exposes **resources** (nouns) identified by URLs and manipulated through standard HTTP methods using **representations** (usually JSON).

**Why it matters.** Interviewers use REST questions to check whether you understand *why* an API is designed a certain way (scalability, cacheability, evolvability), not only how to write a controller.

| Constraint | Meaning | Practical consequence |
|---|---|---|
| Client-server | UI and data storage separated | Frontend and API evolve independently |
| **Stateless** | Each request carries everything needed; no server session | Any instance can serve any request, so scale out behind a load balancer. Auth via JWT, not server sessions |
| **Cacheable** | Responses declare if they may be cached | `Cache-Control`, `ETag`, CDN caching for GETs |
| **Uniform interface** | Resource identification (URLs), manipulation via representations, self-descriptive messages (`Content-Type`, status codes), HATEOAS (links) | Predictable API for every client |
| Layered system | Client cannot tell if it talks to the origin or an intermediary | Gateways, proxies, CDNs, WAF |
| Code on demand (optional) | Server may send executable code | Rarely used |

**Richardson Maturity Model** (how "REST-ful" an API is):

| Level | Description | Example |
|---|---|---|
| 0 | One endpoint, one verb (RPC over HTTP) | `POST /api` with `{ "action": "getOrder" }` |
| 1 | Separate resources | `POST /orders/42` |
| 2 | **Proper HTTP verbs + status codes** (where most real APIs stop) | `GET /orders/42` -> 200, `POST /orders` -> 201 |
| 3 | HATEOAS: responses contain links to next actions | `"links": [{ "rel": "cancel", "href": "/orders/42/cancel" }]` |

#### Resource naming conventions

| Do | Do not |
|---|---|
| Plural nouns: `/orders`, `/customers/7/orders` | Verbs: `/getOrders`, `/createOrder` |
| Lowercase, hyphens: `/order-items` | Camel/Pascal case or underscores in paths |
| Hierarchy for ownership (max ~2 levels): `/orders/42/lines` | Deep nesting: `/a/1/b/2/c/3/d/4` |
| Filters in the query: `/orders?status=paid&from=2026-01-01` | Filters in the path: `/orders/paid/2026` |
| Sub-resource for an action that is not CRUD: `POST /orders/42/cancel` | `GET /cancelOrder?id=42` (a GET must not change state) |
| No file extensions or trailing slashes | `/orders.json` |

:::example E-commerce resource model
`/products`, `/products/{id}`, `/customers/{id}/orders`, `/orders/{id}`, `/orders/{id}/lines`, `/orders/{id}/payments`. Commands that do not map to CRUD are modelled as POST sub-resources: `POST /orders/{id}/cancel`, `POST /orders/{id}/refunds`. The response to the refund is a new `refund` resource with its own URL.
:::

### HTTP methods: safe and idempotent

**Definitions.** A method is **safe** if it does not change server state (read-only). A method is **idempotent** if sending the same request *N* times leaves the server in the same state as sending it once. Idempotency is about **state**, not about getting the same response (a second `DELETE` returns 404 but the state is still "deleted").

| Method | Purpose | Safe | Idempotent | Request body | Typical success |
|---|---|---|---|---|---|
| **GET** | Read a resource/collection | Yes | Yes | No | 200 |
| **HEAD** | GET without body (check existence, headers) | Yes | Yes | No | 200 |
| **OPTIONS** | Capabilities, CORS preflight | Yes | Yes | No | 200/204 |
| **POST** | Create a resource, or run a command | No | **No** | Yes | 201 / 202 / 200 |
| **PUT** | **Replace** a resource completely (or create at a known URL) | No | **Yes** | Yes (full) | 200 / 204 (201 if created) |
| **PATCH** | **Partially** modify a resource | No | Not guaranteed | Yes (partial/patch doc) | 200 / 204 |
| **DELETE** | Remove a resource | No | **Yes** | No | 204 (404 if already gone) |

:::warn POST is not idempotent
A client that retries `POST /orders` after a timeout can create two orders. That is why payment/order APIs support an **idempotency key** (covered later). Never use GET to change state: crawlers, prefetchers, and proxies call GET freely.
:::

#### PUT vs PATCH

| | PUT | PATCH |
|---|---|---|
| Semantics | Replace the **whole** resource | Change **some** fields |
| Missing fields in body | Reset to default/null | Left unchanged |
| Idempotent | Yes | Depends on the patch (`replace` yes, `add` to a list no) |
| Payload size | Full object | Small |
| Formats | Normal DTO | **JSON Patch** (RFC 6902) or **JSON Merge Patch** (RFC 7396) |

```csharp
// PUT: full replacement, idempotent
[HttpPut("{id:int}")]
public async Task<IActionResult> Replace(
    int id, UpdateProductRequest req, CancellationToken ct)
{
    var p = await _db.Products.FirstOrDefaultAsync(x => x.Id == id, ct);
    if (p is null) return NotFound();
    p.Name = req.Name;               // every updatable field is overwritten
    p.Price = req.Price;
    p.Description = req.Description; // null clears it
    await _db.SaveChangesAsync(ct);
    return NoContent();
}
```

```csharp
// PATCH with JSON Patch (RFC 6902). Content-Type: application/json-patch+json
// Body: [ { "op": "replace", "path": "/price", "value": 19.99 },
//         { "op": "remove",  "path": "/description" } ]
[HttpPatch("{id:int}")]
[Consumes("application/json-patch+json")]
public async Task<IActionResult> Patch(
    int id, [FromBody] JsonPatchDocument<ProductPatchDto> patch, CancellationToken ct)
{
    var p = await _db.Products.FirstOrDefaultAsync(x => x.Id == id, ct);
    if (p is null) return NotFound();

    var dto = new ProductPatchDto { Price = p.Price, Description = p.Description };
    patch.ApplyTo(dto, ModelState);               // only whitelisted properties exist on the DTO
    if (!ModelState.IsValid || !TryValidateModel(dto))
        return ValidationProblem(ModelState);

    p.Price = dto.Price;
    p.Description = dto.Description;
    await _db.SaveChangesAsync(ct);
    return NoContent();
}
```

**Setup note.** `JsonPatchDocument<T>` (`Microsoft.AspNetCore.JsonPatch`) has historically required **Newtonsoft.Json** (`AddNewtonsoftJson()` or a dedicated `NewtonsoftJsonPatchInputFormatter` so the rest of the app keeps `System.Text.Json`). ASP.NET Core 10 introduced System.Text.Json-based JSON Patch support in a separate package; verify the package name and status in the official release notes before relying on it.

**Alternative: simple partial update DTO.** Make every property nullable and update only non-null values. Weakness: you cannot distinguish "field omitted" from "field explicitly set to null". Use JSON Merge Patch, or an `Optional<T>` wrapper when that distinction matters.

:::q PUT vs PATCH, and which is idempotent?
PUT replaces the whole resource, so sending it twice leaves the same state: idempotent. PATCH applies a partial change; a `replace` patch is idempotent but an "append item" patch is not, so PATCH is not guaranteed idempotent. I use PUT for full updates from a form and PATCH (JSON Patch or merge patch) for small changes like toggling a status.
:::

### HTTP status code cheat sheet

| Code | Name | When to use | ASP.NET Core |
|---|---|---|---|
| **200** | OK | Successful GET/PUT/PATCH with a body | `Ok(x)` |
| **201** | Created | POST created a resource; return `Location` header + the resource | `CreatedAtAction(...)` |
| **202** | Accepted | Request accepted, processing is **asynchronous** (return a status URL) | `Accepted(uri, x)` |
| **204** | No Content | Success with no body (DELETE, PUT/PATCH) | `NoContent()` |
| **301** | Moved Permanently | Resource has a new permanent URL (cached by clients) | `RedirectPermanent(url)` |
| **304** | Not Modified | Conditional GET: `If-None-Match` matched the `ETag`, client uses its cache | `StatusCode(304)` |
| **400** | Bad Request | Malformed JSON, failed validation, bad query values | `BadRequest()`, `ValidationProblem()` |
| **401** | Unauthorized | **Not authenticated** (missing/invalid/expired token). Send `WWW-Authenticate` | `Unauthorized()` |
| **403** | Forbidden | Authenticated but **not allowed** | `Forbid()` |
| **404** | Not Found | Resource does not exist (also to hide existence from unauthorised users) | `NotFound()` |
| **405** | Method Not Allowed | URL exists but not for this verb; include `Allow` header | automatic |
| **409** | Conflict | State conflict: duplicate unique value, version/ETag conflict, illegal transition | `Conflict()` |
| **415** | Unsupported Media Type | Request `Content-Type` not supported | automatic |
| **422** | Unprocessable Content | Syntax OK but **semantically** invalid (business rule violated) | `UnprocessableEntity()` |
| **429** | Too Many Requests | Rate limit hit; send `Retry-After` | rate limiter |
| **500** | Internal Server Error | Unhandled server bug. Never include stack traces | exception handler |
| **502** | Bad Gateway | Gateway got an invalid response from upstream | proxy |
| **503** | Service Unavailable | Overloaded or in maintenance; send `Retry-After` | health/circuit breaker |
| **504** | Gateway Timeout | Gateway timed out waiting for upstream | proxy |

Also useful: **412 Precondition Failed** (`If-Match` ETag mismatch on update, optimistic concurrency), **206** partial content (range requests), **410 Gone** (permanently deleted).

**Decision rules interviewers like:**

- **400 vs 422.** 400 = the request could not be parsed or fails basic validation. 422 = well-formed but violates a business rule. Many teams use 400 for both; be consistent and document it.
- **401 vs 403.** 401 = "who are you?" 403 = "I know who you are, you may not do this."
- **404 vs 403 for others' data.** Return 404 for another tenant's order to avoid revealing it exists.
- **409.** Duplicate email, concurrent edit (`DbUpdateConcurrencyException`), order already shipped.
- **500 vs 503.** 500 is a bug, 503 is "not now, try later".

:::scenario Which status code for each case?
(1) Register with an email that exists: **409**. (2) POST body is `{"qty":` (broken JSON): **400**. (3) Quantity is 0 but must be 1-100: **400** (validation) with field errors. (4) Cancel an already shipped order: **409** or **422** (state rule). (5) Valid token, user is not an admin: **403**. (6) Token expired: **401**. (7) Client sends XML to a JSON-only endpoint: **415**. (8) Create report that takes 2 minutes: **202** with `Location: /reports/{id}/status`.
:::

### Request/response, headers, and parameters

| Header | Direction | Purpose |
|---|---|---|
| `Content-Type` | Both | Media type of the **body** (`application/json`) |
| `Accept` | Request | Media types the client can handle (content negotiation) |
| `Authorization` | Request | `Bearer <jwt>` |
| `ETag` | Response | Version fingerprint of the representation |
| `If-None-Match` | Request | Send cached ETag; server replies **304** if unchanged |
| `If-Match` | Request | Update only if ETag matches, else **412** (optimistic concurrency) |
| `Cache-Control` | Both | `no-store`, `private, max-age=60`, `public, max-age=3600` |
| `Location` | Response | URL of the created resource (201) or status resource (202) |
| `Retry-After` | Response | Seconds/date to wait (429, 503) |
| `X-Correlation-ID` | Both | Trace one request across services |
| `Idempotency-Key` | Request | De-duplicate POST retries |
| `Link` | Response | Pagination links (RFC 8288) |
| `WWW-Authenticate` | Response | Challenge for 401 |
| `Sunset` / `Deprecation` | Response | API version retirement signals |

```csharp
// Conditional GET with ETag (saves bandwidth + DB work for unchanged resources)
[HttpGet("{id:int}")]
public async Task<ActionResult<ProductDto>> Get(int id, CancellationToken ct)
{
    var p = await _db.Products.AsNoTracking().FirstOrDefaultAsync(x => x.Id == id, ct);
    if (p is null) return NotFound();

    var etag = $"\"{Convert.ToBase64String(p.RowVersion)}\"";     // SQL Server rowversion

    if (Request.Headers.IfNoneMatch == etag)
        return StatusCode(StatusCodes.Status304NotModified);

    Response.Headers.ETag = etag;
    Response.Headers.CacheControl = "private, max-age=60";
    return new ProductDto(p.Id, p.Name, p.Price);
}

// Optimistic concurrency on update with If-Match -> 412
[HttpPut("{id:int}")]
public async Task<IActionResult> Update(int id, UpdateProductRequest req, CancellationToken ct)
{
    var p = await _db.Products.FirstOrDefaultAsync(x => x.Id == id, ct);
    if (p is null) return NotFound();

    var current = $"\"{Convert.ToBase64String(p.RowVersion)}\"";
    if (Request.Headers.IfMatch.Count > 0 && Request.Headers.IfMatch != current)
        return StatusCode(StatusCodes.Status412PreconditionFailed);

    p.Name = req.Name; p.Price = req.Price;
    try { await _db.SaveChangesAsync(ct); }
    catch (DbUpdateConcurrencyException) { return Conflict(); }   // someone else won the race
    return NoContent();
}
```

#### Query vs route vs body parameters

| Use | For | Example |
|---|---|---|
| **Route** | Identity of a resource | `/orders/42` |
| **Query string** | Filtering, sorting, paging, searching, optional flags | `/orders?status=paid&sort=-createdAt&page=2` |
| **Body** | Payload to create/update (can be large/structured) | `POST /orders` + JSON |
| **Header** | Metadata, cross-cutting concerns (auth, correlation, version, idempotency) | `Authorization`, `X-Correlation-ID` |

Do not put secrets in the URL (logged by proxies and stored in browser history). Do not send a body with GET.

:::q What is idempotency and which HTTP methods are idempotent?
An operation is idempotent if repeating it has the same effect on server state as doing it once. GET, HEAD, OPTIONS, PUT and DELETE are idempotent; POST is not, and PATCH depends. It matters because networks fail and clients retry: an idempotent operation is safe to retry. For POST I accept an `Idempotency-Key` header and store the first result.
:::
