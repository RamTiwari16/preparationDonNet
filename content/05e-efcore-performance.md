## EF Core Performance

### The N+1 Query Problem

**Definition.** N+1 happens when code runs **1 query** to load a list and then **N more queries**, one per item, to load related data. 100 orders → 101 round trips. Each is fast alone; together they dominate response time and hammer the database.

**Demo.** Two common ways to cause it:

```csharp
// (a) Lazy loading: touching a navigation inside a loop fires a query each time
var orders = await db.Orders.Where(o => o.Status == OrderStatus.Paid).ToListAsync(); // 1 query
foreach (var o in orders)
    Console.WriteLine($"{o.Id}: {o.Customer.Name}, {o.Items.Count} items");       // 2 per order!

// (b) Manual N+1 without lazy loading: a query inside the loop
foreach (var o in orders)
{
    var customer = await db.Customers.FindAsync(o.CustomerId);       // 1 per order
    var itemCount = await db.OrderItems.CountAsync(i => i.OrderId == o.Id); // 1 per order
}
```

```sql
SELECT [o].* FROM [Orders] AS [o] WHERE [o].[Status] = N'Paid';     -- 1
SELECT [c].* FROM [Customers] AS [c] WHERE [c].[Id] = @p0;          -- N
SELECT [i].* FROM [OrderItems] AS [i] WHERE [i].[OrderId] = @p0;    -- N
SELECT [c].* FROM [Customers] AS [c] WHERE [c].[Id] = @p0;
SELECT [i].* FROM [OrderItems] AS [i] WHERE [i].[OrderId] = @p0;
-- ... repeated for every order
```

**How to spot it:** the SQL log shows the same statement repeated with different parameter values; Application Insights dependency view shows dozens of identical SQL calls per request; MiniProfiler flags duplicate queries.

**Fix 1 — Eager loading with `Include`** (when you need entities):

```csharp
var orders = await db.Orders
    .Include(o => o.Customer)
    .Include(o => o.Items)
    .Where(o => o.Status == OrderStatus.Paid)
    .AsNoTracking()
    .ToListAsync();                                   // 1 query (JOINs)
```

**Fix 2 — Projection** (best for read endpoints — only needed columns, aggregates in SQL):

```csharp
var rows = await db.Orders
    .Where(o => o.Status == OrderStatus.Paid)
    .Select(o => new { o.Id, CustomerName = o.Customer.Name, ItemCount = o.Items.Count })
    .ToListAsync();
```

```sql
SELECT [o].[Id], [c].[Name],
       (SELECT COUNT(*) FROM [OrderItems] AS [i] WHERE [o].[Id] = [i].[OrderId])
FROM [Orders] AS [o]
INNER JOIN [Customers] AS [c] ON [o].[CustomerId] = [c].[Id]
WHERE [o].[Status] = N'Paid'
```

**Fix 3 — Batch load / split query** (when data comes from separate queries or collections are large):

```csharp
var orders = await db.Orders.Where(o => o.Status == OrderStatus.Paid).ToListAsync();
var customerIds = orders.Select(o => o.CustomerId).Distinct().ToList();
var customers = await db.Customers
    .Where(c => customerIds.Contains(c.Id))          // ONE query: WHERE Id IN (...)
    .ToDictionaryAsync(c => c.Id);
// 2 queries total, regardless of N. Or: Include(...).AsSplitQuery() for multiple collections.
```

:::q How do you detect and fix N+1 queries in EF Core?
I detect it from the SQL log or APM — the same query repeated with different parameters per request. Fixes: eager load with `Include` when I need the entities, project with `Select` into a DTO for reads (usually best), or batch-load related rows with one `IN` query / split query. I also disable lazy loading in APIs so N+1 can't happen silently.
:::

### Eager vs Lazy vs Explicit Loading

| | Eager | Lazy | Explicit |
|---|---|---|---|
| How | `Include` / `ThenInclude` | Navigation access triggers a query | `Entry(x).Collection(..).LoadAsync()` |
| When loaded | With the main query | On first access | When you call it |
| Setup | None | `Microsoft.EntityFrameworkCore.Proxies`, `UseLazyLoadingProxies()`, **`virtual`** navigations (or inject `ILazyLoader`) | None |
| Round trips | 1 (or 1 per collection with split) | 1 per navigation per entity → **N+1** | 1 per call, under your control |
| Async | Yes | **No** — synchronous I/O on property access | Yes |
| Best for | Known needs, APIs | Desktop/rich clients with long-lived contexts | Conditional loading |

```csharp
// Explicit loading: load only when needed, and you can filter/count without loading
var order = await db.Orders.SingleAsync(o => o.Id == id);
if (includeItems)
    await db.Entry(order).Collection(o => o.Items).LoadAsync();
await db.Entry(order).Reference(o => o.Customer).LoadAsync();

int bigItems = await db.Entry(order).Collection(o => o.Items)
    .Query().Where(i => i.Quantity > 10).CountAsync();     // SQL COUNT, nothing loaded

// Lazy loading setup (shown to explain why we avoid it in APIs)
builder.Services.AddDbContext<ShopContext>(o => o.UseSqlServer(cs).UseLazyLoadingProxies());
public class Order { public virtual Customer Customer { get; set; } = null!; /* ... */ }
```

:::warn Why lazy loading is risky in Web APIs
1. **Silent N+1** — innocent loops and AutoMapper mappings fire hundreds of queries.
2. **Serialisation** — `System.Text.Json` walks every navigation, triggering loads across the whole graph and cycles.
3. **Sync I/O** — loads block a thread-pool thread; no async.
4. **Disposed context** — accessing a navigation after the request scope ends throws.
Prefer eager loading or projections; if lazy loading exists in a legacy app, log SQL and watch for repeats.
:::

### Logging and Inspecting Generated SQL

```csharp
builder.Services.AddDbContext<ShopContext>(o =>
{
    o.UseSqlServer(cs);
    if (builder.Environment.IsDevelopment())
    {
        o.LogTo(Console.WriteLine, [DbLoggerCategory.Database.Command.Name], LogLevel.Information);
        o.EnableSensitiveDataLogging();   // shows parameter VALUES — dev only (PII/secrets!)
        o.EnableDetailedErrors();         // better messages for materialisation errors
    }
});
```

```json
// Or via standard logging configuration (appsettings.Development.json)
"Logging": { "LogLevel": { "Microsoft.EntityFrameworkCore.Database.Command": "Information" } }
```

Other tools: `query.ToQueryString()` for one query; `TagWith("OrdersPage")` adds a comment to the SQL so you can find it in Query Store/Profiler; SQL Server Query Store and execution plans; MiniProfiler; Application Insights dependency tracking; EF logs a warning for slow multi-collection includes and for `First` without `OrderBy`.

### Indexes

**Definition.** EF creates indexes for **foreign keys** automatically; everything else — columns you filter, sort, join or look up by — needs explicit indexes. Indexes speed up reads and cost writes and storage.

```csharp
modelBuilder.Entity<Customer>()
    .HasIndex(c => c.Email).IsUnique();                        // unique lookup

modelBuilder.Entity<Order>()
    .HasIndex(o => new { o.CustomerId, o.OrderDate })          // composite: equality col first
    .IsDescending(false, true)                                 // EF 7+: per-column direction
    .IncludeProperties(o => new { o.Status, o.Total });        // SQL Server covering index

modelBuilder.Entity<Product>()
    .HasIndex(p => p.Sku).IsUnique()
    .HasFilter("[IsDeleted] = 0")                              // filtered: unique among live rows
    .HasDatabaseName("UX_Products_Sku_Active");

// Attribute form (EF 5+): [Index(nameof(Email), IsUnique = true)] on the class
```

```sql
CREATE NONCLUSTERED INDEX [IX_Orders_CustomerId_OrderDate]
    ON [Orders] ([CustomerId], [OrderDate] DESC) INCLUDE ([Status], [Total]);
CREATE UNIQUE INDEX [UX_Products_Sku_Active] ON [Products] ([Sku]) WHERE [IsDeleted] = 0;
```

The covering index above serves "a customer's recent orders with status and total" entirely from the index — no key lookups. Verify with the actual execution plan, not intuition; avoid functions on indexed columns in `Where` (`o.OrderDate.Year == 2026` prevents a seek — use a date range).

### Compiled Queries

**Definition.** EF caches query translation, but every execution still has to hash and look up the expression tree. `EF.CompileAsyncQuery` does that work **once** and returns a delegate — a modest gain for hot, frequently executed queries.

```csharp
public static class CompiledQueries
{
    public static readonly Func<ShopContext, int, Task<Order?>> OrderById =
        EF.CompileAsyncQuery((ShopContext db, int id) =>
            db.Orders.AsNoTracking()
                .Include(o => o.Items)
                .FirstOrDefault(o => o.Id == id));

    public static readonly Func<ShopContext, int, IAsyncEnumerable<Product>> ByCategory =
        EF.CompileAsyncQuery((ShopContext db, int categoryId) =>
            db.Products.AsNoTracking().Where(p => p.CategoryId == categoryId));
}

var order = await CompiledQueries.OrderById(db, 1001);
await foreach (var p in CompiledQueries.ByCategory(db, 3)) { /* ... */ }
```

Use them on proven hot paths after measuring. Bigger wins usually come from projections, indexes and avoiding N+1. (Startup cost of large models is addressed separately by *compiled models*: `dotnet ef dbcontext optimize`.)

### Batching and Bulk Operations

- `SaveChanges` already **batches** inserts/updates/deletes into few round trips (tune `MaxBatchSize`).
- Set-based work → `ExecuteUpdateAsync` / `ExecuteDeleteAsync` (EF 7+) — one statement, no tracking.
- Very large inserts (100k+ rows) → `SqlBulkCopy`, or libraries such as **EFCore.BulkExtensions** (open source), **Entity Framework Extensions** (commercial, Z.EntityFramework), **linq2db.EntityFrameworkCore** (`BulkCopy`).
- Chunk work and `ChangeTracker.Clear()` between chunks to keep memory flat.

### Context Pooling, Resiliency and Async

```csharp
// DbContext pooling: reuse context instances instead of constructing per request
builder.Services.AddDbContextPool<ShopContext>(o => o
    .UseSqlServer(cs, sql => sql.EnableRetryOnFailure(
        maxRetryCount: 5, maxRetryDelay: TimeSpan.FromSeconds(10), errorNumbersToAdd: null)),
    poolSize: 1024);

// Background workers / Blazor Server: a factory, one short-lived context per unit of work
builder.Services.AddPooledDbContextFactory<ShopContext>(o => o.UseSqlServer(cs));
await using var db = await factory.CreateDbContextAsync();
```

- **Pooling** saves allocation/initialisation per request in high-throughput APIs. The context is reset when returned; don't keep per-request state in fields set by the constructor (tenant id) unless you reset it.
- **Connection resiliency** (`EnableRetryOnFailure`) retries transient errors (Azure SQL failovers, throttling). Combine with an execution strategy around explicit transactions.
- **Async everywhere**: `ToListAsync`, `FirstOrDefaultAsync`, `SaveChangesAsync`; never `.Result`/`.Wait()`. Async frees threads, it doesn't make one query faster.
- **One operation at a time per context**: `Task.WhenAll` over the same `DbContext` throws; use separate contexts (factory) for true parallelism.

### Common Query Anti-Patterns

| Anti-pattern | Better |
|---|---|
| `if (await q.CountAsync() > 0)` | `await q.AnyAsync()` — `EXISTS` stops at the first row |
| `CountAsync()` then load the same rows | Load once, use `.Count` of the list |
| `ToListAsync()` then `.Where()` / `.First()` in memory | Filter in the query |
| Loading entities to show 3 columns | `Select` into a DTO |
| `SingleOrDefault` where uniqueness doesn't matter | `FirstOrDefault` (`TOP 1` vs `TOP 2`) |
| Loading all rows to compute a sum | `SumAsync` / `GroupBy` in SQL |
| Unbounded queries (`ToListAsync()` on a table) | Paging with a max page size |
| `Contains` with thousands of IDs | Temp table / TVP / batch the list |

**`Find` vs `FirstOrDefault`.**

| | `FindAsync(key)` | `FirstOrDefaultAsync(x => x.Id == key)` |
|---|---|---|
| Checks change tracker first | **Yes** — no DB hit if already tracked | No, always queries (but returns the tracked instance) |
| Lookup by | Primary key only | Any predicate |
| `Include`, `AsNoTracking`, projection | Not supported | Supported |
| Returns `Added` (unsaved) entities | Yes | No |
| Use when | Fetch by PK for update in a unit of work | Everything else, read queries |

### Repository Pattern over EF Core: the Debate

**Definition.** The repository pattern hides data access behind an interface (`IOrderRepository`). EF Core's `DbSet<T>` is already a repository and `DbContext` is already a unit of work, so wrapping them is a design choice, not a requirement.

| Against a generic repository | For a (specific) repository |
|---|---|
| Duplicates `DbSet`; `IRepository<T>.GetAll()` hides `Include`, projection, `AsNoTracking`, paging | Expresses domain intent: `GetOrderWithItemsAsync`, `GetOverdueOrdersAsync` |
| Returning `IQueryable` leaks EF anyway; returning `IEnumerable` forces loading too much | DDD aggregates: one repository per aggregate root controls consistency boundaries |
| "Swap the ORM" rarely happens | Centralises tricky queries and reuse |
| Mocks of repositories hide translation bugs; test against SQLite/Testcontainers instead | Easy to fake in unit tests of domain/application logic |

**A balanced position:** no *generic* `IRepository<T>` over EF. Use `DbContext` directly in query handlers/read services (CQRS-style), with projections. For the write side of a rich domain use aggregate-specific repositories or the specification pattern. Integration-test data access against a real database.

:::q Is the repository pattern needed with EF Core?
Not as a generic wrapper — `DbSet` already is a repository and `DbContext` a unit of work, and a generic repository usually removes features like projections and `Include` control. I use specific repositories for aggregates when following DDD, and query the context directly with projections for reads. Testability comes from integration tests against a real provider, not from mocking `IRepository<T>`.
:::

:::scenario An orders page takes 6 seconds - how do you investigate?
1. Measure: enable EF command logging / APM; count queries per request and their durations.
2. Many identical queries → **N+1**: replace with projection or `Include`.
3. One huge query with millions of rows returned → **cartesian explosion**: `AsSplitQuery` or project.
4. Columns you don't display → project to a DTO; add `AsNoTracking`.
5. Slow single query → look at the execution plan: missing index on `(CustomerId, OrderDate)`, non-sargable predicate, implicit conversions (`varchar` column vs `nvarchar` parameter — fix with `HasColumnType`/`IsUnicode(false)`).
6. Deep `Skip` → keyset pagination.
7. Re-measure; add caching only after the query is right.
:::

## Quick-fire Q&A

:::q What is DbContext and what lifetime should it have?
`DbContext` is a session with the database: it exposes `DbSet`s, tracks changes and saves them as a unit of work in one transaction. Register it Scoped (one per request); it is not thread-safe, so never share it across threads or put it in a singleton.
:::

:::q Data Annotations or Fluent API?
Fluent API wins on precedence and covers everything (relationships, delete behavior, inheritance, filters, converters); annotations cover a subset but are quick and double as validation. I keep mapping in `IEntityTypeConfiguration<T>` classes loaded with `ApplyConfigurationsFromAssembly`.
:::

:::q How do you deploy migrations safely to production?
Generate an idempotent script or a migration bundle in CI, review it, and run it as a pipeline step before the app rollout — not `Migrate()` on startup from many instances. Changes are backward compatible (expand/contract) so old and new code can run during the deploy.
:::

:::q How do you configure a many-to-many relationship?
With skip navigations on both sides (`HasMany().WithMany()`), EF creates the join table. If the link has data (date, quantity) I add an explicit join entity via `UsingEntity<T>` or model it as two one-to-many relationships.
:::

:::q What does Include do, and when is AsSplitQuery useful?
`Include` eager-loads navigations in the same query using JOINs. With several collection includes the joins multiply rows (cartesian explosion); `AsSplitQuery` runs one query per collection instead, at the cost of extra round trips and no single snapshot.
:::

:::q What is the change tracker and what are the entity states?
It keeps every tracked entity with an original-values snapshot and a state: Detached, Added, Unchanged, Modified or Deleted. `SaveChanges` runs `DetectChanges`, turns states into INSERT/UPDATE/DELETE, then marks everything Unchanged.
:::

:::q When do you use AsNoTracking and AsNoTrackingWithIdentityResolution?
`AsNoTracking` for read-only queries — faster and lighter because no snapshots or identity map. `AsNoTrackingWithIdentityResolution` when a read-only graph repeats the same related entity many times and I want one instance per key without tracking.
:::

:::q What is identity resolution?
Within a tracking context there is only one instance per primary key; querying the same row again returns the existing instance and does not overwrite pending changes. Attaching a second instance with the same key throws.
:::

:::q Update() vs loading and modifying the entity?
`Update` marks every property modified and writes all columns without a SELECT — risky if the payload is partial. Loading and applying changes costs a SELECT but updates only changed columns and lets concurrency tokens work naturally.
:::

:::q How does EF Core handle concurrency conflicts?
Optimistic concurrency: a `rowversion`/concurrency token is added to the UPDATE's WHERE clause; zero affected rows raises `DbUpdateConcurrencyException`. I catch it, reload database values and either retry, merge, or return 409 to the client.
:::

:::q Is SaveChanges transactional?
Yes. Each `SaveChanges` wraps all its commands in one transaction. For several `SaveChanges` calls or mixed raw SQL/`ExecuteUpdate`, I use `BeginTransactionAsync` — inside the execution strategy if retries are enabled.
:::

:::q What is the N+1 problem and how do you fix it?
One query for a list and one extra query per item for related data. Fix with `Include`, projection to DTOs, or batch-loading with a single `IN` query; avoid lazy loading in APIs.
:::

:::q Eager vs lazy vs explicit loading?
Eager loads related data with the main query via `Include`; lazy loads it on first property access through proxies (convenient but N+1-prone and synchronous); explicit loads it on demand with `Entry().Collection().LoadAsync()`.
:::

:::q How do ExecuteUpdate and ExecuteDelete differ from SaveChanges?
They translate the query into a single UPDATE/DELETE executed immediately, without loading or tracking entities — ideal for bulk changes. They skip interceptors and concurrency checks and leave tracked entities stale.
:::

:::q Find vs FirstOrDefault?
`Find` looks up by primary key and returns a tracked entity from memory without a database round trip if it's already tracked. `FirstOrDefault` always queries, accepts any predicate and supports `Include`, `AsNoTracking` and projections.
:::
