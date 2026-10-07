## EF Core Fundamentals

### What EF Core Is and How It Works

**Definition.** Entity Framework Core is Microsoft's open-source, cross-platform **object-relational mapper (ORM)**. You work with C# classes and LINQ; EF Core translates them to SQL, runs the SQL through an ADO.NET provider, and materializes the rows back into objects. It also **tracks changes** to those objects and writes only what changed on `SaveChanges`.

**Why it matters.** EF Core is the default data-access layer in .NET and is asked about in nearly every .NET interview. Knowing the *pipeline* (not just the API) lets you explain N+1, tracking, client evaluation and performance questions.

```text
READ                                                     WRITE
LINQ query (IQueryable<T>)                               ctx.Add / modify / Remove
   │ expression tree                                        │
   ▼                                                        ▼
Query translation (provider-specific)               ChangeTracker.DetectChanges()
   │ → SQL + parameters (plan cached)                       │ finds Added/Modified/Deleted
   ▼                                                        ▼
DbCommand → database → DbDataReader                 Ordered, batched INSERT/UPDATE/DELETE
   │                                                        │ inside ONE transaction
   ▼                                                        ▼
Materialize entities → (track in ChangeTracker)     Generated values (identity, rowversion) read back
```

**Providers** plug in the database dialect: `Microsoft.EntityFrameworkCore.SqlServer`, `Npgsql.EntityFrameworkCore.PostgreSQL`, `Microsoft.EntityFrameworkCore.Sqlite`, `Microsoft.EntityFrameworkCore.Cosmos`, MySQL (Pomelo / Oracle). The `InMemory` provider exists but ignores relational behaviour (FKs, transactions, SQL translation) — prefer SQLite in-memory or a real database in Testcontainers for tests.

| | EF Core | Dapper (micro-ORM) | ADO.NET |
|---|---|---|---|
| You write | LINQ | SQL | SQL + readers |
| Change tracking, migrations | Yes | No | No |
| Speed | Good (great with `AsNoTracking`/projections) | Near raw | Raw |
| Best for | CRUD, domain models, rapid development | Hot read paths, complex reporting SQL | Bulk/streaming, special cases |

:::tip A strong answer
"I use EF Core for most of the app and drop to raw SQL or Dapper for the few hot or reporting queries. They mix fine on the same connection."
:::

### The Domain Used in These Notes

All examples use one e-commerce model: **Customer → Orders → OrderItems → Product → Category**, plus **Tags** (many-to-many with Product).

```csharp
public class Customer
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public string Email { get; set; } = "";
    public DateTime CreatedUtc { get; set; }
    public List<Order> Orders { get; set; } = [];
}

public enum OrderStatus { Pending, Paid, Shipped, Cancelled }

public class Order
{
    public int Id { get; set; }
    public int CustomerId { get; set; }                 // foreign key
    public Customer Customer { get; set; } = null!;     // reference navigation
    public DateTime OrderDate { get; set; }
    public OrderStatus Status { get; set; }
    public decimal Total { get; set; }
    public byte[] RowVersion { get; set; } = [];        // concurrency token
    public List<OrderItem> Items { get; set; } = [];    // collection navigation
}

public class OrderItem
{
    public int Id { get; set; }
    public int OrderId { get; set; }
    public Order Order { get; set; } = null!;
    public int ProductId { get; set; }
    public Product Product { get; set; } = null!;
    public int Quantity { get; set; }
    public decimal UnitPrice { get; set; }              // price captured at purchase time
}

public class Product
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public string Sku { get; set; } = "";
    public decimal Price { get; set; }
    public bool IsDeleted { get; set; }
    public int CategoryId { get; set; }
    public Category Category { get; set; } = null!;
    public List<Tag> Tags { get; set; } = [];           // many-to-many (skip navigation)
}

public class Category
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public int? ParentId { get; set; }                  // self-reference, optional
    public Category? Parent { get; set; }
    public List<Product> Products { get; set; } = [];
}

public class Tag
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public List<Product> Products { get; set; } = [];
}
```

## DbContext and the Model

### DbContext, DbSet and the Unit of Work

**Definition.** `DbContext` is a **session with the database**. It exposes `DbSet<T>` properties (one per entity set, comparable to a table), holds the **change tracker**, and implements the **Unit of Work** pattern: you make many changes in memory, then `SaveChanges` commits them together in one transaction. A `DbSet<T>` behaves like a repository for `T`.

```csharp
public class ShopContext(DbContextOptions<ShopContext> options) : DbContext(options)
{
    public DbSet<Customer> Customers => Set<Customer>();
    public DbSet<Order> Orders => Set<Order>();
    public DbSet<OrderItem> OrderItems => Set<OrderItem>();
    public DbSet<Product> Products => Set<Product>();
    public DbSet<Category> Categories => Set<Category>();
    public DbSet<Tag> Tags => Set<Tag>();

    protected override void OnModelCreating(ModelBuilder modelBuilder) =>
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(ShopContext).Assembly);

    // Pre-convention rules applied to EVERY matching property
    protected override void ConfigureConventions(ModelConfigurationBuilder cb)
    {
        cb.Properties<decimal>().HavePrecision(18, 2);   // no more decimal(18,2) warnings
        cb.Properties<string>().HaveMaxLength(256);      // instead of nvarchar(max)
    }
}

// Program.cs
builder.Services.AddDbContext<ShopContext>(o => o
    .UseSqlServer(builder.Configuration.GetConnectionString("Shop"),
        sql => sql.EnableRetryOnFailure()));            // lifetime: Scoped by default
```

```csharp
// The unit of work in action: one transaction for everything below
public async Task<int> PlaceOrderAsync(int customerId, List<(int ProductId, int Qty)> lines)
{
    var products = await _db.Products
        .Where(p => lines.Select(l => l.ProductId).Contains(p.Id))
        .ToDictionaryAsync(p => p.Id);

    var order = new Order { CustomerId = customerId, OrderDate = DateTime.UtcNow,
                            Status = OrderStatus.Pending };
    foreach (var (productId, qty) in lines)
        order.Items.Add(new OrderItem { ProductId = productId, Quantity = qty,
                                        UnitPrice = products[productId].Price });
    order.Total = order.Items.Sum(i => i.Quantity * i.UnitPrice);

    _db.Orders.Add(order);                 // graph is tracked as Added
    await _db.SaveChangesAsync();          // INSERT Order, then INSERT OrderItems, atomically
    return order.Id;                       // identity value is back on the object
}
```

**Lifetime rules (a favourite interview topic).**

| Rule | Why |
|---|---|
| Register as **Scoped** (`AddDbContext`) — one instance per HTTP request | Matches the unit of work; tracked entities don't leak across requests |
| **Not thread-safe** — one operation at a time | `Task.WhenAll` on the same context throws *"A second operation was started on this context instance..."* |
| Never inject into a **Singleton** | Captive dependency: one context forever, growing tracker, stale data, concurrency bugs |
| Background services / Blazor Server → `IDbContextFactory<ShopContext>` or `CreateScope()` | There is no request scope there |
| Short-lived and cheap to create | Don't cache it; creating one costs microseconds, connections come from the ADO.NET pool |

:::q Why should DbContext be Scoped and not Singleton or Transient?
Scoped gives one context per request: all repositories/services in that request share the same tracker and transaction, so changes made by one service are saved by one `SaveChanges`. Singleton shares one non-thread-safe context across concurrent requests — data races and an ever-growing tracker. Transient would give each service its own context, so a unit of work could not span them.
:::

### Model Building Conventions

EF builds the model from your classes using **conventions**, then applies **Data Annotations**, then the **Fluent API** (last word wins).

| Convention | Result |
|---|---|
| Property named `Id` or `<ClassName>Id` | Primary key; `int`/`long` keys become `IDENTITY` |
| `DbSet<Order> Orders` | Table named `Orders` (class name if no `DbSet`) |
| Non-nullable value type / (with nullable reference types) non-nullable reference | `NOT NULL`; `int?` / `string?` is nullable |
| `string` | `nvarchar(max)` on SQL Server (set `HaveMaxLength`) |
| `decimal` | `decimal(18,2)` **with a warning** — always set precision |
| Navigation + property `CustomerId` / `<NavName>Id` | Foreign key relationship; required if FK is non-nullable |
| Required relationship | Cascade delete; optional → `ClientSetNull` |
| Property named `RowVersion` of `byte[]` | *Not* automatic — mark with `[Timestamp]` / `IsRowVersion()` |

### Data Annotations vs Fluent API

**Definition.** Two ways to override conventions. **Data Annotations** are attributes on the class; the **Fluent API** is code in `OnModelCreating` or in `IEntityTypeConfiguration<T>` classes.

```csharp
// Data Annotations: quick, visible, also used by MVC/Web API model validation
[Index(nameof(Sku), IsUnique = true)]
public class Product
{
    public int Id { get; set; }
    [Required, MaxLength(200)] public string Name { get; set; } = "";
    [Column(TypeName = "decimal(18,2)")] public decimal Price { get; set; }
    [NotMapped] public string DisplayName => $"{Name} ({Sku})";
    // ...
}

// Fluent API in its own class: the recommended place for anything non-trivial
public class OrderConfiguration : IEntityTypeConfiguration<Order>
{
    public void Configure(EntityTypeBuilder<Order> b)
    {
        b.ToTable("Orders");
        b.Property(o => o.Status).HasConversion<string>().HasMaxLength(20);
        b.Property(o => o.Total).HasPrecision(18, 2);
        b.Property(o => o.RowVersion).IsRowVersion();
        b.HasOne(o => o.Customer).WithMany(c => c.Orders)
            .HasForeignKey(o => o.CustomerId)
            .OnDelete(DeleteBehavior.Restrict);
        b.HasIndex(o => new { o.CustomerId, o.OrderDate });
    }
}
// OnModelCreating: modelBuilder.ApplyConfigurationsFromAssembly(typeof(ShopContext).Assembly);
```

| | Data Annotations | Fluent API |
|---|---|---|
| Where | Attributes on the entity | `OnModelCreating` / `IEntityTypeConfiguration<T>` |
| Coverage | Subset: `Key`, `Required`, `MaxLength`, `Column`, `Table`, `ForeignKey`, `NotMapped`, `Index`, `Timestamp`, `Precision`, `Owned`, `ComplexType` | **Everything**: composite keys, relationship shape, delete behavior, inheritance mapping, converters, query filters, owned/JSON config, indexes with filters/includes |
| Precedence | Overrides conventions | **Overrides annotations and conventions** |
| Domain purity | Couples entities to `System.ComponentModel.DataAnnotations` | Entities stay POCOs |
| Bonus | Reused by ASP.NET Core validation (`[Required]`, `[StringLength]`) | Organised per entity, testable |

**Precedence: Convention < Data Annotation < Fluent API.** My rule: validation-flavoured attributes on DTOs/request models; mapping in Fluent configuration classes; `ApplyConfigurationsFromAssembly` picks them all up.

### Code First vs Database First

| | Code First | Database First |
|---|---|---|
| Starting point | C# entities + Fluent config | An existing database |
| Schema owner | **Migrations** from the code | The DB (DBA scripts / DACPAC) |
| How you start | `dotnet ef migrations add`, `database update` | `dotnet ef dbcontext scaffold` |
| Re-sync | Add a migration | Re-scaffold (overwrites generated files) |
| Fits | New projects, domain-driven design | Legacy databases, DBA-controlled schemas |

```bash
# Reverse-engineer an existing database into entities + a DbContext
dotnet ef dbcontext scaffold \
  "Server=.;Database=Shop;Trusted_Connection=True;TrustServerCertificate=True" \
  Microsoft.EntityFrameworkCore.SqlServer \
  --output-dir Models --context-dir Data --context ShopContext \
  --data-annotations --table Customers --table Orders --force --no-onconfiguring
# requires the Microsoft.EntityFrameworkCore.Design package; --force overwrites existing files
```

Scaffolded classes are `partial` — put your logic in a separate partial file so re-scaffolding doesn't destroy it, and move the connection string to configuration (`--no-onconfiguring`). The old "Model First" (designer) approach no longer exists in EF Core.

:::q Code First or Database First - which do you choose?
Code First for new systems: the C# model is the source of truth and migrations give versioned, repeatable schema changes in source control. Database First when a database already exists and is owned by a DBA team; I scaffold it and treat the DB as the source of truth. Both end up with the same runtime model — it is only the direction of generation.
:::

## Migrations

### Migrations Workflow and Commands

**Definition.** A migration is a C# file (with `Up()` and `Down()`) describing one schema change, generated by diffing your current model against the **model snapshot** from the previous migration. Applied migrations are recorded in the `__EFMigrationsHistory` table.

```bash
dotnet tool install --global dotnet-ef                 # once (or a local tool manifest)

dotnet ef migrations add AddProductTags                # create migration from model changes
dotnet ef migrations list                              # applied / pending
dotnet ef database update                              # apply all pending (to latest)
dotnet ef database update InitialCreate                # roll BACK to that migration (runs Down)
dotnet ef migrations remove                            # delete the last, un-applied migration
dotnet ef migrations script --idempotent -o deploy.sql # SQL that checks history before each step
dotnet ef migrations script InitialCreate AddTags      # script a range
dotnet ef migrations bundle --self-contained -o efbundle   # single executable
# multi-project solutions:
dotnet ef migrations add X --project src/Shop.Data --startup-project src/Shop.Api
```

```csharp
// 20261006_AddProductTags.cs  (generated; review it!)
public partial class AddProductTags : Migration
{
    protected override void Up(MigrationBuilder mb)
    {
        mb.CreateTable(
            name: "Tags",
            columns: t => new
            {
                Id = t.Column<int>(nullable: false).Annotation("SqlServer:Identity", "1, 1"),
                Name = t.Column<string>(maxLength: 50, nullable: false)
            },
            constraints: t => t.PrimaryKey("PK_Tags", x => x.Id));

        mb.CreateIndex("IX_Tags_Name", "Tags", "Name", unique: true);
    }

    protected override void Down(MigrationBuilder mb) => mb.DropTable("Tags");
}
```

:::warn Always read the generated migration
EF cannot tell a **rename** from drop + add: renaming `Product.Title` to `Name` generates `DropColumn` + `AddColumn` — **data loss**. Edit it to `mb.RenameColumn("Title", "Products", newName: "Name")`. Also watch for column type changes that truncate data, and new `NOT NULL` columns on populated tables (supply a default). Never edit a migration that has already been applied elsewhere — add a new one.
:::

### Applying Migrations in Dev and CI/CD

| Approach | How | Pros | Cons |
|---|---|---|---|
| `Database.Migrate()` at app startup | `await db.Database.MigrateAsync();` | Trivial | App needs DDL rights; several instances race (EF9 adds a migration lock); long migrations delay startup; no review or rollback |
| **Idempotent SQL script** | `migrations script --idempotent` → run via release task/sqlcmd | DBA can review; safe to re-run | Extra pipeline step |
| **Migration bundle** | `migrations bundle` → `./efbundle --connection "..."` | Self-contained exe, no SDK on the agent; ideal for containers/pipelines | One more artifact |
| Separate migration job / init container | Same bundle run once before the rollout | No race, clean permissions | Needs orchestration |

```yaml
# Azure DevOps / GitHub Actions: build the bundle once, run it before deploying the app
- script: |
    dotnet tool restore
    dotnet ef migrations bundle --project src/Shop.Data --startup-project src/Shop.Api \
        --self-contained -r linux-x64 -o $(Build.ArtifactStagingDirectory)/efbundle
  displayName: Build EF migration bundle
- script: ./efbundle --connection "$(ShopConnectionString)"   # from a secret variable
  displayName: Apply migrations
```

**EF Core 9 notes.** `Migrate()` throws on *pending model changes* (the model differs from the last snapshot — you forgot `migrations add`); catch it in CI with `dotnet ef migrations has-pending-model-changes`. Migrations also take a database lock so two instances don't run them at once. **Zero-downtime deployments** need *expand/contract*: add the new column nullable (deploy 1), backfill and switch code (deploy 2), drop the old column later (deploy 3) — never rename or drop in the same release that still has old code running.

### Data Seeding

```csharp
// 1. HasData: seed is PART OF THE MODEL; migrations generate InsertData/UpdateData/DeleteData.
//    Keys must be explicit; use FK properties, not navigations.
modelBuilder.Entity<Category>().HasData(
    new Category { Id = 1, Name = "Electronics" },
    new Category { Id = 2, Name = "Books" });

// 2. UseSeeding / UseAsyncSeeding (EF Core 9): code runs after migrations are applied
//    (Migrate, EnsureCreated, and `dotnet ef database update`). Must be idempotent.
builder.Services.AddDbContext<ShopContext>(o => o
    .UseSqlServer(cs)
    .UseSeeding((ctx, _) =>
    {
        if (!ctx.Set<Tag>().Any())
        {
            ctx.Set<Tag>().AddRange(new Tag { Name = "new" }, new Tag { Name = "sale" });
            ctx.SaveChanges();
        }
    })
    .UseAsyncSeeding(async (ctx, _, ct) =>
    {
        if (!await ctx.Set<Tag>().AnyAsync(ct))
        {
            ctx.Set<Tag>().AddRange(new Tag { Name = "new" }, new Tag { Name = "sale" });
            await ctx.SaveChangesAsync(ct);
        }
    }));
```

| | `HasData` | `UseSeeding` / `UseAsyncSeeding` |
|---|---|---|
| Tracked in migrations | Yes (changes produce migration steps) | No |
| Needs fixed PKs | Yes | No |
| Can query/conditional logic | No | Yes |
| Good for | Small static reference data (statuses, countries, roles) | Dev/test data, data depending on other rows, environment-specific data |

:::scenario Add a NOT NULL column to a 50-million-row table without an outage
A naive `AddColumn(nullable: false, defaultValue: "")` takes a schema lock and rewrites a huge table; the migration times out and blocks writes. Plan: (1) migration 1 — add the column **nullable**; (2) deploy code that writes the new column; (3) backfill old rows in small batches (`UPDATE TOP (10000) ... WHERE NewCol IS NULL`) via a job, not inside the migration; (4) migration 2 — make it `NOT NULL` with a check/default once complete; (5) test the generated SQL on a production-sized copy. Explain you split *schema* and *data* changes and keep each step backward compatible.
:::

:::scenario Two developers each added a migration - the snapshot conflicts
Both branches changed `ShopContextModelSnapshot.cs`, so merging creates a conflict and the second migration is based on a stale model. Resolution: merge the branch, delete the conflicting (un-applied) migration with `dotnet ef migrations remove` (or delete its files and revert the snapshot to the merged state), then run `migrations add` again so the migration and snapshot are regenerated from the merged model. Agree as a team: merge `main` before adding a migration, one migration per PR, and CI runs `has-pending-model-changes`.
:::
