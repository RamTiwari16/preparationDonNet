### The answer framework

**In simple words:** SQL rounds test how you think, not just the query. Clarify ties, NULLs and empty results, and sketch a few sample rows with the expected output. Write the simplest correct query, then offer a second approach. Finally, check edge cases on your sample and name an index that makes it fast.

**Real-life example:** A tailor asks questions, takes measurements and shows a sample before cutting the cloth. Cutting first and asking later wastes material.

**Interview question:** The interviewer changes one detail, like "what if two people tie?" How do you handle it?

**Simple answer:** I ask what the business wants: distinct values or rows, and NULL or no row when nothing matches. Then I pick the right tool: `DENSE_RANK` for distinct values, `ROW_NUMBER` for exactly one row, `RANK` for competition-style ranks. I test the tie on my sample rows and suggest an index such as `(DepartmentId, Salary DESC)`.

### 1. Second highest salary

**In simple words:** You want the second highest distinct salary, not simply the second row. The classic way is the `MAX` of all salaries below the overall `MAX`. If nothing is left, `MAX` returns NULL, which is what the problem wants. `DENSE_RANK` also works and can show the people too.

**Real-life example:** Two runners tie for gold in a race. Silver goes to the next different time, not to the second gold runner.

**Interview question:** What happens with ties, and what if there is no second salary?

**Simple answer:** MAX-below-MAX handles ties at the top and returns NULL when there is no second value. `OFFSET 1 ROWS` needs `DISTINCT`, and it returns no row instead of NULL, so I wrap it in a subquery. `DENSE_RANK() = 2` returns everyone on the second salary and also works for any N.

```sql
SELECT MAX(Salary) AS SecondHighest
FROM   dbo.Employees
WHERE  Salary < (SELECT MAX(Salary) FROM dbo.Employees);
```

### 2. Nth highest salary

**In simple words:** Give each salary a `DENSE_RANK` from highest to lowest, where tied salaries share a rank with no gaps. Then keep the rows where the rank equals N. Without window functions, a salary is the Nth highest when exactly N - 1 distinct salaries are bigger.

**Real-life example:** Floors in a building. If two shops share floor 2, the next shop is still on floor 3, and `DENSE_RANK` numbers salary levels the same way.

**Interview question:** Why `DENSE_RANK` and not `RANK`?

**Simple answer:** `RANK` leaves gaps after ties: 150k, 120k, 120k, 100k get 1, 2, 2, 4, so rank 3 does not exist. `DENSE_RANK` gives 1, 2, 2, 3, so rank N is always the Nth distinct salary. If N is too large, the query simply returns no rows.

```sql
WITH r AS (SELECT Name, Salary,
           DENSE_RANK() OVER (ORDER BY Salary DESC) AS dr
           FROM dbo.Employees)
SELECT Name, Salary FROM r WHERE dr = @N;
```

### 3. Find duplicate records

**In simple words:** Group the rows by the columns that define a duplicate, and keep the groups with `HAVING COUNT(*) > 1`. To see every duplicate row with its id, use `COUNT(*) OVER (PARTITION BY ...)`. This window keeps the detail rows and adds the group size to each one.

**Real-life example:** Sorting a pile of forms into stacks by name and email. Any stack with more than one form holds duplicates.

**Interview question:** Why can a self-join miss duplicates?

**Simple answer:** In a join, `NULL = NULL` is not true, so two rows with City NULL never match. `GROUP BY` and `PARTITION BY` treat NULLs as equal, so they catch them. I also ask what "duplicate" means, all columns or a business key like Email, and normalise case and spaces if needed.

```sql
SELECT Name, Email, City, COUNT(*) AS Copies
FROM   dbo.CustomerImport
GROUP  BY Name, Email, City
HAVING COUNT(*) > 1;
```

### 4. Delete duplicate records

**In simple words:** Number the rows inside each duplicate group with `ROW_NUMBER`. `PARTITION BY` lists the columns that define a duplicate, and `ORDER BY` decides which row gets number 1, the one you keep. Put this in a CTE (a named temporary result) and delete the rows where the number is greater than 1.

**Real-life example:** A library finds three copies of the same book. It labels them 1, 2 and 3 by arrival date, keeps copy 1 and removes the rest.

**Interview question:** How do you delete duplicates from a table with no primary key?

**Simple answer:** The same CTE works: `PARTITION BY` all the columns and `ORDER BY (SELECT NULL)`, since any copy may stay. `DELETE FROM` the CTE removes the extra rows from the real table. In production, I run it in a transaction, delete big tables in batches, and add a `UNIQUE` constraint afterwards.

```sql
WITH d AS (
  SELECT ROW_NUMBER() OVER (PARTITION BY Name, Email, City
                            ORDER BY ImportId) AS rn
  FROM dbo.CustomerImport)
DELETE FROM d WHERE rn > 1;
```

### 5. Employees without a department

**In simple words:** An employee with `DepartmentId` NULL has no department. Write `WHERE DepartmentId IS NULL`, never `= NULL`, which is never true. A `LEFT JOIN` to Departments with `WHERE d.DepartmentId IS NULL` also finds employees pointing to a deleted department. For departments with no employees, use `NOT EXISTS`.

**Real-life example:** A school list shows each student's class. Students with a blank class, or a class that was closed, still need a classroom.

**Interview question:** Why does `NOT IN` return no rows when you look for empty departments?

**Simple answer:** Vikram's `DepartmentId` is NULL, so the subquery list contains a NULL. `NOT IN` must then check "not equal to NULL", which is UNKNOWN, not true, so no row passes. `NOT EXISTS` has no such problem, so I use it.

### 6. Department-wise highest salary

**In simple words:** `GROUP BY` department with `MAX(Salary)` gives the top salary value. You cannot just add Name, because Name is not grouped or aggregated. To show who earns it, join back to the per-department maximum. Or use `DENSE_RANK` with `PARTITION BY` department and keep rank 1.

**Real-life example:** Each class has a top exam score. To learn who scored it, you look back at that class's marks list for that score.

**Interview question:** Why can you not add Name to the `GROUP BY` query, and how do you show the people?

**Simple answer:** In a grouped query, each selected column must be grouped or aggregated, so Name causes an error. I use `DENSE_RANK() OVER (PARTITION BY DepartmentId ORDER BY Salary DESC)` and keep rank 1, which returns everyone tied at the top. If exactly one person is required, I use `ROW_NUMBER` with a tie-breaker.

### 7. Top 3 salaries per department

**In simple words:** Rank the employees inside each department by salary, highest first, using `PARTITION BY DepartmentId`. Then keep ranks 1 to 3. The ranking function decides what happens with ties. `DENSE_RANK` keeps the top 3 distinct salary levels, so a department may return more than 3 people.

**Real-life example:** A league sends the top 3 teams of each group to the next round. If two teams tie on points, the rules must say whether both go through.

**Interview question:** Do you want the top 3 salaries or the top 3 people?

**Simple answer:** I ask this first. For 3 distinct salary levels, I use `DENSE_RANK <= 3`; for exactly 3 people, `ROW_NUMBER <= 3` with a tie-breaker like EmployeeId. For competition style, I use `RANK` or `CROSS APPLY TOP (3) WITH TIES`, and an index on `(DepartmentId, Salary DESC)` keeps it fast.

### 8. Employees earning more than their manager

**In simple words:** The manager is also a row in Employees, so join the table to itself. Use alias `e` for the employee and `m` for the manager, and match `m.EmployeeId = e.ManagerId`. Then compare `e.Salary > m.Salary` on the combined row.

**Real-life example:** You hold two copies of the staff list. In one you find each worker; in the other you find their boss, and you compare the salaries side by side.

**Interview question:** What happens to the top boss, who has no manager?

**Simple answer:** The inner join drops her, because her `ManagerId` is NULL and matches no row. That is usually right, since she has no manager to compare with. If the business wants her listed, I use a `LEFT JOIN`; an index on `ManagerId` keeps the self-join cheap.

```sql
SELECT e.Name, e.Salary, m.Name AS Manager
FROM   dbo.Employees e
JOIN   dbo.Employees m ON m.EmployeeId = e.ManagerId
WHERE  e.Salary > m.Salary;
```

### 9. Find missing IDs

**In simple words:** Use `LEAD` to see the next existing id on each row. If the next id is more than 1 bigger, the numbers in between are missing. The gap runs from id + 1 to next id - 1. To list each missing id, generate every expected number and keep those not in the table.

**Real-life example:** Walking down a street and reading house numbers 1, 2, 3, 5. Seeing 5 right after 3 tells you house 4 is missing.

**Interview question:** How do you list each missing id, not just the ranges?

**Simple answer:** I generate all expected numbers with `GENERATE_SERIES` (SQL Server 2022), a numbers table or a recursive CTE. Then I keep the numbers where `NOT EXISTS` a matching row. The `LEAD` query is one ordered pass with a short result, and I mention that identity columns can have gaps by design.

```sql
SELECT InvoiceId + 1 AS GapStart, NextId - 1 AS GapEnd
FROM  (SELECT InvoiceId,
              LEAD(InvoiceId) OVER (ORDER BY InvoiceId) AS NextId
       FROM dbo.Invoices) x
WHERE  NextId - InvoiceId > 1;
```

### 10. Running total

**In simple words:** A running total adds each row's amount to the sum of all earlier rows. Use `SUM(Amount) OVER (ORDER BY ... ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`. Add `PARTITION BY Method` to restart the total for each payment method.

**Real-life example:** A bank passbook shows the balance after each transaction. Each new line is the previous balance plus the new amount.

**Interview question:** What is the common bug in a running-total query?

**Simple answer:** Leaving out the `ROWS` frame. The default `RANGE` frame gives rows with the same `ORDER BY` value the same combined total, and it is slower. So I write `ROWS` and add a unique tie-breaker like PaymentId; a correlated subquery also works, but it re-adds earlier rows for every row, which is O(n^2) (the work grows with the square of the row count).

```sql
SELECT PaymentId, Amount,
       SUM(Amount) OVER (ORDER BY PaidAt, PaymentId
                         ROWS UNBOUNDED PRECEDING) AS RunningTotal
FROM   dbo.Payments;
```

### 11. Rank employees

**In simple words:** Use window ranking functions. `RANK() OVER (PARTITION BY DepartmentId ORDER BY Salary DESC)` ranks people inside each department. `DENSE_RANK() OVER (ORDER BY Salary DESC)` ranks across the whole company. They differ only in how they treat ties.

**Real-life example:** Two runners tie for second place. `RANK` gives the next runner 4th, `DENSE_RANK` gives 3rd, and `ROW_NUMBER` gives everyone a different place.

**Interview question:** What is the difference between `ROW_NUMBER`, `RANK` and `DENSE_RANK`?

**Simple answer:** With a tie for second, `ROW_NUMBER` gives 1, 2, 3, 4, always unique. `RANK` gives 1, 2, 2, 4, with a gap after the tie, and `DENSE_RANK` gives 1, 2, 2, 3, with no gap. I ask which one the business wants and add a tie-breaker if a strict order is needed.

### 12. Find consecutive records (gaps and islands)

**In simple words:** First remove duplicate dates. Then number each user's dates in order with `ROW_NUMBER`. In a run of back-to-back days, the date and the row number both go up by 1, so date minus row number stays the same. Group by that value to get each streak's start, end and length.

**Real-life example:** Cinema seats 5, 6, 7, 10, 11 have list positions 1 to 5. Seat minus position gives 4, 4, 4, 6, 6, and equal results mean the seats sit together.

**Interview question:** Why must you remove duplicate dates first?

**Simple answer:** If a user logs in twice on one day, that day gets two row numbers. Then one date lands in two groups and the streak breaks into pieces. So I use `SELECT DISTINCT` first, or `DENSE_RANK`, and add `HAVING COUNT(*) >= 3` for "3 days in a row".

### 13. Find duplicate transactions

**In simple words:** Exact duplicates are easy: `GROUP BY` all the columns with `HAVING COUNT(*) > 1`. Near duplicates, like the same account and amount within 5 minutes, need `LAG`. Partition by account and amount, order by time, and compare each row's time with the previous row's time. Flag the rows where the gap is 300 seconds or less.

**Real-life example:** A cashier presses "pay" twice by mistake. The bank sees two equal charges a few seconds apart and flags the second one.

**Interview question:** Why does `GROUP BY` miss some duplicates, and how do you prevent them?

**Simple answer:** `GROUP BY` needs exact matches, so payments a few seconds apart look different. `LAG` compares each payment with the previous one for the same account and amount, so it finds near copies and never flags the first one. To prevent them, the client sends an idempotency key (a unique request id), and a unique index rejects the second insert.

### 14. Latest record for each customer

**In simple words:** Number each customer's orders from newest to oldest with `ROW_NUMBER`, partitioned by CustomerId. Order by `OrderDate DESC`, then `OrderId DESC` as a tie-breaker. Keep the rows where the number is 1, which gives exactly one row per customer.

**Real-life example:** A chat app shows only the newest message from each contact at the top of the list.

**Interview question:** Why not just join to `MAX(OrderDate)`?

**Simple answer:** If a customer has two orders on the latest date, that join returns both. `ROW_NUMBER` with a unique tie-breaker always returns one row. `CROSS APPLY` with `TOP (1)` is a good alternative, fast with an index on `(CustomerId, OrderDate DESC)`, and `OUTER APPLY` also keeps customers with no orders.

```sql
WITH r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY CustomerId
           ORDER BY OrderDate DESC, OrderId DESC) AS rn
           FROM dbo.Orders)
SELECT * FROM r WHERE rn = 1;
```

### 15. Monthly sales report

**In simple words:** Join orders to their line items, remove cancelled orders, and group by year and month. Use `SUM(Quantity * UnitPrice)` for revenue and `COUNT(DISTINCT OrderId)` for the number of orders. Filter with a date range, such as `OrderDate >= '2024-01-01' AND OrderDate < '2025-01-01'`, so an index can be used.

**Real-life example:** A shop owner adds up each month's receipts. A receipt with three items still counts as one sale, not three.

**Interview question:** How do you show months with zero sales?

**Simple answer:** `GROUP BY` can only output months that have rows. So I generate the months from a calendar table, `GENERATE_SERIES` or a recursive CTE, `LEFT JOIN` the sales to them, and use `ISNULL(Revenue, 0)`. For a year-to-date column, I add a running `SUM` over the months.

### Can you explain and write this?

**In simple words:** This is a self-test checklist covering joins, `GROUP BY`, `HAVING`, CTEs, subqueries, window functions, ranking, `LEAD` and `LAG`, indexes, procedures, transactions and execution plans. For each topic, explain it aloud in under a minute. Then write the query on the practice tables without looking.

**Real-life example:** A learner driver practises parking, reversing and hill starts one by one. On test day, each skill already feels easy.

**Interview question:** How do you practise SQL so you are ready when the interviewer changes the question?

**Simple answer:** I rebuild the practice database and solve each classic problem twice: once with a window function and once without. Interviewers often forbid the first approach you write. I also say the edge cases aloud, like ties, NULLs and empty results, so a changed detail does not surprise me.

### B1. Customers with no orders

**In simple words:** This is an anti-join: rows in one table with no match in another. `NOT EXISTS` checks, for each customer, whether any order points to them. `LEFT JOIN` with `WHERE o.OrderId IS NULL` does the same, and `EXCEPT` works when you only need the ids.

**Real-life example:** A gym compares its member list with the visit log. Members who never appear in the log have never come in.

**Interview question:** How do you find customers with no shipped orders?

**Simple answer:** I put `Status = 'Shipped'` inside the `NOT EXISTS` subquery, or in the `ON` clause of the `LEFT JOIN`. In the outer `WHERE`, it would turn the `LEFT JOIN` into an inner join and lose the customers I want. I prefer `NOT EXISTS` because it is clear and safe with NULLs.

```sql
SELECT c.CustomerId, c.Name
FROM   dbo.Customers c
WHERE  NOT EXISTS (SELECT 1 FROM dbo.Orders o
                   WHERE o.CustomerId = c.CustomerId);
```

### B2. Products never sold

**In simple words:** The same anti-join idea: list the products that never appear in OrderItems. Use `NOT EXISTS` for each product, or `EXCEPT` on the ProductId column. `EXCEPT` returns the ids from the first query that are missing from the second.

**Real-life example:** A shop compares its catalogue with all past receipts. Items that appear on no receipt have never been sold.

**Interview question:** What if "never sold" means never in a non-cancelled order?

**Simple answer:** Then I join OrderItems to Orders inside the `NOT EXISTS` subquery and add `Status <> 'Cancelled'` there. Keeping the condition inside the subquery means the outer query still checks every product. I always clarify what "sold" means before writing the query.

### B3. Second order date for each customer

**In simple words:** Number each customer's orders from oldest to newest with `ROW_NUMBER`, partitioned by CustomerId. Keep the rows where the number is 2. Customers with one order or none simply do not appear. `CROSS APPLY` with `OFFSET 1 ROWS FETCH NEXT 1 ROWS ONLY` is another way.

**Real-life example:** A coffee shop loyalty card. To find each customer's second visit, you read the second stamp on every card.

**Interview question:** Why add OrderId to the `ORDER BY`?

**Simple answer:** Two orders can share a date. Without a tie-breaker, SQL Server may number them in any order, and the result can change between runs. OrderId makes the order unique and repeatable, and changing `rn = 2` to `rn = N` gives the N-th order.

### B4. Pivot revenue per customer by month

**In simple words:** Pivoting turns rows into columns: each customer becomes a row and each month becomes a revenue column. The `PIVOT` operator does this with `SUM(Amount) FOR M IN ([1], [2], [3], [4])`. It leaves NULL where a customer had no sales, so wrap the columns in `ISNULL(..., 0)`.

**Real-life example:** Turning a long list of receipts into a wall chart. Names go down the side, months go across the top, and totals fill the cells.

**Interview question:** Would you use `PIVOT` or conditional aggregation?

**Simple answer:** Both give the same table. `PIVOT` is short, but the month list is hard-coded and it allows one aggregate. Conditional aggregation, `SUM(CASE WHEN ... THEN ... ELSE 0 END)` per column, works in other databases, gives zeros and supports several measures; for dynamic columns, I build the SQL and run it with `sp_executesql`.

### B5. Median salary

**In simple words:** The median is the middle value after sorting; with an even count, it is the average of the two middle values. SQL Server has `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY Salary) OVER ()`. It is a window function, so add `DISTINCT` to get one row. For the 10 sample salaries, the median is the average of the 5th and 6th: 92,500.

**Real-life example:** Line up ten people by height. The median height is halfway between the 5th and the 6th person.

**Interview question:** How do you find the median without `PERCENTILE_CONT`?

**Simple answer:** I number the rows by salary with `ROW_NUMBER` and get the total with `COUNT(*) OVER ()`. Then I average the rows at positions (count + 1) / 2 and (count + 2) / 2. With integer division, an odd count picks the same middle row twice, and an even count picks the two middle rows.

### B6. Employees hired in the last 30 days

**In simple words:** Compare HireDate with a range: from today minus 30 days up to today. Do the date maths on the constant, not on the column. Keep the column bare, as in `HireDate >= DATEADD(DAY, -30, @Today)`, so SQL Server can use an index on HireDate.

**Real-life example:** To find last month's letters, you compare each letter's date with one fixed start date. You do not work out every letter's age.

**Interview question:** Why not write `DATEDIFF(DAY, HireDate, @Today) <= 30`?

**Simple answer:** It returns the same rows, but it wraps the column in a function. Then SQL Server cannot seek the index on HireDate and must scan every row; this is called non-SARGable (unable to use an index search). I also clarify whether day 30 is included, and handle time zones if the column stores a time.

```sql
DECLARE @Today DATE = CAST(GETDATE() AS DATE);
SELECT Name, HireDate
FROM   dbo.Employees
WHERE  HireDate >= DATEADD(DAY, -30, @Today)
  AND  HireDate <= @Today;
```

### B7. Cumulative percentage (Pareto)

**In simple words:** First, sum the revenue per product in a CTE. Then `SUM(Revenue) OVER ()` gives the grand total, so each product's share is its revenue divided by that. `SUM(Revenue) OVER (ORDER BY Revenue DESC ROWS UNBOUNDED PRECEDING)` gives a running total from the best seller down. Divide it by the grand total for the cumulative percentage.

**Real-life example:** A shop owner learns that a few top products bring in most of the money. The cumulative column shows where the total passes 80%.

**Interview question:** Why multiply by 100.0, and why aggregate in a CTE first?

**Simple answer:** 100.0 forces decimal maths before the division, so integer division does not cut the result. Aggregating first gives one row per product, so the window functions work on product totals, not on order lines. The last row's cumulative share is 100%.

### B8. Year-over-year growth with LAG

**In simple words:** `LAG(Revenue) OVER (ORDER BY SalesYear)` puts the previous year's revenue on the current row. Growth % is (this year - last year) x 100.0 / last year. Wrap the divisor in `NULLIF(..., 0)`, so a zero gives NULL instead of a divide-by-zero error. The first year has no previous value, so its growth is NULL.

**Real-life example:** Comparing this year's payslip with last year's to see your percentage raise.

**Interview question:** When is a self-join safer than `LAG`?

**Simple answer:** When a year can be missing. `LAG` just takes the previous row, so if 2023 is missing, 2024 is compared with 2022. A `LEFT JOIN` on `SalesYear = this year - 1` correctly gives NULL; if every year is present, `LAG` is shorter and reads the table once.

### B9. String aggregation with STRING_AGG

**In simple words:** `STRING_AGG` joins values from many rows into one text value, with a separator. `STRING_AGG(Name, ', ') WITHIN GROUP (ORDER BY Name)` lists each department's employees in one cell. Use it with `GROUP BY`. Before SQL Server 2017, people used `FOR XML PATH` with `STUFF`.

**Real-life example:** A whiteboard team list: one line per team, with the members' names separated by commas.

**Interview question:** What limits or traps does `STRING_AGG` have?

**Simple answer:** It skips NULL values, and the result is limited to 8,000 bytes unless I cast the input to `NVARCHAR(MAX)`. The order is not fixed unless I add `WITHIN GROUP (ORDER BY ...)`. For the reverse, splitting a comma list into rows, I use `STRING_SPLIT`.

### B10. Find duplicate emails

**In simple words:** A plain `GROUP BY Email HAVING COUNT(*) > 1` can miss duplicates. Case rules depend on the collation (the text comparison settings), and a leading space makes emails look different. So normalise first: `GROUP BY LOWER(TRIM(Email))`. `STRING_AGG` can list the ids in each duplicate group.

**Real-life example:** A guest list has "Alice@Mail.com" and " alice@mail.com". A careful host sees they are the same person once spaces and capitals are ignored.

**Interview question:** How do you stop duplicate emails from coming back?

**Simple answer:** I store a normalised email, trimmed and lower-case, in a persisted computed column, and put a `UNIQUE` index on it. Then the database rejects any new row that matches an existing email. To find current duplicates, I group by `LOWER(TRIM(Email))` and keep groups with `COUNT(*) > 1`.
