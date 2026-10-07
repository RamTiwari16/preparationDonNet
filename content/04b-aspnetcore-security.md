## Token Lifecycle

### Access Token vs Refresh Token

**Definition.** An *access token* is a short-lived credential sent to the API on every call (usually a JWT). A *refresh token* is a long-lived credential used **only** against the auth server to obtain a new access token without asking the user to log in again.

**Why it matters.** A stateless JWT cannot be revoked, so you keep its lifetime short (5-15 minutes) to limit the damage of theft. A short lifetime alone would force users to log in every 15 minutes — the refresh token fixes the UX, and because it is *stateful* (stored in your DB) you regain revocation.

| | Access token | Refresh token |
|---|---|---|
| Lifetime | 5-15 min | Days to weeks |
| Format | JWT (self-contained) | **Opaque random string** (32 random bytes), not a JWT |
| Sent to | Every API request | Only `/auth/refresh` |
| Stored server-side | No | **Yes — as a hash**, in the DB |
| Revocable | Not before `exp` | Yes, instantly |
| If stolen | Usable until `exp` | Usable until revoked or until reuse is detected |

**Production design rules.**
1. **Rotate on every use**: each refresh returns a *new* refresh token and invalidates the old one.
2. **Store only a hash** (SHA-256 is fine — the token is 256 random bits, so a slow hash adds nothing). A DB leak then yields nothing usable.
3. **Token families + reuse detection**: all tokens descended from one login share a `FamilyId`. If an already-used token is presented again, someone copied it — revoke the whole family and force re-login.
4. **Sliding + absolute expiry**: sliding (e.g. 14 days since last use) keeps active users logged in; an absolute cap (e.g. 90 days) forces periodic re-authentication.
5. **Re-read the user on refresh** (active? roles? lockout?) so changes propagate within one access-token lifetime.
6. Bind metadata (IP, user-agent, device name) for an "active sessions" screen and anomaly detection.

```csharp
public class RefreshToken
{
    public long Id { get; set; }
    public int UserId { get; set; }
    public string TokenHash { get; set; } = "";     // index, unique
    public Guid FamilyId { get; set; }              // one login = one family
    public DateTime CreatedUtc { get; set; }
    public DateTime ExpiresUtc { get; set; }        // sliding window
    public DateTime AbsoluteExpiresUtc { get; set; } // hard cap, copied down the family
    public DateTime? UsedUtc { get; set; }          // set when rotated
    public DateTime? RevokedUtc { get; set; }
    public string? ReplacedByHash { get; set; }
    public string? CreatedByIp { get; set; }
}
```

```csharp
public sealed class RefreshTokenService(
    AppDbContext db, TokenService tokens, TimeProvider clock)
{
    private static readonly TimeSpan Sliding = TimeSpan.FromDays(14);
    private static readonly TimeSpan Absolute = TimeSpan.FromDays(90);

    private static string NewRawToken() =>
        WebEncoders.Base64UrlEncode(RandomNumberGenerator.GetBytes(32));
    private static string Hash(string raw) =>
        Convert.ToBase64String(SHA256.HashData(Encoding.UTF8.GetBytes(raw)));

    public async Task<string> IssueAsync(int userId, IPAddress? ip)
    {
        var now = clock.GetUtcNow().UtcDateTime;
        var raw = NewRawToken();
        db.RefreshTokens.Add(new RefreshToken
        {
            UserId = userId, TokenHash = Hash(raw), FamilyId = Guid.NewGuid(),
            CreatedUtc = now, ExpiresUtc = now + Sliding,
            AbsoluteExpiresUtc = now + Absolute, CreatedByIp = ip?.ToString()
        });
        await db.SaveChangesAsync();
        return raw;                       // the raw value leaves the server exactly once
    }

    public async Task<(string Access, string Refresh)?> RotateAsync(string raw, IPAddress? ip)
    {
        var now = clock.GetUtcNow().UtcDateTime;
        var hash = Hash(raw);
        var stored = await db.RefreshTokens.SingleOrDefaultAsync(t => t.TokenHash == hash);
        if (stored is null) return null;                          // unknown token

        if (stored.UsedUtc is not null || stored.RevokedUtc is not null)
        {   // REUSE DETECTED: a rotated token came back. Burn the whole family.
            await RevokeFamilyAsync(stored.FamilyId, now);
            return null;
        }
        if (stored.ExpiresUtc <= now || stored.AbsoluteExpiresUtc <= now) return null;

        var user = await db.Users.Include(u => u.Roles)
            .SingleAsync(u => u.Id == stored.UserId);
        if (!user.IsActive) return null;                          // disabled => refresh dies

        var newRaw = NewRawToken();
        var newHash = Hash(newRaw);

        // Atomic claim: only ONE concurrent request can flip UsedUtc from NULL.
        var claimed = await db.RefreshTokens
            .Where(t => t.Id == stored.Id && t.UsedUtc == null && t.RevokedUtc == null)
            .ExecuteUpdateAsync(s => s.SetProperty(t => t.UsedUtc, now)
                                      .SetProperty(t => t.ReplacedByHash, newHash));
        if (claimed == 0) return null;                            // lost the race

        var next = now + Sliding;
        db.RefreshTokens.Add(new RefreshToken
        {
            UserId = user.Id, TokenHash = newHash, FamilyId = stored.FamilyId,
            CreatedUtc = now,
            ExpiresUtc = next < stored.AbsoluteExpiresUtc ? next : stored.AbsoluteExpiresUtc,
            AbsoluteExpiresUtc = stored.AbsoluteExpiresUtc, CreatedByIp = ip?.ToString()
        });
        await db.SaveChangesAsync();

        var (access, _) = tokens.CreateAccessToken(user, user.Roles.Select(r => r.Name));
        return (access, newRaw);
    }

    public Task RevokeFamilyAsync(Guid familyId, DateTime now) =>
        db.RefreshTokens.Where(t => t.FamilyId == familyId && t.RevokedUtc == null)
          .ExecuteUpdateAsync(s => s.SetProperty(t => t.RevokedUtc, now));

    public async Task RevokeByRawAsync(string raw)
    {
        var hash = Hash(raw);
        var familyId = await db.RefreshTokens.Where(t => t.TokenHash == hash)
            .Select(t => (Guid?)t.FamilyId).SingleOrDefaultAsync();
        if (familyId is not null)
            await RevokeFamilyAsync(familyId.Value, clock.GetUtcNow().UtcDateTime);
    }
}
```

```csharp
app.MapPost("/auth/refresh", async (HttpContext http, RefreshTokenService svc) =>
{
    var raw = http.Request.Cookies["rt"];
    if (string.IsNullOrEmpty(raw)) return Results.Unauthorized();

    var result = await svc.RotateAsync(raw, http.Connection.RemoteIpAddress);
    if (result is null)
    {
        http.Response.Cookies.Delete("rt", new CookieOptions { Path = "/auth" });
        return Results.Unauthorized();
    }

    http.Response.Cookies.Append("rt", result.Value.Refresh, new CookieOptions
    {
        HttpOnly = true, Secure = true,
        SameSite = SameSiteMode.Strict,     // never sent cross-site
        Path = "/auth",                     // only sent to /auth/* endpoints
        Expires = DateTimeOffset.UtcNow.AddDays(14)
    });
    return Results.Ok(new { accessToken = result.Value.Access });
}).AllowAnonymous();
```

| Expiry style | Behaviour | Pros | Cons |
|---|---|---|---|
| **Sliding** | Each refresh extends the deadline | Active users never see a login screen | A stolen-and-kept-alive token could live forever |
| **Absolute** | Fixed deadline from login | Predictable, bounds the damage | Everyone re-logs in periodically |
| **Both** (recommended) | Sliding window, capped by absolute | Good UX and bounded risk | Slightly more fields to track |

:::warn Two tabs refresh at the same time
Concurrent refreshes with the same token look like reuse. The atomic `ExecuteUpdate` above means exactly one wins. Real systems add a short grace window (10-30 s) before treating a second use as theft, or the client coordinates a single in-flight refresh (a shared promise in the SPA). Otherwise legitimate users get logged out randomly.
:::

:::q Why must refresh tokens be rotated and stored hashed?
Rotation makes a stolen refresh token useful only once; if both thief and victim use it, the second use trips reuse detection and the whole family is revoked. Hashing means a database leak or a SQL-injection read does not give the attacker working tokens — same reasoning as password hashing, except SHA-256 is enough because the token is random, not human-chosen.
:::

### Where to Store Tokens in an SPA

**Definition.** The browser gives you three places — JavaScript memory, Web Storage (`localStorage`/`sessionStorage`), and cookies — each trading XSS risk against CSRF risk.

| | JS memory (variable) | `localStorage` / `sessionStorage` | `HttpOnly; Secure; SameSite` cookie |
|---|---|---|---|
| Readable by injected JS (XSS) | Only while the page lives; hard to grab | **Yes — trivially exfiltrated** | **No** (but XSS can still *use* the session) |
| CSRF | Immune (header set by your code) | Immune | **Exposed** → SameSite + antiforgery |
| Survives page refresh | No → silent refresh needed | Yes | Yes |
| Sent automatically | No | No | Yes (this is what causes CSRF) |
| Verdict | Good for access token | Avoid for anything sensitive | Good for refresh token / session |

**Recommended pragmatic setup.** Access token in memory; refresh token in an `HttpOnly`, `Secure`, `SameSite=Strict` cookie scoped to `/auth`. On page load the SPA calls `/auth/refresh` to get a fresh access token. XSS cannot read the refresh token; CSRF cannot do harm because `/auth/refresh` only returns a token that the attacker's page cannot read (CORS blocks it) — and the cookie is `SameSite=Strict`.

**Highest security: the BFF pattern.** A *Backend-For-Frontend* is a small server-side app that runs the OIDC code+PKCE flow itself, keeps access and refresh tokens **server-side**, and gives the browser only a session cookie. The SPA never sees a token.

```text
Browser SPA ──(session cookie)──► BFF (ASP.NET Core) ──(Bearer access token)──► Orders API
                                    │  tokens stored server-side
                                    └──(code + PKCE, refresh)──► Identity provider
```

```csharp
// BFF: attach the user's access token while proxying with YARP
builder.Services.AddReverseProxy()
    .LoadFromConfig(builder.Configuration.GetSection("ReverseProxy"))
    .AddTransforms(ctx => ctx.AddRequestTransform(async t =>
    {
        var token = await t.HttpContext.GetTokenAsync("access_token"); // SaveTokens = true
        t.ProposedRequest.Headers.Authorization =
            new AuthenticationHeaderValue("Bearer", token);
    }));
app.MapReverseProxy().RequireAuthorization();
```

:::tip What to say in the interview
"localStorage is the easiest and the worst: any XSS, including one from a compromised npm package, can steal the token. I keep the access token in memory and the refresh token in an HttpOnly SameSite cookie. For high-risk apps I use a BFF so no token reaches the browser at all. This is also what the IETF's *OAuth for Browser-Based Apps* guidance recommends."
:::

### Logout and Revocation

JWT access tokens are stateless, so "logout" has two halves: **kill the refresh side** (revoke the family in the DB, delete the cookie) and **accept that the access token lives until `exp`** — or add state to cut it short:

| Technique | How | Cost |
|---|---|---|
| Short access lifetime | 5-10 min | Free; main defence |
| Deny-list by `jti` | On logout store `jti` in Redis until its `exp`; check in `OnTokenValidated` | One cache hit per request |
| Token version / security stamp | `ver` claim compared with `User.TokenVersion` in DB (cached) | A cheap cached read; bump version to kill all tokens |
| Reference (opaque) tokens + introspection | API calls the IdP to validate | Latency, but instant revocation |

```csharp
// Logout: revoke the refresh family; optionally deny-list the current access token
app.MapPost("/auth/logout", async (HttpContext http, ClaimsPrincipal user,
    RefreshTokenService svc, IDistributedCache cache) =>
{
    if (http.Request.Cookies["rt"] is { } raw)
        await svc.RevokeByRawAsync(raw);               // looks up hash, revokes family
    http.Response.Cookies.Delete("rt", new() { Path = "/auth" });

    var jti = user.FindFirstValue("jti");
    var exp = long.Parse(user.FindFirstValue("exp")!);
    var ttl = DateTimeOffset.FromUnixTimeSeconds(exp) - DateTimeOffset.UtcNow;
    if (jti is not null && ttl > TimeSpan.Zero)
        await cache.SetStringAsync($"deny:{jti}", "1",
            new DistributedCacheEntryOptions { AbsoluteExpirationRelativeToNow = ttl });
    return Results.NoContent();
}).RequireAuthorization();

// in JwtBearerEvents.OnTokenValidated:
var denied = await cache.GetStringAsync($"deny:{ctx.Principal!.FindFirstValue("jti")}");
if (denied is not null) ctx.Fail("Token revoked.");
```

## Authorization

### Claims, Roles and Policies

**Definition.** A *claim* is a fact about the user (`email`, `department`, `permission=orders.refund`). A *role* is just a claim of type "role" — a coarse grouping (`Admin`, `Support`). A *policy* is a named set of **requirements** evaluated against the user (and optionally a resource): "must be authenticated, must have claim X, must satisfy my custom rule".

**Why policies beat roles.** Roles hard-code *who* in controllers (`[Authorize(Roles="Admin,Manager,Support")]`) and explode in number. Policies name the *capability* (`"CanRefundOrders"`), and you change who has it in one place.

| | Role-based | Claim-based | Policy-based |
|---|---|---|---|
| Declaration | `[Authorize(Roles = "Admin")]` | `policy.RequireClaim("dept", "sales")` | `[Authorize(Policy = "CanRefund")]` |
| Granularity | Coarse | Medium | Any logic (time, tenant, resource, DB lookup) |
| Testable / centralised | Meh | Yes | Yes — handlers are plain classes |

```csharp
builder.Services.AddAuthorizationBuilder()                 // .NET 7+/8 fluent API
    .AddPolicy("AdminOnly", p => p.RequireRole("Admin"))
    .AddPolicy("SalesStaff", p => p.RequireClaim("department", "sales", "marketing"))
    .AddPolicy("SeniorSupport", p => p
        .RequireAuthenticatedUser()
        .RequireRole("Support")
        .AddRequirements(new MinimumTenureRequirement(Years: 2)))
    .AddPolicy("ApiScope", p => p.RequireClaim("scope", "orders.write"));

[Authorize(Roles = "Admin,Manager")]       // OR: Admin OR Manager
[Authorize(Roles = "Verified")]            // stacked attributes are AND
public class ReportsController : ControllerBase { }
```

#### Custom requirement and handler

```csharp
public sealed record MinimumTenureRequirement(int Years) : IAuthorizationRequirement;

public sealed class MinimumTenureHandler(TimeProvider clock)
    : AuthorizationHandler<MinimumTenureRequirement>
{
    protected override Task HandleRequirementAsync(
        AuthorizationHandlerContext context, MinimumTenureRequirement requirement)
    {
        var hired = context.User.FindFirstValue("hire_date");
        if (DateOnly.TryParse(hired, CultureInfo.InvariantCulture, out var date))
        {
            var today = DateOnly.FromDateTime(clock.GetUtcNow().UtcDateTime);
            if (date.AddYears(requirement.Years) <= today)
                context.Succeed(requirement);
        }
        return Task.CompletedTask;   // not calling Succeed = "not satisfied" (soft fail)
    }
}

builder.Services.AddSingleton<IAuthorizationHandler, MinimumTenureHandler>();
```

**Evaluation rules to remember:** all requirements in a policy must pass (AND); a requirement passes if *any* of its handlers calls `Succeed` and none calls `Fail` (OR across handlers); `context.Fail()` is a hard veto.

### Resource-Based Authorization

**Definition.** Attributes run *before* your code loads data, so they cannot answer "may this user see **this** order?". Resource-based authorization calls `IAuthorizationService` **inside** the handler, after you load the resource.

**Why it matters.** This is the fix for IDOR / BOLA (OWASP API #1): changing `/orders/17` to `/orders/18` and seeing someone else's order. Role checks cannot catch it.

```csharp
public sealed class OrderOwnerRequirement : IAuthorizationRequirement;

public sealed class OrderOwnerHandler
    : AuthorizationHandler<OrderOwnerRequirement, Order>
{
    protected override Task HandleRequirementAsync(AuthorizationHandlerContext ctx,
        OrderOwnerRequirement req, Order order)
    {
        var userId = ctx.User.FindFirstValue("sub");
        if (order.CustomerId.ToString() == userId || ctx.User.IsInRole("Support"))
            ctx.Succeed(req);
        return Task.CompletedTask;
    }
}
builder.Services.AddSingleton<IAuthorizationHandler, OrderOwnerHandler>();

app.MapGet("/orders/{id:int}", async (int id, AppDbContext db,
    ClaimsPrincipal user, IAuthorizationService authz) =>
{
    var order = await db.Orders.Include(o => o.Items).SingleOrDefaultAsync(o => o.Id == id);
    if (order is null) return Results.NotFound();

    var result = await authz.AuthorizeAsync(user, order, new OrderOwnerRequirement());
    // 404 instead of 403 hides that the order exists at all
    return result.Succeeded ? Results.Ok(order.ToDto()) : Results.NotFound();
}).RequireAuthorization();
```

An even better habit: put the ownership filter into the query itself (`Where(o => o.Id == id && o.CustomerId == userId)`) so other tenants' rows are never loaded.

### [Authorize], [AllowAnonymous] and the Fallback Policy

| Piece | Meaning |
|---|---|
| `[Authorize]` | Requires the **default policy** (authenticated user). Add `Roles`, `Policy` or `AuthenticationSchemes` to tighten. |
| `[AllowAnonymous]` | Opts an action/endpoint out. It **overrides** `[Authorize]` and the fallback policy. |
| `RequireAuthorization()` / `AllowAnonymous()` | Minimal-API equivalents; apply to a `MapGroup("/api")` for a whole area. |
| **Default policy** | Used by bare `[Authorize]`. Default: `RequireAuthenticatedUser()`. |
| **Fallback policy** | Applied to endpoints with **no** authorization metadata at all. Default: none (anonymous). |

```csharp
builder.Services.AddAuthorization(o =>
{
    // Secure by default: everything needs a logged-in user unless it says [AllowAnonymous]
    o.FallbackPolicy = new AuthorizationPolicyBuilder()
        .RequireAuthenticatedUser().Build();
});

app.MapGet("/health", () => "ok").AllowAnonymous();
app.MapGroup("/api/admin").RequireAuthorization("AdminOnly");
```

:::warn Forgetting [Authorize] is the real risk
With no fallback policy, a new endpoint is public until someone remembers to protect it. Set a fallback policy and make `[AllowAnonymous]` the explicit, reviewed exception. Also: `[AllowAnonymous]` on an action beats `[Authorize]` on its controller — a surprise in code review.
:::

### Cookie Authentication vs JWT

| | Cookie (session) auth | JWT bearer |
|---|---|---|
| Credential storage | Browser cookie, set by the server | Client chooses (memory, header) |
| Sent how | Automatically by the browser | Manually in `Authorization` header |
| State | Ticket (encrypted by Data Protection) or server session | Self-contained, stateless |
| CSRF | **Vulnerable** → SameSite + antiforgery | Not vulnerable (no automatic sending) |
| XSS token theft | Safe with `HttpOnly` | At risk if in `localStorage` |
| Revocation | Easy (server-side) | Hard (needs deny-list/short expiry) |
| Best for | Server-rendered apps, BFF, same-site SPA | Mobile apps, third-party/API clients, microservices |
| Cross-domain APIs | Painful (CORS + third-party cookie limits) | Natural |

```csharp
builder.Services.AddAuthentication(CookieAuthenticationDefaults.AuthenticationScheme)
    .AddCookie(o =>
    {
        o.Cookie.Name = "__Host-shop";           // __Host- prefix: Secure, Path=/, no Domain
        o.Cookie.HttpOnly = true;
        o.Cookie.SecurePolicy = CookieSecurePolicy.Always;
        o.Cookie.SameSite = SameSiteMode.Lax;
        o.ExpireTimeSpan = TimeSpan.FromHours(8);
        o.SlidingExpiration = true;
        // For API/SPA calls, answer 401/403 instead of redirecting to a login page
        o.Events.OnRedirectToLogin = c =>
        { c.Response.StatusCode = 401; return Task.CompletedTask; };
        o.Events.OnRedirectToAccessDenied = c =>
        { c.Response.StatusCode = 403; return Task.CompletedTask; };
    });
```

:::q Role-based vs policy-based authorization — when do you use which?
Roles for coarse, stable groupings (Admin, Customer). Policies as soon as the rule involves a claim other than role, several conditions, a resource, or business logic, or when I want one named capability instead of repeating a role list across controllers. Policies can contain role checks, so they are a superset. For "is this *your* order" I use resource-based authorization.
:::

:::q What is the difference between a policy and a requirement?
A requirement is a single condition (`MinimumTenureRequirement`) — data only. A handler contains the logic that decides whether a requirement is met. A policy is a named collection of requirements; the user must satisfy all of them.
:::

## Token Security Scenarios

:::scenario JWT stolen - what now?
**Contain, then cure.**
1. The attacker holds a valid access token until `exp`. With a 15-minute lifetime the window is small — that is why lifetimes are short.
2. Revoke the **refresh token family** for that user/device so they cannot mint new ones; bump the user's `TokenVersion` / security stamp so existing access tokens fail `OnTokenValidated`; optionally deny-list the `jti`.
3. Force password reset / re-login if the cause was credential theft; check audit logs for what the token did.
4. If the **signing key** leaked (not just one token): rotate the key (new `kid`), keep the old public key only long enough, and invalidate everything issued before the rotation. With HS256, every service that knew the secret is a suspect.
5. Find the *root cause*: XSS (token in localStorage), a leaked log line, a missing HTTPS redirect. Move to HttpOnly cookies/BFF, scrub tokens from logs, add reuse detection.

Say: "Stateless tokens trade revocability for scalability, so I compensate with short lifetimes plus a stateful refresh layer."
:::

:::scenario User role changed but the token is still valid
Roles are baked into the JWT at issue time, so an admin who demotes a user sees no effect until the token expires. Options, cheapest first:
- **Accept the lag**: ≤ 15 minutes with short tokens; roles are re-read from the DB when the refresh token rotates (as in `RotateAsync`).
- **Version claim**: put `ver` in the token; compare with `User.TokenVersion` (cached for 30-60 s) in `OnTokenValidated`; bump on role change.
- **Do not put volatile permissions in the token**: keep only identity and look up permissions per request (cached) via a policy handler or `IClaimsTransformation`.
- For sensitive actions (refunds, deletes) always do a **fresh authorization check** against the DB regardless of token claims.
:::

:::scenario How do you log a user out with JWT?
Logging out on the client (deleting the token) only removes *your* copy — a copy elsewhere keeps working. A real logout: (1) revoke the refresh token family server-side and delete the refresh cookie; (2) let the access token die within its short lifetime, or deny-list its `jti` / bump the token version for immediate effect; (3) for SSO, also hit the IdP's `end_session_endpoint` (OIDC RP-initiated logout) so the IdP session ends. Mention that "logout everywhere" = revoke all families for the user.
:::
