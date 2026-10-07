## Relationships

### Relationship Basics: Principal, Dependent, FK, Navigations

**Definition.** A relationship links two entity types through a **foreign key (FK)**. The **principal** is the side with the key being referenced (`Customer`); the **dependent** holds the FK (`Order.CustomerId`). **Navigation properties** let you move between them in C#: a *reference navigation* (`Order.Customer`) points to one entity, a *collection navigation* (`Customer.Orders`) to many.

**Why it matters.** The relationship configuration decides the generated schema (FK columns, indexes, cascade rules), how `Include` builds joins, and what happens when you delete or re-parent something. Most "EF deleted my data" and "FK constraint conflict" bugs are relationship misconfiguration.

| Term | Example in the domain |
|---|---|
| Principal | `Customer`, `Order`, `Category` |
| Dependent | `Order` (of Customer), `OrderItem` (of Order) |
| Foreign key | `Order.CustomerId`, `OrderItem.OrderId` |
| Principal key | Usually the PK (`Customer.Id`); can be an *alternate key* via `HasPrincipalKey` |
| Reference navigation | `Order.Customer`, `Product.Category` |
| Collection navigation | `Customer.Orders`, `Order.Items` |
| Inverse navigation | `Customer.Orders` is the inverse of `Order.Customer` |

### One-to-Many

The most common shape: one `Customer` has many `Order`s. Conventions discover it from the navigations plus `CustomerId`; Fluent API makes it explicit.

```csharp
modelBuilder.Entity<Order>()
    .HasOne(o => o.Customer)            // each order has one customer
    .WithMany(c => c.Orders)            // a customer has many orders
    .HasForeignKey(o => o.CustomerId)   // FK on the dependent
    .IsRequired()                       // CustomerId NOT NULL
    .OnDelete(DeleteBehavior.Restrict); // can't delete a customer who has orders
```

```sql
-- Generated (approximately)
CREATE TABLE [Orders] (
    [Id] int NOT NULL IDENTITY,
    [CustomerId] int NOT NULL,
    [OrderDate] datetime2 NOT NULL,
    [Status] nvarchar(20) NOT NULL,
    [Total] decimal(18,2) NOT NULL,
    [RowVersion] rowversion NOT NULL,
    CONSTRAINT [PK_Orders] PRIMARY KEY ([Id]),
    CONSTRAINT [FK_Orders_Customers_CustomerId] FOREIGN KEY ([CustomerId])
        REFERENCES [Customers] ([Id]) ON DELETE NO ACTION
);
CREATE INDEX [IX_Orders_CustomerId] ON [Orders] ([CustomerId]);  -- FKs get an index by convention
```

### One-to-One

**Definition.** Each principal has at most one dependent. EF needs to know **which side holds the FK** because both sides have a reference navigation.

```csharp
public class CustomerProfile
{
    public int CustomerId { get; set; }          // PK *and* FK (shared primary key)
    public Customer Customer { get; set; } = null!;
    public string LoyaltyTier { get; set; } = "Bronze";
    public DateOnly? Birthday { get; set; }
}
// Customer gets:  public CustomerProfile? Profile { get; set; }

modelBuilder.Entity<CustomerProfile>(b =>
{
    b.HasKey(p => p.CustomerId);
    b.HasOne(p => p.Customer)
     .WithOne(c => c.Profile)
     .HasForeignKey<CustomerProfile>(p => p.CustomerId);   // generic arg = dependent
});
```

With a separate FK column (not the PK) EF adds a **unique index** on it to enforce one-to-one. Use 1:1 to split rarely-read or large columns from a hot table, or for optional extensions. If the data always travels with the owner and has no identity, an **owned/complex type** is simpler.

### Many-to-Many

**Skip navigations (EF Core 5+).** `Product.Tags` and `Tag.Products` with no join class: EF creates a join table automatically.

```csharp
modelBuilder.Entity<Product>()
    .HasMany(p => p.Tags)
    .WithMany(t => t.Products)
    .UsingEntity(j => j.ToTable("ProductTags"));   // optional: rename the join table

// Usage: just manipulate the collections
var product = await db.Products.Include(p => p.Tags).FirstAsync(p => p.Id == 7);
var sale = await db.Tags.SingleAsync(t => t.Name == "sale");
product.Tags.Add(sale);                  // INSERT INTO ProductTags (ProductsId, TagsId) ...
await db.SaveChangesAsync();
```

**Join entity with payload.** When the link itself has data (who tagged it, when, sort order) model the join entity explicitly and keep the skip navigations if you like:

```csharp
public class ProductTag
{
    public int ProductId { get; set; }
    public int TagId { get; set; }
    public DateTime TaggedUtc { get; set; }
    public string TaggedBy { get; set; } = "";
}

modelBuilder.Entity<Product>()
    .HasMany(p => p.Tags)
    .WithMany(t => t.Products)
    .UsingEntity<ProductTag>(
        r => r.HasOne<Tag>().WithMany().HasForeignKey(pt => pt.TagId),
        l => l.HasOne<Product>().WithMany().HasForeignKey(pt => pt.ProductId),
        j =>
        {
            j.HasKey(pt => new { pt.ProductId, pt.TagId });
            j.Property(pt => pt.TaggedUtc).HasDefaultValueSql("SYSUTCDATETIME()");
        });

// Write payload by adding the join entity directly
db.Set<ProductTag>().Add(new ProductTag { ProductId = 7, TagId = 3, TaggedBy = "admin" });
```

`Order` ↔ `Product` through `OrderItem` is the *fully explicit* version: two one-to-many relationships with a real entity in the middle (`Quantity`, `UnitPrice`). Use that when the link is a business concept in its own right.

### Foreign Keys, Shadow FKs and Required vs Optional

**Shadow properties** exist in the EF model and database but not on your class. If a dependent has a navigation but no FK property, EF creates a shadow FK.

```csharp
public class Review                       // no ProductId property
{
    public int Id { get; set; }
    public Product Product { get; set; } = null!;
    public int Rating { get; set; }
}
// EF creates shadow FK "ProductId". Query it with EF.Property:
var reviews = await db.Set<Review>()
    .Where(r => EF.Property<int>(r, "ProductId") == 7).ToListAsync();

// Shadow properties are also handy for audit columns kept out of the domain
modelBuilder.Entity<Order>().Property<DateTime>("LastUpdatedUtc");
db.Entry(order).Property("LastUpdatedUtc").CurrentValue = DateTime.UtcNow;
```

Prefer an explicit FK property in most apps: you can set `order.CustomerId = 5` without loading the customer, and disconnected updates are easier.

| | Required relationship | Optional relationship |
|---|---|---|
| FK type | `int CustomerId` (non-nullable) | `int? ParentId` |
| Navigation (NRT on) | `Customer Customer = null!` | `Category? Parent` |
| Column | `NOT NULL` | `NULL` |
| Default delete behaviour | **Cascade** | **ClientSetNull** |
| Orphan when removed from collection | Dependent is deleted | FK set to null |

### Delete Behaviors

`OnDelete` controls two things: the FK constraint EF creates in the database **and** what EF does to **tracked** dependents when the principal is deleted or the relationship is severed.

| `DeleteBehavior` | Tracked dependents in EF | Database FK `ON DELETE` | Use when |
|---|---|---|---|
| `Cascade` | Deleted | `CASCADE` | Dependents can't exist without the parent (Order → OrderItems) |
| `ClientCascade` | Deleted | `NO ACTION` | DB can't cascade (SQL Server multiple cascade paths) |
| `Restrict` | Throws if dependents tracked | `NO ACTION` (blocks delete) | Protect history: Customer with Orders |
| `NoAction` | Not changed | `NO ACTION` | Let DB decide/raise error |
| `SetNull` | FK set to null | `SET NULL` | Optional link, keep the dependent (Category → Products' optional link) |
| `ClientSetNull` (**optional default**) | FK set to null | `NO ACTION` | Only nulls FKs of entities EF has loaded |
| `ClientNoAction` | Not changed | `NO ACTION` | Rare; full manual control |

```csharp
modelBuilder.Entity<OrderItem>()
    .HasOne(i => i.Order).WithMany(o => o.Items)
    .OnDelete(DeleteBehavior.Cascade);             // deleting an order deletes its items

modelBuilder.Entity<OrderItem>()
    .HasOne(i => i.Product).WithMany()
    .OnDelete(DeleteBehavior.Restrict);            // never delete a product that was sold

modelBuilder.Entity<Category>()
    .HasOne(c => c.Parent).WithMany()
    .HasForeignKey(c => c.ParentId)
    .OnDelete(DeleteBehavior.ClientSetNull);       // self-reference: no DB cascade allowed
```

:::warn Gotchas
- SQL Server rejects schemas with **multiple cascade paths** or cycles (error 1785). Self-references and diamond shapes need `Restrict`/`ClientSetNull`/`ClientCascade`.
- `ClientSetNull`/`ClientCascade` only affect **loaded** dependents; rows not in the tracker hit the `NO ACTION` constraint and the delete fails.
- `order.Items.Remove(item)` on a required relationship **deletes** the item (orphan deletion) — surprising if you only meant to move it.
- In real e-commerce systems you rarely hard-delete principals; soft delete (query filter) is safer.
:::

:::q What is the default delete behavior in EF Core?
For a required relationship (non-nullable FK) it is `Cascade` — deleting the principal deletes dependents in the tracker and the DB constraint is `ON DELETE CASCADE`. For an optional relationship it is `ClientSetNull`: EF nulls the FK of loaded dependents, but the DB constraint is `NO ACTION`, so unloaded dependents make the delete fail.
:::

## Advanced Mapping

### Owned Types and Complex Types (Value Objects)

**Definition.** A **value object** (DDD) is defined by its values, not an identity: `Address`, `Money`, `DateRange`. EF Core maps them with **owned entity types** (`OwnsOne`/`OwnsMany`) or, since EF Core 8, **complex types** (`ComplexProperty` / `[ComplexType]`). Their columns live inside the owner's table by default.

```csharp
public record Address(string Street, string City, string PostalCode, string Country);

public class Customer
{
    // ...
    public Address ShippingAddress { get; set; } = null!;   // owned / complex
    public Address? BillingAddress { get; set; }
}

// Owned type (classic): columns ShippingAddress_Street, ShippingAddress_City ...
modelBuilder.Entity<Customer>().OwnsOne(c => c.ShippingAddress, a =>
{
    a.Property(x => x.City).HasColumnName("ShipCity").HasMaxLength(100);
});

// Complex type (EF Core 8+): true value semantics, no hidden key, same table
modelBuilder.Entity<Customer>().ComplexProperty(c => c.ShippingAddress);

// OwnsMany: a collection of owned values in its own table with a hidden key
modelBuilder.Entity<Customer>().OwnsMany(c => c.SavedAddresses, a => a.ToTable("CustomerAddresses"));
```

| | Owned type | Complex type (EF 8+) |
|---|---|---|
| Identity | Hidden key (it is still an entity type) | None — pure value |
| Same instance shared by two owners | Not allowed | Allowed |
| Collections | `OwnsMany` (separate table or JSON) | JSON collections (EF 10) |
| Optional (`null`) | Supported | Supported from EF 10 (required-only in EF 8/9) |
| JSON column mapping | `OwnsOne(...).ToJson()` (EF 7+) | `ComplexProperty(...).ToJson()` (EF 10) |
| Recommendation | Existing code, `OwnsMany` tables | New value objects on EF 8+ |

### Inheritance: TPH, TPT, TPC

**Definition.** Relational tables have no inheritance, so EF offers three mapping strategies. Domain example: payments for an order.

```csharp
public abstract class Payment
{
    public int Id { get; set; }
    public int OrderId { get; set; }
    public decimal Amount { get; set; }
    public DateTime PaidUtc { get; set; }
}
public class CardPayment : Payment { public string Last4 { get; set; } = ""; public string Network { get; set; } = ""; }
public class UpiPayment  : Payment { public string UpiId { get; set; } = ""; }

// TPH (default): one table + discriminator
modelBuilder.Entity<Payment>()
    .HasDiscriminator<string>("PaymentType")
    .HasValue<CardPayment>("card").HasValue<UpiPayment>("upi");

// TPT: base table + one table per derived type, joined by PK
modelBuilder.Entity<Payment>().UseTptMappingStrategy();

// TPC (EF 7+): one table per CONCRETE type, each with all columns
modelBuilder.Entity<Payment>().UseTpcMappingStrategy();
```

```sql
-- db.Set<Payment>().Where(p => p.Amount > 100) under each strategy (approximately)
-- TPH
SELECT * FROM Payments p WHERE p.Amount > 100;
-- TPT
SELECT ... FROM Payments p
LEFT JOIN CardPayments c ON p.Id = c.Id
LEFT JOIN UpiPayments  u ON p.Id = u.Id
WHERE p.Amount > 100;
-- TPC
SELECT ... FROM (SELECT ... FROM CardPayments UNION ALL SELECT ... FROM UpiPayments) p
WHERE p.Amount > 100;
```

| | TPH | TPT | TPC |
|---|---|---|---|
| Tables | 1 | 1 + one per derived | One per concrete type |
| Derived columns | Nullable in the shared table | Normalised, NOT NULL possible | NOT NULL possible |
| Polymorphic query | Fastest (no joins) | Joins — slowest with many types | `UNION ALL` |
| Query for one leaf type | Filter by discriminator | Join | **Single table — fastest** |
| Keys | Identity OK | Identity OK | No shared IDENTITY: use sequence/HiLo/GUID |
| Default advice | **Start here** | Avoid for hot paths | When you mostly query leaf types |

### Value Converters

**Definition.** A value converter transforms a property value when reading/writing: `model value ⇄ provider value`. Use it for enums as strings, strongly-typed IDs, `Money`, or custom formats.

```csharp
// Enum as readable string instead of int
modelBuilder.Entity<Order>().Property(o => o.Status)
    .HasConversion<string>().HasMaxLength(20);

// Strongly-typed ID
public readonly record struct CustomerId(int Value);
modelBuilder.Entity<Customer>().Property(c => c.Id)
    .HasConversion(id => id.Value, value => new CustomerId(value));

// Convention for every property of a type
protected override void ConfigureConventions(ModelConfigurationBuilder cb) =>
    cb.Properties<CustomerId>().HaveConversion<CustomerIdConverter>();
```

:::warn Converter gotchas
Queries compare **provider values**: an encrypted-string converter makes `Where(c => c.Email.Contains("x"))` impossible to translate meaningfully. Converting collections to a delimited string needs a `ValueComparer`, otherwise changes inside the list are not detected — on EF 8+ prefer *primitive collections* (`List<string>` maps to a JSON column natively).
:::

### Global Query Filters (Soft Delete and Multi-Tenancy)

**Definition.** A global query filter is a LINQ predicate attached to an entity type in the model; EF adds it to **every** query for that type, including `Include`d navigations.

```csharp
public class ShopContext(DbContextOptions<ShopContext> options, ITenantProvider tenant)
    : DbContext(options)
{
    // (assumes Order has TenantId and IsDeleted columns in a multi-tenant deployment)
    private readonly int _tenantId = tenant.TenantId;   // evaluated per context instance

    protected override void OnModelCreating(ModelBuilder mb)
    {
        mb.Entity<Product>().HasQueryFilter(p => !p.IsDeleted);       // soft delete
        mb.Entity<Order>().HasQueryFilter(o => o.TenantId == _tenantId); // multi-tenancy
    }
}

var visible = await db.Products.ToListAsync();               // WHERE IsDeleted = 0
var all = await db.Products.IgnoreQueryFilters().ToListAsync(); // admin "recycle bin"
```

**EF Core 10: named filters.** Before EF 10 an entity had one filter and `IgnoreQueryFilters()` removed everything — dangerous when soft-delete and tenant filters share an entity. Now:

```csharp
mb.Entity<Order>()
  .HasQueryFilter("SoftDelete", o => !o.IsDeleted)
  .HasQueryFilter("Tenant", o => o.TenantId == _tenantId);

var deletedToo = await db.Orders.IgnoreQueryFilters(["SoftDelete"]).ToListAsync(); // tenant kept
```

:::warn Query-filter pitfalls
- The filter must reference a **context field/property**, not a captured local, or the value is frozen into the cached model.
- With `AddDbContextPool`, constructor-injected tenant state is reused across requests — set it per request or don't pool.
- A required navigation to a filtered principal (Order → soft-deleted Customer) makes `Include` drop the *Order* row (inner join). Make the navigation optional or filter both sides.
- Soft delete still needs a delete path: intercept `SaveChanges` and convert `Deleted` → `Modified` with `IsDeleted = true` (see the interceptors topic), plus a filtered unique index (`HasFilter("[IsDeleted] = 0")`).
:::

### JSON Columns and Primitive Collections

**Definition.** EF Core can map an object graph into a single JSON column and still query inside it (SQL Server `JSON_VALUE`/`OPENJSON`). JSON columns arrived with owned types in EF 7, EF 8 added **primitive collections** (`List<string>`, `int[]`) stored as JSON, and EF 10 adds JSON mapping for complex types and SQL Server 2025's native `json` type.

```csharp
public class ProductSpecs { public string? Color { get; set; } public int? WeightGrams { get; set; }
                            public List<string> Features { get; set; } = []; }

// Product: public ProductSpecs Specs { get; set; } = new();  public List<string> ImageUrls ...
modelBuilder.Entity<Product>().OwnsOne(p => p.Specs, b => b.ToJson());   // EF 7+
// EF 10 alternative: modelBuilder.Entity<Product>().ComplexProperty(p => p.Specs, b => b.ToJson());

var black = await db.Products
    .Where(p => p.Specs.Color == "Black" && p.ImageUrls.Count > 0)
    .ToListAsync();
```

```sql
SELECT ... FROM [Products] AS [p]
WHERE JSON_VALUE([p].[Specs], '$.Color') = N'Black'
  AND (SELECT COUNT(*) FROM OPENJSON([p].[ImageUrls]) AS [i]) > 0
```

Use JSON for flexible, document-like attributes read with the owner (product specs, audit snapshots). Don't use it for data you join, aggregate heavily or need FK integrity on — keep that relational.

:::q Owned type, complex type or separate entity - how do you decide?
If it has its own identity and lifecycle (it can be referenced, updated independently, shared), it's an entity with a relationship. If it's a value that belongs to its owner — an address, money, a date range — use a complex type on EF 8+ (or an owned type on older versions or when I need `OwnsMany` tables). If it's a flexible bag of attributes that I only read with the owner, map it to a JSON column.
:::
