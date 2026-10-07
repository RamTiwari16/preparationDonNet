## Searching

**Definition.** Searching locates a target value (or its position) in a collection. *Linear search* checks items one by one; *binary search* repeatedly halves a **sorted** range.

**Why it matters.** Binary search is the most commonly mis-coded algorithm in interviews - off-by-one errors, infinite loops and integer overflow all hide in a dozen lines. Know one template cold.

| | Linear search | Binary search |
|---|---|---|
| Requires sorted data | No | Yes (or any monotonic predicate) |
| Time | O(n) | O(log n) |
| Works on linked lists | Yes | Not usefully (no O(1) random access) |
| .NET | `Array.IndexOf`, `List<T>.IndexOf`, `Contains`, LINQ `FirstOrDefault` | `Array.BinarySearch`, `List<T>.BinarySearch` |

### Linear search

```csharp
// O(n) time, O(1) space. Returns the index or -1.
static int LinearSearch(int[] a, int target)
{
    for (int i = 0; i < a.Length; i++)
        if (a[i] == target) return i;
    return -1;
}
// Prefer a HashSet/Dictionary if you search the same data many times.
```

**Edge cases.** Empty array, target absent, duplicates (first vs last occurrence), `null` elements for reference types (use `Equals`).

### Binary search

**Problem.** Given a sorted array and a target, return its index or `-1`.

**Example.** `[1, 3, 5, 7, 9, 11]`, target `7` returns `3`; target `4` returns `-1`.

**Intuition.** Compare the target with the middle element. If equal, done; if the target is smaller it can only be in the left half, otherwise in the right half. Each step discards half the range, so at most `log2(n) + 1` steps.

**Approach.**
1. `lo = 0`, `hi = n - 1` (inclusive range).
2. While `lo <= hi`: `mid = lo + (hi - lo) / 2`.
3. `a[mid] == target` return `mid`; `a[mid] < target` set `lo = mid + 1`; else `hi = mid - 1`.
4. Range empty: return `-1`.

```csharp
// Iterative: O(log n) time, O(1) space.
static int BinarySearch(int[] a, int target)
{
    int lo = 0, hi = a.Length - 1;
    while (lo <= hi)
    {
        int mid = lo + (hi - lo) / 2;          // NOT (lo + hi) / 2 - see the warning
        if (a[mid] == target) return mid;
        if (a[mid] < target) lo = mid + 1;
        else hi = mid - 1;
    }
    return -1;
}

// Recursive: same O(log n) time, O(log n) call stack.
static int BinarySearchRecursive(int[] a, int target, int lo, int hi)
{
    if (lo > hi) return -1;
    int mid = lo + (hi - lo) / 2;
    if (a[mid] == target) return mid;
    return a[mid] < target
        ? BinarySearchRecursive(a, target, mid + 1, hi)
        : BinarySearchRecursive(a, target, lo, mid - 1);
}

// Lower bound: first index i with a[i] >= target (a.Length if none).
// This is the template that solves "first occurrence", "insert position", "count".
static int LowerBound(int[] a, int target)
{
    int lo = 0, hi = a.Length;                 // half-open range [lo, hi)
    while (lo < hi)
    {
        int mid = lo + (hi - lo) / 2;
        if (a[mid] < target) lo = mid + 1;
        else hi = mid;                         // keep mid: it might be the answer
    }
    return lo;
}

// Upper bound: first index i with a[i] > target.
static int UpperBound(int[] a, int target)
{
    int lo = 0, hi = a.Length;
    while (lo < hi)
    {
        int mid = lo + (hi - lo) / 2;
        if (a[mid] <= target) lo = mid + 1;
        else hi = mid;
    }
    return lo;
}

static int CountOccurrences(int[] a, int target) => UpperBound(a, target) - LowerBound(a, target);
// LowerBound([1, 2, 2, 2, 5], 2) -> 1   UpperBound(..., 2) -> 4   CountOccurrences -> 3
// LowerBound([1, 2, 2, 2, 5], 3) -> 4 (where 3 would be inserted)
```

**Complexity.** O(log n) time; iterative O(1) space.

**Edge cases.** Empty array, one element, target smaller than all or larger than all, duplicates (which index is returned?), arrays of length 2 (checks the `mid` calculation), `int.MaxValue`-sized ranges (overflow).

:::warn The famous overflow bug
`(lo + hi) / 2` overflows `int` when `lo + hi` exceeds `int.MaxValue` (arrays with more than about a billion elements) and yields a negative index. Java's `Arrays.binarySearch` shipped with this bug for years. Always write `lo + (hi - lo) / 2`. Other classic bugs: using `lo < hi` with inclusive bounds (misses the last element), `lo = mid` instead of `mid + 1` (infinite loop), and calling it on unsorted data.
:::

#### Binary search on the answer

**Intuition.** You can binary search anything with a *monotonic* yes/no property - not just arrays. Find the smallest `x` such that `feasible(x)` is true, where feasibility flips from false to true exactly once. Examples: integer square root, minimum shipping capacity, "koko eating bananas".

```csharp
// Floor of the square root without Math.Sqrt. O(log x) time, O(1) space.
static int IntegerSqrt(int x)
{
    int lo = 0, hi = x, answer = 0;
    while (lo <= hi)
    {
        int mid = lo + (hi - lo) / 2;
        if ((long)mid * mid <= x) { answer = mid; lo = mid + 1; }   // long avoids overflow
        else hi = mid - 1;
    }
    return answer;
}
// IntegerSqrt(8) -> 2     IntegerSqrt(2147395599) -> 46339

// Using the framework: a negative result is the bitwise complement of the insert position.
static int FrameworkSearch(int[] sorted, int target)
{
    int i = Array.BinarySearch(sorted, target);
    return i >= 0 ? i : ~i;                     // index if found, else insertion point
}
```

:::q Follow-up: search in a rotated sorted array (e.g. [4,5,6,7,0,1,2])?
Still O(log n). At each step at least one half of `[lo, mid]` or `[mid, hi]` is sorted. Check which half is sorted by comparing `a[lo]` with `a[mid]`, test whether the target lies inside that sorted half, and discard the other half. Duplicates can degrade it to O(n) in the worst case.
:::

:::q Why must the input be sorted, and what if it is not?
The halving step is only valid because order lets you rule out an entire half. On unsorted data either sort first (O(n log n), worthwhile when you will search many times) or use a hash set for O(1) lookup, or fall back to linear search.
:::

## Dynamic Programming

**Definition.** Dynamic programming (DP) solves a problem by combining solutions of *overlapping subproblems*, storing each result so it is computed once. It applies when the problem has **optimal substructure** (the best answer is built from best answers to smaller problems) and **overlapping subproblems** (the same smaller problem recurs).

**Why it matters.** "Minimum / maximum / number of ways / is it possible" over choices is the DP signal. DP converts exponential recursion into polynomial time.

#### A 5-step recipe

1. Define the **state**: what does `dp[i]` (or `dp[i][j]`) mean, in one sentence?
2. Write the **recurrence**: how does a state depend on smaller states?
3. Set the **base cases**.
4. Choose the **order** of evaluation (top-down memoisation or bottom-up tabulation).
5. Identify the **answer** cell and whether you can shrink the table (rolling array).

| | Top-down (memoisation) | Bottom-up (tabulation) |
|---|---|---|
| Style | recursion + cache | loops filling a table |
| Computes | only the needed states | all states |
| Risk | recursion depth / stack overflow | none; must get the order right |
| Space optimisation | harder | easy (rolling array) |

### Fibonacci: recursion to O(1) space

**Problem.** `F(0) = 0`, `F(1) = 1`, `F(n) = F(n-1) + F(n-2)`. Return `F(n)`.

**Example.** `F(10) = 55`; the sequence is `0, 1, 1, 2, 3, 5, 8, 13, ...`.

**Intuition.** The naive recursion recomputes the same values exponentially often (`F(n-2)` is computed inside both `F(n)` and `F(n-1)`). Cache results (memoisation), or build from the bottom (tabulation); finally notice that only the last two values are ever needed.

```csharp
// 1. Plain recursion: O(2^n) time, O(n) stack. Unusable beyond n ~ 40.
static long FibNaive(int n) => n < 2 ? n : FibNaive(n - 1) + FibNaive(n - 2);

// 2. Memoisation (top-down): O(n) time, O(n) space.
static long FibMemo(int n, Dictionary<int, long>? memo = null)
{
    memo ??= new Dictionary<int, long>();
    if (n < 2) return n;
    if (memo.TryGetValue(n, out long cached)) return cached;
    return memo[n] = FibMemo(n - 1, memo) + FibMemo(n - 2, memo);
}

// 3. Tabulation (bottom-up): O(n) time, O(n) space.
static long FibTable(int n)
{
    if (n < 2) return n;
    var dp = new long[n + 1];
    dp[1] = 1;
    for (int i = 2; i <= n; i++) dp[i] = dp[i - 1] + dp[i - 2];
    return dp[n];
}

// 4. Two variables: O(n) time, O(1) space.
static long FibConstantSpace(int n)
{
    if (n < 2) return n;
    long prev = 0, cur = 1;
    for (int i = 2; i <= n; i++)
        (prev, cur) = (cur, prev + cur);
    return cur;
}
// FibConstantSpace(10) -> 55    FibConstantSpace(92) -> 7540113804746346429 (last fit in long)
```

**Complexity.**

| Version | Time | Space |
|---|---|---|
| Naive recursion | O(2^n) | O(n) |
| Memoisation | O(n) | O(n) |
| Tabulation | O(n) | O(n) |
| Rolling variables | O(n) | O(1) |

**Edge cases.** `n = 0` and `n = 1`, negative `n` (reject), overflow: `F(93)` exceeds `long` - use `System.Numerics.BigInteger` for larger values.

:::q Follow-up: can Fibonacci be computed faster than O(n)?
Yes, in O(log n) with matrix exponentiation (`[[1,1],[1,0]]^n`) or the fast-doubling identities. Mention it, but also say that for `n` up to a few thousand the O(n) loop with `BigInteger` is the practical answer.
:::

### Climbing stairs

**Problem.** You can climb 1 or 2 steps at a time. How many distinct ways reach step `n`?

**Example.** `n = 3` gives `3` (1+1+1, 1+2, 2+1). `n = 5` gives `8`.

**Intuition.** The last move was either from step `n-1` (a 1-step) or `n-2` (a 2-step), so `ways(n) = ways(n-1) + ways(n-2)` - Fibonacci in disguise. Generalise by summing over a set of allowed step sizes.

```csharp
// O(n) time, O(1) space.
static int ClimbStairs(int n)
{
    if (n <= 2) return n;
    int a = 1, b = 2;                 // ways to reach step 1 and step 2
    for (int i = 3; i <= n; i++)
        (a, b) = (b, a + b);
    return b;
}

// Any allowed step sizes (e.g. 1, 2, 3): O(n * k) time, O(n) space.
static long ClimbStairsSteps(int n, int[] steps)
{
    var dp = new long[n + 1];
    dp[0] = 1;                                   // one way to stand at the start
    for (int i = 1; i <= n; i++)
        foreach (int s in steps)
            if (i >= s) dp[i] += dp[i - s];
    return dp[n];
}
// ClimbStairsSteps(4, new[] { 1, 2, 3 }) -> 7
```

**Edge cases.** `n = 0` or `1`, huge `n` overflow (`ClimbStairs(45)` = 1,836,311,903 is the last value that fits in `int`).

:::q Follow-up: each step has a cost - find the cheapest way to reach the top.
Let `dp[i] = cost[i] + min(dp[i-1], dp[i-2])` and the answer is `min(dp[n-1], dp[n-2])`. Same recurrence shape, `min` instead of `+`. It also reduces to two rolling variables.
:::

### 0/1 Knapsack

**Problem.** Items have a weight and a value; the bag holds at most `capacity` weight. Pick each item at most once to maximise total value.

**Example.** Weights `[1, 3, 4, 5]`, values `[1, 4, 5, 7]`, capacity `7` gives `9` (items with weights 3 and 4).

**Intuition.** For each item there are two choices: skip it or take it. Let `dp[i][w]` be the best value using the first `i` items with capacity `w`. Skipping gives `dp[i-1][w]`; taking (if it fits) gives `value[i] + dp[i-1][w - weight[i]]`. Take the larger.

**Approach.**
1. Table `(n+1) x (capacity+1)`, row 0 and column 0 are 0.
2. Fill row by row with the recurrence.
3. The answer is `dp[n][capacity]`.
4. To list the chosen items, walk backwards from `(n, capacity)`: if `dp[i][w] != dp[i-1][w]`, item `i` was taken - subtract its weight.

```csharp
// Brute force: try every subset by recursion. O(2^n) time.
static int KnapsackRecursive(int[] weights, int[] values, int capacity, int i = 0)
{
    if (i == weights.Length) return 0;
    int skip = KnapsackRecursive(weights, values, capacity, i + 1);
    if (weights[i] > capacity) return skip;
    int take = values[i] + KnapsackRecursive(weights, values, capacity - weights[i], i + 1);
    return Math.Max(skip, take);
}

// Table: O(n * W) time, O(n * W) space. Also returns the chosen item indices.
static (int Best, List<int> Items) Knapsack(int[] weights, int[] values, int capacity)
{
    int n = weights.Length;
    var dp = new int[n + 1, capacity + 1];
    for (int i = 1; i <= n; i++)
    {
        for (int w = 0; w <= capacity; w++)
        {
            dp[i, w] = dp[i - 1, w];                                    // skip item i-1
            if (weights[i - 1] <= w)
                dp[i, w] = Math.Max(dp[i, w],
                    dp[i - 1, w - weights[i - 1]] + values[i - 1]);     // take item i-1
        }
    }

    var items = new List<int>();
    for (int i = n, w = capacity; i > 0; i--)
    {
        if (dp[i, w] != dp[i - 1, w])           // value changed, so item i-1 was taken
        {
            items.Add(i - 1);
            w -= weights[i - 1];
        }
    }
    items.Reverse();
    return (dp[n, capacity], items);
}

// Space optimised: one row. Iterate capacity DOWNWARDS so each item is used once.
static int KnapsackOneRow(int[] weights, int[] values, int capacity)
{
    var dp = new int[capacity + 1];
    for (int i = 0; i < weights.Length; i++)
        for (int w = capacity; w >= weights[i]; w--)
            dp[w] = Math.Max(dp[w], dp[w - weights[i]] + values[i]);
    return dp[capacity];
}
// Knapsack(new[] {1, 3, 4, 5}, new[] {1, 4, 5, 7}, 7) -> (9, items [1, 2])
```

**Complexity.**

| Version | Time | Space |
|---|---|---|
| Recursion | O(2^n) | O(n) |
| 2D table | O(n * W) | O(n * W) |
| 1D row | O(n * W) | O(W) |

`O(n * W)` is *pseudo-polynomial*: it is polynomial in the numeric value of `W`, not in its bit length.

**Edge cases.** Zero capacity, an item heavier than the capacity, zero-weight items, no items.

:::warn Iterating capacity upwards in the 1D version
Looping `w` upward lets the same item be reused several times - that solves the *unbounded* knapsack, not 0/1. For 0/1 the inner loop must run from `capacity` down to `weight`.
:::

### Longest common subsequence (LCS)

**Problem.** Return the length (and one example) of the longest subsequence common to two strings. A subsequence keeps relative order but need not be contiguous.

**Example.** `"ABCBDAB"` and `"BDCABA"` have LCS length `4` (for example `"BCBA"`).

**Intuition.** Let `dp[i][j]` be the LCS length of the first `i` characters of `a` and the first `j` of `b`. If the characters match, extend the diagonal: `dp[i-1][j-1] + 1`. Otherwise drop one character from either string: `max(dp[i-1][j], dp[i][j-1])`.

```csharp
// O(m * n) time, O(m * n) space.
static int LcsLength(string a, string b)
{
    var dp = new int[a.Length + 1, b.Length + 1];
    for (int i = 1; i <= a.Length; i++)
        for (int j = 1; j <= b.Length; j++)
            dp[i, j] = a[i - 1] == b[j - 1]
                ? dp[i - 1, j - 1] + 1
                : Math.Max(dp[i - 1, j], dp[i, j - 1]);
    return dp[a.Length, b.Length];
}

// Reconstruction: walk back from the bottom-right corner.
static string Lcs(string a, string b)
{
    var dp = new int[a.Length + 1, b.Length + 1];
    for (int i = 1; i <= a.Length; i++)
        for (int j = 1; j <= b.Length; j++)
            dp[i, j] = a[i - 1] == b[j - 1]
                ? dp[i - 1, j - 1] + 1
                : Math.Max(dp[i - 1, j], dp[i, j - 1]);

    var sb = new StringBuilder();
    int x = a.Length, y = b.Length;
    while (x > 0 && y > 0)
    {
        if (a[x - 1] == b[y - 1]) { sb.Append(a[x - 1]); x--; y--; }   // part of the LCS
        else if (dp[x - 1, y] >= dp[x, y - 1]) x--;      // follow the larger neighbour
        else y--;
    }
    var chars = sb.ToString().ToCharArray();
    Array.Reverse(chars);
    return new string(chars);
}

// Length only with two rows: O(m * n) time, O(min(m, n)) space.
static int LcsLengthTwoRows(string a, string b)
{
    if (b.Length > a.Length) (a, b) = (b, a);          // make b the shorter string
    var prev = new int[b.Length + 1];
    var cur = new int[b.Length + 1];
    for (int i = 1; i <= a.Length; i++)
    {
        for (int j = 1; j <= b.Length; j++)
            cur[j] = a[i - 1] == b[j - 1] ? prev[j - 1] + 1 : Math.Max(prev[j], cur[j - 1]);
        (prev, cur) = (cur, prev);
    }
    return prev[b.Length];
}
```

**Complexity.** O(m * n) time; the full table is O(m * n) space, two rows give O(min(m, n)) but lose the ability to reconstruct the string.

**Edge cases.** Empty string (LCS 0), identical strings (full length), no common characters, several equally long answers (return any).

:::q Follow-up: how are LCS, edit distance and longest increasing subsequence related?
All are 2D (or 1D) DP over prefixes. Edit distance uses the same table with `1 + min(insert, delete, replace)` when characters differ. Longest increasing subsequence is O(n^2) with `dp[i]` = best ending at `i`, or O(n log n) with a patience-sorting array and binary search. LCS of a string with its reverse gives the longest palindromic subsequence.
:::

### Coin change

**Problem A (minimum coins).** Given coin denominations (unlimited supply) and an amount, find the fewest coins that sum to it, or `-1`.

**Problem B (number of ways).** Count the distinct combinations of coins that make the amount.

**Example.** `coins = [1, 2, 5]`, `amount = 11` gives min coins `3` (5+5+1). `coins = [1, 2, 5]`, `amount = 5` gives `4` ways (5; 2+2+1; 2+1+1+1; 1x5).

**Intuition (A).** `dp[a]` is the fewest coins for amount `a`: try every coin `c` as the *last* coin, `dp[a] = 1 + min(dp[a - c])`. **Intuition (B).** `dp[a]` counts combinations. Process coins one at a time (coins in the *outer* loop) so each combination is counted once regardless of order; putting amounts in the outer loop would count permutations (1+2 and 2+1 as different).

```csharp
// Top-down memoisation: O(amount * coins) time, O(amount) space.
static int CoinChangeMemo(int[] coins, int amount)
{
    var memo = new int[amount + 1];            // 0 = not computed yet, -1 = impossible
    int Solve(int remaining)
    {
        if (remaining == 0) return 0;
        if (remaining < 0) return -1;
        if (memo[remaining] != 0) return memo[remaining];
        int best = int.MaxValue;
        foreach (int c in coins)
        {
            int sub = Solve(remaining - c);
            if (sub >= 0) best = Math.Min(best, sub + 1);
        }
        return memo[remaining] = best == int.MaxValue ? -1 : best;
    }
    return Solve(amount);
}

// Bottom-up minimum coins: O(amount * coins) time, O(amount) space.
static int CoinChangeMin(int[] coins, int amount)
{
    var dp = new int[amount + 1];
    Array.Fill(dp, amount + 1);                // "infinity": more coins than can ever be needed
    dp[0] = 0;
    for (int a = 1; a <= amount; a++)
        foreach (int c in coins)
            if (c <= a) dp[a] = Math.Min(dp[a], dp[a - c] + 1);
    return dp[amount] > amount ? -1 : dp[amount];
}

// Number of combinations: coins in the OUTER loop.
static long CoinChangeWays(int[] coins, int amount)
{
    var dp = new long[amount + 1];
    dp[0] = 1;                                 // one way to make 0: take nothing
    foreach (int c in coins)
        for (int a = c; a <= amount; a++)
            dp[a] += dp[a - c];
    return dp[amount];
}
// CoinChangeMin(new[] {1, 2, 5}, 11) -> 3      CoinChangeMin(new[] {2}, 3) -> -1
// CoinChangeWays(new[] {1, 2, 5}, 5) -> 4
```

**Complexity.** O(amount * coins) time, O(amount) space for all three.

**Edge cases.** Amount `0` (0 coins, 1 way), impossible amount (`-1`), coin larger than the amount, unsorted coins, `dp[amount]` overflow for ways (use `long`).

:::warn Greedy fails for general coin systems
With coins `{1, 3, 4}` and amount `6`, greedy picks `4+1+1` (3 coins) but `3+3` uses 2. Greedy is only correct for special systems (such as 1, 5, 10, 25). When asked "minimum coins" for arbitrary denominations, answer with DP and mention why greedy breaks.
:::
