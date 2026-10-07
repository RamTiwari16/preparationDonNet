## Window Functions (very important)

### What a window function is

**Definition.** A window function computes a value for **each row** using a set of related rows (the *window*) defined by `OVER (...)`, **without collapsing** the rows the way `GROUP BY` does.

```text
function(...) OVER (
    PARTITION BY <cols>     -- split rows into independent groups (optional)
    ORDER BY     <cols>     -- order inside each partition (required for ranking/LAG/LEAD)
    ROWS | RANGE BETWEEN ... -- frame: which rows around the current one (aggregates, FIRST/LAST_VALUE)
)
```

**Why it matters.** Top-N per group, de-duplication, running totals, previous/next row comparisons, percent-of-total and gaps-and-islands all become one readable pass instead of self-joins and correlated subqueries. It is the most common "senior" SQL interview topic.

| | `GROUP BY` | Window function |
|---|---|---|
| Output rows | One per group | One per input row |
| Detail columns available | Only grouped columns | All columns |
| Can mix aggregate and detail | No | Yes (`Salary` next to `SUM(Salary) OVER (...)`) |
| Evaluated | Step 3 | Step 5 (in `SELECT`), after `WHERE`/`GROUP BY`/`HAVING` |

Because window functions are evaluated in the `SELECT` step, you **cannot** use them in `WHERE`, `GROUP BY` or `HAVING`. Wrap in a CTE/derived table and filter outside.

### ROW_NUMBER, RANK, DENSE_RANK, NTILE

**Definition.** Ranking functions number rows in `ORDER BY` order within each partition. They differ **only in how ties are treated**.

```sql
SELECT Name, Salary,
       ROW_NUMBER() OVER (ORDER BY Salary DESC, EmployeeId) AS RowNum,
       RANK()       OVER (ORDER BY Salary DESC)             AS Rnk,
       DENSE_RANK() OVER (ORDER BY Salary DESC)             AS DenseRnk,
       NTILE(3)     OVER (ORDER BY Salary DESC, EmployeeId) AS Tile
FROM   dbo.Employees
ORDER  BY Salary DESC, EmployeeId;
```

| Name | Salary | ROW_NUMBER | RANK | DENSE_RANK | NTILE(3) |
|---|---|---|---|---|---|
| Asha | 150000 | 1 | 1 | 1 | 1 |
| Ravi | 120000 | 2 | **2** | **2** | 1 |
| Meena | 120000 | 3 | **2** | **2** | 1 |
| Tom | 100000 | 4 | **4** | **3** | 1 |
| Sana | 95000 | 5 | 5 | 4 | 2 |
| Kiran | 90000 | 6 | 6 | 5 | 2 |
| Uma | 70000 | 7 | **7** | **6** | 2 |
| Omar | 70000 | 8 | **7** | **6** | 3 |
| Nina | 65000 | 9 | 9 | 7 | 3 |
| Vikram | 60000 | 10 | 10 | 8 | 3 |

| Function | Ties | Gaps after ties | Use it for |
|---|---|---|---|
| `ROW_NUMBER()` | Different numbers (arbitrary unless the `ORDER BY` is unique) | n/a | De-duplication, pagination, "exactly one row per group" |
| `RANK()` | Same number | **Yes** (1, 2, 2, 4) | Competition ranking ("joint 2nd, next is 4th") |
| `DENSE_RANK()` | Same number | **No** (1, 2, 2, 3) | "Nth highest distinct value", top N salaries per dept including ties |
| `NTILE(n)` | Splits into n near-equal buckets (first buckets get the extra rows: 10 rows / 3 = 4, 3, 3) | n/a | Quartiles, deciles, load splitting |

:::warn ROW_NUMBER with ties is non-deterministic
`ROW_NUMBER() OVER (ORDER BY Salary DESC)` may number Ravi 2 and Meena 3 today and the reverse tomorrow. Always add a unique tie-breaker (`, EmployeeId`) when the result must be stable (pagination, "keep the first duplicate").
:::

### PARTITION BY: per-group calculations

`PARTITION BY` restarts the calculation for each group. Combined with aggregates, you get group totals next to the detail rows.

```sql
SELECT d.DepartmentName, e.Name, e.Salary,
       ROW_NUMBER()  OVER (PARTITION BY e.DepartmentId ORDER BY e.Salary DESC, e.EmployeeId) AS RnInDept,
       DENSE_RANK()  OVER (PARTITION BY e.DepartmentId ORDER BY e.Salary DESC)  AS DrInDept,
       SUM(e.Salary) OVER (PARTITION BY e.DepartmentId) AS DeptPayroll,
       COUNT(*)      OVER (PARTITION BY e.DepartmentId) AS DeptHeadcount,
       CAST(100.0 * e.Salary / SUM(e.Salary) OVER (PARTITION BY e.DepartmentId)
            AS DECIMAL(5,1)) AS PctOfDept
FROM   dbo.Employees e
JOIN   dbo.Departments d ON d.DepartmentId = e.DepartmentId
ORDER  BY e.DepartmentId, e.Salary DESC, e.EmployeeId;
```

| Dept | Name | Salary | RnInDept | DrInDept | DeptPayroll | DeptHeadcount | PctOfDept |
|---|---|---|---|---|---|---|---|
| Engineering | Asha | 150000 | 1 | 1 | 480000 | 4 | 31.3 |
| Engineering | Ravi | 120000 | 2 | 2 | 480000 | 4 | 25.0 |
| Engineering | Meena | 120000 | 3 | 2 | 480000 | 4 | 25.0 |
| Engineering | Kiran | 90000 | 4 | 3 | 480000 | 4 | 18.8 |
| Sales | Tom | 100000 | 1 | 1 | 335000 | 4 | 29.9 |
| Sales | Sana | 95000 | 2 | 2 | 335000 | 4 | 28.4 |
| Sales | Uma | 70000 | 3 | 3 | 335000 | 4 | 20.9 |
| Sales | Omar | 70000 | 4 | 3 | 335000 | 4 | 20.9 |
| HR | Nina | 65000 | 1 | 1 | 65000 | 1 | 100.0 |

```sql
-- Highest paid per department: filter the window result OUTSIDE
WITH r AS (
    SELECT Name, DepartmentId, Salary,
           DENSE_RANK() OVER (PARTITION BY DepartmentId ORDER BY Salary DESC) AS dr
    FROM   dbo.Employees
)
SELECT Name, DepartmentId, Salary FROM r WHERE dr = 1 ORDER BY DepartmentId;
-- Vikram NULL 60000 | Asha 1 150000 | Tom 2 100000 | Nina 3 65000
-- (NULL DepartmentId forms its own partition)

-- Window over an aggregate: rank departments by payroll, show company total
SELECT   DepartmentId, SUM(Salary) AS Payroll,
         SUM(SUM(Salary)) OVER ()                AS Company,       -- 880000
         RANK() OVER (ORDER BY SUM(Salary) DESC) AS PayrollRank
FROM     dbo.Employees WHERE DepartmentId IS NOT NULL
GROUP BY DepartmentId;
-- 1 480000 880000 1 | 2 335000 880000 2 | 3 65000 880000 3
```

`OVER ()` with nothing inside = the whole result set is one window (grand totals, percent of total).

### LAG and LEAD

**Definition.** `LAG(col, n, default)` reads a value from **n rows before** the current row in the window order; `LEAD` reads **n rows after**. Default n = 1, default value `NULL`.

```sql
WITH OrderTotals AS (
    SELECT o.OrderId, o.CustomerId, o.OrderDate, SUM(oi.Quantity * oi.UnitPrice) AS Total
    FROM   dbo.Orders o JOIN dbo.OrderItems oi ON oi.OrderId = o.OrderId
    GROUP  BY o.OrderId, o.CustomerId, o.OrderDate
)
SELECT CustomerId, OrderId, OrderDate, Total,
       LAG(Total)      OVER (PARTITION BY CustomerId ORDER BY OrderDate) AS PrevTotal,
       LEAD(OrderDate) OVER (PARTITION BY CustomerId ORDER BY OrderDate) AS NextOrderDate,
       DATEDIFF(DAY, LAG(OrderDate) OVER (PARTITION BY CustomerId ORDER BY OrderDate),
                OrderDate) AS DaysSincePrev
FROM   OrderTotals
ORDER  BY CustomerId, OrderDate;
```

| CustomerId | OrderId | OrderDate | Total | PrevTotal | NextOrderDate | DaysSincePrev |
|---|---|---|---|---|---|---|
| 1 | 101 | 2024-01-10 | 1050.00 | NULL | 2024-02-05 | NULL |
| 1 | 102 | 2024-02-05 | 300.00 | 1050.00 | 2024-03-25 | 26 |
| 1 | 105 | 2024-03-25 | 100.00 | 300.00 | NULL | 49 |
| 2 | 103 | 2024-02-20 | 325.00 | NULL | 2024-04-02 | NULL |
| 2 | 106 | 2024-04-02 | 300.00 | 325.00 | NULL | 42 |
| 3 | 104 | 2024-03-15 | 1000.00 | NULL | NULL | NULL |

Use cases: change vs previous period (month-over-month, year-over-year growth), time between events (churn, session gaps), detecting status changes, gaps in sequences, consecutive-day streaks. Before SQL Server 2012 this needed a self-join on `RowNum = RowNum - 1`. `LAG(Total, 1, 0)` returns `0` instead of `NULL` for the first row.

### FIRST_VALUE and LAST_VALUE

```sql
SELECT Name, DepartmentId, Salary,
       FIRST_VALUE(Name) OVER (PARTITION BY DepartmentId
                               ORDER BY Salary DESC, EmployeeId)           AS TopEarner,
       LAST_VALUE(Name)  OVER (PARTITION BY DepartmentId
                               ORDER BY Salary DESC, EmployeeId)           AS LastWrong,
       LAST_VALUE(Name)  OVER (PARTITION BY DepartmentId
                               ORDER BY Salary DESC, EmployeeId
                               ROWS BETWEEN UNBOUNDED PRECEDING
                                        AND UNBOUNDED FOLLOWING)          AS LowestEarner
FROM   dbo.Employees WHERE DepartmentId IN (1, 2)
ORDER  BY DepartmentId, Salary DESC, EmployeeId;
-- Asha  | Asha | Asha  | Kiran
-- Ravi  | Asha | Ravi  | Kiran      <- LastWrong just echoes the current row
-- Meena | Asha | Meena | Kiran
-- Kiran | Asha | Kiran | Kiran
-- Tom   | Tom  | Tom   | Omar
-- Sana  | Tom  | Sana  | Omar
-- Uma   | Tom  | Uma   | Omar
-- Omar  | Tom  | Omar  | Omar
```

`LAST_VALUE` looks wrong because of the **default frame** (next topic): with `ORDER BY`, the frame ends at the current row, so the "last" row of the frame is the current row. Specify `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`, or use `FIRST_VALUE` with the order reversed.

### Running totals, frames, ROWS vs RANGE

**Definition.** For aggregate window functions with `ORDER BY`, the **frame** says which rows relative to the current one are aggregated:

```text
ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW   -- running total (all rows so far)
ROWS BETWEEN 2 PRECEDING AND CURRENT ROW           -- moving window of 3 rows
ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING   -- remaining total
ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING   -- whole partition
```

- `ROWS` counts physical rows.
- `RANGE` groups rows with the **same `ORDER BY` value** ("peers") and treats them as one: all peers get the same result. SQL Server supports `RANGE` only with `UNBOUNDED`/`CURRENT ROW`.
- **Default frame when `ORDER BY` is present and no frame is given: `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`.** Without `ORDER BY`: the whole partition.

```sql
SELECT Name, Salary,
       SUM(Salary) OVER (ORDER BY Salary)                                    AS RangeDefault,
       SUM(Salary) OVER (ORDER BY Salary, EmployeeId ROWS UNBOUNDED PRECEDING) AS RowsFrame
FROM   dbo.Employees ORDER BY Salary, EmployeeId;
```

| Name | Salary | RangeDefault | RowsFrame |
|---|---|---|---|
| Vikram | 60000 | 60000 | 60000 |
| Nina | 65000 | 125000 | 125000 |
| Uma | 70000 | **265000** | **195000** |
| Omar | 70000 | 265000 | 265000 |
| Kiran | 90000 | 355000 | 355000 |
| Sana | 95000 | 450000 | 450000 |
| Tom | 100000 | 550000 | 550000 |
| Ravi | 120000 | **790000** | **670000** |
| Meena | 120000 | 790000 | 790000 |
| Asha | 150000 | 940000 | 940000 |

:::warn The ROWS vs RANGE default pitfall
A "running total" written as `SUM(x) OVER (ORDER BY OrderDate)` silently uses `RANGE`: two orders on the same date get the same, already-combined total, so the running total "jumps". It is also slower: `RANGE` uses an on-disk worktable spool, while `ROWS` uses a fast in-memory one (batch mode on 2019+ narrows the gap). **Always write `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` and a unique `ORDER BY`** for running totals.
:::

```sql
-- Running total and 3-order moving average over all orders
WITH OrderTotals AS (
    SELECT o.OrderId, o.OrderDate, SUM(oi.Quantity * oi.UnitPrice) AS Total
    FROM   dbo.Orders o JOIN dbo.OrderItems oi ON oi.OrderId = o.OrderId
    GROUP  BY o.OrderId, o.OrderDate
)
SELECT OrderId, OrderDate, Total,
       SUM(Total) OVER (ORDER BY OrderDate, OrderId
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS RunningTotal,
       AVG(Total) OVER (ORDER BY OrderDate, OrderId
                        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)         AS MovingAvg3
FROM   OrderTotals ORDER BY OrderDate;
```

| OrderId | OrderDate | Total | RunningTotal | MovingAvg3 |
|---|---|---|---|---|
| 101 | 2024-01-10 | 1050.00 | 1050.00 | 1050.000000 |
| 102 | 2024-02-05 | 300.00 | 1350.00 | 675.000000 |
| 103 | 2024-02-20 | 325.00 | 1675.00 | 558.333333 |
| 104 | 2024-03-15 | 1000.00 | 2675.00 | 541.666666 |
| 105 | 2024-03-25 | 100.00 | 2775.00 | 475.000000 |
| 106 | 2024-04-02 | 300.00 | 3075.00 | 466.666666 |

The first two moving-average rows average fewer than 3 rows (the frame is shorter at the start). Add `PARTITION BY CustomerId` for a per-customer running total: Alice 1050 -> 1350 -> 1450, Bob 325 -> 625, Carol 1000.

### COUNT() OVER and other aggregates

Every aggregate (`SUM`, `COUNT`, `AVG`, `MIN`, `MAX`, `STDEV`...) can be a window function.

```sql
-- How many orders does each order's customer have, and what number is this order?
SELECT CustomerId, OrderId,
       COUNT(*) OVER (PARTITION BY CustomerId)                         AS CustomerOrders,
       COUNT(*) OVER (PARTITION BY CustomerId ORDER BY OrderDate
                      ROWS UNBOUNDED PRECEDING)                        AS OrderSeq
FROM   dbo.Orders ORDER BY CustomerId, OrderDate;
-- 1 101 3 1 | 1 102 3 2 | 1 105 3 3 | 2 103 2 1 | 2 106 2 2 | 3 104 1 1

-- Find duplicates without collapsing them (show every duplicate row)
SELECT * FROM (
    SELECT *, COUNT(*) OVER (PARTITION BY Salary) AS SameSalary FROM dbo.Employees
) x WHERE SameSalary > 1;      -- Ravi, Meena (120000) and Uma, Omar (70000)
```

`COUNT(DISTINCT ...) OVER (...)` is **not supported** in SQL Server; use `DENSE_RANK` ascending + descending minus 1, or a grouped subquery.

### Window functions: common patterns

| Problem | Pattern |
|---|---|
| Top N per group | `ROW_NUMBER()`/`DENSE_RANK() OVER (PARTITION BY g ORDER BY x DESC)` then `WHERE rn <= N` |
| Latest row per key | `ROW_NUMBER() OVER (PARTITION BY key ORDER BY date DESC)` then `rn = 1` |
| Delete duplicates | CTE with `ROW_NUMBER() OVER (PARTITION BY dup_cols ORDER BY id)`, `DELETE ... WHERE rn > 1` |
| Running total | `SUM(x) OVER (ORDER BY d ROWS UNBOUNDED PRECEDING)` |
| Percent of total | `x * 100.0 / SUM(x) OVER ()` |
| Change vs previous | `x - LAG(x) OVER (ORDER BY d)` |
| Gaps and islands | `d - ROW_NUMBER()` is constant within a consecutive run |
| Pagination | `ROW_NUMBER()` (old) or `OFFSET ... FETCH` |
| Median | `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY x) OVER (PARTITION BY g)` |

All of these are worked end to end in the SQL coding questions section.

:::q Difference between ROW_NUMBER, RANK and DENSE_RANK?
All three number rows in the `OVER (ORDER BY ...)` order. `ROW_NUMBER` gives unique numbers even for ties (1, 2, 3, 4). `RANK` gives ties the same number and skips the next ones (1, 2, 2, 4). `DENSE_RANK` gives ties the same number without gaps (1, 2, 2, 3). For "second highest salary" with ties I use `DENSE_RANK`; for de-duplication I use `ROW_NUMBER`.
:::

:::q Why can't I use ROW_NUMBER() in a WHERE clause?
Window functions are computed in the `SELECT` phase, after `WHERE`, `GROUP BY` and `HAVING`. So `WHERE ROW_NUMBER() OVER (...) = 1` is a syntax error. Compute it in a CTE or derived table and filter in the outer query. (SQL Server has no `QUALIFY` clause.)
:::

:::q What is the difference between PARTITION BY and GROUP BY?
`GROUP BY` collapses each group into one output row, so detail columns are lost. `PARTITION BY` defines groups for a window function but keeps every row, so I can show each employee with their department's total next to them.
:::

:::q Your running total gives the same value for two rows. Why?
The window has `ORDER BY` but no frame, so the default `RANGE UNBOUNDED PRECEDING` treats rows with the same order value as peers and gives them the same cumulative sum. Use `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` and add a unique tie-breaker to the `ORDER BY`.
:::
