## Authentication Fundamentals

### Authentication vs Authorization

**Definition.** *Authentication (authn)* answers "who are you?" — it proves identity. *Authorization (authz)* answers "what are you allowed to do?" — it decides access for an identity that is already known.

**Why it matters.** Mixing the two is the root of most access-control bugs. A system can authenticate perfectly (valid token) and still be broken because it never checks *whether this user may touch this order*. OWASP's #1 risk, Broken Access Control, is an authorization failure.

| | Authentication | Authorization |
|---|---|---|
| Question | Who are you? | What can you do? |
| Happens | First | After authentication |
| Input | Credentials, token, certificate | Identity + claims/roles + resource |
| ASP.NET Core piece | `UseAuthentication()`, schemes, handlers | `UseAuthorization()`, policies, requirements |
| Failure status | **401 Unauthorized** (really "unauthenticated") | **403 Forbidden** |
| Example | Login with email + password, JWT validated | Only `Admin` may cancel any order; a customer may cancel only their own |

:::example Airport analogy
Passport control checks your passport (authentication). The boarding gate checks your ticket says *this* flight and *business class lounge* (authorization). A valid passport does not get you into the lounge.
:::

:::tip What interviewers look for
Say "401 means *we don't know who you are*, 403 means *we know who you are and the answer is no*." Then mention that in ASP.NET Core the handler's `ChallengeAsync` produces the 401 and `ForbidAsync` produces the 403.
:::

### ASP.NET Core Authentication Architecture

**Definition.** Authentication in ASP.NET Core is built from four ideas: an **authentication scheme** (a name), an **authentication handler** (the code behind the name), the **authentication middleware** (calls the handler on every request), and the resulting **`ClaimsPrincipal`** stored in `HttpContext.User`.

**How it works.**

```text
HTTP request
   │
   ▼
UseAuthentication()  ──► default scheme's handler.AuthenticateAsync()
   │                         (reads cookie / Authorization header / etc.)
   │                         builds ClaimsPrincipal ──► HttpContext.User
   ▼
UseAuthorization()   ──► evaluates [Authorize] policy against HttpContext.User
   │       ├─ not authenticated ──► handler.ChallengeAsync()  ──► 401 / redirect to login
   │       └─ authenticated, policy fails ─► handler.ForbidAsync() ──► 403
   ▼
Endpoint runs
```

| Concept | What it is |
|---|---|
| **Scheme** | A named configuration: `"Bearer"`, `"Cookies"`, `"OpenIdConnect"`. Maps a name to a handler type + options. |
| **Handler** | Implements `IAuthenticationHandler`: `AuthenticateAsync` (who is it?), `ChallengeAsync` (ask for credentials → 401), `ForbidAsync` (→ 403), plus `SignInAsync`/`SignOutAsync` for cookie-like schemes. |
| **`AuthenticationBuilder`** | Returned by `AddAuthentication(...)`. You chain `.AddJwtBearer()`, `.AddCookie()`, `.AddOpenIdConnect()`, `.AddMicrosoftIdentityWebApi()` on it. |
| **`ClaimsPrincipal`** | The user. Contains one or more `ClaimsIdentity` objects (e.g. one from the cookie, one from a Windows login). |
| **`ClaimsIdentity`** | A set of `Claim`s plus an *authentication type* (non-null = authenticated), a name claim type and a role claim type. |
| **`Claim`** | A key/value statement about the user: `("email", "asha@shop.example")`. |

```csharp
// Registering two schemes: JWT for the API, cookie for an admin MVC area
builder.Services
    .AddAuthentication(options =>
    {
        options.DefaultScheme = JwtBearerDefaults.AuthenticationScheme; // "Bearer"
        options.DefaultChallengeScheme = JwtBearerDefaults.AuthenticationScheme;
    })
    .AddJwtBearer(/* ... */)
    .AddCookie("AdminCookie", o => o.LoginPath = "/admin/login");

// Use a specific scheme on a specific endpoint
[Authorize(AuthenticationSchemes = "AdminCookie")]
public class AdminDashboardController : Controller { /* ... */ }
```

```csharp
// Reading the principal in an endpoint
app.MapGet("/me", (ClaimsPrincipal user) => new
{
    IsAuthenticated = user.Identity?.IsAuthenticated,
    Name = user.Identity?.Name,                       // uses NameClaimType
    UserId = user.FindFirstValue(ClaimTypes.NameIdentifier),
    IsAdmin = user.IsInRole("Admin"),                 // uses RoleClaimType
    AllClaims = user.Claims.Select(c => new { c.Type, c.Value })
}).RequireAuthorization();
```

:::warn Middleware order
`UseAuthentication()` must come **before** `UseAuthorization()`, and both after `UseRouting()` and `UseCors()`, before the endpoints. In minimal-hosting apps (.NET 7+) the framework inserts them automatically when auth services are registered, but calling them explicitly is the only way to control the order relative to other middleware such as CORS — do it explicitly.
:::

:::q What is the difference between a ClaimsPrincipal, a ClaimsIdentity and a Claim?
A `Claim` is one statement about the user (type + value). A `ClaimsIdentity` is a bundle of claims from *one* authentication source, plus an authentication type and which claim types mean "name" and "role". A `ClaimsPrincipal` is the user as a whole and can hold several identities. `HttpContext.User` is a `ClaimsPrincipal`; `User.Identity.IsAuthenticated` is true only when the identity has a non-null authentication type.
:::

## JWT

### JWT Anatomy

**Definition.** A *JSON Web Token* (RFC 7519) is a compact, URL-safe string made of three base64url-encoded parts joined by dots: `header.payload.signature`. It carries *claims* and is **signed** so the receiver can verify it was not tampered with. It is **not encrypted** by default (that would be a JWE) — anyone holding it can read the payload.

**Why it matters.** A JWT is *self-contained*: the API validates it with only a key, with no session lookup. That makes stateless horizontal scaling easy, and it is the standard way to authenticate SPAs, mobile apps and service-to-service calls. The trade-off is that you cannot "delete" one before it expires without extra machinery.

A real token (line breaks added), signed with HS256:

```text
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.
eyJzdWIiOiI0MiIsIm5hbWUiOiJBc2hhIiwicm9sZSI6IkN1c3RvbWVyIiwiaXNzIjoic2hvcC1h
dXRoIiwiYXVkIjoic2hvcC1hcGkiLCJpYXQiOjE3NjAwMDAwMDAsImV4cCI6MTc2MDAwMDkwMCwi
anRpIjoiYjdlNWMxZDIifQ.
W_wrhXlqiVoCx3Ilfe3hu6gzECpTr9yTw4kcoUmxzpM
```

Decoded:

```json
// Header
{ "alg": "HS256", "typ": "JWT" }

// Payload (claims)
{
  "sub": "42", "name": "Asha", "role": "Customer",
  "iss": "shop-auth", "aud": "shop-api",
  "iat": 1760000000, "exp": 1760000900, "jti": "b7e5c1d2"
}

// Signature = HMAC-SHA256( base64url(header) + "." + base64url(payload), secret )
```

**Base64url** is base64 with `+` → `-`, `/` → `_` and the `=` padding removed, so the token is safe in URLs and headers. It is an *encoding*, not encryption — paste a token into jwt.io and read it.

| Registered claim | Meaning | Notes |
|---|---|---|
| `iss` | Issuer — who created the token | Validate it; reject tokens from unknown issuers |
| `sub` | Subject — who the token is about | Usually the user id; unique per issuer |
| `aud` | Audience — who the token is *for* | Your API must check it is in the list |
| `exp` | Expiration time (Unix seconds) | Always set; keep short for access tokens |
| `nbf` | Not before | Token invalid until this time |
| `iat` | Issued at | Useful for "revoke everything issued before X" |
| `jti` | JWT id — unique per token | Needed for a deny-list / replay protection |

:::warn Never put secrets in the payload
The payload is readable by the client, by any proxy that logs it, and by anyone who steals it. Put ids and roles in it; do not put passwords, card numbers or personal data you would not print on a postcard. Keep it small too — it travels on **every** request.
:::

:::q Is a JWT encrypted?
No. A normal signed JWT (a JWS) is only base64url-encoded and signed, so it guarantees integrity and authenticity, not confidentiality. Encrypted tokens exist (JWE) but are rare. So never store sensitive data in claims, and always send tokens over HTTPS.
:::

### Signing Algorithms: HS256 vs RS256

**Definition.** The `alg` header says how the signature is produced. **HS256** is HMAC-SHA256 with one *shared secret* (symmetric). **RS256** is RSA-SHA256 with a *private key to sign and a public key to verify* (asymmetric). **ES256** (ECDSA P-256) is asymmetric with much smaller keys and signatures.

| | HS256 (symmetric) | RS256 / ES256 (asymmetric) |
|---|---|---|
| Keys | One shared secret | Private key (issuer only) + public key (anyone) |
| Who can **create** tokens | Anyone who knows the secret — including every API that validates | Only the issuer |
| Who can **verify** | Same holders of the secret | Anyone with the public key (published as JWKS) |
| Speed | Very fast | Slower to sign; verify is fine |
| Key distribution | Hard: the secret must be shared with each API, so each is a leak risk | Easy: publish public key at `/.well-known/jwks.json` |
| Rotation | Painful (all parties change at once) | Smooth: `kid` header + two keys live during rollover |
| Use when | One app issues *and* validates its own tokens (monolith, small API) | Separate identity provider, multiple APIs, third parties, microservices |

```csharp
// RS256: issuer signs with the private key
using var rsa = RSA.Create(2048);                       // load from Key Vault in real life
var key = new RsaSecurityKey(rsa) { KeyId = "2026-10" }; // kid lets validators pick the key
var creds = new SigningCredentials(key, SecurityAlgorithms.RsaSha256);

// API side: no key in config at all — discover the public keys
builder.Services.AddAuthentication().AddJwtBearer(o =>
{
    o.Authority = "https://login.shop.example";   // fetches /.well-known/openid-configuration
    o.Audience  = "shop-api";                     // then the JWKS; caches and refreshes it
});
```

:::warn Algorithm attacks
`alg: none` (unsigned token accepted) and the *RS256 → HS256 confusion* attack (attacker signs with HS256 using your **public** key as the HMAC secret) are classic. Modern IdentityModel rejects `none`, and you should additionally pin `TokenValidationParameters.ValidAlgorithms` so the API only accepts the algorithm you issue.
:::

:::q HS256 or RS256 — which one would you pick?
If one service both issues and validates, HS256 with a long random key from Key Vault is simple and fast. As soon as a *different* service must validate tokens — microservices, a gateway, partners, Entra ID or Keycloak as issuer — use RS256 or ES256, because validators only need the public key and cannot forge tokens. In interviews I say: "HS256 shares the power to sign; RS256 shares only the power to verify."
:::

## Implementing JWT in ASP.NET Core

### Issuing a Token (login endpoint)

**Definition.** The login endpoint verifies credentials, then builds a `SecurityTokenDescriptor` (claims, issuer, audience, expiry, signing credentials) and asks a token handler to serialize and sign it.

**Why `JsonWebTokenHandler`.** `JwtSecurityTokenHandler` is the older class; `JsonWebTokenHandler` (`Microsoft.IdentityModel.JsonWebTokens`) is faster and allocates less, and from .NET 8 it is what the JwtBearer middleware uses by default. Prefer it for new code. Note it does **not** rewrite claim types on the way out, so use the short JWT names (`"role"`, `JwtRegisteredClaimNames.Sub`) when creating claims.

```csharp
// appsettings.json  (the SigningKey comes from user-secrets / Key Vault, never git)
// "Jwt": { "Issuer": "shop-auth", "Audience": "shop-api", "AccessTokenMinutes": 15 }

public sealed class JwtOptions
{
    public string Issuer { get; set; } = "";
    public string Audience { get; set; } = "";
    public string SigningKey { get; set; } = "";       // >= 32 random bytes
    public int AccessTokenMinutes { get; set; } = 15;
}
```

```csharp
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;

public sealed class TokenService(IOptions<JwtOptions> options, TimeProvider clock)
{
    private readonly JwtOptions _o = options.Value;
    private readonly JsonWebTokenHandler _handler = new();
    private readonly SigningCredentials _creds = new(
        new SymmetricSecurityKey(Encoding.UTF8.GetBytes(options.Value.SigningKey)),
        SecurityAlgorithms.HmacSha256);

    public (string Token, DateTime ExpiresUtc) CreateAccessToken(
        AppUser user, IEnumerable<string> roles)
    {
        var now = clock.GetUtcNow().UtcDateTime;
        var expires = now.AddMinutes(_o.AccessTokenMinutes);

        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, user.Id.ToString()),
            new(JwtRegisteredClaimNames.Email, user.Email),
            new(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString("N")),
            new("name", user.DisplayName),
        };
        claims.AddRange(roles.Select(r => new Claim("role", r))); // repeated => JSON array

        var descriptor = new SecurityTokenDescriptor
        {
            Subject = new ClaimsIdentity(claims),
            Issuer = _o.Issuer,
            Audience = _o.Audience,
            IssuedAt = now,
            NotBefore = now,
            Expires = expires,
            SigningCredentials = _creds
        };
        return (_handler.CreateToken(descriptor), expires);
    }
}
```

```csharp
// Program.cs — login endpoint (minimal API)
public record LoginRequest(string Email, string Password);
public record LoginResponse(string AccessToken, string RefreshToken, DateTime ExpiresUtc);

app.MapPost("/auth/login", async (
    LoginRequest req, AppDbContext db, IPasswordHasher<AppUser> hasher,
    TokenService tokens, RefreshTokenService refresh, HttpContext http) =>
{
    var user = await db.Users.Include(u => u.Roles)
        .SingleOrDefaultAsync(u => u.Email == req.Email);

    // Identical response for "unknown user" and "wrong password" — no user enumeration.
    if (user is null || user.IsLockedOut ||
        hasher.VerifyHashedPassword(user, user.PasswordHash, req.Password)
            == PasswordVerificationResult.Failed)
        return Results.Problem("Invalid credentials.", statusCode: 401);

    var (access, expires) = tokens.CreateAccessToken(user, user.Roles.Select(r => r.Name));
    var refreshToken = await refresh.IssueAsync(user.Id, http.Connection.RemoteIpAddress);

    return Results.Ok(new LoginResponse(access, refreshToken, expires));
}).AllowAnonymous().RequireRateLimiting("login");
```

The older equivalent, still common in existing code bases:

```csharp
var token = new JwtSecurityToken(
    issuer: _o.Issuer, audience: _o.Audience, claims: claims,
    notBefore: now, expires: expires, signingCredentials: _creds);
string jwt = new JwtSecurityTokenHandler().WriteToken(token);
// Gotcha: JwtSecurityTokenHandler maps ClaimTypes.Role -> "role" on output (OutboundClaimTypeMap)
```

:::example Real-world example
An e-commerce SPA posts email + password to `/auth/login`, receives a 15-minute access token and a refresh token, and sends `Authorization: Bearer <access>` on every call to the Orders and Catalog APIs. The Orders API never calls the login service — it just validates the signature and claims locally.
:::

### JwtBearer Configuration and TokenValidationParameters

**Definition.** `AddJwtBearer` registers a handler that reads `Authorization: Bearer <token>`, validates it using `TokenValidationParameters`, and on success builds the `ClaimsPrincipal`. **Each property is a check; every check you switch off is an attack you accept.**

```csharp
var jwt = builder.Configuration.GetSection("Jwt").Get<JwtOptions>()!;
builder.Services.Configure<JwtOptions>(builder.Configuration.GetSection("Jwt"));
builder.Services.AddSingleton(TimeProvider.System);
builder.Services.AddScoped<TokenService>();

builder.Services
    .AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(o =>
    {
        o.MapInboundClaims = false;           // keep "sub"/"role", skip legacy URI mapping
        o.RequireHttpsMetadata = true;        // only matters when using Authority

        o.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidIssuer = jwt.Issuer,
            ValidateAudience = true,
            ValidAudience = jwt.Audience,
            ValidateLifetime = true,
            RequireExpirationTime = true,
            ValidateIssuerSigningKey = true,
            IssuerSigningKey = new SymmetricSecurityKey(
                Encoding.UTF8.GetBytes(jwt.SigningKey)),
            ValidAlgorithms = [SecurityAlgorithms.HmacSha256],
            ClockSkew = TimeSpan.FromSeconds(30),
            NameClaimType = "name",
            RoleClaimType = "role"
        };

        o.Events = new JwtBearerEvents
        {
            // SignalR / WebSockets cannot set headers: read ?access_token= for hub paths only
            OnMessageReceived = ctx =>
            {
                var t = ctx.Request.Query["access_token"];
                var isHub = ctx.HttpContext.Request.Path.StartsWithSegments("/hubs");
                if (!string.IsNullOrEmpty(t) && isHub) ctx.Token = t;
                return Task.CompletedTask;
            },
            // Extra check after the signature passes — e.g. is the user still active?
            OnTokenValidated = async ctx =>
            {
                var db = ctx.HttpContext.RequestServices.GetRequiredService<AppDbContext>();
                var id = int.Parse(ctx.Principal!.FindFirstValue("sub")!);
                if (!await db.Users.AnyAsync(u => u.Id == id && u.IsActive))
                    ctx.Fail("User disabled.");
            }
        };
    });

builder.Services.AddAuthorization();
// ...
app.UseAuthentication();
app.UseAuthorization();
```

| Property | What it checks | Default | If you get it wrong |
|---|---|---|---|
| `ValidateIssuer` / `ValidIssuer(s)` | `iss` equals the expected issuer | `true` | Tokens from any other IdP (or an attacker's server with the same key) are accepted |
| `ValidateAudience` / `ValidAudience(s)` | `aud` contains this API | `true` | A token minted for the *Payments* API works on *Orders* ("confused deputy") |
| `ValidateLifetime` | `exp` and `nbf` against the clock (± `ClockSkew`) | `true` | Expired tokens live forever |
| `ValidateIssuerSigningKey` | The signing *key itself* is trusted/valid (e.g. certificate not expired). Signature verification itself always happens | `false` | Keep `true`; essential when keys come from a resolver |
| `IssuerSigningKey(s)` / `IssuerSigningKeyResolver` | The key(s) used to verify the signature | none (or from `Authority`) | `IDX10500: Signature validation failed. No security keys were provided` |
| `ClockSkew` | Tolerance for clock drift between servers | **5 minutes** | A 15-min token is really valid for 20. Lower it to 0-60 s if clocks are synced |
| `RequireSignedTokens` | A signature must exist | `true` | Never disable — it allows `alg: none` |
| `ValidAlgorithms` | Whitelist of `alg` values | any | Pin it to defeat algorithm-confusion |
| `RequireExpirationTime` | `exp` must exist | `true` | Tokens without expiry would be immortal |
| `NameClaimType` / `RoleClaimType` | Which claim feeds `Identity.Name` / `IsInRole()` | `ClaimTypes.Name` / `ClaimTypes.Role` | `[Authorize(Roles="Admin")]` silently fails when your token says `"role"` and mapping is off |
| `ValidTypes` | Allowed `typ` header values | any | Use to stop token-type confusion (access vs id token) |

:::warn Claim type mapping — the classic "my roles don't work" bug
By default the handler *maps* short JWT names to old WS-* URIs (`sub` → `http://schemas.xmlsoap.org/.../nameidentifier`, `role` → `.../claims/role`). Either leave mapping on and read `ClaimTypes.*`, or (recommended) set `MapInboundClaims = false` **and** set `NameClaimType`/`RoleClaimType` explicitly. Mixing the two is why `User.IsInRole("Admin")` returns false even though the token has `"role": "Admin"`.
:::

:::tip Never skip a validation flag "to make it work"
`ValidateAudience = false` and `ValidateIssuer = false` appear in countless tutorials. In an interview, call them out: "I would never disable these in production; I fix the config so the values match."
:::

:::scenario API returns 401 for a valid-looking token
The client sends `Authorization: Bearer ...` and gets 401. Read the `WWW-Authenticate` response header — it names the failure.

- `error="invalid_token", error_description="The token expired at ..."` → exp passed (or client clock wrong). Check refresh logic.
- `The audience '...' is invalid` (IDX10214) → token's `aud` differs from `ValidAudience`. Entra ID v2 tokens use `api://<client-id>` — configure to match.
- `The issuer '...' is invalid` (IDX10205) → `iss` mismatch; v1 vs v2 Entra endpoints and trailing slashes are typical.
- `Signature validation failed` / `IDX10503` → API has a different key than the issuer (secret not synced between environments, or the key rotated).
- No `WWW-Authenticate` error at all → the header never arrived or the scheme prefix is not exactly `Bearer `. Also check middleware order and that `app.UseAuthentication()` runs.

Turn on `Microsoft.IdentityModel` logging (`IdentityModelEventSource.ShowPII = true` in dev only) to see the precise reason.
:::

:::q What is ClockSkew and why would you reduce it?
Servers' clocks never match perfectly, so IdentityModel allows a tolerance when checking `exp` and `nbf`. The default is 5 minutes, which silently extends every token's life — a 15-minute access token works for 20. If your servers use NTP I set it to 30-60 seconds, so token lifetime is what I designed.
:::

:::q Stateless JWT validation vs session lookup — what is the trade-off?
JWT validation needs only the key, so APIs scale horizontally and have no session store. The price: you can't revoke a token before `exp` unless you add state (deny-list by `jti`, token version in DB, short lifetimes plus refresh tokens). Session cookies are the opposite: instant revocation, but a shared session store.
:::
