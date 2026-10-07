## Joins (must know extremely well)

### Join types at a glance

**Definition.** A join combines rows from two row sets based on a condition (`ON`). The join type decides what happens to rows that find **no** match.

**Why it matters.** Joins are the single most-asked SQL topic. You must be able to (1) predict the exact rows, (2) choose the right type, and (3) spot the traps: `NULL` keys, one-to-many fan-out, and `ON` vs `WHERE` for outer joins.

Mini tables (a slice of the practice schema, so every result below can be checked by eye):

```sql
CREATE TABLE #E (Name NVARCHAR(20), DeptId INT);
INSERT #E VALUES (N'Asha', 1), (N'Ravi', 1), (N'Sana', 2), (N'Vikram', NULL);

CREATE TABLE #D (DeptId INT, DeptName NVARCHAR(20));
INSERT #D VALUES (1, N'Engineering'), (2, N'Sales'), (4, N'Finance');
```

```text
 #E (left)                 ON e.DeptId = d.DeptId               #D (right)
 Asha    DeptId = 1   ------------------------------------>   1  Engineering
 Ravi    DeptId = 1   ------------------------------------>   1  Engineering
 Sana    DeptId = 2   ------------------------------------>   2  Sales
 Vikram  DeptId = NULL   (NULL = anything is UNKNOWN: no match)
                              (nothing points here)           4  Finance

 INNER = the 3 arrows only
 LEFT  = 3 arrows + every unmatched LEFT row  (Vikram, right side NULL)
 RIGHT = 3 arrows + every unmatched RIGHT row (Finance, left side NULL)
 FULL  = 3 arrows + unmatched rows from BOTH sides
 CROSS = no ON: every left row paired with every right row (4 x 3 = 12)
```

| Join | Returns | Rows here |
|---|---|---|
| `INNER JOIN` | Only rows that match on both sides | 3 |
| `LEFT [OUTER] JOIN` | All left rows; right columns `NULL` when no match | 4 |
| `RIGHT [OUTER] JOIN` | All right rows; left columns `NULL` when no match | 4 |
| `FULL [OUTER] JOIN` | All rows from both; `NULL` on whichever side is missing | 5 |
| `CROSS JOIN` | Cartesian product, no condition | 12 |
| Self join | Table joined to itself via aliases (any of the above) | varies |

#### INNER JOIN

```sql
SELECT e.Name, d.DeptName
FROM   #E e INNER JOIN #D d ON d.DeptId = e.DeptId;
-- Asha   | Engineering
-- Ravi   | Engineering
-- Sana   | Sales                    (Vikram and Finance are dropped)
```

#### LEFT JOIN

```sql
SELECT e.Name, d.DeptName
FROM   #E e LEFT JOIN #D d ON d.DeptId = e.DeptId;
-- Asha   | Engineering
-- Ravi   | Engineering
-- Sana   | Sales
-- Vikram | NULL                     (kept: left row with no match)
```

#### RIGHT JOIN

```sql
SELECT e.Name, d.DeptName
FROM   #E e RIGHT JOIN #D d ON d.DeptId = e.DeptId;
-- Asha   | Engineering
-- Ravi   | Engineering
-- NULL   | Finance                  (kept: right row with no match)
-- Sana   | Sales
```

`RIGHT JOIN` is just a `LEFT JOIN` with the tables swapped. Most teams standardise on `LEFT JOIN` because it reads in one direction.

#### FULL OUTER JOIN

```sql
SELECT e.Name, d.DeptName
FROM   #E e FULL OUTER JOIN #D d ON d.DeptId = e.DeptId;
-- NULL   | Finance
-- Asha   | Engineering
-- Ravi   | Engineering
-- Sana   | Sales
-- Vikram | NULL
```

Real use: **reconciliation**. Full-join a source table to a target table on the key; rows with `NULL` on one side are missing/extra, rows with differing columns are changed.

#### CROSS JOIN

```sql
SELECT e.Name, d.DeptName FROM #E e CROSS JOIN #D d;     -- 4 x 3 = 12 rows
-- Asha x {Engineering, Finance, Sales}, Ravi x {...}, Sana x {...}, Vikram x {...}
```

Real use: generating combinations (every product x every month for a sales grid), or joining a one-row config/`@variable` table. An accidental cross join (forgetting the `ON`, or a join column that is always true) is a classic cause of a query that "never finishes".

#### SELF JOIN

A table joined to itself, using two aliases that play different roles. The textbook case is employee-to-manager:

```sql
SELECT e.Name AS Employee, m.Name AS Manager
FROM   dbo.Employees e
LEFT JOIN dbo.Employees m ON m.EmployeeId = e.ManagerId     -- LEFT keeps Asha (no manager)
ORDER  BY e.EmployeeId;
-- Asha NULL | Ravi Asha | Meena Asha | Kiran Ravi | Sana Asha
-- Tom Sana  | Uma Sana  | Vikram Asha | Nina Asha | Omar Sana     (10 rows)
-- With INNER JOIN Asha disappears: 9 rows.
```

Other self-join uses: pairs of employees in the same department (`a.EmployeeId < b.EmployeeId` to avoid mirrored duplicates), finding duplicates, comparing a row to the previous row (today `LAG` is better).

:::tip What interviewers look for
They hand you two small tables and ask "how many rows does each join return?". Count matches first, then add unmatched rows for the outer side. Mention how `NULL` keys never match, and say the row count before you run anything.
:::

### Anti-join and semi-join

**Definition.** A *semi-join* returns left rows that **have** a match (without multiplying rows). An *anti-join* returns left rows that have **no** match. They are not keywords; you write them with `EXISTS`/`NOT EXISTS`, `IN`/`NOT IN` or `LEFT JOIN ... IS NULL`.

```sql
-- "Customers who never ordered"  -> Dave
-- 1) LEFT JOIN ... IS NULL   (test a column that is NOT NULL when matched, e.g. the PK)
SELECT c.CustomerId, c.Name
FROM   dbo.Customers c
LEFT JOIN dbo.Orders o ON o.CustomerId = c.CustomerId
WHERE  o.OrderId IS NULL;

-- 2) NOT EXISTS
SELECT c.CustomerId, c.Name
FROM   dbo.Customers c
WHERE  NOT EXISTS (SELECT 1 FROM dbo.Orders o WHERE o.CustomerId = c.CustomerId);
-- Both: 4 | Dave

-- Semi-join: customers that have at least one Pending order (each customer once)
SELECT c.Name FROM dbo.Customers c
WHERE  EXISTS (SELECT 1 FROM dbo.Orders o
               WHERE o.CustomerId = c.CustomerId AND o.Status = N'Pending');   -- Alice
```

| Pattern | NULL-safe? | Notes |
|---|---|---|
| `NOT EXISTS (correlated)` | Yes | Preferred. Stops at first match; clear intent |
| `LEFT JOIN ... WHERE right.PK IS NULL` | Yes (if you test a non-nullable column) | Same plan as `NOT EXISTS` in most cases; popular in interviews |
| `NOT IN (subquery)` | **No** | One `NULL` in the subquery returns **zero rows** |
| `EXCEPT` | Yes (NULLs compare equal) | Returns distinct rows only; compares whole rows |

The optimizer usually turns all three into the same *Left Anti Semi Join* operator, so choose on correctness and readability, not speed folklore.

### ON vs WHERE in outer joins

**Definition.** For an `INNER JOIN`, a predicate in `ON` or `WHERE` gives the same result. For an **outer** join, `ON` decides what *matches*, then unmatched outer rows are added back; `WHERE` runs afterwards and filters the final rows, including those added-back `NULL` rows.

```sql
-- Intent: all customers, with only their Shipped orders
-- WRONG: WHERE kills the NULL rows, so the LEFT JOIN behaves like an INNER JOIN
SELECT c.Name, o.OrderId, o.Status
FROM   dbo.Customers c
LEFT JOIN dbo.Orders o ON o.CustomerId = c.CustomerId
WHERE  o.Status = N'Shipped';
-- Alice 101 | Alice 102 | Bob 103 | Bob 106          (Carol and Dave vanished)

-- RIGHT: condition on the optional side goes in ON
SELECT c.Name, o.OrderId, o.Status
FROM   dbo.Customers c
LEFT JOIN dbo.Orders o ON o.CustomerId = c.CustomerId AND o.Status = N'Shipped'
ORDER  BY c.CustomerId, o.OrderId;
-- Alice 101 Shipped | Alice 102 Shipped | Bob 103 Shipped | Bob 106 Shipped
-- Carol NULL NULL   | Dave NULL NULL                      (all 4 customers kept)
```

Rule of thumb: **filter the preserved (left) side in `WHERE`, filter the optional (right) side in `ON`**. The same trap occurs when you `LEFT JOIN` and then chain an `INNER JOIN` on a column from the optional table: the inner join drops the `NULL` rows again.

:::warn Gotcha
`LEFT JOIN Orders o ... WHERE o.Status <> 'Cancelled'` silently removes customers with no orders (NULL status gives UNKNOWN). Use `ON`, or add `OR o.OrderId IS NULL`.
:::

### Join fan-out (duplicate rows)

Joining two one-to-many children to the same parent multiplies rows, and aggregates are then wrong.

```sql
-- Order 103 has 2 items (325.00 total) and 2 payments (325.00 total)
SELECT o.OrderId,
       SUM(oi.Quantity * oi.UnitPrice) AS ItemsTotal,
       SUM(p.Amount)                   AS Paid
FROM   dbo.Orders o
JOIN   dbo.OrderItems oi ON oi.OrderId = o.OrderId
JOIN   dbo.Payments   p  ON p.OrderId  = o.OrderId
WHERE  o.OrderId = 103
GROUP  BY o.OrderId;
-- 103 | 650.00 | 650.00     <- both doubled: 2 items x 2 payments = 4 joined rows
```

Fix: **aggregate each child to one row per parent first**, then join.

```sql
SELECT o.OrderId, i.ItemsTotal, ISNULL(p.Paid, 0) AS Paid
FROM   dbo.Orders o
JOIN  (SELECT OrderId, SUM(Quantity * UnitPrice) AS ItemsTotal
       FROM dbo.OrderItems GROUP BY OrderId) i ON i.OrderId = o.OrderId
LEFT JOIN (SELECT OrderId, SUM(Amount) AS Paid
           FROM dbo.Payments GROUP BY OrderId) p ON p.OrderId = o.OrderId
ORDER  BY o.OrderId;
-- 101 1050.00 1050.00 | 102 300.00 300.00 | 103 325.00 325.00
-- 104 1000.00 0.00    | 105 100.00 0.00   | 106 300.00 300.00
```

### Join algorithms

**Definition.** The optimizer picks one of three physical join operators per join. You normally do not choose; you give it good indexes and statistics. Knowing them lets you read an execution plan.

| Algorithm | How it works | Best when | Watch out |
|---|---|---|---|
| **Nested Loops** | For each row of the outer input, seek matching rows in the inner input | One side small, other side has an **index on the join key**; OLTP lookups | Inner side as a scan runs once per outer row (huge cost) |
| **Hash Match** | Builds an in-memory hash table on the smaller input, probes with the larger | Large, unsorted, un-indexed inputs; data-warehouse style joins | Needs a memory grant; can **spill to tempdb** if the estimate was low |
| **Merge Join** | Walks two inputs **already sorted** on the join key in lock-step | Both sides indexed/sorted on the key; large ordered sets | If a sort must be added, cost rises |

Join hints (`INNER LOOP JOIN`, `OPTION (HASH JOIN)`) exist but are a last resort: they lock the optimizer into a choice that is wrong when the data grows. SQL Server 2017+ can also pick an *adaptive join* at runtime (batch mode), switching between hash and nested loops based on actual row count.

:::q What is the difference between INNER JOIN and LEFT JOIN, and when would you use each?
`INNER JOIN` returns only rows with a match on both sides. `LEFT JOIN` returns every left row, with NULLs for the right columns when there is no match. Use inner when the relationship is mandatory (order items to orders); use left when the right side is optional or when you are hunting for missing matches, such as customers with no orders.
:::

:::q How do you find records in table A that have no match in table B?
`NOT EXISTS` with a correlated subquery, or `LEFT JOIN B ... WHERE B.pk IS NULL`. I avoid `NOT IN` because a single NULL in the subquery makes it return nothing. `EXCEPT` also works when I compare whole rows.
:::

:::q How many rows does A CROSS JOIN B return, and what if A has 0 rows?
`rows(A) x rows(B)`. With 0 rows on either side the result is empty.
:::

:::q What happens when you join on a column that contains NULLs?
`NULL = NULL` is UNKNOWN, so NULL keys never match in the `ON` clause. With an inner join they vanish; with an outer join they are kept as unmatched rows. If you need NULLs to match, use `ON a.x = b.x OR (a.x IS NULL AND b.x IS NULL)` or `IS NOT DISTINCT FROM` (SQL Server 2022+), knowing both hurt index usage.
:::

## Subqueries, CTEs and Set Operators

### Subqueries

**Definition.** A `SELECT` nested inside another statement. Kinds: **scalar** (returns one value), **row/column list** (used with `IN`/`ANY`), **table** (derived table in `FROM`), **correlated** (references the outer query and is re-evaluated per outer row, at least logically).

```sql
-- Scalar subquery: employees above the company average (94000)
SELECT Name, Salary FROM dbo.Employees
WHERE  Salary > (SELECT AVG(Salary) FROM dbo.Employees)
ORDER  BY Salary DESC;
-- Asha 150000 | Ravi 120000 | Meena 120000 | Tom 100000 | Sana 95000

-- Correlated subquery: above THEIR OWN department's average
SELECT e.Name, e.DepartmentId, e.Salary
FROM   dbo.Employees e
WHERE  e.Salary > (SELECT AVG(x.Salary) FROM dbo.Employees x
                   WHERE  x.DepartmentId = e.DepartmentId)
ORDER  BY e.EmployeeId;
-- Asha (dept 1, avg 120000) | Sana (dept 2, avg 83750) | Tom (dept 2)
-- Vikram (dept NULL): NULL = NULL is UNKNOWN, so the subquery returns NULL and he drops out
```

```sql
-- Scalar subquery in SELECT list: must return exactly one row/column or it errors
SELECT c.Name,
       (SELECT COUNT(*) FROM dbo.Orders o WHERE o.CustomerId = c.CustomerId) AS OrderCount
FROM   dbo.Customers c ORDER BY c.CustomerId;
-- Alice 3 | Bob 2 | Carol 1 | Dave 0
```

#### EXISTS vs IN

| | `IN (subquery)` | `EXISTS (correlated)` |
|---|---|---|
| Question asked | Is the value in this list? | Does at least one matching row exist? |
| Duplicates in subquery | Harmless | Not applicable (stops at first match) |
| `NULL` in subquery | `NOT IN` breaks (returns nothing) | `NOT EXISTS` is safe |
| Multiple columns | No (single column) | Any correlation predicate |
| Performance | Modern optimizer: same semi-join plan in the vast majority of cases | Same |

Rule: use `EXISTS` / `NOT EXISTS` for existence tests; use `IN` for a short literal list. `SELECT 1` vs `SELECT *` inside `EXISTS` makes no difference (the select list is ignored).

:::warn Gotcha
A correlated scalar subquery in the `SELECT` list can run once per row. For large sets rewrite as a `JOIN` to a pre-aggregated derived table, or use a window function.
:::

### CTE (Common Table Expression)

**Definition.** A named, temporary result set defined with `WITH name AS (...)` and visible to **one** following statement. It is a readability tool, similar to an inline view; it is **not** materialised or cached. If you reference it twice it is (usually) evaluated twice.

**Why it matters.** CTEs flatten nested subqueries into a top-to-bottom story, allow multiple steps, and are the only way to write **recursive** queries. They also let you `UPDATE`/`DELETE` through the CTE (the delete-duplicates pattern in the coding section).

```sql
-- Top customers by net spend, in readable steps
WITH OrderTotals AS (
    SELECT OrderId, SUM(Quantity * UnitPrice) AS Total
    FROM   dbo.OrderItems GROUP BY OrderId
),
CustomerSpend AS (
    SELECT o.CustomerId, SUM(t.Total) AS Spend
    FROM   dbo.Orders o JOIN OrderTotals t ON t.OrderId = o.OrderId
    WHERE  o.Status <> N'Cancelled'
    GROUP  BY o.CustomerId
)
SELECT c.Name, cs.Spend
FROM   CustomerSpend cs JOIN dbo.Customers c ON c.CustomerId = cs.CustomerId
ORDER  BY cs.Spend DESC;
-- Alice 1450.00 (1050 + 300 + 100) | Bob 625.00 (325 + 300)
```

Rules: the statement before `WITH` must end in `;` (the classic error 319 "previous statement must be terminated with a semicolon"); column names must be unique; `ORDER BY` is not allowed inside unless with `TOP`.

#### Recursive CTE: org chart

A recursive CTE has an **anchor** member, `UNION ALL`, and a **recursive** member that references the CTE. SQL Server repeats the recursive member against the previous iteration's rows until it returns nothing.

```sql
WITH Org AS (
    SELECT EmployeeId, Name, ManagerId, 0 AS Level,
           CAST(Name AS NVARCHAR(400)) AS Path
    FROM   dbo.Employees WHERE ManagerId IS NULL                 -- anchor: the root
    UNION ALL
    SELECT e.EmployeeId, e.Name, e.ManagerId, o.Level + 1,
           CAST(o.Path + N' > ' + e.Name AS NVARCHAR(400))
    FROM   dbo.Employees e
    JOIN   Org o ON e.ManagerId = o.EmployeeId                   -- recursive member
)
SELECT REPLICATE(N'    ', Level) + Name AS OrgChart, Level, Path
FROM   Org ORDER BY Path;
-- Output:
-- Asha                      0  Asha
--     Meena                 1  Asha > Meena
--     Nina                  1  Asha > Nina
--     Ravi                  1  Asha > Ravi
--         Kiran             2  Asha > Ravi > Kiran
--     Sana                  1  Asha > Sana
--         Omar              2  Asha > Sana > Omar
--         Tom               2  Asha > Sana > Tom
--         Uma               2  Asha > Sana > Uma
--     Vikram                1  Asha > Vikram

-- All direct and indirect reports of Sana (start the anchor at her row)
WITH Reports AS (
    SELECT EmployeeId, Name FROM dbo.Employees WHERE EmployeeId = 5
    UNION ALL
    SELECT e.EmployeeId, e.Name FROM dbo.Employees e JOIN Reports r ON e.ManagerId = r.EmployeeId
)
SELECT Name FROM Reports WHERE EmployeeId <> 5;     -- Tom, Uma, Omar
```

- Default recursion limit is **100** levels. Beyond it: error 530 "The maximum recursion 100 has been exhausted". Override with `OPTION (MAXRECURSION n)` (`0` = unlimited, dangerous with cyclic data).
- A cycle in the data (A manages B, B manages A) loops until the limit. Guard with a path check (`WHERE o.Path NOT LIKE '%' + e.Name + '%'`) or a level cap.
- Other recursive uses: bill of materials, category trees, generating number/date series (`SELECT 1 UNION ALL SELECT n + 1 FROM n WHERE n < 100`).

| | CTE | Derived table | View | `#temp` table |
|---|---|---|---|---|
| Lifetime | One statement, named | One statement, inline | Persisted definition | Stored in tempdb for the session |
| Recursive | **Yes** | No | Only via a CTE inside it | No |
| Data stored | No (expanded into the query) | No | No (unless indexed view) | Yes, with statistics and indexes |
| Reuse in later statements | No | No | Yes | Yes |

:::q Is a CTE faster than a subquery? Is it materialised?
No to both. A CTE is just syntax; the optimizer expands it like a view. It improves readability and enables recursion. If a heavy CTE is referenced several times, it may run several times; put it in a `#temp` table instead.
:::

:::q Write a query to list an employee hierarchy.
Anchor on `ManagerId IS NULL`, `UNION ALL` the recursive member joining `Employees.ManagerId = Org.EmployeeId`, carry a `Level` column that increments, and order by a path string for the indented tree (shown above). Mention the `MAXRECURSION` default of 100 and cycle risk.
:::

### UNION, UNION ALL, EXCEPT, INTERSECT

**Definition.** Set operators combine the results of two `SELECT`s that have the same number of columns with compatible types; column names come from the first query.

| Operator | Result | Duplicates | Cost |
|---|---|---|---|
| `UNION ALL` | Rows from A followed by rows from B | Kept | Cheapest (just concatenates) |
| `UNION` | A + B | **Removed** (sort or hash) | Extra sort/distinct step |
| `INTERSECT` | Rows in **both** | Removed | Distinct |
| `EXCEPT` | Rows in A **not** in B | Removed | Distinct, order matters |

```sql
-- Orders that are Shipped (101,102,103,106) combined with orders that have a payment
SELECT OrderId FROM dbo.Orders WHERE Status = N'Shipped'
UNION                               -- 101, 102, 103, 106                  (4 rows)
SELECT OrderId FROM dbo.Payments;

SELECT OrderId FROM dbo.Orders WHERE Status = N'Shipped'
UNION ALL                           -- 101,101,102,102,103,103,103,106,106 (9 rows)
SELECT OrderId FROM dbo.Payments;

SELECT CustomerId FROM dbo.Customers
EXCEPT    SELECT CustomerId FROM dbo.Orders;             -- 4  (Dave)

SELECT CustomerId FROM dbo.Orders WHERE Status = N'Shipped'
INTERSECT SELECT CustomerId FROM dbo.Orders WHERE Status = N'Pending';   -- 1 (Alice)
```

- Default to `UNION ALL` unless you truly need de-duplication; `UNION` adds a sort/hash on every column.
- `ORDER BY` goes once, at the very end, and may use only first-query column names/aliases.
- Set operators treat `NULL`s as equal (unlike `=`), which makes `EXCEPT` NULL-safe.
- Precedence: `INTERSECT` binds tighter than `UNION`/`EXCEPT`; use parentheses.

### APPLY: CROSS APPLY and OUTER APPLY

**Definition.** `APPLY` runs a table expression (derived table or table-valued function) **once per row of the left input**, and the right side may reference columns of the left row. `CROSS APPLY` is like `INNER JOIN` (left rows with no right rows are dropped). `OUTER APPLY` is like `LEFT JOIN` (kept, with NULLs).

**Why it matters.** It solves things a plain join cannot: "top N per group", calling a TVF per row, unpivoting, and reusing a computed expression.

```sql
-- Latest order per customer: OUTER APPLY keeps Dave
SELECT c.Name, o.OrderId, o.OrderDate
FROM   dbo.Customers c
OUTER APPLY (SELECT TOP (1) OrderId, OrderDate
             FROM   dbo.Orders o
             WHERE  o.CustomerId = c.CustomerId
             ORDER  BY o.OrderDate DESC) o
ORDER  BY c.CustomerId;
-- Alice 105 2024-03-25 | Bob 106 2024-04-02 | Carol 104 2024-03-15 | Dave NULL NULL
-- CROSS APPLY would return only the first three rows.

-- Top 2 orders per customer: change TOP (1) to TOP (2)
-- Alice: 105, 102 | Bob: 106, 103 | Carol: 104
```

```sql
-- Call an inline table-valued function for each row
CREATE FUNCTION dbo.fn_OrderTotal (@OrderId INT) RETURNS TABLE AS RETURN
    (SELECT SUM(Quantity * UnitPrice) AS Total, COUNT(*) AS Lines
     FROM dbo.OrderItems WHERE OrderId = @OrderId);
GO
SELECT o.OrderId, t.Total, t.Lines
FROM   dbo.Orders o CROSS APPLY dbo.fn_OrderTotal(o.OrderId) t;
-- 101 1050.00 2 | 102 300.00 1 | 103 325.00 2 | 104 1000.00 1 | 105 100.00 1 | 106 300.00 1
```

:::q When would you use CROSS APPLY instead of a JOIN?
When the right side depends on the left row: top-N per group (`TOP (n) ... ORDER BY` inside the apply), calling a table-valued function with a column as its argument, or breaking a delimited string with `STRING_SPLIT` per row. A normal join cannot reference the left row inside a derived table. `OUTER APPLY` if I need to keep left rows with no match.
:::

:::q UNION vs UNION ALL?
`UNION ALL` concatenates and keeps duplicates, so it is cheap. `UNION` removes duplicates, which costs a sort or hash across all columns. If the two sets cannot overlap, or duplicates are acceptable, use `UNION ALL`.
:::
