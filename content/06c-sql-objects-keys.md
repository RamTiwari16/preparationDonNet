## SQL Objects

### Tables and constraints

**Definition.** A table stores rows of typed columns. *Constraints* are rules the engine enforces for you, so bad data cannot get in no matter which app, script or person writes it.

| Constraint | Enforces | Example |
|---|---|---|
| `NOT NULL` | A value must be supplied | `Orders.CustomerId` |
| `PRIMARY KEY` | Unique, non-null row identity; one per table | `Orders.OrderId` |
| `UNIQUE` | No duplicates (one `NULL` allowed) | `Customers.Email` |
| `FOREIGN KEY` | Value must exist in the parent table | `Orders.CustomerId -> Customers` |
| `CHECK` | Boolean rule on the row | `CHECK (Quantity > 0)` |
| `DEFAULT` | Value used when none supplied | `DEFAULT SYSUTCDATETIME()` |

```sql
CREATE TABLE dbo.Reviews (
    ReviewId   INT IDENTITY(1,1) CONSTRAINT PK_Reviews PRIMARY KEY,
    ProductId  INT           NOT NULL CONSTRAINT FK_Reviews_Products REFERENCES dbo.Products(ProductId),
    Rating     TINYINT       NOT NULL CONSTRAINT CK_Reviews_Rating CHECK (Rating BETWEEN 1 AND 5),
    Comment    NVARCHAR(500) NULL,
    CreatedAt  DATETIME2(0)  NOT NULL CONSTRAINT DF_Reviews_CreatedAt DEFAULT SYSUTCDATETIME(),
    CommentLen AS (LEN(Comment)) PERSISTED            -- computed column
);
```

Data-type habits that interviewers notice: `DECIMAL(p,s)` for money (never `FLOAT`/`REAL`), `DATE`/`DATETIME2` instead of `DATETIME`, `NVARCHAR` when text may be non-Latin, right-sized `VARCHAR(n)` (avoid `MAX` unless needed, it cannot be an index key), `BIT` for flags, `UNIQUEIDENTIFIER` only when you need globally unique ids. Give constraints **names** so error messages and migrations are readable.

### Views

**Definition.** A view is a stored `SELECT` that behaves like a virtual table. It stores **no data** (unless indexed); the query is expanded into the outer query at run time.

**Why it matters.** Hide join complexity, give reporting users a stable shape, restrict column/row access (security), and keep legacy contracts when the underlying tables change.

```sql
CREATE VIEW dbo.vw_OrderSummary AS
SELECT o.OrderId, c.Name AS Customer, o.OrderDate, o.Status,
       SUM(oi.Quantity * oi.UnitPrice) AS Total
FROM   dbo.Orders o
JOIN   dbo.Customers  c  ON c.CustomerId = o.CustomerId
JOIN   dbo.OrderItems oi ON oi.OrderId   = o.OrderId
GROUP  BY o.OrderId, c.Name, o.OrderDate, o.Status;
GO
SELECT * FROM dbo.vw_OrderSummary WHERE Status = N'Shipped';
-- 101 Alice 1050.00 | 102 Alice 300.00 | 103 Bob 325.00 | 106 Bob 300.00
```

- Views cannot take parameters (use an inline TVF), and `ORDER BY` is not allowed in a view without `TOP`.
- A simple single-table view is **updatable**; add `WITH CHECK OPTION` so an `UPDATE` cannot move a row out of the view's `WHERE`.
- `SELECT *` inside a view is frozen at creation; adding columns later does not show up until `sp_refreshview`. Use `WITH SCHEMABINDING` to prevent that drift.
- Stacking views on views produces huge, hard-to-tune plans. Keep it to one or two levels.

#### Indexed views and SCHEMABINDING

**Definition.** `WITH SCHEMABINDING` ties the view to its base tables: you cannot drop or alter a referenced column while the view exists. Creating a **unique clustered index** on a schema-bound view *materialises* it: the result is stored and SQL Server maintains it on every base-table change.

```sql
CREATE VIEW dbo.vw_ProductSales WITH SCHEMABINDING AS
SELECT ProductId,
       SUM(Quantity)             AS UnitsSold,
       SUM(Quantity * UnitPrice) AS Revenue,
       COUNT_BIG(*)              AS Lines          -- mandatory with GROUP BY
FROM   dbo.OrderItems                              -- two-part names are mandatory
GROUP  BY ProductId;
GO
CREATE UNIQUE CLUSTERED INDEX IX_vw_ProductSales ON dbo.vw_ProductSales (ProductId);
-- Laptop 2 units 2000.00 | Mouse 7 / 175.00 | Desk 2 / 600.00 | Chair 2 / 300.00
-- ALTER TABLE dbo.OrderItems DROP COLUMN UnitPrice;
--   -> Msg 4922: DROP COLUMN failed because one or more objects access this column.
```

| Good for | Costs / limits |
|---|---|
| Pre-computed aggregates for read-heavy reporting | Every `INSERT/UPDATE/DELETE` on the base table also updates the view (write cost, lock contention) |
| Enterprise edition auto-matches queries to it even if they never mention the view; other editions need `WITH (NOEXPAND)` | No outer joins, subqueries, `DISTINCT`, `MIN/MAX`, `TOP`, self-joins; deterministic expressions only |

:::q What is the difference between a view and an indexed view?
A normal view stores only the query; it is re-run against the base tables each time. An indexed (materialised) view has a unique clustered index, so the result set is physically stored and kept in sync automatically. It speeds up aggregate reads but slows writes, and it requires `SCHEMABINDING` and a restricted query shape.
:::

### Stored procedures vs functions

**Definition.** A *stored procedure* is a named, reusable batch of T-SQL that can do anything (DML, DDL, transactions, dynamic SQL). A *function* computes and returns a value or a table and must be side-effect free; it can be used inside a query.

| | Stored procedure | Scalar UDF | Inline TVF | Multi-statement TVF |
|---|---|---|---|---|
| Returns | Optional int code, result sets, `OUTPUT` params | One value | A table | A table (built in a `@table` variable) |
| Use in `SELECT`/`WHERE` | No (`EXEC` or `INSERT...EXEC`) | Yes | Yes, in `FROM` / `APPLY` | Yes |
| Modify data | Yes | No | No | No (only its own return table) |
| `TRY...CATCH`, transactions | Yes | No | No | No |
| Dynamic SQL, temp tables | Yes | No | No | No (table variables only) |
| Optimizer view | Compiled plan, cached and reused | Black box per row (unless inlined, see below) | **Expanded like a view**; full optimization | Black box; fixed row estimate |
| Typical cost | Fine | Row-by-row call: slow on big sets | Fast | Slow on big sets |

```sql
-- Scalar UDF
CREATE FUNCTION dbo.fn_LineTotal (@Qty INT, @UnitPrice DECIMAL(10,2))
RETURNS DECIMAL(12,2) AS BEGIN RETURN @Qty * @UnitPrice; END;
GO
SELECT OrderId, ProductId, dbo.fn_LineTotal(Quantity, UnitPrice) AS LineTotal
FROM   dbo.OrderItems WHERE OrderId = 101;          -- 1000.00, 50.00

-- Inline TVF: one RETURN (SELECT ...), behaves like a parameterised view
CREATE FUNCTION dbo.fn_EmployeesByDept (@DeptId INT) RETURNS TABLE AS
RETURN (SELECT EmployeeId, Name, Salary FROM dbo.Employees WHERE DepartmentId = @DeptId);
GO
SELECT * FROM dbo.fn_EmployeesByDept(3);            -- 9 Nina 65000

-- Multi-statement TVF: declares the table, fills it, RETURN
CREATE FUNCTION dbo.fn_EmployeesByDept_Multi (@DeptId INT)
RETURNS @r TABLE (EmployeeId INT, Name NVARCHAR(50), Salary INT) AS
BEGIN
    INSERT @r SELECT EmployeeId, Name, Salary FROM dbo.Employees WHERE DepartmentId = @DeptId;
    RETURN;
END;
```

- **Scalar UDF inlining** (SQL Server 2019+, compatibility level 150) rewrites many simple scalar functions into the calling query, removing the row-by-row penalty. Functions with loops, table access in some forms, or non-deterministic calls may not qualify.
- A multi-statement TVF has a fixed row estimate (1, then 100 in 2014+; "interleaved execution" in 2017+ fixes this for the first compile), which wrecks join choices. Prefer **inline** TVF.
- A function in a `WHERE` or `JOIN` predicate stops index seeks (see SARGability).

:::q Stored procedure vs function: when do you use which?
A procedure for actions: it can change data, manage transactions, handle errors and run dynamic SQL. A function when I need a value or a result set *inside* a query, and I want it to be deterministic and side-effect free. For set-returning logic I choose an inline table-valued function, because the optimizer expands it like a view; I avoid multi-statement TVFs and scalar UDFs on large row counts.
:::

### Triggers

**Definition.** A trigger is code that runs automatically in response to `INSERT`, `UPDATE` or `DELETE` on a table (DML trigger), or DDL/logon events. Inside it, the virtual tables **`inserted`** (new row images) and **`deleted`** (old row images) hold the affected rows; an `UPDATE` populates both.

| | `AFTER` trigger | `INSTEAD OF` trigger |
|---|---|---|
| Fires | After the action and constraints are checked | **Instead of** the action; you do the work (or refuse) |
| Typical use | Audit trail, denormalised counters, cascading business rules | Make a view updatable; soft delete; veto an operation |
| On | Tables only | Tables and views |
| Per table | Several, order settable only for first/last (`sp_settriggerorder`) | One per action |

```sql
-- AFTER UPDATE: audit every salary change (set-based: handles multi-row updates)
CREATE TRIGGER dbo.trg_Employees_SalaryAudit ON dbo.Employees AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT UPDATE(Salary) RETURN;
    INSERT dbo.SalaryAudit (EmployeeId, OldSalary, NewSalary)
    SELECT i.EmployeeId, d.Salary, i.Salary
    FROM   inserted i JOIN deleted d ON d.EmployeeId = i.EmployeeId
    WHERE  i.Salary <> d.Salary;
END;
GO
UPDATE dbo.Employees SET Salary = Salary + 1000 WHERE DepartmentId = 2;
-- SalaryAudit gets 4 rows: Sana 95000->96000, Tom 100000->101000,
--                          Uma 70000->71000, Omar 70000->71000
```

```sql
-- INSTEAD OF DELETE: veto deleting shipped orders, otherwise perform the delete
CREATE TRIGGER dbo.trg_Orders_NoDeleteShipped ON dbo.Orders INSTEAD OF DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM deleted WHERE Status = N'Shipped')
        THROW 50001, N'Shipped orders cannot be deleted.', 1;
    DELETE o FROM dbo.Orders o JOIN deleted d ON d.OrderId = o.OrderId;
END;
```

:::warn Trigger pitfalls
- **Multi-row statements.** A trigger fires once per *statement*, not per row. `SELECT @x = Salary FROM inserted` silently handles one arbitrary row. Always write set-based joins to `inserted`/`deleted`.
- **Hidden logic.** Developers do not see triggers in the calling code; behaviour "just happens". Document them, keep them tiny.
- **Performance and locking.** The trigger runs inside the caller's transaction and extends it. A slow trigger slows every writer.
- **Recursion/nesting.** `RECURSIVE_TRIGGERS` is off by default but triggers can still chain across tables (nested up to 32 levels).
- **An unhandled error inside a trigger dooms the caller's transaction** (`XACT_STATE() = -1`) and aborts the batch, so the original statement and everything in that transaction is rolled back.
- `@@IDENTITY` returns a trigger's identity; use `SCOPE_IDENTITY()`. EF Core's `OUTPUT` clause fails on tables with triggers unless configured (`HasTrigger`).
- Prefer constraints, temporal tables, CDC or application events when they fit.
:::

### Temp tables, table variables and CTEs

**Definition.** Three ways to hold an intermediate result.
`#Temp` (local) lives in tempdb for your session and child scopes, `##Temp` (global) is visible to *all* sessions until its creator disconnects and nobody references it. `@Table` is a variable scoped to the batch/procedure. A CTE is just a named query for one statement.

| | `#temp` table | `@table` variable | CTE |
|---|---|---|---|
| Stored in | tempdb | tempdb (memory-cached while small) | Not stored (query text) |
| Scope | Session; visible in called procs | Batch / proc only | One statement |
| Statistics | Yes (good estimates) | No column stats (row count visible from first compile on 2019+) | n/a |
| Indexes | Any, added after creation | Inline `PRIMARY KEY`/`UNIQUE`/index only | n/a |
| Transactions | Fully transactional (rolls back) | **Not** undone by `ROLLBACK` | n/a |
| Recompiles | Can trigger recompile when stats change | No | n/a |
| Reusable across statements | Yes | Yes | **No** |
| Parallel plans | Yes | Writes force serial plans (SELECT can go parallel) | n/a |

```sql
CREATE TABLE #Recent (OrderId INT PRIMARY KEY, Total DECIMAL(10,2));
INSERT #Recent SELECT OrderId, SUM(Quantity * UnitPrice) FROM dbo.OrderItems GROUP BY OrderId;
-- ... reuse #Recent in several following queries, add an index, join to it
DROP TABLE IF EXISTS #Recent;     -- good hygiene; auto-dropped at session end otherwise

CREATE TABLE #tt (a INT); DECLARE @tv TABLE (a INT);
BEGIN TRAN; INSERT #tt VALUES (1); INSERT @tv VALUES (1); ROLLBACK;
SELECT (SELECT COUNT(*) FROM #tt) AS temp_rows, (SELECT COUNT(*) FROM @tv) AS var_rows;
-- Output: 0 | 1     (the table variable ignored the rollback)
```

**When to use which:**

- **CTE**: readability, recursion, a one-off step used once. Not a performance tool.
- **`@table` variable**: small sets (tens to low hundreds of rows), simple lookups, when you want no recompiles or must keep data across a rollback (e.g. error log).
- **`#temp` table**: thousands+ rows, you will join it or reuse it, you want statistics and indexes, or a CTE is referenced many times and is expensive. Default choice for large intermediate results.
- Memory-optimised table variables and tempdb metadata optimisations exist in recent versions but do not change these rules of thumb.

:::q What is the difference between a temp table and a table variable?
Both live in tempdb. A temp table has real statistics, supports any index, is transactional and can be used in nested procedures; it can cause recompiles. A table variable has no column statistics (so poor estimates on large sets, improved a bit by deferred compilation in 2019), only inline indexes, is not affected by `ROLLBACK`, and does not cause recompiles. I use table variables for small row counts and temp tables for anything big or reused.
:::

### Table-valued parameters (TVP)

**Definition.** A TVP lets you pass a **set of rows** as one parameter to a stored procedure or function, using a user-defined *table type*. It is read-only inside the callee (`READONLY`).

**Why it matters.** Replaces ugly workarounds: comma-separated strings, XML/JSON blobs, or one round trip per row. One call inserts a whole order with all its lines.

```sql
CREATE TYPE dbo.OrderItemList AS TABLE (
    ProductId INT NOT NULL PRIMARY KEY,
    Quantity  INT NOT NULL CHECK (Quantity > 0)
);
GO
CREATE OR ALTER PROCEDURE dbo.usp_CreateOrder
    @CustomerId INT,
    @Items      dbo.OrderItemList READONLY,       -- READONLY is mandatory
    @OrderId    INT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    BEGIN TRAN;
        INSERT dbo.Orders (CustomerId, OrderDate, Status)
        VALUES (@CustomerId, CAST(SYSUTCDATETIME() AS DATE), N'Pending');
        SET @OrderId = SCOPE_IDENTITY();

        INSERT dbo.OrderItems (OrderId, ProductId, Quantity, UnitPrice)
        SELECT @OrderId, i.ProductId, i.Quantity, p.Price      -- price taken from Products
        FROM   @Items i JOIN dbo.Products p ON p.ProductId = i.ProductId;
    COMMIT;
END;
GO
-- Calling it from T-SQL
DECLARE @items dbo.OrderItemList, @id INT;
INSERT @items VALUES (1, 1), (2, 3);                    -- 1 Laptop, 3 Mouse
EXEC dbo.usp_CreateOrder @CustomerId = 4, @Items = @items, @OrderId = @id OUTPUT;
-- @id = 107; OrderItems gets (107,1,1,1000.00) and (107,2,3,25.00)
```

**From C# (ADO.NET, `Microsoft.Data.SqlClient`):**

```csharp
var items = new DataTable();
items.Columns.Add("ProductId", typeof(int));      // column order/types must match the table type
items.Columns.Add("Quantity",  typeof(int));
items.Rows.Add(1, 1);
items.Rows.Add(2, 3);

await using var conn = new SqlConnection(connectionString);
await using var cmd  = new SqlCommand("dbo.usp_CreateOrder", conn)
{
    CommandType = CommandType.StoredProcedure
};
cmd.Parameters.Add("@CustomerId", SqlDbType.Int).Value = 4;
var tvp = cmd.Parameters.Add("@Items", SqlDbType.Structured);
tvp.TypeName = "dbo.OrderItemList";               // the SQL table type
tvp.Value    = items;                             // DataTable, DbDataReader or IEnumerable<SqlDataRecord>
var outId = cmd.Parameters.Add("@OrderId", SqlDbType.Int);
outId.Direction = ParameterDirection.Output;

await conn.OpenAsync();
await cmd.ExecuteNonQueryAsync();
int orderId = (int)outId.Value;
```

**Dapper:**

```csharp
var p = new DynamicParameters();
p.Add("@CustomerId", 4);
p.Add("@Items", items.AsTableValuedParameter("dbo.OrderItemList"));   // DataTable extension
p.Add("@OrderId", dbType: DbType.Int32, direction: ParameterDirection.Output);

await conn.ExecuteAsync("dbo.usp_CreateOrder", p, commandType: CommandType.StoredProcedure);
int orderId = p.Get<int>("@OrderId");
```

**EF Core (raw SQL, because EF has no native TVP mapping):**

```csharp
var customerId = new SqlParameter("@CustomerId", 4);
var itemsParam = new SqlParameter("@Items", SqlDbType.Structured)
{ TypeName = "dbo.OrderItemList", Value = items };
var orderIdOut = new SqlParameter("@OrderId", SqlDbType.Int) { Direction = ParameterDirection.Output };

await db.Database.ExecuteSqlRawAsync(
    "EXEC dbo.usp_CreateOrder @CustomerId, @Items, @OrderId OUTPUT",
    customerId, itemsParam, orderIdOut);
int orderId = (int)orderIdOut.Value;
```

| Option for "send a list to SQL" | When |
|---|---|
| TVP | Structured rows, tens to thousands, strongly typed, used by a proc |
| `OPENJSON` / `STRING_SPLIT` | Quick lists, no type to create (JSON for several columns) |
| `SqlBulkCopy` | Tens of thousands+ rows straight into a table |
| One call per row | Never for batches (N round trips) |

:::warn TVP gotchas
- Table variables (and therefore TVPs) have no column statistics. For joins on big TVPs, copy into a `#temp` table inside the proc, or add `OPTION (RECOMPILE)`.
- Changing a table type requires dropping every dependent proc first. Version the type (`OrderItemList_v2`) or plan for it.
- The `DataTable` column order and types must match the table type exactly or you get a conversion error at execution.
:::

## Keys

### Primary, foreign, composite, unique and candidate keys

**Definition and relationships.**

- **Candidate key**: any minimal column set that uniquely identifies a row. A table may have several.
- **Primary key (PK)**: the one candidate key chosen as the row's identity; unique, `NOT NULL`, one per table. In SQL Server it creates a **clustered index** by default.
- **Alternate key**: a candidate key that was *not* chosen as the PK; enforced with a `UNIQUE` constraint (`Customers.Email`).
- **Unique key**: a `UNIQUE` constraint or unique index; several per table; one `NULL` allowed.
- **Composite key**: a key made of more than one column, e.g. `(OrderId, ProductId)` on a line-item table.
- **Foreign key (FK)**: column(s) referencing a PK/unique key in another table; guarantees *referential integrity* (no orphan rows).
- **Surrogate key**: artificial, meaningless identifier (`IDENTITY`, `SEQUENCE`, `GUID`). **Natural key**: real-world attribute (email, ISBN, SSN).

| | Surrogate key | Natural key |
|---|---|---|
| Stability | Never changes | May change (email, name) |
| Size | Small (`INT`/`BIGINT`) | Often wide strings |
| Joins/FKs | Compact, fast | Wide FKs everywhere |
| Meaning | None | Has business meaning, can be validated |
| Duplicates risk | Does not prevent duplicate real-world entities | Prevents them |
| Best practice | PK = surrogate **plus** a `UNIQUE` constraint on the natural key | |

```sql
CREATE TABLE dbo.ProductTags (                -- composite PK: a tag once per product
    ProductId INT          NOT NULL REFERENCES dbo.Products(ProductId),
    Tag       NVARCHAR(30) NOT NULL,
    CONSTRAINT PK_ProductTags PRIMARY KEY (ProductId, Tag)
);

CREATE TABLE dbo.OrderNotes (
    NoteId  INT IDENTITY PRIMARY KEY,
    OrderId INT NOT NULL,
    Note    NVARCHAR(200) NOT NULL,
    CONSTRAINT FK_OrderNotes_Orders FOREIGN KEY (OrderId)
        REFERENCES dbo.Orders(OrderId)
        ON DELETE CASCADE                     -- delete notes when the order is deleted
        ON UPDATE NO ACTION
);
```

#### Foreign-key actions

| Action | Effect when the parent row is deleted/updated |
|---|---|
| `NO ACTION` (default) | The statement fails if child rows exist |
| `CASCADE` | Child rows are deleted/updated too |
| `SET NULL` | Child FK set to `NULL` (column must be nullable) |
| `SET DEFAULT` | Child FK set to its default value (must be valid) |

Errors you should recognise:

```sql
DELETE FROM dbo.Customers WHERE CustomerId = 1;
-- Msg 547: The DELETE statement conflicted with the REFERENCE constraint
--          "FK__Orders__Customer..." (table dbo.Orders, column CustomerId)
INSERT dbo.Orders (CustomerId, OrderDate, Status) VALUES (99, '2024-01-01', N'Pending');
-- Msg 547: The INSERT statement conflicted with the FOREIGN KEY constraint ...
INSERT dbo.Customers (CustomerId, Name, Email) VALUES (9, N'Dup', N'alice@example.com');
-- Msg 2627: Violation of UNIQUE KEY constraint ... duplicate key value is (alice@example.com)
```

:::warn Key design mistakes
- **FKs are not indexed automatically.** Index every FK column (`Orders.CustomerId`), or joins and cascaded deletes scan the child table and can block.
- `CASCADE` deletes are dangerous on business data (deleting a customer wipes orders). Prefer soft delete or `NO ACTION` for financial data; SQL Server also rejects cascade paths that form cycles ("multiple cascade paths").
- A random `GUID` clustered PK causes page splits and fragmentation; use `NEWSEQUENTIALID()`, an ordered ID, or cluster on something else.
- `IDENTITY` is not gap-free and can be re-seeded; never use it as a business number (invoice numbers need their own sequence).
- A wide composite PK is copied into every nonclustered index and every child FK. Keep the clustered key narrow.
:::

:::q Difference between primary key and unique key?
A table has one primary key but can have many unique keys. A PK cannot be `NULL`; a unique key allows a single `NULL` in SQL Server. A PK creates a clustered index by default, a unique constraint creates a nonclustered unique index. Both enforce uniqueness and can be the target of a foreign key.
:::

:::q Candidate key vs alternate key vs super key?
A super key is any column set that is unique (even with extra columns). A candidate key is a *minimal* super key. The PK is the chosen candidate key; every other candidate key is an alternate key, enforced with a UNIQUE constraint. In `Customers`, `CustomerId` and `Email` are both candidate keys; `CustomerId` is the PK and `Email` is the alternate key.
:::

:::q Surrogate or natural key: which do you choose?
I use a surrogate PK (narrow, immutable, cheap to join) and still put a UNIQUE constraint on the natural business key, so I get both stability and integrity. Natural keys as PKs bite later when the value changes or turns out not to be unique after all.
:::
