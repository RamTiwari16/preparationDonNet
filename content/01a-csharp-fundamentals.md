## C# Fundamentals

### Data types

**Definition.** C# is statically typed: every variable has a type known at compile time. Built-in types are aliases for .NET types in the `System` namespace (`int` is `System.Int32`, `string` is `System.String`).

**Why it matters.** The type decides memory size, default value, copy semantics and which operations are legal. Picking `double` for money, or `int` for a counter that can pass 2.1 billion, are classic production bugs.

| Type | Size | Range / note | Default |
|---|---|---|---|
| `byte` / `sbyte` | 1 B | 0..255 / -128..127 | 0 |
| `short` / `ushort` | 2 B | -32,768..32,767 / 0..65,535 | 0 |
| `int` / `uint` | 4 B | about +-2.1 billion / 0..4.29 billion | 0 |
| `long` / `ulong` | 8 B | about +-9.2e18 / 0..1.8e19 | 0 |
| `float` | 4 B | ~7 significant digits, binary | 0f |
| `double` | 8 B | ~15-17 digits, binary (default for `1.5`) | 0d |
| `decimal` | 16 B | 28-29 digits, base-10 (suffix `m`) | 0m |
| `bool` | 1 B | `true` / `false` | false |
| `char` | 2 B | one UTF-16 code unit | `'\0'` |
| `string` | ref | immutable sequence of `char` | null |
| `object` | ref | root of every type | null |

```csharp
int    age     = 30;
long   views   = 9_000_000_000;   // digit separator; needs long
double ratio   = 0.1 + 0.2;
decimal price  = 19.99m;          // money => decimal, always
char   grade   = 'A';
DateOnly due   = new(2026, 12, 31);   // .NET 6+: date without time
Guid   orderId = Guid.NewGuid();

Console.WriteLine(0.1 + 0.2 == 0.3);     // False  (binary floating point)
Console.WriteLine(0.1m + 0.2m == 0.3m);  // True   (decimal is base 10)

[Flags] enum Permission { None = 0, Read = 1, Write = 2, Delete = 4 }
var rw = Permission.Read | Permission.Write;     // bitwise combine
Console.WriteLine(rw.HasFlag(Permission.Write)); // True
```

:::warn Money is decimal, never double
`double` cannot represent 0.1 exactly. Summing prices in `double` drifts by fractions of a cent and breaks equality checks. Use `decimal` for money and `Math.Round(x, 2, MidpointRounding.AwayFromZero)` when business rules say "round half up".
:::

:::q What is the difference between float, double and decimal?
`float` and `double` are IEEE-754 binary floating point: fast, huge range, but cannot represent most decimal fractions exactly. `decimal` is a 128-bit base-10 type with 28-29 significant digits: slower (software-implemented) but exact for decimal fractions, so it is the right choice for money. Say: "double for science and graphics, decimal for money."
:::

### Value type vs Reference type

**Definition.** A *value type* (`struct`, `enum`, primitives) holds its data directly in the variable. A *reference type* (`class`, `interface`, `delegate`, `record`, `string`, arrays) holds a reference to an object on the managed heap.

**Why it matters.** Assignment semantics, equality, nullability, allocation cost and GC pressure all follow from this one distinction.

| | Value type | Reference type |
|---|---|---|
| Examples | `int`, `bool`, `DateTime`, `struct`, `enum` | `class`, `string`, `T[]`, `record`, delegates |
| Assignment | copies the data | copies the reference |
| Default | zero-initialised | `null` |
| `null` allowed | only as `T?` | yes (check nullable annotations) |
| Equality (`==`) | value (for built-ins) | reference unless overloaded |
| Inheritance | none (implicit `System.ValueType`) | single base class |
| Allocation | inline in container (stack/local, field, array) | heap, tracked by GC |

```csharp
struct PointS { public int X; }
class  PointC { public int X; }

var a = new PointS { X = 1 }; var b = a; b.X = 99;   // a.X == 1  (copy)
var c = new PointC { X = 1 }; var d = c; d.X = 99;   // c.X == 99 (same object)

// Modern shapes: records give value-based equality + non-destructive mutation
public record Money(decimal Amount, string Currency);           // reference type
public readonly record struct Point(int X, int Y);              // value type

var m1 = new Money(10m, "INR");
var m2 = m1 with { Amount = 20m };      // copy with one change
Console.WriteLine(m1 == new Money(10m, "INR"));   // True (value equality)
```

#### Stack, heap and the GC (briefly)

```text
Stack (one per thread)               Managed heap (shared, GC-managed)
+---------------------+             +------------------------------+
| int count = 3       |             | Order { Id = 7, Lines = ... }|
| Order order  --------------------->                              |
| ref slot (ptr)      |             | List<OrderLine> ...          |
+---------------------+             +------------------------------+
 freed when method returns           freed when GC finds no references
```

- **Stack:** method frames, locals, parameters. Push/pop is just moving a pointer: extremely cheap, no GC.
- **Heap:** objects. Allocation is a fast bump-pointer; the cost is paid later by the garbage collector.
- **Generations:** new objects start in **Gen 0** (collected often, very cheap). Survivors are promoted to **Gen 1** (a buffer) and then **Gen 2** (long-lived; a full collection is expensive). Objects of **85,000 bytes or more** go on the **Large Object Heap**, which is collected with Gen 2, so large short-lived arrays hurt (use `ArrayPool<T>`).
- The "value types live on the stack" slogan is only partly true. A struct that is a field of a class, an element of an array, or captured by a lambda lives on the heap with its owner.

:::q Is a struct always allocated on the stack?
No, that is an implementation detail. Correct statement: value types have *copy semantics*. A struct field of a class lives on the heap inside that object; an `int[]` stores its ints inline on the heap; a boxed struct is a heap object. Locals may even live only in CPU registers.
:::

:::q When would you choose a struct over a class?
When the type is small (about 16 bytes or less), logically a single value (`Point`, `Money`, `DateRange`), immutable (`readonly struct`), short-lived and created in large numbers, so avoiding heap allocation helps. Otherwise use a class: large or mutable shared state, inheritance, or identity semantics.
:::

:::warn Mutable structs
`list[0].X = 5` does not compile for `List<PointS>` because the indexer returns a copy. Mutable structs also break when held in `readonly` fields (the compiler mutates a defensive copy). Make structs `readonly struct` or use `record struct` with `init` properties.
:::

### Variables and constants

**Definition.** A variable is a named storage location of a type. A constant is a value fixed at compile time (`const`) or after construction (`readonly`, next topics).

```csharp
int x;                         // declared, not assigned
// Console.WriteLine(x);       // CS0165: use of unassigned local variable
x = 10;

var total = 0m;                // inferred decimal
List<string> names = new();    // target-typed new (C# 9)
List<int> nums = [1, 2, 3];    // collection expression (C# 12)

const int MaxRetries = 3;      // compile-time constant, implicitly static
const string Currency = "INR";
```

- **Definite assignment:** reading an unassigned local is a compile error. Fields get default values automatically; locals do not.
- **Scope:** a local lives inside its `{ }` block and cannot be redeclared in a nested block.
- **Naming:** `camelCase` locals/parameters, `PascalCase` types/members/constants, `_camelCase` private fields.

### Type casting and conversions

**Definition.** Converting a value from one type to another.

| Kind | Syntax | Fails? | Example |
|---|---|---|---|
| Implicit (widening, safe) | none | never | `long l = intValue;` |
| Explicit cast | `(T)x` | may lose data or throw `InvalidCastException` | `int i = (int)3.99;` gives 3 |
| `as` | `x as T` | returns `null` on failure | `obj as string` |
| `is` pattern | `x is T t` | returns `false` | `if (obj is string s)` |
| `Convert.ToXxx` | `Convert.ToInt32(x)` | throws on bad format/overflow | null becomes 0 |
| `Parse` | `int.Parse(s)` | throws `FormatException` | |
| `TryParse` | `int.TryParse(s, out n)` | returns `false` | use for user input |

```csharp
double d = 3.99;
int trunc = (int)d;                    // 3 (truncates, does not round)
int r1 = Convert.ToInt32(2.5);         // 2 (banker's rounding: nearest even)
int r2 = Convert.ToInt32(3.5);         // 4

// User input: never Parse, always TryParse
string input = "42x";
if (int.TryParse(input, out int qty) && qty > 0)
    Console.WriteLine($"Qty {qty}");
else
    Console.WriteLine("Invalid quantity");   // this branch runs

// Culture matters for decimals
decimal p = decimal.Parse("1,234.50", CultureInfo.InvariantCulture);

// Reference conversions: is / as / pattern matching
object shape = new Circle(2.0);
if (shape is Circle c && c.Radius > 1) { /* c is definitely assigned here */ }
var circle = shape as Circle;          // null if not a Circle, never throws
var strict = (Circle)shape;            // throws InvalidCastException if wrong

string Describe(object o) => o switch
{
    null            => "nothing",
    int n when n < 0 => "negative int",
    int n           => $"int {n}",
    string { Length: 0 } => "empty string",
    string s        => $"string '{s}'",
    Circle { Radius: > 10 } => "big circle",
    Circle          => "circle",
    _               => o.GetType().Name,
};

record Circle(double Radius);
```

User-defined conversions use `implicit operator` (must never lose data or throw) or `explicit operator` (for lossy or throwing conversions).

#### checked and unchecked

Integer arithmetic **wraps silently by default** (`unchecked`). `checked` turns overflow into `OverflowException`.

```csharp
int big = int.MaxValue;
int wrapped = unchecked(big + 1);        // -2147483648 (default behaviour)
try { int boom = checked(big + 1); }     // throws
catch (OverflowException) { Console.WriteLine("overflow"); }

checked { long safe = (long)big * 2; }   // block form
// Whole project: <CheckForOverflowUnderflow>true</CheckForOverflowUnderflow>
// Constants fail at compile time: const int c = int.MaxValue + 1;  // CS0220
```

:::example Where overflow bites
A loyalty-points service stores points in `int` and multiplies by a campaign factor. Past 2,147,483,647 the value silently wraps negative. Fix: use `long`, and wrap financial arithmetic in `checked` so a bug becomes an exception in the logs instead of silent corruption.
:::

:::q What is the difference between `(int)x`, `Convert.ToInt32(x)` and `int.Parse(s)`?
The cast converts between numeric types and truncates doubles. `Convert.ToInt32` accepts many source types, rounds doubles to nearest-even and returns 0 for `null`. `int.Parse` is for strings only and throws on null/bad format. For untrusted strings use `int.TryParse`: no exception cost on the failure path.
:::

:::q `as` vs a direct cast vs `is`?
A direct cast throws `InvalidCastException` on mismatch. `as` returns `null` (reference/nullable types only). `is T t` tests and binds the variable in one step, and is the preferred modern form. Use a direct cast when a wrong type is a programming error you want to fail loudly on.
:::

### Boxing and unboxing

**Definition.** *Boxing* wraps a value type in a new `object` on the heap. *Unboxing* extracts it back with an explicit cast.

**Why it matters.** Every box is a heap allocation (24 bytes for an `int` on 64-bit: header + method table pointer + payload) and later GC work. Hidden boxing in hot paths is a top cause of allocation-heavy code.

```csharp
int n = 42;
object boxed = n;            // BOX: allocate, copy 42 into it
int back = (int)boxed;       // UNBOX: type check + copy out
// long bad = (long)boxed;   // InvalidCastException: must unbox to the EXACT type
long ok = (int)boxed;        // unbox to int, then widen

// Where boxing hides
IComparable cmp = n;                    // struct -> interface = box
Console.WriteLine("{0}", n);            // params object[] = box
var al = new ArrayList { 1, 2, 3 };     // non-generic collection = box per item
// Dictionary<MyStructKey, V> where MyStructKey lacks IEquatable<T> = box per lookup
```

Cost demo (numbers are typical; run BenchmarkDotNet on your machine):

```csharp
const int N = 10_000_000;

var sw = Stopwatch.StartNew();
var al = new ArrayList();
for (int i = 0; i < N; i++) al.Add(i);        // N boxes: ~240 MB of garbage
long s1 = 0;
foreach (int x in al) s1 += x;                // N unboxes
Console.WriteLine($"ArrayList: {sw.ElapsedMilliseconds} ms");

sw.Restart();
var list = new List<int>(N);                  // one 40 MB array, no boxes
for (int i = 0; i < N; i++) list.Add(i);
long s2 = 0;
foreach (int x in list) s2 += x;
Console.WriteLine($"List<int>: {sw.ElapsedMilliseconds} ms");
// Typical: the boxed version is several times slower and triggers many Gen0/Gen1 GCs;
// the generic version allocates once and stays cache-friendly.
```

In words: generics were added to .NET 2.0 precisely to remove this cost. `List<int>` stores ints contiguously; `ArrayList` stores 10 million pointers to 10 million separate heap objects.

:::q What is boxing, why is it expensive, and how do you avoid it?
Boxing copies a value type into a new heap object so it can be treated as `object` or an interface. It costs an allocation, a copy, a type check on unboxing, and GC pressure. Avoid it with generics (`List<T>`, `IEquatable<T>`, `where T : struct`), interpolated strings (`$""` uses handlers that do not box), and by not storing structs in `object`-typed members.
:::

### var, dynamic and object

| | `var` | `dynamic` | `object` |
|---|---|---|---|
| Type fixed at | compile time (inferred) | runtime (DLR) | compile time (`object`) |
| IntelliSense/compile checks | full | none | full, but need casts |
| Performance | same as explicit type | slowest (binder + call-site cache) | boxing for value types |
| Failure mode | compile error | `RuntimeBinderException` | `InvalidCastException` |
| Use for | everyday locals | COM/Office interop, `ExpandoObject`, rare JSON/scripting cases | truly heterogeneous storage, legacy APIs |

```csharp
var order = new Order();            // static type is Order, not "any"
// var x;  var y = null;            // errors: nothing to infer from
// field: var _repo = ...;          // errors: var is for locals only

dynamic d = new ExpandoObject();    // using System.Dynamic;
d.Name = "Widget"; d.Price = 9.99m;
Console.WriteLine(d.Name);          // works
// d.Missing();                     // compiles! RuntimeBinderException at runtime

object o = 5;
// o++;                             // compile error; need (int)o first
```

### Nullable types

**Definition.** Two different features share the word "nullable":

1. **Nullable value types** `T?` (`Nullable<T>`): lets a struct hold "no value".
2. **Nullable reference types (NRT)**, C# 8+: compile-time annotations `string` (non-null intent) vs `string?` (may be null). Enabled with `<Nullable>enable</Nullable>`, default in new .NET templates.

```csharp
int? discount = null;                       // Nullable<int>
Console.WriteLine(discount.HasValue);       // False
int pct = discount ?? 0;                    // null-coalescing
discount ??= 10;                            // assign if null
int safe = discount.GetValueOrDefault(5);

int? a = null;
Console.WriteLine(a > 1);                   // False (lifted comparison, no throw)
Console.WriteLine(a == null);               // True
// int bad = discount.Value;                // InvalidOperationException if null

object boxedNull = (int?)null;              // boxing null int? yields a null reference
Console.WriteLine(boxedNull is null);       // True
object boxedVal = (int?)7;                  // boxes as plain int, not Nullable<int>

// Nullable reference types
public class Customer
{
    public required string Name { get; init; }    // must be set, never null
    public string? Phone { get; init; }           // optional
}

string? phone = customer.Phone;
int len = phone?.Length ?? 0;                     // null-conditional + coalescing
if (phone is not null) Console.WriteLine(phone.Length);   // flow analysis: non-null here
string forced = phone!;                           // null-forgiving: no runtime check
ArgumentNullException.ThrowIfNull(customer);      // guard clause (.NET 6+)

// Nullable attributes teach the compiler about your helpers
public static bool TryGetPhone(int id, [NotNullWhen(true)] out string? phone)
{
    phone = null;                                 // lookup omitted
    return false;
}
```

:::warn NRT is compile-time only
`string` does not stop `null` at runtime: JSON deserialisation, reflection, EF and legacy code can still hand you null. Validate at boundaries (API models with `required`/`[Required]`, guard clauses) and treat warnings as errors in new code (`<WarningsAsErrors>nullable</WarningsAsErrors>`).
:::

:::q Difference between `int?` and `string?`?
`int?` is a real different type, `Nullable<int>`, a struct with a `HasValue` flag, with runtime representation. `string?` is the same `string` type with a compile-time annotation that only drives compiler warnings. Same syntax, completely different mechanism.
:::

### String vs StringBuilder

**Definition.** `string` is an **immutable** sequence of UTF-16 chars. Every "modification" (`Replace`, `+`, `ToUpper`, `Substring`) creates a new string. `StringBuilder` is a mutable buffer (a chain of char chunks) that you append to and convert once with `ToString()`.

**Why immutable?** Thread-safety without locks, safe as dictionary keys (hash never changes), string interning, security (a validated path cannot change after validation).

```csharp
string s = "abc";
string t = s.ToUpper();           // new object; s is still "abc"

// Interning: identical literals share ONE object in the intern pool
string a = "hello";
string b = "hel" + "lo";                       // folded at compile time to "hello"
string c = new string("hello".ToCharArray());  // new heap object
Console.WriteLine(ReferenceEquals(a, b));              // True
Console.WriteLine(ReferenceEquals(a, c));              // False
Console.WriteLine(a == c);                             // True: == compares content
Console.WriteLine(ReferenceEquals(a, string.Intern(c)));   // True
```

```csharp
// Loop concatenation: O(n^2) - each += copies everything built so far
string csv = "";
for (int i = 0; i < 50_000; i++) csv += i + ",";

// StringBuilder: amortised O(n) - appends into a growing buffer
var sb = new StringBuilder(capacity: 400_000);   // pre-size if you can estimate
for (int i = 0; i < 50_000; i++) sb.Append(i).Append(',');
string csv2 = sb.ToString();

// Other good tools
string joined = string.Join(",", Enumerable.Range(0, 50_000));   // no repeated copying
string name = $"{customer.Name} owes {total:C}";                  // no boxing
string json = """
    { "id": 1, "name": "raw string literal" }
    """;                                                          // C# 11 raw string
```

Benchmarks in words: for a handful of pieces in one expression (`a + b + c`, interpolation) the compiler calls `string.Concat` once, so `+` is fine and often faster than a `StringBuilder`. In a loop with thousands of iterations, repeated `+=` allocates a new, longer string every pass, produces gigabytes of garbage for 50,000 appends and is typically two to three orders of magnitude slower than `StringBuilder`, which allocates only a few chunks. The crossover is roughly 5-10 concatenations in a loop. For ultra-hot paths use `string.Create`, `Span<char>` or `ArrayPool<char>`.

| | `string` | `StringBuilder` |
|---|---|---|
| Mutability | immutable | mutable |
| Thread-safe | yes (immutable) | no |
| Best for | few, fixed pieces; keys; comparison | many appends, building output in loops |
| Equality | `==` compares content | compare via `ToString()`; `Equals` is not what you expect |
| Memory | new object per change | amortised growth, chunk list |

:::warn Compare strings explicitly
`s1 == s2` is ordinal and case-sensitive. For case-insensitive use `string.Equals(a, b, StringComparison.OrdinalIgnoreCase)`. Never `a.ToLower() == b.ToLower()` (allocates, culture bugs such as the Turkish dotless i). Use `StringComparison.Ordinal*` for identifiers, `CurrentCulture` only for UI text.
:::

:::q Why is a string immutable and what does that mean for performance?
Immutability makes strings thread-safe, hash-stable and internable. The cost: every change allocates. So avoid concatenating in loops (use `StringBuilder` or `string.Join`), avoid repeated `Substring` in parsers (use `ReadOnlySpan<char>`), and remember interned literals cost no extra memory.
:::

### const vs readonly vs static readonly

| | `const` | `readonly` (instance) | `static readonly` |
|---|---|---|---|
| Value fixed | compile time | at construction (initializer or ctor) | at type initialisation (initializer or static ctor) |
| Allowed types | primitives, `string`, enum, null | any type | any type |
| Memory | no field: value is **inlined into callers' IL** | one slot per instance | one slot per type |
| Implicitly static | yes | no | yes |
| Usable in `case` labels / attributes / default params | yes | no | no |
| Changing it in a library | callers must be recompiled | safe | safe |

```csharp
public class Pricing
{
    public const decimal VatRate = 0.18m;                  // truly fixed: OK for const
    public static readonly TimeSpan Timeout = TimeSpan.FromSeconds(30);  // no const
    public static readonly Regex SkuPattern =
        new(@"^[A-Z]{3}-\d{4}$", RegexOptions.Compiled);

    public readonly Guid InstanceId = Guid.NewGuid();        // different per object
    private readonly IClock _clock;
    public Pricing(IClock clock) => _clock = clock;          // assigned once in ctor
}
```

:::warn The const versioning trap
If library `A` ships `public const int MaxItems = 10` and app `B` compiles against it, the literal `10` is baked into `B`. Changing `A` to 20 and redeploying only `A` leaves `B` still using 10. For values that might change (tax rates, limits, versions) use `static readonly` (or configuration). Reserve `const` for true constants: `Math.PI`, days in a week.
:::

:::q Can a `readonly` field's object be modified?
Yes. `readonly` makes the *reference* (or struct value) unassignable after construction, not the object it points to. `readonly List<string> _items` still lets you call `_items.Add(...)`. For real immutability use `IReadOnlyList<T>`, `ImmutableArray<T>` or records with `init`.
:::

### ref, out, in, ref returns and ref struct

**Definition.** By default arguments are passed **by value** (value types copied, references copied). `ref`, `out` and `in` pass **by reference** (an alias to the caller's variable).

| | `ref` | `out` | `in` |
|---|---|---|---|
| Caller must initialise first | yes | no | yes |
| Callee must assign | no | yes, before returning | cannot assign |
| Direction | in and out | out only | in only (read-only ref) |
| Typical use | swap, mutate in place | `TryXxx`, multiple results | pass big struct without copy |

```csharp
static void Increment(ref int x) => x++;

static bool TryDivide(int a, int b, out int result)
{
    if (b == 0) { result = 0; return false; }   // out must be assigned on every path
    result = a / b; return true;
}

static decimal LineTotal(in OrderLine line) => line.Price * line.Qty;   // no 24-byte copy

int n = 5; Increment(ref n);                    // n == 6
if (TryDivide(10, 2, out var q)) Console.WriteLine(q);   // out var (C# 7)
TryDivide(1, 0, out _);                         // discard

public readonly record struct OrderLine(decimal Price, int Qty);
```

#### ref locals and ref returns

Return a reference to storage instead of a copy, so callers can modify the original in place (used inside `List<T>`/`Span<T>` indexers and high-performance code).

```csharp
static ref int FirstNegative(int[] data)
{
    for (int i = 0; i < data.Length; i++)
        if (data[i] < 0) return ref data[i];
    throw new InvalidOperationException("none");
}

int[] arr = [3, -1, 5];
ref int slot = ref FirstNegative(arr);
slot = 0;                                   // arr is now [3, 0, 5]
```

#### ref struct and Span

A `ref struct` (`Span<T>`, `ReadOnlySpan<T>`) can only live on the stack. That lets it safely point into stack memory, arrays or strings without a heap allocation.

```csharp
Span<byte> buffer = stackalloc byte[256];            // stack memory, no GC
ReadOnlySpan<char> year = "2026-10-06".AsSpan(0, 4); // slice, zero allocation
int y = int.Parse(year);                              // parse straight from the slice
```

Restrictions: cannot be boxed, cannot be a field of a normal class or struct, cannot be captured by lambdas, and cannot cross `await`/`yield` boundaries. C# 13 relaxed some rules: `ref struct`s can implement interfaces, be generic arguments with `where T : allows ref struct`, and appear in async methods and iterators as long as they are not used across an `await`/`yield`. C# 13 also added `params` collections, for example `void Log(params ReadOnlySpan<string> parts)`.

:::q What is the difference between `ref` and `out`?
Both pass by reference. `ref` requires the variable to be initialised by the caller and may be read and written. `out` need not be initialised, but the method must assign it on all paths before returning. `out` expresses "this is a result", `ref` expresses "this is read and updated".
:::

:::q Why is `in` useful, and what is the catch?
`in` passes a struct by read-only reference, avoiding a copy of a large struct. The catch: if the struct is not `readonly`, calling its members through the `in` parameter forces the compiler to make a defensive copy, losing the benefit. Pair `in` with `readonly struct`.
:::

### Static classes and static members

**Definition.** A `static` member belongs to the type, not to any instance. A `static class` can contain only static members, cannot be instantiated or inherited (it is `abstract sealed` in IL).

```csharp
public static class Pricing
{
    private static readonly Dictionary<string, decimal> _rates = new()
    {
        ["IN"] = 0.18m, ["US"] = 0.07m,
    };

    static Pricing() { /* runs once, before first use; CLR guarantees thread-safety */ }

    public static decimal WithTax(decimal net, string country) =>
        net * (1 + _rates.GetValueOrDefault(country, 0m));
}

decimal gross = Pricing.WithTax(100m, "IN");    // 118.0

public class Order
{
    private static int _created;                // one counter shared by ALL orders
    public int Number { get; } = Interlocked.Increment(ref _created);
}
```

- **Static constructor:** parameterless, no access modifier, runs automatically once per type (and per closed generic type).
- **Good uses:** pure helpers (`Math`), constants, extension-method containers, factory methods (`Order.Create`), caches that are intentionally process-wide.
- **Bad uses:** services with dependencies, anything holding per-user or per-request state.
- C# 11 added `static abstract`/`static virtual` members in interfaces (generic math: `T.Zero`, `T.Parse`).

:::warn Static mutable state in web apps
ASP.NET Core serves many requests concurrently in one process. A `static List<Order>` or `static Customer CurrentUser` is shared by all of them: race conditions, data leaking between users, memory leaks, untestable code. Put state in DI-registered services with the right lifetime, and use `ConcurrentDictionary` or `IMemoryCache` for intentional shared caches.
:::

:::q Static class vs Singleton vs DI singleton?
A static class cannot implement interfaces, be injected or mocked, and has hidden global state. A hand-written Singleton gives one instance but still couples callers to the concrete type. A DI singleton (`AddSingleton<IClock, SystemClock>()`) gives one instance per container, testable through the interface. Prefer DI for anything with dependencies or behaviour that tests may need to replace.
:::

### Extension methods

**Definition.** Static methods in a static class whose first parameter has `this`, callable as if they were instance methods. They add behaviour to types you do not own (including interfaces, which is how LINQ works) without inheritance or modification.

```csharp
namespace Shop.Extensions;

public static class StringExtensions
{
    public static string Truncate(this string value, int max) =>
        value.Length <= max ? value : value[..max] + "...";

    public static bool HasValue([NotNullWhen(true)] this string? s) =>
        !string.IsNullOrWhiteSpace(s);
}

public static class OrderQueryExtensions
{
    public static IQueryable<Order> ForCustomer(this IQueryable<Order> q, int id) =>
        q.Where(o => o.CustomerId == id);          // composable, still translated to SQL
}

// Usage (needs `using Shop.Extensions;`)
string title = "A very long product title".Truncate(10);   // "A very lon..."
var mine = db.Orders.ForCustomer(42).Where(o => o.Total > 100);
```

How calls resolve: the compiler first looks for an **instance** method; extension methods are considered only if none matches, so an extension can never override a real method (and a later instance method added to the type silently wins). Resolution is purely compile-time and calling on `null` does not throw until the body dereferences. C# 14 (.NET 10) adds `extension` blocks that also allow extension properties:

```csharp
public static class StringExt14
{
    extension(string value)                       // C# 14 / .NET 10
    {
        public bool IsBlank => string.IsNullOrWhiteSpace(value);
        public string Truncate(int max) => value.Length <= max ? value : value[..max];
    }
}
```

:::example Real-world use
A `ClaimsPrincipalExtensions.GetUserId()` replaces `user.FindFirst(ClaimTypes.NameIdentifier)?.Value` repeated across controllers. `IServiceCollection.AddShopServices()` keeps `Program.cs` tidy: the standard .NET registration style.
:::

:::q Can an extension method access private members? Can it override an instance method?
No to both. It is just a static method and only sees the public/internal surface. If an instance method with the same signature exists, the instance method is always chosen. Extension methods are resolved at compile time using the static type, so they are not polymorphic.
:::
