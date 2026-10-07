## Hashing

### Dictionary and HashSet in .NET

**Definition.** A hash table maps a *key* to a slot using `hash(key)`, giving O(1) average lookups. In .NET, `Dictionary<TKey,TValue>` is the hash map and `HashSet<T>` is the hash set (same engine, no value).

**Why it matters.** "Replace a nested loop with a dictionary lookup" is the single most common optimisation in coding rounds: O(n^2) becomes O(n) at the cost of O(n) memory.

**How it works.**
- `Dictionary` keeps an `int[] buckets` array and an `Entry[] entries` array. The key's hash picks a bucket; colliding entries are chained through an index (`next`) inside the `entries` array.
- When the entries array is full, it resizes to the next larger prime and rehashes. Average cost per insert stays O(1) amortised.
- Equality is decided by `GetHashCode()` first, then `Equals()`. **If two objects are equal they must return the same hash code.** Custom keys must override both (or be a `record`/`record struct`, which does it for you).
- `string` hashing is randomised per process to resist hash-flooding attacks, so enumeration order is never something to depend on.

```csharp
// Idiomatic access patterns.
static void DictionaryPatterns()
{
    var stock = new Dictionary<string, int>();

    stock["apple"] = 10;                                  // add or overwrite
    stock.TryAdd("pear", 5);                              // add only if absent
    if (stock.TryGetValue("apple", out int qty)) { }      // single lookup, no exception
    int missing = stock.GetValueOrDefault("kiwi");        // 0 when absent
    stock["apple"] = stock.GetValueOrDefault("apple") + 1; // counting idiom
}

// A composite key: a record struct gives value equality and a good hash for free.
readonly record struct Cell(int Row, int Col);

static bool VisitTwice()
{
    var visited = new HashSet<Cell>();
    visited.Add(new Cell(2, 3));
    return !visited.Add(new Cell(2, 3));   // true: second Add reports "already there"
}
```

| Question | Answer |
|---|---|
| `Dictionary` vs `Hashtable` | `Dictionary<K,V>` is generic and type safe, no boxing for value types; `Hashtable` is the legacy non-generic one |
| `Dictionary` vs `ConcurrentDictionary` | Plain `Dictionary` is not thread safe; use `ConcurrentDictionary` (or a lock) for concurrent writers |
| Null keys | `Dictionary` throws `ArgumentNullException` for a `null` key; values may be `null` |
| Modify while iterating | Adding keys during `foreach` throws `InvalidOperationException`; since .NET Core 3.0 `Remove` and `Clear` are allowed |
| Worst case | O(n) per operation if every key collides - why a stable, well-distributed `GetHashCode` matters |

:::warn Mutable keys
Never mutate the fields that feed `GetHashCode()` after using the object as a key. The entry stays in its old bucket and every later lookup silently fails.
:::

:::q How does Dictionary handle collisions?
`Dictionary<TKey,TValue>` uses separate chaining implemented with arrays: the hash selects a bucket holding the index of the first entry, and each entry stores the index of the next entry in the same bucket. Lookup walks that chain comparing hash codes and then calling `Equals`. It resizes to a larger prime size when the entries array is full, which keeps chains short and inserts O(1) amortised.
:::

### Frequency counting

**Problem.** Count occurrences, then answer a question from the counts (most frequent, any above a threshold, first unique).

**Example.** Words `["red","blue","red","green","blue","red"]` give `red:3, blue:2, green:1`.

**Intuition.** One pass builds the frequency map; a second pass (over the map or over the original input) answers the question. This is the backbone of "Top K frequent", "first unique character", "majority element" and anagram problems.

```csharp
static Dictionary<string, int> WordCount(IEnumerable<string> words)
{
    var counts = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
    foreach (string w in words)
        counts[w] = counts.GetValueOrDefault(w) + 1;
    return counts;
}

// First character that appears exactly once; -1 if none. O(n) time, O(k) space.
static int FirstUniqueChar(string s)
{
    var counts = new Dictionary<char, int>();
    foreach (char c in s) counts[c] = counts.GetValueOrDefault(c) + 1;
    for (int i = 0; i < s.Length; i++)
        if (counts[s[i]] == 1) return i;
    return -1;
}

// Majority element (> n/2 occurrences) with Boyer-Moore voting: O(n) time, O(1) space.
static int MajorityElement(int[] a)
{
    int candidate = 0, votes = 0;
    foreach (int x in a)
    {
        if (votes == 0) candidate = x;
        votes += x == candidate ? 1 : -1;
    }
    return candidate;       // valid only if a majority is guaranteed to exist
}
// FirstUniqueChar("leetcode") -> 0 ; FirstUniqueChar("aabb") -> -1
```

**Complexity.** O(n) time, O(k) space for `k` distinct items (Boyer-Moore: O(1)).

**Edge cases.** Empty input, ties for the most frequent, case sensitivity (`StringComparer.OrdinalIgnoreCase` handles it in one place).

:::q Follow-up: can you find the majority element without a dictionary?
Yes - Boyer-Moore voting. Keep a candidate and a counter: a matching element increments, a different one decrements, and when the counter hits zero the next element becomes the candidate. Pairs of different elements cancel out, so a true majority survives. It needs a verification pass if a majority is not guaranteed.
:::

### Two Sum and complement lookups

**Definition.** "Complement lookup" is the hashing pattern behind Two Sum: store what you have seen, ask whether what you need is already stored.

The full explanation, brute force and sorted variant are under *Two Sum* in **Arrays & Strings**. The same idea solves several siblings:

```csharp
// Does any pair differ by exactly k? (k > 0)  O(n) time, O(n) space.
static bool HasPairWithDifference(int[] a, int k)
{
    var seen = new HashSet<int>();
    foreach (int x in a)
    {
        if (seen.Contains(x - k) || seen.Contains(x + k)) return true;
        seen.Add(x);
    }
    return false;
}

// Count pairs summing to target (each index pair counted once).
static int CountPairsWithSum(int[] a, int target)
{
    var counts = new Dictionary<int, int>();
    int pairs = 0;
    foreach (int x in a)
    {
        pairs += counts.GetValueOrDefault(target - x);   // earlier partners of x
        counts[x] = counts.GetValueOrDefault(x) + 1;
    }
    return pairs;
}
// CountPairsWithSum(new[] { 1, 1, 1 }, 2) -> 3
```

:::q When is two pointers better than a dictionary for Two Sum?
When the array is already sorted or sorting is acceptable and you need O(1) extra space. The dictionary wins when the input is unsorted and you must preserve original indices, because sorting would lose them unless you also store the indices.
:::

### Duplicate detection within a window

**Problem.** Return `true` if two equal values exist whose indices differ by at most `k`.

**Example.** `nums = [1,2,3,1]`, `k = 3` returns `true`; `k = 2` returns `false`.

**Intuition.** Only the last `k` elements matter, so keep them in a `HashSet` (a sliding window). Add the new value; if it was already there, you found a close duplicate.

```csharp
static bool ContainsNearbyDuplicate(int[] nums, int k)
{
    var window = new HashSet<int>();
    for (int i = 0; i < nums.Length; i++)
    {
        if (!window.Add(nums[i])) return true;
        if (window.Count > k) window.Remove(nums[i - k]);   // slide the window
    }
    return false;
}
```

**Complexity.** O(n) time, O(min(n, k)) space.

**Edge cases.** `k = 0` (never true for distinct indices), `k >= n`, empty input.

### HashSet problems

**Definition.** `HashSet<T>` stores unique items with O(1) `Add`, `Contains` and `Remove`, plus set algebra: `UnionWith`, `IntersectWith`, `ExceptWith`, `SymmetricExceptWith`, `IsSubsetOf`.

```csharp
// Intersection of two arrays (unique values). O(n + m) time.
static int[] IntersectArrays(int[] a, int[] b)
{
    var set = new HashSet<int>(a);
    set.IntersectWith(b);
    return set.ToArray();
}

// Longest run of consecutive integers in an unsorted array. O(n) time, O(n) space.
static int LongestConsecutive(int[] nums)
{
    var set = new HashSet<int>(nums);
    int best = 0;
    foreach (int n in set)
    {
        if (set.Contains(n - 1)) continue;       // n is not the start of a run
        int len = 1;
        while (set.Contains(n + len)) len++;
        best = Math.Max(best, len);
    }
    return best;
}
// LongestConsecutive(new[] { 100, 4, 200, 1, 3, 2 }) -> 4   (1,2,3,4)
```

**Why `LongestConsecutive` is O(n), not O(n^2).** The inner `while` only runs for the *start* of a run, so every element is visited at most twice overall.

:::q Follow-up: why not just sort for longest consecutive sequence?
Sorting is O(n log n) and perfectly acceptable if the interviewer does not demand O(n). The HashSet version is the answer when they ask "can you do it in linear time?". State both and let them choose.
:::

### Group anagrams

**Problem.** Group words that are anagrams of each other.

**Example.** `["eat","tea","tan","ate","nat","bat"]` gives `[["eat","tea","ate"],["tan","nat"],["bat"]]`.

**Intuition.** Anagrams share the same *canonical form* - the sorted letters. Use it as the dictionary key.

```csharp
static List<List<string>> GroupAnagrams(string[] words)
{
    var groups = new Dictionary<string, List<string>>();
    foreach (string w in words)
    {
        char[] key = w.ToCharArray();
        Array.Sort(key);
        string k = new string(key);
        if (!groups.TryGetValue(k, out var list))
            groups[k] = list = new List<string>();
        list.Add(w);
    }
    return groups.Values.ToList();
}
```

**Complexity.** O(n * k log k) time for `n` words of length `k`; O(n * k) space.

### Subarray sum equals K (prefix sums + hashing)

**Problem.** Count contiguous subarrays whose sum is exactly `k` (values may be negative).

**Example.** `[1, 2, 3]`, `k = 3` returns `2` (`[1,2]` and `[3]`).

**Intuition.** Let `prefix[i]` be the sum of the first `i` elements. A subarray `(j, i]` sums to `k` exactly when `prefix[i] - prefix[j] = k`. While scanning, count how many earlier prefixes equal `prefix[i] - k`. Seed the map with `{0: 1}` for subarrays starting at index 0. Sliding window fails here because negatives break monotonicity.

```csharp
// Brute force: O(n^2) time, O(1) space - every start with a running sum.
static int SubarraySumBrute(int[] nums, int k)
{
    int count = 0;
    for (int i = 0; i < nums.Length; i++)
    {
        int sum = 0;
        for (int j = i; j < nums.Length; j++)
        {
            sum += nums[j];
            if (sum == k) count++;
        }
    }
    return count;
}

// Optimal: O(n) time, O(n) space.
static int SubarraySumEqualsK(int[] nums, int k)
{
    var seen = new Dictionary<int, int> { [0] = 1 };    // prefix sum -> times seen
    int sum = 0, count = 0;
    foreach (int x in nums)
    {
        sum += x;
        count += seen.GetValueOrDefault(sum - k);
        seen[sum] = seen.GetValueOrDefault(sum) + 1;
    }
    return count;
}
```

**Edge cases.** `k = 0` with zeros, all negatives, empty array, `int` overflow of the running sum (use `long` for big inputs).

:::q Follow-up: why must the dictionary start with {0: 1}?
It represents the empty prefix. Without it, subarrays that start at index 0 and sum to `k` (where `prefix[i] - k = 0`) would never be counted.
:::

## Stack & Queue

**Definition.** A *stack* is LIFO (last in, first out): `Push`, `Pop`, `Peek`. A *queue* is FIFO (first in, first out): `Enqueue`, `Dequeue`, `Peek`. Both give O(1) for every operation when implemented correctly.

**Why it matters.** Stacks model *nesting and undo* (call stack, brackets, DFS, expression evaluation, browser back button). Queues model *fairness and levels* (BFS, task scheduling, message queues, print jobs). Interviewers ask you to build them from scratch to check that you understand arrays, resizing and linked nodes.

| | Stack | Queue |
|---|---|---|
| Order | LIFO | FIFO |
| Insert / remove | both at the *top* | insert at *tail*, remove from *head* |
| .NET type | `Stack<T>` | `Queue<T>` (and `PriorityQueue<TElem,TPrio>` for ordered removal) |
| Typical use | DFS, brackets, undo, monotonic stack | BFS, scheduling, buffering |

### Implement a Stack

**Problem.** Build a generic stack with `Push`, `Pop`, `Peek`, `Count`, `IsEmpty` without using `Stack<T>`.

**Intuition.** Two classic storages: an *array* with a `count` that doubles when full (cache friendly, amortised O(1) push), or a *singly linked list* where the head is the top (true O(1) push, one allocation per element).

**Approach (array).**
1. Keep `T[] items` and `int count` (the next free slot).
2. `Push`: if full, double the array; store at `items[count++]`.
3. `Pop`: throw if empty; `count--`; clear the slot so the GC can reclaim the object; return the value.
4. `Peek`: return `items[count - 1]`.

```csharp
public class ArrayStack<T>
{
    private T[] _items;
    private int _count;

    public ArrayStack(int capacity = 4) => _items = new T[Math.Max(1, capacity)];

    public int Count => _count;
    public bool IsEmpty => _count == 0;

    public void Push(T item)
    {
        if (_count == _items.Length)
            Array.Resize(ref _items, _items.Length * 2);   // amortised O(1)
        _items[_count++] = item;
    }

    public T Pop()
    {
        if (_count == 0) throw new InvalidOperationException("Stack is empty.");
        T item = _items[--_count];
        _items[_count] = default!;       // do not keep a reference alive
        return item;
    }

    public T Peek() =>
        _count == 0 ? throw new InvalidOperationException("Stack is empty.") : _items[_count - 1];
}

// Linked-node version: the head of the list is the top of the stack.
public class LinkedStack<T>
{
    private class Node
    {
        public T Value;
        public Node? Next;
        public Node(T value, Node? next) { Value = value; Next = next; }
    }

    private Node? _top;
    public int Count { get; private set; }
    public bool IsEmpty => _top is null;

    public void Push(T item)
    {
        _top = new Node(item, _top);     // new node points at the old top
        Count++;
    }

    public T Pop()
    {
        if (_top is null) throw new InvalidOperationException("Stack is empty.");
        T value = _top.Value;
        _top = _top.Next;
        Count--;
        return value;
    }

    public T Peek() =>
        _top is null ? throw new InvalidOperationException("Stack is empty.") : _top.Value;
}
// var s = new ArrayStack<int>(); s.Push(1); s.Push(2); s.Pop() -> 2; s.Peek() -> 1
```

**Complexity.**

| | `Push` | `Pop` / `Peek` | Space |
|---|---|---|---|
| Array stack | O(1) amortised (O(n) on resize) | O(1) | O(n), wasted capacity up to 2x |
| Linked stack | O(1) worst case | O(1) | O(n) plus a pointer per node |

**Edge cases.** Pop/peek on empty (throw `InvalidOperationException`, like `Stack<T>`), resize boundary, storing `null`, `default!` clearing for reference types.

:::q Array stack or linked stack - which would you choose?
Array by default: better cache locality, fewer allocations, and amortised O(1) push is fine. Choose linked nodes when you need a hard O(1) worst case for every push (latency sensitive), when memory should shrink immediately after pops, or when stacks share structure (persistent/immutable stacks).
:::

### Implement a Queue

**Problem.** Build a generic FIFO queue with `Enqueue`, `Dequeue`, `Peek`, `Count`.

**Intuition.** A plain array makes `Dequeue` O(n) because every element would shift left. The fix is a *circular buffer*: keep a `head` index and a `count`; the tail slot is `(head + count) % capacity`. With linked nodes keep both `head` and `tail` pointers: enqueue at the tail, dequeue from the head.

**Approach (circular array).**
1. `Enqueue`: if full, allocate a bigger array and copy elements in logical order (reset `head = 0`); write at `(head + count) % length`.
2. `Dequeue`: read `items[head]`, clear it, `head = (head + 1) % length`, `count--`.

```csharp
public class ArrayQueue<T>
{
    private T[] _items = new T[4];
    private int _head;      // index of the front element
    private int _count;

    public int Count => _count;
    public bool IsEmpty => _count == 0;

    public void Enqueue(T item)
    {
        if (_count == _items.Length) Grow();
        _items[(_head + _count) % _items.Length] = item;
        _count++;
    }

    public T Dequeue()
    {
        if (_count == 0) throw new InvalidOperationException("Queue is empty.");
        T item = _items[_head];
        _items[_head] = default!;
        _head = (_head + 1) % _items.Length;
        _count--;
        return item;
    }

    public T Peek() =>
        _count == 0 ? throw new InvalidOperationException("Queue is empty.") : _items[_head];

    private void Grow()
    {
        var bigger = new T[_items.Length * 2];
        for (int i = 0; i < _count; i++)
            bigger[i] = _items[(_head + i) % _items.Length];   // unwrap the ring
        _items = bigger;
        _head = 0;
    }
}

// Linked-node version: enqueue at tail, dequeue at head, both O(1).
public class LinkedQueue<T>
{
    private class Node
    {
        public T Value;
        public Node? Next;
        public Node(T value) => Value = value;
    }

    private Node? _head, _tail;
    public int Count { get; private set; }

    public void Enqueue(T item)
    {
        var node = new Node(item);
        if (_tail is null) _head = _tail = node;      // first element
        else { _tail.Next = node; _tail = node; }
        Count++;
    }

    public T Dequeue()
    {
        if (_head is null) throw new InvalidOperationException("Queue is empty.");
        T value = _head.Value;
        _head = _head.Next;
        if (_head is null) _tail = null;              // queue became empty
        Count--;
        return value;
    }

    public T Peek() =>
        _head is null ? throw new InvalidOperationException("Queue is empty.") : _head.Value;
}
// enqueue 1,2,3 -> dequeue gives 1, 2, 3 (FIFO)
```

**Complexity.** All operations O(1) (array version: `Enqueue` amortised O(1)). Space O(n).

**Edge cases.** Wrap-around of `head` (the reason for `%`), dequeue until empty then enqueue again (resetting `tail` in the linked version), growth while `head != 0`.

:::warn Using List<T>.RemoveAt(0) as a queue
It shifts every remaining element - O(n) per dequeue, O(n^2) for a full drain. Use `Queue<T>`.
:::

:::q What is a circular queue and why use it?
It is a fixed array treated as a ring: indices wrap with modulo, so freed front slots are reused instead of shifting elements. It gives O(1) enqueue/dequeue with no allocation per item, which is how `Queue<T>` is implemented internally and how bounded buffers (logging, producer/consumer) are built.
:::

### Balanced parentheses

**Problem.** Given a string of `()[]{}` (and possibly other characters), decide if every opener has a matching closer in the correct order.

**Example.** `"{[()]}"` returns `true`. `"([)]"` returns `false`. `"(("` returns `false`.

**Intuition.** The *most recent* unmatched opener must be closed first - that is exactly LIFO. Push openers; on a closer, the stack top must be its matching opener.

**Approach.**
1. Map each closer to its opener.
2. For each character: opener -> push; closer -> if the stack is empty or `Pop()` is not the right opener, return `false`.
3. At the end the stack must be empty.

```csharp
static bool IsBalanced(string s)
{
    var pairs = new Dictionary<char, char> { [')'] = '(', [']'] = '[', ['}'] = '{' };
    var stack = new Stack<char>();

    foreach (char c in s)
    {
        if (c is '(' or '[' or '{')
        {
            stack.Push(c);
        }
        else if (pairs.TryGetValue(c, out char opener))
        {
            if (stack.Count == 0 || stack.Pop() != opener) return false;
        }
        // any other character is ignored
    }
    return stack.Count == 0;       // leftover openers mean unbalanced
}
// IsBalanced("{[()]}") -> true   IsBalanced("([)]") -> false   IsBalanced("(") -> false
```

**Complexity.** O(n) time, O(n) space (worst case all openers).

**Edge cases.** Empty string (balanced), starts with a closer, odd length, leftover openers, interleaving like `([)]`.

:::q Follow-up: only one bracket type - can you do it in O(1) space?
Yes. With a single type of bracket you only need a counter: increment on `(`, decrement on `)`, return `false` if it ever goes negative, and require `0` at the end. The stack is needed only when there are multiple bracket types whose *order* matters. A related interview favourite: "minimum insertions to balance" uses the same counter plus a second counter for unmatched closers.
:::

### Next greater element (monotonic stack)

**Problem.** For each element, find the first larger element to its right; output `-1` if none.

**Example.** `[4, 5, 2, 25]` returns `[5, 25, 25, -1]`. `[13, 7, 6, 12]` returns `[-1, 12, 12, -1]`.

**Intuition.** Brute force rescans to the right for every element. Instead keep a stack of indices whose answer is still *unknown*, with values in decreasing order (a *monotonic* stack). When a new element is larger than the stack top, it is the next greater element for that top - pop and resolve, repeat, then push the new index. Each index is pushed and popped once, so total work is O(n).

**Approach.**
1. Fill the result with `-1`.
2. For each `i`: while the stack is non-empty and `a[stack.Peek()] < a[i]`, set `result[stack.Pop()] = a[i]`.
3. Push `i`.

```csharp
// Brute force: O(n^2) time, O(1) extra space.
static int[] NextGreaterBrute(int[] a)
{
    var result = new int[a.Length];
    for (int i = 0; i < a.Length; i++)
    {
        result[i] = -1;
        for (int j = i + 1; j < a.Length; j++)
            if (a[j] > a[i]) { result[i] = a[j]; break; }
    }
    return result;
}

// Monotonic stack: O(n) time, O(n) space.
static int[] NextGreater(int[] a)
{
    var result = new int[a.Length];
    Array.Fill(result, -1);
    var stack = new Stack<int>();               // indices, values strictly decreasing
    for (int i = 0; i < a.Length; i++)
    {
        while (stack.Count > 0 && a[stack.Peek()] < a[i])
            result[stack.Pop()] = a[i];
        stack.Push(i);
    }
    return result;
}

// Circular array: scan twice, push indices only in the first pass.
static int[] NextGreaterCircular(int[] a)
{
    int n = a.Length;
    var result = new int[n];
    Array.Fill(result, -1);
    var stack = new Stack<int>();
    for (int i = 0; i < 2 * n; i++)
    {
        int idx = i % n;
        while (stack.Count > 0 && a[stack.Peek()] < a[idx])
            result[stack.Pop()] = a[idx];
        if (i < n) stack.Push(idx);
    }
    return result;
}
// NextGreater(new[] { 4, 5, 2, 25 }) -> [5, 25, 25, -1]
// NextGreaterCircular(new[] { 1, 2, 1 }) -> [2, -1, 2]
```

**Complexity.** O(n) time (amortised - the inner `while` pops each index at most once), O(n) space.

**Edge cases.** Empty array, strictly decreasing (all `-1`), equal values (`<` means equal values do not resolve each other), strictly increasing (stack never holds more than one item).

:::q Follow-up: which other problems use a monotonic stack?
Daily temperatures (days until a warmer day), stock span, largest rectangle in a histogram, trapping rain water, and "next smaller element". The recipe is the same: keep a stack in monotonic order, and *the moment an element breaks the order* you have found the answer for everything it pops. Store indices, not values, so you can compute distances.
:::

### Queue using two stacks

**Problem.** Implement a FIFO queue using only stack operations.

**Intuition.** One stack reverses order; two stacks reverse it twice, giving FIFO. Pushes go to an *inbox* stack. When you need to dequeue and the *outbox* is empty, pour the whole inbox into the outbox - the oldest element ends up on top. Elements are only moved when the outbox is empty, so each element is moved at most once.

**Approach.**
1. `Enqueue`: push onto `_in`.
2. `Dequeue`/`Peek`: if `_out` is empty, pop everything from `_in` and push onto `_out`; then pop/peek `_out`.

```csharp
public class QueueViaStacks<T>
{
    private readonly Stack<T> _in = new();
    private readonly Stack<T> _out = new();

    public int Count => _in.Count + _out.Count;

    public void Enqueue(T item) => _in.Push(item);

    public T Dequeue()
    {
        Shift();
        return _out.Pop();            // throws InvalidOperationException when empty
    }

    public T Peek()
    {
        Shift();
        return _out.Peek();
    }

    private void Shift()
    {
        if (_out.Count > 0) return;   // only refill when the outbox is empty
        while (_in.Count > 0)
            _out.Push(_in.Pop());
    }
}
// Enqueue 1,2,3 -> Dequeue 1 -> Enqueue 4 -> Dequeue 2, 3, 4
```

**Complexity.** `Enqueue` O(1). `Dequeue` is O(n) in the worst case but **amortised O(1)**, because each element is pushed and popped at most twice in its whole life.

**Edge cases.** Dequeue on empty, interleaved enqueue/dequeue (do *not* shift while the outbox still has items - that breaks ordering), peek.

:::q Why is the amortised cost O(1) even though one Dequeue can cost O(n)?
Count total work over `m` operations: each element is pushed to `_in` once, moved to `_out` once, and popped once - at most 3 steps per element. So `m` operations cost O(m) in total, i.e. O(1) per operation on average. This is *amortised* analysis, not average-case: there is no randomness, it is a worst-case total bound.
:::

### Stack using queue(s)

**Problem.** Implement a LIFO stack using only queue operations.

**Intuition.** A queue returns the *oldest* element, a stack the *newest*. Make the newest element the oldest: after enqueueing a new item into a single queue, rotate the older `n-1` items behind it. Then the front is always the latest push. That makes `Push` O(n) and `Pop`/`Peek` O(1). The two-queue alternative keeps `Push` O(1) and makes `Pop` O(n).

```csharp
// One queue: Push O(n), Pop/Peek O(1).
public class StackViaQueue<T>
{
    private readonly Queue<T> _q = new();

    public int Count => _q.Count;

    public void Push(T item)
    {
        _q.Enqueue(item);
        for (int i = 0; i < _q.Count - 1; i++)
            _q.Enqueue(_q.Dequeue());      // rotate older items behind the new one
    }

    public T Pop() => _q.Dequeue();
    public T Peek() => _q.Peek();
}

// Two queues: Push O(1), Pop O(n).
public class StackViaTwoQueues<T>
{
    private Queue<T> _main = new();
    private Queue<T> _helper = new();

    public void Push(T item) => _main.Enqueue(item);

    public T Pop()
    {
        if (_main.Count == 0) throw new InvalidOperationException("Stack is empty.");
        while (_main.Count > 1)
            _helper.Enqueue(_main.Dequeue());   // move all but the newest
        T top = _main.Dequeue();
        (_main, _helper) = (_helper, _main);    // swap roles
        return top;
    }
}
// Push 1,2,3 -> Pop gives 3, 2, 1
```

**Complexity.** One-queue version: `Push` O(n), `Pop`/`Peek` O(1), space O(n). Two-queue version: `Push` O(1), `Pop` O(n).

**Edge cases.** Pop on empty, single item, alternating push/pop.

:::q Follow-up: design a stack that returns the minimum in O(1).
Keep a second stack of running minimums (or store `(value, minSoFar)` pairs). On push, also push `min(value, currentMin)`; on pop, pop both; `GetMin` is the top of the min stack. All operations O(1), space O(n). It is the standard "Min Stack" interview problem.
:::
