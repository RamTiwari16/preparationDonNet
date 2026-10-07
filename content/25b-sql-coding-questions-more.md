## Classic SQL Interview Problems (9-15)

### 9. Find missing IDs

**Problem.** Invoice numbers should be continuous. Find the missing numbers, both as ranges and as a full list.

```sql
CREATE TABLE dbo.Invoices (InvoiceId INT PRIMARY KEY);
INSERT dbo.Invoices VALUES (1), (2), (3), (5), (6), (9), (10), (11), (15);
```

**Expected output.**

| GapStart | GapEnd |
|---|---|
| 4 | 4 |
| 7 | 8 |
| 12 | 14 |

As a list: 4, 7, 8, 12, 13, 14.

#### Approach A: LEAD to find gap ranges

```sql
SELECT InvoiceId + 1 AS GapStart,
       NextId    - 1 AS GapEnd
FROM  (SELECT InvoiceId,
              LEAD(InvoiceId) OVER (ORDER BY InvoiceId) AS NextId
       FROM   dbo.Invoices) x
WHERE  NextId - InvoiceId > 1;
```

Why it works: each row looks at the next existing id. If the difference is more than 1, everything strictly between them is missing. One ordered pass over the index, and the output stays small even when a gap is millions long. Pre-2012 alternative: self-join `i.InvoiceId + 1` with `NOT EXISTS`.

#### Approach B: numbers table / GENERATE_SERIES

```sql
SELECT s.value AS MissingId
FROM   GENERATE_SERIES(1, (SELECT MAX(InvoiceId) FROM dbo.Invoices)) AS s   -- SQL Server 2022+
WHERE  NOT EXISTS (SELECT 1 FROM dbo.Invoices i WHERE i.InvoiceId = s.value)
ORDER  BY s.value;
-- 4, 7, 8, 12, 13, 14
```

Generate every expected id, then anti-join against the real ones. `GENERATE_SERIES` needs SQL Server 2022 and database compatibility level 160+. On older versions use a permanent `dbo.Numbers` table (a one-column table of 1..1,000,000, a standard utility) or the recursive CTE below.

#### Approach C: recursive CTE

```sql
WITH n AS (
    SELECT MIN(InvoiceId) AS id, MAX(InvoiceId) AS mx FROM dbo.Invoices
    UNION ALL
    SELECT id + 1, mx FROM n WHERE id < mx
)
SELECT n.id AS MissingId
FROM   n
WHERE  NOT EXISTS (SELECT 1 FROM dbo.Invoices i WHERE i.InvoiceId = n.id)
OPTION (MAXRECURSION 0);          -- default limit of 100 levels would fail on big ranges
```

Works everywhere but is row-by-row; fine for thousands, slow for millions.

**Edge cases.** Missing ids *before* the first row (does numbering start at 1?) and after the last are not detected by approach A; decide the expected range explicitly. Identity columns have gaps by design (rollbacks, restarts with identity cache), so "missing identity values" are usually not a bug; business numbers that must be gap-free need their own allocation logic.

:::tip What interviewers prefer
The `LEAD` gaps query: one pass, compact output, shows window-function fluency. Mention a numbers table when they ask for the individual ids.
:::

### 10. Running total

**Problem.** Show each payment with the running total of all payments to date, and a running total per payment method.

Uses `dbo.Payments` from the practice schema.

**Expected output.**

| PaymentId | PaidAt | Method | Amount | RunningTotal | RunningByMethod |
|---|---|---|---|---|---|
| 1 | 2024-01-10 | Card | 1050.00 | 1050.00 | 1050.00 |
| 2 | 2024-02-06 | UPI | 300.00 | 1350.00 | 300.00 |
| 3 | 2024-02-20 | Card | 200.00 | 1550.00 | 1250.00 |
| 4 | 2024-02-28 | UPI | 125.00 | 1675.00 | 425.00 |
| 5 | 2024-04-03 | Card | 300.00 | 1975.00 | 1550.00 |

#### Approach A: SUM() OVER with a ROWS frame

```sql
SELECT PaymentId, PaidAt, Method, Amount,
       SUM(Amount) OVER (ORDER BY PaidAt, PaymentId
                         ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS RunningTotal,
       SUM(Amount) OVER (PARTITION BY Method
                         ORDER BY PaidAt, PaymentId
                         ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS RunningByMethod
FROM   dbo.Payments
ORDER  BY PaidAt, PaymentId;
```

Why it works: for each row, the frame is "every row from the start of the partition up to this one" in the given order; `PARTITION BY Method` restarts the sum per method. One pass, O(n).

#### Approach B: correlated subquery (pre-2012 / no window functions)

```sql
SELECT p.PaymentId, p.PaidAt, p.Amount,
       (SELECT SUM(x.Amount)
        FROM   dbo.Payments x
        WHERE  x.PaidAt < p.PaidAt
           OR (x.PaidAt = p.PaidAt AND x.PaymentId <= p.PaymentId)) AS RunningTotal
FROM   dbo.Payments p
ORDER  BY p.PaidAt, p.PaymentId;
-- same RunningTotal column: 1050, 1350, 1550, 1675, 1975
```

Each row re-sums all earlier rows: O(n^2) reads, painful beyond a few thousand rows. A self-join with `GROUP BY` has the same cost. Cursors and the "quirky update" trick are other historical answers; do not offer them first.

**Edge cases.** Two payments on the same date: without the `PaymentId` tie-breaker and the explicit `ROWS` frame, the default `RANGE` frame gives both rows the same combined total. NULL amounts are ignored by `SUM` (the total does not change on that row). Running totals per day: aggregate by day first, then window over the daily totals.

:::tip What interviewers prefer
`SUM(...) OVER (PARTITION BY ... ORDER BY ... ROWS UNBOUNDED PRECEDING)`. Say "ROWS, not the default RANGE" and "unique ORDER BY" without being asked.
:::

### 11. Rank employees

**Problem.** Rank employees by salary within their department (ties share a rank) and also show their company-wide dense rank.

**Expected output.**

| DepartmentName | Name | Salary | DeptRank | CompanyDenseRank |
|---|---|---|---|---|
| Engineering | Asha | 150000 | 1 | 1 |
| Engineering | Meena | 120000 | 2 | 2 |
| Engineering | Ravi | 120000 | 2 | 2 |
| Engineering | Kiran | 90000 | 4 | 5 |
| Sales | Tom | 100000 | 1 | 3 |
| Sales | Sana | 95000 | 2 | 4 |
| Sales | Omar | 70000 | 3 | 6 |
| Sales | Uma | 70000 | 3 | 6 |
| HR | Nina | 65000 | 1 | 7 |

#### Approach A: window ranking functions

```sql
SELECT d.DepartmentName, e.Name, e.Salary,
       RANK()       OVER (PARTITION BY e.DepartmentId ORDER BY e.Salary DESC) AS DeptRank,
       DENSE_RANK() OVER (ORDER BY e.Salary DESC)                             AS CompanyDenseRank
FROM   dbo.Employees e
JOIN   dbo.Departments d ON d.DepartmentId = e.DepartmentId
ORDER  BY e.DepartmentId, DeptRank, e.Name;
```

Kiran's `DeptRank` is 4 (not 3) because `RANK` skips after the Meena/Ravi tie. His company dense rank is 5 because distinct salaries above him are 150000, 120000, 100000, 95000. The company rank is computed over the *joined* rows, so Vikram (no department) is not part of it; compute it before the join if he should count.

#### Approach B: correlated COUNT (rank without window functions)

```sql
SELECT e.Name, e.Salary,
       1 + (SELECT COUNT(*) FROM dbo.Employees x WHERE x.Salary > e.Salary) AS RankNoWindow
FROM   dbo.Employees e
ORDER  BY RankNoWindow, e.Name;
-- Asha 1 | Meena 2 | Ravi 2 | Tom 4 | Sana 5 | Kiran 6 | Omar 7 | Uma 7 | Nina 9 | Vikram 10
```

`1 + number of people paid more` reproduces `RANK()`; use `COUNT(DISTINCT x.Salary)` for `DENSE_RANK()` semantics; add `AND x.DepartmentId = e.DepartmentId` for a per-department rank.

**Which to choose:** say what each ranking does with ties (see the window functions topic: 1-2-2-4 vs 1-2-2-3 vs 1-2-3-4) and ask which the business wants. Add a tie-breaker column if a strict order is needed.

### 12. Find consecutive records (gaps and islands)

**Problem.** From a login log, find each user's streaks of consecutive login days, then list users who logged in on at least 3 consecutive days.

```sql
CREATE TABLE dbo.Logins (UserId INT NOT NULL, LoginDate DATE NOT NULL);
INSERT dbo.Logins (UserId, LoginDate) VALUES
 (1, '2024-03-01'), (1, '2024-03-02'), (1, '2024-03-03'), (1, '2024-03-05'), (1, '2024-03-06'),
 (2, '2024-03-01'), (2, '2024-03-03'), (2, '2024-03-04'), (2, '2024-03-05'), (2, '2024-03-06'),
 (3, '2024-03-02'), (3, '2024-03-02'), (3, '2024-03-03');   -- user 3 logged in twice on 03-02
```

**Expected output (all streaks).**

| UserId | StreakStart | StreakEnd | Days |
|---|---|---|---|
| 1 | 2024-03-01 | 2024-03-03 | 3 |
| 1 | 2024-03-05 | 2024-03-06 | 2 |
| 2 | 2024-03-01 | 2024-03-01 | 1 |
| 2 | 2024-03-03 | 2024-03-06 | 4 |
| 3 | 2024-03-02 | 2024-03-03 | 2 |

With `HAVING COUNT(*) >= 3`: user 1 (03-01 to 03-03, 3 days) and user 2 (03-03 to 03-06, 4 days).

#### Approach A: ROW_NUMBER difference (islands)

```sql
WITH d AS (                                   -- one row per user per day
    SELECT DISTINCT UserId, LoginDate FROM dbo.Logins
),
g AS (
    SELECT UserId, LoginDate,
           DATEADD(DAY, -ROW_NUMBER() OVER (PARTITION BY UserId ORDER BY LoginDate),
                   LoginDate) AS Grp          -- constant within a consecutive run
    FROM   d
)
SELECT   UserId, MIN(LoginDate) AS StreakStart, MAX(LoginDate) AS StreakEnd,
         COUNT(*) AS Days
FROM     g
GROUP BY UserId, Grp
HAVING   COUNT(*) >= 3                        -- remove for all streaks
ORDER BY UserId, StreakStart;
```

Why it works: in a run of consecutive dates, the date goes up by 1 and the row number goes up by 1, so `date - row_number` stays the same. A gap makes the date jump more than the row number, so the difference changes and a new group starts.

```text
User 1:  LoginDate   rn   LoginDate - rn
         03-01        1   02-29   } island A (3 days)
         03-02        2   02-29   }
         03-03        3   02-29   }
         03-05        4   03-01   } island B (2 days)
         03-06        5   03-01   }
```

:::warn Duplicates break the trick
Without the `DISTINCT` step, user 3's two logins on 03-02 get row numbers 1 and 2, so the same date lands in two different groups and the streak is reported as 2 + 1. Remove duplicates first, or use `DENSE_RANK()` instead of `ROW_NUMBER()` and count `DISTINCT LoginDate`.
:::

#### Approach B: LAG (does a 3-day run end here?)

```sql
WITH d AS (SELECT DISTINCT UserId, LoginDate FROM dbo.Logins),
l AS (
    SELECT UserId, LoginDate,
           LAG(LoginDate, 1) OVER (PARTITION BY UserId ORDER BY LoginDate) AS Prev1,
           LAG(LoginDate, 2) OVER (PARTITION BY UserId ORDER BY LoginDate) AS Prev2
    FROM   d
)
SELECT DISTINCT UserId
FROM   l
WHERE  Prev1 = DATEADD(DAY, -1, LoginDate)
  AND  Prev2 = DATEADD(DAY, -2, LoginDate);
-- 1, 2
```

Why it works: a row whose previous two rows are exactly one and two days earlier is the end of at least a 3-day run (user 2 matches on 03-05 and 03-06, hence `DISTINCT`). Simple for a fixed N, but the islands approach is better for "longest streak" or variable N. The same patterns solve "3 consecutive seats", "status unchanged for N readings", "consecutive months with sales".

:::tip What interviewers prefer
The `ROW_NUMBER` difference (gaps-and-islands) technique. Explain the "date minus row number is constant" idea with a three-row example, and mention de-duplicating first.
:::

### 13. Find duplicate transactions

**Problem.** Card payments are sometimes submitted twice. Find (a) exact duplicates and (b) "likely duplicates": same account and amount within 5 minutes of the previous one.

```sql
CREATE TABLE dbo.CardTransactions (
    TxnId     INT IDENTITY(1,1) PRIMARY KEY,
    AccountId VARCHAR(10)   NOT NULL,
    Amount    DECIMAL(10,2) NOT NULL,
    TxnTime   DATETIME2(0)  NOT NULL
);
INSERT dbo.CardTransactions (AccountId, Amount, TxnTime) VALUES
 ('A1', 50.00, '2024-03-01 10:00:00'),   -- 1
 ('A1', 50.00, '2024-03-01 10:03:00'),   -- 2  3 minutes after 1: suspicious
 ('A1', 50.00, '2024-03-01 11:00:00'),   -- 3  57 minutes after 2: fine
 ('A2', 20.00, '2024-03-01 10:00:00'),   -- 4
 ('A2', 25.00, '2024-03-01 10:01:00'),   -- 5  different amount: fine
 ('A3', 99.99, '2024-03-01 09:00:00'),   -- 6
 ('A3', 99.99, '2024-03-01 09:00:00');   -- 7  exact duplicate of 6
```

**Expected output (b).**

| TxnId | AccountId | Amount | TxnTime | SecsSincePrev |
|---|---|---|---|---|
| 2 | A1 | 50.00 | 2024-03-01 10:03:00 | 180 |
| 7 | A3 | 99.99 | 2024-03-01 09:00:00 | 0 |

#### Approach A: exact duplicates with GROUP BY

```sql
SELECT   AccountId, Amount, TxnTime, COUNT(*) AS Copies
FROM     dbo.CardTransactions
GROUP BY AccountId, Amount, TxnTime
HAVING   COUNT(*) > 1;
-- A3 | 99.99 | 2024-03-01 09:00:00 | 2
```

Misses txn 2: a few seconds of difference defeats exact matching.

#### Approach B: LAG within account and amount

```sql
WITH x AS (
    SELECT *,
           LAG(TxnTime) OVER (PARTITION BY AccountId, Amount
                              ORDER BY TxnTime, TxnId) AS PrevTime
    FROM   dbo.CardTransactions
)
SELECT TxnId, AccountId, Amount, TxnTime,
       DATEDIFF(SECOND, PrevTime, TxnTime) AS SecsSincePrev
FROM   x
WHERE  DATEDIFF(SECOND, PrevTime, TxnTime) <= 300
ORDER  BY TxnId;
-- 2 (180 s after txn 1) and 7 (0 s after txn 6)
```

Why it works: partitioning by account and amount puts candidate duplicates next to each other in time order; `LAG` compares each one with the previous only. The first transaction of each partition has `PrevTime = NULL`, so `DATEDIFF` is NULL and it is not flagged. The original (1, 6) stays unflagged; only the later copies are reported.

#### Approach C: EXISTS with a time window (self-join)

```sql
SELECT t.TxnId, t.AccountId, t.Amount, t.TxnTime
FROM   dbo.CardTransactions t
WHERE  EXISTS (SELECT 1 FROM dbo.CardTransactions p
               WHERE  p.AccountId = t.AccountId
                 AND  p.Amount    = t.Amount
                 AND  p.TxnId    <> t.TxnId
                 AND  p.TxnTime BETWEEN DATEADD(MINUTE, -5, t.TxnTime) AND t.TxnTime
                 AND (p.TxnTime < t.TxnTime OR p.TxnId < t.TxnId))   -- only "later" copies
ORDER  BY t.TxnId;
-- 2, 7
```

More flexible (compares with *any* earlier row in the window, not just the previous one, and allows "amount within 1%"), and with an index on `(AccountId, Amount, TxnTime)` it is a cheap seek per row.

**Edge cases.** Same timestamp: the `TxnId` tie-breaker decides which is the "copy". Window boundary: is exactly 5 minutes a duplicate (`<=` vs `<`)? Ask. Prevention beats detection: an idempotency key from the client with a unique index stops double submits at insert time.

### 14. Latest record for each customer

**Problem.** For each customer, return their most recent order.

**Expected output.**

| Name | OrderId | OrderDate | Status |
|---|---|---|---|
| Alice | 105 | 2024-03-25 | Pending |
| Bob | 106 | 2024-04-02 | Shipped |
| Carol | 104 | 2024-03-15 | Cancelled |

(Dave has no orders; he appears with NULLs only in the `OUTER APPLY` version.)

#### Approach A: ROW_NUMBER per customer

```sql
WITH r AS (
    SELECT o.*,
           ROW_NUMBER() OVER (PARTITION BY o.CustomerId
                              ORDER BY o.OrderDate DESC, o.OrderId DESC) AS rn
    FROM   dbo.Orders o
)
SELECT c.Name, r.OrderId, r.OrderDate, r.Status
FROM   r JOIN dbo.Customers c ON c.CustomerId = r.CustomerId
WHERE  r.rn = 1
ORDER  BY c.CustomerId;
```

Exactly one row per customer, guaranteed by the unique tie-breaker (`OrderId DESC`). Change `rn = 1` to `rn <= 3` for the latest three.

#### Approach B: CROSS APPLY / OUTER APPLY with TOP (1)

```sql
SELECT c.Name, o.OrderId, o.OrderDate, o.Status
FROM   dbo.Customers c
OUTER APPLY (SELECT TOP (1) OrderId, OrderDate, Status
             FROM   dbo.Orders x
             WHERE  x.CustomerId = c.CustomerId
             ORDER  BY x.OrderDate DESC, x.OrderId DESC) o
ORDER  BY c.CustomerId;
-- Alice 105 | Bob 106 | Carol 104 | Dave NULL   (CROSS APPLY drops Dave)
```

With an index on `Orders (CustomerId, OrderDate DESC) INCLUDE (Status)` this is one tiny seek per customer: the fastest option when there are few customers with many orders each. `ROW_NUMBER` tends to win when you need most of the table anyway (one scan).

#### Approach C: join to MAX(date)

```sql
SELECT c.Name, o.OrderId, o.OrderDate
FROM   dbo.Orders o
JOIN   dbo.Customers c ON c.CustomerId = o.CustomerId
JOIN  (SELECT CustomerId, MAX(OrderDate) AS MaxDate
       FROM dbo.Orders GROUP BY CustomerId) m
       ON m.CustomerId = o.CustomerId AND m.MaxDate = o.OrderDate;
-- same 3 rows here
```

Classic but **returns two rows** if a customer has two orders on the latest date, and needs a second pass. Fine to mention, not to lead with.

:::tip What interviewers prefer
`ROW_NUMBER() OVER (PARTITION BY CustomerId ORDER BY OrderDate DESC, OrderId DESC)` filtered to `rn = 1`, then `CROSS APPLY TOP (1)` as the alternative with the index that makes it fast. Mention the tie-breaker and whether customers with no orders should appear.
:::

### 15. Monthly sales report

**Problem.** Report revenue (sum of `Quantity * UnitPrice`) and order count per month for 2024, excluding cancelled orders. Then show months with no sales as zero with a year-to-date total, and pivot revenue by category per month.

**Expected output.**

| SalesYear | SalesMonth | Orders | Revenue |
|---|---|---|---|
| 2024 | 1 | 1 | 1050.00 |
| 2024 | 2 | 2 | 625.00 |
| 2024 | 3 | 1 | 100.00 |
| 2024 | 4 | 1 | 300.00 |

(March: order 104 is cancelled, so only order 105 counts.)

#### Approach A: GROUP BY YEAR, MONTH

```sql
SELECT   YEAR(o.OrderDate)                AS SalesYear,
         MONTH(o.OrderDate)               AS SalesMonth,
         COUNT(DISTINCT o.OrderId)        AS Orders,      -- DISTINCT: items multiply rows
         SUM(oi.Quantity * oi.UnitPrice)  AS Revenue
FROM     dbo.Orders o
JOIN     dbo.OrderItems oi ON oi.OrderId = o.OrderId
WHERE    o.Status <> N'Cancelled'
  AND    o.OrderDate >= '2024-01-01' AND o.OrderDate < '2025-01-01'   -- SARGable year filter
GROUP BY YEAR(o.OrderDate), MONTH(o.OrderDate)
ORDER BY SalesYear, SalesMonth;
```

`COUNT(*)` would count order *lines* (February would show 3, not 2). The functions in `GROUP BY` are fine; filtering with `WHERE YEAR(OrderDate) = 2024` is not (non-SARGable).

#### Approach B: one month key (DATEFROMPARTS / EOMONTH) + FORMAT for display

```sql
SELECT   DATEFROMPARTS(YEAR(o.OrderDate), MONTH(o.OrderDate), 1)   AS MonthStart,
         FORMAT(DATEFROMPARTS(YEAR(o.OrderDate), MONTH(o.OrderDate), 1), 'MMM yyyy')
                                                                  AS MonthLabel,
         SUM(oi.Quantity * oi.UnitPrice)                          AS Revenue
FROM     dbo.Orders o JOIN dbo.OrderItems oi ON oi.OrderId = o.OrderId
WHERE    o.Status <> N'Cancelled'
GROUP BY DATEFROMPARTS(YEAR(o.OrderDate), MONTH(o.OrderDate), 1)
ORDER BY MonthStart;
-- 2024-01-01 Jan 2024 1050.00 | 2024-02-01 Feb 2024 625.00
-- 2024-03-01 Mar 2024 100.00  | 2024-04-01 Apr 2024 300.00
-- GROUP BY EOMONTH(o.OrderDate) gives month-end keys: 2024-01-31, 2024-02-29, ...
```

A single date key sorts correctly and joins easily to a calendar. `FORMAT` is CLR-based and slow on large sets: use it only on the final, small result (or format in the UI). Never group by the formatted string and then sort it ("Apr" sorts before "Feb").

#### Fill missing months and add YTD

```sql
WITH Months AS (                                          -- Jan..May 2024 (2022+ syntax)
    SELECT DATEADD(MONTH, value, CAST('2024-01-01' AS DATE)) AS MonthStart
    FROM   GENERATE_SERIES(0, 4)
),
Sales AS (
    SELECT DATEFROMPARTS(YEAR(o.OrderDate), MONTH(o.OrderDate), 1) AS MonthStart,
           SUM(oi.Quantity * oi.UnitPrice) AS Revenue
    FROM   dbo.Orders o JOIN dbo.OrderItems oi ON oi.OrderId = o.OrderId
    WHERE  o.Status <> N'Cancelled'
    GROUP  BY DATEFROMPARTS(YEAR(o.OrderDate), MONTH(o.OrderDate), 1)
)
SELECT m.MonthStart,
       ISNULL(s.Revenue, 0) AS Revenue,
       SUM(ISNULL(s.Revenue, 0)) OVER (ORDER BY m.MonthStart ROWS UNBOUNDED PRECEDING) AS Ytd
FROM   Months m LEFT JOIN Sales s ON s.MonthStart = m.MonthStart
ORDER  BY m.MonthStart;
-- 2024-01-01 1050.00 1050.00 | 2024-02-01 625.00 1675.00 | 2024-03-01 100.00 1775.00
-- 2024-04-01 300.00 2075.00  | 2024-05-01 0.00 2075.00
```

`GROUP BY` can only produce months that have rows. Driving from a calendar (or `dbo.Calendar` table) with a `LEFT JOIN` is the only way to show May as zero.

#### Pivot: category x month

```sql
-- PIVOT operator
SELECT Category, [1] AS Jan, [2] AS Feb, [3] AS Mar, [4] AS Apr
FROM  (SELECT p.Category, MONTH(o.OrderDate) AS M, oi.Quantity * oi.UnitPrice AS Amount
       FROM   dbo.Orders o
       JOIN   dbo.OrderItems oi ON oi.OrderId  = o.OrderId
       JOIN   dbo.Products   p  ON p.ProductId = oi.ProductId
       WHERE  o.Status <> N'Cancelled' AND YEAR(o.OrderDate) = 2024) src
PIVOT (SUM(Amount) FOR M IN ([1], [2], [3], [4])) pvt
ORDER BY Category;
-- Electronics | 1050.00 | 25.00  | 100.00 | NULL
-- Furniture   | NULL    | 600.00 | NULL   | 300.00

-- Conditional aggregation: same result, zeros instead of NULLs, easier to extend
SELECT p.Category,
       SUM(CASE WHEN MONTH(o.OrderDate) = 1 THEN oi.Quantity * oi.UnitPrice ELSE 0 END) AS Jan,
       SUM(CASE WHEN MONTH(o.OrderDate) = 2 THEN oi.Quantity * oi.UnitPrice ELSE 0 END) AS Feb,
       SUM(CASE WHEN MONTH(o.OrderDate) = 3 THEN oi.Quantity * oi.UnitPrice ELSE 0 END) AS Mar,
       SUM(CASE WHEN MONTH(o.OrderDate) = 4 THEN oi.Quantity * oi.UnitPrice ELSE 0 END) AS Apr
FROM   dbo.Orders o
JOIN   dbo.OrderItems oi ON oi.OrderId  = o.OrderId
JOIN   dbo.Products   p  ON p.ProductId = oi.ProductId
WHERE  o.Status <> N'Cancelled'
  AND  o.OrderDate >= '2024-01-01' AND o.OrderDate < '2025-01-01'
GROUP  BY p.Category
ORDER  BY p.Category;
-- Electronics | 1050.00 | 25.00  | 100.00 | 0.00
-- Furniture   | 0.00    | 600.00 | 0.00   | 300.00
```

Check: February = order 102 (Desk 300, Furniture) + order 103 (Chair 2 x 150 = 300 Furniture, Mouse 25 Electronics), so Furniture 600 and Electronics 25.

`PIVOT` needs the column list hard-coded; for dynamic months build the `IN (...)` list with `STRING_AGG(QUOTENAME(...))` and run it via `sp_executesql`. The source subquery must contain only the grouping, spreading and value columns, or extra columns silently create extra groups.

:::tip What interviewers prefer
`GROUP BY` on a month key with `COUNT(DISTINCT OrderId)`, a SARGable date range in `WHERE`, and a calendar `LEFT JOIN` when asked for empty months. For pivots, many interviewers like conditional aggregation (`SUM(CASE ...)`) because it is portable and handles multiple measures; know the `PIVOT` syntax too.
:::
