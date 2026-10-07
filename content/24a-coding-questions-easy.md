## How to Use This Practice List

These 25 problems come up again and again in .NET service-company and product-company coding rounds. Each one is a short lesson: the problem, examples, C# solutions (brute force and optimal where they differ), complexity, and the follow-up you are most likely to get. When a problem is covered in depth in **Section 7 (Coding / DSA)**, it is cross-referenced by name. The code here is still complete, so you can revise from this page alone.

All snippets assume `using System; using System.Collections.Generic; using System.Linq; using System.Text;` (the .NET 8 console template's implicit usings plus `System.Text`) and are written as `static` methods. Every snippet was compiled and run against test cases.

:::tip How to practise these
Solve each one in a plain editor without IntelliSense first, then say the complexity out loud. Re-solve after 3 days, then after a week. Being fluent on the easy ten is what earns you time for the medium ones.
:::

## Easy Problems (1-10)

### 1. Reverse a string

**Problem.** Return the reverse of a string without using `Reverse()`.

**Examples.** `"hello"` returns `"olleh"`. `""` returns `""`. `"a"` returns `"a"`.

Deep dive: *Reverse a string* in Section 7, Arrays & Strings.

```csharp
// Two pointers on a char[] copy: O(n) time, O(n) space (strings are immutable).
static string ReverseString(string s)
{
    char[] c = s.ToCharArray();
    for (int l = 0, r = c.Length - 1; l < r; l++, r--)
        (c[l], c[r]) = (c[r], c[l]);
    return new string(c);
}

// StringBuilder walking backwards: O(n) time, O(n) space.
static string ReverseWithBuilder(string s)
{
    var sb = new StringBuilder(s.Length);
    for (int i = s.Length - 1; i >= 0; i--) sb.Append(s[i]);
    return sb.ToString();
}

// Recursive: elegant but O(n^2) because of substring copies, and O(n) stack depth.
static string ReverseRecursive(string s) =>
    s.Length <= 1 ? s : ReverseRecursive(s[1..]) + s[0];

// Library one-liners interviewers accept AFTER you show the loop:
//   new string(s.Reverse().ToArray())   or   Array.Reverse(charArray)
```

**Complexity.** O(n) time, O(n) space for the loop versions.

:::q Follow-up: reverse each word but keep the word order ("hello world" -> "olleh dlrow").
Split on spaces, reverse each word with the same two-pointer routine, and join with a space. That is O(n) overall. To do it without `Split`, scan once: when you hit a space or the end, reverse the `char[]` segment between the last word start and the current index.
:::

### 2. Reverse an array

**Problem.** Reverse an `int[]` in place.

**Examples.** `[1, 2, 3, 4, 5]` becomes `[5, 4, 3, 2, 1]`. `[7]` stays `[7]`.

Deep dive: *Reverse an array in place* in Section 7.

```csharp
// Two pointers: O(n) time, O(1) space.
static void ReverseArray(int[] a)
{
    for (int l = 0, r = a.Length - 1; l < r; l++, r--)
        (a[l], a[r]) = (a[r], a[l]);
}

// Generic version works for any element type.
static void ReverseArray<T>(T[] a)
{
    for (int l = 0, r = a.Length - 1; l < r; l++, r--)
        (a[l], a[r]) = (a[r], a[l]);
}
// Framework: Array.Reverse(a) does the same in place.
```

**Complexity.** O(n) time, O(1) space.

:::q Follow-up: rotate the array right by k steps.
Normalise `k %= n`. Then reverse the whole array, reverse the first `k` elements, and reverse the remaining `n-k`. That is O(n) time and O(1) space. Example: `[1,2,3,4,5,6,7]`, k=3 gives `[5,6,7,1,2,3,4]`.
:::

### 3. Palindrome

**Problem.** Check whether a string is a palindrome. Variant: ignore case and non-alphanumeric characters.

**Examples.** `"level"` returns `true`. `"A man, a plan, a canal: Panama"` returns `true` (variant). `"hello"` returns `false`.

Deep dive: *Palindrome check* in Section 7.

```csharp
// Two pointers: O(n) time, O(1) space.
static bool IsPalindrome(string s)
{
    for (int l = 0, r = s.Length - 1; l < r; l++, r--)
        if (s[l] != s[r]) return false;
    return true;
}

// Ignore case and anything that is not a letter or digit.
static bool IsPalindromeIgnoringSymbols(string s)
{
    int l = 0, r = s.Length - 1;
    while (l < r)
    {
        if (!char.IsLetterOrDigit(s[l])) { l++; continue; }
        if (!char.IsLetterOrDigit(s[r])) { r--; continue; }
        if (char.ToLowerInvariant(s[l]) != char.ToLowerInvariant(s[r])) return false;
        l++;
        r--;
    }
    return true;
}

// Number palindrome without string conversion: reverse the digits.
static bool IsPalindromeNumber(int n)
{
    if (n < 0) return false;
    int original = n;
    long reversed = 0;                       // long: reversing can overflow int
    while (n > 0)
    {
        reversed = reversed * 10 + n % 10;
        n /= 10;
    }
    return reversed == original;
}
```

**Complexity.** O(n) time, O(1) space. Number version: O(digits).

:::q Follow-up: can you make it a palindrome by deleting at most one character?
Run two pointers. At the first mismatch, try skipping either the left or the right character, and check whether the remaining range `[l+1..r]` or `[l..r-1]` is a palindrome. That is O(n) time and O(1) space. This is the "valid palindrome II" problem.
:::

### 4. Fibonacci

**Problem.** Return the n-th Fibonacci number (`F(0)=0`, `F(1)=1`), and print the first `n` terms.

**Examples.** `F(7) = 13`. First 8 terms: `0 1 1 2 3 5 8 13`.

Deep dive: *Fibonacci: recursion to O(1) space* in Section 7, Dynamic Programming.

```csharp
// Iterative: O(n) time, O(1) space - the answer to give first.
static long Fibonacci(int n)
{
    if (n < 0) throw new ArgumentOutOfRangeException(nameof(n));
    long a = 0, b = 1;
    for (int i = 0; i < n; i++)
        (a, b) = (b, a + b);
    return a;
}

// Recursive: O(2^n) time - show it, then explain why it is slow.
static long FibonacciRecursive(int n) =>
    n < 2 ? n : FibonacciRecursive(n - 1) + FibonacciRecursive(n - 2);

// Memoised: O(n) time, O(n) space.
static long FibonacciMemo(int n) => FibonacciMemo(n, new long[n + 1]);

static long FibonacciMemo(int n, long[] memo)
{
    if (n < 2) return n;
    if (memo[n] != 0) return memo[n];
    return memo[n] = FibonacciMemo(n - 1, memo) + FibonacciMemo(n - 2, memo);
}

// First n terms as a lazy sequence.
static IEnumerable<long> FibonacciSequence(int count)
{
    long a = 0, b = 1;
    for (int i = 0; i < count; i++)
    {
        yield return a;
        (a, b) = (b, a + b);
    }
}
// string.Join(" ", FibonacciSequence(8)) -> "0 1 1 2 3 5 8 13"
```

**Complexity.**

| Version | Time | Space |
|---|---|---|
| Iterative | O(n) | O(1) |
| Recursive | O(2^n) | O(n) stack |
| Memoised | O(n) | O(n) |

**Edge cases.** `n = 0`, `n = 1`, negative input, `F(93)` overflows `long` (use `System.Numerics.BigInteger`).

:::q Follow-up: why is the naive recursion exponential?
Each call branches into two, and the same subproblems are recomputed again and again. `F(n-2)` is computed by both `F(n)` and `F(n-1)`. The call tree has about `phi^n` (roughly 1.6^n) nodes. Caching each `F(k)` once reduces it to `n` distinct computations.
:::

### 5. Factorial

**Problem.** Return `n! = 1 x 2 x ... x n` (`0! = 1`).

**Examples.** `5! = 120`. `0! = 1`. `20! = 2,432,902,008,176,640,000` is the largest factorial that fits in `long`.

```csharp
// Iterative: O(n) time, O(1) space. checked() turns silent overflow into an exception.
static long Factorial(int n)
{
    if (n < 0) throw new ArgumentOutOfRangeException(nameof(n), "n must be >= 0");
    long result = 1;
    for (int i = 2; i <= n; i++)
        result = checked(result * i);
    return result;
}

// Recursive: O(n) time, O(n) stack.
static long FactorialRecursive(int n) => n <= 1 ? 1 : n * FactorialRecursive(n - 1);

// Large n: BigInteger never overflows (memory and time grow with the digit count).
static System.Numerics.BigInteger FactorialBig(int n)
{
    System.Numerics.BigInteger result = 1;
    for (int i = 2; i <= n; i++) result *= i;
    return result;
}

// Memoised across calls - useful if you need many factorials (e.g. combinations).
static readonly List<long> FactorialCache = new() { 1 };

static long FactorialCached(int n)
{
    for (int i = FactorialCache.Count; i <= n; i++)
        FactorialCache.Add(checked(FactorialCache[i - 1] * i));
    return FactorialCache[n];
}
// Factorial(5) -> 120     Factorial(21) -> OverflowException (checked)
```

**Complexity.** O(n) time. O(1) space iterative, O(n) recursive.

:::q Follow-up: how many trailing zeros does n! have?
Every trailing zero comes from a factor 10 = 2 x 5, and there are always more 2s than 5s. So count the factors of 5: `n/5 + n/25 + n/125 + ...`. That is O(log n) and needs no factorial at all. Example: `100!` has `20 + 4 = 24` trailing zeros.
:::

### 6. Prime number

**Problem.** (a) Check whether `n` is prime. (b) List all primes up to `n`.

**Examples.** `IsPrime(29)` is `true`, `IsPrime(1)` is `false`, `IsPrime(2)` is `true`. Primes up to 30: `2 3 5 7 11 13 17 19 23 29`.

**Intuition.** If `n = a x b` with `a <= b`, then `a <= sqrt(n)`. So you only need to test divisors up to `sqrt(n)`. For many numbers at once, the **Sieve of Eratosthenes** crosses out multiples of each prime, starting from `p*p`.

```csharp
// Brute force: try every divisor. O(n).
static bool IsPrimeBrute(int n)
{
    if (n < 2) return false;
    for (int d = 2; d < n; d++)
        if (n % d == 0) return false;
    return true;
}

// Trial division up to sqrt(n), skipping even numbers: O(sqrt n).
static bool IsPrime(int n)
{
    if (n < 2) return false;
    if (n % 2 == 0) return n == 2;
    for (long d = 3; d * d <= n; d += 2)       // long: d*d must not overflow
        if (n % d == 0) return false;
    return true;
}

// Sieve of Eratosthenes: O(n log log n) time, O(n) space.
static List<int> PrimesUpTo(int n)
{
    var primes = new List<int>();
    if (n < 2) return primes;
    var composite = new bool[n + 1];
    for (long p = 2; p * p <= n; p++)
    {
        if (composite[p]) continue;
        for (long m = p * p; m <= n; m += p)    // smaller multiples already crossed out
            composite[m] = true;
    }
    for (int i = 2; i <= n; i++)
        if (!composite[i]) primes.Add(i);
    return primes;
}
// PrimesUpTo(30) -> [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
```

**Complexity.**

| Approach | Time | Space |
|---|---|---|
| Brute force | O(n) per number | O(1) |
| Trial division to sqrt(n) | O(sqrt n) per number | O(1) |
| Sieve | O(n log log n) for all numbers up to n | O(n) |

**Edge cases.** `0`, `1` and negatives are not prime. `2` is the only even prime. Perfect squares like `25` and `49` (why the loop uses `<=`). `int.MaxValue` (overflow of `d * d` with `int`).

:::q Follow-up: why does the sieve start crossing out at p*p?
Any smaller multiple `k*p` with `k < p` has a prime factor smaller than `p`, so it was already crossed out when that smaller prime was processed. Starting at `p*p` avoids redundant work. It is also why the outer loop can stop at `sqrt(n)`.
:::

### 7. Second largest number

**Problem.** Find the second largest distinct value in one pass.

**Examples.** `[10, 5, 20, 8, 20]` returns `10`. `[4, 4]` has none (`null`).

Deep dive: *Find the second largest* in Section 7.

```csharp
// Brute force: sort distinct values descending. O(n log n).
static int? SecondLargestBySort(int[] a)
{
    var distinct = a.Distinct().OrderByDescending(x => x).ToArray();
    return distinct.Length >= 2 ? distinct[1] : null;
}

// Single pass: O(n) time, O(1) space. Nullable avoids the int.MinValue sentinel trap.
static int? SecondLargestOnePass(int[] a)
{
    int? largest = null, second = null;
    foreach (int x in a)
    {
        if (largest is null || x > largest)
        {
            second = largest;
            largest = x;
        }
        else if (x < largest && (second is null || x > second))
        {
            second = x;
        }
    }
    return second;
}
```

**Complexity.** O(n) time, O(1) space.

:::q Follow-up: what if the array contains int.MinValue and you used it as the sentinel?
With `second = int.MinValue` as the "not found" marker, you cannot tell "no second largest" apart from "the second largest is `int.MinValue`". Use `int?` or a `bool found` flag, or initialise from the first two elements. Mentioning this unprompted is a strong signal.
:::

### 8. Remove duplicates

**Problem.** Remove duplicate values (a) from an unsorted array, keeping the first occurrence order, (b) from a sorted array in place, (c) from a string.

**Examples.** `[3, 1, 3, 2, 1]` gives `[3, 1, 2]`. Sorted `[1, 1, 2, 3, 3]` gives length `3` with prefix `[1, 2, 3]`. `"programming"` gives `"progamin"`.

Deep dive: *Remove duplicates from a sorted array* in Section 7.

```csharp
// (a) Unsorted, keep order: HashSet. O(n) time, O(n) space.
static int[] RemoveDuplicatesKeepOrder(int[] a)
{
    var seen = new HashSet<int>();
    var result = new List<int>(a.Length);
    foreach (int x in a)
        if (seen.Add(x)) result.Add(x);
    return result.ToArray();
}
// LINQ: a.Distinct().ToArray() keeps first-occurrence order in practice, but the docs
// call the result unordered - use the explicit loop when order is a requirement.

// (b) Sorted, in place: read/write pointers. O(n) time, O(1) space.
static int RemoveDuplicatesInPlace(int[] sorted)
{
    if (sorted.Length == 0) return 0;
    int write = 1;
    for (int read = 1; read < sorted.Length; read++)
        if (sorted[read] != sorted[write - 1])
            sorted[write++] = sorted[read];
    return write;                       // new logical length
}

// (c) String: same HashSet idea with a StringBuilder.
static string RemoveDuplicateChars(string s)
{
    var seen = new HashSet<char>();
    var sb = new StringBuilder(s.Length);
    foreach (char c in s)
        if (seen.Add(c)) sb.Append(c);
    return sb.ToString();
}
```

**Complexity.** (a) and (c): O(n) time, O(n) space. (b): O(n) time, O(1) space.

:::q Follow-up: no extra memory and the array is unsorted?
Either sort it first (O(n log n), loses the original order) and then use the in-place routine, or use nested loops in O(n^2) that compact unique values to the front. State the trade-off: memory versus time versus preserving order.
:::

### 9. Count characters

**Problem.** Count the occurrences of each character. Common variants: count vowels/consonants/digits/spaces, or count words.

**Examples.** `"hello"` gives `h:1 e:1 l:2 o:1`. `"Hello World 2024"` has 3 vowels, 7 consonants, 4 digits and 2 spaces.

Deep dive: *Character frequency* in Section 7.

```csharp
// Frequency map: O(n) time, O(k) space for k distinct characters.
static Dictionary<char, int> CountChars(string s)
{
    var counts = new Dictionary<char, int>();
    foreach (char c in s)
        counts[c] = counts.GetValueOrDefault(c) + 1;
    return counts;
}

// Category counts in a single pass.
static (int Vowels, int Consonants, int Digits, int Spaces) CountCategories(string s)
{
    int vowels = 0, consonants = 0, digits = 0, spaces = 0;
    foreach (char ch in s)
    {
        char c = char.ToLowerInvariant(ch);
        if (c is 'a' or 'e' or 'i' or 'o' or 'u') vowels++;
        else if (c is >= 'a' and <= 'z') consonants++;
        else if (char.IsDigit(c)) digits++;
        else if (char.IsWhiteSpace(c)) spaces++;
    }
    return (vowels, consonants, digits, spaces);
}

// Word count, tolerant of repeated spaces.
static int CountWords(string s) =>
    s.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries).Length;

// Occurrences of a single character.
static int CountOf(string s, char target) => s.Count(c => c == target);
// CountWords("  the quick  brown fox ") -> 4
```

**Complexity.** O(n) time. O(k) space for the map, O(1) for category counts.

:::q Follow-up: print characters in descending order of frequency.
Build the frequency map, then sort the entries: `counts.OrderByDescending(kv => kv.Value).ThenBy(kv => kv.Key)`, which is O(k log k). For O(n), use bucket sort: an array of lists indexed by frequency from 0 to n, then walk it from the top.
:::

### 10. Find the missing number

**Problem.** An array contains `n` distinct numbers from `0..n` (or `n-1` numbers from `1..n`), with one missing. Find it.

**Examples.** `[3, 0, 1]` returns `2`. `[1, 2, 4, 5]` (from 1..5) returns `3`.

Deep dive: *Find the missing number* in Section 7.

```csharp
// Sum formula: O(n) time, O(1) space. long prevents overflow.
static int FindMissing(int[] a)                // numbers from 0..n, length n
{
    long n = a.Length;
    long sum = 0;
    foreach (int x in a) sum += x;
    return (int)(n * (n + 1) / 2 - sum);
}

// XOR: O(n) time, O(1) space, no overflow risk.
static int FindMissingXor(int[] a)
{
    int result = a.Length;
    for (int i = 0; i < a.Length; i++)
        result ^= i ^ a[i];
    return result;
}

// HashSet: O(n) time, O(n) space - simplest to explain, works with any range.
static int FindMissingHashSet(int[] a, int from, int to)
{
    var present = new HashSet<int>(a);
    for (int v = from; v <= to; v++)
        if (!present.Contains(v)) return v;
    return -1;
}
// FindMissing(new[] { 3, 0, 1 }) -> 2     FindMissingHashSet(new[] { 1, 2, 4, 5 }, 1, 5) -> 3
```

**Complexity.** O(n) time. O(1) space for sum and XOR.

:::q Follow-up: the array is sorted - can you beat O(n)?
Yes. Binary search for the first index where `a[i] != i` (for the 0..n version). Everything left of the gap satisfies `a[i] == i`, which is a monotonic predicate. That is O(log n).
:::
