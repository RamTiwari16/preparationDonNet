## Change Tracking (very important)

### What the Change Tracker Is

**Definition.** The **change tracker** is the part of `DbContext` that remembers every entity instance the context knows about, its **state**, and a **snapshot of its original values**. On `SaveChanges`, EF compares current values to the snapshot (`DetectChanges`) and generates INSERT/UPDATE/DELETE statements only for what changed.

**Why it matters.** Tracking is what makes "load, change a property, `SaveChanges`" work with no `Update` call. It also costs memory and CPU for every tracked entity. Knowing when to turn it off (read-only queries) and how it behaves with disconnected entities (Web API PUT) is one of the most asked EF topics.

### Entity States, Walkthrough

| State | Meaning | On `SaveChanges` |
|---|---|---|
| `Detached` | Context doesn't know the entity | Nothing |
| `Added` | New, to be inserted | `INSERT` → then `Unchanged` |
| `Unchanged` | Tracked, same as DB snapshot | Nothing |
| `Modified` | Tracked, one or more properties changed | `UPDATE` of **modified columns** → `Unchanged` |
| `Deleted` | Tracked, marked for removal | `DELETE` → then `Detached` |

```csharp
await using var db = new ShopContext(options);

var tag = new Tag { Name = "eco" };
Console.WriteLine(db.Entry(tag).State);          // Output: Detached

db.Tags.Add(tag);
Console.WriteLine(db.Entry(tag).State);          // Output: Added
await db.SaveChangesAsync();                     // INSERT INTO [Tags] ... OUTPUT INSERTED.[Id]
Console.WriteLine($"{db.Entry(tag).State} {tag.Id}"); // Output: Unchanged 12

var product = await db.Products.FirstAsync(p => p.Id == 7);
Console.WriteLine(db.Entry(product).State);      // Output: Unchanged

product.Price = 899m;                            // plain property set, no EF call
Console.WriteLine(db.Entry(product).State);      // Output: Modified  (Entry() runs DetectChanges)
Console.WriteLine(db.Entry(product).Property(p => p.Price).IsModified); // Output: True
Console.WriteLine(db.Entry(product).Property(p => p.Name).IsModified);  // Output: False
Console.WriteLine(db.Entry(product).Property(p => p.Price).OriginalValue); // Output: 949.00

await db.SaveChangesAsync();                     // UPDATE [Products] SET [Price] = @p0 WHERE [Id] = @p1
Console.WriteLine(db.Entry(product).State);      // Output: Unchanged

db.Tags.Remove(tag);
Console.WriteLine(db.Entry(tag).State);          // Output: Deleted
await db.SaveChangesAsync();                     // DELETE FROM [Tags] WHERE [Id] = @p0
Console.WriteLine(db.Entry(tag).State);          // Output: Detached

Console.WriteLine(db.ChangeTracker.DebugView.LongView); // dump everything tracked
```

```sql
-- Only the changed column is updated
SET NOCOUNT ON;
UPDATE [Products] SET [Price] = @p0
OUTPUT 1
WHERE [Id] = @p1;
```

### Identity Resolution

**Definition.** A tracking context guarantees **one instance per primary key**. Query the same row twice and you get the same object back; navigations between tracked entities are wired up automatically (*fix-up*).

```csharp
var a = await db.Products.FirstAsync(p => p.Id == 7);
var b = await db.Products.FirstAsync(p => p.Id == 7);   // still runs SQL...
Console.WriteLine(ReferenceEquals(a, b));               // Output: True  (...but returns the tracked instance)

var c = await db.Products.AsNoTracking().FirstAsync(p => p.Id == 7);
Console.WriteLine(ReferenceEquals(a, c));               // Output: False
```

Consequences: a tracking query **does not overwrite** in-memory changes with DB values (the tracked instance wins); and attaching a second instance with the same key throws *"The instance of entity type 'Product' cannot be tracked because another instance with the key value '{Id: 7}' is already being tracked"*.

### DetectChanges and Its Cost

`DetectChanges` walks **every tracked entity** and compares each property to its snapshot. It runs automatically on `SaveChanges`, `Entry()`, `Entries()`, local queries and some other calls. With thousands of tracked entities this becomes O(n) work, repeated. Mitigations:

```csharp
// Large inserts: avoid repeated scans, save in batches, then clear the tracker
db.ChangeTracker.AutoDetectChangesEnabled = false;
foreach (var chunk in products.Chunk(1000))
{
    db.Products.AddRange(chunk);
    await db.SaveChangesAsync();       // SaveChanges still calls DetectChanges once
    db.ChangeTracker.Clear();          // keep the tracker small (EF 5+)
}
db.ChangeTracker.AutoDetectChangesEnabled = true;
```

For truly bulk loads use `ExecuteUpdate/Delete`, `SqlBulkCopy` or a bulk library rather than the tracker.

### AsNoTracking, AsNoTrackingWithIdentityResolution, AsTracking

```csharp
// Read-only: no snapshot, no identity map -> faster, less memory
var list = await db.Products.AsNoTracking()
    .Include(p => p.Category)
    .ToListAsync();

// No tracking BUT de-duplicate instances within this query result
var orders = await db.Orders.AsNoTrackingWithIdentityResolution()
    .Include(o => o.Customer)              // 100 orders of 3 customers -> 3 Customer objects
    .ToListAsync();

// Make no-tracking the context default; opt in where you write
builder.Services.AddDbContext<ShopContext>(o => o
    .UseSqlServer(cs)
    .UseQueryTrackingBehavior(QueryTrackingBehavior.NoTracking));

var toEdit = await db.Products.AsTracking().FirstAsync(p => p.Id == 7);
// Or per instance: db.ChangeTracker.QueryTrackingBehavior = QueryTrackingBehavior.TrackAll;
```

| | Tracking (default) | `AsNoTracking()` | `AsNoTrackingWithIdentityResolution()` |
|---|---|---|---|
| Snapshot + change detection | Yes | No | No |
| Same row → same instance | Yes (across the context) | **No** — duplicates per row | Yes, within this query only |
| `SaveChanges` sees edits | Yes | No | No |
| Speed / memory | Baseline | Fastest | Between (temporary identity map) |
| Typical use | Read-modify-write | Lists, DTO queries, reports | Large no-tracking graph with many shared references |

Projections to DTOs/anonymous types are never tracked anyway — but **entities inside a projection are** (`Select(o => new { o, o.Customer })` tracks both) unless the query is no-tracking.

### When to Use Tracking vs AsNoTracking

| Scenario | Choice | Why |
|---|---|---|
| GET list / details endpoint returning DTOs | `Select` projection (or `AsNoTracking`) | Nothing to save; cheaper |
| Report, export, dashboard | `AsNoTracking` + projection | Large result sets |
| Load → change → `SaveChanges` in same request | **Tracking** | Change detection writes only changed columns |
| Domain command with business rules on an aggregate | **Tracking** | Load aggregate, call methods, save |
| Lookup data cached in memory | `AsNoTracking` | Must not be tied to a context |
| Big graph with repeated references, read-only | `AsNoTrackingWithIdentityResolution` | Avoid duplicate objects |
| Set-based update of many rows | `ExecuteUpdate` | No tracking at all |

:::tip What interviewers want to hear
"Reads use projections or `AsNoTracking`; writes use tracking. In read-heavy APIs I sometimes make NoTracking the context default and opt in with `AsTracking()` in command handlers."
:::

### Disconnected Entities: Update() vs Attach() vs Modifying a Tracked Entity

**Context.** In a Web API the entity arrives in the request body — it was *not* loaded by this context (it is `Detached`). You have three main options, and they generate different SQL.

```csharp
// PUT /products/7  body: { "id": 7, "name": "Phone X", "price": 899, ... }

// Option 1: load, apply, save  (recommended for most updates)
var product = await db.Products.FindAsync(dto.Id);
if (product is null) return Results.NotFound();
db.Entry(product).CurrentValues.SetValues(dto);   // copies matching property names
await db.SaveChangesAsync();
// SELECT ... ; UPDATE Products SET Price = @p0 WHERE Id = @p1   -- only changed columns

// Option 2: Update() — no SELECT, marks ALL properties Modified
db.Products.Update(new Product { Id = dto.Id, Name = dto.Name, Price = dto.Price });
await db.SaveChangesAsync();
// UPDATE Products SET Name=@p0, Price=@p1, Sku=@p2, CategoryId=@p3, IsDeleted=@p4 WHERE Id=@p5
// Any property you didn't set (Sku = "") overwrites the DB value!

// Option 3: Attach() + mark specific properties — partial update, no SELECT
var stub = new Product { Id = dto.Id, Price = dto.Price };
db.Products.Attach(stub);                               // state: Unchanged
db.Entry(stub).Property(p => p.Price).IsModified = true;
await db.SaveChangesAsync();
// UPDATE Products SET Price = @p0 WHERE Id = @p1
```

| | Load + modify (tracked) | `Update(entity)` | `Attach` + `IsModified` | `ExecuteUpdate` |
|---|---|---|---|---|
| Extra SELECT | Yes | No | No | No |
| Columns updated | Only changed ones | **All** | Only flagged ones | Ones you set |
| Risk | Extra round trip | Overwrites with defaults; over-posting | Must flag correctly | Bypasses tracker/interceptors |
| Concurrency token | From DB (or set original) | Uses value you supply | Uses value you supply | Manual |
| Graph behaviour | — | Traverses: key set → Modified, key default → **Added** | Traverses: key set → Unchanged, default → Added | — |

`Update` on an entity whose key doesn't exist produces 0 affected rows → `DbUpdateConcurrencyException`. `db.Entry(entity).State = EntityState.Modified` is like `Update` but does **not** traverse the graph.

:::q What is the difference between Update() and Attach()?
`Attach` starts tracking the entity as `Unchanged` (or `Added` if its key is unset), so nothing is written unless you change or flag properties afterwards — good for partial updates. `Update` starts tracking it as `Modified` with every property marked, so `SaveChanges` updates all columns without first reading the row — anything the client didn't send gets overwritten. Both traverse the navigation graph. For typical APIs I load the entity and apply the DTO so only real changes are written.
:::

## SaveChanges, Transactions and Concurrency

### SaveChanges Internals

What happens in `SaveChangesAsync()`:

1. `DetectChanges()` (unless disabled) — finds Added/Modified/Deleted entities.
2. Runs `SavingChanges` events and **interceptors** (audit fields, soft delete).
3. Builds modification commands and **orders them by dependencies**: principals inserted before dependents (Order before OrderItems), dependents deleted before principals.
4. Opens the connection and starts a **transaction** if none is active — *every `SaveChanges` is atomic*.
5. **Batches** commands into as few round trips as possible (SQL Server default max batch size 42 statements; configure `MaxBatchSize`).
6. Reads back store-generated values (IDENTITY, `rowversion`, defaults) via `OUTPUT` and fixes up FKs on dependents.
7. Checks rows-affected for concurrency tokens → `DbUpdateConcurrencyException` on mismatch.
8. Commits, then `AcceptAllChanges()` — Added/Modified → Unchanged, Deleted → Detached. On failure the transaction rolls back and states stay as they were.

```csharp
// One order with 3 items: ONE transaction, typically 2 round trips
db.Orders.Add(new Order { CustomerId = 5, Items = { item1, item2, item3 } });
await db.SaveChangesAsync();
// BEGIN TRAN
//   INSERT INTO Orders (...) OUTPUT INSERTED.Id, INSERTED.RowVersion VALUES (...);
//   INSERT INTO OrderItems (...) OUTPUT INSERTED.Id VALUES (...), (...), (...);  -- batched
// COMMIT
```

### Explicit Transactions and Execution Strategies

Use an explicit transaction when **several `SaveChanges` calls, raw SQL or `ExecuteUpdate`** must succeed or fail together.

```csharp
await using var tx = await db.Database.BeginTransactionAsync();   // IsolationLevel overload exists
try
{
    var order = new Order { CustomerId = customerId, Status = OrderStatus.Paid, /*...*/ };
    db.Orders.Add(order);
    await db.SaveChangesAsync();                                   // gets order.Id

    int reserved = await db.Products                               // same transaction
        .Where(p => p.Id == productId && p.Stock >= qty)
        .ExecuteUpdateAsync(s => s.SetProperty(p => p.Stock, p => p.Stock - qty));
    if (reserved == 0) throw new InvalidOperationException("Out of stock");

    await tx.CommitAsync();
}
catch
{
    await tx.RollbackAsync();   // also happens automatically on dispose without commit
    throw;
}
```

**Connection resiliency conflicts with manual transactions.** With `EnableRetryOnFailure()` EF may retry a failed operation — but it cannot replay half a user-initiated transaction, so it throws *"The configured execution strategy 'SqlServerRetryingExecutionStrategy' does not support user-initiated transactions"*. Wrap the whole unit in the strategy:

```csharp
var strategy = db.Database.CreateExecutionStrategy();
await strategy.ExecuteAsync(async () =>
{
    await using var tx = await db.Database.BeginTransactionAsync();
    // ... SaveChanges / ExecuteUpdate ...
    await tx.CommitAsync();
});
// The delegate may run more than once: keep it self-contained and idempotent;
// call db.ChangeTracker.Clear() at the start if state from a failed attempt could linger.
```

Savepoints (`tx.CreateSavepointAsync("beforeStock")`) allow partial rollback; `TransactionScope` works for ambient transactions but avoid distributed transactions across services — use the outbox pattern instead.

### Optimistic Concurrency with RowVersion

**Definition.** Optimistic concurrency assumes conflicts are rare: no locks are held; instead a **concurrency token** is included in the `WHERE` of each UPDATE/DELETE. If someone else changed the row, 0 rows are affected and EF throws `DbUpdateConcurrencyException`.

```csharp
// Order.RowVersion: [Timestamp] byte[]   or   b.Property(o => o.RowVersion).IsRowVersion();
// Any property can be a token:              b.Property(p => p.Price).IsConcurrencyToken();
```

```sql
UPDATE [Orders] SET [Status] = @p0
OUTPUT INSERTED.[RowVersion]
WHERE [Id] = @p1 AND [RowVersion] = @p2;     -- 0 rows => conflict
```

```csharp
// API: client sends back the RowVersion it read (as base64); 409 on conflict
app.MapPut("/orders/{id:int}/status", async (int id, UpdateStatusDto dto, ShopContext db) =>
{
    var order = await db.Orders.FindAsync(id);
    if (order is null) return Results.NotFound();

    // Compare against what the CLIENT saw, not what we just loaded
    db.Entry(order).Property(o => o.RowVersion).OriginalValue = dto.RowVersion;
    order.Status = dto.Status;
    try
    {
        await db.SaveChangesAsync();
        return Results.Ok(new { order.RowVersion });
    }
    catch (DbUpdateConcurrencyException ex)
    {
        var entry = ex.Entries.Single();
        var dbValues = await entry.GetDatabaseValuesAsync();
        if (dbValues is null) return Results.NotFound();          // deleted meanwhile
        // Strategies: "client wins" -> entry.OriginalValues.SetValues(dbValues) and retry;
        //             "store wins"  -> entry.CurrentValues.SetValues(dbValues);
        //             or return the conflict to the user to merge:
        return Results.Conflict(new { message = "Order was modified by someone else.",
                                      current = dbValues.ToObject() });
    }
});
```

:::example Real-world example
Two support agents open order 1001. Agent A cancels it; agent B, a minute later, marks it shipped. Without a token B's update silently overwrites A's cancellation (lost update) and a cancelled order ships. With `RowVersion`, B gets a 409 and the UI reloads the order showing "Cancelled".
:::

### SaveChanges Interceptors for Audit and Soft Delete

**Definition.** Interceptors hook into EF operations. A `SaveChangesInterceptor` runs before/after `SaveChanges`, the ideal place for cross-cutting rules: audit columns, soft delete, domain events.

```csharp
public interface IAuditable
{
    DateTime CreatedUtc { get; set; } string? CreatedBy { get; set; }
    DateTime? UpdatedUtc { get; set; } string? UpdatedBy { get; set; }
}
public interface ISoftDelete { bool IsDeleted { get; set; } DateTime? DeletedUtc { get; set; } }

public sealed class AuditInterceptor(ICurrentUser user, TimeProvider clock) : SaveChangesInterceptor
{
    public override ValueTask<InterceptionResult<int>> SavingChangesAsync(
        DbContextEventData eventData, InterceptionResult<int> result,
        CancellationToken ct = default)
    {
        var db = eventData.Context;
        if (db is null) return base.SavingChangesAsync(eventData, result, ct);
        var now = clock.GetUtcNow().UtcDateTime;

        foreach (var e in db.ChangeTracker.Entries<IAuditable>())
        {
            if (e.State == EntityState.Added)
            { e.Entity.CreatedUtc = now; e.Entity.CreatedBy = user.Id; }
            else if (e.State == EntityState.Modified)
            { e.Entity.UpdatedUtc = now; e.Entity.UpdatedBy = user.Id; }
        }
        foreach (var e in db.ChangeTracker.Entries<ISoftDelete>()
                     .Where(e => e.State == EntityState.Deleted))
        {
            e.State = EntityState.Modified;          // turn DELETE into UPDATE
            e.Entity.IsDeleted = true;
            e.Entity.DeletedUtc = now;
        }
        return base.SavingChangesAsync(eventData, result, ct);
    }
}

builder.Services.AddScoped<AuditInterceptor>();
builder.Services.AddDbContext<ShopContext>((sp, o) => o
    .UseSqlServer(cs)
    .AddInterceptors(sp.GetRequiredService<AuditInterceptor>()));
```

Other interceptors: `DbCommandInterceptor` (inspect/modify SQL, add query hints, log slow commands), `DbConnectionInterceptor` (e.g. set an Azure AD access token on the connection), `IMaterializationInterceptor` (EF 7+, act when entities are created). Remember interceptors don't run for `ExecuteUpdate/Delete` or raw SQL.

:::scenario Updates sometimes silently overwrite other users' changes
Symptoms: support reports "my edit disappeared". Cause: last-write-wins — the API uses `Update(dto-mapped entity)` with no concurrency token, so every PUT overwrites all columns. Fix: add a `rowversion` column (`IsRowVersion()`), return it to clients (ETag header is a nice touch), require it on PUT (`If-Match`), set it as the property's `OriginalValue`, and translate `DbUpdateConcurrencyException` to 409/412. Also switch to load-and-apply so only changed columns are written.
:::
