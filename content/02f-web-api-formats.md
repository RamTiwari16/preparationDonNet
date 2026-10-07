### Content negotiation and custom formatters

**Definition.** *Content negotiation* lets the client and server agree on the representation. The client's **`Accept`** header says what it can read (`application/json`, `text/csv`); the **`Content-Type`** header says what it is sending. ASP.NET Core picks an **input formatter** (request) and an **output formatter** (response) accordingly.

| Situation | Result |
|---|---|
| `Accept` missing or `*/*` | First output formatter that can write the type (JSON by default) |
| `Accept: application/xml` and no XML formatter | Default: falls back to JSON. With `ReturnHttpNotAcceptable = true`: **406 Not Acceptable** |
| Request `Content-Type` has no input formatter | **415 Unsupported Media Type** |
| `[Produces("application/json")]` | Forces that response type for the action/controller |
| `[Consumes("application/json")]` | Action only accepts that request type |

```csharp
builder.Services.AddControllers(o =>
{
    o.ReturnHttpNotAcceptable = true;                    // strict: 406 instead of silent JSON
    o.OutputFormatters.Add(new CsvOutputFormatter());    // custom formatter (below)
})
.AddXmlSerializerFormatters();                           // opt-in XML (input + output)

[HttpGet]
[Produces("application/json", "application/xml", "text/csv")]
public ActionResult<IEnumerable<OrderDto>> List() => Ok(_orders.GetAll());
// GET /api/orders   Accept: text/csv   ->   CSV file content
```

```csharp
// Custom output formatter: CSV for lists of OrderDto
public class CsvOutputFormatter : TextOutputFormatter
{
    public CsvOutputFormatter()
    {
        SupportedMediaTypes.Add("text/csv");
        SupportedEncodings.Add(Encoding.UTF8);
    }

    protected override bool CanWriteType(Type? type) =>
        type is not null && typeof(IEnumerable<OrderDto>).IsAssignableFrom(type);

    public override async Task WriteResponseBodyAsync(
        OutputFormatterWriteContext context, Encoding selectedEncoding)
    {
        var rows = (IEnumerable<OrderDto>)context.Object!;
        var sb = new StringBuilder("Id,Total,Status\n");
        foreach (var r in rows)
            sb.Append(r.Id).Append(',')
              .Append(r.Total.ToString(CultureInfo.InvariantCulture)).Append(',')
              .Append(Escape(r.Status)).Append('\n');

        await context.HttpContext.Response.WriteAsync(sb.ToString(), selectedEncoding);
    }

    // Quote values and neutralise CSV/formula injection (=, +, -, @)
    private static string Escape(string s) =>
        "\"" + (s.Length > 0 && "=+-@".Contains(s[0]) ? "'" + s : s).Replace("\"", "\"\"") + "\"";
}
```

Minimal APIs have no formatter pipeline: they write JSON by default. For other formats inspect `Accept` yourself or return `Results.Text(csv, "text/csv")`.

### JSON serialization: System.Text.Json vs Newtonsoft.Json

**Definition.** ASP.NET Core uses **System.Text.Json (STJ)** by default since 3.0. **Newtonsoft.Json** (Json.NET) is the older, more flexible library, still used for legacy features.

| | System.Text.Json | Newtonsoft.Json |
|---|---|---|
| Default in ASP.NET Core | **Yes** | No (`AddNewtonsoftJson()`) |
| Speed / allocations | Faster, less memory, span-based | Slower |
| AOT / trimming | **Source generators**, AOT-ready | Reflection-heavy |
| Strictness | Strict (no comments/trailing commas, no private setters unless `[JsonInclude]`) | Lenient, many auto-conversions |
| Dynamic data | `JsonNode`, `JsonDocument` | `JObject`, `dynamic`, `JToken` |
| Polymorphism | **Built in since .NET 7** (`[JsonPolymorphic]`) | `TypeNameHandling` (security risk) |
| JSON Patch | Separate support (see above) | Native |
| Extras | Naming policies incl. snake/kebab (.NET 8) | `[JsonObject]`, converters, `IContractResolver`, `ReferenceLoopHandling` |

```csharp
// One place for options. Controllers and minimal APIs use DIFFERENT option objects.
static void Configure(JsonSerializerOptions o)
{
    o.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;        // web default
    o.DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull;
    o.Converters.Add(new JsonStringEnumConverter());            // "Paid" instead of 2
    o.ReferenceHandler = ReferenceHandler.IgnoreCycles;         // break entity cycles
    o.PropertyNameCaseInsensitive = true;                       // web default
}
builder.Services.AddControllers().AddJsonOptions(o => Configure(o.JsonSerializerOptions));
builder.Services.ConfigureHttpJsonOptions(o => Configure(o.SerializerOptions));  // minimal APIs
```

```csharp
public class ProductDto
{
    [JsonPropertyName("sku")]                         public string Code { get; set; } = "";
    [JsonIgnore]                                      public string InternalNote { get; set; } = "";
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] public string? Brand { get; set; }
    [JsonConverter(typeof(JsonStringEnumConverter))]  public ProductStatus Status { get; set; }
}

// Source generator: no reflection at runtime, faster startup, required for Native AOT
[JsonSerializable(typeof(ProductDto))]
[JsonSerializable(typeof(List<ProductDto>))]
[JsonSourceGenerationOptions(PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase)]
public partial class AppJsonContext : JsonSerializerContext { }

builder.Services.ConfigureHttpJsonOptions(o =>
    o.SerializerOptions.TypeInfoResolverChain.Insert(0, AppJsonContext.Default));
```

```csharp
// Polymorphism (STJ, .NET 7+): the "kind" discriminator tells the deserializer the subtype
[JsonPolymorphic(TypeDiscriminatorPropertyName = "kind")]
[JsonDerivedType(typeof(CardPayment), "card")]
[JsonDerivedType(typeof(PayPalPayment), "paypal")]
public abstract record Payment(decimal Amount);
public record CardPayment(decimal Amount, string Last4) : Payment(Amount);
public record PayPalPayment(decimal Amount, string Email) : Payment(Amount);
// { "kind": "card", "amount": 49.9, "last4": "4242" }  -> CardPayment

// Newtonsoft setup if you must
builder.Services.AddControllers().AddNewtonsoftJson(o =>
{
    o.SerializerSettings.ContractResolver = new CamelCasePropertyNamesContractResolver();
    o.SerializerSettings.ReferenceLoopHandling = ReferenceLoopHandling.Ignore;
    o.SerializerSettings.NullValueHandling = NullValueHandling.Ignore;
});
```

:::warn Typical STJ surprises when migrating from Newtonsoft
Enums serialise as numbers unless you add `JsonStringEnumConverter`. Fields and private setters are ignored unless `[JsonInclude]`. A property that is `null` in JSON for a non-nullable type is a validation problem, not silently defaulted. `DateTime` is ISO 8601 and round-trips `Kind` differently, so store/send UTC (`DateTimeOffset`). Controllers and minimal APIs have **separate** options objects, so configure both. .NET 9/10 add stricter options (for example disallowing duplicate properties); verify in the release notes.
:::

### Swagger / OpenAPI

**Definition.** **OpenAPI** is the standard, machine-readable description (JSON/YAML) of an HTTP API: paths, parameters, schemas, responses, auth. **Swagger UI** is a web page that renders it and lets you call the API. "Swagger" is the old name of the spec.

**Why it matters.** Living documentation, contract testing, client generation (NSwag, Kiota, openapi-generator), and Postman import.

| | Swashbuckle.AspNetCore | NSwag | Built-in `Microsoft.AspNetCore.OpenApi` (.NET 9+) |
|---|---|---|---|
| Generates document | Yes | Yes | Yes (`AddOpenApi`, `MapOpenApi`) |
| UI | Swagger UI included | Swagger UI/ReDoc included | **None**: add Swagger UI, Scalar, or ReDoc |
| Client generation | No | **Yes** (C#/TS) | No (use Kiota/NSwag on the JSON) |
| Template status | Default through .NET 8; **removed from the .NET 9 Web API template** | Optional | **Default from .NET 9** |
| Extensibility | Filters (`IOperationFilter`) | Processors | Document/operation/schema transformers |

```csharp
// A) Built-in OpenAPI (.NET 9+) with a JWT security scheme via a document transformer
builder.Services.AddOpenApi("v1", options =>
{
    options.AddDocumentTransformer((doc, context, ct) =>
    {
        doc.Info = new OpenApiInfo { Title = "Shop API", Version = "v1" };
        doc.Components ??= new OpenApiComponents();
        doc.Components.SecuritySchemes["Bearer"] = new OpenApiSecurityScheme
        {
            Type = SecuritySchemeType.Http,
            Scheme = "bearer",
            BearerFormat = "JWT"
        };
        return Task.CompletedTask;
    });
});
// ...
app.MapOpenApi();                                   // /openapi/v1.json
// UI: e.g. app.MapScalarApiReference();  (Scalar.AspNetCore) or Swagger UI pointed at the JSON
// NOTE: types above are Microsoft.OpenApi 1.x (.NET 8/9). .NET 10 uses Microsoft.OpenApi 2.x,
// where security-scheme/reference types changed: verify against the .NET 10 docs.
```

```csharp
// B) Swashbuckle (classic) with JWT "Authorize" button and XML comments
builder.Services.AddEndpointsApiExplorer();          // needed for minimal APIs
builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new OpenApiInfo { Title = "Shop API", Version = "v1" });
    c.IncludeXmlComments(Path.Combine(AppContext.BaseDirectory, "Shop.Api.xml"));

    c.AddSecurityDefinition("Bearer", new OpenApiSecurityScheme
    {
        Type = SecuritySchemeType.Http,
        Scheme = "bearer",
        BearerFormat = "JWT",
        In = ParameterLocation.Header,
        Description = "Paste the JWT only (without the 'Bearer ' prefix)"
    });
    c.AddSecurityRequirement(new OpenApiSecurityRequirement
    {
        [new OpenApiSecurityScheme
        {
            Reference = new OpenApiReference { Type = ReferenceType.SecurityScheme, Id = "Bearer" }
        }] = new List<string>()
    });
});

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();                              // /swagger
}
```

> Swashbuckle 10 moved to Microsoft.OpenApi 2.x, which changes the security-scheme reference types used above. Pin the package version or verify the migration notes for your version.

```csharp
// Make the document accurate: declare ALL responses
[HttpGet("{id:int}")]
[ProducesResponseType<OrderDto>(StatusCodes.Status200OK)]
[ProducesResponseType(StatusCodes.Status404NotFound)]
[ProducesResponseType<ProblemDetails>(StatusCodes.Status401Unauthorized)]
public Task<ActionResult<OrderDto>> Get(int id) => ...

// Minimal API metadata
app.MapGet("/orders/{id}", GetOrder)
   .WithName("GetOrder").WithSummary("Get one order").WithTags("Orders")
   .Produces<OrderDto>().ProducesProblem(StatusCodes.Status404NotFound);
```

:::tip Production hygiene
Do not expose Swagger UI publicly in production unless intended; protect or disable it. Generate the OpenAPI JSON in CI and diff it to catch accidental breaking changes. Treat the spec as the contract: consumers generate clients from it.
:::

### API versioning

**Definition.** Versioning lets you change an API without breaking existing clients. The standard library is **Asp.Versioning** (`Asp.Versioning.Mvc`, `Asp.Versioning.Http` for minimal APIs, `Asp.Versioning.Mvc.ApiExplorer`).

| Strategy | Example | Pros | Cons |
|---|---|---|---|
| **URL segment** | `/api/v2/orders` | Simple, visible, cache/gateway friendly. **Most common** | URL changes between versions |
| Query string | `/api/orders?api-version=2.0` | Easy to add | Easy to forget, cache keys |
| Header | `X-Api-Version: 2.0` | Clean URLs | Hard to test in a browser |
| Media type | `Accept: application/vnd.shop.v2+json` | Purest REST | Complex for clients |

```csharp
builder.Services.AddApiVersioning(o =>
{
    o.DefaultApiVersion = new ApiVersion(1, 0);
    o.AssumeDefaultVersionWhenUnspecified = true;
    o.ReportApiVersions = true;     // adds api-supported-versions / api-deprecated-versions headers
    o.ApiVersionReader = ApiVersionReader.Combine(
        new UrlSegmentApiVersionReader(),
        new HeaderApiVersionReader("X-Api-Version"),
        new QueryStringApiVersionReader("api-version"));
})
.AddMvc()
.AddApiExplorer(o =>
{
    o.GroupNameFormat = "'v'VVV";          // v1, v2 -> one Swagger doc per version
    o.SubstituteApiVersionInUrl = true;
});

[ApiController]
[ApiVersion("1.0", Deprecated = true)]    // still works, advertised as deprecated
[ApiVersion("2.0")]
[Route("api/v{version:apiVersion}/orders")]
public class OrdersController : ControllerBase
{
    [HttpGet("{id:int}"), MapToApiVersion("1.0")]
    public ActionResult<OrderV1Dto> GetV1(int id) => Ok(/* old shape */);

    [HttpGet("{id:int}"), MapToApiVersion("2.0")]
    public ActionResult<OrderV2Dto> GetV2(int id) => Ok(/* new shape */);
}
```

```csharp
// Minimal APIs
var orders = app.NewVersionedApi("Orders")
                .MapGroup("/api/v{version:apiVersion}/orders")
                .HasDeprecatedApiVersion(1.0)
                .HasApiVersion(2.0);

orders.MapGet("/{id:int}", (int id) => new OrderV1Dto(id)).MapToApiVersion(1.0);
orders.MapGet("/{id:int}", (int id) => new OrderV2Dto(id)).MapToApiVersion(2.0);

// Deprecation signals (RFC 8594 "Sunset"); keep the old version alive for an announced window
Response.Headers["Deprecation"] = "true";
Response.Headers["Sunset"] = "Wed, 31 Dec 2026 23:59:59 GMT";
Response.Headers.Append("Link", "</api/v2/orders>; rel=\"successor-version\"");
```

**What is a breaking change?** Removing or renaming a field or endpoint; changing a type or meaning; making an optional input required; changing status codes or error formats; tightening validation. **Not breaking:** adding an optional request field or a new response field (clients must ignore unknown fields), adding an endpoint.

**Versioning policy to quote:** support N-1 versions, announce deprecation with `Deprecation`/`Sunset` headers and docs, track usage per version in telemetry, and retire only when traffic is near zero.

### Rate limiting (built-in, .NET 7+)

**Definition.** Limits how many requests a client can make in a time window to protect the API from abuse and overload. Returns **429** with `Retry-After`.

| Algorithm | Behaviour | Use for |
|---|---|---|
| **Fixed window** | N requests per window, counter resets at window boundary | Simple quotas (can burst at boundaries) |
| **Sliding window** | Window divided into segments, smoother | Fairer per-user limits |
| **Token bucket** | Tokens refill steadily; bursts allowed up to bucket size | APIs that allow short bursts |
| **Concurrency** | Max N requests *in flight* | Expensive endpoints (reports, exports) |

```csharp
builder.Services.AddRateLimiter(o =>
{
    o.RejectionStatusCode = StatusCodes.Status429TooManyRequests;
    o.OnRejected = async (ctx, ct) =>
    {
        if (ctx.Lease.TryGetMetadata(MetadataName.RetryAfter, out var retryAfter))
            ctx.HttpContext.Response.Headers.RetryAfter =
                ((int)retryAfter.TotalSeconds).ToString(CultureInfo.InvariantCulture);
        await ctx.HttpContext.Response.WriteAsJsonAsync(
            new ProblemDetails { Status = 429, Title = "Too many requests" }, ct);
    };

    o.AddFixedWindowLimiter("public", p =>
    { p.PermitLimit = 60; p.Window = TimeSpan.FromMinutes(1); p.QueueLimit = 0; });

    o.AddConcurrencyLimiter("reports", p => { p.PermitLimit = 4; p.QueueLimit = 10; });

    // Per authenticated user (falls back to IP)
    o.AddPolicy("per-user", ctx => RateLimitPartition.GetSlidingWindowLimiter(
        ctx.User.Identity?.Name ?? ctx.Connection.RemoteIpAddress?.ToString() ?? "anon",
        _ => new SlidingWindowRateLimiterOptions
        { PermitLimit = 120, Window = TimeSpan.FromMinutes(1), SegmentsPerWindow = 6 }));
});

app.UseRateLimiter();                                  // after UseRouting, usually after auth
app.MapGet("/api/products", ListProducts).RequireRateLimiting("public");
// Controllers: [EnableRateLimiting("per-user")] / [DisableRateLimiting]
```

:::warn Limits are per instance
The built-in limiter keeps counters **in memory of one process**. With three instances behind a load balancer the real limit is three times higher. For global limits use the gateway (Azure API Management, YARP, nginx, Cloudflare) or a Redis-backed limiter. Also decide the partition key carefully: behind a proxy `RemoteIpAddress` is the proxy unless forwarded headers are configured.
:::

### Error responses with ProblemDetails

**Definition.** `ProblemDetails` is the standard JSON error format (RFC 9457, which obsoletes RFC 7807), served as `application/problem+json`: `type`, `title`, `status`, `detail`, `instance` plus any extension members.

```json
{
  "type": "https://shop.example.com/errors/out-of-stock",
  "title": "Insufficient stock",
  "status": 409,
  "detail": "Product 17 has 2 units left; 5 requested.",
  "instance": "/api/orders",
  "traceId": "00-7d5f...-01",
  "productId": 17
}
```

```csharp
builder.Services.AddProblemDetails(o =>
    o.CustomizeProblemDetails = ctx =>
    {
        ctx.ProblemDetails.Extensions["traceId"] =
            Activity.Current?.Id ?? ctx.HttpContext.TraceIdentifier;
        ctx.ProblemDetails.Extensions["correlationId"] =
            ctx.HttpContext.Items["CorrelationId"];
    });

app.UseExceptionHandler();      // unhandled exceptions -> ProblemDetails 500
app.UseStatusCodePages();       // empty 404/401/403 etc. -> ProblemDetails (works for minimal APIs too)

// In an action
return Problem(statusCode: 409, title: "Insufficient stock",
               detail: "Product 17 has 2 units left", type: "https://shop.example.com/errors/out-of-stock");
// In a minimal API
return TypedResults.Problem(title: "Insufficient stock", statusCode: 409);
```

`[ApiController]` already returns `ValidationProblemDetails` (with an `errors` dictionary) for model validation failures and `ProblemDetails` for bare error status codes. Use one error format everywhere so clients write one error parser.

:::q Swashbuckle vs the built-in OpenAPI support?
From .NET 9 the Web API template uses `Microsoft.AspNetCore.OpenApi`, which generates the OpenAPI document (`AddOpenApi`, `MapOpenApi`) but ships no UI, and Swashbuckle was removed from the template. I still use Swashbuckle or NSwag when I want the bundled Swagger UI and filters. With the built-in generator I add Scalar or Swagger UI on top of the JSON.
:::

:::q How do you version a Web API?
With the Asp.Versioning library. I default to URL-segment versions like `/api/v2/orders` because they are visible and gateway-friendly, report supported and deprecated versions in response headers, mark old versions `Deprecated`, send `Sunset` headers, and retire a version only after telemetry shows near-zero usage. I only create a new version for breaking changes; additive changes stay in the same version.
:::
