## Indexes

### How an index is built: the B-tree

**Definition.** A rowstore index in SQL Server is a balanced tree (B+ tree) of 8 KB pages: one **root** page, zero or more **intermediate** levels, and the **leaf** level. Each level is a doubly linked list in key order. Finding one key costs one page read per level (usually 2-4), no matter how big the table is.

**Why it matters.** Every indexing decision (which column first, what to include, why a lookup is expensive) follows from this picture.

```text
                       [ Root: 1 .. 120000 | 120001 .. 200000 ]          level 2
                        /                                 \
      [ Intermediate: 1..1500 | 1501..3000 | ... ]   [ ... ]             level 1
         /           |            \
   [Leaf 1..62] <-> [Leaf 63..124] <-> [Leaf 125..186] <-> ...           level 0
   Clustered index: the leaf pages ARE the data rows (all columns)
   Nonclustered:    leaf = index key + included columns + row locator
                    (the clustered key, or a RID if the table is a heap)
```

Measured on a 200,000-row test table `dbo.BigOrders(OrderId PK, CustomerId, OrderDate, Status, Total, Notes CHAR(100))`: the clustered index has **3 levels** (1 root page, 11 intermediate, 3,226 leaf pages). A seek on `OrderId` reads 3 pages; a full scan reads ~3,240.

### Clustered vs non-clustered index

**Definition.** The **clustered index** *is* the table: rows are stored in the leaf, sorted by the clustered key. A **non-clustered index** is a separate structure holding the key (plus included columns) and a pointer back to the row.

| | Clustered | Non-clustered |
|---|---|---|
| Per table | **1** (the table's physical order) | Up to 999 |
| Leaf level contains | All columns of the row | Key + `INCLUDE` columns + row locator |
| Created by default with | `PRIMARY KEY` | `UNIQUE` constraint, or `CREATE INDEX` |
| Extra storage | None (it is the data) | A copy of the indexed columns |
| Good for | Range scans on the key, `ORDER BY` key, the most common access path | Selective lookups on other columns, covering specific queries |
| Without it | Table is a **heap** (unordered, uses RIDs, forwarded records) | Lookups scan the table |

**Choosing the clustered key**: narrow, unique, static, ever-increasing (`INT`/`BIGINT IDENTITY`). The clustered key is copied into every non-clustered index, so a wide or random key (GUID from `NEWID()`) bloats them all and causes page splits.

### Seek vs scan vs lookup

Measured with `SET STATISTICS IO ON` on `BigOrders` (customer 42 has 40 orders out of 200,000):

```sql
SELECT OrderId, OrderDate, Total FROM dbo.BigOrders WHERE CustomerId = 42;
```

| Index available | Plan operators | Logical reads |
|---|---|---|
| Only the clustered PK | **Clustered Index Scan** (reads every row) | 3,239 |
| `IX (CustomerId)` | Index **Seek** + **Key Lookup** x 40 (Nested Loops) | 133 |
| `IX (CustomerId) INCLUDE (OrderDate, Total)` | Index **Seek** only (covering) | **3** |
| Same covering index but `SELECT *` | Seek + Key Lookup again (`Notes`, `Status` not in index) | 134 |

| Operator | Meaning | Good or bad? |
|---|---|---|
| Index Seek | Navigate the tree straight to the matching range | Good for selective predicates |
| Index/Clustered Index Scan | Read the whole leaf level (or a large range) | Fine for small tables or when most rows are needed; bad for "find a few rows" |
| Table Scan | Scan of a heap | Usually means a missing clustered index |
| Key Lookup / RID Lookup | For each row found in a non-clustered index, fetch missing columns from the clustered index/heap | Cheap for a few rows; disastrous for thousands (random I/O) |

The **tipping point**: if a non-clustered index would need lookups for more than a small percentage of the table (often well under 5%), the optimizer prefers a full scan. That is why an index on a low-selectivity column (`Status` with 4 values) is often ignored.

:::q What is a key lookup and how do you remove it?
The non-clustered index found the rows but does not contain every column the query needs, so SQL Server goes back to the clustered index once per row to fetch them. Fix it by adding the missing columns to the index as `INCLUDE` columns (a covering index), or by selecting fewer columns. Only cover columns for important queries; every included column costs storage and write time.
:::

### Composite index and column order

**Definition.** An index on more than one column. The B-tree is sorted by the first column, then by the second within equal first values, and so on, exactly like a phone book sorted by (LastName, FirstName).

**The rule**: an index can be *seeked* only on a **left-based prefix** of its key.

```sql
CREATE INDEX IX_BigOrders_Customer_Date ON dbo.BigOrders (CustomerId, OrderDate);

WHERE CustomerId = 42                              -- seek (leading column)
WHERE CustomerId = 42 AND OrderDate >= '2024-01-01' -- seek on both columns
WHERE CustomerId = 42 ORDER BY OrderDate           -- seek, and no Sort operator needed
WHERE OrderDate >= '2024-01-01'                    -- cannot seek: leading column missing -> scan
```

Ordering guideline for the key columns:

1. **Equality** predicates first (`CustomerId = @id`).
2. Then the **range/inequality** column (`OrderDate >= @from`); anything after a range column can no longer be seeked, only filtered.
3. Then columns for `ORDER BY`/`GROUP BY` if you want to avoid a sort.
4. Columns that are only *returned* go in `INCLUDE`, not the key.

"Most selective column first" is a myth when all columns are equality predicates; what matters is which queries can use the prefix.

### Covering, filtered and unique indexes

```sql
-- Covering: key = what you search/sort on, INCLUDE = what you return
CREATE NONCLUSTERED INDEX IX_BigOrders_CustomerId_Cover
    ON dbo.BigOrders (CustomerId) INCLUDE (OrderDate, Total);

-- Filtered: index only the rows a hot query touches (small, cheap to maintain)
CREATE NONCLUSTERED INDEX IX_Orders_Pending
    ON dbo.Orders (OrderDate) INCLUDE (CustomerId)
    WHERE Status = N'Pending';

-- Unique index: enforces uniqueness; filtered unique allows many NULLs
CREATE UNIQUE NONCLUSTERED INDEX UX_Customers_Phone
    ON dbo.Customers (Phone) WHERE Phone IS NOT NULL;     -- illustrative Phone column
```

- `INCLUDE` columns live only at the leaf level, are not sorted, and do not count toward the 900/1,700-byte key limit.
- A filtered index is used only when the query predicate provably matches (parameterised `WHERE Status = @s` may not use it; a literal or `OPTION (RECOMPILE)` will). Filtered indexes need `SET QUOTED_IDENTIFIER ON` and friends in the session.
- A `UNIQUE` index also gives the optimizer a guarantee (at most one row), which produces better plans.

### Columnstore indexes

A **columnstore** stores data column by column in compressed segments of ~1 million rows and processes them in *batch mode*. It is 10x+ faster and smaller for analytic scans and aggregates (`SUM` over millions of rows), and poor for single-row lookups. Use a clustered columnstore for fact tables in a warehouse, or a non-clustered columnstore on an OLTP table for real-time reporting (HTAP).

```sql
CREATE NONCLUSTERED COLUMNSTORE INDEX NCCI_BigOrders
    ON dbo.BigOrders (CustomerId, OrderDate, Status, Total);
```

### Index fragmentation and maintenance

**Definition.** *Logical (external) fragmentation*: leaf pages whose logical order no longer matches physical order, mostly caused by **page splits** when rows are inserted into a full page mid-index. *Page density (internal fragmentation)*: pages only partly full, wasting memory and I/O.

```sql
SELECT OBJECT_NAME(ps.object_id)      AS TableName,
       i.name                         AS IndexName,
       ps.avg_fragmentation_in_percent,
       ps.avg_page_space_used_in_percent,       -- NULL in LIMITED mode
       ps.page_count
FROM   sys.dm_db_index_physical_stats(DB_ID(), NULL, NULL, NULL, 'SAMPLED') AS ps
JOIN   sys.indexes AS i ON i.object_id = ps.object_id AND i.index_id = ps.index_id
WHERE  ps.page_count > 1000                      -- ignore small indexes
ORDER  BY ps.avg_fragmentation_in_percent DESC;
```

| Fragmentation | Classic guidance | Command |
|---|---|---|
| < 5% | Leave it | |
| 5% - 30% | **Reorganize**: online, always, interruptible, compacts leaf pages in place | `ALTER INDEX IX_x ON dbo.T REORGANIZE;` |
| > 30% | **Rebuild**: recreates the index, also updates its statistics with full scan; offline unless `ONLINE = ON` (Enterprise/Azure SQL) | `ALTER INDEX IX_x ON dbo.T REBUILD WITH (ONLINE = ON, FILLFACTOR = 90);` |

- **Fill factor** leaves free space in leaf pages at rebuild time (e.g. 90 = 10% free) to absorb inserts and reduce page splits on randomly-keyed indexes. Leave it at 100 (default `0`) for ever-increasing keys; lowering it everywhere just makes every read bigger.
- On SSD/SAN storage, fragmentation hurts far less than out-of-date **statistics**. Many teams now rebuild rarely and update statistics often (`UPDATE STATISTICS`, or Ola Hallengren's maintenance solution).
- `REORGANIZE` does not update statistics; `REBUILD` does (for that index).

### How to decide what to index

1. Start from the **workload**, not the table: the top queries by CPU/reads in Query Store or `sys.dm_exec_query_stats`.
2. Index columns used in `WHERE`, `JOIN ... ON`, `ORDER BY`, `GROUP BY` of those queries; always index **foreign-key columns**.
3. Prefer one well-designed composite/covering index over several single-column ones.
4. Consider selectivity: an index on a column with three values rarely gets a seek.
5. Read the **missing-index hints** in plans and `sys.dm_db_missing_index_details` as *suggestions*: they ignore existing indexes, column order nuance and write cost.
6. Count the cost: each index slows every `INSERT`, `DELETE` and relevant `UPDATE`, and uses memory. Find unused ones with `sys.dm_db_index_usage_stats` (high `user_updates`, zero seeks/scans) and drop duplicates.
7. Verify with the actual plan and `STATISTICS IO` before and after.

:::scenario Orders search page is slow
`SELECT OrderId, OrderDate, Total FROM Orders WHERE CustomerId = @c AND OrderDate >= @from ORDER BY OrderDate DESC` takes 2 s on 50 M rows; the plan shows a Clustered Index Scan and a Sort. Create `IX_Orders_Customer_Date ON Orders(CustomerId, OrderDate) INCLUDE (Total)`: equality column first, range/sort column second, returned column included. The plan becomes a single Index Seek with no Sort and no Key Lookup, reading a handful of pages. Check write overhead on the busiest insert path before shipping.
:::

:::q Clustered vs non-clustered index?
The clustered index defines the physical order of the table: its leaf pages are the data rows, so there is only one. A non-clustered index is a separate B-tree containing the key, any included columns and a pointer to the row (the clustered key), and you can have many. Queries using a non-clustered index may need key lookups to fetch other columns.
:::

:::q Can too many indexes hurt?
Yes. Every insert, delete and update of an indexed column must maintain every affected index, which adds I/O, log, locking and blocking. They also consume buffer pool memory and maintenance time. I keep indexes that serve real, frequent queries and drop unused or duplicate ones.
:::

## Stored Procedures

### Parameters, return codes and SET NOCOUNT

**Definition.** A stored procedure is a compiled, named T-SQL routine stored in the database. It takes **input** parameters (with optional defaults), **output** parameters (values handed back), returns an **integer status code** with `RETURN`, and can emit result sets.

**Why it matters.** Procs give you a stable API over the schema, plan reuse, fewer round trips, and a security boundary (grant `EXECUTE` without table access, which also blocks most SQL injection).

```sql
CREATE OR ALTER PROCEDURE dbo.usp_RecordPayment
    @OrderId   INT,                         -- input
    @Amount    DECIMAL(10,2),
    @Method    NVARCHAR(10) = N'Card',      -- input with a default
    @PaymentId INT OUTPUT                   -- output
AS
BEGIN
    SET NOCOUNT ON;     -- suppress "(1 row affected)" messages: less network chatter,
                        -- and some clients misread them as result sets
    SET XACT_ABORT ON;  -- any run-time error rolls back the whole transaction

    IF NOT EXISTS (SELECT 1 FROM dbo.Orders WHERE OrderId = @OrderId)
        RETURN 1;                                       -- status: not found
    IF EXISTS (SELECT 1 FROM dbo.Orders WHERE OrderId = @OrderId AND Status = N'Cancelled')
        RETURN 2;                                       -- status: cancelled

    BEGIN TRY
        BEGIN TRAN;
            DECLARE @Due DECIMAL(10,2) =
                  (SELECT SUM(Quantity * UnitPrice) FROM dbo.OrderItems WHERE OrderId = @OrderId)
                - (SELECT ISNULL(SUM(Amount), 0) FROM dbo.Payments WITH (UPDLOCK, HOLDLOCK)
                   WHERE OrderId = @OrderId);           -- lock to stop a concurrent double pay

            IF @Amount > @Due
                THROW 50010, N'Payment exceeds the amount due.', 1;

            INSERT dbo.Payments (OrderId, Amount, PaidAt, Method)
            VALUES (@OrderId, @Amount, CAST(SYSUTCDATETIME() AS DATE), @Method);
            SET @PaymentId = SCOPE_IDENTITY();

            IF @Amount = @Due
                UPDATE dbo.Orders SET Status = N'Paid' WHERE OrderId = @OrderId;
        COMMIT;
        RETURN 0;                                       -- success
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK;
        THROW;                                          -- re-raise the original error
    END CATCH
END;
GO

DECLARE @rc INT, @pid INT;
EXEC @rc = dbo.usp_RecordPayment @OrderId = 105, @Amount = 100.00, @Method = N'UPI',
                                 @PaymentId = @pid OUTPUT;
SELECT @rc AS ReturnCode, @pid AS PaymentId;   -- 0 | 6   (order 105 now 'Paid')
-- @OrderId = 104 -> returns 2 (cancelled);  @OrderId = 999 -> returns 1 (not found)
-- @OrderId = 102 (already fully paid), @Amount = 10
--   -> Msg 50010 'Payment exceeds the amount due.', @@TRANCOUNT back to 0
```

| Mechanism | Use for |
|---|---|
| `RETURN n` | Integer status only (0 = success by convention). Not for data |
| `OUTPUT` parameter | A few scalar values (new id, computed total) |
| Result set (`SELECT`) | Rows of data |
| `THROW` / error | Exceptional failures the caller must handle |

### Error handling: TRY...CATCH, THROW, XACT_ABORT

**Definition.** `BEGIN TRY ... END TRY BEGIN CATCH ... END CATCH` traps errors of severity 11-19 in the same scope. Inside `CATCH`, `ERROR_NUMBER()`, `ERROR_MESSAGE()`, `ERROR_LINE()`, `ERROR_PROCEDURE()` describe the error. `THROW` (2012+) raises or re-raises; `RAISERROR` is the legacy way.

| | `THROW` | `RAISERROR` |
|---|---|---|
| Re-raise original error inside `CATCH` | `THROW;` keeps the number, message, line | Not possible (raises a new error 50000) |
| Severity | Always 16 | Any |
| Aborts the batch | Yes (ends execution) | No, execution continues |
| Needs `sys.messages` entry | No (numbers >= 50000) | For message ids |
| Statement before it | Must end with `;` | n/a |

**`XACT_ABORT` matters.** With it `OFF` (the default), many run-time errors abort only the failing *statement*; the transaction stays open and `COMMIT` saves the half that worked:

```sql
SET XACT_ABORT OFF;
BEGIN TRAN;
    INSERT dbo.Payments (OrderId, Amount, PaidAt, Method) VALUES (106, 5, '2024-05-01', N'Card');
    INSERT dbo.Payments (OrderId, Amount, PaidAt, Method) VALUES (999, 5, '2024-05-01', N'Card');
    -- Msg 547 FK violation: only this statement fails
COMMIT;                     -- the first payment IS committed: a partial transaction
```

With `SET XACT_ABORT ON` the error dooms and rolls back the whole transaction. It also ensures that a client **timeout** (the client stops the batch, so no `CATCH` runs) does not leave an open transaction holding locks. Standard template: `SET NOCOUNT ON; SET XACT_ABORT ON;` + `TRY/CATCH` + `IF @@TRANCOUNT > 0 ROLLBACK; THROW;`.

`XACT_STATE()` in `CATCH`: `1` = active and committable, `-1` = doomed (only rollback allowed), `0` = no transaction.

### Transactions inside procedures and savepoints

`BEGIN TRAN` increments `@@TRANCOUNT`; `COMMIT` decrements it, and only the outermost commit really commits. `ROLLBACK` (without a name) rolls back **everything** to the outermost `BEGIN TRAN` and sets `@@TRANCOUNT` to 0. SQL Server has no true nested transactions.

A **savepoint** rolls back part of a transaction without ending it:

```sql
BEGIN TRAN;
    INSERT dbo.Payments (OrderId, Amount, PaidAt, Method) VALUES (106, 1, '2024-05-01', N'Card');
    SAVE TRAN BeforeStatus;
    UPDATE dbo.Orders SET Status = N'Refunded' WHERE OrderId = 106;
    ROLLBACK TRAN BeforeStatus;        -- undo only the UPDATE
    -- @@TRANCOUNT = 1, order 106 still 'Shipped', the payment insert is still pending
COMMIT;
```

Savepoints do not work once the transaction is doomed (`XACT_STATE() = -1`), and they do not release locks taken after the savepoint.

### Dynamic SQL: sp_executesql vs EXEC

**Definition.** Dynamic SQL builds a statement as a string at run time. Needed for optional filters ("catch-all search"), dynamic sort columns, or object names that vary.

```sql
CREATE OR ALTER PROCEDURE dbo.usp_SearchOrders
    @CustomerId INT = NULL, @Status NVARCHAR(20) = NULL, @FromDate DATE = NULL
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @sql NVARCHAR(MAX) = N'SELECT OrderId, CustomerId, OrderDate, Status
FROM dbo.Orders WHERE 1 = 1';
    IF @CustomerId IS NOT NULL SET @sql += N' AND CustomerId = @CustomerId';
    IF @Status     IS NOT NULL SET @sql += N' AND Status = @Status';
    IF @FromDate   IS NOT NULL SET @sql += N' AND OrderDate >= @FromDate';
    SET @sql += N' ORDER BY OrderDate;';

    EXEC sys.sp_executesql @sql,
         N'@CustomerId INT, @Status NVARCHAR(20), @FromDate DATE',   -- parameter list
         @CustomerId, @Status, @FromDate;                             -- values, never concatenated
END;
GO
EXEC dbo.usp_SearchOrders @CustomerId = 1, @FromDate = '2024-02-01';  -- 102, 105
EXEC dbo.usp_SearchOrders @Status = N'Shipped';                       -- 101, 102, 103, 106
```

Each combination of filters becomes its own small, well-indexed plan, cached and reused.

```sql
-- The injection: values concatenated into the string and run with EXEC
DECLARE @name NVARCHAR(100) = N'x'' OR 1=1 --';
DECLARE @bad  NVARCHAR(MAX) =
    N'SELECT CustomerId, Name FROM dbo.Customers WHERE Name = ''' + @name + N'''';
-- @bad = SELECT ... WHERE Name = 'x' OR 1=1 --'
EXEC (@bad);                                   -- returns ALL 4 customers

EXEC sys.sp_executesql
     N'SELECT CustomerId, Name FROM dbo.Customers WHERE Name = @name',
     N'@name NVARCHAR(100)', @name = @name;    -- 0 rows: the value is just data
```

| | `EXEC (@sql)` with concatenation | `sp_executesql` with parameters |
|---|---|---|
| SQL injection | Vulnerable | Safe for **values** |
| Plan reuse | New plan per distinct literal (plan-cache bloat) | One plan per statement shape |
| Output parameters | No | Yes |

Identifiers (table/column names) cannot be parameters: validate them against a whitelist or `sys.columns` and wrap with `QUOTENAME()`.

### Parameter sniffing

**Definition.** On first execution SQL Server compiles the procedure using the *actual parameter values* passed ("sniffs" them) and caches that plan for all later calls. Usually great. It becomes a problem when data is **skewed**: a plan built for a customer with 3 orders (seek + lookups) is reused for a customer with 2 million orders, or the reverse.

**Symptom**: "The proc is fast in SSMS but slow from the app", or "it was fine until this morning" (the plan was evicted and recompiled with an unusual value).

| Fix | How | Trade-off |
|---|---|---|
| `OPTION (RECOMPILE)` on the statement | Fresh plan for each call using the real values | CPU per execution; great for infrequent or reporting queries |
| `OPTIMIZE FOR (@CustomerId = 42)` | Always build the plan for a representative value | Bad for the other extreme |
| `OPTIMIZE FOR UNKNOWN` / copy into local variables | Use average density instead of the sniffed value | A mediocre plan for everyone |
| Separate procs / branches | Route big customers to a different statement | More code |
| Better index (covering) | Makes the seek plan good for all values | Write cost |
| Query Store plan forcing, PSP optimisation (2022+, compat 160) | Force a known good plan; SQL Server 2022 can cache multiple plans per parameter range | Needs monitoring |

```sql
SELECT OrderId, OrderDate, Total
FROM   dbo.BigOrders
WHERE  CustomerId = @CustomerId
OPTION (RECOMPILE);                                  -- or OPTIMIZE FOR (@CustomerId UNKNOWN)
```

"Slow in app, fast in SSMS" is often *different SET options* (`ARITHABORT` is ON in SSMS, OFF from ADO.NET), which gives SSMS a separate cache entry and a fresh, sniffed-for-your-value plan.

### Performance habits for procedures

- `SET NOCOUNT ON`; schema-qualify every object (`dbo.`); avoid the `sp_` prefix (SQL Server looks in `master` first).
- Set-based statements, not cursors or `WHILE` loops over rows.
- Keep transactions short; no user interaction or external calls inside them.
- Avoid functions on columns in `WHERE` (SARGability), implicit conversions (match parameter types to column types, e.g. `NVARCHAR` vs `VARCHAR`).
- Return only the columns needed; no `SELECT *`.
- Use `#temp` tables for large intermediate results, table variables for small ones.
- Watch for parameter sniffing on skewed data; capture plans with Query Store.

### Calling procedures from .NET

```csharp
// ADO.NET
await using var cmd = new SqlCommand("dbo.usp_RecordPayment", conn)
{ CommandType = CommandType.StoredProcedure };
cmd.Parameters.Add("@OrderId", SqlDbType.Int).Value = 105;
cmd.Parameters.Add("@Amount", SqlDbType.Decimal).Value = 100.00m;
cmd.Parameters["@Amount"].Precision = 10; cmd.Parameters["@Amount"].Scale = 2;
cmd.Parameters.Add("@Method", SqlDbType.NVarChar, 10).Value = "UPI";
var pid = cmd.Parameters.Add("@PaymentId", SqlDbType.Int);
pid.Direction = ParameterDirection.Output;
var rc = cmd.Parameters.Add("@rc", SqlDbType.Int);
rc.Direction = ParameterDirection.ReturnValue;

await cmd.ExecuteNonQueryAsync();          // SqlException carries Number = 50010 on THROW
int status = (int)rc.Value, paymentId = (int)pid.Value;
```

```csharp
// Dapper
var p = new DynamicParameters(new { OrderId = 105, Amount = 100.00m, Method = "UPI" });
p.Add("@PaymentId", dbType: DbType.Int32, direction: ParameterDirection.Output);
p.Add("@rc",        dbType: DbType.Int32, direction: ParameterDirection.ReturnValue);
await conn.ExecuteAsync("dbo.usp_RecordPayment", p, commandType: CommandType.StoredProcedure);
int paymentId = p.Get<int>("@PaymentId");

// Result-set proc into objects
var orders = await conn.QueryAsync<OrderDto>("dbo.usp_SearchOrders",
    new { CustomerId = 1 }, commandType: CommandType.StoredProcedure);
```

```csharp
// EF Core: FromSql is parameterised (the interpolation becomes a DbParameter)
var orders = await db.Orders
    .FromSql($"EXEC dbo.usp_SearchOrders @CustomerId = {customerId}")
    .ToListAsync();                       // proc must return all columns of the entity

// Non-query proc with output parameters
await db.Database.ExecuteSqlRawAsync(
    "EXEC @rc = dbo.usp_RecordPayment @OrderId, @Amount, @Method, @PaymentId OUTPUT",
    rcParam, orderIdParam, amountParam, methodParam, paymentIdParam);
```

:::warn Gotcha
`FromSqlRaw($"... {value}")` with string interpolation concatenates the value into SQL (injection). Use `FromSql`/`FromSqlInterpolated` with interpolation, or `FromSqlRaw` with explicit `SqlParameter` objects. Also, results of a stored proc in `FromSql` cannot be composed with further LINQ on the server.
:::

:::q How do you handle errors and transactions in a stored procedure?
`SET XACT_ABORT ON`, then `BEGIN TRY`, `BEGIN TRAN`, the work, `COMMIT`. In `CATCH`: `IF @@TRANCOUNT > 0 ROLLBACK;` then `THROW;` to re-raise the original error to the caller, which logs it. `XACT_ABORT` guarantees rollback even for errors that skip `CATCH`, such as client timeouts.
:::

:::q What is parameter sniffing and how do you fix it?
SQL Server compiles a plan for the first parameter values it sees and reuses it. With skewed data that plan can be terrible for other values. Fixes: `OPTION (RECOMPILE)` for statements that run rarely, `OPTIMIZE FOR` a typical value or `UNKNOWN`, a better covering index so one plan suits all values, or Query Store plan forcing. I diagnose by comparing estimated vs actual rows in the actual plan.
:::

:::q Why is sp_executesql preferred over EXEC for dynamic SQL?
It accepts real parameters, so values are never concatenated into the SQL text (no injection) and the plan is reused across values. `EXEC` of a concatenated string is injectable and compiles a new plan for every distinct literal.
:::
