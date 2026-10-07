## LINQ

### LINQ basics: query vs method syntax

**Definition.** LINQ (Language Integrated Query) is a set of query operators plus language support (lambdas, extension methods, query expressions) that lets you query *any* data source — in-memory collections, SQL through EF Core, XML, JSON — with one uniform API.

**Why it matters.** It replaces nested `foreach` + `if` + temp lists with declarative code. It is asked in almost every .NET interview, usually as "write this query" followed by "when does it actually execute?".

**How it works.** The operators are extension methods in `System.Linq`. There are two families:

- `Enumerable` — works on `IEnumerable<T>`, takes **delegates** (`Func<T,bool>`), runs in your process (*LINQ to Objects*).
- `Queryable` — works on `IQueryable<T>`, takes **expression trees** (`Expression<Func<T,bool>>`); a provider translates them (EF Core → SQL).

Query syntax is just sugar: the compiler rewrites it into method calls.

| | Query syntax | Method (fluent) syntax |
|---|---|---|
| Look | SQL-like (`from … where … select`) | Chained extension methods + lambdas |
| Coverage | Subset of operators | Every operator |
| Shines at | `join`, `let`, several `from` clauses | Short chains, `Count`, `Take`, `Distinct`, `First` |
| Compiled to | Method calls | Itself |

All examples in this section use this dataset (Dev has no orders on purpose):

```csharp
record Customer(int Id, string Name, string City);
record Product(int Id, string Name, string Category, decimal Price);
record OrderLine(int ProductId, int Qty);
record Order(int Id, int CustomerId, string Status, decimal Total, List<OrderLine> Lines);

var customers = new List<Customer> {
    new(1, "Asha", "Pune"), new(2, "Ben", "Delhi"),
    new(3, "Chen", "Pune"), new(4, "Dev", "Mumbai") };
var products = new List<Product> {
    new(1, "Laptop", "Electronics", 900m), new(2, "Mouse", "Electronics", 20m),
    new(3, "Desk", "Furniture", 250m),     new(4, "Chair", "Furniture", 120m) };
var orders = new List<Order> {
    new(101, 1, "Paid",      920m,  [new(1, 1), new(2, 1)]),
    new(102, 1, "Shipped",   250m,  [new(3, 1)]),
    new(103, 2, "Paid",      240m,  [new(4, 2)]),
    new(104, 3, "Cancelled", 20m,   [new(2, 1)]),
    new(105, 3, "Paid",      1020m, [new(1, 1), new(4, 1)]) };
```

The same query in both syntaxes:

```csharp
var q1 = from c in customers
         where c.City == "Pune"
         orderby c.Name
         select c.Name;

var q2 = customers.Where(c => c.City == "Pune")
                  .OrderBy(c => c.Name)
                  .Select(c => c.Name);
// Output (both): Asha, Chen
```

`let` is where query syntax is genuinely nicer — it names an intermediate value once:

```csharp
var q = from o in orders
        let tax = o.Total * 0.18m
        where tax > 100
        select new { o.Id, tax };
// Output: { 101, 165.60 }, { 105, 183.60 }
```

:::tip What interviewers look for
Say "query syntax compiles to method syntax; I use whichever reads better, usually method syntax, and query syntax for joins and `let`." Knowing that the two are equivalent is the point.
:::

### Filtering and projection: Where, Select, SelectMany

**Definition.** `Where` keeps elements matching a predicate. `Select` transforms each element into something else (projection). `SelectMany` projects each element to a *sequence* and flattens all the sequences into one.

```csharp
var bigPaid = orders.Where(o => o.Status == "Paid" && o.Total > 500);
// Output: orders 101 (920), 105 (1020)

var dtos = orders.Select(o => new { o.Id, Label = $"#{o.Id} - {o.Status}" });
var indexed = customers.Select((c, i) => $"{i + 1}. {c.Name}");   // 1. Asha, 2. Ben ...

// Select = nested; SelectMany = flat
var nested = orders.Select(o => o.Lines);              // IEnumerable<List<OrderLine>> (5 lists)
var flat   = orders.SelectMany(o => o.Lines);          // IEnumerable<OrderLine> (7 lines)

var rows = orders.SelectMany(o => o.Lines,
                             (o, l) => new { o.Id, l.ProductId, l.Qty });
// Output: (101,1,1) (101,2,1) (102,3,1) (103,4,2) (104,2,1) (105,1,1) (105,4,1)
```

`OfType<T>()` filters by runtime type; `Cast<T>()` converts and throws on mismatch. Use `OfType` for mixed `object` lists and non-generic collections.

:::example Real-world example
"Show every product ever sold with total quantity": `orders.SelectMany(o => o.Lines).GroupBy(l => l.ProductId).Select(g => new { g.Key, Qty = g.Sum(l => l.Qty) })`. Without `SelectMany` you would write a nested loop.
:::

### Ordering: OrderBy, ThenBy, Order

```csharp
var sorted = customers.OrderBy(c => c.City).ThenByDescending(c => c.Name);
// Output: Ben (Delhi), Dev (Mumbai), Chen (Pune), Asha (Pune)

var nums = new[] { 5, 1, 4 };
nums.Order();             // .NET 7+: 1, 4, 5 — no key selector needed
nums.OrderDescending();   // 5, 4, 1
```

:::warn Gotcha: OrderBy().OrderBy()
A second `OrderBy` **replaces** the first sort; it does not add a tiebreaker. Use `ThenBy` for secondary keys. `OrderBy` is a *stable* sort in LINQ to Objects (equal keys keep source order).
:::

### Quantifiers and element operators

**Definition.** `Any`/`All`/`Contains` return `bool`. `First`/`Single`/`Last`/`ElementAt` (and their `*OrDefault` forms) return one element.

```csharp
customers.Any(c => c.City == "Pune");                 // true
orders.All(o => o.Total > 0);                         // true
new int[0].All(x => x > 5);                           // true  (vacuous truth!)
orders.Select(o => o.Status).Contains("Cancelled");   // true
```

**First vs Single vs *OrDefault — exactly what throws:**

| Method | 0 matches | 1 match | 2+ matches |
|---|---|---|---|
| `First` | `InvalidOperationException` | the item | the first item |
| `FirstOrDefault` | `default` (`null` / `0`) | the item | the first item |
| `Single` | `InvalidOperationException` | the item | `InvalidOperationException` |
| `SingleOrDefault` | `default` | the item | `InvalidOperationException` |

```csharp
orders.First(o => o.Status == "Paid");            // order 101
orders.FirstOrDefault(o => o.Id == 999);          // null
orders.Single(o => o.Id == 102);                  // order 102
orders.Single(o => o.Status == "Paid");           // throws: more than one element
orders.FirstOrDefault(o => o.Id == 999, new Order(0, 0, "", 0, []));  // .NET 6+ custom default
```

- Use **Single** when your business rule says "exactly one" (lookup by unique key) — it *validates* the rule. Use **First** when many may match and you want any/the first.
- In EF Core, `First` becomes `TOP 1` and `Single` becomes `TOP 2` (so it can detect duplicates). Always add `OrderBy` before `First` or the "first" row is undefined.
- `FirstOrDefault` on a value-type sequence returns `0`, which you cannot tell from a real `0`. Use the custom-default overload or project to a nullable.

### Aggregation: Count, Sum, Average, Min, Max, Aggregate

```csharp
orders.Count();                        // 5
orders.Count(o => o.Status == "Paid"); // 3
orders.Sum(o => o.Total);              // 2450
orders.Average(o => o.Total);          // 490
orders.Max(o => o.Total);              // 1020
orders.Min(o => o.Total);              // 20
products.Aggregate("", (acc, p) => acc + p.Name[0]);   // "LMDC"  (custom fold)
```

:::warn Empty sequences
`Sum` of an empty sequence is `0`, but `Average`, `Min` and `Max` of an empty sequence of a non-nullable type **throw** `InvalidOperationException`. Fix with `DefaultIfEmpty(0).Max()` or project to nullable: `Max(o => (decimal?)o.Total)`. The same applies in EF Core: SQL returns `NULL` and the cast to a non-nullable type fails.
:::

### GroupBy

**Definition.** Groups elements by a key and returns `IEnumerable<IGrouping<TKey, T>>`; each group has a `Key` and is itself enumerable.

```csharp
var byCity = customers.GroupBy(c => c.City)
    .Select(g => new { City = g.Key, Count = g.Count(), Names = g.Select(c => c.Name) });
// Output: Pune 2 [Asha, Chen] | Delhi 1 [Ben] | Mumbai 1 [Dev]

// Query syntax with 'into' and ordering by an aggregate
var spend = from o in orders
            where o.Status != "Cancelled"
            group o by o.CustomerId into g
            orderby g.Sum(x => x.Total) descending
            select new { CustomerId = g.Key, Spent = g.Sum(x => x.Total) };
// Output: (1, 1170) (3, 1020) (2, 240)
```

`GroupBy` is deferred but **buffers** the whole source on first `MoveNext`. In EF Core it translates to `GROUP BY` only when you project the key and aggregates; to get full row groups, fetch the rows first and group in memory.

### Join, GroupJoin and the left-join pattern

**Definition.** `Join` is an inner equi-join. `GroupJoin` returns each outer element with the *collection* of matching inner elements (the basis of a left join).

```csharp
var inner = from o in orders
            join c in customers on o.CustomerId equals c.Id
            select new { o.Id, c.Name, o.Total };
// Method syntax: orders.Join(customers, o => o.CustomerId, c => c.Id,
//                            (o, c) => new { o.Id, c.Name, o.Total });
// Output: (101,Asha,920) (102,Asha,250) (103,Ben,240) (104,Chen,20) (105,Chen,1020)
// Dev is missing — inner join drops customers without orders.

// GroupJoin: one row per customer with a child collection
var counts = customers.GroupJoin(orders, c => c.Id, o => o.CustomerId,
                (c, os) => new { c.Name, OrderCount = os.Count() });
// Output: Asha 2, Ben 1, Chen 2, Dev 0

// LEFT JOIN: GroupJoin + DefaultIfEmpty
var left = from c in customers
           join o in orders on c.Id equals o.CustomerId into g
           from o in g.DefaultIfEmpty()
           select new { c.Name, OrderId = o?.Id, Total = o?.Total ?? 0m };
// Output: Asha 101 920 | Asha 102 250 | Ben 103 240 | Chen 104 20 | Chen 105 1020
//         Dev null 0
```

- `join` only supports equality (`equals`, with left key on the left). For other conditions use `from … from … where`.
- .NET 10 adds built-in `LeftJoin` / `RightJoin` operators (and EF Core 10 translates them) — check your target framework before using them.
- With EF Core you rarely write joins by hand: use navigation properties (`c.Orders`, `Include`) and let EF generate the join.

### Set, partitioning and modern operators

```csharp
var cities = customers.Select(c => c.City).Distinct();        // Pune, Delhi, Mumbai
var page   = products.OrderBy(p => p.Id).Skip(2).Take(2);     // Desk, Chair (page 2 of size 2)
// Union (distinct merge), Concat (plain append), Intersect, Except: set operations
```

Pagination always needs a deterministic `OrderBy`; for deep pages prefer keyset pagination (`Where(p => p.Id > lastId).Take(n)`) because `Skip(100000)` still scans those rows.

**Modern operators (know the version):**

| Operator | Since | What it does |
|---|---|---|
| `DistinctBy`, `MinBy`, `MaxBy`, `Chunk`, 3-way `Zip` | .NET 6 | Key-based distinct/min/max, batches, zip of three sequences |
| `Order`, `OrderDescending` | .NET 7 | Sort without a key selector |
| `CountBy`, `AggregateBy`, `Index` | .NET 9 | Group-count and group-fold without building groups; `(index, item)` pairs |
| `LeftJoin`, `RightJoin` | .NET 10 | Outer joins without the `GroupJoin` dance |

```csharp
customers.DistinctBy(c => c.City).Select(c => c.Name);   // Asha, Ben, Dev
products.MaxBy(p => p.Price)!.Name;                      // Laptop (returns the element, not 900)
products.Chunk(3);                                       // [Laptop,Mouse,Desk] [Chair]

var stock = new[] { 5, 0, 12, 3 };
products.Zip(stock, (p, s) => $"{p.Name}:{s}");          // Laptop:5, Mouse:0, Desk:12, Chair:3
                                                         // stops at the shorter sequence

orders.CountBy(o => o.Status);                           // .NET 9
// Output: [Paid, 3] [Shipped, 1] [Cancelled, 1]  (KeyValuePair<string,int>)

orders.AggregateBy(o => o.CustomerId, 0m, (sum, o) => sum + o.Total);   // .NET 9
// Output: [1, 1170] [2, 240] [3, 1040]

foreach (var (i, c) in customers.Index())                // .NET 9: (int Index, T Item)
    Console.WriteLine($"{i}: {c.Name}");                 // 0: Asha, 1: Ben ...

var lookup = orders.ToLookup(o => o.CustomerId);         // immediate multimap
lookup[1].Count();                                       // 2
lookup[99].Count();                                      // 0 — missing key = empty, no throw
```

`ToLookup` vs `GroupBy`: `ToLookup` executes immediately and gives O(1) key lookups; `GroupBy` is deferred. `ToDictionary` throws on duplicate keys — use `ToLookup` when keys repeat.

### Deferred vs immediate execution

**Definition.** A LINQ query *describes* work; it does not run when defined. It runs when you enumerate it (`foreach`, `ToList`, `Count`, `First` ...). Operators that return a sequence are deferred; operators that return a single value or a materialised collection are immediate.

| Category | Operators | Behaviour |
|---|---|---|
| Deferred, streaming | `Where`, `Select`, `SelectMany`, `Take`, `Skip`, `Concat`, `Zip`, `Distinct` | Yields one element at a time; low memory |
| Deferred, buffering | `OrderBy`, `GroupBy`, `Join` (inner side), `Reverse` | Still deferred, but reads the whole source on first pull |
| Immediate | `ToList`, `ToArray`, `ToDictionary`, `ToHashSet`, `Count`, `Sum`, `Min`, `Max`, `Average`, `First`, `Single`, `Any`, `All`, `Contains`, `ElementAt` | Runs now and returns a value |

**Gotcha 1 — modify the source after defining the query:**

```csharp
var numbers = new List<int> { 1, 2, 3 };
var evens = numbers.Where(n => n % 2 == 0);        // nothing executes here
numbers.Add(4);
Console.WriteLine(string.Join(",", evens));        // Output: 2,4   (ran now, saw the 4)

var snapshot = numbers.Where(n => n % 2 == 0).ToList();   // materialised: frozen
numbers.Add(6);
Console.WriteLine(snapshot.Count);                 // Output: 2

var min = 1;
var q = numbers.Where(n => n > min);               // closure captures the VARIABLE
min = 3;
Console.WriteLine(q.Count());                      // Output: 2 (uses min == 3 => 4, 6; not 1)
```

Also: changing the *collection* (`Add`/`Remove`) while a `foreach` over a query on it is running throws `InvalidOperationException: Collection was modified`.

**Gotcha 2 — multiple enumeration.** Every enumeration re-runs the whole pipeline: side effects repeat, `Select(x => Guid.NewGuid())` produces different values each time, and over a database it sends the SQL again.

```csharp
IEnumerable<Order> paid = db.Orders.Where(o => o.Status == "Paid");
if (paid.Any())                       // SQL #1
    foreach (var o in paid)           // SQL #2
        Log(paid.Count());            // SQL #3 ... once per iteration!

var paidList = await db.Orders.Where(o => o.Status == "Paid").ToListAsync();  // one query
```

:::warn Rule of thumb
If you need the result more than once, or you must freeze it at a point in time, materialise it (`ToList`/`ToArray`). If you only iterate once, leave it deferred. ReSharper/Rider flag this as "Possible multiple enumeration of IEnumerable".
:::

:::q Which LINQ operators force immediate execution?
Anything that returns a scalar or a collection instead of a lazy sequence: `ToList`, `ToArray`, `ToDictionary`, `ToHashSet`, `Count`, `Sum`, `Min`, `Max`, `Average`, `First`, `Single`, `Any`, `All`, `Contains`, and a `foreach`. Everything that returns `IEnumerable<T>`/`IQueryable<T>` (`Where`, `Select`, `OrderBy` ...) is deferred.
:::

### LINQ to Objects vs LINQ to EF Core

**Definition.** *LINQ to Objects* runs operators over in-memory `IEnumerable<T>` using compiled delegates. *LINQ to EF* runs over `IQueryable<T>` (`DbSet<T>`), where lambdas become **expression trees** that EF Core translates to SQL and executes in the database.

| | LINQ to Objects | LINQ to EF Core |
|---|---|---|
| Source type | `IEnumerable<T>` | `IQueryable<T>` |
| Lambda is | `Func<T,bool>` (compiled code) | `Expression<Func<T,bool>>` (data / AST) |
| Runs | In your process, element by element | In SQL Server, then results come back |
| Any C# call allowed | Yes | Only what the provider can translate |
| Triggered by | `foreach`, `ToList` ... | same, plus `ToListAsync`, `FirstOrDefaultAsync` ... |

```csharp
Func<Order, bool> f = o => o.Total > 500;                 // opaque compiled delegate
Expression<Func<Order, bool>> e = o => o.Total > 500;     // inspectable tree
Console.WriteLine(e.Body);                                // Output: (o.Total > 500)

var q = db.Orders.Where(o => o.Status == "Paid" && o.Total > 500)
                 .OrderByDescending(o => o.Total)
                 .Select(o => new { o.Id, o.Total });
// SELECT [o].[Id], [o].[Total] FROM [Orders] AS [o]
// WHERE [o].[Status] = N'Paid' AND [o].[Total] > 500.0
// ORDER BY [o].[Total] DESC
```

**Client vs server evaluation.** Since EF Core 3.0, only the **final projection** (`Select`) may run on the client. An untranslatable call anywhere else throws `InvalidOperationException: The LINQ expression ... could not be translated`.

```csharp
db.Orders.Where(o => IsVipOrder(o));                     // throws at runtime: your method
db.Orders.Select(o => new { o.Id, Tag = Format(o) });    // OK: final projection, client-side
db.Orders.AsEnumerable().Where(o => IsVipOrder(o));      // OK but loads the WHOLE table first
```

**What not to call inside an EF query:**

- Your own methods, local functions, or unmapped computed properties (`FullName => First + " " + Last`).
- `Regex`, `Convert.*`, `DateTime.Parse`, most custom-comparer overloads (`Distinct(comparer)`, `Contains(x, comparer)`).
- `ToList()`/`AsEnumerable()` **before** `Where`/`OrderBy`/`Take` — everything after it runs in memory on the full table.
- Prefer `EF.Functions.Like`, `EF.Functions.DateDiffDay` etc. for database-specific functions, and `AsNoTracking()` + `Select` projections for read-only queries.

### Any() vs Count() > 0

| | `Any()` | `Count() > 0` |
|---|---|---|
| In memory | Stops at the first element | Walks everything (unless the source is an `ICollection<T>`, then O(1)) |
| EF Core SQL | `EXISTS (SELECT 1 …)` | `SELECT COUNT(*) …` |
| Intent | "is there at least one?" | "how many?" |

```csharp
if (await db.Orders.AnyAsync(o => o.CustomerId == id)) { ... }   // EXISTS: stops early
if (list.Count > 0) { ... }                                       // List<T>: property, O(1)
```

Rule: use `Any()` for existence on queries and lazy sequences; use the `Count`/`Length` *property* on `List<T>`/arrays; use `Count()` only when you need the number.

### Classic LINQ interview exercises

```csharp
// 1. Customers with no orders (anti-join)
customers.Where(c => !orders.Any(o => o.CustomerId == c.Id));        // Dev

// 2. Highest-value order per customer
orders.GroupBy(o => o.CustomerId).Select(g => g.MaxBy(o => o.Total)!.Id);
// Output: 101, 103, 105

// 3. Second-highest order total (distinct first, or ties break the answer)
orders.Select(o => o.Total).Distinct().OrderByDescending(t => t).Skip(1).FirstOrDefault();
// Output: 920

// 4. Duplicates in a list
new[] { "a", "b", "a", "c", "b" }.GroupBy(x => x).Where(g => g.Count() > 1)
                                 .Select(g => g.Key);                // a, b

// 5. Products per category as text
products.GroupBy(p => p.Category)
        .Select(g => $"{g.Key}: {string.Join(", ", g.Select(p => p.Name))}");
// Output: "Electronics: Laptop, Mouse", "Furniture: Desk, Chair"

// 6. Revenue per product name (join + group)
orders.SelectMany(o => o.Lines)
      .Join(products, l => l.ProductId, p => p.Id,
            (l, p) => new { p.Name, Amount = l.Qty * p.Price })
      .GroupBy(x => x.Name)
      .Select(g => new { g.Key, Revenue = g.Sum(x => x.Amount) });
// Output: Laptop 1800, Mouse 40, Desk 250, Chair 360
```

:::q First vs Single — which do you use and why?
`First` returns the first match and throws only if there is none; `Single` asserts there is exactly one and throws on zero *or* more than one. I use `Single`/`SingleOrDefault` for lookups that must be unique (by primary key or unique index) because a duplicate then fails loudly instead of silently returning a random row. I use `First`/`FirstOrDefault` after an `OrderBy` when many rows may match and I want a specific one.
:::

:::q Select vs SelectMany?
`Select` maps one input to exactly one output, so projecting a collection property gives a collection of collections. `SelectMany` maps one input to many outputs and flattens them into a single sequence — e.g. `orders.SelectMany(o => o.Lines)` gives all order lines as one flat list.
:::

:::scenario The report endpoint that hit the database 400 times
A dashboard action loads `IEnumerable<Customer> vips = db.Customers.Where(IsVip)` then loops: `foreach (var c in vips) total += db.Orders.Count(o => o.CustomerId == c.Id)`. Problems: (1) `vips` is re-queried each time it is enumerated, (2) one `COUNT` query per customer (N+1), (3) `IsVip` is a C# method so it either throws or someone added `.ToList()` earlier and loaded all customers.
**Fix:** express `IsVip` as an expression, project in one query: `db.Customers.Where(c => c.Spent > 1000).Select(c => new { c.Id, c.Name, Orders = c.Orders.Count }).ToListAsync()`. One round-trip, one SQL statement, only needed columns.
:::

:::q Difference between IEnumerable and IQueryable in LINQ?
`IEnumerable<T>` operators take delegates and run in memory, so a `Where` after `ToList()` filters in your process. `IQueryable<T>` operators take expression trees that the provider (EF Core) translates to SQL, so the filter runs in the database. Returning `IQueryable` from a repository lets callers keep composing; returning `IEnumerable` freezes the query at that point.
:::

:::q Why does my EF query throw "could not be translated"?
Because part of the lambda calls something EF cannot convert to SQL — usually my own method or an unsupported .NET API inside `Where`/`OrderBy`. Fix by rewriting with translatable members/`EF.Functions`, or deliberately bring *already-filtered* data to memory with `AsEnumerable()`/`ToListAsync()` and finish the query client-side.
:::
