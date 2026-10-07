### What EF Core Is and How It Works

**In simple words:** EF Core is an *ORM* (a tool that maps C# classes to database tables). You write C# and LINQ, and EF Core turns it into SQL. It runs the SQL and turns the rows back into objects. It also remembers what you changed and saves only those changes.

**Real-life example:** It is like a translator at a hotel desk. You speak your language (C#), the translator talks to the staff in theirs (SQL), and brings the answer back in your language.

**Interview question:** What is EF Core, and when would you use something else, like Dapper?

**Simple answer:** EF Core is Microsoft's ORM. It translates LINQ into SQL, turns rows into objects and tracks changes, so `SaveChanges` writes only what changed. I use it for most CRUD work, and use raw SQL or Dapper for a few very hot or complex reporting queries.

### The Domain Used in These Notes

**In simple words:** All EF Core examples here use one small online-shop model. A Customer has many Orders. Each Order has OrderItems, and each item points to a Product. A Product belongs to a Category and can have many Tags.

**Real-life example:** A maths teacher uses the same sample shop in every lesson, so you learn new ideas, not a new story.

**Interview question:** How would you model a simple online shop with EF Core entities?

**Simple answer:** I create classes like Customer, Order, OrderItem, Product and Category, each with an `Id` key. I add foreign key properties like `CustomerId` and navigation properties like `Order.Customer` and `Customer.Orders`. I store the unit price on OrderItem, because the product price can change later.

```csharp
public class Order
{
    public int Id { get; set; }
    public int CustomerId { get; set; }             // foreign key
    public Customer Customer { get; set; } = null!; // navigation
    public List<OrderItem> Items { get; set; } = [];
}
```

### DbContext, DbSet and the Unit of Work

**In simple words:** `DbContext` is your session with the database. Each `DbSet<T>` is like a table you can query. The context remembers your changes in memory. When you call `SaveChanges`, it writes all of them in one *transaction* (all succeed or all fail).

**Real-life example:** It is like a shopping cart. You add and remove items while you shop, and you pay for everything once at the checkout.

**Interview question:** What is DbContext, and why is it registered as Scoped?

**Simple answer:** DbContext is a unit of work: it tracks changes and saves them together in one transaction. It is Scoped, so each HTTP request gets its own context, shared by all services in that request. It is not thread-safe, so I never put it in a singleton or run two queries on it at the same time.

### Model Building Conventions

**In simple words:** EF Core builds its model from your classes by following default rules called *conventions*. A property named `Id` becomes the primary key. A property like `CustomerId` next to a `Customer` navigation becomes a foreign key. You can change any rule with attributes or the Fluent API, and the Fluent API wins.

**Real-life example:** In a library, a new book goes on the shelf by its subject code, unless the librarian says otherwise. The default rule works most of the time.

**Interview question:** What conventions does EF Core use, and which ones do you usually override?

**Simple answer:** `Id` or `<ClassName>Id` becomes the key, `DbSet` names become table names, and nullable C# types become nullable columns. I usually override `string`, which becomes `nvarchar(max)`, and `decimal`, which gets `decimal(18,2)` with a warning. I often set length and precision once for all properties in `ConfigureConventions`.

### Data Annotations vs Fluent API

**In simple words:** Both let you change the default mapping. Data Annotations are attributes on the class, like `[Required]` or `[MaxLength(200)]`. The Fluent API is C# code in `OnModelCreating` or in configuration classes. The Fluent API can configure everything, and it wins if both are used.

**Real-life example:** Annotations are sticky notes on each file folder. The Fluent API is one rule book in the manager's desk. The rule book covers more and has the final word.

**Interview question:** Data Annotations or Fluent API — which do you prefer?

**Simple answer:** The order is conventions, then annotations, then Fluent API — the last one wins. Annotations are quick but cover only some features, while Fluent API covers relationships, delete rules, filters and more. I keep mapping in `IEntityTypeConfiguration<T>` classes so entities stay clean.

### Code First vs Database First

**In simple words:** In Code First, you write C# classes first, and migrations create the database. In Database First, the database already exists, and you generate C# classes from it with `dotnet ef dbcontext scaffold`. At runtime both work the same way. Only the direction of generation is different.

**Real-life example:** Code First is drawing a house plan and then building the house. Database First is measuring a house that already exists and drawing the plan from it.

**Interview question:** Code First or Database First — which do you choose?

**Simple answer:** For new projects I choose Code First, because the C# model is the source of truth and migrations keep schema changes in source control. For an existing database owned by DBAs, I use Database First and scaffold it. I put my own logic in separate partial classes, so re-scaffolding does not delete it.

### Migrations Workflow and Commands

**In simple words:** A migration is a C# file that describes one change to the database schema. EF creates it by comparing your current model with a saved snapshot. `Up()` applies the change and `Down()` undoes it. Applied migrations are recorded in the `__EFMigrationsHistory` table.

**Real-life example:** It is like a renovation log for a building. Each page says what changed and how to undo it, and the log shows which pages are already done.

**Interview question:** How do migrations work, and what do you check before applying one?

**Simple answer:** I run `migrations add` to create the change and `database update` to apply it. I always read the generated code, because EF sees a rename as drop plus add, which loses data, so I change it to `RenameColumn`. I never edit a migration that is already applied somewhere; I add a new one.

```bash
dotnet ef migrations add AddProductTags
dotnet ef database update
dotnet ef migrations script --idempotent -o deploy.sql
```

### Applying Migrations in Dev and CI/CD

**In simple words:** In development you can run `database update` or call `Migrate()` at startup. In production that is risky: many app copies can start at once, and the app needs extra rights. A safer way is to build an *idempotent* script (safe to run twice) or a migration bundle (one executable) in CI. The pipeline runs it once, before the new app version goes live.

**Real-life example:** Before a shop opens with a new layout, one team moves the shelves at night. You do not ask every cashier to move shelves when they arrive.

**Interview question:** How do you deploy EF Core migrations safely to production?

**Simple answer:** CI builds an idempotent script or a migration bundle, it is reviewed, and the pipeline runs it once before the app deploys. I avoid `Migrate()` on startup with many instances. I keep changes backward compatible: add the new column first, switch the code, and drop the old column in a later release.

### Data Seeding

**In simple words:** Seeding means putting starting data into the database. `HasData` keeps the seed inside the model, so migrations insert it, and it needs fixed key values. `UseSeeding` and `UseAsyncSeeding` (EF Core 9) run your own code after migrations. That code must be safe to run many times.

**Real-life example:** A new restaurant prints its fixed menu once (`HasData`). Every morning the manager checks the fridge and orders only what is missing (`UseSeeding`).

**Interview question:** What is the difference between HasData and UseSeeding?

**Simple answer:** `HasData` is part of the model and tracked by migrations, so it suits small fixed lists like statuses or countries, with explicit keys. `UseSeeding` runs normal code after migrations, so it can check for existing rows first. I use it for test data or data that depends on other rows.

```csharp
modelBuilder.Entity<Category>().HasData(
    new Category { Id = 1, Name = "Electronics" },
    new Category { Id = 2, Name = "Books" });
```

### Relationship Basics: Principal, Dependent, FK, Navigations

**In simple words:** A relationship links two entities with a *foreign key* (FK, a column that points to another table's key). The principal is the "parent", like `Customer`. The dependent is the "child" that holds the FK, like `Order.CustomerId`. Navigation properties let you move between them in C#, like `order.Customer` or `customer.Orders`.

**Real-life example:** A child's school form has the parent's phone number on it. The child is the dependent, the phone number is the foreign key, and the parent is the principal.

**Interview question:** What are principal and dependent entities in EF Core?

**Simple answer:** The principal has the key that is referenced, and the dependent stores the foreign key. A reference navigation points to one entity, and a collection navigation points to many. This setup decides the database schema, the joins and what happens on delete.

### One-to-Many

**In simple words:** One-to-many is the most common relationship. One customer has many orders, but each order has one customer. The foreign key (`CustomerId`) lives on the "many" side. EF finds it by convention, or you set it with `HasOne().WithMany()`.

**Real-life example:** One mother can have many children, but each child has one mother. Each child's record stores the mother's ID.

**Interview question:** How do you configure a one-to-many relationship?

**Simple answer:** I put a foreign key property and a reference navigation on the dependent, and a collection on the principal, so EF finds it by convention. To be explicit, I use `HasOne(...).WithMany(...).HasForeignKey(...)`. EF also creates an index on the FK column.

### One-to-One

**In simple words:** In one-to-one, each principal has at most one dependent. Both sides have a single navigation, so you must tell EF which side holds the foreign key. Often the dependent's primary key is also its foreign key. If the FK is a separate column, EF adds a unique index on it.

**Real-life example:** One person has one passport, and one passport belongs to one person. The passport carries the person's ID number, not the other way round.

**Interview question:** How do you configure one-to-one, and when would you use it?

**Simple answer:** I use `HasOne().WithOne()` with `HasForeignKey<TDependent>()` to say which side holds the key. I use it to move large or rarely read columns out of a busy table. If the data has no identity and always goes with the owner, an owned or complex type is simpler.

### Many-to-Many

**In simple words:** Many-to-many means each side can have many of the other. A product has many tags, and a tag is on many products. The database needs a *join table* (a middle table holding both keys). EF Core 5+ creates it for you when both sides have collections.

**Real-life example:** Students and courses: one student takes many courses, and one course has many students. The school keeps an enrolment list that pairs them.

**Interview question:** How do you configure a many-to-many relationship?

**Simple answer:** I add collections on both sides and use `HasMany().WithMany()`, and EF creates the join table. If the link has its own data, like who added a tag and when, I add an explicit join entity with `UsingEntity<T>`. Or I model it as two one-to-many relationships, like Order and Product through OrderItem.

### Foreign Keys, Shadow FKs and Required vs Optional

**In simple words:** A *shadow property* exists in the EF model and the database, but not in your class. If you have a navigation but no FK property, EF creates a shadow FK. A required relationship has a non-nullable FK (`int`). An optional one has a nullable FK (`int?`), and this also changes the default delete behavior.

**Real-life example:** A shadow property is like a note the receptionist writes about you in her own register. It is not on your ID card, but the office still keeps it.

**Interview question:** What is a shadow property, and how do required and optional relationships differ?

**Simple answer:** A shadow property is mapped by EF but not on the class; I read it with `EF.Property<T>(entity, "Name")`. A required relationship uses a non-nullable FK and defaults to cascade delete; an optional one uses a nullable FK and defaults to `ClientSetNull`. I prefer explicit FK properties, so I can set `CustomerId` without loading the customer.

### Delete Behaviors

**In simple words:** `OnDelete` decides what happens to children when you delete a parent. It controls the database constraint and also what EF does to children it has loaded. `Cascade` deletes them, `SetNull` clears their FK, and `Restrict` blocks the delete. Required relationships default to `Cascade`, optional ones to `ClientSetNull`.

**Real-life example:** If a school closes a class, it can send the students home (cascade), mark them "no class yet" (set null), or refuse to close the class while students are in it (restrict).

**Interview question:** What is the default delete behavior in EF Core?

**Simple answer:** For a required relationship it is `Cascade`: deleting the parent deletes the children, and the database has `ON DELETE CASCADE`. For an optional one it is `ClientSetNull`: EF sets the FK to null only on loaded children. The database rule is `NO ACTION`, so children that are not loaded make the delete fail.

### Owned Types and Complex Types (Value Objects)

**In simple words:** A *value object* is defined only by its values, like an Address or Money. It has no ID of its own. EF Core maps it as an owned type (`OwnsOne`) or, from EF Core 8, a complex type (`ComplexProperty`). By default, its columns live inside the owner's table.

**Real-life example:** The address printed on a parcel is not a separate thing with its own ID. It is just part of the parcel, and two parcels can show the same address.

**Interview question:** Owned type, complex type or separate entity — how do you decide?

**Simple answer:** If it has its own identity and can be changed or shared on its own, it is an entity with a relationship. If it is a value that belongs to its owner, like an address, I use a complex type on EF 8+, or an owned type on older versions or when I need `OwnsMany`. Owned types still have a hidden key; complex types do not.

### Inheritance: TPH, TPT, TPC

**In simple words:** Database tables have no inheritance, so EF offers three ways to store a class hierarchy. TPH (Table per Hierarchy) puts all types in one table with a *discriminator* (a "type" column). TPT (Table per Type) uses a base table plus one table per derived type, joined by key. TPC (Table per Concrete type) gives each concrete class its own complete table.

**Real-life example:** Storing card and UPI payments. TPH is one notebook with a "type" column. TPT is a main notebook plus extra notebooks for card and UPI details. TPC is a separate complete notebook for each payment type.

**Interview question:** Which inheritance strategy would you choose, and why?

**Simple answer:** I start with TPH, the default, because it needs no joins and is fast; but derived-type columns must be nullable. TPT needs joins and gets slow with many types. TPC is fastest when I mostly query one concrete type, but it cannot share an IDENTITY key, so I use a sequence or GUIDs.

### Value Converters

**In simple words:** A *value converter* changes a property's value when EF reads or writes it. For example, it can save an enum as text instead of a number. It can also map a strongly typed ID, like `CustomerId`, to a plain `int` column.

**Real-life example:** A currency exchange desk at the airport. You hand in one currency, the bank stores another, and you get your own currency back when you return.

**Interview question:** What are value converters, and what should you be careful about?

**Simple answer:** They convert between the C# value and the database value, for example `HasConversion<string>()` for enums. Queries compare the stored value, so with an encryption converter a search like `Contains` cannot work correctly. For a list saved as one string I need a `ValueComparer`, but on EF 8+ I prefer primitive collections.

```csharp
modelBuilder.Entity<Order>()
    .Property(o => o.Status)
    .HasConversion<string>();   // stored as "Paid", not 1
```

### Global Query Filters (Soft Delete and Multi-Tenancy)

**In simple words:** A global query filter is a `Where` condition that EF adds to every query for an entity. It is used for *soft delete* (hide rows marked `IsDeleted`) and *multi-tenancy* (show only the current client company's rows). `IgnoreQueryFilters()` turns it off for one query. EF Core 10 adds named filters, so you can turn off just one of them.

**Real-life example:** A library computer hides books marked "lost". Only the librarian can switch to the "show everything" view.

**Interview question:** How do you implement soft delete with EF Core?

**Simple answer:** I add an `IsDeleted` column and `HasQueryFilter(p => !p.IsDeleted)`, so normal queries skip deleted rows. A `SaveChanges` interceptor turns each delete into an update that sets `IsDeleted = true`. For tenant filters, the filter must read a field on the context, not a local variable, or the value is frozen in the cached model.

```csharp
modelBuilder.Entity<Product>().HasQueryFilter(p => !p.IsDeleted);
var all = await db.Products.IgnoreQueryFilters().ToListAsync();
```

### JSON Columns and Primitive Collections

**In simple words:** EF Core can store a small object, like product specs, in one JSON column and still filter on values inside it. From EF Core 8, simple lists like `List<string>` (*primitive collections*) are also stored as JSON. On SQL Server, EF uses functions like `JSON_VALUE` and `OPENJSON` to query them.

**Real-life example:** A product box with a leaflet inside listing colour, weight and features. You keep the leaflet in the box instead of building a separate shelf for each detail.

**Interview question:** When would you use a JSON column instead of separate tables?

**Simple answer:** I use JSON for flexible, document-like data that I read together with its owner, like product specs or audit snapshots. I do not use it for data I join, sum up a lot, or need foreign keys on. That data stays in normal tables.

### IQueryable, Deferred Execution and Translation

**In simple words:** `DbSet<T>` is an `IQueryable<T>`. Calls like `Where` and `OrderBy` only build a description of the query (an *expression tree*). Nothing runs until you call something like `ToListAsync`, `FirstAsync` or `CountAsync`. Then EF turns the whole chain into one SQL statement.

**Real-life example:** In a restaurant, you write your order on a slip. The kitchen starts cooking only when you hand over the full slip, not after each line.

**Interview question:** What is the difference between IQueryable and IEnumerable in EF Core?

**Simple answer:** `IQueryable` builds a query that runs in the database, while `IEnumerable` runs in memory on rows already loaded. If I call `AsEnumerable()` or `ToList()` too early, EF loads the whole table and filters in C#. So I keep filters, sorting and paging on `IQueryable`.

```csharp
var q = db.Orders.Where(o => o.Total > 1000); // no SQL yet
string sql = q.ToQueryString();               // see the SQL
var list = await q.ToListAsync();             // SQL runs here
```

### Filtering, Sorting and Client Evaluation

**In simple words:** Most LINQ methods translate to SQL: `Where`, `OrderBy`, `Contains` (as `IN` or `LIKE`), and `GroupBy` with `Sum` or `Count`. Since EF Core 3.0, C# code that cannot become SQL is allowed only in the final `Select`. Anywhere else, EF throws a "could not be translated" error instead of quietly loading everything.

**Real-life example:** A bank teller handles standard requests at the counter. If you ask for something the counter cannot do, the teller clearly says no, instead of handing you the whole vault to search.

**Interview question:** What happens when EF Core cannot translate a LINQ expression?

**Simple answer:** If it is in the last `Select`, EF runs that part in C# after the SQL returns; anywhere else it throws an exception. I fix it by rewriting the condition, using `EF.Functions`, a computed column or raw SQL. I never add `ToList()` before it, because that loads the whole table.

### Include, ThenInclude and Filtered Include

**In simple words:** `Include` loads related data in the same query. This is called *eager loading*. `ThenInclude` goes one level deeper, like order, then items, then product. Since EF Core 5, you can filter, sort and limit an included collection — a *filtered include*.

**Real-life example:** When you collect a parcel, you get the box and everything inside at once. You do not go back to the counter for each item.

**Interview question:** What does Include do, and what is a filtered include?

**Simple answer:** `Include` adds JOINs so related entities come back in one query, and `ThenInclude` loads deeper levels. A filtered include, like `Include(c => c.Orders.Where(...).Take(5))`, loads only some children. With tracking, other children already in the context can still appear, so I use it with `AsNoTracking`.

```csharp
var order = await db.Orders
    .Include(o => o.Items).ThenInclude(i => i.Product)
    .SingleAsync(o => o.Id == id);
```

### Single Query vs Split Query (Cartesian Explosion)

**In simple words:** By default, EF loads all includes in one SQL query with JOINs. If you include two collections, rows multiply: 50 items × 10 payments = 500 rows. This is the *cartesian explosion*. `AsSplitQuery()` runs one query per collection instead, so data is not repeated.

**Real-life example:** If you write one list pairing every shirt with every pair of trousers, the list grows very fast. Two separate lists are much shorter.

**Interview question:** When would you use AsSplitQuery?

**Simple answer:** I use it when a query includes several or large collections, because JOINs would repeat data many times. The cost is more round trips, and the data can change between the queries. With paging, it needs a unique, stable `OrderBy`.

### Projection with Select to DTOs

**In simple words:** *Projection* means using `Select` to get only the columns you need, straight into a DTO (a simple data class). You do not load full entities or use `Include`. For read endpoints, it is usually the best single speed-up.

**Real-life example:** You ask the librarian only for a book's title and author, not the whole book. You carry less and get it faster.

**Interview question:** Why is projection to DTOs often better than Include?

**Simple answer:** It reads fewer columns, so less data travels, and DTOs are never tracked, so it uses less memory. It also avoids serialization loops, and an index can cover the whole query. I use navigations inside `Select`, and EF builds the joins, so `Include` is not needed.

```csharp
var rows = await db.Orders
    .Select(o => new { o.Id, Customer = o.Customer.Name, Items = o.Items.Count })
    .ToListAsync();
```

### Pagination: Offset vs Keyset

**In simple words:** Offset paging uses `Skip` and `Take`. It is simple and supports "go to page 37", but the database still reads all skipped rows, so deep pages are slow. Keyset paging remembers the last row and asks for rows after it. It uses an index *seek* (a direct jump), so every page is fast.

**Real-life example:** Offset is counting 500 pages from the start of a book each time. Keyset is using a bookmark and opening the book right where you stopped.

**Interview question:** How would you paginate an orders API with millions of rows?

**Simple answer:** I use keyset paging ordered by `(OrderDate, Id)` with a matching index, and return a cursor for the next page, so every page costs the same. If the UI needs page numbers, I use `Skip/Take` with a stable `OrderBy` and a maximum page size. I also project to a DTO and use `AsNoTracking`.

```csharp
var next = await db.Orders
    .Where(o => o.OrderDate < lastDate ||
               (o.OrderDate == lastDate && o.Id < lastId))
    .OrderByDescending(o => o.OrderDate).ThenByDescending(o => o.Id)
    .Take(20).ToListAsync();
```

### Raw SQL: FromSql, SqlQuery, ExecuteSql

**In simple words:** Sometimes you need your own SQL. `FromSql` returns entities, and you can add LINQ after it. `Database.SqlQuery<T>` returns other types or single values, and `ExecuteSql` runs commands like UPDATE. With interpolated strings, EF turns each `{value}` into a SQL parameter, which protects you from *SQL injection* (attackers changing your SQL).

**Real-life example:** Most days you order from the menu (LINQ). For a special dish you talk to the chef directly (raw SQL), but you still follow the kitchen's safety rules (parameters).

**Interview question:** How do you run raw SQL safely in EF Core?

**Simple answer:** I use `FromSql`, `SqlQuery` or `ExecuteSql` with string interpolation, so each `{value}` becomes a parameter. I avoid `FromSqlRaw` with string concatenation. For entities, the SQL must return all mapped columns with matching names.

```csharp
var items = await db.Products
    .FromSql($"SELECT * FROM Products WHERE Price > {minPrice}")
    .ToListAsync();
```

### Bulk Updates and Deletes: ExecuteUpdate / ExecuteDelete

**In simple words:** EF Core 7 added `ExecuteUpdateAsync` and `ExecuteDeleteAsync`. They turn a LINQ query directly into one UPDATE or DELETE statement and run it right away. They do not load entities or use the change tracker. That makes them very fast for many rows.

**Real-life example:** A shop changes all prices in one section with one announcement, instead of re-labelling each product by hand.

**Interview question:** When would you use ExecuteUpdate instead of SaveChanges?

**Simple answer:** For changes to many rows, like price updates or deleting old carts, where loading entities would waste time; it runs one SQL statement with no tracking. The trade-off is that `SaveChanges` interceptors and concurrency checks do not run. Also, tracked entities already in memory become out of date.

```csharp
await db.Products
    .Where(p => p.CategoryId == 3)
    .ExecuteUpdateAsync(s => s.SetProperty(p => p.Price, p => p.Price * 1.10m));
```

### What the Change Tracker Is

**In simple words:** The *change tracker* is the part of `DbContext` that remembers every entity it loaded or added. It stores each entity's state and a copy of its original values. On `SaveChanges`, it compares current values with the originals. Then it writes only what changed.

**Real-life example:** A teacher keeps a photocopy of your test before you correct it. Later she compares both copies and sees exactly which answers you changed.

**Interview question:** What is the change tracker, and why does it matter?

**Simple answer:** It keeps tracked entities, their states and their original values. That is why "load, change a property, `SaveChanges`" works without calling `Update`. It costs memory and CPU per entity, so for read-only queries I turn it off with `AsNoTracking`.

### Entity States, Walkthrough

**In simple words:** Every entity has a state. `Detached` means the context does not know it. `Added` will be inserted, `Modified` will be updated, `Deleted` will be removed, and `Unchanged` needs nothing. After a successful save, Added and Modified become Unchanged, and Deleted becomes Detached.

**Real-life example:** Parcels at a post office: new (to send), on the shelf (unchanged), changed address (to update), cancelled (to remove), or not in the system at all (detached).

**Interview question:** What entity states exist, and what does SaveChanges do with each?

**Simple answer:** Added becomes INSERT, Modified becomes UPDATE of only the changed columns, and Deleted becomes DELETE; Unchanged and Detached do nothing. After saving, Added and Modified become Unchanged, and Deleted becomes Detached. I can check a state with `db.Entry(entity).State`.

```csharp
var p = await db.Products.FirstAsync(x => x.Id == 7); // Unchanged
p.Price = 899m;                                        // Modified
await db.SaveChangesAsync();                           // UPDATE Price only
```

### Identity Resolution

**In simple words:** A tracking context keeps only one object per primary key. If you query the same row twice, you get the same object back. The second query still runs SQL, but it does not overwrite your unsaved changes. If you attach another object with the same key, EF throws an error.

**Real-life example:** A school keeps only one file per student number. If someone brings a second file for the same number, the office refuses it.

**Interview question:** What is identity resolution in EF Core?

**Simple answer:** Within one tracking context, each key maps to one object. Querying the row again returns the tracked object and keeps my in-memory changes. Attaching a second object with the same key throws "another instance with the same key value is already being tracked".

### DetectChanges and Its Cost

**In simple words:** `DetectChanges` walks through every tracked entity and compares each property with its original value. It runs automatically on `SaveChanges`, `Entry()` and some other calls. With thousands of tracked entities, this gets slow, especially when it runs again and again.

**Real-life example:** Checking every item in a warehouse by hand each time one box arrives. With ten items it is fine; with ten thousand it takes all day.

**Interview question:** How do you make large inserts faster with EF Core?

**Simple answer:** I insert in chunks, call `SaveChanges` per chunk, and then `ChangeTracker.Clear()` to keep the tracker small. I can also turn off `AutoDetectChangesEnabled` during the loop. For really big loads I use `ExecuteUpdate/Delete`, `SqlBulkCopy` or a bulk library.

```csharp
foreach (var chunk in products.Chunk(1000))
{
    db.Products.AddRange(chunk);
    await db.SaveChangesAsync();
    db.ChangeTracker.Clear();
}
```

### AsNoTracking, AsNoTrackingWithIdentityResolution, AsTracking

**In simple words:** `AsNoTracking()` loads entities without tracking them. It is faster and uses less memory, but `SaveChanges` will not see your edits. `AsNoTrackingWithIdentityResolution()` also skips tracking, but still keeps one object per key inside that query. `AsTracking()` turns tracking on when no-tracking is the default.

**Real-life example:** Reading a library book in the reading room (no tracking) versus borrowing it with your card (tracking). The library records only the borrowed books.

**Interview question:** When do you use AsNoTracking and AsNoTrackingWithIdentityResolution?

**Simple answer:** `AsNoTracking` is for read-only queries like lists and reports. `AsNoTrackingWithIdentityResolution` is for read-only data where the same related entity appears many times: 100 orders from 3 customers give 3 customer objects, not 100. In read-heavy apps I can make no-tracking the default and use `AsTracking()` for writes.

### When to Use Tracking vs AsNoTracking

**In simple words:** Use tracking when you load, change and save data in the same request. Use `AsNoTracking` or a `Select` projection when you only read, like lists, detail pages and reports. To change many rows at once, use `ExecuteUpdate`.

**Real-life example:** To check a train timetable, you do not need a ticket. You need a ticket only when you actually travel.

**Interview question:** When should you use tracking, and when AsNoTracking?

**Simple answer:** Reads use projections or `AsNoTracking`; writes use tracking, so change detection updates only the changed columns. Data I cache in memory must be no-tracking, so it is not tied to a context. Bulk changes use `ExecuteUpdate`.

### Disconnected Entities: Update() vs Attach() vs Modifying a Tracked Entity

**In simple words:** In a Web API, the entity arrives in the request body, so the context does not track it. You can load the row and copy in the new values (only changed columns are updated). `Update()` marks every property as modified, without a SELECT. `Attach()` marks it unchanged, and then you flag only the properties to update.

**Real-life example:** Fixing a form: get the original and correct only the wrong fields, rewrite the whole form from memory, or attach a note saying "only the phone number changed".

**Interview question:** What is the difference between Update() and Attach()?

**Simple answer:** `Attach` tracks the entity as `Unchanged`, so nothing is written unless I flag properties — good for partial updates. `Update` marks all properties modified and writes every column, so missing values overwrite real data. In most APIs I load the entity and apply the DTO, so only real changes are saved.

```csharp
var stub = new Product { Id = dto.Id, Price = dto.Price };
db.Products.Attach(stub);
db.Entry(stub).Property(p => p.Price).IsModified = true;
await db.SaveChangesAsync(); // UPDATE ... SET Price only
```

### SaveChanges Internals

**In simple words:** `SaveChanges` first detects changes and runs *interceptors* (hooks like audit code). It orders commands so parents are inserted before children. It wraps everything in one transaction and sends commands in batches. Then it reads back generated values like IDs, checks concurrency, commits, and marks entities `Unchanged`.

**Real-life example:** A delivery company loads your parcels in the right order, ships them in one truck, and gives you tracking numbers.

**Interview question:** Is SaveChanges transactional, and what does it do?

**Simple answer:** Yes, each `SaveChanges` runs all its commands in one transaction, so all succeed or none do. It orders commands by dependency, batches them to save round trips, and reads back identity values so `order.Id` is filled in. If a concurrency check fails, it throws `DbUpdateConcurrencyException` and rolls back.

### Explicit Transactions and Execution Strategies

**In simple words:** Use an explicit transaction when several `SaveChanges` calls, raw SQL or `ExecuteUpdate` must succeed or fail together. With retry on failure on (`EnableRetryOnFailure`), EF cannot retry half of a transaction you started yourself. So you wrap the whole transaction in an *execution strategy* (a retry helper).

**Real-life example:** Moving money between two bank accounts: the debit and credit must both happen or both be cancelled. If the line drops, the bank repeats the whole transfer, not just half.

**Interview question:** How do you use transactions when connection resiliency is enabled?

**Simple answer:** I call `CreateExecutionStrategy()` and put all the work inside `strategy.ExecuteAsync`. Inside it, I begin the transaction, do the work and commit. The block may run more than once, so it must be safe to repeat.

```csharp
var strategy = db.Database.CreateExecutionStrategy();
await strategy.ExecuteAsync(async () =>
{
    await using var tx = await db.Database.BeginTransactionAsync();
    await db.SaveChangesAsync();
    await tx.CommitAsync();
});
```

### Optimistic Concurrency with RowVersion

**In simple words:** *Optimistic concurrency* assumes conflicts are rare, so it does not lock rows. Instead, EF adds a version value, like `RowVersion`, to the `WHERE` of each UPDATE or DELETE. If someone else changed the row first, 0 rows are updated. Then EF throws `DbUpdateConcurrencyException`.

**Real-life example:** Two support agents open the same order. Agent A cancels it. Agent B then tries to ship it from an old screen, and the system says "this order changed — please reload".

**Interview question:** How does EF Core handle concurrency conflicts?

**Simple answer:** I add a `rowversion` column marked `[Timestamp]` or `IsRowVersion()`, and EF adds it to the WHERE clause. Zero affected rows raises `DbUpdateConcurrencyException`. I catch it, read the current database values, and then retry, merge, or return HTTP 409 to the client.

```sql
UPDATE Orders SET Status = @p0
WHERE Id = @p1 AND RowVersion = @p2;  -- 0 rows = conflict
```

### SaveChanges Interceptors for Audit and Soft Delete

**In simple words:** An *interceptor* is a hook that runs when EF does something. A `SaveChangesInterceptor` runs before or after `SaveChanges`. It is a good place for rules that apply everywhere, like filling `CreatedBy` and `UpdatedUtc`, or turning a delete into a soft delete.

**Real-life example:** A guard at the office exit stamps the date and your name on every box you carry out. You do not have to remember to do it yourself.

**Interview question:** How would you add audit fields automatically in EF Core?

**Simple answer:** I write a `SaveChangesInterceptor` and override `SavingChangesAsync`. It loops over tracked entries: Added gets created fields, Modified gets updated fields, and for soft delete it changes Deleted to Modified with `IsDeleted = true`. Interceptors do not run for `ExecuteUpdate/Delete` or raw SQL.

### The N+1 Query Problem

**In simple words:** N+1 means one query loads a list, and then one more query runs for each item. With 100 orders, you get 101 database calls. Each call is fast, but together they make the page slow. Lazy loading or a query inside a loop usually causes it.

**Real-life example:** A waiter takes one person's order, walks to the kitchen, comes back for the next person, and walks again. Taking the whole table's order in one trip is much faster.

**Interview question:** What is the N+1 problem, and how do you fix it?

**Simple answer:** I spot it in the SQL log or APM: the same query repeats with different parameters. I fix it with `Include`, with a `Select` projection (usually best for reads), or by loading related rows in one `IN` query. I also turn off lazy loading in APIs, so it cannot happen silently.

```csharp
// one query instead of 1 + N
var rows = await db.Orders
    .Select(o => new { o.Id, o.Customer.Name, Items = o.Items.Count })
    .ToListAsync();
```

### Eager vs Lazy vs Explicit Loading

**In simple words:** Eager loading gets related data with the main query, using `Include`. Lazy loading gets it automatically the first time you touch a navigation property; it needs proxies and `virtual` properties. Explicit loading gets it only when you call `Entry(x).Collection(...).LoadAsync()`.

**Real-life example:** Eager is ordering the full meal at once. Lazy is the waiter bringing a dish only when you reach for it. Explicit is you deciding, dish by dish, what to order next.

**Interview question:** What is the difference between eager, lazy and explicit loading?

**Simple answer:** Eager uses `Include` and loads everything in one query. Lazy loads on first access; it is easy but causes N+1 and blocking (synchronous) database calls, so I avoid it in APIs. Explicit loads on demand with `LoadAsync`, which is useful when I need the data only in some cases.

### Logging and Inspecting Generated SQL

**In simple words:** You should always check the SQL that EF creates. `LogTo` or normal logging can print every SQL command. `ToQueryString()` shows the SQL of one query without running it. `TagWith("name")` adds a comment to the SQL, so you can find it later in database tools.

**Real-life example:** It is like reading the receipt after shopping. It shows exactly what you paid for, so you can find mistakes.

**Interview question:** How do you see the SQL that EF Core generates?

**Simple answer:** In development I use `LogTo`, or set the `Microsoft.EntityFrameworkCore.Database.Command` log level to Information. I use `ToQueryString()` for one query and `TagWith` to find queries in Query Store. `EnableSensitiveDataLogging` shows parameter values, so I use it only in development.

### Indexes

**In simple words:** An *index* helps the database find rows fast, like the index at the back of a book. EF creates indexes for foreign keys automatically. For other columns you filter, sort or look up by, you add indexes yourself with `HasIndex`. Indexes speed up reads, but they slow writes a little and use space.

**Real-life example:** A phone's contact list sorted by name. You jump straight to "R" instead of scrolling through every contact.

**Interview question:** How do you define indexes in EF Core?

**Simple answer:** I use `HasIndex` in the Fluent API or `[Index]` on the class, and can make it unique, composite, filtered (`HasFilter`) or covering (`IncludeProperties`). I check the execution plan to confirm the index is used. I avoid functions on indexed columns, like `OrderDate.Year == 2026`, and use a date range instead.

### Compiled Queries

**In simple words:** EF caches translated queries, but each run still has to find the query in the cache. `EF.CompileAsyncQuery` does that work once and gives you a ready *delegate* (a function stored in a variable). It gives a small speed gain for queries that run very often.

**Real-life example:** A coffee shop saves your usual order. The barista does not need to ask and write it down each time.

**Interview question:** What are compiled queries, and when do you use them?

**Simple answer:** They prepare a LINQ query once, so later runs skip the cache lookup. I use them only on proven hot paths, after measuring. Projections, indexes and fixing N+1 usually give much bigger wins.

### Batching and Bulk Operations

**In simple words:** `SaveChanges` already groups many inserts, updates and deletes into a few round trips. This is called *batching*. For really large jobs, like 100,000 rows, you need set-based or bulk tools instead.

**Real-life example:** A post office sends letters in sacks, not one by one. For a whole truckload, it uses a special freight service.

**Interview question:** How do you insert or update a very large number of rows with EF Core?

**Simple answer:** For updates and deletes I use `ExecuteUpdateAsync` and `ExecuteDeleteAsync`, which are single statements. For huge inserts I use `SqlBulkCopy` or a library like EFCore.BulkExtensions. If I must use `SaveChanges`, I save in chunks and call `ChangeTracker.Clear()` between them.

### Context Pooling, Resiliency and Async

**In simple words:** *Context pooling* (`AddDbContextPool`) reuses `DbContext` objects instead of creating new ones. *Connection resiliency* (`EnableRetryOnFailure`) retries short-lived errors, like during an Azure SQL failover. Async methods free threads while the database works. One context can run only one operation at a time.

**Real-life example:** A bike-sharing station: you take a bike, return it, and the next person reuses it. Nobody builds a new bike for each trip.

**Interview question:** What is DbContext pooling, and what should you watch out for?

**Simple answer:** Pooling keeps reset contexts ready, so busy APIs save setup work on each request. The risk is per-request state, like a tenant ID set in the constructor, which can leak to the next request. I use async methods everywhere, never `.Result`, and for parallel work I create separate contexts with a factory.

### Common Query Anti-Patterns

**In simple words:** Some LINQ habits waste time. Use `AnyAsync` instead of `CountAsync() > 0`. Filter in the query, not after `ToListAsync`. Use `Select` instead of loading full entities to show a few columns, and always page large results.

**Real-life example:** To know if a shop has milk, you ask "Is there any?" You do not ask the shopkeeper to count every bottle first.

**Interview question:** What is the difference between Find and FirstOrDefault?

**Simple answer:** `Find` searches by primary key, and if the entity is already tracked, it returns it without a database call. `FirstOrDefault` always runs a query, accepts any condition, and supports `Include`, `AsNoTracking` and projections. I use `Find` to load by key for an update, and `FirstOrDefault` for other reads.

### Repository Pattern over EF Core: the Debate

**In simple words:** The repository pattern hides data access behind an interface, like `IOrderRepository`. But `DbSet` is already a repository, and `DbContext` is already a unit of work. A generic `IRepository<T>` often hides useful EF features, like `Include`, projections and `AsNoTracking`.

**Real-life example:** Hiring an assistant to pass your notes to a translator, when the translator is already in the room. The assistant adds a step and can lose details.

**Interview question:** Do you need the repository pattern with EF Core?

**Simple answer:** Not as a generic wrapper. For reads I query `DbContext` directly with projections. For a rich domain I may use specific repositories per aggregate (a group of objects saved together), and I test data access against a real database instead of mocking repositories.
