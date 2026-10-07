## Mastery Checklist

### Can you explain and write this?

Use this as a drill: cover the right column, answer aloud in under a minute, then write the query on the practice schema without looking.

| Topic | Drill (explain it, then write it) |
|---|---|
| JOIN | Given `Employees` and `Departments`, state the row count of INNER (9), LEFT from Employees (10), RIGHT/FULL (10/11) before running them, and explain where the NULL rows come from. |
| GROUP BY | Headcount and payroll per department, including the NULL-department group; explain why `Name` cannot be in the select list. |
| HAVING | Departments with more than 2 employees and average salary above 80000; say which condition belongs in WHERE and which in HAVING. |
| CTE | Rewrite a nested subquery as two chained CTEs; write the recursive org chart with levels and explain MAXRECURSION. |
| Subquery | Employees paid above their department's average (correlated) and above the company average (scalar); explain why NOT IN fails with NULLs. |
| Window functions | Show each employee with department total, department average and percent of department payroll in one query without GROUP BY. |
| ROW_NUMBER | Delete duplicates keeping the earliest row; latest order per customer; explain why a tie-breaker is mandatory. |
| RANK | Rank employees by salary per department and explain the gap after a tie (1, 2, 2, 4). |
| DENSE_RANK | Nth highest salary and top 3 salaries per department; explain why it beats RANK for "Nth highest". |
| LEAD | Days until each customer's next order; find gaps in invoice numbers. |
| LAG | Month-over-month or year-over-year growth percentage with NULLIF for division by zero; detect duplicate transactions within 5 minutes. |
| Indexes | Design the index for `WHERE CustomerId = @c AND OrderDate >= @d ORDER BY OrderDate` and explain key order, INCLUDE and key lookups. |
| Stored Procedures | Write a proc with input/output parameters, `SET NOCOUNT ON`, `XACT_ABORT`, TRY/CATCH and THROW; call it from Dapper. |
| Transactions | Explain ACID, `@@TRANCOUNT`, what ROLLBACK does inside nested BEGIN TRANs, and the isolation level that removes reader/writer blocking (RCSI). |
| Execution Plans | Read a plan right to left, spot a scan vs seek, a key lookup, a spill and an estimated-vs-actual mismatch, and name the fix for each. |

:::tip How to practise
Rebuild the practice database from the CREATE/INSERT script, then solve each classic problem twice: once with a window function and once without. Interviewers often forbid the first approach you write.
:::

## Bonus Practice Questions

### B1. Customers with no orders

**Expected:** `4 | Dave`.

```sql
-- Anti-join with NOT EXISTS (preferred)
SELECT c.CustomerId, c.Name
FROM   dbo.Customers c
WHERE  NOT EXISTS (SELECT 1 FROM dbo.Orders o WHERE o.CustomerId = c.CustomerId);

-- LEFT JOIN ... IS NULL
SELECT c.CustomerId, c.Name
FROM   dbo.Customers c LEFT JOIN dbo.Orders o ON o.CustomerId = c.CustomerId
WHERE  o.OrderId IS NULL;

-- Set operator (ids only)
SELECT CustomerId FROM dbo.Customers EXCEPT SELECT CustomerId FROM dbo.Orders;
```

Variation: "customers with no *shipped* orders" puts `AND o.Status = N'Shipped'` inside the subquery or the `ON` clause, never in the outer `WHERE` (that would turn the LEFT JOIN into an INNER JOIN). Answer: Carol and Dave.

### B2. Products never sold

**Expected:** `5 | Monitor`.

```sql
SELECT p.ProductId, p.Name
FROM   dbo.Products p
WHERE  NOT EXISTS (SELECT 1 FROM dbo.OrderItems oi WHERE oi.ProductId = p.ProductId);

SELECT ProductId FROM dbo.Products
EXCEPT
SELECT ProductId FROM dbo.OrderItems;          -- 5
```

Edge case: "never sold" might mean "never in a non-cancelled order". Then Laptop still counts as sold (order 101), but add the status filter inside the subquery to be safe.

### B3. Second order date for each customer

**Expected:**

| Name | OrderId | OrderDate |
|---|---|---|
| Alice | 102 | 2024-02-05 |
| Bob | 106 | 2024-04-02 |

Carol has only one order and Dave none, so they do not appear.

```sql
WITH r AS (
    SELECT CustomerId, OrderId, OrderDate,
           ROW_NUMBER() OVER (PARTITION BY CustomerId ORDER BY OrderDate, OrderId) AS rn
    FROM   dbo.Orders
)
SELECT c.Name, r.OrderId, r.OrderDate
FROM   r JOIN dbo.Customers c ON c.CustomerId = r.CustomerId
WHERE  r.rn = 2;

-- APPLY + OFFSET: skip the first order, take the next
SELECT c.Name, o.OrderId, o.OrderDate
FROM   dbo.Customers c
CROSS APPLY (SELECT OrderId, OrderDate FROM dbo.Orders x
             WHERE  x.CustomerId = c.CustomerId
             ORDER  BY OrderDate, OrderId
             OFFSET 1 ROWS FETCH NEXT 1 ROWS ONLY) o;
```

### B4. Pivot revenue per customer by month

**Expected** (non-cancelled orders, 2024):

| Customer | Jan | Feb | Mar | Apr |
|---|---|---|---|---|
| Alice | 1050.00 | 300.00 | 100.00 | 0.00 |
| Bob | 0.00 | 325.00 | 0.00 | 300.00 |

```sql
SELECT Customer,
       ISNULL([1], 0) AS Jan, ISNULL([2], 0) AS Feb,
       ISNULL([3], 0) AS Mar, ISNULL([4], 0) AS Apr
FROM  (SELECT c.Name AS Customer, MONTH(o.OrderDate) AS M,
              oi.Quantity * oi.UnitPrice AS Amount
       FROM   dbo.Orders o
       JOIN   dbo.Customers  c  ON c.CustomerId = o.CustomerId
       JOIN   dbo.OrderItems oi ON oi.OrderId   = o.OrderId
       WHERE  o.Status <> N'Cancelled') src
PIVOT (SUM(Amount) FOR M IN ([1], [2], [3], [4])) pvt
ORDER BY Customer;
```

`PIVOT` leaves NULL where a customer has no sales in a month, hence `ISNULL` in the outer select. The conditional-aggregation form (`SUM(CASE WHEN MONTH(o.OrderDate) = 1 THEN ... ELSE 0 END)`) gives the same table. Carol is missing because her only order is cancelled.

### B5. Median salary

Sorted salaries: 60000, 65000, 70000, 70000, **90000, 95000**, 100000, 120000, 120000, 150000. With 10 rows the median is the average of the 5th and 6th: **92500**.

```sql
-- PERCENTILE_CONT is a window (analytic) function in SQL Server: DISTINCT collapses the repeats
SELECT DISTINCT
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY Salary) OVER () AS MedianSalary
FROM   dbo.Employees;                                            -- 92500.0

-- Per department
SELECT DISTINCT DepartmentId,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY Salary)
           OVER (PARTITION BY DepartmentId) AS MedianSalary
FROM   dbo.Employees;
-- NULL 60000 | 1 120000 | 2 82500 | 3 65000

-- Without PERCENTILE_CONT: average the middle one or two rows
SELECT AVG(1.0 * Salary) AS MedianSalary
FROM  (SELECT Salary,
              ROW_NUMBER() OVER (ORDER BY Salary, EmployeeId) AS rn,
              COUNT(*)     OVER ()                            AS Cnt
       FROM   dbo.Employees) x
WHERE  rn IN ((Cnt + 1) / 2, (Cnt + 2) / 2);                    -- rows 5 and 6 -> 92500
```

`PERCENTILE_DISC(0.5)` returns an actual value from the set instead (90000 here). Integer division makes `(Cnt + 1) / 2` and `(Cnt + 2) / 2` the same row when the count is odd.

### B6. Employees hired in the last 30 days

```sql
DECLARE @Today DATE = '2024-10-01';          -- in production: CAST(GETDATE() AS DATE)
SELECT Name, HireDate
FROM   dbo.Employees
WHERE  HireDate >= DATEADD(DAY, -30, @Today)
  AND  HireDate <= @Today;
-- Omar 2024-09-15
```

Keep the column bare and do the arithmetic on the constant: `WHERE DATEDIFF(DAY, HireDate, @Today) <= 30` returns the same rows but cannot seek an index on `HireDate`. Be explicit about the boundary (30 days inclusive?) and about time zones if `HireDate` were a `DATETIME2` (use `SYSUTCDATETIME()` consistently).

### B7. Cumulative percentage (Pareto)

**Problem.** Revenue per product (non-cancelled orders), its share of the total, and the cumulative share from the best seller down.

| Name | Revenue | PctOfTotal | CumulativePct |
|---|---|---|---|
| Laptop | 1000.00 | 48.19 | 48.19 |
| Desk | 600.00 | 28.92 | 77.11 |
| Chair | 300.00 | 14.46 | 91.57 |
| Mouse | 175.00 | 8.43 | 100.00 |

```sql
WITH ps AS (
    SELECT p.Name, SUM(oi.Quantity * oi.UnitPrice) AS Revenue
    FROM   dbo.OrderItems oi
    JOIN   dbo.Orders   o ON o.OrderId   = oi.OrderId
    JOIN   dbo.Products p ON p.ProductId = oi.ProductId
    WHERE  o.Status <> N'Cancelled'
    GROUP  BY p.Name
)
SELECT Name, Revenue,
       CAST(100.0 * Revenue / SUM(Revenue) OVER () AS DECIMAL(5,2)) AS PctOfTotal,
       CAST(100.0 * SUM(Revenue) OVER (ORDER BY Revenue DESC, Name
                                       ROWS UNBOUNDED PRECEDING)
            / SUM(Revenue) OVER () AS DECIMAL(5,2))                 AS CumulativePct
FROM   ps
ORDER  BY Revenue DESC, Name;
```

Total = 2075.00 (Laptop 1000 from order 101 only, since 104 is cancelled; Mouse 50 + 25 + 100). `100.0 *` forces decimal arithmetic before the division. Aggregate first in the CTE, then apply windows over the aggregated rows.

### B8. Year-over-year growth with LAG

```sql
CREATE TABLE dbo.AnnualRevenue (SalesYear INT PRIMARY KEY, Revenue DECIMAL(12,2) NOT NULL);
INSERT dbo.AnnualRevenue VALUES (2021, 800000), (2022, 950000), (2023, 1140000), (2024, 1083000);

SELECT SalesYear, Revenue,
       LAG(Revenue) OVER (ORDER BY SalesYear) AS PrevYear,
       CAST(100.0 * (Revenue - LAG(Revenue) OVER (ORDER BY SalesYear))
            / NULLIF(LAG(Revenue) OVER (ORDER BY SalesYear), 0) AS DECIMAL(6,2)) AS YoYPct
FROM   dbo.AnnualRevenue
ORDER  BY SalesYear;
```

| SalesYear | Revenue | PrevYear | YoYPct |
|---|---|---|---|
| 2021 | 800000.00 | NULL | NULL |
| 2022 | 950000.00 | 800000.00 | 18.75 |
| 2023 | 1140000.00 | 950000.00 | 20.00 |
| 2024 | 1083000.00 | 1140000.00 | -5.00 |

Alternative: self-join `LEFT JOIN dbo.AnnualRevenue p ON p.SalesYear = c.SalesYear - 1` (same result). The self-join is safer when a year can be **missing**: `LAG` would compare 2024 with 2022 if 2023 had no row, while the join correctly returns NULL. `NULLIF(..., 0)` prevents divide-by-zero.

### B9. String aggregation with STRING_AGG

**Expected:**

| DepartmentName | Employees | Headcount |
|---|---|---|
| Engineering | Asha, Kiran, Meena, Ravi | 4 |
| HR | Nina | 1 |
| Sales | Omar, Sana, Tom, Uma | 4 |

```sql
SELECT   d.DepartmentName,
         STRING_AGG(e.Name, ', ') WITHIN GROUP (ORDER BY e.Name) AS Employees,
         COUNT(*) AS Headcount
FROM     dbo.Departments d
JOIN     dbo.Employees   e ON e.DepartmentId = d.DepartmentId
GROUP BY d.DepartmentName
ORDER BY d.DepartmentName;

-- Before SQL Server 2017: FOR XML PATH + STUFF (keeps Finance with NULL)
SELECT d.DepartmentName,
       STUFF((SELECT ', ' + e.Name
              FROM   dbo.Employees e
              WHERE  e.DepartmentId = d.DepartmentId
              ORDER  BY e.Name
              FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS Employees
FROM   dbo.Departments d;
```

`STRING_AGG` skips NULL values; the result is limited to 8000 bytes unless the input is cast to `NVARCHAR(MAX)`. Reverse operation: `STRING_SPLIT(@csv, ',')` (with `enable_ordinal` on 2022+ when order matters).

### B10. Find duplicate emails

```sql
CREATE TABLE dbo.Users (UserId INT PRIMARY KEY, Email NVARCHAR(100) NOT NULL);
INSERT dbo.Users VALUES
 (1, N'alice@example.com'), (2, N'Alice@Example.com'),
 (3, N'bob@example.com'),   (4, N' bob@example.com'),       -- leading space
 (5, N'carol@example.com');

-- Naive: depends on collation; misses the leading-space copy
SELECT Email, COUNT(*) AS Cnt FROM dbo.Users GROUP BY Email HAVING COUNT(*) > 1;
-- alice@example.com | 2    (case-insensitive default collation SQL_Latin1_General_CP1_CI_AS)

-- Normalised: trim + lower-case, and list the offending ids
SELECT   LOWER(TRIM(Email)) AS NormalizedEmail, COUNT(*) AS Cnt,
         STRING_AGG(UserId, ',') WITHIN GROUP (ORDER BY UserId) AS UserIds
FROM     dbo.Users
GROUP BY LOWER(TRIM(Email))
HAVING   COUNT(*) > 1;
-- alice@example.com | 2 | 1,2
-- bob@example.com   | 2 | 3,4
```

Under a case-sensitive collation (`GROUP BY Email COLLATE Latin1_General_CS_AS`) the naive query finds **no** duplicates. Trailing spaces are ignored by `=` comparisons in SQL Server, leading spaces are not. To list every duplicate row use `COUNT(*) OVER (PARTITION BY LOWER(TRIM(Email)))`. To prevent it: store a normalised email in a persisted computed column with a `UNIQUE` index.

## Quick-fire Q&A

:::q Second highest salary in one line?
`SELECT MAX(Salary) FROM Employees WHERE Salary < (SELECT MAX(Salary) FROM Employees);` It handles ties at the top and returns NULL when there is no second value. For the general Nth case use `DENSE_RANK()`.
:::

:::q How do you delete duplicate rows but keep one?
CTE with `ROW_NUMBER() OVER (PARTITION BY <duplicate columns> ORDER BY <keep-first column>)`, then `DELETE FROM cte WHERE rn > 1`. It works even without a primary key. Then add a unique constraint so they do not return.
:::

:::q ROW_NUMBER vs RANK vs DENSE_RANK on ties?
ROW_NUMBER: 1, 2, 3, 4 (unique). RANK: 1, 2, 2, 4 (gap). DENSE_RANK: 1, 2, 2, 3 (no gap). Pick based on whether you want rows, competition ranks or distinct value levels.
:::

:::q What is the gaps-and-islands technique?
Within an ordered sequence, `value - ROW_NUMBER()` stays constant across a run of consecutive values and changes at every gap. Group by that difference to get each island's start, end and length. De-duplicate first.
:::

:::q How do you get the latest row per group efficiently?
`ROW_NUMBER() OVER (PARTITION BY key ORDER BY date DESC, id DESC)` and keep `rn = 1`, or `CROSS APPLY (SELECT TOP (1) ... ORDER BY date DESC)` backed by an index on `(key, date DESC)`. Joining to `MAX(date)` returns duplicates on date ties.
:::

:::q Why is COUNT(DISTINCT OrderId) needed in a monthly report joined to OrderItems?
Joining orders to their line items repeats each order once per line, so `COUNT(*)` counts lines, not orders. `COUNT(DISTINCT o.OrderId)` counts orders while `SUM` over lines still gives revenue.
:::

:::q How do you show months with zero sales?
`GROUP BY` can only output months that have rows. Generate the months (calendar table, `GENERATE_SERIES`, or a recursive CTE) and `LEFT JOIN` the aggregated sales to it, with `ISNULL(Revenue, 0)`.
:::

:::q How do you calculate a running total, and what is the common bug?
`SUM(x) OVER (PARTITION BY ... ORDER BY ... ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`. The bug is omitting the frame: the default `RANGE` frame gives rows with equal ORDER BY values the same total and is slower.
:::

:::q PIVOT or conditional aggregation?
Both turn rows into columns. PIVOT is concise but needs hard-coded column values and one aggregate. Conditional aggregation (`SUM(CASE WHEN ... THEN ... ELSE 0 END)`) is portable, supports several measures and zeros instead of NULLs. For dynamic columns, build the list and run it with `sp_executesql`.
:::

:::q How do you find employees earning more than their managers?
Self-join `Employees e JOIN Employees m ON m.EmployeeId = e.ManagerId WHERE e.Salary > m.Salary`. The inner join excludes the top manager, whose `ManagerId` is NULL. On the sample data the only match is Tom (100000) over Sana (95000).
:::
