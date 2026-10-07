## OAuth 2.0 and OpenID Connect

### OAuth 2.0

**Definition.** OAuth 2.0 (RFC 6749) is a **delegated authorization** framework: it lets an application obtain a limited *access token* to call an API on a user's behalf — *without ever seeing the user's password*. It is not an authentication protocol.

**Why it matters.** "Sign in with Google", "this app wants to read your calendar", and every service-to-service call in Azure all use it. Interviewers use it to test whether you can separate *who the user is* (OIDC) from *what the app may do* (OAuth).

**The four roles.**

| Role | Example |
|---|---|
| **Resource Owner** | The customer (the user who owns the data) |
| **Client** | The Shop web app / SPA / mobile app asking for access |
| **Authorization Server** | Entra ID, Keycloak, Duende IdentityServer — issues tokens |
| **Resource Server** | The Orders API — accepts and validates access tokens |

**Grant types (flows).**

| Grant | Use for | Status |
|---|---|---|
| **Authorization Code + PKCE** | Web apps, SPAs, mobile/desktop apps — anything with a user | **The default today** (OAuth 2.1 makes PKCE mandatory) |
| **Client Credentials** | Machine-to-machine: a background worker calling an API as itself, no user | Current |
| **Refresh Token** | Get a new access token silently | Current |
| **Device Code** | TVs, CLIs, IoT with no browser | Current |
| Implicit | Old SPAs: tokens returned in the URL fragment | **Deprecated** — tokens leak via history/referrer; use code + PKCE |
| Resource Owner Password (ROPC) | Client collects the username/password itself | **Deprecated** — defeats the point of OAuth; breaks MFA/SSO |

#### Authorization Code with PKCE

PKCE (*Proof Key for Code Exchange*, pronounced "pixy") stops an attacker who steals the authorization `code` (from a redirect, a malicious app registered on the same scheme) from exchanging it, because only the real client knows the secret `code_verifier`.

```text
1. Client creates   code_verifier  = random 43-128 chars
                    code_challenge = BASE64URL( SHA256(code_verifier) )
2. Browser ──► GET /authorize?response_type=code&client_id=shop-web
                  &redirect_uri=https://shop.example/signin-oidc
                  &scope=openid profile offline_access orders.read
                  &state=<csrf random>&nonce=<random>
                  &code_challenge=<challenge>&code_challenge_method=S256
3. User authenticates (+ MFA) and consents at the Authorization Server
4. AS ──► 302 https://shop.example/signin-oidc?code=SplxlOBe&state=<same>
5. Client ──► POST /token  grant_type=authorization_code & code=SplxlOBe
                  & redirect_uri=... & client_id=... & code_verifier=<original>
6. AS checks SHA256(code_verifier) == stored challenge
   ──► { access_token, id_token, refresh_token, expires_in }
```

- `state` protects against CSRF on the callback; `nonce` binds the `id_token` to this login (replay protection).
- The code travels through the browser (front channel); tokens travel directly client ⇄ AS (back channel).

#### Client Credentials (machine to machine)

```csharp
// Shipping worker calls the Orders API as itself. No user is involved.
using var http = new HttpClient();
var response = await http.PostAsync("https://login.shop.example/connect/token",
    new FormUrlEncodedContent(new Dictionary<string, string>
    {
        ["grant_type"]    = "client_credentials",
        ["client_id"]     = "shipping-worker",
        ["client_secret"] = config["Shipping:ClientSecret"]!, // Key Vault, not appsettings
        ["scope"]         = "orders.read"
    }));
var token = (await response.Content.ReadFromJsonAsync<TokenResponse>())!;
// Cache token.AccessToken until ~1 minute before expires_in; don't request per call.
// In production prefer Duende.AccessTokenManagement or a certificate/managed identity.
```

**Scopes** are the permissions the client asks for (`orders.read`, `orders.write`). The user (or admin) consents; the API checks the `scope` claim (`scp` in Entra). A scope limits the *client*, it does not grant the *user* anything they could not already do.

:::warn OAuth is not login
Treating "I got an access token" as proof of identity is the classic mistake (token substitution attacks). An access token is for the API; it may be opaque and says nothing reliable to the client about who the user is. To log a user in, use **OpenID Connect** and validate the `id_token`.
:::

:::q Why was the implicit flow deprecated and what replaces it?
The implicit flow returned the access token directly in the redirect URL fragment, exposing it to browser history, referrer headers, extensions and injected scripts, with no way to authenticate the client. Authorization Code + PKCE replaces it: only a short-lived code goes through the browser, and the token is fetched over a back channel, protected by the PKCE verifier. Same reasoning explains why the password grant is also dead — the client would see the user's password.
:::

### OpenID Connect (OIDC)

**Definition.** OIDC is a thin **identity layer on top of OAuth 2.0**. By requesting the `openid` scope the client gets an **ID token** (a signed JWT that says *who authenticated, when and how*), and may call the **UserInfo endpoint** for profile data.

| | ID token | Access token |
|---|---|---|
| Purpose | Proof of authentication for the **client** | Permission to call an **API** |
| Audience (`aud`) | The client (`client_id`) | The API / resource server |
| Format | Always a JWT | JWT or opaque |
| Who validates it | The client app | The API |
| Send to the API? | **Never** | Yes, as `Authorization: Bearer` |
| Typical claims | `sub`, `iss`, `aud`, `nonce`, `auth_time`, `amr`, `name`, `email` | `sub`, `scope`/`scp`, `client_id`, `roles` |

**Standard scopes:** `openid` (required), `profile` (name, picture…), `email`, `address`, `phone`, `offline_access` (issue a refresh token).

**Discovery:** everything is published at `{authority}/.well-known/openid-configuration` — endpoints, supported scopes, and the `jwks_uri` with signing keys. That is why `Authority = "..."` is the only setting a JwtBearer API needs.

```csharp
// Server-rendered web app (or BFF): cookie session + OIDC login
builder.Services.AddAuthentication(o =>
{
    o.DefaultScheme = CookieAuthenticationDefaults.AuthenticationScheme;
    o.DefaultChallengeScheme = OpenIdConnectDefaults.AuthenticationScheme;
})
.AddCookie(o => { o.Cookie.SameSite = SameSiteMode.Lax; o.Cookie.HttpOnly = true; })
.AddOpenIdConnect(o =>
{
    o.Authority = "https://login.shop.example";
    o.ClientId = "shop-web";
    o.ClientSecret = builder.Configuration["Oidc:ClientSecret"];   // Key Vault
    o.ResponseType = "code";            // authorization code flow
    o.UsePkce = true;
    o.Scope.Add("offline_access");      // openid + profile are added by default
    o.Scope.Add("orders.read");
    o.SaveTokens = true;                // keep access/refresh tokens in the cookie ticket
    o.GetClaimsFromUserInfoEndpoint = true;
    o.MapInboundClaims = false;
    o.TokenValidationParameters.NameClaimType = "name";
    o.TokenValidationParameters.RoleClaimType = "role";
});

// later, in an endpoint: call a downstream API as the user
var accessToken = await httpContext.GetTokenAsync("access_token");
```

:::example Real-world example
Shop Web (MVC) redirects to Entra ID for login. After sign-in, ASP.NET Core stores the user in an encrypted cookie. Calls from Shop Web to the Orders API attach the user's *access token*; the Orders API (JwtBearer, `Audience = api://orders`) validates it. The *ID token* never leaves Shop Web.
:::

:::q What is the difference between OAuth 2.0 and OpenID Connect?
OAuth 2.0 answers "may this app access that API?" and returns an access token. OIDC adds "who is the user?" by defining the `openid` scope, the ID token, the UserInfo endpoint and discovery. One-liner: *OAuth is authorization, OIDC is authentication built on it.*
:::

### Single Sign-On (SSO)

**Definition.** SSO lets a user authenticate **once** with a central identity provider (IdP) and then access many applications without logging in again. Apps (service providers / relying parties) trust the IdP's assertion.

**How it works.** The first app redirects to the IdP; the IdP creates its own *session cookie*. When the user opens a second app, that app redirects to the same IdP, which sees the existing session and immediately returns a token — no password prompt.

```text
User ──► App A ──302──► IdP (login, MFA)  ──token──► App A  (IdP session cookie set)
User ──► App B ──302──► IdP (already logged in) ──token──► App B  (no prompt)
```

| | SAML 2.0 | OpenID Connect |
|---|---|---|
| Format | XML assertions | JSON / JWT |
| Transport | Browser POST/redirect bindings | Redirect + REST (token endpoint) |
| Age / usage | Older, entrenched in enterprise/legacy SaaS | Modern default; mobile & SPA friendly |
| ASP.NET Core support | Third-party (Sustainsys.Saml2, ITfoxtec) | Built-in `AddOpenIdConnect` |
| Choose when | A partner/vendor only speaks SAML | Everything new |

**Microsoft Entra ID** (formerly Azure AD) is the common corporate IdP. You register an *app registration* per API/client and use **Microsoft.Identity.Web** which wraps JwtBearer/OIDC with Entra-specific defaults (v1/v2 issuers, key rollover, multi-tenant, token cache).

```csharp
// Protect an API with Entra ID
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddMicrosoftIdentityWebApi(builder.Configuration.GetSection("AzureAd"));
```

```json
"AzureAd": {
  "Instance": "https://login.microsoftonline.com/",
  "TenantId": "11111111-2222-3333-4444-555555555555",
  "ClientId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "Audience": "api://aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
}
```

```csharp
using Microsoft.Identity.Web.Resource;

[Authorize]
[ApiController, Route("api/orders")]
[RequiredScope("orders.read")]             // delegated permission: checks the "scp" claim
public class OrdersController : ControllerBase
{
    [HttpPost("{id}/refund")]
    [Authorize(Roles = "Orders.Refund")]   // app role: checks the "roles" claim
    public IActionResult Refund(int id) => NoContent();
}

// Web app signing users in and calling a downstream API
builder.Services.AddMicrosoftIdentityWebAppAuthentication(builder.Configuration, "AzureAd")
    .EnableTokenAcquisitionToCallDownstreamApi(["api://orders/orders.read"])
    .AddInMemoryTokenCaches();             // distributed cache in production
```

:::tip Entra ID facts worth knowing
- Delegated (user) tokens carry `scp` (space-separated scopes); app-only (client credentials) tokens carry `roles`. Use `.default` scope for client credentials: `api://orders/.default`.
- Always validate **both** `aud` and `iss`; multi-tenant apps validate the issuer per tenant.
- Prefer **managed identity** over client secrets for Azure-to-Azure calls (see secrets topic).
- Azure AD B2C is legacy; **Entra External ID** is Microsoft's customer-identity (CIAM) direction — verify current guidance in the docs.
:::

## ASP.NET Core Identity

### Identity Overview

**Definition.** ASP.NET Core Identity is the built-in **membership system**: users, hashed passwords, roles, claims, external logins, lockout, email confirmation, MFA — persisted with EF Core. It is a *user store and login library*, **not** an OAuth/OIDC server.

| Piece | Responsibility |
|---|---|
| `IdentityUser` / `IdentityRole` | Entity classes (`AspNetUsers`, `AspNetRoles`, `AspNetUserClaims`, …) — extend them with your own fields |
| `UserManager<TUser>` | Create user, change/verify password, roles, claims, tokens, MFA keys, lockout counters |
| `SignInManager<TUser>` | Sign in/out with cookies, password check with lockout, 2FA, external logins |
| `RoleManager<TRole>` | Create/manage roles |
| `IPasswordHasher<TUser>` | Hashing — **PBKDF2 with HMAC-SHA512, 128-bit salt, 256-bit subkey, 100,000 iterations by default since .NET 7** (version marker stored in the hash, old hashes are verified and upgraded on next login; raise `PasswordHasherOptions.IterationCount` for stronger defence) |
| Token providers | Email confirmation, password reset, authenticator (TOTP) codes — protected by Data Protection |

```csharp
public class AppUser : IdentityUser<int> { public string DisplayName { get; set; } = ""; }
public class AppDbContext(DbContextOptions<AppDbContext> o)
    : IdentityDbContext<AppUser, IdentityRole<int>, int>(o) { /* + your DbSets */ }

builder.Services
    .AddIdentityCore<AppUser>(o =>             // Core: no cookie scheme hijacking
    {
        o.Password.RequiredLength = 12;        // length beats forced complexity (NIST 800-63B)
        o.Password.RequireNonAlphanumeric = false;
        o.User.RequireUniqueEmail = true;
        o.SignIn.RequireConfirmedEmail = true;
        o.Lockout.MaxFailedAccessAttempts = 5;
        o.Lockout.DefaultLockoutTimeSpan = TimeSpan.FromMinutes(15);
        o.Lockout.AllowedForNewUsers = true;
    })
    .AddRoles<IdentityRole<int>>()
    .AddEntityFrameworkStores<AppDbContext>()
    .AddSignInManager()
    .AddDefaultTokenProviders();
```

:::warn AddIdentity vs AddIdentityCore
`AddIdentity<,>` also registers the Identity **cookie** schemes and makes them the default authenticate/challenge schemes, which silently breaks a JWT API (you get redirects to `/Account/Login`). For token-based APIs use `AddIdentityCore` (as above) or call `AddAuthentication(JwtBearerDefaults.AuthenticationScheme)` *after* `AddIdentity`.
:::

```csharp
// Register + login for a JWT API using Identity for the heavy lifting
app.MapPost("/auth/register", async (RegisterRequest r, UserManager<AppUser> users) =>
{
    var user = new AppUser { UserName = r.Email, Email = r.Email, DisplayName = r.Name };
    var result = await users.CreateAsync(user, r.Password);   // hashes + validates policy
    if (!result.Succeeded) return Results.ValidationProblem(
        result.Errors.ToDictionary(e => e.Code, e => new[] { e.Description }));
    await users.AddToRoleAsync(user, "Customer");
    return Results.Created($"/users/{user.Id}", new { user.Id });
});

app.MapPost("/auth/login", async (LoginRequest r, UserManager<AppUser> users,
    SignInManager<AppUser> signIn, TokenService tokens) =>
{
    var user = await users.FindByEmailAsync(r.Email);
    if (user is null) return Results.Unauthorized();

    // Checks the password and counts failures — but does NOT set a cookie
    var result = await signIn.CheckPasswordSignInAsync(
        user, r.Password, lockoutOnFailure: true);
    if (result.IsLockedOut) return Results.Problem("Account locked.", statusCode: 423);
    if (result.RequiresTwoFactor) return Results.Ok(new { mfaRequired = true });
    if (!result.Succeeded) return Results.Unauthorized();

    var roles = await users.GetRolesAsync(user);
    var (access, expires) = tokens.CreateAccessToken(user, roles);
    return Results.Ok(new { accessToken = access, expiresUtc = expires });
});
```

**Multi-factor authentication (TOTP).** Identity supports authenticator apps out of the box:

```csharp
var key = await users.GetAuthenticatorKeyAsync(user);
if (string.IsNullOrEmpty(key))
{
    await users.ResetAuthenticatorKeyAsync(user);
    key = await users.GetAuthenticatorKeyAsync(user);
}
// show QR for: otpauth://totp/Shop:{email}?secret={key}&issuer=Shop

bool ok = await users.VerifyTwoFactorTokenAsync(
    user, users.Options.Tokens.AuthenticatorTokenProvider, codeFromApp);
if (ok) await users.SetTwoFactorEnabledAsync(user, true);
var recovery = await users.GenerateNewTwoFactorRecoveryCodesAsync(user, 10);
```

### Identity API Endpoints (.NET 8)

**Definition.** .NET 8 added `MapIdentityApi<TUser>()`, which maps a ready-made set of JSON endpoints — `/register`, `/login`, `/refresh`, `/confirmEmail`, `/resendConfirmationEmail`, `/forgotPassword`, `/resetPassword`, `/manage/2fa`, `/manage/info` — so an SPA or mobile app can use Identity without the Razor UI.

```csharp
builder.Services.AddAuthorization();
builder.Services.AddDbContext<AppDbContext>(o => o.UseSqlServer(cs));
builder.Services.AddIdentityApiEndpoints<AppUser>()
    .AddEntityFrameworkStores<AppDbContext>();

var app = builder.Build();
app.MapIdentityApi<AppUser>();                // POST /login?useCookies=true  (or tokens)
app.MapGet("/secure", () => "hi").RequireAuthorization();
```

Important facts: the default `/login` returns an **opaque bearer token** (and a refresh token) produced by the `BearerToken` scheme and protected with Data Protection — it is **not a JWT**. Pass `?useCookies=true` for cookie sessions. It is great for first-party SPAs and quick APIs; it is **not** an OAuth 2.0/OIDC server, so third-party clients, SSO between many apps, or scopes need Duende/OpenIddict/Keycloak/Entra instead.

### Identity Providers and Servers

| Option | What it is | Notes |
|---|---|---|
| **Microsoft Entra ID** | Managed corporate IdP (SaaS) | Best fit for Azure/M365 shops; Microsoft.Identity.Web |
| **Entra External ID / Auth0 / Okta / Cognito** | Managed customer-identity (CIAM) | Social login, MFA, hosted pages; per-user pricing |
| **Duende IdentityServer** | Commercial, certified OIDC/OAuth framework for ASP.NET Core; successor of IdentityServer4 (IS4 reached end of life in Dec 2022) | Free for development and small orgs under a revenue threshold — check the licence |
| **OpenIddict** | Open-source OIDC server **framework** for ASP.NET Core | Free; you assemble UI, storage and flows |
| **Keycloak** | Open-source standalone IdP (Java), SAML + OIDC, admin console, federation | Self-host; popular on Kubernetes |
| **ASP.NET Core Identity** | User store + login (not a protocol server) | Often sits *behind* Duende/OpenIddict |

:::tip Buy before you build
"I would not hand-roll a token server. For internal apps I use Entra ID; for customer-facing, a managed CIAM or Keycloak; if we need a custom server inside ASP.NET Core, Duende or OpenIddict on top of ASP.NET Core Identity."
:::

:::q What are the PBKDF2 settings used by ASP.NET Core Identity, and can they be changed?
Identity's `PasswordHasher` uses PBKDF2 with HMAC-SHA512, a random 128-bit salt, a 256-bit key and, since .NET 7, 100,000 iterations (older versions used HMAC-SHA256 and 10,000). The format is versioned, so old hashes still verify and are rehashed on the next successful login (`PasswordVerificationResult.SuccessRehashNeeded`). Iteration count is configurable through `PasswordHasherOptions`; OWASP recommends higher counts today, so measure on your hardware and raise it.
:::

:::q Why would you use the Identity API endpoints instead of writing your own login controller?
They give a tested implementation of register/login/refresh/confirm/reset/2FA with lockout and password policy in a few lines, saving time and avoiding classic mistakes. I would not use them as a general OAuth server: tokens are opaque and tied to this app's Data Protection keys, so multi-app SSO or third-party clients need an OIDC server.
:::
