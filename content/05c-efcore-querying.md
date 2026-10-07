## Querying with LINQ

### IQueryable, Deferred Execution and Translation

**Definition.** A `DbSet<T>` is an `IQueryable<T>`. Each LINQ operator you chain (`Where`, `OrderBy`, `Select`) only builds an **expression tree**; nothing runs until you *enumerate* — `ToListAsync`, `FirstOrDefaultAsync`, `CountAsync`, `AnyAsync`, `foreach`. At that point the provider translates the whole tree into **one SQL statement**.

**Why it matters.** Where you switch from `IQueryable` (runs in SQL) to `IEnumerable` (runs in memory) decides whether you filter 10 rows in the database or download 10 million rows and filter in C#.

```csharp
// Translated entirely to SQL
var recent = await db.Orders
    .Where(o => o.Status == OrderStatus.Paid && o.OrderDate >= since)
    .OrderByDescending(o => o.OrderDate)
    .Take(20)
    .ToListAsync();
```

```sql
SELECT TOP(@__p_1) [o].[Id], [o].[CustomerId], [o].[OrderDate], [o].[RowVersion],
       [o].[Status], [o].[Total]
FROM [Orders] AS [o]
WHERE [o].[Status] = N'Paid' AND [o].[OrderDate] >= @__since_0
ORDER BY [o].[OrderDate] DESC
```

```csharp
// BUG: AsEnumerable()/ToList() too early — everything after runs in memory
var bad = db.Orders.AsEnumerable()                    // SELECT * FROM Orders  (all rows!)
    .Where(o => o.Status == OrderStatus.Paid)          // filtered in C#
    .Take(20).ToList();

// Inspect the SQL without executing
string sql = db.Orders.Where(o => o.Total > 1000).ToQueryString();
```

| | `IQueryable<T>` | `IEnumerable<T>` |
|---|---|---|
| Runs | In the database (translated) | In memory (LINQ to Objects) |
| Lambdas are | Expression trees | Compiled delegates |
| Any C# method allowed? | Only translatable ones | Yes |
| Use for | Building DB queries | Post-processing loaded data |

### Filtering, Sorting and Client Evaluation

Most operators translate: comparisons, `&&`/`||`, `Contains` on a list (`IN`), `string.StartsWith/Contains/EndsWith` (`LIKE`), `ToLower`, date parts, `Math` functions, `GroupBy` + aggregates, `Any`/`All`, null checks, conditional expressions. EF-specific helpers live on `EF.Functions`:

```csharp
var ids = new[] { 3, 5, 8 };
var q = db.Products
    .Where(p => ids.Contains(p.Id))                          // IN (...) / OPENJSON (version-dependent)
    .Where(p => EF.Functions.Like(p.Name, "%phone%"))        // explicit LIKE with wildcards
    .Where(p => p.Category.Name == "Electronics")            // navigation => JOIN, no Include needed
    .OrderBy(p => p.Price).ThenBy(p => p.Name);              // ThenBy, not a second OrderBy

var sales = await db.Orders                                   // GROUP BY in SQL
    .GroupBy(o => o.Status)
    .Select(g => new { Status = g.Key, Count = g.Count(), Revenue = g.Sum(o => o.Total) })
    .ToListAsync();
```

**Client evaluation rules (EF Core 3.0+).** EF may run *untranslatable* code on the client **only in the final (top-level) `Select`**. Anywhere else — `Where`, `OrderBy`, `GroupBy`, joins — an untranslatable method throws `InvalidOperationException: The LINQ expression ... could not be translated`.

```csharp
static string Mask(string email) => email[..2] + "***";

// OK: custom method in the final projection runs on the client after SQL returns
var list = await db.Customers.Select(c => new { c.Id, Masked = Mask(c.Email) }).ToListAsync();

// THROWS: custom method inside Where cannot be translated
var bad = await db.Customers.Where(c => Mask(c.Email).StartsWith("as")).ToListAsync();
```

:::warn Don't "fix" translation errors with ToList()
Adding `.ToList()` before the failing operator makes the error disappear and silently loads the whole table. Rewrite the predicate with translatable expressions, use `EF.Functions`, a computed column, or raw SQL instead. (EF 2.x evaluated silently on the client — a big reason old apps were slow.)
:::

**EF Core 10 joins.** `LeftJoin` and `RightJoin` are now first-class operators, replacing the old `GroupJoin` + `SelectMany` + `DefaultIfEmpty` pattern:

```csharp
var rows = await db.Customers
    .LeftJoin(db.Orders, c => c.Id, o => o.CustomerId,
              (c, o) => new { c.Name, OrderId = (int?)o!.Id })
    .ToListAsync();
```

## Loading Related Data

### Include, ThenInclude and Filtered Include

**Definition.** `Include` tells EF to load a navigation **in the same query** (eager loading). `ThenInclude` continues down the chain. Since EF Core 5 the included collection can be filtered, ordered and limited (*filtered include*).

```csharp
var order = await db.Orders
    .Include(o => o.Customer)                     // reference -> JOIN
    .Include(o => o.Items)                        // collection
        .ThenInclude(i => i.Product)              // Items -> Product
            .ThenInclude(p => p.Category)         //   -> Category
    .SingleOrDefaultAsync(o => o.Id == orderId);

// Filtered include: only this year's paid orders, newest 5
var customer = await db.Customers
    .Include(c => c.Orders
        .Where(o => o.Status == OrderStatus.Paid && o.OrderDate.Year == 2026)
        .OrderByDescending(o => o.OrderDate)
        .Take(5))
    .SingleAsync(c => c.Id == customerId);
```

```sql
-- Approximate SQL for the first query (single query mode)
SELECT [o].*, [c].*, [s].*
FROM [Orders] AS [o]
INNER JOIN [Customers] AS [c] ON [o].[CustomerId] = [c].[Id]
LEFT JOIN (
    SELECT [i].*, [p].*, [c0].*
    FROM [OrderItems] AS [i]
    INNER JOIN [Products] AS [p] ON [i].[ProductId] = [p].[Id]
    INNER JOIN [Categories] AS [c0] ON [p].[CategoryId] = [c0].[Id]
) AS [s] ON [o].[Id] = [s].[OrderId]
WHERE [o].[Id] = @__orderId_0
ORDER BY [o].[Id], [c].[Id], [s].[Id]
```

:::warn Filtered include + tracking
In a *tracking* query, if the same context already tracks other `Orders` of that customer, the navigation will also contain them (identity resolution fixes them up) — the filter seems ignored. Use filtered includes with `AsNoTracking()` or a fresh context.
:::

### Single Query vs Split Query (Cartesian Explosion)

**Definition.** By default EF loads all includes in **one SQL query** with JOINs. Including **two or more sibling collections** multiplies rows: an order with 50 items and 10 payments returns 500 rows, each repeating the order and customer columns — the **cartesian explosion**. `AsSplitQuery()` instead runs **one query per collection**.

```csharp
var orders = await db.Orders
    .Include(o => o.Items)
    .Include(o => o.Payments)            // second collection => explosion risk
    .Where(o => o.CustomerId == id)
    .AsSplitQuery()
    .ToListAsync();
```

```sql
-- Split query: 3 round trips, no row multiplication
SELECT [o].* FROM [Orders] AS [o] WHERE [o].[CustomerId] = @id ORDER BY [o].[Id];
SELECT [i].*, [o].[Id] FROM [Orders] AS [o]
  INNER JOIN [OrderItems] AS [i] ON [o].[Id] = [i].[OrderId]
  WHERE [o].[CustomerId] = @id ORDER BY [o].[Id];
SELECT [p].*, [o].[Id] FROM [Orders] AS [o]
  INNER JOIN [Payments] AS [p] ON [o].[Id] = [p].[OrderId]
  WHERE [o].[CustomerId] = @id ORDER BY [o].[Id];
```

| | Single query (default) | Split query |
|---|---|---|
| Round trips | 1 | 1 + one per collection include |
| Data duplication | High with multiple collections | None |
| Consistency | One snapshot | Data could change between queries (no snapshot unless serializable/snapshot transaction) |
| Skip/Take with includes | Correct | Needs a **unique, deterministic ORDER BY** |
| Best for | References, one small collection | Several or large collections |

Set it globally with `UseSqlServer(cs, o => o.UseQuerySplittingBehavior(QuerySplittingBehavior.SplitQuery))` and opt back per query with `AsSingleQuery()`. EF logs a warning when a query includes multiple collections without an explicit choice.

## Projection, Paging and Raw SQL

### Projection with Select to DTOs

**Definition.** Projection means selecting **only the columns you need**, shaped directly into a DTO, instead of loading full entities with `Include`. For read endpoints it is usually the single best optimisation.

```csharp
public record OrderSummaryDto(int Id, DateTime OrderDate, string CustomerName,
                              int ItemCount, decimal Total, List<string> ProductNames);

var page = await db.Orders
    .Where(o => o.CustomerId == customerId)
    .OrderByDescending(o => o.OrderDate)
    .Select(o => new OrderSummaryDto(
        o.Id,
        o.OrderDate,
        o.Customer.Name,                                   // JOIN, no Include needed
        o.Items.Count,                                     // COUNT subquery
        o.Items.Sum(i => i.Quantity * i.UnitPrice),
        o.Items.Select(i => i.Product.Name).ToList()))
    .ToListAsync();
```

```sql
SELECT [o].[Id], [o].[OrderDate], [c].[Name],
       (SELECT COUNT(*) FROM [OrderItems] AS [i] WHERE [o].[Id] = [i].[OrderId]),
       (SELECT COALESCE(SUM(CAST([i0].[Quantity] AS decimal(18,2)) * [i0].[UnitPrice]), 0.0)
          FROM [OrderItems] AS [i0] WHERE [o].[Id] = [i0].[OrderId]),
       [s].[Name], [s].[Id]
FROM [Orders] AS [o]
INNER JOIN [Customers] AS [c] ON [o].[CustomerId] = [c].[Id]
LEFT JOIN (SELECT [p].[Name], [i1].[Id], [i1].[OrderId] FROM [OrderItems] AS [i1]
           INNER JOIN [Products] AS [p] ON [i1].[ProductId] = [p].[Id]) AS [s]
       ON [o].[Id] = [s].[OrderId]
WHERE [o].[CustomerId] = @__customerId_0
ORDER BY [o].[OrderDate] DESC, [o].[Id], [c].[Id]
```

Benefits: fewer columns over the wire, no change tracking (DTOs are never tracked), no over-posting/serialisation cycles, and indexes can *cover* the query. `Include` is ignored when you project — you navigate inside `Select` instead. AutoMapper's `ProjectTo<T>()` or Mapperly generate the same kind of expression.

### Pagination: Offset vs Keyset

**Offset paging** (`Skip`/`Take`) is simple and supports "jump to page 37", but the database still reads and discards all skipped rows, so deep pages get slower, and rows shift if data changes between requests.

```csharp
// Offset: always with a deterministic ORDER BY (add the key as tie-breaker)
var items = await db.Products
    .OrderBy(p => p.Name).ThenBy(p => p.Id)
    .Skip((page - 1) * pageSize).Take(pageSize)
    .Select(p => new ProductDto(p.Id, p.Name, p.Price))
    .ToListAsync();
// ORDER BY [p].[Name], [p].[Id] OFFSET @skip ROWS FETCH NEXT @take ROWS ONLY
```

**Keyset (seek) paging** remembers the last row and asks for rows *after* it — uses an index seek, constant speed at any depth, stable under inserts. Ideal for infinite scroll and APIs with a `next` cursor.

```csharp
// Keyset: newest orders first, cursor = (lastDate, lastId)
var next = await db.Orders
    .Where(o => o.OrderDate < lastDate || (o.OrderDate == lastDate && o.Id < lastId))
    .OrderByDescending(o => o.OrderDate).ThenByDescending(o => o.Id)
    .Take(pageSize)
    .Select(o => new { o.Id, o.OrderDate, o.Total })
    .ToListAsync();
// Needs an index on (OrderDate DESC, Id DESC)
```

| | Offset (`Skip/Take`) | Keyset (seek) |
|---|---|---|
| Deep page cost | Grows with offset | Constant |
| Jump to page N | Yes | No (next/previous only) |
| Stable when rows inserted | No (duplicates/skips) | Yes |
| Total count | Often added (`CountAsync`, extra query) | Usually omitted |

:::q How would you implement pagination for an orders API with millions of rows?
Keyset pagination ordered by `(OrderDate, Id)` with a composite index, returning an opaque cursor for the next page — every page is an index seek regardless of depth. If the UI needs page numbers I use `Skip/Take` with a deterministic `OrderBy`, a max page size, and maybe cap how deep users can go. I always project to a DTO and use `AsNoTracking`.
:::

### Raw SQL: FromSql, SqlQuery, ExecuteSql

```csharp
// Entities from raw SQL; composable — EF wraps it as a subquery
var expensive = await db.Products
    .FromSql($"SELECT * FROM Products WHERE Price > {minPrice}")   // parameterised
    .Where(p => !p.IsDeleted)
    .OrderBy(p => p.Price)
    .ToListAsync();

// Stored procedure (not composable: nothing after it can be translated into SQL)
var top = await db.Products.FromSql($"EXEC dbo.GetTopProducts {count}").ToListAsync();

// Unmapped types / scalars (EF 7 scalars, EF 8 any type)
var stats = await db.Database
    .SqlQuery<CategorySales>($"""
        SELECT c.Name AS CategoryName, SUM(i.Quantity * i.UnitPrice) AS Revenue
        FROM OrderItems i JOIN Products p ON p.Id = i.ProductId
        JOIN Categories c ON c.Id = p.CategoryId
        GROUP BY c.Name
        """)
    .ToListAsync();

// Non-query commands
int rows = await db.Database.ExecuteSqlAsync(
    $"UPDATE Products SET Price = Price * 1.05 WHERE CategoryId = {categoryId}");
```

Rules: the SQL for an entity must return all mapped columns with matching names; use `FromSql`/`ExecuteSql` (interpolated, safe) rather than `FromSqlRaw` with concatenation; raw results are tracked like any query unless `AsNoTracking`.

### Bulk Updates and Deletes: ExecuteUpdate / ExecuteDelete

**Definition.** EF Core 7 added set-based `ExecuteUpdateAsync` and `ExecuteDeleteAsync`. They translate a LINQ query **directly into one UPDATE/DELETE statement**, run immediately, and **do not load entities or use the change tracker**.

```csharp
// Raise prices 10% in a category: 1 statement, no entities loaded
int updated = await db.Products
    .Where(p => p.CategoryId == 3 && !p.IsDeleted)
    .ExecuteUpdateAsync(s => s
        .SetProperty(p => p.Price, p => p.Price * 1.10m)
        .SetProperty(p => p.Sku, p => "SALE-" + p.Sku));

// Purge abandoned carts older than 30 days
int deleted = await db.Orders
    .Where(o => o.Status == OrderStatus.Pending && o.OrderDate < DateTime.UtcNow.AddDays(-30))
    .ExecuteDeleteAsync();
```

```sql
UPDATE [p] SET [p].[Price] = [p].[Price] * 1.10, [p].[Sku] = N'SALE-' + [p].[Sku]
FROM [Products] AS [p]
WHERE [p].[CategoryId] = 3 AND [p].[IsDeleted] = CAST(0 AS bit);

DELETE FROM [o] FROM [Orders] AS [o]
WHERE [o].[Status] = N'Pending' AND [o].[OrderDate] < DATEADD(day, -30.0, GETUTCDATE());
```

| | Load + modify + `SaveChanges` | `ExecuteUpdate` / `ExecuteDelete` |
|---|---|---|
| Round trips | SELECT + batched UPDATEs | 1 statement |
| Change tracker | Used | Bypassed — tracked entities become **stale** |
| Interceptors / audit via `SaveChanges` | Run | **Don't run** |
| Concurrency tokens | Checked | Not checked (unless you add them to `Where`) |
| Transaction | Implicit per `SaveChanges` | Its own statement; wrap in an explicit transaction to combine |
| Cascade delete for tracked children | EF handles | Only DB-level `ON DELETE CASCADE` |

EF Core 10 also accepts a regular lambda (not only an expression) in `ExecuteUpdateAsync`, so setters can be added conditionally with ordinary `if` statements.

:::q When would you use ExecuteUpdate instead of SaveChanges?
For set-based changes to many rows — price adjustments, status changes, purges — where loading entities would be wasteful. It runs one SQL statement without tracking. The trade-offs: no `SaveChanges` interceptors or audit hooks, no optimistic concurrency checks, and already-tracked entities aren't updated in memory. For business operations on a single aggregate I still load, modify and `SaveChanges`.
:::
