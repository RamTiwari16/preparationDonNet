## How to Approach SQL Coding Rounds

### The answer framework

**Definition.** SQL coding rounds give you a small schema and a business question, then watch *how* you reason: do you clarify ties and NULLs, pick a set-based approach, and verify against sample rows?

**Why it matters.** Most candidates know one memorised answer per question. Interviewers then change one detail ("what if two people tie?", "what if there is no second salary?", "now per department"). Knowing two approaches and the edge cases is what separates a 2-year from a 5-year answer.

Say these steps out loud:

1. **Clarify**: ties (distinct values or rows?), NULLs, empty result (return NULL or no row?), what "latest" means when dates tie.
2. **Sketch the rows**: write 4-6 sample rows and the expected output first.
3. **Write the simplest correct query**, then offer the alternative (window function vs subquery vs `APPLY`).
4. **Walk the edge cases** against your sample.
5. **Mention performance**: which index supports it (`(DepartmentId, Salary DESC)`, `(CustomerId, OrderDate DESC)`).

All questions reuse the practice schema from the SQL Server section (`Employees`, `Departments`, `Customers`, `Orders`, `OrderItems`, `Products`, `Payments`). The Employees data, which most questions use:

| EmployeeId | Name | Salary | DepartmentId | ManagerId |
|---|---|---|---|---|
| 1 | Asha | 150000 | 1 Engineering | NULL |
| 2 | Ravi | 120000 | 1 Engineering | 1 |
| 3 | Meena | 120000 | 1 Engineering | 1 |
| 4 | Kiran | 90000 | 1 Engineering | 2 |
| 5 | Sana | 95000 | 2 Sales | 1 |
| 6 | Tom | 100000 | 2 Sales | 5 |
| 7 | Uma | 70000 | 2 Sales | 5 |
| 8 | Vikram | 60000 | NULL | 1 |
| 9 | Nina | 65000 | 3 HR | 1 |
| 10 | Omar | 70000 | 2 Sales | 5 |

Departments: 1 Engineering, 2 Sales, 3 HR, 4 Finance (empty). Distinct salaries, highest first: 150000, 120000, 100000, 95000, 90000, 70000, 65000, 60000.

## Classic SQL Interview Problems (1-8)

### 1. Second highest salary

**Problem.** Return the second highest salary in `Employees`. If there is no second highest, return `NULL`.

**Expected output.**

| SecondHighest |
|---|
| 120000 |

Note the tie: Ravi and Meena both earn 120000. "Second highest" means the second highest **distinct** value, not the second row (which would also be 120000 here, but would be wrong if two people shared 150000).

#### Approach A: MAX below the MAX

```sql
SELECT MAX(Salary) AS SecondHighest
FROM   dbo.Employees
WHERE  Salary < (SELECT MAX(Salary) FROM dbo.Employees);
-- 120000
```

Why it works: remove the top value, then the maximum of what is left is the second highest distinct value. Ties at the top are handled automatically, and if nothing is left `MAX` over an empty set returns `NULL` (one row with NULL), which is exactly the required behaviour. Does not generalise to N.

#### Approach B: DISTINCT + OFFSET/FETCH

```sql
SELECT DISTINCT Salary
FROM   dbo.Employees
ORDER  BY Salary DESC
OFFSET 1 ROWS FETCH NEXT 1 ROWS ONLY;
-- 120000

-- Wrap it as a scalar subquery to get NULL instead of an empty result
SELECT (SELECT DISTINCT Salary FROM dbo.Employees WHERE DepartmentId = 3
        ORDER BY Salary DESC OFFSET 1 ROWS FETCH NEXT 1 ROWS ONLY) AS SecondInHR;
-- NULL   (HR has only Nina)
```

`DISTINCT` is essential: without it, two people on 150000 would make "offset 1" return 150000 again. The older equivalent is `TOP (1)` over a `DISTINCT TOP (2)` sorted ascending.

#### Approach C: DENSE_RANK (returns the people too)

```sql
WITH r AS (
    SELECT Name, Salary, DENSE_RANK() OVER (ORDER BY Salary DESC) AS dr
    FROM   dbo.Employees
)
SELECT Name, Salary FROM r WHERE dr = 2;
-- Ravi  120000
-- Meena 120000
```

`DENSE_RANK` gives tied salaries the same rank with no gaps, so rank 2 is always the second distinct value. `RANK` would be wrong after a tie at the top (1, 1, 3: there would be no rank 2). `ROW_NUMBER` would pick one arbitrary row.

**Edge cases.** All salaries equal: A returns NULL, B returns no row (wrap it), C returns no row. NULL salaries: ignored by `MAX`; sorted last in `DESC` order; filter them out explicitly if the column is nullable. Single employee: NULL.

:::tip What interviewers prefer
Start with `DENSE_RANK` (it generalises to N, per department, and returns names), then show `MAX(...) WHERE < MAX(...)` as the classic one-liner. Mentioning the tie and the "return NULL" requirement unprompted is what scores.
:::

### 2. Nth highest salary

**Problem.** Return the Nth highest distinct salary for a given `@N`. Return nothing (or NULL) if fewer than N distinct salaries exist.

**Expected output** (`@N = 3`):

| Name | Salary |
|---|---|
| Tom | 100000 |

For `@N = 4`: 95000 (Sana). For `@N = 20`: no rows.

#### Approach A: DENSE_RANK

```sql
DECLARE @N INT = 3;
WITH r AS (
    SELECT Name, Salary, DENSE_RANK() OVER (ORDER BY Salary DESC) AS dr
    FROM   dbo.Employees
)
SELECT Name, Salary FROM r WHERE dr = @N;
-- Tom 100000
```

#### Approach B: correlated subquery (no window functions)

```sql
DECLARE @N INT = 3;
SELECT DISTINCT e1.Salary
FROM   dbo.Employees e1
WHERE  @N - 1 = (SELECT COUNT(DISTINCT e2.Salary)
                 FROM   dbo.Employees e2
                 WHERE  e2.Salary > e1.Salary);
-- 100000
```

Why it works: a salary is the Nth highest exactly when **N-1 distinct salaries are greater** than it. For 100000, the greater distinct values are 150000 and 120000: 2 = 3 - 1. It runs the subquery per row (O(n^2)), fine for an interview, slow on millions of rows.

#### Approach C: OFFSET with a variable

```sql
DECLARE @N INT = 4;
SELECT DISTINCT Salary
FROM   dbo.Employees
ORDER  BY Salary DESC
OFFSET @N - 1 ROWS FETCH NEXT 1 ROWS ONLY;
-- 95000
```

**Edge cases.** `@N` larger than the number of distinct salaries: all three return no rows. `@N <= 0`: OFFSET raises an error for negative values; validate input. Ties: all approaches work on *distinct* salaries.

As a reusable object, wrap approach A in an inline table-valued function `dbo.fn_NthHighestSalary(@N)` rather than a scalar UDF.

:::q Why DENSE_RANK and not RANK for Nth highest?
`RANK` leaves gaps after ties: salaries 150000, 120000, 120000, 100000 get ranks 1, 2, 2, 4, so asking for rank 3 returns nothing. `DENSE_RANK` gives 1, 2, 2, 3, so rank N is always the Nth distinct value.
:::

### 3. Find duplicate records

**Problem.** A customer import staging table received duplicate rows. List the duplicated customers and how many copies each has; also list every duplicate row with its id.

```sql
CREATE TABLE dbo.CustomerImport (
    ImportId INT IDENTITY(1,1) PRIMARY KEY,
    Name     NVARCHAR(50)  NOT NULL,
    Email    NVARCHAR(100) NOT NULL,
    City     NVARCHAR(50)  NULL
);
INSERT dbo.CustomerImport (Name, Email, City) VALUES
 (N'Alice', N'alice@example.com', N'Pune'),     -- 1
 (N'Bob',   N'bob@example.com',   N'Mumbai'),   -- 2
 (N'Alice', N'alice@example.com', N'Pune'),     -- 3
 (N'Carol', N'carol@example.com', N'Pune'),     -- 4
 (N'Bob',   N'bob@example.com',   N'Mumbai'),   -- 5
 (N'Alice', N'alice@example.com', N'Pune'),     -- 6
 (N'Dave',  N'dave@example.com',  NULL),        -- 7
 (N'Dave',  N'dave@example.com',  NULL);        -- 8
```

**Expected output (summary).**

| Name | Email | City | Copies |
|---|---|---|---|
| Alice | alice@example.com | Pune | 3 |
| Bob | bob@example.com | Mumbai | 2 |
| Dave | dave@example.com | NULL | 2 |

#### Approach A: GROUP BY ... HAVING

```sql
SELECT   Name, Email, City, COUNT(*) AS Copies
FROM     dbo.CustomerImport
GROUP BY Name, Email, City
HAVING   COUNT(*) > 1
ORDER BY Name;
```

`GROUP BY` puts identical rows into one group; `HAVING` keeps groups with more than one row. `GROUP BY` treats NULLs as equal, so the two Dave rows (City NULL) are correctly detected.

#### Approach B: COUNT(*) OVER (every duplicate row, with ids)

```sql
SELECT ImportId, Name, Email, City
FROM  (SELECT *, COUNT(*) OVER (PARTITION BY Name, Email, City) AS Copies
       FROM dbo.CustomerImport) x
WHERE  Copies > 1
ORDER  BY Name, ImportId;
-- 1, 3, 6 (Alice) | 2, 5 (Bob) | 7, 8 (Dave)
```

The window keeps the detail rows, which you need when someone asks "which rows exactly?"

:::warn Self-join trap with NULLs
`JOIN CustomerImport b ON a.Email = b.Email AND a.Name = b.Name AND a.City = b.City AND a.ImportId <> b.ImportId` returns ids 1, 2, 3, 5, 6 and **misses Dave** (7, 8), because `NULL = NULL` is not TRUE in a join. `GROUP BY` and `PARTITION BY` do not have this problem.
:::

**Edge cases.** Define "duplicate" first: all columns, or a business key such as `Email` only? Case and spaces: under a case-insensitive collation `Alice@x.com` and `alice@x.com` group together, but `' bob@x.com'` (leading space) does not; normalise with `LOWER(TRIM(Email))` if required (see bonus question 10).

### 4. Delete duplicate records

**Problem.** Remove duplicates from `CustomerImport`, keeping the **first** row (lowest `ImportId`) of each group.

**Expected result** (ids 3, 5, 6, 8 deleted):

| ImportId | Name | Email | City |
|---|---|---|---|
| 1 | Alice | alice@example.com | Pune |
| 2 | Bob | bob@example.com | Mumbai |
| 4 | Carol | carol@example.com | Pune |
| 7 | Dave | dave@example.com | NULL |

#### Approach A: CTE + ROW_NUMBER (the expected answer)

```sql
WITH d AS (
    SELECT ImportId,
           ROW_NUMBER() OVER (PARTITION BY Name, Email, City   -- what makes a duplicate
                              ORDER BY ImportId) AS rn          -- which one to keep
    FROM   dbo.CustomerImport
)
DELETE FROM d
OUTPUT deleted.ImportId                 -- audit what went: 3, 6, 5, 8
WHERE  rn > 1;
```

Why it works: within each duplicate group, the row to keep gets `rn = 1`; every other copy gets 2, 3, ... A CTE over a single table is updatable, so `DELETE FROM d` deletes the underlying rows. Change the `ORDER BY` to keep the latest instead (`ORDER BY ImportId DESC`, or `CreatedAt DESC`).

This also works on a table **with no key at all** (fully identical rows), which is the follow-up question interviewers love: `ROW_NUMBER() OVER (PARTITION BY <all columns> ORDER BY (SELECT NULL))`.

#### Approach B: keep MIN(id) per group

```sql
DELETE FROM dbo.CustomerImport
WHERE  ImportId NOT IN (SELECT MIN(ImportId)
                        FROM   dbo.CustomerImport
                        GROUP  BY Name, Email, City);
-- 4 rows remain
```

`NOT IN` is safe here because `MIN(ImportId)` of a non-null key is never NULL. Needs a unique key.

#### Approach C: EXISTS an earlier copy (business key only)

```sql
DELETE a
FROM   dbo.CustomerImport a
WHERE  EXISTS (SELECT 1 FROM dbo.CustomerImport b
               WHERE  b.Email = a.Email AND b.ImportId < a.ImportId);
-- keeps 1, 2, 4, 7
```

Easy to read when duplicates are defined by one non-null column. If the comparison columns are nullable, it misses NULL groups (same trap as the self-join).

**Production notes.** Run it inside a transaction and check the count, or `SELECT` the CTE first. On millions of rows delete in batches (`DELETE TOP (5000) FROM d WHERE rn > 1` in a loop). Afterwards add a `UNIQUE` constraint/index so duplicates cannot come back. Alternative for a huge mostly-duplicated table: `SELECT DISTINCT ... INTO` a new table and swap.

:::tip What interviewers prefer
CTE + `ROW_NUMBER()` + `DELETE WHERE rn > 1`. Explain `PARTITION BY` = definition of duplicate, `ORDER BY` = which one survives, and mention adding a unique constraint afterwards.
:::

### 5. Employees without a department

**Problem.** List employees not assigned to any department. Follow-up: list departments with no employees.

**Expected output.**

| EmployeeId | Name |
|---|---|
| 8 | Vikram |

Follow-up: `4 Finance`.

#### Approach A: IS NULL on the FK

```sql
SELECT EmployeeId, Name FROM dbo.Employees WHERE DepartmentId IS NULL;
```

Correct when a foreign key guarantees every non-null `DepartmentId` exists. Never write `= NULL` (always UNKNOWN, zero rows).

#### Approach B: LEFT JOIN anti-join (also catches orphans)

```sql
SELECT e.EmployeeId, e.Name
FROM   dbo.Employees e
LEFT JOIN dbo.Departments d ON d.DepartmentId = e.DepartmentId
WHERE  d.DepartmentId IS NULL;
-- 8 Vikram
```

This also finds employees pointing at a **department that no longer exists** (possible if there is no FK), which approach A misses.

#### Follow-up: departments with no employees

```sql
SELECT d.DepartmentId, d.DepartmentName
FROM   dbo.Departments d
WHERE  NOT EXISTS (SELECT 1 FROM dbo.Employees e WHERE e.DepartmentId = d.DepartmentId);
-- 4 Finance
```

:::warn The NOT IN version returns nothing
`WHERE DepartmentId NOT IN (SELECT DepartmentId FROM dbo.Employees)` returns **zero rows** because Vikram's NULL is in the list. This is the most common "spot the bug" question built on this data.
:::

### 6. Department-wise highest salary

**Problem.** For each department, show the highest salary; then show *who* earns it (all of them if tied).

**Expected output.**

| DepartmentName | Name | Salary |
|---|---|---|
| Engineering | Asha | 150000 |
| Sales | Tom | 100000 |
| HR | Nina | 65000 |

#### Approach A: GROUP BY (value only)

```sql
SELECT   d.DepartmentName, MAX(e.Salary) AS MaxSalary
FROM     dbo.Departments d
LEFT JOIN dbo.Employees e ON e.DepartmentId = d.DepartmentId
GROUP BY d.DepartmentName
ORDER BY MaxSalary DESC;
-- Engineering 150000 | Sales 100000 | HR 65000 | Finance NULL
```

You cannot just add `e.Name` to this query: `Name` is neither grouped nor aggregated (error 8120). That is the trap the follow-up is testing.

#### Approach B: join back to the per-department max

```sql
WITH m AS (
    SELECT DepartmentId, MAX(Salary) AS MaxSalary
    FROM   dbo.Employees GROUP BY DepartmentId
)
SELECT d.DepartmentName, e.Name, e.Salary
FROM   dbo.Employees e
JOIN   m ON m.DepartmentId = e.DepartmentId AND m.MaxSalary = e.Salary
JOIN   dbo.Departments d ON d.DepartmentId = e.DepartmentId
ORDER  BY e.Salary DESC;
```

#### Approach C: DENSE_RANK per partition

```sql
WITH r AS (
    SELECT e.DepartmentId, e.Name, e.Salary,
           DENSE_RANK() OVER (PARTITION BY e.DepartmentId ORDER BY e.Salary DESC) AS dr
    FROM   dbo.Employees e
)
SELECT d.DepartmentName, r.Name, r.Salary
FROM   r JOIN dbo.Departments d ON d.DepartmentId = r.DepartmentId
WHERE  r.dr = 1
ORDER  BY r.Salary DESC;
```

A correlated version (`WHERE e.Salary = (SELECT MAX(x.Salary) FROM Employees x WHERE x.DepartmentId = e.DepartmentId)`) gives the same three rows.

**Edge cases.** Ties at the top: B and C return all tied employees (use `ROW_NUMBER` if exactly one is required, with a tie-breaker). Empty departments: shown only with a `LEFT JOIN` from `Departments` (Finance, NULL). Employees without a department: excluded by the inner join to `Departments`; with `PARTITION BY` alone, Vikram would form his own NULL partition.

### 7. Top 3 salaries per department

**Problem.** For each department, list employees whose salary is among the top 3 **distinct** salaries of that department.

**Expected output** (`DENSE_RANK <= 3`):

| DepartmentName | Name | Salary | Rank |
|---|---|---|---|
| Engineering | Asha | 150000 | 1 |
| Engineering | Meena | 120000 | 2 |
| Engineering | Ravi | 120000 | 2 |
| Engineering | Kiran | 90000 | 3 |
| Sales | Tom | 100000 | 1 |
| Sales | Sana | 95000 | 2 |
| Sales | Omar | 70000 | 3 |
| Sales | Uma | 70000 | 3 |
| HR | Nina | 65000 | 1 |

Engineering and Sales return **4** rows each because of ties; HR returns 1 (fewer than 3 people is fine).

#### Approach A: DENSE_RANK (top 3 distinct salaries)

```sql
WITH r AS (
    SELECT e.DepartmentId, e.Name, e.Salary,
           DENSE_RANK() OVER (PARTITION BY e.DepartmentId ORDER BY e.Salary DESC) AS dr
    FROM   dbo.Employees e
    WHERE  e.DepartmentId IS NOT NULL
)
SELECT d.DepartmentName, r.Name, r.Salary, r.dr AS [Rank]
FROM   r JOIN dbo.Departments d ON d.DepartmentId = r.DepartmentId
WHERE  r.dr <= 3
ORDER  BY r.DepartmentId, r.Salary DESC, r.Name;
```

#### Approach B: ROW_NUMBER (exactly 3 people)

```sql
WITH r AS (
    SELECT DepartmentId, Name, Salary,
           ROW_NUMBER() OVER (PARTITION BY DepartmentId
                              ORDER BY Salary DESC, EmployeeId) AS rn
    FROM   dbo.Employees WHERE DepartmentId IS NOT NULL
)
SELECT DepartmentId, Name, Salary, rn FROM r WHERE rn <= 3;
-- 1: Asha, Ravi, Meena | 2: Tom, Sana, Uma (Omar cut by tie-breaker) | 3: Nina
```

#### Approach C: CROSS APPLY TOP (3) WITH TIES

```sql
SELECT d.DepartmentName, t.Name, t.Salary
FROM   dbo.Departments d
CROSS APPLY (SELECT TOP (3) WITH TIES e.Name, e.Salary
             FROM   dbo.Employees e
             WHERE  e.DepartmentId = d.DepartmentId
             ORDER  BY e.Salary DESC) t;
-- Engineering: Asha, Meena, Ravi | Sales: Tom, Sana, Omar, Uma | HR: Nina
```

Note the semantics: `TOP (3) WITH TIES` means "top 3 *rows*, plus anyone tied with the 3rd row". Engineering returns Asha, Meena, Ravi but **not** Kiran (the 3rd row is 120000). That is `RANK <= 3` semantics, different from `DENSE_RANK <= 3`. With an index on `(DepartmentId, Salary DESC)` this is very efficient: one small seek per department.

**Which one?** Ask: "top 3 salaries or top 3 people?" Distinct salary levels: `DENSE_RANK`. Exactly 3 people: `ROW_NUMBER` with a tie-breaker. Competition style: `RANK`/`WITH TIES`. Interviewers mostly expect `DENSE_RANK` with `PARTITION BY` and are impressed when you explain the difference.

### 8. Employees earning more than their manager

**Problem.** List employees whose salary is greater than their direct manager's salary.

**Expected output.**

| Employee | Salary | Manager | ManagerSalary |
|---|---|---|---|
| Tom | 100000 | Sana | 95000 |

#### Approach A: self join

```sql
SELECT e.Name AS Employee, e.Salary, m.Name AS Manager, m.Salary AS ManagerSalary
FROM   dbo.Employees e
JOIN   dbo.Employees m ON m.EmployeeId = e.ManagerId     -- m plays the "manager" role
WHERE  e.Salary > m.Salary;
```

Why it works: the same table is used twice with different aliases; the join pairs each employee row with its manager row, then we compare two columns of the combined row. The inner join naturally drops Asha (no manager).

#### Approach B: correlated subquery

```sql
SELECT e.Name
FROM   dbo.Employees e
WHERE  e.Salary > (SELECT m.Salary FROM dbo.Employees m WHERE m.EmployeeId = e.ManagerId);
-- Tom
```

For Asha the subquery returns NULL, `150000 > NULL` is UNKNOWN, so she is excluded.

**Variations** interviewers ask next: employees earning more than *any* manager above them (recursive CTE up the chain), managers with more than N direct reports (`GROUP BY ManagerId HAVING COUNT(*) > N`: Asha has 5, Sana 3), employees who are not managers (`NOT EXISTS` on `ManagerId`). Index `ManagerId` to make the self join cheap.

:::tip What interviewers prefer
The self join. Name the aliases by role (`e`, `m`), state that an inner join excludes the CEO, and say what you would change to include her (`LEFT JOIN` plus `OR m.EmployeeId IS NULL`, if the business wants it).
:::
