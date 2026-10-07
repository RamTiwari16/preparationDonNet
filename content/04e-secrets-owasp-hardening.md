## Secrets, Abuse Protection and Cryptography

### Secret Management

**Definition.** A *secret* is any value that grants access: connection strings, JWT signing keys, API keys, client secrets, certificates' private keys, SAS tokens. Secret management is how you keep them out of source control and out of logs, and how you rotate them.

**Why it matters.** Bots scan public GitHub for keys within minutes of a push, and git history keeps a secret forever — deleting the file does not delete the leak. A leaked signing key lets an attacker mint valid tokens for any user.

**Configuration providers and precedence.** `WebApplication.CreateBuilder` loads providers in this order; **later wins**:

```text
appsettings.json
  -> appsettings.{Environment}.json
     -> User Secrets          (Development environment only)
        -> Environment variables
           -> Command-line arguments
              (+ Azure Key Vault if you add it last)
```

| Where | Tool | Use for | Notes |
|---|---|---|---|
| Developer machine | **User Secrets** (`dotnet user-secrets`) | Local dev only | Stored as plain JSON **outside the repo**: `%APPDATA%\Microsoft\UserSecrets\<id>\secrets.json`. Not encrypted. |
| CI/CD | Pipeline secret variables / GitHub Actions secrets / variable groups linked to Key Vault | Build-time & deploy-time values | Masked in logs |
| Containers / App Service | **Environment variables** | Non-critical config | Visible to anyone who can read the process/pod spec — fine for small secrets only with RBAC |
| Production | **Azure Key Vault + Managed Identity** | Everything sensitive | No credentials in the app at all; audit log, rotation, RBAC |

```bash
dotnet user-secrets init                                  # adds <UserSecretsId> to the csproj
dotnet user-secrets set "Jwt:SigningKey" "k8Zp...32+random bytes..."
dotnet user-secrets set "ConnectionStrings:Shop" "Server=.;Database=Shop;Trusted_Connection=True"
dotnet user-secrets list
```

```bash
# Environment variables map ':' to '__' (double underscore)
export Jwt__SigningKey="..."
export ConnectionStrings__Shop="Server=tcp:shop.database.windows.net;..."
```

```csharp
// Azure Key Vault + Managed Identity. Packages:
//   Azure.Extensions.AspNetCore.Configuration.Secrets, Azure.Identity
if (!builder.Environment.IsDevelopment())
{
    var vault = new Uri($"https://{builder.Configuration["KeyVaultName"]}.vault.azure.net/");
    builder.Configuration.AddAzureKeyVault(vault, new DefaultAzureCredential(),
        new AzureKeyVaultConfigurationOptions { ReloadInterval = TimeSpan.FromMinutes(5) });
}
// Key Vault secret "Jwt--SigningKey"  =>  configuration key "Jwt:SigningKey"
// ('--' replaces ':' because Key Vault names allow only letters, digits and hyphens)

// Fail fast on startup if config is missing or weak
builder.Services.AddOptions<JwtOptions>()
    .BindConfiguration("Jwt")
    .Validate(o => o.SigningKey.Length >= 32, "Jwt:SigningKey too short")
    .ValidateOnStart();
```

**Managed Identity** gives the App Service / Container App / AKS pod an Entra identity. `DefaultAzureCredential` uses it automatically in Azure and falls back to your `az login` / Visual Studio sign-in locally. Grant it the *Key Vault Secrets User* RBAC role. The same identity can reach Azure SQL with no password: `Server=tcp:shop.database.windows.net;Database=Shop;Authentication=Active Directory Default;`. App Service can also resolve `@Microsoft.KeyVault(SecretUri=...)` references in app settings.

:::warn Where secrets leak
Committed `appsettings.json`/`.env`; `ENV`/`ARG` in a Dockerfile (baked into image layers); build logs; exception messages and `EnableSensitiveDataLogging`; Swagger examples; **anything shipped to the SPA** (an Angular `environment.ts` or React `.env` value is public, so a "secret" there is not secret). Add secret scanning to the pipeline (GitHub push protection, gitleaks, truffleHog). If a secret leaks: **rotate first**, clean history second.
:::

:::q How do you manage secrets in an ASP.NET Core app across environments?
Locally `dotnet user-secrets` keeps them out of the repo. In CI they are masked pipeline secrets. In production the app reads from Azure Key Vault using a Managed Identity, so the app has no credential to leak, and I get rotation, RBAC and audit logs. Configuration layering means the same code reads all of them via `IConfiguration`/`IOptions`.
:::

### Rate Limiting and Brute-Force Protection

**Definition.** Rate limiting caps how many requests a client may make in a time window. ASP.NET Core has built-in middleware (`Microsoft.AspNetCore.RateLimiting`, .NET 7+).

**Why it matters.** It blunts brute-force and credential-stuffing on `/login`, scraping, accidental client loops, and cheap denial-of-service. It also protects expensive endpoints (reports, exports).

| Algorithm | Behaviour | Good for |
|---|---|---|
| Fixed window | N requests per window, counter resets at window end | Simple quotas; allows a 2x burst at the boundary |
| Sliding window | Window split into segments that roll | Smoother limit for login attempts |
| Token bucket | Tokens refill steadily, bursts allowed up to bucket size | APIs that tolerate short bursts |
| Concurrency | Max N requests *in flight* | Expensive endpoints (PDF generation) |

```csharp
builder.Services.AddRateLimiter(o =>
{
    o.RejectionStatusCode = StatusCodes.Status429TooManyRequests;
    o.OnRejected = (ctx, ct) =>
    {
        if (ctx.Lease.TryGetMetadata(MetadataName.RetryAfter, out var retry))
            ctx.HttpContext.Response.Headers["Retry-After"] =
                ((int)retry.TotalSeconds).ToString();
        return ValueTask.CompletedTask;
    };

    // Global: 100 req/min per user, or per IP for anonymous callers
    o.GlobalLimiter = PartitionedRateLimiter.Create<HttpContext, string>(ctx =>
    {
        var key = ctx.User.FindFirstValue("sub")
                  ?? ctx.Connection.RemoteIpAddress?.ToString() ?? "anon";
        return RateLimitPartition.GetFixedWindowLimiter(key, _ =>
            new FixedWindowRateLimiterOptions
            { PermitLimit = 100, Window = TimeSpan.FromMinutes(1) });
    });

    // Strict named policy for login: 5 attempts per minute per IP
    o.AddPolicy("login", ctx => RateLimitPartition.GetSlidingWindowLimiter(
        ctx.Connection.RemoteIpAddress?.ToString() ?? "anon",
        _ => new SlidingWindowRateLimiterOptions
        { PermitLimit = 5, Window = TimeSpan.FromMinutes(1), SegmentsPerWindow = 4 }));

    o.AddConcurrencyLimiter("reports", c => { c.PermitLimit = 4; c.QueueLimit = 10; });
});

app.UseRateLimiter();                     // after UseRouting
app.MapPost("/auth/login", LoginHandler).RequireRateLimiting("login");
app.MapGet("/reports/sales", ReportHandler).RequireRateLimiting("reports");
// controllers: [EnableRateLimiting("login")] / [DisableRateLimiting]
```

:::warn Limits of the built-in limiter
It is **in-memory per instance**: with 4 pods the effective limit is 4x. For a real limit use a gateway (Azure API Management, Front Door, YARP, NGINX) or a Redis-backed limiter. Behind a proxy you must enable forwarded headers, or every client appears to have the proxy's IP and one user locks everyone out.
:::

**Brute-force protection is layered:**
1. Per-IP **and** per-account throttling (credential stuffing spreads over many IPs; brute force hammers one account).
2. Temporary account lockout (Identity: 5 failures, 15 min) — remember lockout can be abused to lock a victim out, so combine with throttling and notify the user.
3. Identical error and timing for "unknown user" and "wrong password"; do not leak which emails exist.
4. MFA, breached-password checks (HIBP *k-anonymity* API), CAPTCHA after repeated failures.
5. Log failed logins and alert on spikes.

### Password Hashing

**Definition.** Passwords are stored as the output of a **slow, salted, one-way** *password hashing function* — never encrypted, never plain, never a bare fast hash.

**Why `SHA256(password)` is not acceptable:** it is designed to be fast (billions per second on a GPU), so a leaked table is cracked in hours; without a per-user **salt**, identical passwords give identical hashes and rainbow tables work. A password hash must be **expensive on purpose** (work factor) and **salted**.

| Algorithm | Strength | .NET | Notes |
|---|---|---|---|
| **PBKDF2** | CPU-hard only | `Rfc2898DeriveBytes.Pbkdf2` (built in), used by ASP.NET Core Identity | FIPS-friendly; OWASP: >= 600,000 iterations with HMAC-SHA256 (210,000 with SHA-512) |
| **bcrypt** | CPU-hard, 72-byte input limit | `BCrypt.Net-Next` | Work factor >= 10-12; use `EnhancedHashPassword` (pre-hashes long input) |
| **Argon2id** | CPU **and memory**-hard — best against GPUs | `Konscious.Security.Cryptography.Argon2`, `Isopoh...` | OWASP minimum: 19 MiB memory, 2 iterations, parallelism 1 — *check the cheat sheet, numbers move* |

```csharp
public static class Pbkdf2Hasher
{
    private const int SaltSize = 16, KeySize = 32, Iterations = 600_000;

    public static string Hash(string password)
    {
        var salt = RandomNumberGenerator.GetBytes(SaltSize);            // unique per user
        var key = Rfc2898DeriveBytes.Pbkdf2(
            password, salt, Iterations, HashAlgorithmName.SHA256, KeySize);
        return $"v1.{Iterations}.{Convert.ToBase64String(salt)}.{Convert.ToBase64String(key)}";
    }                                         // iterations stored => can raise later

    public static bool Verify(string password, string stored)
    {
        var p = stored.Split('.');
        var iterations = int.Parse(p[1]);
        var salt = Convert.FromBase64String(p[2]);
        var expected = Convert.FromBase64String(p[3]);
        var actual = Rfc2898DeriveBytes.Pbkdf2(
            password, salt, iterations, HashAlgorithmName.SHA256, expected.Length);
        return CryptographicOperations.FixedTimeEquals(actual, expected); // no timing leak
    }
}

// bcrypt
var h = BCrypt.Net.BCrypt.EnhancedHashPassword(password, workFactor: 12);
bool ok = BCrypt.Net.BCrypt.EnhancedVerify(password, h);

// Argon2id (Konscious)
var argon = new Argon2id(Encoding.UTF8.GetBytes(password))
{ Salt = RandomNumberGenerator.GetBytes(16), DegreeOfParallelism = 2,
  MemorySize = 19 * 1024, Iterations = 2 };           // MemorySize in KiB
byte[] hash = argon.GetBytes(32);
```

A **pepper** is an extra secret mixed in and stored *outside* the DB (Key Vault); a salt is public and per-user. Best practice in .NET: use `UserManager`/`IPasswordHasher<T>` and let Identity handle upgrades, instead of writing your own.

:::q Why is SHA-256 alone not good enough for passwords?
It is fast and unsalted by default, so attackers test billions of guesses per second and reuse precomputed tables. Password hashing needs a unique salt and a tunable work factor (PBKDF2 iterations, bcrypt cost, Argon2 memory/time) so each guess is expensive, plus constant-time comparison. In ASP.NET Core I use Identity's `PasswordHasher` (PBKDF2) or Argon2id.
:::

### Data Protection API

**Definition.** The ASP.NET Core **Data Protection API** is a built-in, key-managed encryption service for *short-to-medium-lived app data*: it powers authentication cookies, antiforgery tokens, Identity reset/confirmation tokens and the Identity bearer tokens. `IDataProtector.Protect/Unprotect` give you the same for your own payloads (magic links, signed state).

```csharp
public sealed class InvoiceLinkService(IDataProtectionProvider provider)
{
    // "purpose" isolates payloads: a token protected for one purpose can't be read by another
    private readonly ITimeLimitedDataProtector _protector =
        provider.CreateProtector("Shop.InvoiceLinks.v1").ToTimeLimitedDataProtector();

    public string CreateToken(int orderId) =>
        _protector.Protect(orderId.ToString(), TimeSpan.FromHours(24));  // self-expiring

    public int? ReadToken(string token)
    {
        try { return int.Parse(_protector.Unprotect(token)); }
        catch (CryptographicException) { return null; }   // tampered, wrong purpose, expired
    }
}
```

**The gotcha everyone hits: the key ring.** Keys are generated automatically, rotate about every 90 days (old keys stay for decryption) and are stored by default in the user profile (`%LOCALAPPDATA%\ASP.NET\DataProtection-Keys`, `~/.aspnet/DataProtection-Keys`). In containers or with multiple instances, each instance has its own keys, so a cookie from instance A is unreadable on B and **everyone is logged out on every deploy**. Share and protect the key ring:

```csharp
builder.Services.AddDataProtection()
    .SetApplicationName("shop")                         // same name on every instance
    .PersistKeysToAzureBlobStorage(
        new Uri("https://shopstore.blob.core.windows.net/keys/keys.xml"),
        new DefaultAzureCredential())                    // Azure.Extensions.AspNetCore.DataProtection.Blobs
    .ProtectKeysWithAzureKeyVault(
        new Uri("https://shopkv.vault.azure.net/keys/dp-key"),
        new DefaultAzureCredential());                   // keys encrypted at rest
// alternatives: PersistKeysToStackExchangeRedis, PersistKeysToDbContext<AppDbContext>
```

:::warn Don't misuse it
Data Protection is not for long-term data at rest (keys expire and rotate; losing the ring loses the data), not for password storage (use a password hash), and not for cross-system interop (the format is private to ASP.NET Core). For database encryption use TDE / Always Encrypted or AES-GCM with Key Vault-managed keys.
:::

## OWASP Top 10 for .NET Developers

### OWASP Top 10 (2025) and .NET Mitigations

**Definition.** The OWASP Top 10 is the industry-standard awareness list of the most critical web application risks. The 2025 edition reordered the 2021 list and added supply-chain and exceptional-condition categories (SSRF is now folded into A01).

| # | Category | Typical .NET example | Mitigation in ASP.NET Core / .NET |
|---|---|---|---|
| A01 | **Broken Access Control** | IDOR `/orders/18`, missing `[Authorize]`, CORS wildcard with credentials, SSRF | Fallback policy, resource-based authorization, ownership filter in queries, deny by default, CORS allow-list, validate outbound URLs |
| A02 | **Security Misconfiguration** | Developer exception page or Swagger open in prod, default credentials, verbose errors | `UseExceptionHandler` + `ProblemDetails`, per-environment config, security headers, least-privilege cloud roles, IaC scanning |
| A03 | **Software Supply Chain Failures** | Vulnerable or malicious NuGet/npm package, poisoned CI | `dotnet list package --vulnerable`, NuGet Audit, Dependabot/Renovate, lock files (`RestoreLockedMode`), SBOM, private feed, pinned base images, hardened pipelines |
| A04 | **Cryptographic Failures** | MD5/SHA-1 passwords, HTTP, hard-coded keys, PII in clear | HTTPS + HSTS, PBKDF2/Argon2, Data Protection, AES-GCM, Key Vault, TDE/Always Encrypted |
| A05 | **Injection** | SQL injection, command injection, XSS | LINQ/parameters, `FromSql` not `FromSqlRaw` concatenation, output encoding, CSP, allow-list validation, avoid `Process.Start` with user input |
| A06 | **Insecure Design** | No abuse cases: negative quantities, coupon reuse, no rate limits | Threat modelling, server-side business-rule validation, rate limiting, idempotency keys |
| A07 | **Authentication Failures** | Weak passwords, no lockout, credential stuffing, long-lived tokens | Identity lockout + MFA, strong hashing, short JWT + rotating refresh, rate limiting, breached-password check |
| A08 | **Software or Data Integrity Failures** | Insecure deserialization, unsigned artifacts, unverified webhooks | Never `BinaryFormatter` (removed from modern .NET), typed `System.Text.Json`, verify webhook HMAC signatures, signed artifacts, protected branches |
| A09 | **Security Logging and Alerting Failures** | No audit trail, secrets/PII in logs, nobody notices attacks | Serilog structured logs, audit login failures and permission changes, correlation ids, App Insights alerts, never log tokens |
| A10 | **Mishandling of Exceptional Conditions** | Stack traces to the client, fail-open authorization on exception, swallowed errors | Global `IExceptionHandler` returning `ProblemDetails`, fail **closed**, timeouts and cancellation, resilient handling of bad input |

**Also know the OWASP API Security Top 10:** BOLA (object-level authorization = IDOR), broken authentication, **BOPLA / mass assignment**, unrestricted resource consumption, broken function-level authorization, SSRF. Mass assignment is why you bind to **DTOs**, never to entities:

```csharp
// VULNERABLE: client sends {"name":"Asha","isAdmin":true}
app.MapPut("/users/{id}", async (int id, User body, AppDbContext db) =>
{ db.Update(body); await db.SaveChangesAsync(); });

// SAFE: DTO contains only fields the caller may set
public record UpdateProfileDto(string Name, string? Phone);
app.MapPut("/users/me", async (UpdateProfileDto dto, ClaimsPrincipal me, AppDbContext db) =>
{
    var id = int.Parse(me.FindFirstValue("sub")!);
    await db.Users.Where(u => u.Id == id).ExecuteUpdateAsync(s => s
        .SetProperty(u => u.Name, dto.Name).SetProperty(u => u.Phone, dto.Phone));
    return Results.NoContent();
}).RequireAuthorization();
```

:::tip How to answer "how do you secure an ASP.NET Core API?"
Structure: **transport** (HTTPS, HSTS) → **authentication** (OIDC/JWT, short tokens) → **authorization** (fallback policy, policies, resource checks) → **input/output** (DTO validation, parameterised queries, encoding, CORS allow-list) → **secrets** (Key Vault, managed identity) → **abuse** (rate limiting, lockout) → **operations** (logging, alerts, dependency scanning). One sentence each, then offer to go deeper on any layer.
:::

## Security Scenarios

:::scenario A developer committed the production connection string to GitHub
1. **Rotate immediately** — change the SQL password / regenerate the key; assume it is compromised, even if the repo is private (forks, clones, CI caches).
2. Check Azure SQL/audit logs and firewall for unknown access; look at data exfiltration.
3. Remove it from the code and history (`git filter-repo` / BFG) — secondary, because the leak already happened.
4. Prevent a repeat: Key Vault + Managed Identity (no password at all), `.gitignore`, pre-commit and server-side secret scanning with push protection, and `ValidateOnStart` so missing config fails fast instead of tempting people to hard-code values.
:::

:::scenario Brute-force attack on the login endpoint
Symptoms: thousands of `POST /auth/login` per minute, many failures, from varied IPs. Response: (1) immediate - `RequireRateLimiting("login")` per IP and per username, 429 + `Retry-After`; (2) enable Identity lockout (`lockoutOnFailure: true`) and notify affected users; (3) block known bad ASNs at the WAF/Front Door; (4) add MFA and breached-password checks; (5) generic error messages and constant-time hashing paths to prevent user enumeration; (6) alert on failed-login ratio. Mention credential stuffing needs the **per-account** limit because the IPs differ.
:::

## Quick-fire Q&A

:::q What is the difference between authentication and authorization, and 401 vs 403?
Authentication proves who you are; authorization decides what you may do. 401 means "not authenticated" (missing/invalid credentials); 403 means "authenticated but not allowed".
:::

:::q What are the three parts of a JWT and which claims must you validate?
Header (algorithm, type), payload (claims) and signature, base64url-encoded and dot-separated. The API must validate the signature, issuer (`iss`), audience (`aud`) and lifetime (`exp`/`nbf`), and pin the allowed algorithm.
:::

:::q HS256 vs RS256 in one sentence each?
HS256 uses one shared secret to both sign and verify, so every validator could also forge tokens. RS256 signs with a private key and verifies with a public key, so APIs only need the public key published via JWKS.
:::

:::q Why short-lived access tokens plus refresh tokens?
A stateless JWT can't be revoked, so I keep it to minutes to limit theft damage. The refresh token is opaque, stored hashed in the DB, rotated on each use with reuse detection, so I get revocation and a good user experience.
:::

:::q localStorage, memory or cookie for tokens?
Not `localStorage` — any XSS reads it. Access token in memory, refresh token in an HttpOnly, Secure, SameSite cookie scoped to the refresh endpoint; or a BFF that keeps tokens server-side. Cookies bring CSRF, which SameSite and antiforgery handle.
:::

:::q Role-based or policy-based authorization?
Roles for coarse groups; policies when the rule uses claims, several conditions or business logic — each policy is a set of requirements evaluated by handlers. For "does this user own this order" I use resource-based authorization with `IAuthorizationService`.
:::

:::q What does a fallback authorization policy do?
It applies to endpoints that declare no authorization metadata, so setting `RequireAuthenticatedUser()` makes the API secure by default; public endpoints must opt out with `[AllowAnonymous]`.
:::

:::q Why Authorization Code with PKCE instead of implicit?
Only a short-lived code crosses the browser; the token is fetched on a back channel and the PKCE verifier proves the same client that started the flow is redeeming it. Implicit exposed tokens in URLs and is deprecated.
:::

:::q ID token vs access token?
The ID token tells the client who logged in (audience = client, always a JWT). The access token is for calling an API (audience = API). Never send the ID token to an API.
:::

:::q How do CORS and CSRF differ?
CORS is a browser rule that blocks JavaScript from *reading* cross-origin responses unless the server allows the origin. CSRF is an attack that makes the browser *send* an authenticated request using automatically attached cookies. CORS doesn't prevent CSRF; SameSite cookies and antiforgery tokens do.
:::

:::q How do you prevent SQL injection with EF Core?
Use LINQ (parameterised automatically); for raw SQL use `FromSql`/`FromSqlInterpolated`/`ExecuteSql`, which parameterise interpolation holes, or pass `SqlParameter`. Never concatenate into `FromSqlRaw`. Whitelist dynamic column names and give the DB login least privilege.
:::

:::q How do you store passwords?
With a salted, slow password hash — PBKDF2, bcrypt or Argon2id — via ASP.NET Core Identity's `PasswordHasher`; never SHA-256 alone, never reversible encryption. Compare in constant time and rehash when parameters are upgraded.
:::

:::q How do you protect against brute force on login?
Rate limiting per IP and per account, Identity lockout, MFA, breached-password checks, generic error messages and monitoring. I use `AddRateLimiter` with a sliding-window `login` policy and a gateway for multi-instance limits.
:::

:::q Where do production secrets live?
In Azure Key Vault, read via `AddAzureKeyVault` with a Managed Identity, so no credential is stored in config; user-secrets locally; never in git or Docker images.
:::

:::q Why do users get logged out after each deployment behind multiple instances?
The Data Protection key ring is per instance or lost with the container, so cookies/antiforgery tokens encrypted by one key can't be decrypted by another. Persist keys to shared storage (Blob, Redis, DB), protect them with Key Vault, and set the same application name.
:::
