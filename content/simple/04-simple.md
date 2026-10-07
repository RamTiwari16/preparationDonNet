### Authentication vs Authorization

**In simple words:** Authentication checks who you are, for example with a password or a token. Authorization checks what you are allowed to do, and it always comes after authentication. If the API does not know who you are, it returns 401. If it knows you but you are not allowed, it returns 403.

**Real-life example:** At the airport, passport control checks who you are. The lounge door checks whether your ticket lets you in, and a valid passport alone does not open it.

**Interview question:** What is the difference between authentication and authorization, and between 401 and 403?

**Simple answer:** Authentication proves identity; authorization decides what that identity may access. 401 means "we don't know who you are", and 403 means "we know you, but the answer is no". In ASP.NET Core, the handler's challenge produces the 401 and forbid produces the 403.

### ASP.NET Core Authentication Architecture

**In simple words:** Authentication has four parts. A scheme is a name, like "Bearer" or "Cookies", and a handler is the code behind that name that reads the token or cookie. The authentication middleware calls the handler on every request. The result is a `ClaimsPrincipal` (the user), stored in `HttpContext.User`.

**Real-life example:** A building accepts staff cards and visitor passes, and each has its own checking desk (handler). Whoever passes gets a badge that lists facts about them (claims).

**Interview question:** What is the difference between a `ClaimsPrincipal`, a `ClaimsIdentity` and a `Claim`?

**Simple answer:** A `Claim` is one fact about the user, like an email or a role. A `ClaimsIdentity` is a set of claims from one login source. A `ClaimsPrincipal` is the whole user and can hold several identities; `HttpContext.User` is a `ClaimsPrincipal`.

### JWT Anatomy

**In simple words:** A JWT (JSON Web Token) is a string with three parts joined by dots: header, payload and signature. The payload holds claims like `sub` (user ID), `exp` (expiry time) and `aud` (who the token is for). The parts are only base64url-encoded, not encrypted, so anyone holding the token can read them. The signature proves that nobody changed the token.

**Real-life example:** A concert wristband has your name printed on it and a special hologram. Anyone can read the name, but nobody can copy the hologram.

**Interview question:** Is a JWT encrypted?

**Simple answer:** No. A normal JWT is only encoded and signed, so it protects against changes but not against reading. So I never put secrets in claims, I keep the payload small, and I always send tokens over HTTPS.

```text
header.payload.signature
{"alg":"HS256","typ":"JWT"} . {"sub":"42","exp":1760000900} . <signature>
```

### Signing Algorithms: HS256 vs RS256

**In simple words:** HS256 signs and checks tokens with one shared secret key. RS256 signs with a private key and checks with a public key. With HS256, every API that can check tokens can also create them. With RS256, APIs get only the public key, often from a JWKS URL (a published list of public keys).

**Real-life example:** HS256 is like giving every shop the same stamp that head office uses to make vouchers. RS256 is like giving shops only a way to check the stamp, while head office keeps the stamp itself.

**Interview question:** HS256 or RS256 — which one would you pick?

**Simple answer:** If one service both issues and checks its own tokens, HS256 with a long random key from Key Vault is fine. When other services must validate tokens, I use RS256 or ES256, so they cannot forge tokens. I also pin the allowed algorithm with `ValidAlgorithms`.

### Issuing a Token (login endpoint)

**In simple words:** The login endpoint checks the email and password. If they are correct, it builds a token with claims, issuer, audience, expiry and signing credentials. In new code, use `JsonWebTokenHandler`, which is faster than the older `JwtSecurityTokenHandler`. Return the same error for "unknown user" and "wrong password", so attackers cannot discover valid emails.

**Real-life example:** A hotel desk checks your ID and booking. Then it gives you a key card that works for your room until checkout.

**Interview question:** What does a secure login endpoint do?

**Simple answer:** It verifies the password with a password hasher, checks lockout, and returns the same 401 message for every failure. On success, it creates a short-lived access token and a refresh token. It is also rate-limited to slow down password guessing.

### JwtBearer Configuration and TokenValidationParameters

**In simple words:** `AddJwtBearer` reads the `Authorization: Bearer <token>` header and checks the token. `TokenValidationParameters` lists the checks: issuer, audience, lifetime, signing key and allowed algorithms. Never turn a check off just to make things work. Also set `MapInboundClaims = false` with explicit name and role claim types, or role checks can fail silently.

**Real-life example:** A ticket inspector checks the train company, the route, the date and the hologram. Skipping one check lets fake tickets through.

**Interview question:** What is `ClockSkew`, and why would you reduce it?

**Simple answer:** Server clocks are never exactly the same, so expiry checks allow a small tolerance. The default is 5 minutes, so a 15-minute token really works for 20. If the servers sync their clocks, I set it to 30–60 seconds.

```csharp
o.TokenValidationParameters = new TokenValidationParameters
{
    ValidIssuer = jwt.Issuer,
    ValidAudience = jwt.Audience,
    IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwt.SigningKey)),
    ValidAlgorithms = [SecurityAlgorithms.HmacSha256],
    ClockSkew = TimeSpan.FromSeconds(30)
};
```

### Access Token vs Refresh Token

**In simple words:** An access token is short-lived (5–15 minutes) and sent with every API call. A refresh token lives for days and is used only to get a new access token. Store refresh tokens as hashes in the database and rotate them: each use returns a new one and invalidates the old one. If an old one is used again, someone copied it, so revoke the whole token family.

**Real-life example:** A gym day pass works only today. Your membership card gets you a new day pass each day, and the gym can cancel the card at any time.

**Interview question:** Why use short-lived access tokens together with refresh tokens?

**Simple answer:** A JWT cannot be revoked before it expires, so I keep it short to limit the damage if it is stolen. The refresh token is random, stored as a hash and rotated on each use, so I can revoke it at any time. Reuse detection catches stolen refresh tokens.

### Where to Store Tokens in an SPA

**In simple words:** A browser app can keep tokens in JavaScript memory, in `localStorage`, or in cookies. `localStorage` is the worst choice, because any injected script (XSS) can read it. A good setup keeps the access token in memory and the refresh token in an `HttpOnly`, `Secure`, `SameSite=Strict` cookie. The safest option is a BFF (Backend-For-Frontend), which keeps all tokens on the server.

**Real-life example:** Do not leave your house key under the doormat (`localStorage`). Keep it in your pocket (memory), or let the building's concierge hold it for you (BFF).

**Interview question:** Where should an SPA store tokens?

**Simple answer:** Not in `localStorage`, because any XSS attack can steal it. I keep the access token in memory and the refresh token in an HttpOnly, Secure, SameSite cookie. For high-risk apps, I use a BFF, so no token reaches the browser at all.

### Logout and Revocation

**In simple words:** A JWT stays valid until it expires, even after logout. So a real logout has two parts. First, revoke the refresh token in the database and delete its cookie. Second, let the access token expire within minutes, or block it early with a deny-list of its `jti` (token ID) or a token version check.

**Real-life example:** When you cancel a gym membership, the card stops working. A day pass you already printed still works until tonight, unless the gym adds its number to a blocked list.

**Interview question:** How do you log a user out when using JWT?

**Simple answer:** I revoke the refresh token family on the server and delete the refresh cookie. The access token dies within its short lifetime, or I deny-list its `jti` in Redis or bump the user's token version for an immediate effect. For SSO, I also call the identity provider's logout endpoint.

### Claims, Roles and Policies

**In simple words:** A claim is a fact about the user, like `department=sales`. A role is just a claim of type "role", like `Admin`. A policy is a named set of requirements, like "CanRefundOrders", checked against the user. Policies are better than role lists in code, because you change who has a capability in one place.

**Real-life example:** In a hospital, your badge shows your name, department and job title. The rule "may open the medicine cabinet" is a policy that checks several of these facts.

**Interview question:** Role-based or policy-based authorization — when do you use which?

**Simple answer:** I use roles for simple, stable groups like Admin and Customer. I use policies when a rule needs other claims, several conditions or business logic. A policy is a list of requirements, and every requirement must pass.

```csharp
builder.Services.AddAuthorizationBuilder()
    .AddPolicy("AdminOnly", p => p.RequireRole("Admin"))
    .AddPolicy("SalesStaff", p => p.RequireClaim("department", "sales"));
```

### Resource-Based Authorization

**In simple words:** Attributes like `[Authorize]` run before your code loads any data. So they cannot answer "may this user see this order?". Resource-based authorization loads the order first, then calls `IAuthorizationService` to check it. This stops IDOR (Insecure Direct Object Reference), where a user changes `/orders/17` to `/orders/18` and sees someone else's order.

**Real-life example:** A bank teller first looks up the account. Then the teller checks that you own it before showing the balance.

**Interview question:** How do you make sure a user can only see their own orders?

**Simple answer:** I use resource-based authorization: load the order, then call `IAuthorizationService.AuthorizeAsync` with an owner requirement. I return 404 instead of 403, to hide that the order exists. Even better, I filter by owner in the query itself.

```csharp
var order = await db.Orders
    .SingleOrDefaultAsync(o => o.Id == id && o.CustomerId == userId);
```

### [Authorize], [AllowAnonymous] and the Fallback Policy

**In simple words:** `[Authorize]` requires a logged-in user, or a role or policy if you add one. `[AllowAnonymous]` opens an endpoint to everyone and wins over `[Authorize]`. The fallback policy applies to endpoints that have no authorization attribute at all. Set it to require an authenticated user, so new endpoints are secure by default.

**Real-life example:** In an office, every door is locked by default. Only the reception door has a sign saying "open to the public".

**Interview question:** What does a fallback authorization policy do?

**Simple answer:** It applies to every endpoint that declares no authorization metadata. If I set it to `RequireAuthenticatedUser()`, the whole API is secure by default. Public endpoints, like health checks, must opt out with `[AllowAnonymous]`.

```csharp
builder.Services.AddAuthorization(o =>
    o.FallbackPolicy = new AuthorizationPolicyBuilder()
        .RequireAuthenticatedUser().Build());
```

### Cookie Authentication vs JWT

**In simple words:** With cookie authentication, the browser sends the login cookie automatically on every request. With `HttpOnly`, scripts cannot read it, but it needs CSRF protection. With JWT, your code adds the token to the `Authorization` header itself. That suits mobile apps and APIs, but revoking a token early is harder.

**Real-life example:** A cookie is like a festival wristband: it shows itself at every gate automatically. A JWT is like a ticket you must hand over yourself at each gate.

**Interview question:** When would you use cookie authentication and when JWT?

**Simple answer:** I use cookies for server-rendered apps, same-site SPAs and the BFF pattern, with SameSite and antiforgery protection. I use JWT bearer tokens for mobile apps, third-party clients and service-to-service calls. Cookie sessions are easy to revoke; JWTs scale without a session store.

### OAuth 2.0

**In simple words:** OAuth 2.0 lets an app get an access token to call an API for a user, without ever seeing the user's password. It is about authorization, not login. Apps with users should use Authorization Code with PKCE (a one-time secret proof that makes a stolen code useless). Machine-to-machine calls use Client Credentials, and the implicit and password grants are deprecated.

**Real-life example:** You give a parking valet a special key that starts the car but cannot open the boot. You never hand over your full set of keys.

**Interview question:** Why was the implicit flow deprecated, and what replaces it?

**Simple answer:** The implicit flow put the access token in the redirect URL, where it could leak through browser history, logs or scripts. Authorization Code with PKCE replaces it: only a short-lived code goes through the browser. The token is fetched on a back channel, and PKCE proves that the same client started the flow.

### OpenID Connect (OIDC)

**In simple words:** OIDC is an identity layer on top of OAuth 2.0. When the app asks for the `openid` scope, it also gets an ID token: a signed JWT that says who logged in. The ID token is for the client app, and the access token is for the API. Never send the ID token to an API.

**Real-life example:** At a conference, the desk gives you a name badge (ID token) and separate session tickets (access tokens). You show the tickets at each room, not the badge.

**Interview question:** What is the difference between OAuth 2.0 and OpenID Connect?

**Simple answer:** OAuth 2.0 answers "may this app call that API?" and returns an access token. OIDC adds "who is the user?" with the ID token, the UserInfo endpoint and discovery. In short, OAuth is authorization, and OIDC is authentication built on top of it.

### Single Sign-On (SSO)

**In simple words:** SSO lets a user log in once with a central identity provider (IdP) and then use many apps without logging in again. The first app sends the user to the IdP, which creates its own session. When the user opens another app, the IdP sees that session and returns a token at once. OIDC is the modern standard; SAML is older but still common in large companies.

**Real-life example:** At a theme park, you buy one wristband at the entrance. Every ride then lets you in without a new ticket.

**Interview question:** How does SSO work, and would you use OIDC or SAML?

**Simple answer:** All apps trust the same identity provider, which keeps a session after the first login, so later apps get a token without a password prompt. For new apps, I use OIDC, often with Microsoft Entra ID and Microsoft.Identity.Web. I use SAML only when a partner supports nothing else.

### Identity Overview

**In simple words:** ASP.NET Core Identity is a built-in membership system that stores users, hashed passwords, roles and claims with EF Core. It supports lockout, email confirmation, external logins and two-factor login. `UserManager` manages users, and `SignInManager` handles sign-in. It is a user store, not an OAuth or OIDC server.

**Real-life example:** It is like a gym's membership desk. It keeps member records, checks cards, and blocks a card after too many wrong PINs.

**Interview question:** How does Identity store passwords, and why use `AddIdentityCore` for a JWT API?

**Simple answer:** Since .NET 7, Identity hashes passwords with PBKDF2, HMAC-SHA512, a random salt and 100,000 iterations by default. `AddIdentity` also makes cookie schemes the default, which breaks a JWT API with login redirects. So for token APIs, I use `AddIdentityCore` and set JWT as the default scheme.

### Identity API Endpoints (.NET 8)

**In simple words:** In .NET 8, `MapIdentityApi<TUser>()` adds ready-made JSON endpoints: register, login, refresh, confirm email, reset password and 2FA. An SPA or mobile app can use Identity without Razor pages. The login returns an opaque bearer token (not a JWT), or a cookie if you call it with `?useCookies=true`. It is not an OAuth or OIDC server.

**Real-life example:** It is like a ready-made ticket booth for your own shop. It works well there, but other shops cannot accept its tickets.

**Interview question:** When would you use the Identity API endpoints?

**Simple answer:** For a first-party SPA or mobile app, they give tested register, login, refresh and reset endpoints in a few lines. The tokens are opaque and tied to this app's Data Protection keys. For SSO across many apps or for third-party clients, I need a real OIDC server.

### Identity Providers and Servers

**In simple words:** An identity provider (IdP) logs users in and issues tokens. Microsoft Entra ID is the managed choice for company staff, and Auth0, Okta or Entra External ID are managed options for customers. Duende IdentityServer and OpenIddict let you build your own OIDC server in ASP.NET Core. Keycloak is an open-source IdP you host yourself.

**Real-life example:** Most shops use a bank's card machine instead of building their own payment system. The same idea applies to login.

**Interview question:** Would you build your own token server?

**Simple answer:** No, I buy before I build. For internal apps, I use Entra ID, and for customer apps, a managed CIAM (customer identity) service or Keycloak. If we need a custom server, I use Duende IdentityServer or OpenIddict on top of ASP.NET Core Identity.

### CORS (Cross-Origin Resource Sharing)

**In simple words:** An origin is scheme + host + port, like `https://shop.example`. Browsers block JavaScript from reading responses from another origin, and CORS lets your API allow trusted origins with `Access-Control-*` headers. For many requests, the browser first sends an `OPTIONS` preflight request to ask permission. Only browsers enforce CORS, so it does not protect your API from tools like Postman.

**Real-life example:** A school gate lets only parents on the approved list collect children. Couriers who go straight to the school office are not checked against that list.

**Interview question:** Why can't you use `AllowAnyOrigin` together with `AllowCredentials`?

**Simple answer:** Browsers reject a wildcard origin when the request carries cookies or other credentials, and ASP.NET Core throws an error at startup. Allowing every origin with credentials would let any website act as the logged-in user. The correct fix is an explicit list of trusted origins with `WithOrigins`.

```csharp
builder.Services.AddCors(o => o.AddPolicy("Spa", p => p
    .WithOrigins("https://shop.example")
    .AllowAnyHeader().AllowAnyMethod()
    .AllowCredentials()));
```

### CSRF (Cross-Site Request Forgery)

**In simple words:** CSRF tricks your browser into sending a request to a site where you are logged in. It works because browsers attach cookies automatically. The attacker cannot read the response, but can change data, like your email address. Defences are SameSite cookies, antiforgery tokens, checking the `Origin` header, and never changing data with GET.

**Real-life example:** A stranger gives you a sealed envelope to drop at your bank. The bank trusts it because you hand it in, but inside is a transfer order to the stranger.

**Interview question:** Do you need antiforgery tokens for a JWT-protected Web API?

**Simple answer:** Not if the token is sent in the `Authorization` header, because the browser never adds it automatically. As soon as authentication uses a cookie, including a BFF or a refresh-token cookie, I need SameSite plus antiforgery or an Origin check. That applies to every endpoint that changes data.

### XSS (Cross-Site Scripting)

**In simple words:** XSS happens when an attacker's script gets into a page that other users see. The script runs with your site's rights: it can read the page, call your API as the user, and steal tokens from `localStorage`. The main defences are output encoding, never building HTML from strings, sanitising rich text, and a Content Security Policy (CSP).

**Real-life example:** Someone pins a fake notice on the school's official board saying "pay fees at this new counter". Everyone trusts it, because it is on the official board.

**Interview question:** How does Razor protect you from XSS, and where does it not?

**Simple answer:** Razor HTML-encodes every `@expression`, so `<script>` becomes harmless text. It does not protect `Html.Raw`, `MarkupString`, data put into JavaScript blocks, or unsafe `href` values. I also add a CSP and HttpOnly cookies as a second layer.

```javascript
el.innerHTML = review.text;    // unsafe: can run scripts
el.textContent = review.text;  // safe: shown as plain text
```

### SQL Injection in ASP.NET Core

**In simple words:** SQL injection happens when user input is joined into SQL text, so the database runs it as code. EF Core LINQ queries are safe, because they always send values as parameters. `FromSqlRaw` with string concatenation or `$"..."` interpolation is not safe. Use `FromSql` with interpolation, which turns each value into a parameter.

**Real-life example:** A clerk copies your form text straight into an official order. If you write "and also give me all the cash", the clerk does it.

**Interview question:** Does Entity Framework protect you from SQL injection?

**Simple answer:** For LINQ queries, yes, because values are always parameterised. Raw SQL is safe only with `FromSql`/`FromSqlInterpolated` or explicit `SqlParameter`s, never with concatenation in `FromSqlRaw`. Column names cannot be parameters, so I whitelist them, and the database login gets least privilege.

```csharp
var bad  = db.Products.FromSqlRaw("SELECT * FROM Products WHERE Name = '" + term + "'");
var good = db.Products.FromSql($"SELECT * FROM Products WHERE Name = {term}");
```

### HTTPS, HSTS and Redirection

**In simple words:** HTTPS encrypts traffic between the client and the server. HSTS (HTTP Strict Transport Security) is a header that tells the browser to use only HTTPS for your site for a set time. `UseHttpsRedirection` sends plain HTTP requests to HTTPS. Behind a proxy, enable forwarded headers, or you can get endless redirect loops.

**Real-life example:** A bank tells you: "From now on, use only the secure front entrance." After that, you never try the side door again.

**Interview question:** What is HSTS, and why use it with HTTPS redirection?

**Simple answer:** Redirection moves an HTTP request to HTTPS, but that first request still travels in clear text. HSTS tells the browser to go straight to HTTPS next time, which stops downgrade attacks. I enable `UseHsts` only outside Development, and pure APIs should not listen on HTTP at all.

### Security Headers

**In simple words:** Security headers are response headers that tell the browser to behave more safely. `Content-Security-Policy` limits where scripts can come from, and `X-Content-Type-Options: nosniff` stops the browser from guessing file types. `X-Frame-Options` or CSP `frame-ancestors` blocks clickjacking (hiding your page inside another site). `Referrer-Policy` stops full URLs from leaking to other sites.

**Real-life example:** A building posts clear rules at the entrance, and the guard enforces them for every visitor. Here the browser is the guard.

**Interview question:** Which security headers would you add to an ASP.NET Core app?

**Simple answer:** HSTS, a Content-Security-Policy, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` or `frame-ancestors`, `Referrer-Policy` and `Permissions-Policy`. I also remove the `Server` header. I check the result with securityheaders.com or OWASP ZAP.

### Secret Management

**In simple words:** A secret is any value that gives access: connection strings, signing keys, API keys and client secrets. Never put secrets in git, because git history keeps them forever. Locally, use `dotnet user-secrets`, and in CI, use masked pipeline secrets. In production, use Azure Key Vault with a Managed Identity, so the app has no password to leak.

**Real-life example:** A bank keeps the vault codes in a locked safe, not on a sticky note on the counter.

**Interview question:** How do you manage secrets across environments?

**Simple answer:** Locally I use user secrets, in CI I use masked pipeline secrets, and in production I read from Key Vault with a Managed Identity. The app reads all of them the same way, through `IConfiguration` and options. If a secret leaks, I rotate it first and clean the git history second.

### Rate Limiting and Brute-Force Protection

**In simple words:** Rate limiting caps how many requests a client can make in a time window, and on the login endpoint it slows down password guessing. Protect logins in layers: limit per IP and per account, and lock the account after several failures. Show the same error for every failure, and add MFA (multi-factor authentication). The built-in limiter counts per server, so use a gateway for a global limit.

**Real-life example:** An ATM blocks your card after three wrong PINs. The bank also notices when many cards fail at the same ATM.

**Interview question:** How do you protect the login endpoint from brute-force attacks?

**Simple answer:** I add a strict sliding-window rate limit per IP and per account, and turn on Identity lockout. I use the same error message for every failure, add MFA and breached-password checks, and alert on spikes. Because the built-in limiter is per instance, I add a gateway limit when there are many servers.

```csharp
o.AddPolicy("login", ctx => RateLimitPartition.GetSlidingWindowLimiter(
    ctx.Connection.RemoteIpAddress?.ToString() ?? "anon",
    _ => new SlidingWindowRateLimiterOptions
    { PermitLimit = 5, Window = TimeSpan.FromMinutes(1), SegmentsPerWindow = 4 }));
```

### Password Hashing

**In simple words:** Never store passwords as plain text or with reversible encryption; store a slow, salted, one-way hash. A salt is a random value per user, so equal passwords give different hashes. "Slow" means each guess costs an attacker real time. Use PBKDF2, bcrypt or Argon2id, ideally through ASP.NET Core Identity's `PasswordHasher`.

**Real-life example:** It is like making a smoothie from fruit. You can make the same smoothie again to compare, but you can never get the fruit back.

**Interview question:** Why is SHA-256 alone not good enough for passwords?

**Simple answer:** SHA-256 is fast, so attackers can test billions of guesses per second, and without a salt they can use precomputed tables. Password hashing needs a unique salt and a work factor that makes each guess slow. I use Identity's `PasswordHasher` (PBKDF2) or Argon2id, and compare hashes in constant time.

### Data Protection API

**In simple words:** The Data Protection API is ASP.NET Core's built-in encryption service for auth cookies, antiforgery tokens and Identity tokens. You can also use `IDataProtector` to protect your own data, like a link that expires. Its keys rotate about every 90 days. With many servers or containers, store the keys in shared storage, or users get logged out after each deploy.

**Real-life example:** All branches of a bank need the same key type for their safe boxes. If each branch has its own key, a box locked in one branch cannot be opened in another.

**Interview question:** Why do users get logged out after each deployment when there are multiple instances?

**Simple answer:** Each instance or new container creates its own Data Protection keys, so it cannot decrypt cookies made by another. I persist the key ring to shared storage, like Blob Storage, Redis or the database, and protect it with Key Vault. I also set the same application name on every instance.

```csharp
builder.Services.AddDataProtection()
    .SetApplicationName("shop")
    .PersistKeysToAzureBlobStorage(blobUri, new DefaultAzureCredential());
```

### OWASP Top 10 (2025) and .NET Mitigations

**In simple words:** The OWASP Top 10 is a well-known list of the biggest web application security risks. In the 2025 list, number one is Broken Access Control, such as a missing `[Authorize]` or seeing other users' orders. Others include security misconfiguration, supply chain failures, cryptographic failures, injection and authentication failures. Each risk has standard .NET fixes, such as policies, parameterised queries and Key Vault.

**Real-life example:** It is like a hospital's list of the ten most common mistakes. Every new doctor learns it, because most accidents come from these few causes.

**Interview question:** How do you secure an ASP.NET Core API?

**Simple answer:** I go layer by layer: HTTPS and HSTS, then OIDC or JWT with short-lived tokens, then a fallback policy, policies and resource checks. Next come DTO validation, parameterised queries, output encoding and a CORS allow-list. Finally, Key Vault for secrets, rate limiting and lockout, plus logging, alerts and dependency scanning.
