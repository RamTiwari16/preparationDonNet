### How an index is built: the B-tree

**In simple words:** A normal SQL Server index is a balanced tree (*B-tree*) of 8 KB pages. It has a root page at the top, middle levels, and leaf pages at the bottom. To find one key, SQL Server reads one page per level, usually only 2 to 4 pages. That stays true even for very big tables.

**Real-life example:** Finding a word in a dictionary. You open at the right letter, then the right page, then the right word. You never read the whole book.

**Interview question:** How is an index stored, and why is a seek so fast?

**Simple answer:** It is a B+ tree of 8 KB pages: a root, intermediate levels and a leaf level, with leaf pages linked in key order. A seek goes from the root down to the leaf, reading one page per level. So finding one row among millions takes only a few page reads.

### Clustered vs non-clustered index

**In simple words:** The clustered index *is* the table: the rows are stored in its leaf pages, sorted by the key. So a table can have only one. A non-clustered index is a separate copy of some columns, with a pointer back to the row. You can have many of them.

**Real-life example:** A phone book sorted by last name is like a clustered index: the data itself is in that order. The index at the back of a textbook is non-clustered: it lists topics and points to page numbers.

**Interview question:** What is the difference between a clustered and a non-clustered index?

**Simple answer:** The clustered index stores the table rows in key order, so there is only one per table. A non-clustered index is a separate B-tree with the key, any included columns and a pointer to the row, and there can be many. A good clustered key is narrow, unique, unchanging and increasing, like an `INT IDENTITY`.

### Seek vs scan vs lookup

**In simple words:** A *seek* jumps through the index straight to the rows you need. A *scan* reads the whole index or table. A *key lookup* happens when a non-clustered index finds the rows but lacks some columns, so SQL Server goes back to the clustered index for each row. A few lookups are cheap; thousands are slow.

**Real-life example:** A seek is walking straight to shelf 42 in a library. A scan is walking past every shelf. A lookup is finding a book in the catalogue, then walking to the shelf to read the rest.

**Interview question:** What is a key lookup, and how do you remove it?

**Simple answer:** The non-clustered index found the rows but does not have every column the query needs, so SQL Server fetches them from the clustered index, once per row. I fix it by adding the missing columns with `INCLUDE` (a covering index), or by selecting fewer columns. I cover only important queries, because each extra column costs storage and write time.

```sql
CREATE INDEX IX_BigOrders_CustomerId
    ON dbo.BigOrders (CustomerId) INCLUDE (OrderDate, Total);
-- WHERE CustomerId = 42: seek only, no key lookup
```

### Composite index and column order

**In simple words:** A *composite index* has more than one column. It is sorted by the first column, then by the second inside the first, and so on. SQL Server can seek only on a left-based prefix of the key. So an index on (CustomerId, OrderDate) helps `WHERE CustomerId = 42`, but not `WHERE OrderDate > '2024-01-01'` alone.

**Real-life example:** A phone book sorted by (last name, first name). You can quickly find all "Sharma"s, or "Sharma, Ravi". But you cannot quickly find everyone called "Ravi".

**Interview question:** How do you decide the column order of a composite index?

**Simple answer:** Equality columns first, then the range column, then columns used for sorting. Columns that are only returned go in `INCLUDE`. Only a left-based prefix of the key can be used for a seek.

```sql
CREATE INDEX IX_Customer_Date ON dbo.BigOrders (CustomerId, OrderDate);
-- seek: WHERE CustomerId = 42 AND OrderDate >= '2024-01-01'
-- scan: WHERE OrderDate >= '2024-01-01'   (first column missing)
```

### Covering, filtered and unique indexes

**In simple words:** A *covering index* holds every column a query needs, so no lookups are needed. Key columns are for searching and sorting; `INCLUDE` columns are only returned. A *filtered index* covers only some rows, chosen with a `WHERE`, so it is small and cheap. A *unique index* blocks duplicate values and also helps the optimizer.

**Real-life example:** A covering index is a cheat sheet with every answer you need. A filtered index is a list of only the overdue library books, not all books.

**Interview question:** What is a covering index, and when would you use a filtered index?

**Simple answer:** A covering index has all the columns a query needs, so the query is answered from the index alone, without key lookups. A filtered index includes only rows that match a condition, like `WHERE Status = 'Pending'`, so it is small and fast for that hot query. A filtered unique index can also allow many NULLs while keeping other values unique.

```sql
CREATE INDEX IX_Orders_Pending
    ON dbo.Orders (OrderDate) INCLUDE (CustomerId)
    WHERE Status = N'Pending';
```

### Columnstore indexes

**In simple words:** A *columnstore* index stores data column by column, compressed, instead of row by row. It processes many rows at once, which is called *batch mode*. This makes big reports, like a SUM over millions of rows, much faster. It is poor for finding single rows.

**Real-life example:** To add up all prices in a shop, reading one long price list is faster than opening every product box and reading its label.

**Interview question:** When would you use a columnstore index?

**Simple answer:** For analytics: large scans and aggregates, like data-warehouse fact tables, where it is often 10 times faster and much smaller. I can also add a non-clustered columnstore to an OLTP table for real-time reports. For single-row lookups, a normal B-tree (rowstore) index is better.

### Index fragmentation and maintenance

**In simple words:** Over time, inserts cause *page splits*, which leave index pages out of order and partly empty — this is *fragmentation*. Between about 5% and 30%, you can REORGANIZE, which is light and online. Above 30%, you can REBUILD, which recreates the index and updates its statistics. On modern SSD storage, fresh statistics usually matter more than fragmentation.

**Real-life example:** A library shelf where new books are squeezed in wherever there is space. Reorganizing tidies the shelf; rebuilding takes all the books off and puts them back in perfect order.

**Interview question:** What is the difference between reorganizing and rebuilding an index?

**Simple answer:** Reorganize is online, light and can be stopped; it compacts and re-orders the leaf pages in place, but it does not update statistics. Rebuild recreates the index and updates its statistics, and it is offline unless I use `ONLINE = ON`. Many teams now rebuild rarely and update statistics often.

```sql
ALTER INDEX IX_x ON dbo.T REORGANIZE;
ALTER INDEX IX_x ON dbo.T REBUILD WITH (ONLINE = ON);
```

### How to decide what to index

**In simple words:** Start from the real workload, not from the table. Find the most expensive queries, for example in Query Store. Index the columns they use in WHERE, JOIN, ORDER BY and GROUP BY, and always index foreign keys. Remember that each index slows inserts, updates and deletes.

**Real-life example:** A supermarket puts the most-bought items near the door. It does not move every item; it looks at what customers really buy.

**Interview question:** Can too many indexes hurt performance?

**Simple answer:** Yes. Every insert, delete and update of an indexed column must also update each index, which adds I/O, log writes and locking, and indexes use memory too. I add indexes for real, frequent queries, treat missing-index hints only as suggestions, and drop unused or duplicate indexes found with `sys.dm_db_index_usage_stats`.

### Parameters, return codes and SET NOCOUNT

**In simple words:** A stored procedure can take input parameters (with defaults) and output parameters (values sent back). `RETURN n` sends back a whole-number status code, where 0 usually means success. Rows of data come back as result sets. `SET NOCOUNT ON` stops the "(1 row affected)" messages, which saves network traffic.

**Real-life example:** At a post office, you hand in a parcel and an address (input). You get a tracking number back (output), and the clerk says "done" or "address not found" (return code).

**Interview question:** What is the difference between a return value, an output parameter and a result set?

**Simple answer:** `RETURN` gives only an integer status, like 0 for success. An output parameter returns a few single values, like a new ID, and a result set returns rows of data. Real errors should be raised with `THROW`, not hidden in a return code.

```sql
CREATE PROCEDURE dbo.usp_AddOrder @CustomerId INT, @OrderId INT OUTPUT
AS BEGIN
    SET NOCOUNT ON;
    INSERT dbo.Orders (CustomerId, OrderDate, Status)
    VALUES (@CustomerId, CAST(GETDATE() AS DATE), N'Pending');
    SET @OrderId = SCOPE_IDENTITY();
    RETURN 0;
END;
```

### Error handling: TRY...CATCH, THROW, XACT_ABORT

**In simple words:** `BEGIN TRY ... END TRY BEGIN CATCH ... END CATCH` catches errors, like try/catch in C#. Inside CATCH, `THROW;` re-raises the original error. By default, many errors stop only the failing statement, and the transaction stays open. `SET XACT_ABORT ON` makes any error roll back the whole transaction.

**Real-life example:** When a bank transfer fails halfway, you want the bank to cancel the whole transfer. You do not want it to keep the money already taken from your account.

**Interview question:** How do you handle errors and transactions in a stored procedure?

**Simple answer:** I start with `SET XACT_ABORT ON`, then `BEGIN TRY`, `BEGIN TRAN`, the work and `COMMIT`. In CATCH I write `IF @@TRANCOUNT > 0 ROLLBACK;` and then `THROW;`, so the caller gets the original error. XACT_ABORT also rolls back when the client times out and CATCH never runs.

```sql
SET XACT_ABORT ON;
BEGIN TRY
    BEGIN TRAN;  /* work here */  COMMIT;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK;
    THROW;
END CATCH
```

### Transactions inside procedures and savepoints

**In simple words:** `BEGIN TRAN` adds 1 to `@@TRANCOUNT`, and `COMMIT` takes 1 away; only the outermost COMMIT really saves the work. A plain `ROLLBACK` undoes everything and sets the count to 0. So SQL Server has no true nested transactions. A *savepoint* (`SAVE TRAN name`) lets you undo only part of a transaction.

**Real-life example:** Writing a long document with "undo to checkpoint". You can go back to the checkpoint without losing everything you wrote before it.

**Interview question:** Does SQL Server support nested transactions?

**Simple answer:** Not really. Inner BEGIN TRAN and COMMIT only change `@@TRANCOUNT`, the outer COMMIT does the real commit, and any plain ROLLBACK undoes everything. To undo part of the work, I use `SAVE TRAN` and `ROLLBACK TRAN name`, which stop working once the transaction is doomed.

```sql
BEGIN TRAN;
    INSERT dbo.Payments (OrderId, Amount, PaidAt, Method)
    VALUES (106, 1, '2024-05-01', N'Card');
    SAVE TRAN BeforeStatus;
    UPDATE dbo.Orders SET Status = N'Refunded' WHERE OrderId = 106;
    ROLLBACK TRAN BeforeStatus;   -- undo only the UPDATE
COMMIT;
```

### Dynamic SQL: sp_executesql vs EXEC

**In simple words:** *Dynamic SQL* builds a SQL statement as a string at run time, for example for optional search filters. `sp_executesql` lets you pass real parameters, so values are never pasted into the SQL text. `EXEC(@sql)` with values joined into the string is open to *SQL injection* (attackers changing your SQL). Table or column names cannot be parameters, so check them against a list and wrap them with `QUOTENAME()`.

**Real-life example:** A form with fixed boxes for each answer (parameters) is safe. Letting someone write anything into the middle of your instructions (joining strings) lets them change the instructions.

**Interview question:** Why is sp_executesql preferred over EXEC for dynamic SQL?

**Simple answer:** It accepts typed parameters, so values stay as data and cannot inject SQL. The plan is also reused for different values. `EXEC` with a joined string can be injected and creates a new plan for each different value.

```sql
EXEC sys.sp_executesql
     N'SELECT CustomerId, Name FROM dbo.Customers WHERE Name = @name',
     N'@name NVARCHAR(100)',
     @name = @name;
```

### Parameter sniffing

**In simple words:** The first time a procedure runs, SQL Server builds a plan using the actual parameter values it sees ("sniffs") and caches that plan. Later calls reuse it. This is usually good. But with uneven data, a plan built for a customer with 3 orders can be terrible for a customer with 2 million orders.

**Real-life example:** A tour guide plans a route for the first group, which is small. Later a group of 200 arrives, and the narrow path chosen for 5 people is now a disaster.

**Interview question:** What is parameter sniffing, and how do you fix it?

**Simple answer:** SQL Server builds and caches a plan for the first parameter values, and that plan can be bad for very different values. Fixes include `OPTION (RECOMPILE)` for rarely run statements, `OPTIMIZE FOR` a typical value or UNKNOWN, a better covering index, or Query Store plan forcing. I confirm it by comparing estimated and actual rows in the actual plan.

```sql
SELECT OrderId, OrderDate, Total
FROM   dbo.BigOrders
WHERE  CustomerId = @CustomerId
OPTION (RECOMPILE);   -- fresh plan for each value
```

### Performance habits for procedures

**In simple words:** A few habits keep procedures fast. Use `SET NOCOUNT ON` and always write the schema, like `dbo.Orders`. Do not start procedure names with `sp_`, because SQL Server looks in the master database first. Use set-based statements instead of loops, keep transactions short, and return only the columns you need.

**Real-life example:** A delivery driver plans one route for all parcels, instead of driving back to the depot after each one.

**Interview question:** What best practices do you follow when writing stored procedures?

**Simple answer:** `SET NOCOUNT ON`, schema-qualified names, no `sp_` prefix, and set-based code instead of cursors. I keep transactions short, avoid functions on columns in WHERE, and match parameter types to column types. I use temp tables for big middle results and watch for parameter sniffing in Query Store.

### Calling procedures from .NET

**In simple words:** In ADO.NET, you create a `SqlCommand` with `CommandType.StoredProcedure` and add typed parameters. Output parameters and return values use `ParameterDirection`. Dapper does the same with `DynamicParameters`. In EF Core, you use `FromSql` for results or `ExecuteSql` for commands.

**Real-life example:** It is like filling in a bank's official form. You write each value in its own box, hand it in, and read the answer from the reply boxes.

**Interview question:** How do you call a stored procedure with an output parameter from C#?

**Simple answer:** I set `CommandType.StoredProcedure`, add typed input parameters, and add the output parameter with `Direction = ParameterDirection.Output`. After running the command, I read its `Value`. I never build SQL by joining strings: `FromSqlRaw` with string interpolation is not safe, but `FromSql` is.

```csharp
var cmd = new SqlCommand("dbo.usp_RecordPayment", conn)
    { CommandType = CommandType.StoredProcedure };
cmd.Parameters.Add("@OrderId", SqlDbType.Int).Value = 105;
cmd.Parameters.Add("@Amount", SqlDbType.Decimal).Value = 100.00m;
var pid = cmd.Parameters.Add("@PaymentId", SqlDbType.Int);
pid.Direction = ParameterDirection.Output;
await cmd.ExecuteNonQueryAsync();
int paymentId = (int)pid.Value;
```

### What a window function is

**In simple words:** A *window function* calculates a value for each row using a group of related rows, defined with `OVER (...)`. Unlike `GROUP BY`, it does not merge rows, so you keep all the detail. `PARTITION BY` splits rows into groups, and `ORDER BY` sets the order inside each group. Window functions run in the SELECT step, so you cannot use them in WHERE.

**Real-life example:** On a class result sheet, each student's row shows their own mark and the class average next to it. No student's row disappears.

**Interview question:** What is a window function, and how is it different from GROUP BY?

**Simple answer:** It computes a value over a set of rows for each row, without merging the rows. GROUP BY returns one row per group and loses the detail columns. With a window function, I can show each employee's salary next to their department total.

```sql
SELECT Name, DepartmentId, Salary,
       SUM(Salary) OVER (PARTITION BY DepartmentId) AS DeptPayroll
FROM   dbo.Employees;
```

### ROW_NUMBER, RANK, DENSE_RANK, NTILE

**In simple words:** These functions number rows in a chosen order, and they differ only in how they treat ties. `ROW_NUMBER` always gives unique numbers (1, 2, 3, 4). `RANK` gives ties the same number and then skips (1, 2, 2, 4). `DENSE_RANK` gives ties the same number with no gaps (1, 2, 2, 3), and `NTILE(n)` splits rows into n nearly equal groups.

**Real-life example:** In a race, two runners finish together in second place. RANK says the next runner is 4th. DENSE_RANK says the next runner is 3rd. ROW_NUMBER just gives everyone a different bib number.

**Interview question:** What is the difference between ROW_NUMBER, RANK and DENSE_RANK?

**Simple answer:** ROW_NUMBER gives unique numbers even for ties, RANK gives ties the same number and leaves gaps, and DENSE_RANK gives ties the same number with no gaps. For "second highest salary" with ties I use DENSE_RANK, and to remove duplicates I use ROW_NUMBER. With ROW_NUMBER, I add a unique tie-breaker, like the ID, so the result is stable.

```sql
SELECT Name, Salary,
       ROW_NUMBER() OVER (ORDER BY Salary DESC, EmployeeId) AS RowNum,
       RANK()       OVER (ORDER BY Salary DESC) AS Rnk,
       DENSE_RANK() OVER (ORDER BY Salary DESC) AS DenseRnk
FROM   dbo.Employees;
```

### PARTITION BY: per-group calculations

**In simple words:** `PARTITION BY` restarts the window calculation for each group. For example, `ROW_NUMBER() OVER (PARTITION BY DepartmentId ...)` starts again at 1 in each department. With aggregates, you get group totals next to each detail row. `OVER ()` with nothing inside treats all rows as one group.

**Real-life example:** Each class in a school ranks its own students. The best student in every class is number 1, not only the best student in the whole school.

**Interview question:** What is the difference between PARTITION BY and GROUP BY?

**Simple answer:** GROUP BY collapses each group into one row, so the detail columns are lost. PARTITION BY makes groups for a window function but keeps every row. To get "top earner per department", I rank inside a CTE with PARTITION BY and filter outside it.

```sql
WITH r AS (
    SELECT Name, DepartmentId, Salary,
           DENSE_RANK() OVER (PARTITION BY DepartmentId ORDER BY Salary DESC) AS dr
    FROM dbo.Employees
)
SELECT Name, DepartmentId, Salary FROM r WHERE dr = 1;
```

### LAG and LEAD

**In simple words:** `LAG` reads a value from an earlier row, and `LEAD` reads a value from a later row, in the window's order. By default, they look 1 row away and return NULL when there is no such row. They are great for comparing a row with the one before it, without a self-join.

**Real-life example:** Looking at this month's electricity bill and comparing it with last month's bill on the same page.

**Interview question:** How do you compare each row with the previous row?

**Simple answer:** I use `LAG(col) OVER (PARTITION BY ... ORDER BY ...)` to get the previous value, and then subtract. This gives month-over-month change, days between orders, and similar results. `LAG(col, 1, 0)` returns 0 instead of NULL for the first row.

```sql
SELECT CustomerId, OrderId, OrderDate,
       LAG(OrderDate)  OVER (PARTITION BY CustomerId ORDER BY OrderDate) AS PrevDate,
       LEAD(OrderDate) OVER (PARTITION BY CustomerId ORDER BY OrderDate) AS NextDate
FROM   dbo.Orders;
```

### FIRST_VALUE and LAST_VALUE

**In simple words:** `FIRST_VALUE` returns the first value in the window, and `LAST_VALUE` returns the last one. LAST_VALUE often looks wrong. With `ORDER BY`, the default *frame* (the rows the function can see) ends at the current row. So the "last" row is simply the current row.

**Real-life example:** You ask "who is last in the queue?", but you can only see people up to yourself. So you answer "me" every time.

**Interview question:** Why does LAST_VALUE return the current row's value?

**Simple answer:** Because the default frame with ORDER BY goes from the start up to the current row, so the last row in the frame is the current row. I fix it with `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`. Or I use FIRST_VALUE with the order reversed.

```sql
SELECT Name, DepartmentId,
       LAST_VALUE(Name) OVER (PARTITION BY DepartmentId ORDER BY Salary DESC
           ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS LowestEarner
FROM   dbo.Employees;
```

### Running totals, frames, ROWS vs RANGE

**In simple words:** A *frame* says which rows around the current row a window aggregate uses; `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` gives a running total. `ROWS` counts physical rows. `RANGE` treats rows with the same ORDER BY value as one block. If you write ORDER BY without a frame, the default is RANGE, which gives tied rows the same total.

**Real-life example:** A running bank balance after each payment. If two payments happen on the same day, RANGE shows the same balance for both, while ROWS shows each step.

**Interview question:** Your running total shows the same value for two rows. Why?

**Simple answer:** The window has ORDER BY but no frame, so SQL Server uses the default `RANGE UNBOUNDED PRECEDING`. Rows with the same order value are treated as peers and get the same total. I write `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` with a unique ORDER BY, and ROWS is also faster.

```sql
SELECT OrderId, OrderDate, Total,
       SUM(Total) OVER (ORDER BY OrderDate, OrderId
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS RunningTotal
FROM   OrderTotals;   -- a CTE with one row and Total per order
```

### COUNT() OVER and other aggregates

**In simple words:** Every aggregate, like SUM, COUNT, AVG, MIN and MAX, can also be a window function. `COUNT(*) OVER (PARTITION BY CustomerId)` shows each order with its customer's total number of orders. You can use this to find duplicates and still see every row. `COUNT(DISTINCT ...) OVER` is not supported in SQL Server.

**Real-life example:** Each student's report card says "you are one of 32 students in this class", without merging all the report cards into one.

**Interview question:** How do you find duplicate rows but still show every duplicate row?

**Simple answer:** I add `COUNT(*) OVER (PARTITION BY the duplicate columns)` in a subquery and keep rows where the count is greater than 1. GROUP BY with HAVING would show only one row per group. A window count keeps all the detail.

```sql
SELECT * FROM (
    SELECT *, COUNT(*) OVER (PARTITION BY Salary) AS SameSalary
    FROM dbo.Employees
) x
WHERE SameSalary > 1;
```

### Window functions: common patterns

**In simple words:** A few window patterns solve many interview questions. Top N per group uses ROW_NUMBER or DENSE_RANK with PARTITION BY, then filters `rn <= N`. Removing duplicates uses ROW_NUMBER in a CTE and deletes rows where `rn > 1`. Running totals use SUM with ROWS, and change from the previous row uses LAG.

**Real-life example:** A toolbox with a few favourite tools. Once you know which tool fits which job, most repairs are quick.

**Interview question:** How do you delete duplicate rows but keep one copy?

**Simple answer:** I number the rows in each duplicate group with `ROW_NUMBER() OVER (PARTITION BY the duplicate columns ORDER BY Id)` in a CTE. Then I delete from the CTE where the number is greater than 1. The ORDER BY decides which copy is kept.

```sql
WITH d AS (
    SELECT ROW_NUMBER() OVER (PARTITION BY Email ORDER BY CustomerId) AS rn
    FROM dbo.Customers
)
DELETE FROM d WHERE rn > 1;
```

### Reading an execution plan

**In simple words:** An *execution plan* shows the steps SQL Server chose to run your query. The estimated plan is a guess made without running; the actual plan also shows real row counts. Read it from right to left. Look for big gaps between estimated and actual rows, thick arrows, scans on big tables, key lookups and warning signs.

**Real-life example:** It is like the route on a map app after a slow trip. It shows exactly which road had the traffic jam.

**Interview question:** How do you read an execution plan to find the slow part?

**Simple answer:** I get the actual plan and read it right to left, following the thick arrows. I compare estimated and actual rows, because a big difference often means old statistics or parameter sniffing. Then I look for scans on big tables, many key lookups, sorts or hash spills to tempdb, and implicit conversion warnings.

### STATISTICS IO and STATISTICS TIME

**In simple words:** `SET STATISTICS IO, TIME ON` makes SQL Server print how many pages each query read and how long it took. *Logical reads* are 8 KB pages read from memory. They are the best number for comparing two versions of a query, because they do not depend on the cache or server load.

**Real-life example:** Counting how many pages you turned to find an answer. Fewer pages means a smarter way of searching, no matter how fast you read today.

**Interview question:** How do you measure whether a query change really helped?

**Simple answer:** I turn on STATISTICS IO and TIME, and compare logical reads before and after the change. Logical reads stay stable between runs, unlike time. If elapsed time is much bigger than CPU time, the query is waiting, for example on disk or on blocking.

```sql
SET STATISTICS IO, TIME ON;
SELECT OrderId, OrderDate, Total FROM dbo.BigOrders WHERE CustomerId = 42;
SET STATISTICS IO, TIME OFF;
```

### SARGability

**In simple words:** A condition is *SARGable* when SQL Server can use an index seek for it. The column must stand alone on one side of the comparison, with a matching data type. Putting the column inside a function, doing maths on it, a type mismatch, or a leading `%` wildcard forces a scan of every row.

**Real-life example:** In a phone book you can quickly find "names starting with Sha". But "names ending with rma" means reading every name in the book.

**Interview question:** What makes a predicate non-SARGable, and how do you fix it?

**Simple answer:** Functions or maths on the column, implicit type conversions, leading wildcards, and OR across different columns. The fix is to leave the column bare and move the calculation to the other side. For example, I use a date range instead of `YEAR(OrderDate) = 2024`.

```sql
-- Bad: scan
WHERE YEAR(OrderDate) = 2024
-- Good: seek
WHERE OrderDate >= '2024-01-01' AND OrderDate < '2025-01-01'
```

### Query optimization checklist

**In simple words:** A few simple rules fix most slow queries: no `SELECT *`, no joins you do not need, and no `DISTINCT` to hide duplicate rows from a bad join. Use `EXISTS` instead of `COUNT(*) > 0`, and set-based code instead of loops. Filter early, return only the rows you need, and keep statistics up to date.

**Real-life example:** Packing for a trip: take only what you need, do not pack the same shirt twice, and check the weather (statistics) before you leave.

**Interview question:** A query is slow. What do you check first?

**Simple answer:** I find the expensive query in Query Store, read its actual plan and measure logical reads. Then I check for SELECT *, extra joins, DISTINCT hiding a fan-out, non-SARGable conditions, and missing or non-covering indexes. After each change I measure again.

### Pagination: OFFSET-FETCH vs keyset

**In simple words:** `OFFSET ... FETCH` skips N rows and returns the next page. It is simple, but SQL Server still reads all the skipped rows, so deep pages are slow. Keyset paging remembers the last key and asks for the rows after it. It uses an index seek, so every page costs the same.

**Real-life example:** OFFSET is counting from the first page of a book every time. Keyset is opening the book at your bookmark.

**Interview question:** Why is deep OFFSET paging slow, and what is the alternative?

**Simple answer:** OFFSET must read and throw away all skipped rows, so page 10,000 reads far more than page 1. Keyset paging uses `TOP` with `WHERE Id > @lastId ORDER BY Id`, so it is an index seek at any depth and stays stable when new rows arrive. The downside is that users cannot jump to any page number.

```sql
SELECT TOP (20) OrderId, OrderDate, Total
FROM   dbo.BigOrders
WHERE  OrderId > @LastOrderId
ORDER  BY OrderId;
```

### Blocking

**In simple words:** *Blocking* happens when one session holds a lock that another session needs, so the second one waits. Short waits are normal. It becomes a problem when a long transaction keeps its locks for seconds or minutes. You can see who blocks whom in `sys.dm_exec_requests`.

**Real-life example:** One person stays in the only bathroom for a long time. Everyone else waits in the queue until they come out.

**Interview question:** What causes blocking, and how do you reduce it?

**Simple answer:** Common causes are long open transactions, missing indexes that make updates lock many rows, big batch updates, and readers waiting for writers. I keep transactions short, index the WHERE columns of updates, and split big changes into smaller batches. I also turn on RCSI, so readers and writers do not block each other.

```sql
SELECT session_id, blocking_session_id, wait_type, wait_time
FROM   sys.dm_exec_requests
WHERE  blocking_session_id <> 0;
```

### Deadlocks

**In simple words:** A *deadlock* is when two sessions each hold a lock the other needs, so neither can continue. SQL Server finds this circle and picks one session as the *victim*. It rolls that one back with error 1205, and the other session continues. You can see the details in the deadlock graph from the `system_health` session.

**Real-life example:** Two cars meet on a narrow bridge from opposite sides. Neither can move until one of them backs out.

**Interview question:** What is the difference between blocking and a deadlock, and how do you prevent deadlocks?

**Simple answer:** Blocking is one session waiting, and it ends when the other commits; a deadlock is a circle of waiting that never ends, so SQL Server kills one transaction. To prevent it, I access tables in the same order, keep transactions short, add indexes, use RCSI, and use UPDLOCK when I read and then update. Deadlocks cannot be fully avoided, so the app retries error 1205.

### Transactions and ACID

**In simple words:** A *transaction* is a unit of work that happens completely or not at all. ACID names its four guarantees: Atomicity (all or nothing), Consistency (rules and constraints always hold), Isolation (others do not see half-done work) and Durability (committed data survives a crash).

**Real-life example:** A bank transfer takes money from one account and adds it to another. Either both happen or neither does, and once confirmed, a power cut cannot undo it.

**Interview question:** What does ACID mean?

**Simple answer:** Atomicity means all statements succeed or all are undone, and Consistency means data moves from one valid state to another. Isolation means running transactions do not see each other's partial changes. Durability means committed data survives a crash, thanks to the transaction log.

```sql
BEGIN TRAN;
    UPDATE dbo.Accounts SET Balance = Balance - 100 WHERE Id = 1;
    UPDATE dbo.Accounts SET Balance = Balance + 100 WHERE Id = 2;
COMMIT;   -- both changes, or none
```

### Isolation levels vs read phenomena

**In simple words:** Isolation levels decide how much one transaction sees of other transactions' changes. A *dirty read* reads uncommitted data, a *non-repeatable read* sees a row change between two reads, and a *phantom read* sees new rows appear. Levels go from READ UNCOMMITTED (allows all three) to SERIALIZABLE (prevents all three, with the most blocking). SNAPSHOT and RCSI use row versions, so readers do not block writers.

**Real-life example:** Reading a shared online document. You can see someone typing live (dirty), only saved versions (committed), or a frozen copy from the moment you opened it (snapshot).

**Interview question:** Which isolation level would you choose for an OLTP database, and why not NOLOCK?

**Simple answer:** I use READ COMMITTED with RCSI turned on: readers see committed data and do not block writers, with no code changes. For critical spots, like reducing stock, I use targeted locks such as `UPDLOCK, HOLDLOCK`, or optimistic concurrency. NOLOCK can return uncommitted, skipped or double-read rows, so it is not a safe speed fix.

```sql
ALTER DATABASE PrepDb SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;
```

### Normal forms with a worked example

**In simple words:** *Normalization* organises tables so each fact is stored only once, which avoids update, insert and delete problems (*anomalies*). 1NF means one value per cell and no repeating groups. 2NF means every column depends on the whole key. 3NF means no column depends on another non-key column.

**Real-life example:** If a customer's city is written on every order, a move means fixing many papers. Keeping the city once, on the customer's card, means just one change.

**Interview question:** Explain 1NF, 2NF and 3NF.

**Simple answer:** 1NF means atomic values: one value per cell and one row per item. 2NF means no column depends on only part of a composite key. 3NF means no column depends on another non-key column — "the key, the whole key, and nothing but the key".

### Denormalization and OLTP vs OLAP

**In simple words:** *Denormalization* means adding repeated data on purpose to make reads faster, like storing an order total on the order row. OLTP systems run the business with many small reads and writes, so they stay normalized. OLAP systems analyse the business with big reports, so they use denormalized star schemas and columnstore indexes.

**Real-life example:** A shop's till records each sale in detail (OLTP). At month end, the manager reads a summary report built from those sales (OLAP).

**Interview question:** When would you denormalize?

**Simple answer:** When a frequent, measured read is too slow and the extra copy is cheap to keep correct, like a stored order total or a dashboard table. I keep the main transactional tables normalized. I treat the copy as derived data with a clear refresh method, such as triggers, events or a nightly job.
