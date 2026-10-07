## SQL Performance

The measurements in this group come from the 200,000-row `dbo.BigOrders` test table introduced under Indexes (`OrderId` clustered PK, plus `CustomerId`, `OrderDate`, `Status`, `Total`, `OrderRef VARCHAR(20)`). Your exact page counts will differ; the ratios are what matter.

### Reading an execution plan

**Definition.** An execution plan is the tree of physical operators the optimizer chose to run a query. The *estimated* plan is the optimizer's prediction (no execution); the *actual* plan also records real row counts, executions, memory grants and spills.

**Why it matters.** "The query is slow" becomes concrete only when you can say *which operator* reads too much and *why* the optimizer chose it.

How to get one: SSMS **Ctrl+L** (estimated) / **Ctrl+M** (include actual), `SET STATISTICS XML ON`, Query Store (history of plans per query), or `sys.dm_exec_query_plan(plan_handle)` for cached plans.

How to read it:

1. Read **right to left, top to bottom**: data flows from the leaf operators on the right toward `SELECT` on the left.
2. Look at the **thick arrows**: arrow width is row count. A fat arrow early in the plan that thins out later means filtering happened too late.
3. Compare **estimated vs actual rows** on each operator. A 10x+ gap usually means stale/missing statistics, parameter sniffing, a table variable, a multi-statement TVF, or a non-SARGable predicate. Bad estimates cause the wrong join type and memory grant.
4. Look for **warning triangles**: implicit conversion, spill to tempdb, missing statistics, no join predicate.
5. Operator cost percentages are *estimates* even in an actual plan; do not trust them blindly.

| Operator / sign | What it tells you | Typical fix |
|---|---|---|
| Table Scan / Clustered Index Scan on a big table for a selective query | No usable index, or predicate not SARGable | Index the predicate; rewrite the predicate |
| Key Lookup (with Nested Loops) executed thousands of times | Non-clustered index not covering | `INCLUDE` the missing columns, select fewer columns |
| Sort (especially with spill warning) | `ORDER BY`/merge join/`DISTINCT` without an index in that order | Index in the needed order; remove needless `ORDER BY`/`DISTINCT` |
| Hash Match with spill to tempdb | Memory grant too small (bad estimate) | Fix statistics/estimates; reduce rows earlier |
| Nested Loops with a scan on the inner side | Inner input not indexed on the join key | Index the join column (often an FK) |
| `CONVERT_IMPLICIT` in a predicate | Data type mismatch | Match parameter type to column type |
| Green "Missing Index" text | Optimizer suggests an index | Evaluate it; merge with existing indexes, check column order |
| Parallelism (Gather Streams) on a small OLTP query | High cost estimate, often from a scan | Fix the scan; tune cost threshold for parallelism |

### STATISTICS IO and STATISTICS TIME

```sql
SET STATISTICS IO, TIME ON;
SELECT OrderId, OrderDate, Total FROM dbo.BigOrders WHERE CustomerId = 42;
-- Table 'BigOrders'. Scan count 1, logical reads 3239, physical reads 413, read-ahead reads 3235
-- SQL Server Execution Times: CPU time = 31 ms, elapsed time = 45 ms.   (example)
SET STATISTICS IO, TIME OFF;
```

- **Logical reads** = 8 KB pages read from memory: the most stable metric for comparing two versions of a query (it does not depend on cache state or server load).
- **Physical / read-ahead reads** = pages pulled from disk (cold cache).
- **CPU vs elapsed time**: elapsed much larger than CPU means waiting (I/O, blocking, network).

### SARGability

**Definition.** A predicate is **SARGable** (Search ARGument-able) when SQL Server can use an index **seek** to satisfy it: the column must appear bare on one side of the comparison, with a compatible data type. Wrapping the column in a function, converting it, or using a leading wildcard forces it to evaluate *every row* (scan).

| Pattern | Bad (non-SARGable) | Good (SARGable) | Logical reads bad -> good |
|---|---|---|---|
| Function on column | `WHERE YEAR(OrderDate) = 2024 AND MONTH(OrderDate) = 3` | `WHERE OrderDate >= '2024-03-01' AND OrderDate < '2024-04-01'` | 548 -> 20 |
| Arithmetic on column | `WHERE DATEADD(DAY, 30, OrderDate) > '2024-12-31'` | `WHERE OrderDate > DATEADD(DAY, -30, '2024-12-31')` | 548 -> 19 |
| Implicit conversion | `VARCHAR` column `= @ref NVARCHAR(20)` | Parameter declared `VARCHAR(20)` | 574 -> 3 |
| Leading wildcard | `WHERE OrderRef LIKE '%23456'` | `WHERE OrderRef LIKE 'ORD12345%'` (or full-text search) | 574 -> 3 |
| `ISNULL`/`COALESCE` on column | `WHERE ISNULL(City, '') = 'Pune'` | `WHERE City = 'Pune'` | scan -> seek |
| String functions | `WHERE LEFT(Name, 2) = 'Al'` | `WHERE Name LIKE 'Al%'` | scan -> seek |
| `OR` across different columns | `WHERE CustomerId = 42 OR OrderRef = 'ORD000042'` | Two indexed queries combined with `UNION` (or `UNION ALL` + exclusion) | scan -> two seeks |
| Catch-all optional filter | `WHERE (@c IS NULL OR CustomerId = @c)` | Dynamic SQL with `sp_executesql`, or `OPTION (RECOMPILE)` | scan -> seek |

:::warn The .NET angle on implicit conversion
`AddWithValue("@ref", "ORD123456")` sends a .NET `string` as `NVARCHAR(4000)`. Against a `VARCHAR` column with a SQL collation the column is converted on every row: index scan plus a `CONVERT_IMPLICIT` warning. Use `Parameters.Add("@ref", SqlDbType.VarChar, 20)`, Dapper `new DbString { IsAnsi = true, Length = 20 }`, or EF Core `HasColumnType("varchar(20)")`/`IsUnicode(false)`.
:::

### Query optimization checklist

**Avoid `SELECT *`.** It returns unneeded data over the network, defeats covering indexes (forces key lookups: 3 reads became 134 in the index demo), breaks code when columns change, and drags `VARCHAR(MAX)`/blob columns along.

**Avoid unnecessary joins.** Every join is work and can multiply rows. Do not join a table only to "check it exists" when an `EXISTS` will do; do not join lookup tables whose columns you never select. With a *trusted* foreign key and a `NOT NULL` FK column, SQL Server can eliminate an unused inner join to the parent automatically; disabled/untrusted FKs (`WITH NOCHECK`) lose that.

**Avoid `DISTINCT` as a band-aid.** If duplicates appear, a one-to-many join is fanning out. `DISTINCT` adds a sort/hash over every column and hides the bug. Use `EXISTS` or aggregate the child first.

**More rules interviewers like to hear:**

- `EXISTS` instead of `COUNT(*) > 0` (stops at the first row).
- Set-based statements instead of cursors/`WHILE` loops; batch large `UPDATE`/`DELETE`s.
- `UNION ALL` instead of `UNION` when duplicates are impossible.
- Keep statistics fresh (`AUTO_UPDATE_STATISTICS`, scheduled `UPDATE STATISTICS` for big tables with skew).
- Filter early (in `WHERE`, before aggregation) and return only the rows the UI needs (pagination).
- Avoid scalar UDFs and multi-statement TVFs on large sets; prefer inline TVFs.
- Cache rarely changing reference data in the application instead of re-querying it.

**Index optimization in one breath:** find the top queries (Query Store, `sys.dm_exec_query_stats`), read their actual plans, add or adjust composite/covering indexes for their predicates and sort order, index FK columns, remove unused and duplicate indexes, keep statistics current, then re-measure with `STATISTICS IO`.

```sql
-- Most expensive cached queries by average logical reads
SELECT TOP (10)
       qs.total_logical_reads / qs.execution_count AS avg_reads,
       qs.execution_count,
       SUBSTRING(t.text, 1, 200)                   AS sql_text
FROM   sys.dm_exec_query_stats AS qs
CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) AS t
ORDER  BY avg_reads DESC;
```

### Pagination: OFFSET-FETCH vs keyset

```sql
-- OFFSET-FETCH: simple, supports "jump to page N"
SELECT OrderId, OrderDate, Total
FROM   dbo.BigOrders
ORDER  BY OrderId
OFFSET 190000 ROWS FETCH NEXT 20 ROWS ONLY;      -- 6,145 logical reads: reads and discards 190,000 rows

-- Keyset (seek) pagination: remember the last key of the previous page
DECLARE @LastOrderId INT = 190000;
SELECT TOP (20) OrderId, OrderDate, Total
FROM   dbo.BigOrders
WHERE  OrderId > @LastOrderId
ORDER  BY OrderId;                               -- 3 logical reads, for any page depth
```

| | OFFSET-FETCH | Keyset / seek |
|---|---|---|
| Cost of page N | Grows linearly with N | Constant (index seek) |
| Jump to arbitrary page | Yes | No (next/previous only) |
| Stable under concurrent inserts | No (rows shift between pages, duplicates/skips) | Yes |
| Requirement | Deterministic `ORDER BY` | Unique, indexed sort key (add the PK as tie-breaker: `WHERE (OrderDate, OrderId) > ...` written as `OrderDate > @d OR (OrderDate = @d AND OrderId > @id)`) |
| Typical UI | Admin grids with page numbers | Infinite scroll, APIs, exports |

## Concurrency: Locks, Blocking and Deadlocks

### Blocking

**Definition.** Blocking happens when one session holds a lock that another session needs in an incompatible mode (e.g. a writer's exclusive `X` lock on a row a reader wants to `S`-lock under `READ COMMITTED`). The second session waits. It is normal for milliseconds; it is a problem when a long transaction holds locks for seconds.

```sql
-- Who is blocked, by whom, waiting on what
SELECT r.session_id, r.blocking_session_id, r.wait_type, r.wait_time AS wait_ms,
       r.wait_resource, t.text AS running_sql
FROM   sys.dm_exec_requests AS r
CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) AS t
WHERE  r.blocking_session_id <> 0;

-- The head blocker is often IDLE with an open transaction (no row in dm_exec_requests)
SELECT s.session_id, s.login_name, s.host_name, s.program_name,
       s.open_transaction_count, t.text AS last_sql
FROM   sys.dm_exec_sessions AS s
JOIN   sys.dm_exec_connections AS c ON c.session_id = s.session_id
CROSS APPLY sys.dm_exec_sql_text(c.most_recent_sql_handle) AS t
WHERE  s.open_transaction_count > 0;
```

Also: `sp_who2`, Activity Monitor, `sys.dm_tran_locks`, the *blocked process report* Extended Event (threshold set via `sp_configure 'blocked process threshold'`).

Common causes and fixes: long transactions (a transaction left open across a user prompt or an HTTP call; fix: keep transactions short), missing indexes (an `UPDATE` scanning a table locks far more rows; fix: index the `WHERE`), lock escalation on big batch updates (fix: batch in chunks of a few thousand), and readers blocked by writers (fix: RCSI).

### Deadlocks

**Definition.** Two (or more) sessions each hold a lock the other needs, so neither can proceed. SQL Server's lock monitor detects the cycle (every ~5 s, faster when deadlocks are frequent), picks a **victim** (the cheapest to roll back, unless `DEADLOCK_PRIORITY` says otherwise), rolls it back and raises **error 1205**. The other session continues.

```sql
-- Session A                                   -- Session B
BEGIN TRAN;                                    BEGIN TRAN;
UPDATE dbo.Orders   SET Status = N'Paid'       UPDATE dbo.Payments SET Method = N'Card'
WHERE  OrderId = 103;    -- X lock on order    WHERE  OrderId = 103;  -- X lock on payments
UPDATE dbo.Payments SET Method = N'UPI'        UPDATE dbo.Orders   SET Status = N'Shipped'
WHERE  OrderId = 103;    -- waits for B        WHERE  OrderId = 103;  -- waits for A -> cycle
-- One session gets: Msg 1205 ... was deadlocked on lock resources with another process
-- and has been chosen as the deadlock victim. Rerun the transaction.
```

**Reading the deadlock graph.** Get it from the built-in `system_health` Extended Events session (no setup needed):

```sql
SELECT xed.event_data.value('(event/@timestamp)[1]', 'datetime2') AS deadlock_time,
       xed.event_data.query('(event/data/value/deadlock)[1]')     AS deadlock_graph
FROM (SELECT CAST(event_data AS XML) AS event_data
      FROM   sys.fn_xe_file_target_read_file('system_health*.xel', NULL, NULL, NULL)
      WHERE  object_name = 'xml_deadlock_report') AS xed
ORDER BY deadlock_time DESC;
```

In the XML/graph: `process-list` shows each session's statement, isolation level and the lock it *waits for*; `resource-list` shows each object/key (`keylock`, `pagelock`, index name) with its *owner* and *waiter*. The victim is marked. Read it as "A owns X on key K1 and wants U on K2; B owns X on K2 and wants S on K1".

**Prevention:**

| Technique | Why it helps |
|---|---|
| Access tables in the **same order** in every code path | Removes the cycle in the classic case above |
| Keep transactions **short**; no user/HTTP waits inside | Locks held for less time |
| **Index** the `WHERE`/`JOIN` columns of updates and deletes | Fewer rows/pages locked, no scans that collide |
| Use **RCSI/SNAPSHOT** | Readers stop taking shared locks, eliminating reader-writer deadlocks |
| `UPDLOCK` when you read-then-update | Prevents the two-readers-both-upgrade (conversion) deadlock |
| Lower isolation where safe (avoid `SERIALIZABLE` by default) | Fewer and shorter range locks |
| **Retry** on 1205 in the application | Deadlocks can be reduced but never fully eliminated |

```csharp
// Simple retry for deadlock victims (1205) - keep the whole transaction inside the delegate
async Task<T> WithDeadlockRetryAsync<T>(Func<Task<T>> work, int maxAttempts = 3)
{
    for (var attempt = 1; ; attempt++)
    {
        try { return await work(); }
        catch (SqlException ex) when (ex.Number == 1205 && attempt < maxAttempts)
        {
            await Task.Delay(TimeSpan.FromMilliseconds(100 * attempt));   // back off
        }
    }
}
// EF Core alternative: options.UseSqlServer(cs, o => o.EnableRetryOnFailure());
// (its transient-error list includes deadlocks; wrap manual transactions in
//  db.Database.CreateExecutionStrategy().ExecuteAsync(...))
```

:::q What is the difference between blocking and a deadlock?
Blocking is one session waiting for another's lock; it resolves itself when the holder commits. A deadlock is a cycle where each session waits on the other, so nobody can finish; SQL Server detects it, kills one transaction (error 1205) and lets the other continue. Blocking is fixed with short transactions and good indexes; deadlocks additionally need consistent access order and retry logic.
:::

## Transactions and Isolation Levels

### Transactions and ACID

**Definition.** A transaction is a unit of work that either completes entirely or not at all.

| Property | Meaning | How SQL Server provides it |
|---|---|---|
| **Atomicity** | All statements succeed or all are undone | Transaction log + rollback |
| **Consistency** | The database moves from one valid state to another (constraints hold) | Constraints, FKs, triggers checked at statement end |
| **Isolation** | Concurrent transactions do not see each other's intermediate state (to the chosen level) | Locks and/or row versions |
| **Durability** | Once committed, it survives a crash | Write-ahead logging: log hardened to disk at commit |

Modes: **autocommit** (default: every statement is its own transaction), **explicit** (`BEGIN TRAN ... COMMIT/ROLLBACK`), **implicit** (`SET IMPLICIT_TRANSACTIONS ON`, rarely used). From .NET: `SqlTransaction`, `DbContext.Database.BeginTransactionAsync()`, or `TransactionScope` (beware escalation to distributed transactions when two connections are opened).

### Isolation levels vs read phenomena

**Phenomena:**

- **Dirty read**: reading another transaction's *uncommitted* change (which may be rolled back).
- **Non-repeatable read**: reading the same row twice in one transaction and getting different values because someone committed an update in between.
- **Phantom read**: re-running a range query and getting *new rows* inserted by someone else.
- (**Lost update**: two transactions read, both update, one overwrites the other.)

| Isolation level | Dirty read | Non-repeatable read | Phantom | Mechanism | Readers block writers? |
|---|---|---|---|---|---|
| `READ UNCOMMITTED` (= `NOLOCK`) | Possible | Possible | Possible | No shared locks | No |
| `READ COMMITTED` (default, locking) | Prevented | Possible | Possible | Shared locks released after each read | Yes |
| `READ COMMITTED SNAPSHOT` (**RCSI**, a database option) | Prevented | Possible | Possible | Row versions as of **statement** start | **No** |
| `REPEATABLE READ` | Prevented | Prevented | Possible | Shared locks held until commit | Yes |
| `SNAPSHOT` | Prevented | Prevented | Prevented | Row versions as of **transaction** start; write-write conflict = error 3960 | **No** |
| `SERIALIZABLE` | Prevented | Prevented | Prevented | Key-range locks held until commit | Yes (most blocking) |

```sql
-- RCSI: database-wide, no code change; default in Azure SQL Database
ALTER DATABASE PrepDb SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;

-- SNAPSHOT: must be allowed, then opted into per session
ALTER DATABASE PrepDb SET ALLOW_SNAPSHOT_ISOLATION ON;
SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
BEGIN TRAN;
    SELECT SUM(Amount) FROM dbo.Payments;    -- consistent view for the whole transaction
COMMIT;
```

Row versioning costs: version store in tempdb (and in-row space with ADR), slightly more write overhead, and long-running transactions keep old versions alive. It is still the standard fix for reader/writer blocking in OLTP systems.

:::warn NOLOCK is not a performance switch
`WITH (NOLOCK)` / `READ UNCOMMITTED` can return **uncommitted data that is later rolled back**, **skip rows** or **read the same row twice** (allocation-order scans racing with page splits), and fail with error 601 (data movement). Totals in financial reports can simply be wrong. If the real problem is readers being blocked, enable **RCSI**: consistent committed data without shared locks.
:::

:::q Which isolation level would you choose for an e-commerce OLTP database?
`READ COMMITTED` with the RCSI option on: readers see committed data, never block writers, and the code does not change. For specific critical sections (inventory decrement, double-payment check) I take targeted locks such as `UPDLOCK, HOLDLOCK` or use `SERIALIZABLE` just for that transaction, or optimistic concurrency with a `rowversion` column.
:::

## Normalization and Data Modeling

### Normal forms with a worked example

**Definition.** Normalization organises tables so each fact is stored **once**, removing *update, insert and delete anomalies*. Each normal form builds on the previous one.

Start with a spreadsheet-style table:

| OrderId | OrderDate | CustomerName | CustomerCity | Products |
|---|---|---|---|---|
| 101 | 2024-01-10 | Alice | Pune | Laptop x1 @1000, Mouse x2 @25 |
| 102 | 2024-02-05 | Alice | Pune | Desk x1 @300 |

Anomalies: Alice moves city, you must update many rows (update anomaly); you cannot record a product that has never been ordered (insert anomaly); deleting order 102 might lose the only record of the Desk price (delete anomaly).

**1NF: atomic values, no repeating groups.** One value per cell, one row per order line.

| OrderId | ProductName | OrderDate | CustomerName | CustomerCity | UnitPrice | Qty |
|---|---|---|---|---|---|---|
| 101 | Laptop | 2024-01-10 | Alice | Pune | 1000 | 1 |
| 101 | Mouse | 2024-01-10 | Alice | Pune | 25 | 2 |
| 102 | Desk | 2024-02-05 | Alice | Pune | 300 | 1 |

Key: (`OrderId`, `ProductName`).

**2NF: 1NF + no partial dependency** (every non-key column depends on the *whole* composite key). `OrderDate`, `CustomerName`, `CustomerCity` depend only on `OrderId`; the catalogue price depends only on the product. Split:
`Orders(OrderId, OrderDate, CustomerName, CustomerCity)`, `Products(ProductId, Name, Price)`, `OrderItems(OrderId, ProductId, Qty, UnitPrice)`.
(`OrderItems.UnitPrice` stays deliberately: it is the price *at the time of sale*, a different fact from the current catalogue price.)

**3NF: 2NF + no transitive dependency** (non-key column depending on another non-key column). In `Orders`, `CustomerCity` depends on the customer, not the order. Split:
`Customers(CustomerId, Name, City)` and `Orders(OrderId, CustomerId, OrderDate)`. This is exactly the practice schema.

"Every non-key attribute depends on the key, the whole key, and nothing but the key."

**BCNF: every determinant is a candidate key.** It catches a rare case 3NF allows. Example: `AccountManagers(CustomerId, Category, Manager)`, key (`CustomerId`, `Category`), and each manager handles exactly one category (`Manager -> Category`). `Manager` is a determinant but not a key, so a manager's category is repeated per customer. Split into `ManagerCategory(Manager PK, Category)` and `CustomerManagers(CustomerId, Manager)`.

### Denormalization and OLTP vs OLAP

**Denormalization** deliberately reintroduces redundancy to make reads faster: storing `OrderTotal` on `Orders`, copying `CustomerName` into an invoice, a reporting table refreshed nightly, an indexed view. Do it when a measured read path is too slow and the data changes rarely; keep the copies in sync with triggers, application events, computed/indexed views, or batch jobs, and accept the consistency risk.

| | OLTP | OLAP |
|---|---|---|
| Purpose | Run the business: orders, payments | Analyse the business: trends, dashboards |
| Workload | Many small reads/writes, single rows | Few huge reads, aggregates over millions of rows |
| Schema | Normalized (3NF) | Denormalized star/snowflake (facts + dimensions) |
| Indexes | B-tree, narrow, selective | Columnstore, partitioning |
| Data | Current | Historical, loaded by ETL/ELT |
| Isolation concerns | Concurrency, locking | Mostly read-only |
| Examples | SQL Server/Azure SQL behind an API | Synapse, Fabric warehouse, SSAS, Power BI models |

:::q When would you denormalize?
When a frequent, measured read is too slow and the redundancy is cheap to keep correct: e.g. a stored order total for order lists, a read-model table for a dashboard, or a reporting warehouse. I keep the transactional source normalized and treat the denormalized copy as derived data with a clear refresh mechanism.
:::

## Quick-fire Q&A

:::q What is the logical order of execution of a SELECT?
FROM/JOIN, WHERE, GROUP BY, HAVING, SELECT (including window functions), DISTINCT, ORDER BY, TOP/OFFSET. So a SELECT alias works in ORDER BY but not in WHERE.
:::

:::q WHERE vs HAVING?
WHERE filters rows before grouping and cannot use aggregates. HAVING filters groups after aggregation and can. Put non-aggregate conditions in WHERE so fewer rows get grouped.
:::

:::q DELETE vs TRUNCATE?
DELETE is row-by-row logged, can have WHERE, fires triggers and keeps the identity counter. TRUNCATE deallocates pages, removes all rows, resets the identity, does not fire triggers, is blocked by referencing foreign keys, and can still be rolled back inside a transaction.
:::

:::q Why does NOT IN return no rows sometimes?
If the subquery returns a NULL, `x NOT IN (..., NULL)` is never TRUE under three-valued logic. Use NOT EXISTS or filter NULLs out.
:::

:::q INNER vs LEFT JOIN, and where do filters on the right table go?
INNER keeps only matches; LEFT keeps all left rows with NULLs for missing matches. Filters on the right table of a LEFT JOIN go in ON; in WHERE they discard the NULL rows and turn it into an inner join.
:::

:::q Clustered vs non-clustered index?
Clustered = the table itself sorted by the key, one per table. Non-clustered = separate B-tree of key + included columns + pointer to the row, many per table, may need key lookups.
:::

:::q What is a covering index?
A non-clustered index that contains every column a query needs (key columns for filtering/sorting, INCLUDE columns for the rest), so the query is answered from the index alone without key lookups.
:::

:::q How do you decide the column order of a composite index?
Equality-filtered columns first, then the range column, then sort columns; returned-only columns go in INCLUDE. Only a left-based prefix of the key can be seeked.
:::

:::q Reorganize vs rebuild?
Reorganize (roughly 5-30% fragmentation) is online and lightweight, defragmenting leaf pages in place. Rebuild (over 30%) recreates the index, updates its statistics, and is offline unless ONLINE = ON. On modern storage, up-to-date statistics matter more than fragmentation.
:::

:::q What makes a predicate non-SARGable?
Functions or arithmetic on the column, implicit type conversions, leading wildcards, and ORs across different columns. The fix is to leave the column bare and move the computation to the constant side.
:::

:::q Function vs stored procedure?
Functions return a value or table, are usable inside queries and cannot change data. Procedures can change data, manage transactions, use TRY/CATCH and dynamic SQL, but are called with EXEC. Prefer inline TVFs over scalar and multi-statement functions.
:::

:::q Temp table vs table variable vs CTE?
CTE: a named query for one statement, no storage. Table variable: small sets, no statistics, unaffected by rollback. Temp table: large or reused intermediate results with statistics and indexes.
:::

:::q How do you prevent deadlocks?
Access objects in the same order, keep transactions short, index update predicates, use RCSI for readers, take UPDLOCK when reading to update, and retry error 1205 in the application.
:::

:::q What is RCSI and why turn it on?
Read Committed Snapshot Isolation makes READ COMMITTED read the last committed row version instead of taking shared locks. Readers stop blocking writers and vice versa, with no code changes, at the cost of tempdb version store usage.
:::

:::q What is parameter sniffing?
The first execution's parameter values shape the cached plan. With skewed data it can be bad for other values. Fix with OPTION (RECOMPILE), OPTIMIZE FOR, better indexes, or Query Store plan forcing.
:::
