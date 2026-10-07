## SQL Fundamentals

### Practice schema used throughout

**Definition.** One small e-commerce + HR schema that every SQL example in this section (and the coding questions in the next section) reuses. Keep it in your head: when an interviewer says "Employees and Departments" or "Customers and Orders", this is the shape.

**Why it matters.** Interviewers rarely test syntax in isolation. They give you two or three tables and ask a question. Knowing the tables cold lets you spend your time on the *logic*, and lets you verify each result row by hand.

```text
Departments 1 ──< Employees >── 1 Employees      (Employees.ManagerId = self reference)
Customers   1 ──< Orders 1 ──< OrderItems >── 1 Products
                       └──< Payments
```

```sql
CREATE TABLE dbo.Departments (
    DepartmentId   INT          NOT NULL PRIMARY KEY,
    DepartmentName NVARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE dbo.Employees (
    EmployeeId   INT          NOT NULL PRIMARY KEY,
    Name         NVARCHAR(50) NOT NULL,
    Salary       INT          NOT NULL,
    DepartmentId INT          NULL REFERENCES dbo.Departments(DepartmentId),
    ManagerId    INT          NULL REFERENCES dbo.Employees(EmployeeId),
    HireDate     DATE         NOT NULL
);

CREATE TABLE dbo.Customers (
    CustomerId INT           NOT NULL PRIMARY KEY,
    Name       NVARCHAR(50)  NOT NULL,
    Email      NVARCHAR(100) NOT NULL UNIQUE,
    City       NVARCHAR(50)  NULL
);

CREATE TABLE dbo.Products (
    ProductId INT           NOT NULL PRIMARY KEY,
    Name      NVARCHAR(50)  NOT NULL,
    Category  NVARCHAR(30)  NOT NULL,
    Price     DECIMAL(10,2) NOT NULL
);

CREATE TABLE dbo.Orders (
    OrderId    INT IDENTITY(101,1) PRIMARY KEY,
    CustomerId INT          NOT NULL REFERENCES dbo.Customers(CustomerId),
    OrderDate  DATE         NOT NULL,
    Status     NVARCHAR(20) NOT NULL
);

CREATE TABLE dbo.OrderItems (
    OrderItemId INT IDENTITY(1,1) PRIMARY KEY,
    OrderId     INT           NOT NULL REFERENCES dbo.Orders(OrderId),
    ProductId   INT           NOT NULL REFERENCES dbo.Products(ProductId),
    Quantity    INT           NOT NULL,
    UnitPrice   DECIMAL(10,2) NOT NULL
);

CREATE TABLE dbo.Payments (
    PaymentId INT IDENTITY(1,1) PRIMARY KEY,
    OrderId   INT           NOT NULL REFERENCES dbo.Orders(OrderId),
    Amount    DECIMAL(10,2) NOT NULL,
    PaidAt    DATE          NOT NULL,
    Method    NVARCHAR(10)  NOT NULL
);
```

```sql
INSERT dbo.Departments (DepartmentId, DepartmentName) VALUES
 (1, N'Engineering'), (2, N'Sales'), (3, N'HR'), (4, N'Finance');

INSERT dbo.Employees (EmployeeId, Name, Salary, DepartmentId, ManagerId, HireDate) VALUES
 (1,  N'Asha',   150000, 1,    NULL, '2018-01-15'),
 (2,  N'Ravi',   120000, 1,    1,    '2019-03-01'),
 (3,  N'Meena',  120000, 1,    1,    '2020-07-20'),
 (4,  N'Kiran',   90000, 1,    2,    '2021-06-01'),
 (5,  N'Sana',    95000, 2,    1,    '2019-11-11'),
 (6,  N'Tom',    100000, 2,    5,    '2022-02-14'),
 (7,  N'Uma',     70000, 2,    5,    '2023-01-09'),
 (8,  N'Vikram',  60000, NULL, 1,    '2024-05-06'),
 (9,  N'Nina',    65000, 3,    1,    '2022-09-01'),
 (10, N'Omar',    70000, 2,    5,    '2024-09-15');

INSERT dbo.Customers (CustomerId, Name, Email, City) VALUES
 (1, N'Alice', N'alice@example.com', N'Pune'),
 (2, N'Bob',   N'bob@example.com',   N'Mumbai'),
 (3, N'Carol', N'carol@example.com', N'Pune'),
 (4, N'Dave',  N'dave@example.com',  NULL);

INSERT dbo.Products (ProductId, Name, Category, Price) VALUES
 (1, N'Laptop',  N'Electronics', 1000.00),
 (2, N'Mouse',   N'Electronics',   25.00),
 (3, N'Desk',    N'Furniture',    300.00),
 (4, N'Chair',   N'Furniture',    150.00),
 (5, N'Monitor', N'Electronics',  200.00);

INSERT dbo.Orders (CustomerId, OrderDate, Status) VALUES      -- OrderId 101..106
 (1, '2024-01-10', N'Shipped'),
 (1, '2024-02-05', N'Shipped'),
 (2, '2024-02-20', N'Shipped'),
 (3, '2024-03-15', N'Cancelled'),
 (1, '2024-03-25', N'Pending'),
 (2, '2024-04-02', N'Shipped');

INSERT dbo.OrderItems (OrderId, ProductId, Quantity, UnitPrice) VALUES
 (101, 1, 1, 1000.00), (101, 2, 2, 25.00), (102, 3, 1, 300.00), (103, 4, 2, 150.00),
 (103, 2, 1, 25.00),   (104, 1, 1, 1000.00), (105, 2, 4, 25.00), (106, 3, 1, 300.00);

INSERT dbo.Payments (OrderId, Amount, PaidAt, Method) VALUES
 (101, 1050.00, '2024-01-10', N'Card'),
 (102,  300.00, '2024-02-06', N'UPI'),
 (103,  200.00, '2024-02-20', N'Card'),    -- order 103 is paid in two instalments
 (103,  125.00, '2024-02-28', N'UPI'),
 (106,  300.00, '2024-04-03', N'Card');
```

The resulting data, as tables you can check against:

| EmployeeId | Name | Salary | DepartmentId | ManagerId | HireDate |
|---|---|---|---|---|---|
| 1 | Asha | 150000 | 1 | NULL | 2018-01-15 |
| 2 | Ravi | 120000 | 1 | 1 | 2019-03-01 |
| 3 | Meena | 120000 | 1 | 1 | 2020-07-20 |
| 4 | Kiran | 90000 | 1 | 2 | 2021-06-01 |
| 5 | Sana | 95000 | 2 | 1 | 2019-11-11 |
| 6 | Tom | 100000 | 2 | 5 | 2022-02-14 |
| 7 | Uma | 70000 | 2 | 5 | 2023-01-09 |
| 8 | Vikram | 60000 | NULL | 1 | 2024-05-06 |
| 9 | Nina | 65000 | 3 | 1 | 2022-09-01 |
| 10 | Omar | 70000 | 2 | 5 | 2024-09-15 |

| OrderId | CustomerId | OrderDate | Status | | OrderId | Items (Product x Qty) | Order total |
|---|---|---|---|---|---|---|---|
| 101 | 1 Alice | 2024-01-10 | Shipped | | 101 | Laptop x1, Mouse x2 | 1050.00 |
| 102 | 1 Alice | 2024-02-05 | Shipped | | 102 | Desk x1 | 300.00 |
| 103 | 2 Bob | 2024-02-20 | Shipped | | 103 | Chair x2, Mouse x1 | 325.00 |
| 104 | 3 Carol | 2024-03-15 | Cancelled | | 104 | Laptop x1 | 1000.00 |
| 105 | 1 Alice | 2024-03-25 | Pending | | 105 | Mouse x4 | 100.00 |
| 106 | 2 Bob | 2024-04-02 | Shipped | | 106 | Desk x1 | 300.00 |

Deliberate "traps" built into the data: **Finance** has no employees; **Vikram** has no department; **Asha** has no manager; **Dave** has no orders and no city; **Monitor** was never sold; **order 103** has two payments; **orders 104 and 105** have none; **Ravi and Meena** tie on salary; **Uma and Omar** tie on salary. Almost every interview question exercises one of these.

:::tip Tip
In an interview, redraw 4-6 rows of the relevant tables on paper before you write any SQL. Interviewers love a candidate who checks the query against sample rows and then says "and this is what happens to the NULL row".
:::

### Logical query processing order

**Definition.** The order in which SQL Server *conceptually* evaluates the clauses of a `SELECT`. It is not the order you type them. The optimizer may physically execute in a different order, but the result must be as if this order was followed.

**Why it matters.** Almost every "why does this error / why is this wrong" question is answered by it: why an alias is not visible in `WHERE`, why you cannot filter on an aggregate in `WHERE`, why a window function cannot appear in `WHERE`, why `TOP` without `ORDER BY` is arbitrary.

| Step | Clause | What happens | Consequence |
|---|---|---|---|
| 1 | `FROM` / `JOIN` / `APPLY` | Build the working row set. `ON` filters each join as it is formed | `ON` vs `WHERE` differs for outer joins |
| 2 | `WHERE` | Filter individual rows | Cannot reference aggregates or `SELECT` aliases |
| 3 | `GROUP BY` | Collapse rows into groups | After this, only grouped columns and aggregates are usable |
| 4 | `HAVING` | Filter whole groups | Can reference aggregates |
| 5 | `SELECT` | Evaluate expressions, aliases, **window functions** | Aliases first exist here; windows run on the post-`HAVING` rows |
| 6 | `DISTINCT` | Remove duplicate result rows | Runs before `ORDER BY` |
| 7 | `ORDER BY` | Sort the result | The first clause that can use `SELECT` aliases |
| 8 | `TOP` / `OFFSET-FETCH` | Keep the first N rows of the sorted result | Without `ORDER BY` the rows are arbitrary |

```sql
SELECT DISTINCT TOP (2)                       -- steps 5, 6, 8
       d.DepartmentName,
       COUNT(*)      AS Headcount,
       AVG(e.Salary) AS AvgSalary
FROM   dbo.Employees   AS e                   -- step 1
JOIN   dbo.Departments AS d ON d.DepartmentId = e.DepartmentId
WHERE  e.HireDate >= '2019-01-01'             -- step 2
GROUP  BY d.DepartmentName                    -- step 3
HAVING COUNT(*) >= 2                          -- step 4
ORDER  BY AvgSalary DESC;                     -- step 7 (alias is visible here)
-- Output:
-- DepartmentName | Headcount | AvgSalary
-- Engineering    | 3         | 110000      (Ravi 120000, Meena 120000, Kiran 90000)
-- Sales          | 4         | 83750       (Sana, Tom, Uma, Omar; HR dropped by HAVING)
```

```sql
-- Fails: WHERE runs before SELECT, so the alias does not exist yet
SELECT Salary * 12 AS Annual FROM dbo.Employees WHERE Annual > 1000000;
-- Msg 207: Invalid column name 'Annual'.

-- Works: ORDER BY runs after SELECT
SELECT Name, Salary * 12 AS Annual FROM dbo.Employees ORDER BY Annual DESC;
```

:::q In what order does SQL Server logically process a SELECT query?
FROM (including joins), WHERE, GROUP BY, HAVING, SELECT, DISTINCT, ORDER BY, then TOP or OFFSET-FETCH. That is why an alias defined in SELECT is usable in ORDER BY but not in WHERE, why aggregates can only be filtered in HAVING, and why window functions are not allowed in WHERE or GROUP BY. The physical plan can differ, but results must match this logical order.
:::

### SELECT essentials

**Definition.** `SELECT` reads rows. The parts interviewers poke at: column lists vs `*`, aliases, `TOP`, `ORDER BY` determinism, string literals with the `N` prefix.

```sql
SELECT TOP (3) WITH TIES Name, Salary          -- WITH TIES needs ORDER BY
FROM   dbo.Employees
ORDER  BY Salary DESC;
-- Output: Asha 150000 | Ravi 120000 | Meena 120000   (3 rows; ties at the cut-off are kept)

SELECT TOP (3) PERCENT Name FROM dbo.Employees ORDER BY Salary DESC;   -- 10 rows -> 1 row (Asha)
```

- Use `N'text'` for `NVARCHAR` literals. Without it the literal is `VARCHAR` and a non-Latin character becomes `?`. Comparing an `NVARCHAR` column to a `VARCHAR` literal is fine; the reverse (a `VARCHAR` column compared to an `NVARCHAR` value) can cause an implicit conversion that kills index seeks (see SARGability).
- Always qualify columns with an alias in multi-table queries. Name the schema (`dbo.Employees`) to avoid a schema-resolution lookup and cache-plan problems.
- `ORDER BY` is the *only* thing that guarantees order. A query without it may look sorted today (clustered key order) and come back differently tomorrow (parallel plan).
- `SELECT *` is acceptable for ad-hoc exploration, not production code (breaks covering indexes, pulls unneeded columns, breaks when columns are added).

:::warn Gotcha
`SELECT TOP (10) ...` without `ORDER BY` is legal and returns *some* 10 rows. In an interview, always say which ten you mean.
:::

### INSERT, UPDATE, DELETE and OUTPUT

**Definition.** The three DML (data-modification) statements. SQL Server's `OUTPUT` clause lets any of them return the affected rows (`inserted` and `deleted` virtual tables) in the same statement, without a second query.

**Why it matters.** `OUTPUT` is the correct way to get identity values for multi-row inserts, to build an audit trail, and to implement "delete and archive" atomically.

```sql
-- INSERT: multi-row + OUTPUT returns generated keys
INSERT dbo.Customers (CustomerId, Name, Email, City)
OUTPUT inserted.CustomerId, inserted.Name
VALUES (5, N'Eve',   N'eve@example.com',   N'Chennai'),
       (6, N'Frank', N'frank@example.com', NULL);
-- Output: 5 Eve | 6 Frank

-- INSERT ... SELECT copies rows; SELECT ... INTO creates the target table too
INSERT dbo.EmployeeArchive (EmployeeId, Name)
SELECT EmployeeId, Name FROM dbo.Employees WHERE DepartmentId = 3;   -- Nina
```

```sql
-- Getting an identity value
INSERT dbo.Orders (CustomerId, OrderDate, Status) VALUES (4, '2024-05-01', N'Pending');
SELECT SCOPE_IDENTITY();            -- 107: last identity in THIS scope  (use this)
SELECT @@IDENTITY;                  -- last identity in this session, any scope (trigger inserts!)
SELECT IDENT_CURRENT('dbo.Orders'); -- last identity for the table, any session (race-prone)
```

```sql
-- UPDATE with OUTPUT: show old and new values
UPDATE dbo.Employees
SET    Salary = Salary * 1.10
OUTPUT inserted.EmployeeId, deleted.Salary AS OldSalary, inserted.Salary AS NewSalary
WHERE  DepartmentId = 3;
-- Output: 9 | 65000 | 71500

-- UPDATE with JOIN (T-SQL extension): alias goes after UPDATE, join in FROM
UPDATE e
SET    e.Salary = e.Salary + 5000
FROM   dbo.Employees   AS e
JOIN   dbo.Departments AS d ON d.DepartmentId = e.DepartmentId
WHERE  d.DepartmentName = N'Sales';
-- Sana 95000->100000, Tom 100000->105000, Uma 70000->75000, Omar 70000->75000
```

```sql
-- DELETE and archive atomically
DECLARE @gone TABLE (OrderItemId INT, OrderId INT);
DELETE FROM dbo.OrderItems
OUTPUT deleted.OrderItemId, deleted.OrderId INTO @gone
WHERE  OrderId = 104;                        -- cancelled order
-- @gone now holds (6, 104)

-- Large cleanups: delete in batches to keep the log and locks small
WHILE 1 = 1
BEGIN
    DELETE TOP (5000) FROM dbo.AuditLog          -- illustrative table, not in the schema
    WHERE  CreatedAt < DATEADD(YEAR, -2, SYSUTCDATETIME());
    IF @@ROWCOUNT = 0 BREAK;
END
```

:::warn Pitfalls that cause real incidents
- `UPDATE`/`DELETE` **without `WHERE`** hits every row. Habit: write it as a `SELECT` first, then switch the verb; run inside `BEGIN TRAN` and check `@@ROWCOUNT` before `COMMIT`.
- `UPDATE ... FROM ... JOIN` with a one-to-many join is **non-deterministic**: if two source rows match one target row, SQL Server silently picks one. Make sure the join is 1:1 or aggregate first.
- `Salary * 1.10` is `DECIMAL` arithmetic; assigning it back to an `INT` column rounds/truncates silently.
- Identity values are **not rolled back** with a transaction, so gaps are normal. Never rely on gap-free identities.
:::

:::q SCOPE_IDENTITY vs @@IDENTITY vs IDENT_CURRENT?
`SCOPE_IDENTITY()` returns the last identity generated in the current session and current scope, so a trigger that inserts into an audit table cannot corrupt it. `@@IDENTITY` is session-wide and will return the trigger's identity. `IDENT_CURRENT('table')` is table-wide across all sessions, so under concurrency it may be someone else's row. Best of all for multi-row inserts is the `OUTPUT inserted.Id` clause.
:::

### MERGE and its caveats

**Definition.** `MERGE` performs insert/update/delete against a target in one statement, driven by a join to a source. It is the "upsert".

```sql
-- Sync a staging table of price changes into Products
MERGE dbo.Products WITH (HOLDLOCK) AS tgt
USING #Stage AS src ON tgt.ProductId = src.ProductId
WHEN MATCHED AND tgt.Price <> src.Price THEN
     UPDATE SET tgt.Price = src.Price
WHEN NOT MATCHED BY TARGET THEN
     INSERT (ProductId, Name, Category, Price)
     VALUES (src.ProductId, src.Name, src.Category, src.Price)
OUTPUT $action AS Action, inserted.ProductId, inserted.Price, deleted.Price AS OldPrice;
-- #Stage = (2, Mouse, Electronics, 30.00), (6, Keyboard, Electronics, 45.00)
-- Output:
-- Action | ProductId | Price | OldPrice
-- UPDATE | 2         | 30.00 | 25.00
-- INSERT | 6         | 45.00 | NULL
```

**Caveats interviewers expect you to know:**

- **Concurrency.** Without `HOLDLOCK` (serializable semantics on the target) two sessions can both decide "not matched" and both insert, giving a duplicate-key error. `MERGE` is not magically atomic.
- **Bugs and surprises.** `MERGE` has a long history of defects (filtered indexes, triggers, indexed views, `OUTPUT` quirks). Many teams ban it in OLTP code.
- Source must not produce **two rows per target row** (error 8672: "attempted to UPDATE or DELETE the same row more than once").
- Must end with a `;`. `WHEN NOT MATCHED BY SOURCE THEN DELETE` deletes every target row absent from the source, which is catastrophic if the staging load was partial.
- Triggers fire per action; only one `OUTPUT` clause is allowed.

The boring, safe alternative that most senior developers prefer for a single-row upsert:

```sql
BEGIN TRAN;
    UPDATE dbo.Products WITH (UPDLOCK, HOLDLOCK)
    SET    Price = @Price
    WHERE  ProductId = @ProductId;

    IF @@ROWCOUNT = 0
        INSERT dbo.Products (ProductId, Name, Category, Price)
        VALUES (@ProductId, @Name, @Category, @Price);
COMMIT;
```

:::q Would you use MERGE in production?
Carefully. It is fine for batch/ETL loads from a staging table if I add `WITH (HOLDLOCK)` and test it, but for OLTP upserts I prefer `UPDATE` then `INSERT IF @@ROWCOUNT = 0` inside a transaction with `UPDLOCK, HOLDLOCK`, because the behaviour is easier to reason about and avoids the known MERGE bugs.
:::

### TRUNCATE vs DELETE vs DROP

**Definition.** Three ways to get rid of data: `DELETE` removes rows (DML), `TRUNCATE` empties the whole table by deallocating pages (DDL-like), `DROP` removes the table itself.

| | `DELETE` | `TRUNCATE TABLE` | `DROP TABLE` |
|---|---|---|---|
| Removes | Rows matching `WHERE` (or all) | **All** rows | Rows **and** table definition, indexes, constraints |
| `WHERE` clause | Yes | No (partition-level only) | n/a |
| Logging | Every row fully logged | Page deallocations only (minimal) | Metadata |
| Speed on big tables | Slow | Very fast | Very fast |
| Identity | **Not** reset | **Reset** to seed | Gone |
| Triggers | `DELETE` triggers fire | Do **not** fire | Do not fire |
| Table referenced by an FK | Allowed if no child rows | **Not allowed**, even if the child is empty | Not allowed until FK is dropped |
| Rollback inside a transaction | Yes | **Yes** (SQL Server, unlike some engines) | Yes |
| Permission | `DELETE` | `ALTER` on table | `ALTER` on schema / `CONTROL` |

```sql
DELETE dbo.T1;               INSERT dbo.T1 (V) VALUES (9);   -- Id = 4 (identity kept going)
TRUNCATE TABLE dbo.T1;       INSERT dbo.T1 (V) VALUES (9);   -- Id = 1 (reset)

TRUNCATE TABLE dbo.Orders;
-- Msg 4712: Cannot truncate table 'dbo.Orders' because it is being referenced by a
-- FOREIGN KEY constraint.
```

:::tip Say this
"DELETE is logged row by row, fires triggers and can be filtered. TRUNCATE is minimally logged, resets the identity, cannot be used on a table referenced by a foreign key, and can still be rolled back in SQL Server. DROP removes the table itself."
:::

### WHERE vs HAVING

**Definition.** `WHERE` filters **rows** before grouping. `HAVING` filters **groups** after aggregation.

| | `WHERE` | `HAVING` |
|---|---|---|
| Runs | Before `GROUP BY` | After `GROUP BY` |
| Filters | Individual rows | Groups |
| Can use aggregates | No | Yes |
| Can be used without `GROUP BY` | Yes | Yes (whole table = one group) |
| Performance | Reduces rows before grouping (use it for anything that is not an aggregate) | Evaluated on groups only |

```sql
-- "Departments whose average salary is above 80000, counting only people paid >= 65000"
SELECT   d.DepartmentName, COUNT(*) AS Headcount, AVG(e.Salary) AS AvgSalary
FROM     dbo.Employees e JOIN dbo.Departments d ON d.DepartmentId = e.DepartmentId
WHERE    e.Salary >= 65000                 -- row filter: shrinks the input first
GROUP BY d.DepartmentName
HAVING   AVG(e.Salary) > 80000;            -- group filter: needs the aggregate
-- Output: Engineering | 4 | 120000
--         Sales       | 4 | 83750          (HR avg 65000 -> removed)
```

:::warn Common mistake
Putting a non-aggregate condition in `HAVING` (`HAVING DepartmentId = 2`). It works but the optimizer may not push it down in older plans and it reads like you do not understand the difference. Row condition goes in `WHERE`.
:::

### GROUP BY, aggregates and DISTINCT

**Definition.** `GROUP BY` collapses rows with the same grouping values into one row per group so aggregates (`COUNT`, `SUM`, `AVG`, `MIN`, `MAX`) can be computed. `DISTINCT` removes duplicate rows from the *result*.

```sql
SELECT   DepartmentId,
         COUNT(*)         AS Headcount,     -- counts rows
         COUNT(ManagerId) AS WithManager,   -- counts NON-NULL ManagerId only
         SUM(Salary)      AS Payroll
FROM     dbo.Employees
GROUP BY DepartmentId
ORDER BY DepartmentId;
-- Output:
-- DepartmentId | Headcount | WithManager | Payroll
-- NULL         | 1         | 1           | 60000     (Vikram: NULL forms its own group)
-- 1            | 4         | 3           | 480000    (Asha has no manager)
-- 2            | 4         | 4           | 335000
-- 3            | 1         | 1           | 65000
```

Rules to state out loud:

- Every column in `SELECT` must be either in `GROUP BY` or inside an aggregate.
- `NULL`s are grouped together as one group (for `GROUP BY` and `DISTINCT`, NULL = NULL, unlike in `WHERE`).
- Aggregates **ignore NULLs** (except `COUNT(*)`).
- `AVG` of an `INT` column returns an `INT` (truncated): `AVG(Quantity)` over order items is `1`, not `1.625`. Use `AVG(1.0 * Quantity)` or cast.
- `COUNT(DISTINCT City)` counts distinct non-NULL values: Customers has 4 rows, 3 non-NULL cities, 2 distinct (`Pune`, `Mumbai`).

```sql
-- Subtotals and grand total in one pass
SELECT   p.Category, p.Name, SUM(oi.Quantity) AS Units,
         GROUPING(p.Name) AS IsSubtotal           -- 1 on the rolled-up row
FROM     dbo.OrderItems oi JOIN dbo.Products p ON p.ProductId = oi.ProductId
GROUP BY ROLLUP (p.Category, p.Name)
ORDER BY GROUPING(p.Category), p.Category, GROUPING(p.Name), p.Name;
-- Output:
-- Electronics | Laptop | 2  | 0
-- Electronics | Mouse  | 7  | 0
-- Electronics | NULL   | 9  | 1      <- Electronics subtotal
-- Furniture   | Chair  | 2  | 0
-- Furniture   | Desk   | 2  | 0
-- Furniture   | NULL   | 4  | 1
-- NULL        | NULL   | 13 | 1      <- grand total
```

`ROLLUP`, `CUBE` and `GROUPING SETS` are extensions of `GROUP BY` for reporting; `GROUPING()` tells a real NULL from a subtotal NULL.

:::q Difference between COUNT(*), COUNT(column) and COUNT(DISTINCT column)?
`COUNT(*)` counts rows, including those with NULLs. `COUNT(col)` counts rows where `col` is not NULL. `COUNT(DISTINCT col)` counts unique non-NULL values. On Customers, `COUNT(*)` is 4, `COUNT(City)` is 3 and `COUNT(DISTINCT City)` is 2.
:::

:::q Can you use DISTINCT instead of GROUP BY?
For simply removing duplicates, they produce the same plan. But `GROUP BY` is needed when you aggregate. Using `DISTINCT` to "fix" a join that returns duplicate rows is a smell: the join is multiplying rows (one-to-many) and the right fix is to aggregate first, use `EXISTS`, or correct the join condition.
:::

### CASE expressions

**Definition.** `CASE` is SQL's if/else *expression* (not statement). It returns one value and is allowed anywhere an expression is: `SELECT`, `WHERE`, `ORDER BY`, `GROUP BY`, inside aggregates.

```sql
-- Searched CASE: conditions evaluated top to bottom, first match wins
SELECT Name, Salary,
       CASE WHEN Salary >= 120000 THEN 'Senior'
            WHEN Salary >= 80000  THEN 'Mid'
            ELSE                       'Junior' END AS Band
FROM   dbo.Employees
ORDER  BY Salary DESC, Name;
-- Asha Senior | Meena Senior | Ravi Senior | Tom Mid | Sana Mid | Kiran Mid
-- Omar Junior | Uma Junior | Nina Junior | Vikram Junior

-- Simple CASE: equality only (cannot test NULL)
SELECT OrderId, CASE Status WHEN N'Shipped' THEN 1 ELSE 0 END AS IsShipped FROM dbo.Orders;

-- Conditional aggregation: a poor man's pivot, one pass over the table
SELECT SUM(CASE WHEN Status = N'Shipped'   THEN 1 ELSE 0 END) AS Shipped,
       SUM(CASE WHEN Status = N'Pending'   THEN 1 ELSE 0 END) AS Pending,
       SUM(CASE WHEN Status = N'Cancelled' THEN 1 ELSE 0 END) AS Cancelled
FROM   dbo.Orders;
-- Output: 4 | 1 | 1
```

- Without `ELSE`, unmatched rows give `NULL`. The return type is the highest-precedence type among the branches, so mixing `INT` and `VARCHAR` branches tries to convert the text to `INT` and fails.
- `CASE` in `ORDER BY` gives custom sort order: `ORDER BY CASE Status WHEN N'Pending' THEN 0 ELSE 1 END, OrderDate`.
- `IIF(cond, a, b)` and `CHOOSE` are shorthand for `CASE`.

### NULL semantics

**Definition.** `NULL` means *unknown or missing*, not zero and not empty string. SQL uses **three-valued logic**: every predicate is `TRUE`, `FALSE` or `UNKNOWN`. `WHERE` keeps only `TRUE` rows, so `UNKNOWN` rows vanish silently.

| a | b | a AND b | a OR b | NOT a |
|---|---|---|---|---|
| TRUE | UNKNOWN | UNKNOWN | TRUE | FALSE |
| FALSE | UNKNOWN | FALSE | UNKNOWN | TRUE |
| UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

Any comparison with `NULL` (`=`, `<>`, `<`, `>`, even `NULL = NULL`) is `UNKNOWN`. Use `IS NULL` / `IS NOT NULL`.

```sql
SELECT Name, City FROM dbo.Customers WHERE City <> N'Pune';             -- Bob only! Dave (NULL) vanishes
SELECT Name, City FROM dbo.Customers WHERE City <> N'Pune' OR City IS NULL;   -- Bob, Dave
SELECT Name, City FROM dbo.Customers WHERE City = NULL;                 -- 0 rows, always
SELECT Name, City FROM dbo.Customers WHERE City IS NOT DISTINCT FROM NULL;    -- SQL Server 2022+: NULL-safe equality
```

#### COALESCE vs ISNULL

| | `COALESCE(a, b, c...)` | `ISNULL(a, b)` |
|---|---|---|
| Standard | ANSI SQL | T-SQL only |
| Arguments | 2 or more | Exactly 2 |
| Result type | Highest-precedence type of all arguments | Type of the **first** argument |
| Nullability of result | Nullable if all args nullable | Non-nullable if second arg is non-null |
| Evaluation | Subqueries may be evaluated more than once | Evaluated once |

```sql
DECLARE @x VARCHAR(3) = NULL;
SELECT ISNULL(@x, 'abcdef')  AS IsNullRes,     -- 'abc'    truncated to VARCHAR(3)!
       COALESCE(@x, 'abcdef') AS CoalesceRes;  -- 'abcdef'

SELECT 10 / NULLIF(0, 0);                      -- NULL instead of divide-by-zero error
```

Other NULL facts: aggregates skip NULLs; `NULL + 1` and `'a' + NULL` are `NULL` (with `CONCAT_NULL_YIELDS_NULL` ON, the default; `CONCAT()` treats NULL as empty); `ORDER BY` sorts NULLs **first** in `ASC` in SQL Server; a `UNIQUE` constraint allows only **one** NULL (SQL Server treats NULLs as equal there, unlike the standard; a filtered unique index `WHERE col IS NOT NULL` allows many).

#### The NOT IN with NULL trap

```sql
-- "Departments with no employees"  -> expected: Finance
SELECT DepartmentId, DepartmentName
FROM   dbo.Departments
WHERE  DepartmentId NOT IN (SELECT DepartmentId FROM dbo.Employees);
-- Output: 0 rows!  Employees.DepartmentId contains NULL (Vikram).
-- x NOT IN (1,2,3,NULL)  =  x<>1 AND x<>2 AND x<>3 AND x<>NULL  =  ... AND UNKNOWN  ->  never TRUE

-- Fix 1: NOT EXISTS (NULL-safe, usually the best plan)
SELECT d.DepartmentId, d.DepartmentName
FROM   dbo.Departments d
WHERE  NOT EXISTS (SELECT 1 FROM dbo.Employees e WHERE e.DepartmentId = d.DepartmentId);
-- Output: 4 | Finance

-- Fix 2: filter NULLs out of the subquery
... WHERE DepartmentId NOT IN (SELECT DepartmentId FROM dbo.Employees
                               WHERE  DepartmentId IS NOT NULL);
```

:::scenario Report shows 0 rows after a new row was added
A "customers who never ordered" report using `NOT IN (SELECT CustomerId FROM Orders)` has worked for years. After a data import, one order row gets a NULL `CustomerId` and the report suddenly returns nothing. Reason: `NOT IN` against a set containing NULL is never TRUE. Fix with `NOT EXISTS` (or `LEFT JOIN ... IS NULL`), and make `Orders.CustomerId` `NOT NULL` so the bad row cannot exist.
:::

:::q What is the difference between NULL, 0 and an empty string?
NULL means unknown/missing; 0 is a known number; `''` is a known empty string. `NULL = NULL` is UNKNOWN, `0 = 0` is TRUE. Aggregates ignore NULL but include 0. In Oracle `''` is NULL; in SQL Server it is not.
:::

:::q What does three-valued logic mean and why does `WHERE col <> 'x'` miss NULL rows?
Predicates evaluate to TRUE, FALSE or UNKNOWN. A `WHERE` clause only keeps TRUE rows. When `col` is NULL, `col <> 'x'` is UNKNOWN, so the row is filtered out. To include NULLs add `OR col IS NULL`, or use `IS DISTINCT FROM` on SQL Server 2022 and later.
:::
