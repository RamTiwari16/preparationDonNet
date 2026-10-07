### Data types

**In simple words:** Every variable in C# has a type, and the compiler knows it before the program runs. The type decides how much memory the value uses, its default value and what you can do with it. For example, `int` holds whole numbers up to about 2.1 billion. `decimal` holds exact money values. Picking the wrong type causes real bugs.

**Real-life example:** In a kitchen you keep milk in a bottle, rice in a jar and eggs in a tray. Each container fits one kind of food, and the wrong container causes a mess.

**Interview question:** What is the difference between float, double and decimal?

**Simple answer:** `float` and `double` store numbers in binary, so they are fast but cannot store values like 0.1 exactly. `decimal` stores numbers in base 10 with 28–29 digits, so it is exact for money. I use `double` for science and graphics, and `decimal` for money.

```csharp
Console.WriteLine(0.1 + 0.2 == 0.3);    // False (double)
Console.WriteLine(0.1m + 0.2m == 0.3m); // True  (decimal)
```

### Value type vs Reference type

**In simple words:** A value type (like `int`, `struct` or `enum`) holds its data directly. When you assign it to another variable, C# copies the data. A reference type (like `class`, `string` or an array) holds a reference (an address) to an object on the heap (the memory area for objects). Assigning it copies only the address, so both variables point to the same object.

**Real-life example:** A value type is like giving a friend a photocopy of a document; their changes do not affect yours. A reference type is like giving a friend your home address; you both visit the same house.

**Interview question:** What is the difference between a value type and a reference type?

**Simple answer:** A value type is copied when you assign it, and a reference type shares the same object through a reference. Value types default to zero, and reference types default to `null`. "Structs always live on the stack" is not true — a struct inside a class or an array lives on the heap with its owner.

```csharp
struct PointS { public int X; }
class  PointC { public int X; }
var a = new PointS { X = 1 }; var b = a; b.X = 9; // a.X is still 1
var c = new PointC { X = 1 }; var d = c; d.X = 9; // c.X is now 9
```

### Variables and constants

**In simple words:** A variable is a named box that stores a value of one type. You can change its value later. A constant (`const`) is a value fixed when the code is compiled, and it can never change. C# does not let you read a local variable before you give it a value.

**Real-life example:** A variable is like a classroom whiteboard; you can wipe it and write again. A constant is like the school's name carved in stone above the gate.

**Interview question:** What happens if you use a local variable before assigning it?

**Simple answer:** The compiler gives an error (CS0165). C# needs "definite assignment": every local must get a value before it is read. Fields of a class are different — they get default values automatically, like 0 or `null`.

```csharp
int x;
// Console.WriteLine(x); // error CS0165
x = 10;
const int MaxRetries = 3; // fixed forever
```

### Type casting and conversions

**In simple words:** Casting means changing a value from one type to another. Safe conversions, like `int` to `long`, happen automatically (implicit). Risky conversions, like `double` to `int`, need an explicit cast and may lose data. For text typed by users, use `TryParse`. It returns `false` instead of throwing an error.

**Real-life example:** Pouring water from a small glass into a big jug is always safe. Pouring a big jug into a small glass needs care, because some water may spill.

**Interview question:** What is the difference between `(int)x`, `Convert.ToInt32(x)` and `int.Parse(s)`?

**Simple answer:** A cast like `(int)3.99` cuts off the decimal part and gives 3. `Convert.ToInt32` accepts many types, rounds to the nearest even number (2.5 becomes 2) and turns `null` into 0. `int.Parse` reads a string and throws if the format is wrong, so for user input I use `int.TryParse`.

```csharp
int a = (int)3.99;                        // 3
int b = Convert.ToInt32(2.5);             // 2 (rounds to even)
bool ok = int.TryParse("42x", out int n); // false, no exception
```

### Boxing and unboxing

**In simple words:** Boxing means putting a value type (like an `int`) inside an `object`. .NET creates a new object on the heap (the memory area for objects) and copies the value into it. Unboxing copies the value back out with a cast, and the cast must use the exact type. Both cost time and memory, so avoid them in code that runs very often.

**Real-life example:** You put a single coin into a gift box to mail it. Packing and unpacking takes effort, even though you only wanted to send a coin.

**Interview question:** What is boxing and why should we avoid it?

**Simple answer:** Boxing converts a value type to `object` or an interface by copying it to the heap, and unboxing copies it back. Each box is a new object that the garbage collector must clean, so in loops it slows the app. Using generics like `List<int>` instead of `ArrayList` avoids it.

```csharp
int n = 42;
object box = n;      // boxing: copy to heap
int back = (int)box; // unboxing: copy back
```

### var, dynamic and object

**In simple words:** `var` lets the compiler work out the type from the value. The type is still fixed at compile time. `dynamic` skips compile-time checks, so the type is checked only when the program runs. `object` is the base type of everything, so it can hold any value, but you must cast it back to use it.

**Real-life example:** `var` is like a parcel where the post office writes the label for you — it is still labelled. `dynamic` is a parcel with no label, so you only find out what is inside when you open it.

**Interview question:** What is the difference between `var` and `dynamic`?

**Simple answer:** `var` is strongly typed: the compiler decides the type once, and you get IntelliSense and compile errors. `dynamic` is resolved at run time, so mistakes appear as a `RuntimeBinderException` while the app runs, and it is slower. I use `var` every day, and `dynamic` only for rare cases like COM interop or `ExpandoObject`.

### Nullable types

**In simple words:** "Nullable" means two different things in C#. `int?` is a real type, `Nullable<int>`, that lets a number also hold "no value". `string?` is only a hint for the compiler (nullable reference types, C# 8+). It gives warnings when you might use `null` by mistake, but it does not stop `null` at run time.

**Real-life example:** An exam result sheet can show a score or "absent". `int?` adds that "absent" option to a number.

**Interview question:** What is the difference between `int?` and `string?`?

**Simple answer:** `int?` is a different type — a struct with a `HasValue` flag — and it exists at run time. `string?` is the same `string` type with a compile-time note that only creates warnings. I use `??` and `?.` to handle nulls safely, and I still check inputs at the edges of the app.

```csharp
int? discount = null;
int pct = discount ?? 0;      // 0
string? phone = null;
int len = phone?.Length ?? 0; // 0, no exception
```

### String vs StringBuilder

**In simple words:** A `string` is immutable (it can never change after it is created). Every change, like `+` or `Replace`, makes a new string. `StringBuilder` is a buffer you can change. You add many pieces to it and create the final string once with `ToString()`.

**Real-life example:** Changing a printed letter means printing a whole new page every time. A `StringBuilder` is like a notebook: you keep adding lines, then make one clean copy at the end.

**Interview question:** Why is string immutable, and when do you use StringBuilder?

**Simple answer:** Immutability makes strings safe to share between threads and safe as dictionary keys. But each change creates a new string, so `+=` in a big loop copies the text again and again and becomes very slow. I use `StringBuilder` or `string.Join` for many appends, and plain `+` or `$""` for a few pieces.

```csharp
var sb = new StringBuilder();
for (int i = 0; i < 1000; i++) sb.Append(i).Append(',');
string csv = sb.ToString();
```

### const vs readonly vs static readonly

**In simple words:** `const` is fixed at compile time, and the value is copied into every place that uses it. `readonly` is set once when the object is created, in the declaration or the constructor. Each object can have its own value. `static readonly` is set once for the whole type at run time, and it can hold any type, like `TimeSpan`.

**Real-life example:** `const` is like the number of days in a week — it never changes. `readonly` is like a passport number — given once when it is issued, and different for each person.

**Interview question:** What is the difference between const, readonly and static readonly?

**Simple answer:** `const` is a compile-time value for simple types like numbers and strings, and it is copied into the calling code. `readonly` is assigned once per object, and `static readonly` once per type, both at run time. If a library changes a `const`, every app using it must be recompiled, so for values that may change I use `static readonly`.

### ref, out, in, ref returns and ref struct

**In simple words:** Normally C# passes a copy of the argument to a method. `ref`, `out` and `in` pass the caller's real variable instead. `ref` means read and change it, `out` means the method must give it a value, and `in` means read-only. A `ref struct`, like `Span<T>`, can only live on the stack (the method's own memory). This lets it point into arrays or strings safely, with no copying.

**Real-life example:** Passing by value is giving someone a photocopy of your form. `ref` is handing over the original form to edit, and `out` is handing over a blank form they must fill in.

**Interview question:** What is the difference between `ref` and `out`?

**Simple answer:** Both pass a variable by reference. With `ref`, the caller must set the variable first, and the method may read and change it. With `out`, the caller does not need to set it, but the method must assign it before it returns — `TryParse` uses this pattern.

```csharp
static void Increment(ref int x) => x++;
int n = 5; Increment(ref n);                      // n is 6
if (int.TryParse("42", out int q)) Console.WriteLine(q);
```

### Static classes and static members

**In simple words:** A `static` member belongs to the type itself, not to one object. There is only one copy, shared by everyone. A `static class` holds only static members, and you cannot create objects from it. It suits simple helpers like `Math`. Be careful with static data that changes in web apps, because all users share it.

**Real-life example:** The clock on a classroom wall is static — one clock for the whole class. A student's notebook is an instance member, because each student has their own.

**Interview question:** What is the difference between a static class and a singleton registered in DI (dependency injection)?

**Simple answer:** A static class cannot implement an interface, so you cannot inject it or replace it with a fake in tests. A DI singleton, like `AddSingleton<IClock, SystemClock>()`, also gives one shared object, but other classes get it through an interface. I use static classes for pure helpers and DI for services with dependencies.

### Extension methods

**In simple words:** An extension method lets you add a new method to a type you do not own, without changing it or inheriting from it. You write a static method in a static class and put `this` before the first parameter. Then you can call it like a normal instance method. LINQ methods like `Where` and `Select` are extension methods.

**Real-life example:** You buy a phone case with a built-in card holder. The phone itself is unchanged, but now it seems to have a new feature.

**Interview question:** Can an extension method access private members or override an instance method?

**Simple answer:** No to both. It is only a static method, so it sees only the public or internal members. If the type already has an instance method with the same signature, the compiler always picks the instance method. Extension methods are chosen at compile time, based on the variable's declared type.

```csharp
public static class StringExtensions
{
    public static string Truncate(this string s, int max) =>
        s.Length <= max ? s : s[..max] + "...";
}
// "A very long title".Truncate(6) -> "A very..."
```

### Class and Object

**In simple words:** A class is a blueprint. It describes the data (fields and properties) and the actions (methods) of something. An object is one real thing built from that blueprint with `new`, and it has its own data. Modern C# also has `record`, a type for data objects that compare by value.

**Real-life example:** A house plan is the class. Each house built from that plan is an object — they look the same, but different families live inside.

**Interview question:** What is the difference between a class and an object, and when do you use a record?

**Simple answer:** A class is the type definition, and an object is an instance of it created at run time. Classes compare by reference, so two objects with the same data are not equal by default. A record gets value equality, `ToString` and `with` copies from the compiler, so I use it for DTOs (simple data-transfer objects) and value objects.

```csharp
public record OrderDto(int Id, decimal Total);
var a = new OrderDto(1, 500m);
var b = a with { Total = 450m };               // copy with one change
Console.WriteLine(a == new OrderDto(1, 500m)); // True
```

### Encapsulation

**In simple words:** Encapsulation means keeping an object's data private and changing it only through its own methods. This way the object can protect its rules. For example, an `Order` can refuse new lines after it is submitted. Access modifiers like `private`, `public` and `protected` control who can see what.

**Real-life example:** An ATM does not let you open the cash box. You can only use the buttons, and the machine checks your PIN and balance before it gives money.

**Interview question:** What is encapsulation and how do you apply it in C#?

**Simple answer:** Encapsulation is bundling data with the methods that use it and hiding the internal state. In C# I make fields private, use properties with `private set`, and expose collections as `IReadOnlyList<T>`. Then all changes go through methods that check the business rules.

```csharp
public OrderStatus Status { get; private set; }
public IReadOnlyList<OrderLine> Lines => _lines.AsReadOnly();
public void Submit() { /* check rules */ Status = OrderStatus.Submitted; }
```

### Abstraction

**In simple words:** Abstraction means showing *what* something does and hiding *how* it does it. The caller works with a simple interface or abstract class, not with the details. For example, checkout code only knows `IPaymentGateway.Charge()`. It does not know about the web calls or retries inside.

**Real-life example:** When you drive a car, you use the steering wheel and the pedals. You do not need to know how the engine and gearbox work.

**Interview question:** What is the difference between abstraction and encapsulation?

**Simple answer:** Abstraction is about the outside view — what an object offers, like "you can pay". Encapsulation is how we hide and protect the inside, with private fields and rule checks. Abstraction answers "what does it do?", and encapsulation answers "how do I protect its state?".

### Inheritance

**In simple words:** Inheritance lets one class reuse and extend another class. The new class (derived) gets the members of the base class, and it can add or change behaviour. It models an "is-a" relationship: "a `DigitalProduct` is a `Product`". C# allows only one base class, but many interfaces.

**Real-life example:** A sports car is a kind of car. It has everything a normal car has — wheels, engine, brakes — plus some extra features of its own.

**Interview question:** Does C# support multiple inheritance?

**Simple answer:** Not for classes — a class can have only one base class. But a class can implement many interfaces, which gives most of the same benefit. When you create a derived object, the base constructor runs before the derived constructor body.

```csharp
public class Product { public virtual decimal TaxRate() => 0.18m; }
public class DigitalProduct : Product
{
    public override decimal TaxRate() => 0.09m;
}
```

### Polymorphism

**In simple words:** Polymorphism means "many forms". One method call can behave differently, depending on the real object. There are two kinds. Compile-time polymorphism is method overloading, chosen by the compiler. Run-time polymorphism uses `virtual` and `override`, chosen by the object's real type while the program runs.

**Real-life example:** You press "Pay" in a shopping app. The same button charges a card, a wallet or cash on delivery, depending on what you picked.

**Interview question:** Explain compile-time vs run-time polymorphism.

**Simple answer:** Compile-time polymorphism is overloading: the compiler picks a method by the argument types. Run-time polymorphism is overriding: a `virtual` call runs the version of the object's real type. For example, `PaymentMethod m = new CardPayment(); m.Pay(100)` runs the card logic, even though the variable type is the base class.

### Method overloading

**In simple words:** Overloading means several methods with the same name in one class, but with different parameters. The parameters can differ in number, type or order. A different return type alone is not enough. The compiler picks the right method at compile time, from the argument types.

**Real-life example:** At a café you can say "one coffee" or "one coffee, large, with milk". The same counter handles both, based on the details you give.

**Interview question:** Can you overload a method only by changing its return type?

**Simple answer:** No. Overloads must differ in their parameter list — count, types, order, or `ref`/`out`/`in`. The compiler chooses at compile time: an exact match wins over a conversion, and a conversion wins over `params`. Optional parameters are often simpler than many overloads.

```csharp
decimal Total(decimal price, int qty) => price * qty;
decimal Total(decimal price, int qty, decimal discountPct) =>
    price * qty * (1 - discountPct / 100m);
```

### Method overriding, `virtual`, `new` and `sealed`

**In simple words:** Overriding lets a derived class replace a base method marked `virtual` or `abstract`. The version that runs depends on the real object type at run time. The `new` keyword only hides the base method, so the variable's declared type decides which one runs. `sealed` stops more overriding or inheritance.

**Real-life example:** Overriding is like updating the restaurant's official menu — every waiter now serves the new dish. Hiding with `new` is like one waiter keeping a private menu — you get it only if you ask that waiter directly.

**Interview question:** What is the difference between `override` and `new`?

**Simple answer:** `override` keeps run-time polymorphism: a base-type variable still runs the derived code. `new` hides the base member, so `Animal a = new Dog(); a.Kind()` runs the `Animal` version. Hiding is almost always a design mistake, which is why the compiler warns about it.

```csharp
class Animal { public virtual string Speak() => "..."; public string Kind() => "Animal"; }
class Dog : Animal { public override string Speak() => "Woof"; public new string Kind() => "Dog"; }
Animal a = new Dog();
a.Speak(); // "Woof"   (real type decides)
a.Kind();  // "Animal" (declared type decides)
```

### Abstract class

**In simple words:** An abstract class is a base class you cannot create objects from. It can have fields, constructors and normal methods, plus `abstract` methods with no body. Every non-abstract child class must implement those abstract methods. Use it when related classes share real code and state.

**Real-life example:** "Vehicle" is only an idea — you cannot buy just a vehicle. You buy a car or a bus, and each one must define how it moves, while they share things like a registration number.

**Interview question:** Why would you use an abstract class?

**Simple answer:** You cannot create an abstract class with `new`; you create one of its child classes. I use it for a family of closely related types that share code, fields or a constructor. A common case is the template method: the base class holds the main steps, and each child fills in one step.

```csharp
public abstract class Report
{
    protected abstract IEnumerable<string> BuildRows(); // each report defines this
    public string Render() => string.Join("\n", BuildRows());
}
```

### Interface

**In simple words:** An interface is a contract. It lists members that a class promises to provide. A class can implement many interfaces. Interfaces are the base of dependency injection and mocking (using fake objects in tests). Since C# 8, an interface can also have default method bodies.

**Real-life example:** A wall power socket is like an interface. Any device with the right plug — a lamp, a phone charger, a fan — can use it, and the socket does not care what the device is.

**Interview question:** Why do we use interfaces?

**Simple answer:** Interfaces let code depend on "what it can do", not on a concrete class. That makes it easy to swap implementations, register them in dependency injection and replace them with fakes in unit tests. A class can implement many interfaces, so this is also how C# shares abilities without multiple inheritance.

```csharp
public interface INotifier { void Send(string to, string message); }
public class EmailNotifier : INotifier
{
    public void Send(string to, string message) => Console.WriteLine($"Mail {to}");
}
```

### Abstract class vs Interface

**In simple words:** Both describe what a type must do, and you cannot create either with `new`. An abstract class can have fields, constructors and shared code, but a class can inherit only one. An interface has no instance fields, but a class can implement many. An abstract class means "is-a"; an interface means "can-do".

**Real-life example:** An abstract class is like a restaurant franchise — every branch shares the same kitchen setup and recipes. An interface is like a food-safety certificate — many different restaurants can hold the same one.

**Interview question:** When do you choose an abstract class over an interface, now that interfaces can have default methods?

**Simple answer:** I start with an interface for the contract, because it is easy to inject and mock. I add an abstract class only when implementations share real state, constructors or protected helpers. Default interface methods are mainly for adding members to a published interface without breaking existing classes.

### Composition vs Inheritance

**In simple words:** Inheritance reuses code through "is-a", like `VipOrder : Order`. Composition reuses code through "has-a": an object holds helper objects and calls them. The common advice is "favour composition over inheritance". Composition is more flexible, because you can change or combine the helpers at run time.

**Real-life example:** A meal combo is built from parts — a burger, fries and a drink. You can change one part without inventing a new kind of meal.

**Interview question:** Why prefer composition over inheritance?

**Simple answer:** Composition lets me swap parts at run time and combine them freely, and my class depends only on an interface. Inheritance is fixed at compile time and tightly tied to the base class, so deep hierarchies break easily. I still use inheritance for a true is-a relationship and for framework base classes like `BackgroundService`.

```csharp
public interface IDiscount { decimal Apply(decimal amount); }
public sealed class PricedOrder(IReadOnlyList<IDiscount> discounts)
{
    public decimal Total(decimal subtotal) =>
        discounts.Aggregate(subtotal, (sum, d) => d.Apply(sum));
}
```

### SOLID principles

**In simple words:** SOLID is five design rules that keep code easy to change and test. S: one class, one reason to change. O: add new behaviour by adding code, not by editing working code. L: a child class must work anywhere its base class works. I: prefer small, focused interfaces. D: depend on interfaces, not on concrete classes.

**Real-life example:** In a restaurant, the chef cooks, the waiter serves and the cashier takes money — one job each (S). A new dish joins the menu without rebuilding the kitchen (O).

**Interview question:** Explain SOLID in one line each, with an example.

**Simple answer:** S: `OrderService` only coordinates, while pricing, saving and emails live in separate classes. O: a new discount is a new `IDiscountStrategy` class, not a new `case` in a switch. L: no override should throw `NotSupportedException`. I: split a fat interface into small ones. D: inject `IOrderRepository` instead of calling `new SqlOrderRepository()`.

### Array

**In simple words:** An array is a fixed-size list of items of one type, kept in one continuous block of memory. You choose the length when you create it, and it never changes. Reading an item by its index is very fast. Arrays are reference types, even when they hold `int` values.

**Real-life example:** An egg tray has a fixed number of slots. You can quickly pick slot 5, but you cannot add a 13th slot to a 12-egg tray.

**Interview question:** What is the difference between an array and a `List<T>`?

**Simple answer:** An array has a fixed size and is the fastest collection. `List<T>` grows and shrinks as needed and has more helpful methods, with a small extra cost. I use an array when the count is known and fixed, and `List<T>` when items are added or removed.

```csharp
int[] primes = [2, 3, 5, 7, 11];
Console.WriteLine(primes[^1]); // 11 (last item)
// primes[10] = 1;             // IndexOutOfRangeException
```

### ArrayList

**In simple words:** `ArrayList` is an old, non-generic list from .NET 1.0. It stores everything as `object`. So each `int` is boxed (wrapped in a new heap object), and you must cast when you read. Type mistakes show up only at run time. In new code, always use `List<T>` instead.

**Real-life example:** It is like a storeroom where every item goes into the same plain brown box. You must open each box to find out what is inside, and sometimes you get a surprise.

**Interview question:** Why shouldn't you use `ArrayList` in new code?

**Simple answer:** It stores `object`, so value types get boxed, the compiler cannot check types, and wrong casts throw `InvalidCastException` at run time. `List<T>` gives the same resizable list with type safety and no boxing. `ArrayList` survives only for old APIs.

```csharp
var al = new ArrayList { 1, "two" }; // compiles: no type safety
int x = (int)al[1]!;                 // InvalidCastException at run time
```

### List

**In simple words:** `List<T>` is a resizable array. Inside, it keeps a normal array and a count. When the array is full, it creates a new one twice as big and copies the items. So adding at the end is usually very fast. It is the default choice for an ordered list of items.

**Real-life example:** When a bus is full, everyone moves to a bus twice as big. Moving takes time, but it happens rarely, so most new passengers just sit down.

**Interview question:** Why does changing a `List<T>` inside a `foreach` throw an exception?

**Simple answer:** `List<T>` keeps a version number that changes on every edit. The loop checks it on each step and throws `InvalidOperationException` if the list changed. To remove items safely, I use `RemoveAll(predicate)` or a `for` loop that goes backwards.

```csharp
// foreach (var p in list) if (p.Price == 0) list.Remove(p); // throws
list.RemoveAll(p => p.Price == 0);                          // safe, one pass
```

### Dictionary

**In simple words:** `Dictionary<TKey, TValue>` stores key–value pairs, like "product code → stock count". It finds a value by its key very fast, usually in O(1) time (the same speed however big it is). Keys must be unique and not null. Use `TryGetValue` to read safely without an exception.

**Real-life example:** A hotel reception has a key board with room numbers. The clerk goes straight to hook 305 instead of checking every key.

**Interview question:** How does a Dictionary work internally?

**Simple answer:** It calls `GetHashCode` on the key and uses that number to pick a bucket (a slot in an array). If several keys land in the same bucket, it keeps them in a short chain and compares them with `Equals`. So lookup is O(1) on average and O(n) in the worst case. When it gets full, it grows to about twice the size and places every item again.

```csharp
var stock = new Dictionary<string, int> { ["P1"] = 10 };
if (stock.TryGetValue("P1", out int qty)) Console.WriteLine(qty); // 10
```

### GetHashCode and Equals contract

**In simple words:** `Dictionary` and `HashSet` use `GetHashCode` to find the right bucket, and `Equals` to confirm the match. So these two methods must agree. If two objects are equal, they must return the same hash code. If you override one, override both, or lookups will fail without any error.

**Real-life example:** In a library, the shelf number is like the hash code, and the exact book title is like `Equals`. If two copies of the same book get different shelf numbers, you search the wrong shelf and never find it.

**Interview question:** What is the GetHashCode and Equals contract?

**Simple answer:** Equal objects must return equal hash codes, but different objects may share a hash. The hash must not change while the object is a key, so never build it from fields that can change. I override both together using the same fields and `HashCode.Combine`, or I just use a `record`, which does this for me.

```csharp
public override bool Equals(object? o) => o is Sku s && s.Code == Code;
public override int GetHashCode() => Code.GetHashCode();
```

### HashSet

**In simple words:** `HashSet<T>` is a collection of unique items with no fixed order. It uses the same hashing as `Dictionary`, but stores only keys, no values. `Add`, `Remove` and `Contains` are O(1) on average (fast, whatever the size). It also has set operations like union and intersection.

**Real-life example:** A guest list at a party door. Each name appears only once, and the guard can check a name quickly without reading the whole list.

**Interview question:** When would you use a `HashSet<T>` instead of `List<T>.Contains`?

**Simple answer:** `HashSet<T>.Contains` is O(1) on average, but `List<T>.Contains` is O(n), because it checks every item. So for membership checks, removing duplicates and set operations like `IntersectWith`, I use a `HashSet`. I use a `List` when I need order, duplicates or index access.

```csharp
var blocked = new HashSet<string>(blockedIds);
var allowed = orders.Where(o => !blocked.Contains(o.CustomerId));
```

### Queue

**In simple words:** `Queue<T>` is first in, first out (FIFO). The first item you add is the first item you take out. `Enqueue` adds to the back, `Dequeue` takes from the front, and both are fast (O(1)). .NET also has `PriorityQueue`, where the item with the smallest priority value comes out first.

**Real-life example:** A line at a bank counter. The person who came first is served first.

**Interview question:** Is `Queue<T>` thread-safe, and what do you use between threads?

**Simple answer:** No, `Queue<T>` is not thread-safe — it can break if many threads use it at once. Between producer and consumer threads, I use `ConcurrentQueue<T>`, or `Channel<T>` for async code. I also use `TryDequeue`, because `Dequeue` on an empty queue throws.

```csharp
var jobs = new Queue<string>();
jobs.Enqueue("email-1"); jobs.Enqueue("email-2");
while (jobs.TryDequeue(out var job)) Console.WriteLine(job); // email-1, email-2
```

### Stack

**In simple words:** `Stack<T>` is last in, first out (LIFO). The last item you add is the first item you take out. `Push` adds to the top, `Pop` removes from the top, and `Peek` looks without removing. All are fast (O(1)). It is used for undo, checking brackets and depth-first search.

**Real-life example:** A pile of plates in a restaurant kitchen. You put a clean plate on top, and you also take the top plate first.

**Interview question:** How would you check if the brackets in a string are balanced?

**Simple answer:** I loop through the characters with a `Stack<char>` and push every opening bracket. For each closing bracket, I pop and check that it matches. If the stack is empty or the pair does not match, the string is not balanced. At the end, the stack must be empty.

### LinkedList

**In simple words:** `LinkedList<T>` is a doubly linked list. Each item is a separate node that knows the previous and the next node. Adding or removing at a node you already hold is O(1) (instant). But there is no index, so finding an item means walking the list (O(n)). In practice, `List<T>` is faster for almost everything.

**Real-life example:** A train with coaches. You can add or remove a coach next to the one you stand in, but to find coach 8 you must walk through the coaches one by one.

**Interview question:** When would you use `LinkedList<T>` instead of `List<T>`?

**Simple answer:** Rarely. Each node is a separate heap object spread around memory, so the CPU cache works poorly and `List<T>` usually wins. I use `LinkedList<T>` when I hold node references and move items often. A classic case is an LRU cache (it removes the least recently used item), together with a `Dictionary` for fast lookup.

### IEnumerable, ICollection, IList, IDictionary

**In simple words:** These interfaces describe what you can do with a collection. `IEnumerable<T>` only lets you loop forward. `ICollection<T>` adds `Count`, `Add` and `Remove`. `IList<T>` adds access by index. `IDictionary<K,V>` adds lookup by key. Each level adds more abilities.

**Real-life example:** A museum visitor can only walk past the paintings (`IEnumerable`). Staff can also count, add or remove paintings (`ICollection`), and the guide can go straight to painting number 12 (`IList`).

**Interview question:** Why accept `IEnumerable<T>` as a parameter but return `IReadOnlyList<T>`?

**Simple answer:** A parameter should ask for as little as possible, so callers can pass arrays, lists, sets or LINQ queries. A return type should give useful, safe abilities: count and index, but no changes. Returning `List<T>` lets callers change my internal data, and returning `IEnumerable<T>` may hide a lazy query that runs again each time.

### IEnumerable vs IQueryable

**In simple words:** `IEnumerable<T>` runs LINQ in memory, on objects you already loaded. `IQueryable<T>` builds an expression tree (a description of the query, stored as data). A provider like EF Core turns that tree into SQL and runs it in the database. So with `IQueryable`, filtering and paging happen in the database, before data is loaded.

**Real-life example:** `IEnumerable` is like carrying every book home from the library, then picking the three you want. `IQueryable` is like giving the librarian a list, so they bring only those three books.

**Interview question:** What is the difference between IEnumerable and IQueryable?

**Simple answer:** `IEnumerable<T>` uses compiled code and filters inside my app. `IQueryable<T>` uses expression trees that EF Core translates to SQL, so the database does the filtering. If I call `ToList()` or `AsEnumerable()` before `Where`, the whole table is loaded into memory — a common performance bug.

```csharp
// Good: one SQL query with WHERE and TOP
var page = await db.Orders.Where(o => o.Total > 1000).Take(20).ToListAsync();
// Bad: loads the whole table, then filters in memory
var bad = db.Orders.ToList().Where(o => o.Total > 1000).Take(20).ToList();
```

### Complexity (Big-O) cheat sheet

**In simple words:** Big-O describes how the work grows when the data grows. O(1) means the time stays the same, whatever the size. O(n) means the time grows with the number of items. O(log n) grows very slowly, like searching a sorted list by halves. Knowing this helps you pick the right collection.

**Real-life example:** Finding a hotel room by its number is O(1) — you go straight there. Finding a guest by name with no register is O(n) — you knock on every door.

**Interview question:** What are the time complexities of the common collection operations?

**Simple answer:** `List<T>` and arrays give O(1) access by index, but O(n) search and O(n) insert in the middle. `Dictionary` and `HashSet` give O(1) lookup on average. Sorted collections like `SortedDictionary` give O(log n), and `Queue` and `Stack` give O(1) add and remove at their ends.

### Which collection should I choose?

**In simple words:** Choose a collection by what you do most often with it. Use `List<T>` by default for an ordered list. Use `Dictionary` for lookup by key, and `HashSet` for unique items and fast "is it there?" checks. Use `Queue` for first-in-first-out work, and `Stack` for undo. For data shared between threads, use concurrent collections.

**Real-life example:** In a kitchen you pick the tool for the job: a ladle for soup, a knife for vegetables, a whisk for eggs. No single tool is best for everything.

**Interview question:** Which collection would you use for fast lookup of a product by its ID?

**Simple answer:** A `Dictionary<int, Product>`, because lookup by key is O(1) on average. If the data is built once at startup and only read after that, `FrozenDictionary` (.NET 8) is even faster to read. If I need the keys in sorted order, I use `SortedDictionary`, which is O(log n).

### LINQ basics: query vs method syntax

**In simple words:** LINQ (Language Integrated Query) lets you query data with C# code. It works on lists in memory, on databases through EF Core, on XML and more. There are two styles. Query syntax looks like SQL (`from … where … select`). Method syntax chains methods like `.Where().Select()`. The compiler turns query syntax into method calls, so both give the same result.

**Real-life example:** You can order food by saying it aloud or by writing it on a slip. The kitchen gets the same order either way.

**Interview question:** What is the difference between query syntax and method syntax?

**Simple answer:** There is no difference in the result; the compiler converts query syntax into method calls. Method syntax supports every operator, like `Count`, `Take` and `Distinct`. I usually use method syntax, and I use query syntax for joins and `let`, where it reads better.

```csharp
var q1 = from c in customers where c.City == "Pune" select c.Name;
var q2 = customers.Where(c => c.City == "Pune").Select(c => c.Name);
```

### Filtering and projection: Where, Select, SelectMany

**In simple words:** `Where` keeps only the items that match a condition. `Select` changes each item into something else, like a DTO or a single field. `SelectMany` takes a list from each item and joins all those lists into one flat list — for example, all order lines from all orders.

**Real-life example:** At a post office, `Where` picks only the parcels for one city, and `Select` reads just the address on each. `SelectMany` empties every mail bag onto one table, so you get one pile of letters.

**Interview question:** What is the difference between Select and SelectMany?

**Simple answer:** `Select` maps each input to exactly one output, so selecting a list property gives a list of lists. `SelectMany` maps each input to many outputs and flattens them into one sequence. For example, `orders.SelectMany(o => o.Lines)` gives all order lines as one flat list.

```csharp
var nested = orders.Select(o => o.Lines);     // list of lists
var flat   = orders.SelectMany(o => o.Lines); // one list of lines
```

### Ordering: OrderBy, ThenBy, Order

**In simple words:** `OrderBy` sorts items by a key, and `OrderByDescending` sorts in reverse. To sort by a second key, use `ThenBy` or `ThenByDescending`. Since .NET 7, `Order()` sorts simple values without a key. In LINQ to Objects, `OrderBy` is a stable sort (equal items keep their original order).

**Real-life example:** A teacher sorts students by class, and then by name inside each class. The second sort only breaks ties; it does not undo the first one.

**Interview question:** What happens if you call `OrderBy` twice?

**Simple answer:** The second `OrderBy` replaces the first sort; it does not add a second level. To add a tie-breaker, use `ThenBy`. For example, `OrderBy(c => c.City).ThenBy(c => c.Name)` sorts by city, then by name inside each city.

```csharp
var sorted = customers.OrderBy(c => c.City).ThenByDescending(c => c.Name);
```

### Quantifiers and element operators

**In simple words:** Quantifiers answer yes/no questions: `Any` (is there at least one?), `All` (do all items match?) and `Contains`. Element operators return one item: `First`, `Single`, `Last` and `ElementAt`. The `OrDefault` versions return a default value, like `null` or 0, instead of throwing when nothing is found.

**Real-life example:** At a railway ticket counter, `Any` asks "is any seat free?". `Single` asks for "the one seat booked on ticket 123" — and complains if it finds two.

**Interview question:** What is the difference between First and Single?

**Simple answer:** `First` returns the first match and throws only if there is none. `Single` expects exactly one match and throws if there are zero or more than one. `SingleOrDefault` returns `default` for zero, but still throws for two or more. I use `Single` for unique lookups, like by primary key, and `First` after an `OrderBy`.

```csharp
orders.First(o => o.Status == "Paid"); // first paid order
orders.Single(o => o.Id == 102);       // exactly one, or it throws
new int[0].All(x => x > 5);            // true (empty sequence)
```

### Aggregation: Count, Sum, Average, Min, Max, Aggregate

**In simple words:** Aggregation methods turn a whole sequence into one value. `Count` counts the items, `Sum` adds them up, and `Average` finds the mean. `Min` and `Max` find the smallest and the largest. `Aggregate` lets you write your own way to combine the items, step by step.

**Real-life example:** At the end of the day, a shop cashier counts the receipts, adds up the sales and finds the biggest sale. Each task turns many receipts into one number.

**Interview question:** What happens when you call `Max` or `Average` on an empty sequence?

**Simple answer:** `Sum` of an empty sequence is 0, but `Average`, `Min` and `Max` on non-nullable types throw `InvalidOperationException`. To avoid this, I use `DefaultIfEmpty(0).Max()`. Or I project to a nullable type, like `Max(o => (decimal?)o.Total)`, which returns `null`.

```csharp
var empty = new List<decimal>();
decimal s = empty.Sum();                  // 0
decimal? m = empty.Max(x => (decimal?)x); // null, no exception
```

### GroupBy

**In simple words:** `GroupBy` puts items into groups that share the same key. Each group has a `Key` and the items that belong to it. You often follow it with `Select` to count or sum each group — for example, group customers by city and count them.

**Real-life example:** A post office sorts letters into bags by city. Each bag has a city label (the key) and holds the letters for that city.

**Interview question:** How do you get the total order amount per customer with LINQ?

**Simple answer:** I group the orders by `CustomerId`, then select the key and the sum of each group. `GroupBy` is deferred, but it reads the whole source when it runs. In EF Core it becomes SQL `GROUP BY` when I select only the key and totals like `Sum` or `Count`.

```csharp
var spend = orders.GroupBy(o => o.CustomerId)
    .Select(g => new { CustomerId = g.Key, Total = g.Sum(o => o.Total) });
```
