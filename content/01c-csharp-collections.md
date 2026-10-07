## Collections

Two namespaces: `System.Collections` (legacy, non-generic, stores `object`, boxes value types) and `System.Collections.Generic` (type-safe, no boxing). In new code always use the generic ones. Running example: products and orders in an e-commerce shop.

```csharp
public record Product(string Sku, string Name, decimal Price);
```

### Array

**Definition.** A fixed-length, zero-based, contiguous block of elements of one type. Length is set at creation and never changes. It is a reference type even when it holds `int`s.

**Why it matters.** It is the fastest collection (one allocation, cache-friendly, JIT-optimised bounds checks) and the building block under `List<T>`, `Dictionary`, `Queue` and `Stack`.

```csharp
int[] scores = new int[5];                    // [0,0,0,0,0]
int[] primes = [2, 3, 5, 7, 11];              // collection expression (C# 12)
Console.WriteLine(primes[^1]);                // 11   index from end
int[] middle = primes[1..4];                  // [3,5,7]  range = a COPY for arrays
Span<int> view = primes.AsSpan(1, 3);         // slice WITHOUT copying

int[,]  grid   = new int[3, 3];               // rectangular (one block)
int[][] jagged = [[1], [2, 3], [4, 5, 6]];    // array of arrays, rows may differ

Array.Sort(primes);
int pos = Array.BinarySearch(primes, 7);      // 3 (array must be sorted)
Array.Resize(ref primes, 10);                 // allocates a NEW array and copies
// primes[10] = 1;                            // IndexOutOfRangeException

object[] objs = new string[2];                // array covariance compiles...
// objs[0] = 42;                              // ...ArrayTypeMismatchException at run time
```

:::warn Array gotchas
Array covariance is a legacy unsafe feature (the runtime checks every store into an `object[]` backed by a `string[]`). `IList<T>.Add` on an array throws `NotSupportedException` because arrays implement `IList<T>` but have fixed size. `Array.Empty<T>()` or `[]` returns a cached empty array: do not `new T[0]` repeatedly.
:::

### ArrayList

**Definition.** The pre-generics (.NET 1.0) dynamic array: `ArrayList` stores `object`, so every value type is boxed and every read needs a cast.

```csharp
var al = new ArrayList { 1, "two", 3.0 };      // compiles: no type safety
int first = (int)al[0]!;                       // unbox
// int bad = (int)al[1]!;                      // InvalidCastException at run time
// With generics: List<int> numbers = [1, 2, 3];   // no boxing, compile-time safety
```

Costs: a heap allocation per element (24 bytes per boxed `int`), extra GC work, runtime casts that fail late. It survives only for legacy APIs. The same applies to `Hashtable`, non-generic `Queue`/`Stack` and `SortedList`.

:::q Why shouldn't you use ArrayList in new code?
It stores `object`: boxing for value types, no compile-time type checking, runtime `InvalidCastException`s, and slower iteration. `List<T>` gives the same dynamic-array behaviour with type safety and no boxing, so there is no reason to prefer `ArrayList`.
:::

### List

**Definition.** `List<T>` is a resizable array: an internal `T[]` plus a count. It is the default collection for "an ordered list of things".

**How it grows.** Capacity starts at 0, becomes 4 on the first `Add`, then doubles (8, 16, 32...). When full, it allocates a bigger array and copies. That makes `Add` **amortised O(1)**. Pre-size with `new List<T>(capacity)` when you know the count.

```csharp
var l = new List<int>();
Console.WriteLine(l.Capacity);          // 0
l.Add(1);   Console.WriteLine(l.Capacity);   // 4
l.AddRange([2, 3, 4, 5]); Console.WriteLine(l.Capacity);   // 8

List<Product> catalog =
[
    new("P1", "Mouse", 499m),
    new("P2", "Keyboard", 1299m),
    new("P3", "Cable", 0m),
];

catalog.Insert(0, new("P0", "Monitor", 8999m));   // O(n): shifts everything right
var cheap = catalog.FindAll(p => p.Price < 1000m);
catalog.Sort((a, b) => a.Price.CompareTo(b.Price));   // in place, introsort, not stable

// WRONG: modifying while enumerating
// foreach (var p in catalog) { if (p.Price == 0) catalog.Remove(p); }
//   -> InvalidOperationException: Collection was modified
catalog.RemoveAll(p => p.Price == 0m);                // correct and one pass
```

- `Contains`, `IndexOf`, `Remove(item)` are **O(n)**. If you call them in a loop over big data, use a `HashSet<T>` or `Dictionary` (O(1)).
- `foreach` on `List<T>` uses a struct enumerator (no allocation) and a version check, hence the exception when the list changes mid-loop.
- `list.Sort()` is unstable; `OrderBy` (LINQ) is stable but allocates a new sequence.

:::q List vs Array?
Array: fixed size, fastest, multi-dimensional support. `List<T>`: dynamic size with amortised O(1) append, rich API, but a small overhead. If the count is fixed and known (a buffer, a lookup table) use an array or `Span<T>`; for a collection that grows or shrinks use `List<T>`.
:::

### Dictionary

**Definition.** `Dictionary<TKey, TValue>` is a hash table: key to value lookup in **O(1) on average**. Keys are unique and non-null; values may be anything.

```csharp
var stock = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase)
{
    ["P1"] = 10,
    ["P2"] = 0,
};

stock["P3"] = 7;                      // indexer: add OR overwrite
stock.Add("P4", 1);                   // throws ArgumentException if the key exists
stock.TryAdd("P4", 99);               // false: no change, no exception
Console.WriteLine(stock["p1"]);       // 10 (case-insensitive comparer)

// One lookup, no exception: the idiomatic read
if (stock.TryGetValue("P2", out int qty) && qty > 0) { /* in stock */ }
int safe = stock.GetValueOrDefault("P9", 0);

// Anti-pattern: two hash lookups
if (stock.ContainsKey("P1")) { var v = stock["P1"]; }

// Counting words: one lookup, mutate in place (using System.Runtime.InteropServices)
var counts = new Dictionary<string, int>();
foreach (var w in "to be or not to be".Split(' '))
    CollectionsMarshal.GetValueRefOrAddDefault(counts, w, out _)++;   // to=2, be=2 ...

foreach (var (sku, count) in stock)      // KeyValuePair deconstruction
    Console.WriteLine($"{sku}: {count}");
```

#### How a Dictionary works internally

```text
Add("apple", 3):
  1. h      = comparer.GetHashCode("apple")
  2. bucket = h % buckets.Length         (length is a prime)   -> say 2
  3. walk bucket 2's chain: same hash AND Equals(key)?  -> duplicate / found
  4. otherwise append a new entry to entries[] and link it at the chain head

buckets[]  (index of chain head in entries[], -1 = empty)
  [0] -1
  [1] -1
  [2]  2 --+
           v
entries[]  (append order; each holds hash, key, value, next)
  [0] pear    next = -1
  [1] fig     next =  0      fig and pear collided: same bucket
  [2] apple   next =  1      chain: apple -> fig -> pear
```

- Two arrays: `buckets` (each holds the head of a chain) and `entries` (a struct per item: stored hash code, key, value, `next` index). That is *separate chaining* implemented with array indexes, not object nodes, so it stays cache-friendly.
- **Lookup:** compute hash, pick a bucket, walk the chain comparing the stored hash first and `Equals` only when hashes match.
- **Collisions** (different keys landing in the same bucket) just lengthen a chain. With a good hash function chains stay at about 1-2 items, so O(1) average.
- **Resize:** when `entries` is full the dictionary allocates arrays about twice as big (next prime), and **rehashes every entry**. One resize is O(n), but amortised across inserts `Add` stays O(1). Pre-size with `new Dictionary<K,V>(expectedCount)` to avoid resizes.
- **Worst case O(n):** all keys with the same hash degenerate to one long chain. .NET randomises string hash codes per process (so they differ between runs and attackers cannot craft colliding keys, "HashDoS"). Never persist or compare `GetHashCode()` values across processes.
- **Order:** enumeration order is *not guaranteed*. After removals, freed slots are reused. If you need insertion order use `OrderedDictionary<TKey, TValue>` (.NET 9); for sorted keys use `SortedDictionary`.
- Not thread-safe for concurrent writes: use `ConcurrentDictionary` (see Multithreading).

:::q How does Dictionary work internally and what is its time complexity?
It hashes the key with `GetHashCode`, maps the hash to a bucket with modulo on a prime-sized array, then walks a short chain comparing hash and `Equals`. Lookup/insert/delete are O(1) on average, O(n) in the worst case with many collisions. It resizes by roughly doubling and rehashing, so inserts are amortised O(1).
:::

### GetHashCode and Equals contract

Hash-based collections (`Dictionary`, `HashSet`, `ConcurrentDictionary`, LINQ `Distinct`/`GroupBy`) depend on this contract. Break it and lookups silently fail.

**Rules**

1. If `a.Equals(b)` is `true`, then `a.GetHashCode() == b.GetHashCode()`. (The reverse is not required: different objects may share a hash.)
2. `GetHashCode()` must return the same value for the lifetime of the object while it is in a collection: **never hash mutable fields**.
3. `Equals` must be reflexive, symmetric, transitive, consistent, and `x.Equals(null)` is `false`.
4. Override **both together** (compiler warning CS0659 if you only override `Equals`). Implement `IEquatable<T>` for speed and to avoid boxing in structs.

```csharp
// BROKEN: Equals overridden, GetHashCode not (uses reference-based hash)
class BadSku
{
    public string Code = "";
    public override bool Equals(object? o) => o is BadSku s && s.Code == Code;
}
var set = new HashSet<BadSku> { new() { Code = "A1" } };
Console.WriteLine(set.Contains(new BadSku { Code = "A1" }));   // False! different hash

// CORRECT: immutable value object
public sealed class Sku : IEquatable<Sku>
{
    public string Code { get; }
    public Sku(string code) => Code = code.Trim().ToUpperInvariant();

    public bool Equals(Sku? other) => other is not null && Code == other.Code;
    public override bool Equals(object? obj) => Equals(obj as Sku);
    public override int GetHashCode() => Code.GetHashCode();   // or HashCode.Combine(a, b)
    public static bool operator ==(Sku? l, Sku? r) => l?.Equals(r) ?? r is null;
    public static bool operator !=(Sku? l, Sku? r) => !(l == r);
}

// Records generate all of this from their members (value equality + hash)
public record ProductKey(string Sku, string Warehouse);   // works as a dictionary key

// MUTABLE key: lookup breaks after mutation
class Key
{
    public int Id;
    public override int GetHashCode() => Id;
    public override bool Equals(object? o) => o is Key k && k.Id == Id;
}
var k1 = new Key { Id = 1 };
var d = new Dictionary<Key, string> { [k1] = "x" };
k1.Id = 2;
Console.WriteLine(d.ContainsKey(k1));   // False: stored under hash 1, now looked up as 2
```

Custom comparers when you do not own the type: `new HashSet<string>(StringComparer.OrdinalIgnoreCase)` or any `IEqualityComparer<T>`.

:::warn Good hash code
Combine the same fields `Equals` compares, with `HashCode.Combine(Sku, Warehouse)`. Never return a constant (everything collides, lookups become O(n)); never use `DateTime.Now`/random values.
:::

### HashSet

**Definition.** `HashSet<T>` is an unordered set of unique elements built on the same bucket/entry hashing as `Dictionary` (just no values). `Add`, `Remove`, `Contains` are O(1) average.

```csharp
var tags = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "sale", "new" };
bool added = tags.Add("SALE");           // false: duplicate (case-insensitive)
Console.WriteLine(tags.Count);           // 2

// Dedupe a list in O(n)
List<int> ids = [1, 2, 2, 3, 3, 3];
HashSet<int> unique = [.. ids];          // collection expression with spread

var a = new HashSet<int> { 1, 2, 3, 4 };
var b = new HashSet<int> { 3, 4, 5 };
var union = new HashSet<int>(a); union.UnionWith(b);              // 1,2,3,4,5
var both  = new HashSet<int>(a); both.IntersectWith(b);           // 3,4
var onlyA = new HashSet<int>(a); onlyA.ExceptWith(b);             // 1,2
var xor   = new HashSet<int>(a); xor.SymmetricExceptWith(b);      // 1,2,5
Console.WriteLine(a.Overlaps(b));        // True
Console.WriteLine(new HashSet<int> { 3, 4 }.IsSubsetOf(a));       // True

// Fast membership instead of List.Contains in a loop (O(n*m) -> O(n+m))
var blocked = new HashSet<string>(blockedCustomerIds);
var allowed = orders.Where(o => !blocked.Contains(o.CustomerId));
```

For read-mostly lookup tables built once at startup, `FrozenSet<T>` / `FrozenDictionary<K,V>` (`.ToFrozenSet()`, .NET 8, `System.Collections.Frozen`) are slower to create but faster to read than their mutable counterparts. `SortedSet<T>` keeps elements ordered (O(log n)).

### Queue

**Definition.** `Queue<T>` is **FIFO** (first in, first out), implemented as a circular array. `Enqueue` and `Dequeue` are O(1) (amortised for growth).

```csharp
var jobs = new Queue<string>();
jobs.Enqueue("resize-image-1");
jobs.Enqueue("send-email-7");
Console.WriteLine(jobs.Peek());                 // resize-image-1 (not removed)
while (jobs.TryDequeue(out var job))            // safe: no exception when empty
    Console.WriteLine($"Processing {job}");

// PriorityQueue (.NET 6): smallest priority value comes out first
var pq = new PriorityQueue<string, int>();
pq.Enqueue("refund", 1);
pq.Enqueue("newsletter", 5);
pq.Enqueue("payment-failed", 0);
Console.WriteLine(pq.Dequeue());                // payment-failed
```

Use cases: background job processing, BFS traversal, request buffering. `Dequeue` on empty throws `InvalidOperationException`: use `TryDequeue`. `Queue<T>` is not thread-safe: use `ConcurrentQueue<T>` or `Channel<T>` between producers and consumers. `PriorityQueue` is O(log n) per operation, has no stable order for equal priorities and no `Contains`/update.

### Stack

**Definition.** `Stack<T>` is **LIFO** (last in, first out), array-backed. `Push`, `Pop`, `Peek` are O(1).

```csharp
var undo = new Stack<string>();
undo.Push("typed A"); undo.Push("typed B"); undo.Push("deleted line");
Console.WriteLine(undo.Pop());       // deleted line  (undo the last action)
Console.WriteLine(undo.Peek());      // typed B       (look, don't remove)

static bool IsBalanced(string s)     // classic interview problem
{
    var stack = new Stack<char>();
    foreach (char ch in s)
    {
        if (ch is '(' or '[' or '{') stack.Push(ch);
        else if (ch is ')' or ']' or '}')
        {
            if (!stack.TryPop(out char open) || !Matches(open, ch)) return false;
        }
    }
    return stack.Count == 0;

    static bool Matches(char o, char c) =>
        (o, c) is ('(', ')') or ('[', ']') or ('{', '}');
}
Console.WriteLine(IsBalanced("{[()]}"));   // True
Console.WriteLine(IsBalanced("{[(])}"));   // False
```

Use cases: undo/redo, expression evaluation, DFS, parsing (balanced brackets), the call stack itself. Enumerating a `Stack<T>` yields items in pop (LIFO) order.

### LinkedList

**Definition.** `LinkedList<T>` is a **doubly linked list** of `LinkedListNode<T>` objects (each with `Previous`/`Next`). Insert or remove at a node you already hold is O(1); there is no indexer and finding by position or value is O(n).

```csharp
var ll = new LinkedList<int>([1, 2, 3]);
var two = ll.Find(2)!;                // O(n) to find
ll.AddAfter(two, 99);                 // O(1): 1,2,99,3
ll.AddFirst(0);                       // 0,1,2,99,3
ll.Remove(two);                       // O(1) given the node
// ll[2]  -> no indexer
```

Reality check: each element is a separate heap object (about 40 bytes of overhead on 64-bit), nodes are scattered in memory, and CPU caches love arrays. In practice `List<T>` beats `LinkedList<T>` for almost everything, even middle inserts, until the list is very large. Its real use is when you hold node references and move/remove items constantly, such as an **LRU cache**:

```csharp
public class LruCache<TKey, TValue>(int capacity) where TKey : notnull
{
    private readonly Dictionary<TKey, LinkedListNode<(TKey Key, TValue Value)>>
        _map = new();
    private readonly LinkedList<(TKey Key, TValue Value)> _order = new();  // first = newest

    public bool TryGet(TKey key, out TValue? value)
    {
        if (_map.TryGetValue(key, out var node))
        {
            _order.Remove(node); _order.AddFirst(node);       // O(1) move-to-front
            value = node.Value.Value; return true;
        }
        value = default; return false;
    }

    public void Put(TKey key, TValue value)
    {
        if (_map.Remove(key, out var old)) _order.Remove(old);
        else if (_map.Count == capacity)
        {
            var last = _order.Last!;                          // evict least recently used
            _order.RemoveLast();
            _map.Remove(last.Value.Key);
        }
        _map[key] = _order.AddFirst((key, value));
    }
}
```

### IEnumerable, ICollection, IList, IDictionary

**Definition.** A hierarchy of interfaces describing *what you can do* with a collection. Each level adds capabilities.

```text
IEnumerable<T>              GetEnumerator()  ->  forward-only iteration (foreach, LINQ)
 |-- IReadOnlyCollection<T>     + Count
 |    '-- IReadOnlyList<T>      + this[int]  (read-only)
 '-- ICollection<T>             + Count, Add, Remove, Contains, Clear, CopyTo
      |-- IList<T>              + this[int], IndexOf, Insert, RemoveAt
      |-- ISet<T>               + UnionWith, IntersectWith, ExceptWith, ...
      '-- IDictionary<K,V>      + this[key], Keys, Values, TryGetValue, ContainsKey
                                  (it is ICollection<KeyValuePair<K,V>>)
```

| Interface | Gives you | Implemented by |
|---|---|---|
| `IEnumerable<T>` | iterate once, forward, lazily; no Count | everything, plus `yield` iterators and LINQ results |
| `ICollection<T>` | Count + add/remove/contains | `List<T>`, `HashSet<T>`, `Dictionary` |
| `IList<T>` | indexed access, insert/remove at position | `List<T>`, arrays |
| `IDictionary<K,V>` | key lookup | `Dictionary`, `SortedDictionary` |
| `IReadOnlyList<T>` / `IReadOnlyDictionary<K,V>` | read-only views (no Add) | `List<T>`, arrays, `Dictionary` |

```csharp
// foreach is a pattern: GetEnumerator() / MoveNext() / Current
IEnumerable<int> Evens(IEnumerable<int> src)
{
    foreach (var n in src)
        if (n % 2 == 0) yield return n;      // lazy: runs when you iterate
}

// Multiple enumeration trap
IEnumerable<Order> orders = repo.GetPendingOrders();     // may be a lazy query
if (orders.Any())                              // enumeration #1 (runs the query)
    Console.WriteLine(orders.Count());         // enumeration #2 (runs it AGAIN)
var snapshot = orders.ToList();                // materialise once, then reuse
```

Design guidance:

- **Parameters:** accept the *least specific* type you need: `IEnumerable<T>` to just iterate, `IReadOnlyCollection<T>` for Count, `IReadOnlyList<T>` for indexing; `IList<T>`/`ICollection<T>` only if you mutate.
- **Return types:** return `IReadOnlyList<T>` (or a concrete immutable type) from public APIs so callers cannot mutate your internals.
- `IEnumerable<out T>` is covariant (`IEnumerable<Dog>` converts to `IEnumerable<Animal>`); `IList<T>` is invariant (it allows writes).
- `Queue<T>` and `Stack<T>` implement `IEnumerable<T>` and `IReadOnlyCollection<T>` but **not** `ICollection<T>` or `IList<T>`.

:::q Why accept IEnumerable as a parameter type but return IReadOnlyList?
A parameter should demand as little as possible, so many callers can pass arrays, lists, sets or LINQ queries. A return type should promise useful, safe capabilities: count and index access, with no mutation. Returning `IEnumerable<T>` hides whether it is lazy and invites multiple enumeration; returning `List<T>` lets callers change internal state.
:::

### IEnumerable vs IQueryable

**Definition.** `IEnumerable<T>` runs LINQ **in memory** over objects you already have; lambdas are compiled delegates (`Func<T,bool>`). `IQueryable<T>` (in `System.Linq`) carries a LINQ **expression tree** (`Expression<Func<T,bool>>`) that a provider such as EF Core translates into another language, typically SQL.

| | `IEnumerable<T>` | `IQueryable<T>` |
|---|---|---|
| Executes | in your process | in the data source (SQL Server, etc.) |
| Lambda is | `Func<T, bool>` (compiled code) | `Expression<Func<T, bool>>` (data to inspect) |
| Filtering/sorting happens | after all data is loaded | in the database, before loading |
| Execution | deferred | deferred (until `ToList`, `First`, `foreach`, `Count`...) |
| Use for | in-memory lists, small data | EF Core, OData, remote providers |
| Can call any C# method in predicate | yes | only what the provider can translate |

```csharp
// IQueryable: composed, then translated to ONE SQL statement
IQueryable<Order> q = db.Orders.Where(o => o.Total > 1000m);       // nothing sent yet
q = q.OrderByDescending(o => o.CreatedUtc).Take(20);               // still composing
List<Order> page = await q.ToListAsync();
// SELECT TOP(20) ... FROM Orders WHERE Total > 1000 ORDER BY CreatedUtc DESC

// IEnumerable too early: the WHOLE table is loaded, then filtered in C#
var bad = db.Orders.ToList().Where(o => o.Total > 1000m).Take(20).ToList();
// SELECT * FROM Orders   -> millions of rows into memory

// Silent trap: repository returns IEnumerable, so the caller's Where is in-memory
IEnumerable<Order> GetOrders() => db.Orders;                    // typed as IEnumerable
var slow = GetOrders().Where(o => o.Total > 1000m).ToList();    // Enumerable.Where, no SQL

// Non-translatable code inside an expression tree
// db.Orders.Where(o => IsVip(o.CustomerId)).ToList();
//   -> InvalidOperationException: could not be translated (EF Core 3+)
```

:::scenario The orders page times out
The API returned `IEnumerable<Order>` from a repository method; the controller added `.Where(...)` and `.Skip/Take` for paging. Logs show `SELECT * FROM Orders` with 3 million rows, and memory spikes. Cause: once the static type is `IEnumerable<T>`, LINQ operators bind to `Enumerable` (in memory). Fix: keep the query as `IQueryable<T>` until the final `ToListAsync()`, push filter, sort and paging into the query, project to a DTO with `Select`, and have the repository expose intent-based methods (`GetPageAsync(filter, page)`) instead of leaking `IQueryable` across layers.
:::

:::tip Interviewers' key points
Say three things: expression tree vs delegate, where execution happens (DB vs memory), and the danger of `ToList()`/`AsEnumerable()` before filtering.
:::

### Complexity (Big-O) cheat sheet

| Collection | Index / lookup by key | Search by value | Add | Remove / Insert in middle |
|---|---|---|---|---|
| `T[]` | O(1) | O(n); O(log n) if sorted | fixed size (resize O(n)) | O(n) shift |
| `List<T>` | O(1) | O(n) | O(1) amortised at end | O(n) |
| `LinkedList<T>` | O(n) | O(n) | O(1) at ends or after a node | O(1) given node, O(n) to find |
| `Dictionary<K,V>` | O(1) avg, O(n) worst | O(n) | O(1) amortised | O(1) |
| `HashSet<T>` | Contains O(1) avg | n/a | O(1) amortised | O(1) |
| `SortedDictionary` / `SortedSet` | O(log n) | O(n) | O(log n) | O(log n) |
| `SortedList<K,V>` | O(log n) | O(n) | O(n) (array shift) | O(n) |
| `Queue<T>` | Peek O(1) | O(n) | Enqueue O(1) amortised | Dequeue O(1) |
| `Stack<T>` | Peek O(1) | O(n) | Push O(1) amortised | Pop O(1) |
| `PriorityQueue` | Peek O(1) | O(n) | Enqueue O(log n) | Dequeue O(log n) |

### Which collection should I choose?

| I need... | Use | Why |
|---|---|---|
| Fixed-size, hot loop, interop, buffers | `T[]` / `Span<T>` | fastest, no overhead |
| Ordered list that grows, index access | `List<T>` | the default |
| Lookup by key (id to entity) | `Dictionary<K,V>` | O(1) |
| Unique items, fast "is it in there?" | `HashSet<T>` | O(1) Contains, set algebra |
| Sorted keys/items, range scans | `SortedDictionary` / `SortedSet` | O(log n), ordered iteration |
| Keep insertion order and key lookup | `OrderedDictionary<K,V>` (.NET 9) | ordered + keyed |
| FIFO processing | `Queue<T>` (`Channel<T>` across threads) | O(1) enqueue/dequeue |
| Process by priority | `PriorityQueue<E,P>` | O(log n) min-heap |
| LIFO, undo, DFS | `Stack<T>` | O(1) push/pop |
| Frequent O(1) insert/remove at a held node (LRU) | `LinkedList<T>` + `Dictionary` | node-level splicing |
| Built once, read many (config, lookup tables) | `FrozenDictionary` / `FrozenSet` | optimised reads |
| Share across threads safely | `ConcurrentDictionary`, `ConcurrentQueue`, `ImmutableArray` | thread safety |
| Expose to callers without mutation | `IReadOnlyList<T>` / `IReadOnlyDictionary` | encapsulation |

## Quick-fire Q&A: Fundamentals, OOP & Collections

:::q Value type vs reference type in one breath?
Value types hold their data directly and are copied on assignment (`int`, `struct`, `enum`); reference types hold a reference to a heap object and assignment copies the reference (`class`, `string`, arrays, `record`). Value types are zero-initialised and not null; reference types default to null. "Stack vs heap" is an implementation detail; the real difference is copy semantics.
:::

:::q What is boxing and what does it cost?
Converting a value type to `object` or an interface: the runtime allocates a heap object and copies the value in; unboxing type-checks and copies it out. It costs an allocation (24 bytes for an `int`), a copy and GC pressure. Avoid it with generics and `IEquatable<T>`.
:::

:::q Why is string immutable and when do you use StringBuilder?
Immutability gives thread-safety, stable hash codes and interning. Each modification allocates a new string, so repeated concatenation in a loop is O(n squared). Use `StringBuilder` (or `string.Join`) for many appends; plain `+` or interpolation is fine for a few pieces.
:::

:::q const vs readonly vs static readonly?
`const` is a compile-time value inlined into callers (primitives and strings only, implicitly static). `readonly` is assigned once at runtime, in the declaration or constructor, per instance. `static readonly` is assigned once per type at runtime and can hold any type. Use `static readonly` for values that may change between releases; a changed `const` requires recompiling every consumer.
:::

:::q ref vs out vs in?
All pass by reference. `ref`: caller initialises, method may read and write. `out`: caller need not initialise, method must assign before returning (the `TryParse` pattern). `in`: read-only reference, avoids copying large structs.
:::

:::q Abstract class vs interface?
Abstract class: single inheritance, can hold state, constructors, concrete and abstract members; models is-a with shared code. Interface: a contract with multiple implementation, no instance state (default methods allowed since C# 8); models can-do and is what you inject and mock. Start with an interface; add a base class when implementations share real code.
:::

:::q What is the difference between method overriding, overloading and hiding?
Overloading: same name, different parameters, chosen at compile time by static types. Overriding: `virtual` in base, `override` in derived, chosen at run time by the object's actual type. Hiding (`new`): a separate member with the same name, chosen by the variable's static type, and normally a design smell.
:::

:::q Explain SOLID in one line each.
S: one reason to change per class. O: add behaviour by adding classes, not editing working ones. L: subtypes must work wherever the base type is used (no throwing `NotSupportedException` overrides). I: many small interfaces beat one fat one. D: depend on abstractions and inject them rather than calling `new` on concrete dependencies.
:::

:::q Composition or inheritance?
Prefer composition (has-a): flexible at run time, loosely coupled to an interface, easy to test. Use inheritance for a true is-a with stable behaviour and for framework extension points such as `BackgroundService` or `Exception`.
:::

:::q Array vs List vs LinkedList?
Array: fixed size, fastest, O(1) index. `List<T>`: resizable array, O(1) index, amortised O(1) append, O(n) middle insert. `LinkedList<T>`: O(1) insert/remove at a held node but O(n) search and poor cache locality, so `List<T>` wins in nearly every real case.
:::

:::q How does Dictionary work and what happens on a hash collision?
It calls `GetHashCode`, maps it to a bucket (hash modulo a prime-sized array), and chains entries sharing a bucket. Lookup compares stored hash then `Equals`. Collisions lengthen a chain, so average O(1) and worst case O(n). It resizes about 2x and rehashes when full.
:::

:::q What is the GetHashCode and Equals contract?
Equal objects must return equal hash codes; the hash must not change while the object is a key; `Equals` must be reflexive, symmetric, transitive and consistent. Override both together (records do it for you), base the hash on the same immutable fields, and prefer `HashCode.Combine`.
:::

:::q HashSet vs List.Contains, and when do you use which?
`HashSet<T>.Contains` is O(1) average versus O(n) for a list, so use a set for membership tests, de-duplication and set algebra (`IntersectWith`, `ExceptWith`). Use a list when you need order, duplicates or index access.
:::

:::q IEnumerable vs IQueryable?
`IEnumerable<T>` filters in memory using delegates; `IQueryable<T>` builds an expression tree that EF Core translates to SQL so filtering happens in the database. Calling `ToList()` or `AsEnumerable()` before `Where` pulls the whole table into memory.
:::

:::q Why does modifying a List inside foreach throw?
`List<T>` keeps a version counter incremented on every change; its enumerator compares it on each `MoveNext` and throws `InvalidOperationException` if it changed. Collect items to remove first, use `RemoveAll(predicate)`, or iterate backwards with a `for` loop.
:::
