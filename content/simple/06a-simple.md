### Practice schema used throughout

**In simple words:** All SQL examples in this section use one small practice database. It has an HR part (Departments, and Employees with a ManagerId) and a shop part (Customers, Orders, OrderItems, Products, Payments). The data has planned "traps", like an employee with no department and a customer with no orders. Most interview questions test one of these traps.

**Real-life example:** A driving school uses the same practice route in every lesson. Once you know the route, you can focus on driving well, not on finding the way.

**Interview question:** How do you approach a SQL question when the interviewer gives you two or three tables?

**Simple answer:** First I write down a few sample rows from each table, including tricky ones like NULLs and rows with no match. Then I write the query and check it against those rows by hand. I also say out loud what happens to the NULL or unmatched rows.

### Logical query processing order

**In simple words:** SQL Server does not process a SELECT in the order you type it. Logically it goes: FROM/JOIN, WHERE, GROUP BY, HAVING, SELECT, DISTINCT, ORDER BY, then TOP. This explains many errors. For example, an alias made in SELECT does not exist yet in WHERE.

**Real-life example:** In a kitchen, you first collect ingredients (FROM), throw away bad ones (WHERE), sort them into bowls (GROUP BY), drop bowls that are too small (HAVING), cook (SELECT), and finally arrange the plates (ORDER BY).

**Interview question:** In what order does SQL Server logically process a SELECT query?

**Simple answer:** FROM with joins, WHERE, GROUP BY, HAVING, SELECT, DISTINCT, ORDER BY, and then TOP or OFFSET-FETCH. That is why a SELECT alias works in ORDER BY but not in WHERE, and why aggregates are filtered in HAVING. The real plan may run steps differently, but the result must be the same.

```sql
-- Fails: WHERE runs before SELECT, so Annual does not exist yet
SELECT Salary * 12 AS Annual FROM dbo.Employees WHERE Annual > 1000000;
-- Works: ORDER BY runs after SELECT
SELECT Name, Salary * 12 AS Annual FROM dbo.Employees ORDER BY Annual DESC;
```

### SELECT essentials

**In simple words:** `SELECT` reads rows from tables. Only `ORDER BY` guarantees the order of the results; without it, the order can change at any time. `TOP (n)` without `ORDER BY` returns any n rows, and you cannot know which. Use `N'text'` for Unicode (`NVARCHAR`) text, and list the columns you need instead of `SELECT *`.

**Real-life example:** If you ask a librarian for "any 10 books", you get some 10 books. If you ask for "the 10 newest books", you get a clear answer. `ORDER BY` is the "newest" part.

**Interview question:** Why should you avoid SELECT * and TOP without ORDER BY?

**Simple answer:** `SELECT *` pulls columns you do not need, stops covering indexes from working, and can break code when columns are added. `TOP` without `ORDER BY` returns any rows, and the result can change between runs. So I list the columns and always add `ORDER BY` with `TOP`.

```sql
SELECT TOP (3) WITH TIES Name, Salary
FROM   dbo.Employees
ORDER  BY Salary DESC;   -- ties at the cut-off are kept
```

### INSERT, UPDATE, DELETE and OUTPUT

**In simple words:** INSERT adds rows, UPDATE changes rows, and DELETE removes rows. The `OUTPUT` clause returns the affected rows in the same statement. It can show the new values (`inserted`) and the old values (`deleted`). To get a new identity value, use `SCOPE_IDENTITY()` or `OUTPUT`.

**Real-life example:** When a bank changes your address, it gives you a slip showing the old and the new address. You do not need to call the bank again to check.

**Interview question:** What is the difference between SCOPE_IDENTITY, @@IDENTITY and IDENT_CURRENT?

**Simple answer:** `SCOPE_IDENTITY()` gives the last identity created in my session and my scope, so a trigger cannot change it. `@@IDENTITY` covers the whole session, so it can return an identity created by a trigger. `IDENT_CURRENT('table')` works across all sessions, so it may be someone else's row; for multi-row inserts, `OUTPUT inserted.Id` is best.

```sql
UPDATE dbo.Employees
SET    Salary = Salary * 1.10
OUTPUT inserted.EmployeeId, deleted.Salary AS OldSalary, inserted.Salary AS NewSalary
WHERE  DepartmentId = 3;
```

### MERGE and its caveats

**In simple words:** `MERGE` can insert, update and delete in one statement. It compares a target table with a source and acts on matched and unmatched rows. People often call it an *upsert* (update or insert). But it is not safe from race conditions by itself, and it has a history of bugs.

**Real-life example:** A shop updates its price list from a supplier sheet. Items on both lists get new prices, and new items are added. If two clerks do this at the same time without coordinating, the same item can be added twice.

**Interview question:** Would you use MERGE in production?

**Simple answer:** Carefully. For batch loads from a staging table, it is fine with `WITH (HOLDLOCK)` and good tests. For single-row upserts in OLTP code, I prefer `UPDATE`, then `INSERT` if `@@ROWCOUNT = 0`, inside a transaction with `UPDLOCK, HOLDLOCK`.

```sql
BEGIN TRAN;
UPDATE dbo.Products WITH (UPDLOCK, HOLDLOCK)
SET    Price = @Price WHERE ProductId = @Id;
IF @@ROWCOUNT = 0
    INSERT dbo.Products (ProductId, Name, Category, Price)
    VALUES (@Id, @Name, @Category, @Price);
COMMIT;
```

### TRUNCATE vs DELETE vs DROP

**In simple words:** `DELETE` removes rows one by one, and it can use a `WHERE`. `TRUNCATE` removes all rows very fast by freeing whole data pages. `DROP` removes the table itself, with its structure and indexes.

**Real-life example:** DELETE is taking chosen books off a shelf one by one. TRUNCATE is emptying the whole shelf at once. DROP is removing the shelf from the room.

**Interview question:** What is the difference between DELETE and TRUNCATE?

**Simple answer:** DELETE logs every row, can filter with WHERE, fires triggers and keeps the identity counter. TRUNCATE removes all rows with minimal logging, resets the identity, does not fire triggers, and is not allowed if a foreign key references the table. In SQL Server, both can be rolled back inside a transaction.

### WHERE vs HAVING

**In simple words:** `WHERE` filters single rows before grouping. `HAVING` filters whole groups after grouping. Only `HAVING` can use aggregates like `COUNT` or `AVG`. Put normal row conditions in `WHERE`, so fewer rows need to be grouped.

**Real-life example:** On a school sports day, WHERE removes students who are absent. HAVING then removes teams that have fewer than five players.

**Interview question:** What is the difference between WHERE and HAVING?

**Simple answer:** WHERE runs before GROUP BY and filters rows, so it cannot use aggregates. HAVING runs after GROUP BY and filters groups, so it can use aggregates. I put every non-aggregate condition in WHERE.

```sql
SELECT   DepartmentId, AVG(Salary) AS AvgSalary
FROM     dbo.Employees
WHERE    Salary >= 65000          -- row filter
GROUP BY DepartmentId
HAVING   AVG(Salary) > 80000;     -- group filter
```

### GROUP BY, aggregates and DISTINCT

**In simple words:** `GROUP BY` puts rows with the same values into one group, so you can use aggregates like `COUNT`, `SUM` and `AVG`. Each SELECT column must be in the GROUP BY or inside an aggregate. Aggregates skip NULLs, except `COUNT(*)`. `DISTINCT` just removes duplicate rows from the result.

**Real-life example:** A teacher sorts exam papers into piles by class. Then she counts the papers and finds the average mark for each pile.

**Interview question:** What is the difference between COUNT(*), COUNT(column) and COUNT(DISTINCT column)?

**Simple answer:** `COUNT(*)` counts all rows, even rows with NULLs. `COUNT(col)` counts rows where that column is not NULL, and `COUNT(DISTINCT col)` counts unique non-NULL values. Also, `AVG` of an INT column returns an INT, so I write `AVG(1.0 * col)` to keep decimals.

```sql
SELECT COUNT(*)             AS AllRows,   -- 4
       COUNT(City)          AS WithCity,  -- 3
       COUNT(DISTINCT City) AS Cities     -- 2
FROM   dbo.Customers;
```

### CASE expressions

**In simple words:** `CASE` is SQL's if/else. It returns one value, so you can use it in SELECT, WHERE, ORDER BY and inside aggregates. Conditions are checked from top to bottom, and the first match wins. Without `ELSE`, rows that match nothing get NULL.

**Real-life example:** A cinema sets ticket prices by age. Under 12 pays the child price, over 60 pays the senior price, and everyone else pays the normal price.

**Interview question:** How can you count rows per status in one query, as separate columns?

**Simple answer:** I use conditional aggregation: one `SUM(CASE WHEN Status = 'Shipped' THEN 1 ELSE 0 END)` per status. It reads the table only once and gives one column per status. It is a simple way to pivot data.

```sql
SELECT SUM(CASE WHEN Status = N'Shipped' THEN 1 ELSE 0 END) AS Shipped,
       SUM(CASE WHEN Status = N'Pending' THEN 1 ELSE 0 END) AS Pending
FROM   dbo.Orders;
```

### NULL semantics

**In simple words:** `NULL` means unknown or missing — not zero and not an empty string. Any comparison with NULL, even `NULL = NULL`, gives UNKNOWN, and `WHERE` keeps only TRUE rows. So use `IS NULL` and `IS NOT NULL`. Be careful: `NOT IN` returns no rows if its list contains a NULL.

**Real-life example:** A form field left blank is not "zero". If a person's age is unknown, you cannot say they are older or younger than you.

**Interview question:** Why does NOT IN sometimes return no rows?

**Simple answer:** SQL uses three-valued logic: TRUE, FALSE or UNKNOWN. If the subquery returns a NULL, `x NOT IN (..., NULL)` is never TRUE, so every row is filtered out. I use `NOT EXISTS` instead, or remove NULLs inside the subquery.

```sql
SELECT d.DepartmentName
FROM   dbo.Departments d
WHERE  NOT EXISTS (SELECT 1 FROM dbo.Employees e
                   WHERE e.DepartmentId = d.DepartmentId);  -- NULL-safe
```

### Join types at a glance

**In simple words:** A join combines rows from two tables using a condition. INNER JOIN keeps only matching rows. LEFT JOIN keeps all left rows and puts NULLs where nothing matches; RIGHT JOIN does the same for the right side. FULL JOIN keeps unmatched rows from both sides, and CROSS JOIN pairs every row with every row.

**Real-life example:** Matching students to lockers. INNER gives only students who have a locker. LEFT gives all students, some with "no locker". FULL gives all students and all lockers, even empty ones.

**Interview question:** What is the difference between INNER JOIN and LEFT JOIN?

**Simple answer:** INNER JOIN returns only rows that match on both sides. LEFT JOIN returns every left row, with NULLs in the right columns when there is no match. I use LEFT JOIN when the right side is optional, or to find missing matches, like customers with no orders.

```sql
SELECT e.Name, d.DepartmentName
FROM   dbo.Employees e
LEFT JOIN dbo.Departments d ON d.DepartmentId = e.DepartmentId;
-- Vikram (no department) is kept, with NULL
```

### Anti-join and semi-join

**In simple words:** A *semi-join* returns rows that have at least one match, without repeating them. An *anti-join* returns rows that have no match. SQL has no keyword for them. You write them with `EXISTS` / `NOT EXISTS`, `IN`, or `LEFT JOIN ... WHERE right.Id IS NULL`.

**Real-life example:** From a class list, a semi-join finds the students who handed in homework. An anti-join finds the students who did not.

**Interview question:** How do you find records in table A that have no match in table B?

**Simple answer:** I use `NOT EXISTS` with a correlated subquery, or `LEFT JOIN B ... WHERE B.Id IS NULL`. I avoid `NOT IN`, because one NULL in the subquery makes it return nothing. The optimizer usually builds the same plan for both safe ways.

```sql
SELECT c.Name
FROM   dbo.Customers c
WHERE  NOT EXISTS (SELECT 1 FROM dbo.Orders o
                   WHERE o.CustomerId = c.CustomerId);  -- Dave
```

### ON vs WHERE in outer joins

**In simple words:** For an INNER JOIN, a condition in `ON` or in `WHERE` gives the same result, but not for a LEFT JOIN. In a LEFT JOIN, `ON` decides which rows match, and unmatched left rows are still kept. `WHERE` runs later and can remove those kept rows. That silently turns your LEFT JOIN into an INNER JOIN.

**Real-life example:** You want every guest listed, with only their vegetarian orders. If you filter "vegetarian" after the list is made, guests with no order disappear. Filtering while matching keeps every guest.

**Interview question:** In a LEFT JOIN, where should a filter on the right table go?

**Simple answer:** In the `ON` clause. If I put it in WHERE, the NULL rows for unmatched left rows fail the test and are removed. My rule: filter the left (kept) table in WHERE, and the right (optional) table in ON.

```sql
SELECT c.Name, o.OrderId
FROM   dbo.Customers c
LEFT JOIN dbo.Orders o
       ON o.CustomerId = c.CustomerId AND o.Status = N'Shipped';
-- all customers are kept
```

### Join fan-out (duplicate rows)

**In simple words:** If you join a parent table to two child tables, the rows multiply. An order with 2 items and 2 payments becomes 4 rows. Then `SUM` counts each value twice, and the totals are wrong. The fix is to sum up each child table to one row per parent first, then join.

**Real-life example:** If you list every dish with every drink from a dinner, each dish repeats once per drink. Adding up dish prices from that list gives a wrong bill.

**Interview question:** Why are my SUM totals too big after joining two tables?

**Simple answer:** Because of fan-out: joining two one-to-many children repeats each row once per match on the other side. I aggregate each child in a subquery or CTE first, so each gives one row per parent, and then join. `DISTINCT` is not the right fix.

```sql
SELECT o.OrderId, i.ItemsTotal, p.Paid
FROM   dbo.Orders o
JOIN  (SELECT OrderId, SUM(Quantity * UnitPrice) AS ItemsTotal
       FROM dbo.OrderItems GROUP BY OrderId) i ON i.OrderId = o.OrderId
LEFT JOIN (SELECT OrderId, SUM(Amount) AS Paid
           FROM dbo.Payments GROUP BY OrderId) p ON p.OrderId = o.OrderId;
```

### Join algorithms

**In simple words:** SQL Server can run a join in three physical ways. *Nested Loops* takes each row from one side and looks up its matches on the other; it is good when one side is small and the other is indexed. *Hash Match* builds a hash table (a fast in-memory lookup) from the smaller input; it suits large, unsorted data. *Merge Join* walks two inputs that are already sorted on the join key.

**Real-life example:** Nested loops: for each guest, you look up their name in an alphabetical guest book. Hash match: you first drop all names into labelled boxes, then check each person against the boxes. Merge join: you compare two sorted lists side by side, top to bottom.

**Interview question:** What join algorithms does SQL Server use, and when?

**Simple answer:** Nested Loops for a small outer input and an index on the inner side, typical for OLTP lookups. Hash Match for big, unsorted inputs, but it needs memory and can spill to tempdb. Merge Join when both inputs are already sorted on the key; I rarely force one with hints and fix indexes and statistics instead.

### Subqueries

**In simple words:** A subquery is a SELECT inside another statement. A *scalar* subquery returns one value. A *correlated* subquery uses columns from the outer query, so logically it runs once per outer row. For "does a matching row exist?" checks, `EXISTS` is clear and NULL-safe.

**Real-life example:** "Show employees who earn more than the company average" first asks a small question (what is the average?) and then uses that answer.

**Interview question:** What is a correlated subquery, and what is the difference between EXISTS and IN?

**Simple answer:** A correlated subquery refers to the outer row, like "salary above their own department's average". `IN` checks if a value is in a list, while `EXISTS` checks if at least one matching row exists. They usually get the same plan, but `NOT EXISTS` is safe with NULLs and `NOT IN` is not.

```sql
SELECT e.Name, e.Salary
FROM   dbo.Employees e
WHERE  e.Salary > (SELECT AVG(x.Salary) FROM dbo.Employees x
                   WHERE  x.DepartmentId = e.DepartmentId);
```

### CTE (Common Table Expression)

**In simple words:** A CTE is a named, temporary query written with `WITH name AS (...)`. It exists only for the next statement. It makes long queries easier to read, step by step. It is not stored or cached, and a *recursive* CTE can walk a tree, like an org chart.

**Real-life example:** It is like writing helper notes beside a maths problem. The notes make the steps clear, but you throw them away after that one problem.

**Interview question:** Is a CTE faster than a subquery, and how do you write a recursive CTE?

**Simple answer:** No, a CTE is just syntax and is expanded like a view; if I use it twice, it may run twice. A recursive CTE has an anchor query, `UNION ALL`, and a part that joins back to the CTE. The default limit is 100 levels, which I can change with `OPTION (MAXRECURSION n)`.

```sql
WITH Org AS (
    SELECT EmployeeId, Name, 0 AS Lvl FROM dbo.Employees WHERE ManagerId IS NULL
    UNION ALL
    SELECT e.EmployeeId, e.Name, o.Lvl + 1
    FROM dbo.Employees e JOIN Org o ON e.ManagerId = o.EmployeeId
)
SELECT * FROM Org;
```

### UNION, UNION ALL, EXCEPT, INTERSECT

**In simple words:** These combine the results of two SELECTs that have the same number of columns. `UNION ALL` just adds the rows together. `UNION` adds them and removes duplicates. `INTERSECT` keeps rows found in both, and `EXCEPT` keeps rows in the first but not in the second.

**Real-life example:** Two class lists for a school trip. UNION ALL staples them together. UNION removes names that appear twice. INTERSECT finds students on both lists, and EXCEPT finds students only on the first list.

**Interview question:** What is the difference between UNION and UNION ALL?

**Simple answer:** UNION ALL keeps all rows, including duplicates, so it is cheap. UNION removes duplicates, which needs an extra sort or hash step. If duplicates cannot happen or are fine, I use UNION ALL.

```sql
SELECT CustomerId FROM dbo.Customers
EXCEPT
SELECT CustomerId FROM dbo.Orders;   -- customers with no orders
```

### APPLY: CROSS APPLY and OUTER APPLY

**In simple words:** `APPLY` runs a small query or table function once for each row of the left table. The right side can use columns from the current left row, which a normal join cannot do. `CROSS APPLY` works like INNER JOIN. `OUTER APPLY` works like LEFT JOIN and keeps left rows with no result.

**Real-life example:** For each customer at the counter, the cashier pulls out that customer's latest receipt. The search depends on who is standing there.

**Interview question:** When would you use CROSS APPLY instead of a JOIN?

**Simple answer:** When the right side depends on the left row. Examples are top N per group (`TOP (n) ... ORDER BY` inside the apply) and calling a table-valued function with a column as input. I use OUTER APPLY when I must keep left rows that have no match.

```sql
SELECT c.Name, o.OrderId, o.OrderDate
FROM   dbo.Customers c
OUTER APPLY (SELECT TOP (1) OrderId, OrderDate
             FROM   dbo.Orders o
             WHERE  o.CustomerId = c.CustomerId
             ORDER  BY o.OrderDate DESC) o;   -- latest order per customer
```

### Tables and constraints

**In simple words:** A table stores rows of typed columns. *Constraints* are rules the database enforces, so bad data cannot get in from any app or script. The main ones are NOT NULL, PRIMARY KEY, UNIQUE, FOREIGN KEY, CHECK and DEFAULT. Choose good data types too: `DECIMAL` for money, never `FLOAT`.

**Real-life example:** A bank form has rules: the account number must be filled in and unique, and the amount must be positive. The bank checks these rules no matter who fills in the form.

**Interview question:** What constraints does SQL Server support, and why use them instead of checks in the app?

**Simple answer:** NOT NULL, PRIMARY KEY, UNIQUE, FOREIGN KEY, CHECK and DEFAULT. The database enforces them for every writer, not just one app, so data stays correct even with scripts or other services. I also give constraints names, so error messages and migrations are easy to read.

```sql
CREATE TABLE dbo.Reviews (
    ReviewId  INT IDENTITY PRIMARY KEY,
    ProductId INT NOT NULL REFERENCES dbo.Products(ProductId),
    Rating    TINYINT NOT NULL CHECK (Rating BETWEEN 1 AND 5),
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
```

### Views

**In simple words:** A view is a saved SELECT that you can query like a table. A normal view stores no data; its query runs each time you use it. Views hide complex joins and can limit which columns or rows users see. An *indexed view* stores its results and keeps them up to date.

**Real-life example:** A view is like a saved filter in your email app. It does not copy your emails; it just shows them in a handy way each time you open it.

**Interview question:** What is the difference between a view and an indexed view?

**Simple answer:** A normal view stores only the query and re-runs it against the tables every time. An indexed view has a unique clustered index, so its results are stored and updated automatically when the tables change. It speeds up reads, like report totals, but slows writes and needs `SCHEMABINDING`.

```sql
CREATE VIEW dbo.vw_ShippedOrders AS
SELECT o.OrderId, c.Name AS Customer, o.OrderDate
FROM   dbo.Orders o JOIN dbo.Customers c ON c.CustomerId = o.CustomerId
WHERE  o.Status = N'Shipped';
```

### Stored procedures vs functions

**In simple words:** A stored procedure is a saved block of T-SQL that can do almost anything: change data, use transactions and handle errors. A function returns a value or a table and must not change data. You can use a function inside a query, but you call a procedure with `EXEC`. Scalar and multi-statement functions can be slow on many rows.

**Real-life example:** A procedure is a chef who can cook, clean and order stock. A function is a kitchen scale: you give it something and it gives you back a number, without changing anything.

**Interview question:** Stored procedure vs function — when do you use which?

**Simple answer:** I use a procedure for actions: changing data, transactions, error handling and dynamic SQL. I use a function when I need a value or a table inside a query. For table results I prefer an inline table-valued function, because the optimizer expands it like a view.

```sql
CREATE FUNCTION dbo.fn_EmployeesByDept (@DeptId INT)
RETURNS TABLE AS
RETURN (SELECT EmployeeId, Name, Salary
        FROM dbo.Employees WHERE DepartmentId = @DeptId);
```

### Triggers

**In simple words:** A *trigger* is code that runs automatically when rows are inserted, updated or deleted. Inside it, the `inserted` table holds the new rows and `deleted` holds the old rows. An `AFTER` trigger runs after the change, and an `INSTEAD OF` trigger runs in place of it. A trigger fires once per statement, not once per row.

**Real-life example:** A shop door rings a bell every time someone opens it. Nobody presses the bell; it happens by itself.

**Interview question:** What are the risks of using triggers?

**Simple answer:** A trigger fires once per statement, so code that reads one row from `inserted` breaks on multi-row updates; I always write set-based code. Triggers are hidden logic and run inside the caller's transaction, so a slow trigger slows every write. An unhandled error in a trigger rolls back the whole transaction, so I keep triggers small or use other options.

```sql
CREATE TRIGGER dbo.trg_SalaryAudit ON dbo.Employees AFTER UPDATE AS
INSERT dbo.SalaryAudit (EmployeeId, OldSalary, NewSalary)
SELECT i.EmployeeId, d.Salary, i.Salary
FROM   inserted i JOIN deleted d ON d.EmployeeId = i.EmployeeId
WHERE  i.Salary <> d.Salary;
```

### Temp tables, table variables and CTEs

**In simple words:** All three hold a middle result. A `#temp` table lives in tempdb for your session; it has statistics and can have any index. A `@table` variable lives only in its batch or procedure, has no column statistics, and is not undone by ROLLBACK. A CTE stores nothing; it is just a named query for one statement.

**Real-life example:** A CTE is a note on your hand for one task. A table variable is a sticky note for a short list. A temp table is a proper notebook for big lists you will use many times.

**Interview question:** What is the difference between a temp table and a table variable?

**Simple answer:** Both live in tempdb. A temp table has statistics, supports any index and is undone by ROLLBACK, so it suits large or reused data. A table variable has no column statistics, so estimates are poor for big sets, and ROLLBACK does not undo it; I use it for small sets.

```sql
CREATE TABLE #tt (a INT); DECLARE @tv TABLE (a INT);
BEGIN TRAN; INSERT #tt VALUES (1); INSERT @tv VALUES (1); ROLLBACK;
SELECT (SELECT COUNT(*) FROM #tt) AS TempRows,  -- 0
       (SELECT COUNT(*) FROM @tv) AS VarRows;   -- 1
```

### Table-valued parameters (TVP)

**In simple words:** A TVP lets you send many rows to a stored procedure as one parameter. First you create a table type with `CREATE TYPE ... AS TABLE`. Inside the procedure, the parameter is read-only (`READONLY`). It replaces comma-separated strings or one database call per row.

**Real-life example:** Instead of mailing ten letters in ten envelopes, you put all ten in one big envelope with a clear list inside.

**Interview question:** How do you pass a list of rows from .NET to a stored procedure?

**Simple answer:** I create a table type and give the procedure a `READONLY` parameter of that type. In ADO.NET I pass a `DataTable` with `SqlDbType.Structured` and set `TypeName`; in Dapper I use `AsTableValuedParameter`. For very large loads, tens of thousands of rows or more, `SqlBulkCopy` is better.

```sql
CREATE TYPE dbo.OrderItemList AS TABLE (
    ProductId INT NOT NULL PRIMARY KEY,
    Quantity  INT NOT NULL
);
-- in the procedure: @Items dbo.OrderItemList READONLY
```

### Primary, foreign, composite, unique and candidate keys

**In simple words:** A *candidate key* is any smallest set of columns that uniquely identifies a row. The *primary key* is the one you choose: unique, not NULL, and only one per table. Other candidate keys get UNIQUE constraints. A *composite key* has more than one column, and a *foreign key* points to a key in another table, so there are no orphan rows.

**Real-life example:** A student can be found by student number or by email. The school picks the student number as the main ID (primary key), and the email must still be unique (unique key). The library card stores the student number (foreign key).

**Interview question:** What is the difference between a primary key and a unique key?

**Simple answer:** A table has one primary key but can have many unique keys. A primary key cannot be NULL, while a unique key allows one NULL in SQL Server. By default, the primary key creates a clustered index and a unique key creates a non-clustered one; a foreign key can point to either.

```sql
CREATE TABLE dbo.ProductTags (
    ProductId INT NOT NULL REFERENCES dbo.Products(ProductId),
    Tag       NVARCHAR(30) NOT NULL,
    CONSTRAINT PK_ProductTags PRIMARY KEY (ProductId, Tag)  -- composite
);
```
