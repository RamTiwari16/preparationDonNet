## Design 7: Multi-Tenant Application

Flow from the outline: *Tenant identification, Tenant isolation, Database strategy, Security, Configuration*. Think "one codebase, many customers" (a SaaS HR, CRM or invoicing product).

### 1. Requirements

**Clarifying questions.** Are tenants companies (B2B) with many users each? How many tenants (tens, thousands, hundreds of thousands)? Any regulated customers that demand dedicated databases or data residency? Custom domains and branding? Different plans (free/pro/enterprise) with different limits and features? Do tenants need their own backups or exports?

**Functional**
- Tenant onboarding/provisioning, suspension, deletion.
- Tenant identification on every request; users belong to a tenant.
- Complete data isolation between tenants.
- Per-tenant configuration: branding, feature flags, limits, integrations.
- Per-plan quotas and rate limits; usage metering for billing.

**Non-functional:** zero cross-tenant data leakage (the single worst bug a SaaS can have); noisy-neighbour protection; fast onboarding (minutes, automated); cost-efficient for small tenants; the option to give big customers dedicated resources.

### 2. Capacity estimation (illustrative)

- 5,000 tenants, 500K users in total, power-law distribution: the top 1% of tenants produce ~50% of the load.
- 500 QPS average, 2,500 QPS peak.
- Data per tenant: 100 MB (small) to 50 GB (large). Total ~5-10 TB.
- Conclusion: **pooled infrastructure for the long tail, dedicated resources for the few huge or regulated tenants.** One model rarely fits all.

### 3. API design

The tenant is never a normal request parameter the caller can freely choose. It is derived from the host, the token, or a trusted gateway header.

```json
// GET https://acme.app.example.com/api/v1/invoices?page=1      (tenant = "acme" from host)
// Authorization: Bearer <JWT with claim "tid": "t-1001">
{ "tenantId": "t-1001", "items": [ { "id": 981, "number": "INV-2026-0981", "total": 1200.00 } ] }

// GET /api/v1/tenant/settings
{ "tenantId": "t-1001", "plan": "pro", "branding": { "primaryColor": "#0b5fff", "logoUrl": "..." },
  "features": { "advancedReports": true, "sso": false }, "limits": { "rpm": 600, "seats": 50 } }

// PUT /api/v1/tenant/settings   (tenant admin only)
// POST /api/v1/admin/tenants    (platform admin: provisioning)
{ "name": "Acme Ltd", "slug": "acme", "plan": "pro", "isolation": "shared", "region": "centralindia" }
```

### 4. Data model

A small **tenant catalog** (control plane) tells the app how to reach each tenant's data (data plane).

```sql
-- Catalog DB (control plane)
CREATE TABLE Tenants (
  TenantId       NVARCHAR(20) PRIMARY KEY,
  Slug           NVARCHAR(60) NOT NULL UNIQUE,            -- subdomain
  Name           NVARCHAR(200) NOT NULL,
  Plan           TINYINT NOT NULL, Status TINYINT NOT NULL,   -- Active, Suspended, Deleted
  IsolationModel TINYINT NOT NULL,                        -- 0 Shared, 1 Schema, 2 Database
  ConnectionRef  NVARCHAR(200) NULL,                      -- Key Vault secret name, not the secret
  Region NVARCHAR(30), CreatedAtUtc DATETIME2
);
CREATE TABLE TenantDomains (Host NVARCHAR(253) PRIMARY KEY, TenantId NVARCHAR(20));
CREATE TABLE TenantSettings (TenantId NVARCHAR(20), [Key] NVARCHAR(100), Value NVARCHAR(MAX),
  PRIMARY KEY (TenantId, [Key]));

-- Data plane (shared model): every business table carries TenantId, and every index leads with it
CREATE TABLE Invoices (
  TenantId NVARCHAR(20) NOT NULL, InvoiceId BIGINT NOT NULL, Number NVARCHAR(30),
  Total DECIMAL(18,2), CreatedAtUtc DATETIME2,
  CONSTRAINT PK_Invoices PRIMARY KEY (TenantId, InvoiceId)       -- clustered: tenant data is contiguous
);
CREATE INDEX IX_Invoices_Date ON Invoices (TenantId, CreatedAtUtc DESC);
```

### 5. High-level architecture

```text
 acme.app.com / globex.app.com / custom domain
              |
      Azure Front Door (TLS, WAF, custom domains)
              |
        ASP.NET Core API (stateless, same code for all tenants)
              |
   [1] TenantResolutionMiddleware  host/header/claim -> TenantInfo  (cached catalog lookup)
   [2] Authentication: JWT "tid" claim must match resolved tenant
   [3] Per-tenant rate limiter (partitioned by TenantId + plan)
   [4] ITenantContext (scoped) -> DbContext (query filter) / settings / feature flags
              |
   +----------+-----------------------+------------------------------+
   |  Shared DB, shared schema        |  Schema per tenant           |  DB per tenant
   |  (TenantId column + RLS)         |  (acme.Invoices)             |  (Azure SQL Elastic Pool)
   +----------------------------------+------------------------------+
   Tenant catalog DB  |  Redis (keys prefixed by tenant)  |  Blob (container per tenant)
   Background jobs & queues carry TenantId in every message
```

### 6. Deep dives

#### 6a. Tenant identification (resolution middleware)

| Source | Example | Use for | Risk |
|---|---|---|---|
| Subdomain / host | `acme.app.com` | Browser-facing apps, custom domains | Must map host to tenant via catalog; wildcard certs |
| JWT claim | `tid: t-1001` | **Authoritative** for authenticated calls | Token must be issued per tenant membership |
| Header | `X-Tenant-Id` | Service-to-service, mobile SDKs, gateways | A public client can forge it. Accept only from trusted callers, or cross-check with the claim |
| Route/path | `/t/acme/...` | Simple APIs | Easy to leak into caches and logs; same cross-check needed |

**Golden rule:** resolve the tenant, then **verify the authenticated user belongs to it**. If the host says `acme` and the token says `globex`, reject with 403.

```csharp
public interface ITenantContext
{
    TenantInfo Tenant { get; }
    bool IsResolved { get; }
}

public sealed record TenantInfo(string Id, string Slug, TenantPlan Plan,
                                IsolationModel Isolation, string? ConnectionRef);

public sealed class TenantContext : ITenantContext
{
    public TenantInfo? Current { get; set; }
    public TenantInfo Tenant => Current ?? throw new InvalidOperationException("No tenant");
    public bool IsResolved => Current is not null;
}

public sealed class TenantResolutionMiddleware(RequestDelegate next)
{
    public async Task InvokeAsync(HttpContext ctx, ITenantStore store, TenantContext tenantCtx)
    {
        string? slug = null;
        var host = ctx.Request.Host.Host;                         // acme.app.example.com
        if (host.EndsWith(".app.example.com", StringComparison.OrdinalIgnoreCase))
            slug = host[..host.IndexOf('.')];
        else
            slug = (await store.FindByCustomDomainAsync(host))?.Slug;   // vanity domain

        // Trusted gateway header only (never from the open internet)
        if (slug is null && ctx.Request.Headers.TryGetValue("X-Tenant-Slug", out var h)
            && ctx.Connection.RemoteIpAddress is { } ip && TrustedProxies.Contains(ip))
            slug = h.ToString();

        if (slug is null) { ctx.Response.StatusCode = 400; return; }

        var tenant = await store.FindBySlugAsync(slug);           // IMemoryCache, 5 min
        if (tenant is null || tenant.Status != TenantStatus.Active)
        { ctx.Response.StatusCode = 404; return; }                // do not reveal why

        tenantCtx.Current = tenant;
        using (LogContext.PushProperty("TenantId", tenant.Id))    // every log line gets it
            await next(ctx);
    }
}

// After UseAuthentication: cross-check the claim
app.Use(async (ctx, next) =>
{
    var tenant = ctx.RequestServices.GetRequiredService<ITenantContext>().Tenant;
    var claim = ctx.User.FindFirst("tid")?.Value;
    if (ctx.User.Identity?.IsAuthenticated == true && claim != tenant.Id)
    { ctx.Response.StatusCode = StatusCodes.Status403Forbidden; return; }
    await next(ctx);
});

// Registration
builder.Services.AddScoped<TenantContext>();
builder.Services.AddScoped<ITenantContext>(sp => sp.GetRequiredService<TenantContext>());
```

#### 6b. Tenant isolation in EF Core: global query filter

Add `TenantId` to every tenant-owned entity, filter reads automatically, stamp writes automatically.

```csharp
public interface ITenantEntity { string TenantId { get; set; } }

public class Invoice : ITenantEntity
{
    public string TenantId { get; set; } = default!;
    public long InvoiceId { get; set; }
    public string Number { get; set; } = default!;
    public decimal Total { get; set; }
}

public sealed class AppDbContext(DbContextOptions<AppDbContext> options, ITenantContext tenant)
    : DbContext(options)
{
    // A property on the context: EF parameterises it per context instance, so the compiled
    // query is cached once and the value is substituted each time.
    private string CurrentTenantId => tenant.Tenant.Id;
    public DbSet<Invoice> Invoices => Set<Invoice>();

    protected override void OnModelCreating(ModelBuilder mb)
    {
        mb.Entity<Invoice>().HasKey(i => new { i.TenantId, i.InvoiceId });
        foreach (var et in mb.Model.GetEntityTypes()
                     .Where(t => typeof(ITenantEntity).IsAssignableFrom(t.ClrType)))
        {
            var p = Expression.Parameter(et.ClrType, "e");
            var body = Expression.Equal(
                Expression.Property(p, nameof(ITenantEntity.TenantId)),
                Expression.Property(Expression.Constant(this), nameof(CurrentTenantId)));
            mb.Entity(et.ClrType).HasQueryFilter(Expression.Lambda(body, p));
        }
    }

    public override Task<int> SaveChangesAsync(CancellationToken ct = default)
    {
        foreach (var entry in ChangeTracker.Entries<ITenantEntity>())
        {
            if (entry.State == EntityState.Added) entry.Entity.TenantId = CurrentTenantId;
            else if (entry.State is EntityState.Modified or EntityState.Deleted
                     && entry.Entity.TenantId != CurrentTenantId)
                throw new InvalidOperationException("Cross-tenant write blocked");
        }
        return base.SaveChangesAsync(ct);
    }
}
```

A simpler, commonly shown form for one entity: `modelBuilder.Entity<Invoice>().HasQueryFilter(i => i.TenantId == _tenantId);` where `_tenantId` is a field/property of the context. Both work because EF treats the context member as a parameter.

:::warn Filters are not a security boundary on their own
`IgnoreQueryFilters()`, raw SQL (`FromSqlRaw`, `ExecuteSqlRaw`), `ExecuteDelete`-style bulk SQL written by hand, and Dapper bypass the filter. Add **defence in depth**: SQL Server/Azure SQL **Row-Level Security** driven by `SESSION_CONTEXT`, plus tests that prove tenant A cannot read tenant B. Also remember that with `AddDbContextPool` a pooled context is reused across requests, so tenant state must be set per lease (use a pooled factory and set the tenant on each leased context) or skip pooling.
:::

```sql
-- Row-Level Security: the database itself enforces tenant isolation
CREATE FUNCTION Security.fn_TenantFilter(@TenantId NVARCHAR(20))
RETURNS TABLE WITH SCHEMABINDING AS
  RETURN SELECT 1 AS ok WHERE @TenantId = CAST(SESSION_CONTEXT(N'TenantId') AS NVARCHAR(20));

CREATE SECURITY POLICY Security.TenantPolicy
  ADD FILTER PREDICATE Security.fn_TenantFilter(TenantId) ON dbo.Invoices,
  ADD BLOCK  PREDICATE Security.fn_TenantFilter(TenantId) ON dbo.Invoices AFTER INSERT
  WITH (STATE = ON);
```

```csharp
// Set it when a connection is opened (EF Core DbConnectionInterceptor)
public sealed class TenantSessionInterceptor(ITenantContext tenant) : DbConnectionInterceptor
{
    public override async Task ConnectionOpenedAsync(DbConnection conn,
        ConnectionEndEventData e, CancellationToken ct = default)
    {
        await using var cmd = conn.CreateCommand();
        cmd.CommandText = "EXEC sp_set_session_context @key=N'TenantId', @value=@t";
        var p = cmd.CreateParameter(); p.ParameterName = "@t"; p.Value = tenant.Tenant.Id;
        cmd.Parameters.Add(p);
        await cmd.ExecuteNonQueryAsync(ct);
    }
}
```

#### 6c. Three isolation models

| | Shared DB, shared schema | Schema per tenant | Database per tenant |
|---|---|---|---|
| How | One set of tables, `TenantId` column | One DB, a schema per tenant (`acme.Invoices`) | A dedicated database per tenant |
| Isolation strength | Logical only (bugs leak data) | Better (permissions per schema) but same DB | Strongest; separate credentials/encryption keys possible |
| Cost per tenant | Lowest | Low-medium | Highest (mitigate with Azure SQL **elastic pools**) |
| Noisy neighbour | High risk | Medium | Low (per-DB limits) |
| Onboarding | Insert a row (seconds) | Create schema + objects | Provision DB (minutes) |
| Schema migrations | Once | N schemas | N databases (needs a runner, canary rollout) |
| Backup/restore one tenant | Hard (filter and extract) | Hard | Easy (restore one DB) |
| Scale limits | One DB ceiling; shard later | Object-count limits at thousands of schemas | Thousands of DBs fine with elastic pools; ops tooling needed |
| Fit | Long tail, small tenants, free tier | Rare; middle ground | Enterprise, regulated, big data volume |

Typical answer: **hybrid**. Pool small tenants in shared databases (maybe several shards), put enterprise tenants in dedicated databases, and let the *tenant catalog* hold `IsolationModel` + `ConnectionRef` so the same code serves all.

```csharp
// Database-per-tenant: connection chosen per request from the catalog
public sealed class TenantDbContextFactory(ITenantContext tenant, ISecretStore secrets,
    IConfiguration cfg)
{
    public async Task<AppDbContext> CreateAsync()
    {
        string cs = tenant.Tenant.Isolation == IsolationModel.Database
            ? await secrets.GetAsync(tenant.Tenant.ConnectionRef!)       // Key Vault, cached
            : cfg.GetConnectionString("SharedPool")!;
        var options = new DbContextOptionsBuilder<AppDbContext>().UseSqlServer(cs).Options;
        return new AppDbContext(options, tenant);
    }
}
// Migrations: a runner iterates the catalog and calls Database.MigrateAsync() per tenant DB,
// canary tenants first, tracking version per tenant in the catalog.
```

#### 6d. Per-tenant configuration

Keep settings in the catalog (key/value or JSON), cache them, and expose them through one abstraction. Feature flags can be plan-driven.

```csharp
public sealed class TenantSettingsProvider(ITenantContext tenant, IMemoryCache cache, ITenantStore store)
{
    public async Task<T> GetAsync<T>(string key, T fallback) =>
        (await cache.GetOrCreateAsync($"ts:{tenant.Tenant.Id}:{key}", async e =>
        {
            e.AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(5);
            var raw = await store.GetSettingAsync(tenant.Tenant.Id, key);
            return raw is null ? fallback : JsonSerializer.Deserialize<T>(raw)!;
        }))!;
}
// Usage: bool sso = await settings.GetAsync("features.sso", false);
```

:::warn Cache keys must include the tenant
`cache.Set("invoices:981", ...)` is a classic data-leak bug: tenant B reads tenant A's cached invoice 981. Prefix **every** cache key (Redis, MemoryCache, output cache vary-by) with the tenant id, and apply the same rule to blob paths, queue messages and search indexes.
:::

#### 6e. Per-tenant rate limits and noisy neighbours

One tenant running a heavy export must not slow everyone else. Defences: per-tenant rate limiting, per-tenant concurrency caps, queue fairness, resource governance in the DB, and moving heavy tenants to dedicated capacity.

```csharp
builder.Services.AddRateLimiter(o =>
{
    o.RejectionStatusCode = StatusCodes.Status429TooManyRequests;
    o.GlobalLimiter = PartitionedRateLimiter.Create<HttpContext, string>(ctx =>
    {
        var t = ctx.RequestServices.GetRequiredService<ITenantContext>().Tenant;
        int perMinute = t.Plan switch { TenantPlan.Free => 60, TenantPlan.Pro => 600, _ => 6000 };
        return RateLimitPartition.GetTokenBucketLimiter(t.Id, _ => new TokenBucketRateLimiterOptions
        {
            TokenLimit = perMinute, TokensPerPeriod = perMinute,
            ReplenishmentPeriod = TimeSpan.FromMinutes(1), QueueLimit = 0, AutoReplenishment = true
        });
    });
});
// app.UseRateLimiter() must come AFTER the tenant middleware so the tenant is known.
```

| Noisy-neighbour layer | Technique |
|---|---|
| API | Token bucket per tenant; concurrency limiter per tenant; separate limits for expensive endpoints (exports, reports) |
| Queues/jobs | Per-tenant sub-queues or fair scheduling; max concurrent jobs per tenant; heavy work off the request path |
| Database | Elastic pool with per-DB min/max; Resource Governor; query timeouts; indexes that lead with `TenantId` |
| Cache/storage | Per-tenant quotas; key prefixes; container per tenant |
| Architecture | Deployment **stamps/cells**: groups of tenants share a full copy of the stack, a failure or a hot tenant affects only its cell |

Per-tenant metrics (requests, DB time, errors by `TenantId` dimension) are what let you *find* the noisy tenant; see the Observability section.

#### 6f. Security checklist

- Resolve tenant from a trusted source and cross-check with the token claim; deny by default.
- Query filter + stamping + RLS + automated tests that create two tenants and assert zero overlap on every endpoint.
- Background jobs and message handlers carry `TenantId` explicitly; set `ITenantContext` before touching data.
- Per-tenant encryption keys (customer-managed keys) for enterprise tiers; separate Blob container and SAS scope per tenant.
- Admin/support access is audited and time-boxed; "impersonate tenant" is a logged privileged action.
- Offboarding: soft delete, export, then hard delete across DB, blobs, caches, search and backups according to policy.

### 7. Scaling, failure modes, trade-offs

- **Catalog is critical:** cache aggressively, keep a read replica, and make the app survive a catalog outage using stale cached entries.
- **Shard map:** `TenantId -> (database, region, cell)` lets you rebalance and move a hot tenant to its own database with a tenant-level migration (copy, cut over, verify).
- **Data residency:** place a tenant's data in its required region; route by `Region` in the catalog.
- **Trade-off:** shared model = cheapest and simplest to operate but highest blast radius; database-per-tenant = strongest isolation but heaviest on operations. A senior answer names *both* and explains the hybrid.

:::tip How to present this in 45 minutes
Open with "control plane vs data plane" and the three isolation models table. Deep-dive tenant resolution + EF filter + RLS defence in depth, then noisy neighbours. Closing line: "The worst failure mode is a cross-tenant data leak, so I test for it explicitly."
:::

:::q Follow-up 1: A tenant on the shared model grows huge and slows others. What do you do?
Short term: tighten their rate limits and move their heavy jobs to a throttled queue. Long term: migrate that tenant to a dedicated database using the catalog's `IsolationModel`/`ConnectionRef` (copy data, cut over during a maintenance window, verify, update catalog). The application code does not change.
:::

:::q Follow-up 2: How do you run schema migrations across 2,000 tenant databases?
A migration runner reads the catalog and applies migrations per database in batches with parallelism limits, canary tenants first. Track `SchemaVersion` per tenant, keep migrations backward compatible (expand/contract) so old and new app versions work during rollout, and alert on failures without blocking the whole fleet.
:::

:::q Follow-up 3: How would you let a tenant bring their own identity provider (SSO)?
Store per-tenant IdP configuration (authority, client id, metadata) in the catalog. The login flow resolves the tenant first (from host or email domain), then redirects to that tenant's IdP via a dynamic authentication scheme; the returned token is mapped to a tenant user and issued with `tid`. Microsoft Entra multi-tenant apps and `OpenIdConnect` with per-tenant options are the building blocks.
:::

## Quick-fire Q&A

:::q What are the steps of a system design interview, in order?
Clarify requirements (functional and non-functional), estimate capacity, define the API, design the data model, draw the high-level architecture, deep-dive the 2 hardest parts, then discuss scaling, failure modes and trade-offs. Say your assumptions out loud at every step.
:::

:::q How do you estimate QPS and storage quickly?
QPS = requests per day / 86,400 (round to 100K), then multiply by 3-10 for peak. Storage = records per day x size per record x retention. Do the multiplication on the board, label the result as an assumption, and conclude something from it (for example "reads dominate, so cache").
:::

:::q SQL or NoSQL for a new design?
Choose from access patterns. Relational data with transactions and joins (orders, payments, ledger) fits SQL. Huge write volume, key or partition-based access and flexible shape (chat messages, click events, URL mappings) fits NoSQL. Many systems use both: SQL as the system of record plus Redis, a search index and a NoSQL store for specific workloads.
:::

:::q Why put a message queue in so many of these designs?
It decouples producers from consumers, absorbs spikes, lets consumers retry at their own pace, and gives you a dead-letter queue for poison messages. The price is eventual consistency, duplicate delivery (design consumers to be idempotent), and ordering concerns.
:::

:::q Explain idempotency in one minute.
An operation is idempotent if doing it twice has the same effect as once. For non-idempotent actions like "charge a card" the client sends a unique idempotency key; the server stores the key with the response and replays it on duplicates. Consumers also dedupe by message id. It is what makes retries safe.
:::

:::q How do you prevent overselling in an e-commerce checkout?
Make the stock check and the decrement one atomic operation: `UPDATE ... WHERE OnHand - Reserved >= qty` and check rows affected, or use optimistic concurrency with a `rowversion` and retry. Add time-limited reservations and a saga so a failed payment releases stock.
:::

:::q 301 or 302 for a URL shortener?
301 is cached by browsers, which reduces load but loses analytics and makes edits/expiry ineffective. 302 hits our server every time, so we can count clicks and change or expire links. 302 is the safe default; use 301 only for immutable links where offload matters more.
:::

:::q How does a SignalR chat scale to many servers?
Add a backplane (Redis) or use Azure SignalR Service so a message sent via one server reaches clients connected to any other. Keep the hub stateless, persist messages before broadcasting, order with a per-conversation sequence, and use client-generated ids to dedupe retries.
:::

:::q Why not upload files through your API?
It wastes API threads, memory and bandwidth and makes large uploads fragile. The API authorises the user and issues a short-lived SAS URL, the client uploads blocks straight to Blob Storage, and an event triggers virus scanning and status updates.
:::

:::q Strong vs eventual consistency: where do you use each?
Strong consistency inside a service for money and stock (payments, ledger, inventory decrement). Eventual consistency across services and read models (search index, notifications, analytics, caches). Say which boundary each choice lives on.
:::

:::q What is the cache-aside pattern and what can go wrong?
The app reads the cache first, loads from the database on a miss, then fills the cache. Risks: stale data (use TTL and invalidate on writes), cache stampede on a hot key expiry (single-flight lock or early refresh), and cache penetration for non-existent keys (negative caching or a Bloom filter).
:::

:::q How do you make a distributed call safe?
Timeout, retry with exponential backoff and jitter on transient errors only, circuit breaker to stop hammering a failing dependency, bulkheads to isolate resources, idempotency keys so retries are harmless, and a fallback or queue when the dependency is down.
:::

:::q Name the multi-tenant isolation models and when you would pick each.
Shared database with a `TenantId` column for many small tenants and lowest cost; schema per tenant as a middle ground (rarely chosen); database per tenant for large, regulated or noisy tenants. A hybrid driven by a tenant catalog is the usual real-world answer.
:::

:::q What do you do when you do not know part of a design question?
Say so, state an assumption, and reason from first principles ("I have not used Kafka in production; I would pick Service Bus here because we need DLQ and sessions, and here is how Kafka would differ"). Interviewers reward structured thinking and honesty over bluffing.
:::
