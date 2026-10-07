## How to Approach a Coding Round

Every snippet in this section assumes the default .NET 8 console-project usings (`System`, `System.Collections.Generic`, `System.Linq`) plus `using System.Text;`. Methods are written as `static` members so you can drop them into any `static class` or use them as local functions in top-level statements. All code was compiled and run against assertions before it was written down here.

### The 7-step framework

**Definition.** A coding round tests how you think, not whether you have memorised the answer. Interviewers score *communication, correctness, complexity awareness and testing* — in that order of importance for 2-5 years experience.

```text
1. Clarify      -> restate the problem, ask about input size, duplicates, empty input, negatives
2. Examples     -> write 1 normal case + 2 edge cases (empty, single element, all same)
3. Brute force  -> say the obvious O(n^2) / O(n^3) solution out loud, with its complexity
4. Optimise     -> find the bottleneck, name a pattern (hashing, two pointers, ...)
5. Code         -> clean names, small helper methods, no clever one-liners you can't explain
6. Test         -> dry-run your own code on the examples line by line
7. Complexity   -> state time AND space, and what you would do for bigger inputs
```

:::tip What interviewers actually look for
They do not expect the optimal solution in 5 minutes. They expect you to (a) ask good questions, (b) reach a correct brute force, (c) improve it with a reason, and (d) catch your own bugs by dry-running. A candidate who writes a correct O(n^2) and explains how to reach O(n) usually beats one who silently writes a buggy O(n).
:::

#### Questions to ask before writing code

- Can the input be `null` or empty? What should I return - `null`, empty array, `-1`, or throw?
- Are values bounded? Can they be negative? Can they overflow `int` (use `long` for sums)?
- Can there be duplicates? Is the input already sorted?
- Is it case-sensitive? ASCII only or full Unicode?
- Should I modify the input in place, or is extra memory allowed?
- How large is `n`? (This decides which complexity is acceptable.)

#### Input size tells you the target complexity

| n (max) | Acceptable complexity | Typical technique |
|---|---|---|
| up to 10-12 | O(n!) | permutations, backtracking |
| up to 20-25 | O(2^n) | subsets, bitmask |
| up to 500 | O(n^3) | triple loops, Floyd-Warshall |
| up to 5,000 | O(n^2) | nested loops, 2D DP |
| up to 1,000,000 | O(n log n) | sort, heap, divide and conquer |
| 10^7 and above | O(n) or O(log n) | hashing, two pointers, binary search, math |

#### Big-O of common .NET collections

| Collection | Access by index/key | Search | Add | Remove | Notes |
|---|---|---|---|---|---|
| `T[]` | O(1) | O(n); O(log n) if sorted + `Array.BinarySearch` | fixed size | O(n) shift | contiguous, cache friendly |
| `List<T>` | O(1) | O(n) | O(1) amortised at end; O(n) in the middle | O(n) (O(1) for last) | doubles capacity when full |
| `LinkedList<T>` | O(n) | O(n) | O(1) at a known node / ends | O(1) at a known node | poor cache locality; rarely best |
| `Dictionary<K,V>` | O(1) average | O(1) average | O(1) amortised | O(1) | worst case O(n) with bad hashes |
| `HashSet<T>` | n/a | O(1) average | O(1) amortised | O(1) | `Add` returns `false` if present |
| `SortedDictionary<K,V>` | O(log n) | O(log n) | O(log n) | O(log n) | red-black tree, ordered keys |
| `SortedSet<T>` | n/a | O(log n) | O(log n) | O(log n) | `Min`, `Max`, `GetViewBetween` |
| `SortedList<K,V>` | O(log n) | O(log n) | O(n) (array shift) | O(n) | less memory than `SortedDictionary` |
| `Stack<T>` | `Peek` O(1) | O(n) | `Push` O(1) amortised | `Pop` O(1) | array backed |
| `Queue<T>` | `Peek` O(1) | O(n) | `Enqueue` O(1) amortised | `Dequeue` O(1) | circular array |
| `PriorityQueue<TElem,TPrio>` | `Peek` O(1) | n/a | `Enqueue` O(log n) | `Dequeue` O(log n) | binary/d-ary min-heap; no cheap decrease-key |
| `string` | index O(1) | `Contains` O(n*m) worst | `+` creates a new string O(n) | n/a | immutable |
| `StringBuilder` | O(1) amortised append | n/a | `Append` O(1) amortised | n/a | use inside loops |

:::warn String concatenation in a loop
`s += c` inside a loop copies the whole string every time - O(n^2) overall. Use `StringBuilder` or collect `char`s in an array and call `new string(chars)`.
:::

### Pattern cheat-sheet

**Why it matters.** Most interview problems are a known pattern in disguise. Name the pattern out loud - it signals experience.

| Signal in the problem statement | Pattern | Typical complexity |
|---|---|---|
| Sorted array, pair/triple with a target, palindrome, in-place compaction | **Two pointers** | O(n) |
| Contiguous subarray/substring, "longest / shortest / at most K" | **Sliding window** | O(n) |
| "Have I seen this?", count occurrences, complement lookup, grouping | **Hashing** (`Dictionary`, `HashSet`) | O(n) |
| Cycle in a linked list, middle node, k-th from end | **Fast/slow pointers** | O(n), O(1) space |
| Matching brackets, undo, nested structure, evaluate expression | **Stack** | O(n) |
| "Next greater / smaller element", stock span, histogram | **Monotonic stack** | O(n) |
| Shortest path in unweighted graph/grid, level by level, minimum steps | **BFS** | O(V+E) |
| Explore all paths, connected components, tree recursion, permutations | **DFS / backtracking** | O(V+E) / exponential |
| "Minimum / maximum / number of ways", overlapping subproblems | **Dynamic programming** | O(states x transitions) |
| Sorted data or a monotonic yes/no predicate, "smallest x such that..." | **Binary search (on index or on answer)** | O(log n) x check |
| Top K, running median, merge K sorted lists | **Heap / `PriorityQueue`** | O(n log k) |
| Intervals, meeting rooms, scheduling | **Sort + sweep** (often greedy) | O(n log n) |
| Subarray sum queries, "sum equals K" | **Prefix sums + hashing** | O(n) |
| Locally optimal choice is provably globally optimal | **Greedy** | O(n log n) |

## Arrays & Strings

The most common warm-up group. Master the two-pointer idiom: `l` and `r` walking inwards, or `read` and `write` walking in the same direction.

### Reverse an array in place

**Problem.** Reverse the elements of an `int[]` without allocating a second array.

**Example.** `[1, 2, 3, 4, 5]` becomes `[5, 4, 3, 2, 1]`.

**Intuition.** The first and last elements must swap, then the second and second-last, and so on. Stop when the pointers meet - the middle element of an odd-length array stays.

**Approach.**
1. Put `l` at index 0 and `r` at the last index.
2. While `l < r`: swap `a[l]` and `a[r]`, then `l++`, `r--`.
3. Done after `n / 2` swaps.

```csharp
// Brute force: allocate a copy. O(n) time, O(n) extra space.
static int[] ReverseCopy(int[] a)
{
    var result = new int[a.Length];
    for (int i = 0; i < a.Length; i++)
        result[a.Length - 1 - i] = a[i];
    return result;
}

// Optimal: two pointers, tuple swap. O(n) time, O(1) extra space.
static void ReverseInPlace(int[] a)
{
    int l = 0, r = a.Length - 1;
    while (l < r)
    {
        (a[l], a[r]) = (a[r], a[l]);
        l++;
        r--;
    }
}
// ReverseInPlace(new[] { 1, 2, 3, 4, 5 }) -> [5, 4, 3, 2, 1]
// The framework call Array.Reverse(a) does exactly this.
```

**Complexity.** Time O(n), space O(1) (the copy version is O(n) space).

**Edge cases.** Empty array, single element, even vs odd length, `null` input (throw `ArgumentNullException` or return).

:::q Follow-up: how do you rotate an array by k positions in O(1) extra space?
Use three reversals: reverse the whole array, then reverse the first `k % n` elements, then reverse the rest. Each reversal is the in-place routine above, so total time is O(n) and space O(1). Example: `[1,2,3,4,5]`, k=2 right-rotation -> reverse all `[5,4,3,2,1]` -> reverse first 2 `[4,5,3,2,1]` -> reverse rest `[4,5,1,2,3]`.
:::

### Reverse a string

**Problem.** Return the reverse of a string. Strings are immutable in C#, so you cannot swap characters in place.

**Example.** `"hello"` becomes `"olleh"`.

**Intuition.** Copy to a mutable `char[]`, run the same two-pointer swap, build a new string. The interviewer usually bans `Reverse()` to see whether you know the idiom.

**Approach.**
1. `ToCharArray()` to get a mutable copy.
2. Two-pointer swap.
3. `new string(chars)`.

```csharp
static string ReverseString(string s)
{
    char[] chars = s.ToCharArray();
    int l = 0, r = chars.Length - 1;
    while (l < r)
    {
        (chars[l], chars[r]) = (chars[r], chars[l]);
        l++;
        r--;
    }
    return new string(chars);
}

// Allocation-friendly version for hot paths: reverse directly inside the new string.
static string ReverseWithSpan(string s) =>
    string.Create(s.Length, s, (span, src) =>
    {
        src.AsSpan().CopyTo(span);
        span.Reverse();
    });

// Reverse the order of words, not the letters.
static string ReverseWords(string s)
{
    string[] words = s.Split(' ', StringSplitOptions.RemoveEmptyEntries);
    Array.Reverse(words);
    return string.Join(" ", words);
}
// ReverseWords("  the sky  is blue ") -> "blue is sky the"
```

**Complexity.** Time O(n), space O(n) (a new string is unavoidable because strings are immutable).

**Edge cases.** Empty string, single character, spaces, surrogate pairs (emoji).

:::warn Reversing UTF-16 code units can corrupt text
A `char` is a UTF-16 code unit, not a user-perceived character. Emoji and many scripts use *surrogate pairs* or combining marks, so reversing `char`s breaks them. For real text use `System.Globalization.StringInfo` / `EnumerateRunes()`. In an interview, mention it in one sentence and move on.
:::

:::q Follow-up: why is `string` reversal O(n) space even with two pointers?
Because `string` is immutable - `s[i] = 'x'` does not compile. Any "in place" claim needs a mutable buffer (`char[]`, `Span<char>`, `StringBuilder`). The two-pointer swap is in place *on the buffer*, but producing the final `string` allocates.
:::

### Find duplicate elements

**Problem.** Return the values that appear more than once in an array.

**Example.** `[4, 3, 2, 7, 8, 2, 3, 1]` returns `[2, 3]` (order not important).

**Intuition.** You need "have I seen this before?" in O(1). A `HashSet<T>` answers that, and `Add` already tells you whether the item was new.

**Approach.**
1. Keep `seen` (all values so far) and `dups` (values seen at least twice).
2. For each `x`: if `seen.Add(x)` returns `false`, put `x` in `dups`.
3. Alternative without extra structures: sort, then compare neighbours.

```csharp
// Brute force: compare every pair. O(n^2) time, O(1) extra space.
static List<int> FindDuplicatesBrute(int[] a)
{
    var result = new List<int>();
    for (int i = 0; i < a.Length; i++)
        for (int j = i + 1; j < a.Length; j++)
            if (a[i] == a[j] && !result.Contains(a[i]))
                result.Add(a[i]);
    return result;
}

// Optimal: HashSet. O(n) time, O(n) space.
static List<int> FindDuplicates(int[] a)
{
    var seen = new HashSet<int>();
    var dups = new HashSet<int>();
    foreach (int x in a)
        if (!seen.Add(x))      // Add returns false when the item already exists
            dups.Add(x);
    return dups.ToList();
}

// LINQ: readable, still O(n) but allocates groups.
static List<int> FindDuplicatesLinq(int[] a) =>
    a.GroupBy(x => x).Where(g => g.Count() > 1).Select(g => g.Key).ToList();

// Sort first: O(n log n) time, O(n) for the copy (O(1) if you may mutate the input).
static List<int> FindDuplicatesSorted(int[] a)
{
    int[] copy = (int[])a.Clone();
    Array.Sort(copy);
    var result = new List<int>();
    for (int i = 1; i < copy.Length; i++)
        if (copy[i] == copy[i - 1] && (result.Count == 0 || result[^1] != copy[i]))
            result.Add(copy[i]);
    return result;
}

// Quick yes/no check.
static bool HasDuplicate(int[] a) => new HashSet<int>(a).Count != a.Length;
```

**Complexity.**

| Approach | Time | Space |
|---|---|---|
| Nested loops | O(n^2) | O(1) |
| Sort + neighbours | O(n log n) | O(1)-O(n) |
| HashSet | O(n) | O(n) |

**Edge cases.** Empty array, no duplicates, one value repeated many times (report it once), negatives.

:::q Follow-up: values are in 1..n, one is duplicated, and you may not use extra space. How?
Treat the array as a linked list where `i -> a[i]`. A duplicate means two indices point to the same node, which creates a cycle; Floyd's tortoise and hare finds the cycle entry in O(n) time and O(1) space without modifying the array (see *Find the cycle start* in the Linked List group). A simpler variant that may mutate the input: negate `a[|x|-1]` as you visit `x`; seeing an already-negative cell means `x` is a duplicate.
:::

### Find the missing number

**Problem.** An array of length `n` holds distinct numbers from `0..n` with exactly one missing. Find it.

**Example.** `[3, 0, 1]` returns `2`. `[9,6,4,2,3,5,7,0,1]` returns `8`.

**Intuition.** Two ways to "cancel out" everything that is present. Sum: expected total `n(n+1)/2` minus actual total. XOR: `x ^ x = 0`, so XOR-ing all indices and all values leaves only the missing one - and it cannot overflow.

**Approach (sum).** Compute `expected = n*(n+1)/2` in `long`, subtract the array's sum.
**Approach (XOR).** Start with `n`, XOR in every `i` and `a[i]`.

```csharp
// Brute force: for every candidate check membership. O(n^2) time, O(1) space.
static int MissingBrute(int[] a)
{
    for (int candidate = 0; candidate <= a.Length; candidate++)
        if (Array.IndexOf(a, candidate) < 0) return candidate;
    return -1;
}

// Sum formula. O(n) time, O(1) space. Use long to avoid overflow for large n.
static int MissingBySum(int[] a)
{
    long n = a.Length;
    long expected = n * (n + 1) / 2;
    long actual = 0;
    foreach (int x in a) actual += x;
    return (int)(expected - actual);
}

// XOR: no overflow possible. O(n) time, O(1) space.
static int MissingByXor(int[] a)
{
    int xor = a.Length;                 // the value n is never an index
    for (int i = 0; i < a.Length; i++)
        xor ^= i ^ a[i];
    return xor;
}

// Variant: array of n-1 numbers taken from 1..n.
static int MissingFromOneToN(int[] a)
{
    int xor = a.Length + 1;
    for (int i = 0; i < a.Length; i++)
        xor ^= (i + 1) ^ a[i];
    return xor;
}
```

**Complexity.** O(n) time, O(1) space for sum and XOR.

**Edge cases.** `[0]` returns 1; `[1]` returns 0; missing value is `0` or `n`.

:::q Follow-up: what if two numbers are missing?
Sum and XOR alone give one equation. With the sum of the two missing numbers `s` and their XOR (or sum of squares) you can solve for both. Simpler to explain: use a `bool[] seen` of size `n+1` in O(n) time and O(n) space, or sort the array and scan for gaps in O(n log n).
:::

### Find the second largest

**Problem.** Return the second largest *distinct* value in an array without sorting.

**Example.** `[12, 35, 1, 10, 34, 1]` returns `34`. `[5, 5, 5]` has no second largest.

**Intuition.** Track two variables as you scan once. A new maximum pushes the old maximum down to second place. Anything between the two updates only `second`.

**Approach.**
1. `first = second = null` (nullable avoids the `int.MinValue` sentinel bug).
2. For each `x`: if `first` is null or `x > first`, set `second = first`, `first = x`.
3. Else if `x != first` and (`second` is null or `x > second`), set `second = x`.
4. Return `second`.

```csharp
// Brute force: distinct + sort. O(n log n) time, O(n) space.
static int? SecondLargestSort(int[] a) =>
    a.Distinct().OrderByDescending(x => x).Skip(1).Select(x => (int?)x).FirstOrDefault();

// Optimal: single pass. O(n) time, O(1) space.
static int? SecondLargest(int[] a)
{
    int? first = null, second = null;
    foreach (int x in a)
    {
        if (first is null || x > first)
        {
            second = first;
            first = x;
        }
        else if (x != first && (second is null || x > second))
        {
            second = x;
        }
    }
    return second;
}
// SecondLargest(new[] { 12, 35, 1, 10, 34, 1 }) -> 34
// SecondLargest(new[] { 5, 5, 5 })              -> null
```

**Complexity.** O(n) time, O(1) space.

**Edge cases.** Fewer than two elements, all equal, duplicates of the maximum (`[7, 7, 3]` returns `3`), negatives, `int.MinValue` present (why a sentinel is risky).

:::q Follow-up: generalise to the k-th largest.
For small `k`, keep a min-heap of size `k` using `PriorityQueue<int,int>`: push each element, pop when the heap exceeds `k`; the root is the answer in O(n log k). For one-off queries on a mutable array, Quickselect gives O(n) average. Sorting is O(n log n) and acceptable when `n` is small.
:::

### Find the maximum and minimum

**Problem.** Return both the smallest and largest element in one pass.

**Example.** `[3, 5, 1, 9, 2]` returns `(Min: 1, Max: 9)`.

**Intuition.** Initialise both to the first element (never to `0` or `int.MaxValue`, which break on all-negative or extreme data), then compare each element once.

```csharp
static (int Min, int Max) MinMax(int[] a)
{
    if (a.Length == 0)
        throw new ArgumentException("Array must not be empty.", nameof(a));

    int min = a[0], max = a[0];
    for (int i = 1; i < a.Length; i++)
    {
        if (a[i] < min) min = a[i];
        else if (a[i] > max) max = a[i];   // safe: min <= max always holds
    }
    return (min, max);
}
// LINQ equivalents: a.Min(), a.Max() - two passes but trivially readable.
// MinMax(new[] { 3, 5, 1, 9, 2 }) -> (1, 9)
```

**Complexity.** Time O(n), space O(1). The `else if` trims comparisons to about 1.5n on average.

**Edge cases.** Empty array (decide: throw or return `null`), single element, all equal, all negative.

:::q Follow-up: how would you do it with fewer comparisons?
Process elements in pairs: compare the two elements with each other first (1 comparison), then compare the smaller to `min` and the larger to `max` (2 comparisons) - 3 comparisons per 2 elements, i.e. about `3n/2` instead of `2n`. In practice, mention it but say the constant-factor win rarely matters.
:::

### Two Sum

**Problem.** Given an array and a target, return the indices of the two numbers that add up to the target. Exactly one solution exists; you may not use the same element twice.

**Example.** `nums = [2, 7, 11, 15]`, `target = 9` returns `[0, 1]`.

**Intuition.** For each `x` you are looking for `target - x`. Instead of scanning for it (O(n)), remember every number you have already passed in a dictionary (`value -> index`) and look the complement up in O(1).

**Approach.**
1. Create `Dictionary<int,int> indexOf`.
2. For each index `i`, compute `need = target - nums[i]`.
3. If `need` is in the dictionary, return `[indexOf[need], i]`.
4. Otherwise store `indexOf[nums[i]] = i` and continue.

```csharp
// Brute force: try all pairs. O(n^2) time, O(1) space.
static int[] TwoSumBrute(int[] nums, int target)
{
    for (int i = 0; i < nums.Length; i++)
        for (int j = i + 1; j < nums.Length; j++)
            if (nums[i] + nums[j] == target) return [i, j];
    return [];
}

// Optimal: one pass with a dictionary. O(n) time, O(n) space.
static int[] TwoSum(int[] nums, int target)
{
    var indexOf = new Dictionary<int, int>();       // value -> index
    for (int i = 0; i < nums.Length; i++)
    {
        int need = target - nums[i];
        if (indexOf.TryGetValue(need, out int j)) return [j, i];
        indexOf[nums[i]] = i;                       // insert AFTER the check
    }
    return [];
}

// Sorted input (Two Sum II): two pointers, O(n) time, O(1) space.
static int[] TwoSumSorted(int[] sorted, int target)
{
    int l = 0, r = sorted.Length - 1;
    while (l < r)
    {
        long sum = (long)sorted[l] + sorted[r];
        if (sum == target) return [l, r];
        if (sum < target) l++; else r--;
    }
    return [];
}
// TwoSum(new[] { 3, 2, 4 }, 6) -> [1, 2]   (3 + 3 would reuse the same element)
// TwoSum(new[] { 3, 3 }, 6)    -> [0, 1]
```

**Complexity.**

| Approach | Time | Space |
|---|---|---|
| Brute force | O(n^2) | O(1) |
| Dictionary | O(n) | O(n) |
| Sorted + two pointers | O(n) | O(1) |

**Edge cases.** Duplicates (`[3,3]`), negatives, target `0`, no solution, complement equal to the element itself (inserting *after* the check handles it), `target - nums[i]` overflow near `int.MinValue`.

:::q Follow-up: you must return all unique pairs, not just one.
Sort the array and use two pointers, skipping equal neighbours after recording a pair. If you also need counts, use a `Dictionary<int,int>` of frequencies and count pairs `(x, target-x)`, taking care of the `x == target-x` case (`n*(n-1)/2` pairs). Three Sum extends this and is solved in the Coding Questions section.
:::

### Remove duplicates from a sorted array

**Problem.** Given a sorted `int[]`, remove duplicates *in place* so each value appears once. Return the new length `k`; the first `k` elements must hold the unique values in order.

**Example.** `[0,0,1,1,1,2,2,3,3,4]` becomes `[0,1,2,3,4,...]` and returns `5`.

**Intuition.** Duplicates are adjacent because the array is sorted. Use a *read* pointer that scans everything and a *write* pointer that marks where the next unique value belongs.

**Approach.**
1. `write = 1` (the first element is always unique).
2. For `read` from 1: if `a[read] != a[write - 1]`, copy it to `a[write]` and `write++`.
3. Return `write`.

```csharp
// Brute force: build a HashSet / new list. O(n) time, O(n) space, not in place.
static int[] RemoveDuplicatesNewArray(int[] sorted) => sorted.Distinct().ToArray();

// Optimal: read/write pointers. O(n) time, O(1) space.
static int RemoveDuplicatesSorted(int[] a)
{
    if (a.Length == 0) return 0;
    int write = 1;
    for (int read = 1; read < a.Length; read++)
    {
        if (a[read] != a[write - 1])
            a[write++] = a[read];
    }
    return write;
}
// var a = new[] { 0, 0, 1, 1, 1, 2, 2, 3, 3, 4 };
// RemoveDuplicatesSorted(a) -> 5, and a starts with [0, 1, 2, 3, 4]
```

**Complexity.** O(n) time, O(1) space.

**Edge cases.** Empty array, one element, all identical, no duplicates, negatives.

:::q Follow-up: allow each value to appear at most twice.
Change the comparison to look two slots back: copy `a[read]` when `write < 2 || a[read] != a[write - 2]`. The generalisation to "at most k" uses `a[write - k]`. Still O(n) time and O(1) space.
:::

### Character frequency

**Problem.** Count how many times each character occurs in a string.

**Example.** `"banana"` gives `a:3, b:1, n:2`.

**Intuition.** This is the building block for anagrams, first unique character, and "most frequent" questions. Pick the container by alphabet size: a fixed array for `a-z`, a dictionary for arbitrary Unicode.

```csharp
// General: any char. O(n) time, O(k) space for k distinct characters.
static Dictionary<char, int> CharFrequency(string s)
{
    var freq = new Dictionary<char, int>();
    foreach (char c in s)
        freq[c] = freq.GetValueOrDefault(c) + 1;
    return freq;
}

// Lowercase a-z only: fixed array, no hashing. O(n) time, O(1) space (26 ints).
static int[] LetterFrequency(string s)
{
    var counts = new int[26];
    foreach (char c in s)
        if (c is >= 'a' and <= 'z')
            counts[c - 'a']++;
    return counts;
}

// LINQ: concise. (.NET 9 also adds s.CountBy(c => c).)
static Dictionary<char, int> CharFrequencyLinq(string s) =>
    s.GroupBy(c => c).ToDictionary(g => g.Key, g => g.Count());

// Most frequent character (ties: first found).
static char MostFrequent(string s)
{
    var freq = CharFrequency(s);
    return freq.MaxBy(kv => kv.Value).Key;
}
// CharFrequency("banana") -> { b: 1, a: 3, n: 2 }
```

**Complexity.** O(n) time. Space O(1) for a bounded alphabet, O(k) otherwise.

**Edge cases.** Empty string, mixed case (decide whether `'A'` and `'a'` are the same), spaces and punctuation, Unicode.

:::q Follow-up: find the first non-repeating character.
Two passes: count frequencies, then scan the string again and return the first character whose count is 1 (or its index). It is O(n) time and O(k) space. The second pass over the *string* (not the dictionary) is what preserves order.
:::

### Palindrome check

**Problem.** Decide whether a string reads the same forwards and backwards. Variant: ignore case and non-alphanumeric characters.

**Example.** `"madam"` returns `true`. `"A man, a plan, a canal: Panama"` returns `true` in the variant. `"race a car"` returns `false`.

**Intuition.** A palindrome only needs the outer characters to match, then the next pair, and so on - two pointers moving inwards, no reversed copy needed.

**Approach (variant).** Move `l` right past non-alphanumerics, move `r` left past non-alphanumerics, compare lower-cased characters, move both inwards.

```csharp
// Brute force: reverse and compare. O(n) time, O(n) space.
static bool IsPalindromeReverse(string s) => s == ReverseString(s);

// Optimal: two pointers. O(n) time, O(1) space.
static bool IsPalindrome(string s)
{
    int l = 0, r = s.Length - 1;
    while (l < r)
    {
        if (s[l++] != s[r--]) return false;
    }
    return true;
}

// Ignore case, spaces and punctuation.
static bool IsPalindromeAlnum(string s)
{
    int l = 0, r = s.Length - 1;
    while (l < r)
    {
        while (l < r && !char.IsLetterOrDigit(s[l])) l++;
        while (l < r && !char.IsLetterOrDigit(s[r])) r--;
        if (char.ToLowerInvariant(s[l]) != char.ToLowerInvariant(s[r])) return false;
        l++;
        r--;
    }
    return true;
}

// Integer palindrome without converting to string: reverse only the second half.
static bool IsPalindromeNumber(int x)
{
    if (x < 0 || (x % 10 == 0 && x != 0)) return false;
    int reversedHalf = 0;
    while (x > reversedHalf)
    {
        reversedHalf = reversedHalf * 10 + x % 10;
        x /= 10;
    }
    return x == reversedHalf || x == reversedHalf / 10;   // even / odd digit count
}
```

**Complexity.** O(n) time, O(1) space for the two-pointer versions.

**Edge cases.** Empty string and single character (palindromes), only punctuation (`".,"` is a palindrome after filtering), mixed case, negative numbers, numbers ending in `0`.

:::q Follow-up: longest palindromic substring?
Expand around every centre (`n` odd centres and `n-1` even centres), tracking the best span - O(n^2) time, O(1) space, and simple to code on a whiteboard. Manacher's algorithm does it in O(n) but is rarely expected. A DP table `dp[i][j]` also works at O(n^2) space.
:::

### Anagram check

**Problem.** Two strings are anagrams if one is a rearrangement of the other's letters.

**Example.** `"listen"` and `"silent"` returns `true`. `"rat"` and `"car"` returns `false`.

**Intuition.** Anagrams have identical character multisets. Either normalise both (sort them) and compare, or count letters: increment for the first string, decrement for the second, and every counter must end at zero.

**Approach.**
1. If lengths differ, return `false`.
2. *Sort method:* sort both `char[]`s and compare - O(n log n).
3. *Count method:* one `int[26]`; `++` for `a[i]`, `--` for `b[i]`; any non-zero counter means `false` - O(n).

```csharp
// Sort and compare. O(n log n) time, O(n) space.
static bool IsAnagramSort(string a, string b)
{
    if (a.Length != b.Length) return false;
    char[] x = a.ToCharArray(), y = b.ToCharArray();
    Array.Sort(x);
    Array.Sort(y);
    return new string(x) == new string(y);
}

// Frequency array for lowercase a-z. O(n) time, O(1) space.
static bool IsAnagramCount(string a, string b)
{
    if (a.Length != b.Length) return false;
    var counts = new int[26];
    for (int i = 0; i < a.Length; i++)
    {
        counts[a[i] - 'a']++;
        counts[b[i] - 'a']--;
    }
    foreach (int c in counts)
        if (c != 0) return false;
    return true;
}

// Any characters (Unicode): dictionary instead of fixed array. O(n) time.
static bool IsAnagramAnyChar(string a, string b)
{
    if (a.Length != b.Length) return false;
    var counts = new Dictionary<char, int>();
    foreach (char c in a) counts[c] = counts.GetValueOrDefault(c) + 1;
    foreach (char c in b)
    {
        if (!counts.TryGetValue(c, out int n) || n == 0) return false;
        counts[c] = n - 1;
    }
    return true;
}
```

**Complexity.**

| Approach | Time | Space |
|---|---|---|
| Sort | O(n log n) | O(n) |
| Count array (a-z) | O(n) | O(1) |
| Dictionary (any char) | O(n) | O(k) |

**Edge cases.** Different lengths, empty strings (anagrams), case sensitivity, spaces (strip them first if "dormitory" vs "dirty room"), characters outside `a-z` crash the array version with `IndexOutOfRangeException`.

:::q Follow-up: group a list of words into anagram groups.
Use the sorted word (or a 26-count signature) as the dictionary key and a `List<string>` as the value - see *Group anagrams* in the Hashing group. O(n * k log k) with sorted keys, O(n * k) with count signatures, where `k` is the average word length.
:::
