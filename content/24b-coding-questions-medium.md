## Medium Problems (11-18)

### 11. Two Sum

**Problem.** Return the indices of the two numbers that add up to `target`. Exactly one answer exists, and you cannot use the same element twice.

**Examples.** `[2, 7, 11, 15]`, target `9` returns `[0, 1]`. `[3, 2, 4]`, target `6` returns `[1, 2]`. `[3, 3]`, target `6` returns `[0, 1]`.

Deep dive: *Two Sum* in Section 7, Arrays & Strings (also *Two Sum and complement lookups* under Hashing).

```csharp
// Brute force: O(n^2) time, O(1) space.
static int[] TwoSumBrute(int[] nums, int target)
{
    for (int i = 0; i < nums.Length; i++)
        for (int j = i + 1; j < nums.Length; j++)
            if (nums[i] + nums[j] == target) return [i, j];
    return [];
}

// One-pass dictionary: O(n) time, O(n) space.
static int[] TwoSum(int[] nums, int target)
{
    var seen = new Dictionary<int, int>();        // value -> index
    for (int i = 0; i < nums.Length; i++)
    {
        if (seen.TryGetValue(target - nums[i], out int j)) return [j, i];
        seen[nums[i]] = i;                        // add after checking: no self-pairing
    }
    return [];
}
```

**Complexity.** Brute O(n^2) / O(1). Dictionary O(n) / O(n). Sorted input with two pointers: O(n) / O(1).

:::q Follow-up: the input is a stream - add(number) and find(value) are called many times. How do you design it?
Keep a `Dictionary<int,int>` of counts. `add` is O(1). `find(value)` iterates over the distinct keys `x` and checks whether `value - x` exists, needing a count of at least 2 when `value - x == x`. That makes `find` O(k). If `find` is called far more often than `add`, precompute all pair sums into a `HashSet` instead: `add` becomes O(k) and `find` O(1). Name the trade-off.
:::

### 12. Three Sum

**Problem.** Return all **unique** triplets `[a, b, c]` with `a + b + c = 0`.

**Examples.** `[-1, 0, 1, 2, -1, -4]` returns `[[-1, -1, 2], [-1, 0, 1]]`. `[0, 0, 0, 0]` returns `[[0, 0, 0]]`. `[1, 2, -2, -1]` returns `[]`.

**Intuition.** Sort the array. Fix the first element `a[i]` and solve Two Sum on the sorted suffix with two pointers for target `-a[i]`. Sorting also makes duplicates adjacent, so you can skip them. That is the only reliable way to return each triplet once without a set of keys.

**Approach.**
1. Sort.
2. For each `i`: if `a[i] > 0`, stop (all remaining are positive). If `a[i] == a[i-1]`, skip it (duplicate first element).
3. `l = i + 1`, `r = n - 1`. If the sum is less than 0, `l++`. If it is greater than 0, `r--`. If it equals 0, record the triplet, move both pointers, and skip equal neighbours on both sides.

```csharp
// Brute force: O(n^3) time + a set of keys to remove duplicate triplets.
static List<int[]> ThreeSumBrute(int[] nums)
{
    var keys = new HashSet<(int, int, int)>();
    var result = new List<int[]>();
    for (int i = 0; i < nums.Length; i++)
        for (int j = i + 1; j < nums.Length; j++)
            for (int k = j + 1; k < nums.Length; k++)
            {
                if (nums[i] + nums[j] + nums[k] != 0) continue;
                int[] t = [nums[i], nums[j], nums[k]];
                Array.Sort(t);                                   // canonical order
                if (keys.Add((t[0], t[1], t[2]))) result.Add(t);
            }
    return result;
}

// Sort + two pointers: O(n^2) time, O(1) extra (besides the output and the sort).
static List<int[]> ThreeSum(int[] nums)
{
    var result = new List<int[]>();
    int[] a = (int[])nums.Clone();
    Array.Sort(a);
    for (int i = 0; i < a.Length - 2; i++)
    {
        if (a[i] > 0) break;                          // smallest is positive: no more zeros
        if (i > 0 && a[i] == a[i - 1]) continue;      // skip duplicate first elements
        int l = i + 1, r = a.Length - 1;
        while (l < r)
        {
            int sum = a[i] + a[l] + a[r];
            if (sum < 0) l++;
            else if (sum > 0) r--;
            else
            {
                result.Add([a[i], a[l], a[r]]);
                l++;
                r--;
                while (l < r && a[l] == a[l - 1]) l++;    // skip duplicate seconds
                while (l < r && a[r] == a[r + 1]) r--;    // skip duplicate thirds
            }
        }
    }
    return result;
}
// ThreeSum(new[] { -1, 0, 1, 2, -1, -4 }) -> [[-1, -1, 2], [-1, 0, 1]]
```

**Complexity.** O(n^2) time (O(n log n) sort + n two-pointer scans). O(1) extra space, or O(n) for the cloned array and sort.

**Edge cases.** Fewer than 3 elements, all zeros, no solution, many duplicates, overflow of the sum for values near `int.MaxValue` (use `long sum`).

:::q Follow-up: Three Sum Closest, or Four Sum?
Closest: the same sort and two-pointer loop, tracking the sum with the smallest `|sum - target|`. That is O(n^2). Four Sum: add one more outer loop with the same duplicate skipping, which is O(n^3). In general, k-Sum is `k-2` nested loops around a two-pointer core, giving O(n^(k-1)).
:::

### 13. Anagram

**Problem.** Decide whether two strings are anagrams (same letters with the same counts).

**Examples.** `"listen"` / `"silent"` returns `true`. `"anagram"` / `"nagaram"` returns `true`. `"rat"` / `"car"` returns `false`.

Deep dive: *Anagram check* and *Group anagrams* in Section 7.

```csharp
// Sort both: O(n log n) time, O(n) space.
static bool AreAnagramsBySort(string a, string b)
{
    if (a.Length != b.Length) return false;
    char[] x = a.ToCharArray(), y = b.ToCharArray();
    Array.Sort(x);
    Array.Sort(y);
    return x.AsSpan().SequenceEqual(y);
}

// Count array for a-z: O(n) time, O(1) space.
static bool AreAnagrams(string a, string b)
{
    if (a.Length != b.Length) return false;
    var count = new int[26];
    foreach (char c in a) count[c - 'a']++;
    foreach (char c in b)
        if (--count[c - 'a'] < 0) return false;     // b has more of c than a
    return true;
}

// Case-insensitive, ignoring spaces ("Dormitory" vs "Dirty room").
static bool AreAnagramsLoose(string a, string b)
{
    static string Normalize(string s) =>
        new string(s.Where(char.IsLetter).Select(char.ToLowerInvariant).OrderBy(c => c).ToArray());
    return Normalize(a) == Normalize(b);
}
```

**Complexity.** Count version O(n) time, O(1) space. Sort version O(n log n).

:::q Follow-up: find all start indices of anagrams of p inside s.
Use a fixed-size sliding window of length `p.Length` with two count arrays (or one difference array). Slide one character at a time: add the incoming character, remove the outgoing one, and compare the counts. Comparing 26 counters is O(1), so the whole scan is O(n). Example: `s = "cbaebabacd"`, `p = "abc"` gives `[0, 6]`.
:::

### 14. Merge two sorted arrays

**Problem.** (a) Merge two sorted arrays into a new sorted array. (b) In-place variant: `nums1` has length `m + n`, with the last `n` slots empty. Merge `nums2` into it without another array.

**Examples.** `[1, 3, 5]` + `[2, 4, 6, 8]` gives `[1, 2, 3, 4, 5, 6, 8]`. In-place: `nums1 = [1, 2, 3, 0, 0, 0]`, `m = 3`, `nums2 = [2, 5, 6]` gives `[1, 2, 2, 3, 5, 6]`.

**Intuition.** Two pointers, always taking the smaller head (the merge step of merge sort). For the in-place version, fill from the **back**. The largest remaining element goes into the last free slot, so nothing in `nums1` is overwritten before it is read.

```csharp
// Brute force: concatenate and sort. O((n+m) log(n+m)).
static int[] MergeBySort(int[] a, int[] b)
{
    int[] all = [.. a, .. b];
    Array.Sort(all);
    return all;
}

// Two pointers: O(n + m) time, O(n + m) output.
static int[] MergeSortedArrays(int[] a, int[] b)
{
    var result = new int[a.Length + b.Length];
    int i = 0, j = 0, k = 0;
    while (i < a.Length && j < b.Length)
        result[k++] = a[i] <= b[j] ? a[i++] : b[j++];
    while (i < a.Length) result[k++] = a[i++];
    while (j < b.Length) result[k++] = b[j++];
    return result;
}

// In place from the back: O(m + n) time, O(1) extra space.
static void MergeInPlace(int[] nums1, int m, int[] nums2, int n)
{
    int i = m - 1, j = n - 1, k = m + n - 1;
    while (j >= 0)                                   // once nums2 is done, nums1 is in place
    {
        if (i >= 0 && nums1[i] > nums2[j]) nums1[k--] = nums1[i--];
        else nums1[k--] = nums2[j--];
    }
}
```

**Complexity.** O(n + m) time. O(1) extra for the in-place version.

**Edge cases.** One array empty, `m = 0`, all of `b` smaller than `a`, duplicates across arrays.

:::q Follow-up: merge k sorted arrays.
Put the first element of each array into a `PriorityQueue<(int Array, int Index), int>` keyed by value. Repeatedly dequeue the smallest, output it, and enqueue the next element from the same array. That is O(N log k) for N total elements. Pairwise divide-and-conquer merging has the same complexity.
:::

### 15. Binary search

**Problem.** Find the index of `target` in a sorted array, or `-1`. Variant: first and last position of a repeated target.

**Examples.** `[-1, 0, 3, 5, 9, 12]`, target `9` returns `4`, target `2` returns `-1`. `[5, 7, 7, 8, 8, 10]`, target `8` gives first/last `[3, 4]`.

Deep dive: *Binary search* (including lower/upper bound and binary search on the answer) in Section 7, Searching.

```csharp
// Iterative: O(log n) time, O(1) space.
static int Search(int[] a, int target)
{
    int lo = 0, hi = a.Length - 1;
    while (lo <= hi)
    {
        int mid = lo + (hi - lo) / 2;              // overflow-safe midpoint
        if (a[mid] == target) return mid;
        if (a[mid] < target) lo = mid + 1; else hi = mid - 1;
    }
    return -1;
}

// Recursive: O(log n) time, O(log n) stack.
static int SearchRecursive(int[] a, int target, int lo, int hi)
{
    if (lo > hi) return -1;
    int mid = lo + (hi - lo) / 2;
    if (a[mid] == target) return mid;
    return a[mid] < target ? SearchRecursive(a, target, mid + 1, hi)
                           : SearchRecursive(a, target, lo, mid - 1);
}

// First and last occurrence: keep searching after a hit. O(log n).
static int[] SearchRange(int[] a, int target) =>
    [FindEdge(a, target, first: true), FindEdge(a, target, first: false)];

static int FindEdge(int[] a, int target, bool first)
{
    int lo = 0, hi = a.Length - 1, found = -1;
    while (lo <= hi)
    {
        int mid = lo + (hi - lo) / 2;
        if (a[mid] == target)
        {
            found = mid;
            if (first) hi = mid - 1; else lo = mid + 1;   // keep looking left / right
        }
        else if (a[mid] < target) lo = mid + 1;
        else hi = mid - 1;
    }
    return found;
}
```

**Complexity.** O(log n) time.

:::warn Say these three things while coding
`lo + (hi - lo) / 2` instead of `(lo + hi) / 2` (overflow). `lo <= hi` matches the inclusive `hi = n - 1` (otherwise the last element is never checked). Always move past `mid` with `mid + 1` / `mid - 1`, or the loop can run forever.
:::

:::q Follow-up: find the peak element, or the minimum in a rotated sorted array.
Both are binary search on a property, not on a value. For the peak: if `a[mid] < a[mid+1]`, a peak exists to the right, so `lo = mid + 1`, else `hi = mid`. For the rotated minimum: if `a[mid] > a[hi]`, the minimum is to the right, else `hi = mid`. Both are O(log n).
:::

### 16. Sliding window

**Problem A (fixed window).** Find the maximum sum of any contiguous subarray of size `k`.
**Problem B (variable window).** Find the length of the shortest contiguous subarray with sum `>= target` (all numbers positive).

**Examples.** A: `[2, 1, 5, 1, 3, 2]`, `k = 3` returns `9` (`5+1+3`). B: `[2, 3, 1, 2, 4, 3]`, `target = 7` returns `2` (`[4, 3]`).

**Intuition.** Recomputing every window costs O(n*k). When the window slides by one, only one element enters and one leaves. Add the newcomer and subtract the leaver, which gives O(n). For variable windows, *expand* the right edge until the window is valid, then *shrink* the left edge while it stays valid, recording the best.

```csharp
// A, brute force: O(n * k).
static int MaxSumWindowBrute(int[] a, int k)
{
    int best = int.MinValue;
    for (int i = 0; i + k <= a.Length; i++)
    {
        int sum = 0;
        for (int j = i; j < i + k; j++) sum += a[j];
        best = Math.Max(best, sum);
    }
    return best;
}

// A, sliding window: O(n) time, O(1) space.
static int MaxSumWindow(int[] a, int k)
{
    if (k <= 0 || k > a.Length) throw new ArgumentException("k must be in 1..n");
    int window = 0;
    for (int i = 0; i < k; i++) window += a[i];      // first window
    int best = window;
    for (int i = k; i < a.Length; i++)
    {
        window += a[i] - a[i - k];                   // add entering, remove leaving
        best = Math.Max(best, window);
    }
    return best;
}

// B, variable window (positive numbers only): O(n) time, O(1) space.
static int MinSubArrayLen(int target, int[] a)
{
    int left = 0, sum = 0, best = int.MaxValue;
    for (int right = 0; right < a.Length; right++)
    {
        sum += a[right];                             // expand
        while (sum >= target)                        // shrink while still valid
        {
            best = Math.Min(best, right - left + 1);
            sum -= a[left++];
        }
    }
    return best == int.MaxValue ? 0 : best;
}
```

**Complexity.** O(n) time, O(1) space. Each index enters and leaves the window at most once, even with the nested `while`.

**Edge cases.** `k > n`, `k = 0`, negative numbers (fixed windows still work; the *variable* window needs positives, otherwise use prefix sums + hashing), no valid window (return 0).

:::q Follow-up: maximum of every window of size k?
Use a monotonic deque (`LinkedList<int>` of indices) that keeps values in decreasing order. Drop indices that fell out of the window from the front. Drop smaller values from the back before pushing the new index. The front is the window maximum. That is O(n) overall, versus O(n*k) brute force or O(n log k) with a heap.
:::

### 17. Longest substring without repeating characters

**Problem.** Return the length of the longest substring with all distinct characters.

**Examples.** `"abcabcbb"` returns `3` (`"abc"`). `"bbbbb"` returns `1`. `"pwwkew"` returns `3` (`"wke"`). `""` returns `0`.

**Intuition.** This is a variable sliding window `[left, right]` that always holds distinct characters. When `s[right]` was already seen *inside the window*, jump `left` to just past its previous position. A dictionary of **last index** per character makes the jump O(1), so `left` never moves backwards.

**Approach.**
1. `lastIndex = new Dictionary<char,int>()`, `left = 0`, `best = 0`.
2. For each `right`: if `s[right]` was seen at index `p >= left`, set `left = p + 1`.
3. Store `lastIndex[s[right]] = right` and update `best = max(best, right - left + 1)`.

```csharp
// Brute force: check every substring. O(n^3) (or O(n^2) with an incremental set).
static int LongestUniqueBrute(string s)
{
    int best = 0;
    for (int i = 0; i < s.Length; i++)
    {
        var seen = new HashSet<char>();
        for (int j = i; j < s.Length && seen.Add(s[j]); j++)
            best = Math.Max(best, j - i + 1);
    }
    return best;
}

// Sliding window + dictionary of last index: O(n) time, O(k) space.
static int LengthOfLongestSubstring(string s)
{
    var lastIndex = new Dictionary<char, int>();
    int left = 0, best = 0;
    for (int right = 0; right < s.Length; right++)
    {
        char c = s[right];
        if (lastIndex.TryGetValue(c, out int prev) && prev >= left)
            left = prev + 1;                         // jump past the previous copy
        lastIndex[c] = right;
        best = Math.Max(best, right - left + 1);
    }
    return best;
}

// Same idea with a HashSet: shrink one step at a time. Still O(n), each char removed once.
static int LengthOfLongestSubstringSet(string s)
{
    var window = new HashSet<char>();
    int left = 0, best = 0;
    for (int right = 0; right < s.Length; right++)
    {
        while (!window.Add(s[right]))
            window.Remove(s[left++]);
        best = Math.Max(best, right - left + 1);
    }
    return best;
}
```

**Complexity.** O(n) time. O(min(n, alphabet)) space.

**Edge cases.** Empty string, all identical, all unique, spaces and symbols count as characters, `"abba"`. The `prev >= left` check stops `left` from jumping *backwards* when the second `a` is seen.

:::q Follow-up: return the substring itself, or allow at most k distinct characters.
To return it, track `bestStart` whenever `best` improves and return `s.Substring(bestStart, best)`. For "at most k distinct", keep a `Dictionary<char,int>` of counts in the window. While `counts.Count > k`, decrement `s[left]` (removing the key when it reaches 0) and advance `left`. It is still O(n).
:::

### 18. Valid parentheses

**Problem.** A string contains only `()[]{}`. It is valid if every opener is closed by the same type in the correct order.

**Examples.** `"()[]{}"` returns `true`. `"(]"` returns `false`. `"([)]"` returns `false`. `"{[]}"` returns `true`.

Deep dive: *Balanced parentheses* in Section 7, Stack & Queue.

```csharp
// Stack of EXPECTED closers: push the matching closer for each opener. O(n) / O(n).
static bool IsValidParentheses(string s)
{
    if (s.Length % 2 == 1) return false;            // quick reject
    var expected = new Stack<char>();
    foreach (char c in s)
    {
        switch (c)
        {
            case '(': expected.Push(')'); break;
            case '[': expected.Push(']'); break;
            case '{': expected.Push('}'); break;
            default:
                if (expected.Count == 0 || expected.Pop() != c) return false;
                break;
        }
    }
    return expected.Count == 0;
}

// Only '(' and ')': a counter is enough. O(n) time, O(1) space.
static bool IsValidSingleType(string s)
{
    int open = 0;
    foreach (char c in s)
    {
        open += c == '(' ? 1 : -1;
        if (open < 0) return false;                 // a ')' with nothing to close
    }
    return open == 0;
}
```

**Complexity.** O(n) time. O(n) space for the stack, O(1) for the counter version.

:::q Follow-up: longest valid parentheses substring?
Keep a stack of indices with a sentinel `-1` at the bottom. Push the index for `(`. For `)`, pop. If the stack is then empty, push the current index as the new base. Otherwise the current valid length is `i - stack.Peek()`. That is O(n) time. A two-pass counter approach (left-to-right, then right-to-left) gives O(1) space.
:::
