## OOP Concepts

### Class and Object

**Definition.** A *class* is a blueprint: fields (state), properties, methods (behaviour), constructors. An *object* is an instance of it created with `new`, living on the heap with its own state.

**Why it matters.** Everything in C# is built from types. Modern C# gives you several shapes, and choosing the right one is a daily design decision.

| Shape | Kind | Equality | Use for |
|---|---|---|---|
| `class` | reference | reference (default) | entities with identity and behaviour: `Order`, `Customer` |
| `record` | reference | by value (all members) | DTOs, messages, value objects: `Money`, `OrderPlaced` |
| `struct` / `record struct` | value | by value | small immutable values: `Point`, `DateRange` |

```csharp
// Primary constructor (C# 12): parameters are in scope for the whole class body.
// In a CLASS they are NOT properties - you copy them into members yourself.
public class Product(string sku, string name, decimal price)
{
    public string Sku { get; } = sku;                 // read-only after construction
    public string Name { get; set; } = name;
    public decimal Price { get; private set; } = price;

    public void ChangePrice(decimal newPrice)
    {
        ArgumentOutOfRangeException.ThrowIfNegative(newPrice);
        Price = newPrice;
    }
}

// required + init (C# 11 / 9): callers must supply values, then it is immutable
public class Customer
{
    public required string Name  { get; init; }
    public required string Email { get; init; }
    public DateTime CreatedUtc   { get; init; } = DateTime.UtcNow;
}

var asha = new Customer { Name = "Asha", Email = "asha@shop.com" };
// asha.Name = "X";                       // error CS8852: init-only
// var bad = new Customer { Name = "X" }; // error CS9035: required member 'Email'

// Records: primary constructor DOES create public init properties + value equality
public record OrderDto(int Id, string CustomerName, decimal Total);
var o1 = new OrderDto(1, "Asha", 500m);
var o2 = o1 with { Total = 450m };        // non-destructive copy
Console.WriteLine(o1 == new OrderDto(1, "Asha", 500m));   // True
Console.WriteLine(o1);   // OrderDto { Id = 1, CustomerName = Asha, Total = 500 }
```

Object creation order for `new Derived()`: derived field initialisers, then base field initialisers, then the base constructor, then the derived constructor body.

:::warn Primary constructor parameters are mutable captures
In a class, a primary constructor parameter used in a method is captured into a hidden, *mutable* field; any method can reassign it. If you need immutability, copy to a `readonly` field or `get;` property (as above) and do not use the raw parameter elsewhere.
:::

:::q Class vs object? Class vs struct vs record?
A class is the type definition; an object is a runtime instance. Class: reference type with identity semantics. Struct: value type, copied on assignment, best for small immutable data. Record: a class (or struct) with compiler-generated value equality, `ToString` and `with`, ideal for DTOs and value objects.
:::

### Encapsulation

**Definition.** Bundling data with the methods that operate on it and *hiding internal state* behind a controlled surface, so an object can always guarantee its own invariants.

**Why it matters.** If any code can set `order.Status = Shipped` or `order.Lines.Clear()`, no rule can be enforced. Encapsulation concentrates the rules in one place.

| Modifier | Visible to |
|---|---|
| `public` | everyone |
| `private` | the declaring type only (default for members) |
| `protected` | declaring type + derived types |
| `internal` | same assembly (default for top-level types) |
| `protected internal` | same assembly **or** derived types anywhere |
| `private protected` | derived types **and** in the same assembly |
| `file` (C# 11) | the same source file (types only) |

```csharp
public enum OrderStatus { Draft, Submitted, Shipped }
public record OrderLine(string Sku, decimal Price, int Qty);

public class Order
{
    private readonly List<OrderLine> _lines = [];

    public int Id { get; }
    public OrderStatus Status { get; private set; } = OrderStatus.Draft;
    public IReadOnlyList<OrderLine> Lines => _lines.AsReadOnly();  // wrapper view
    public decimal Total => _lines.Sum(l => l.Price * l.Qty);

    public Order(int id) => Id = id;

    public void AddLine(string sku, decimal price, int qty)
    {
        if (Status != OrderStatus.Draft)
            throw new InvalidOperationException("Order already submitted.");
        ArgumentOutOfRangeException.ThrowIfNegativeOrZero(qty);
        _lines.Add(new OrderLine(sku, price, qty));
    }

    public void Submit()
    {
        if (_lines.Count == 0) throw new InvalidOperationException("Empty order.");
        Status = OrderStatus.Submitted;      // only this class can change Status
    }
}
```

Property validation with the `field` keyword (C# 14 / .NET 10; before that you declare a backing field yourself):

```csharp
public string Email
{
    get;
    set => field = value.Trim().ToLowerInvariant();   // 'field' = compiler backing field
}
```

:::warn Encapsulation leaks
`public List<OrderLine> Lines { get; set; }` lets anyone clear or replace the list. Returning `IReadOnlyList<T>` that is the raw `List<T>` can still be cast back and mutated; return `AsReadOnly()`, an immutable collection, or a copy.
:::

### Abstraction

**Definition.** Exposing *what* something does and hiding *how*. Callers depend on a simplified model (an abstract class or interface), not on implementation details.

**Encapsulation vs abstraction** (a favourite question): abstraction is a design-level idea about the *outside view* ("you can pay"); encapsulation is the mechanism of *hiding internals* (private fields, invariants). Abstraction answers "what does it offer?", encapsulation answers "how do I protect its state?".

```csharp
// Checkout knows only "something that can charge money"
public interface IPaymentGateway
{
    PaymentResult Charge(decimal amount, string currency);
}
public record PaymentResult(bool Success, string Reference, string? Error = null);

// Details (Razorpay REST calls, retries, signatures) stay inside the implementation
public class RazorpayGateway : IPaymentGateway
{
    public PaymentResult Charge(decimal amount, string currency) =>
        new(true, $"rzp_{Guid.NewGuid():N}");          // HTTP call omitted
}
```

### Inheritance

**Definition.** A class derives from one base class and reuses/extends its members (`class Dog : Animal`). It models an **is-a** relationship. C# allows single class inheritance but many interfaces. All types derive from `object`.

```csharp
public class Product(string name, decimal price)
{
    public string Name { get; } = name;
    public decimal Price { get; protected set; } = price;
    public virtual decimal PriceWithTax() => Price * 1.18m;
}

public class DigitalProduct(string name, decimal price, string downloadUrl)
    : Product(name, price)                     // calls the base constructor
{
    public string DownloadUrl { get; } = downloadUrl;
    public override decimal PriceWithTax() => Price * 1.09m;   // different tax slab
}

class Base    { public Base()    => Console.WriteLine("Base ctor"); }
class Derived : Base { public Derived() => Console.WriteLine("Derived ctor"); }
new Derived();   // Output: Base ctor, Derived ctor
```

- `sealed class X` cannot be inherited; `sealed override` stops further overriding. Seal types that are not designed for extension: safer API and slightly faster virtual-call devirtualisation.
- `protected` exposes members to subclasses only; keep this surface small, it is part of your public contract.
- The "fragile base class" problem: a change in the base silently breaks derived classes. Deep hierarchies (more than 2-3 levels) are a smell.

:::warn Virtual call in a constructor
`Base()` calling a virtual method runs the *derived* override before the derived constructor body has executed, so derived fields may still be null/default. Do not call virtual members from constructors.
:::

### Polymorphism

**Definition.** "Many forms": one call site, different behaviour depending on the object. Two kinds:

- **Compile-time (static):** method overloading, operator overloading, generics. Chosen by the compiler.
- **Run-time (dynamic):** `virtual`/`override` and interface implementations. Chosen at run time from the object's *actual* type via the virtual method table.

**Why it matters.** It lets you add behaviour by *adding a class*, not by editing `if/switch` chains in working code (the Open/Closed Principle).

:::example Payment polymorphism in an e-commerce checkout
Checkout must support card, UPI and cash-on-delivery, each with its own fee and charging logic. The checkout code must not change when "wallet" is added next month.
:::

```csharp
public abstract class PaymentMethod
{
    public abstract string Name { get; }
    protected abstract PaymentResult Charge(decimal total);        // must override
    public virtual decimal Fee(decimal amount) => 0m;              // may override

    public PaymentResult Pay(decimal amount)                       // template method
    {
        ArgumentOutOfRangeException.ThrowIfNegativeOrZero(amount);
        return Charge(amount + Fee(amount));
    }
}

public sealed class CardPayment(string token) : PaymentMethod
{
    public override string Name => "Card";
    public override decimal Fee(decimal amount) => Math.Round(amount * 0.02m, 2);
    protected override PaymentResult Charge(decimal total) =>
        new(true, $"CARD-{token}-{total}");
}
public sealed class UpiPayment(string vpa) : PaymentMethod
{
    public override string Name => "UPI";                          // no fee: inherits 0
    protected override PaymentResult Charge(decimal total) =>
        new(true, $"UPI-{vpa}-{total}");
}
public sealed class CodPayment : PaymentMethod
{
    public override string Name => "Cash on delivery";
    public override decimal Fee(decimal amount) => 40m;            // flat handling fee
    protected override PaymentResult Charge(decimal total) => new(true, $"COD-{total}");
}

public class CheckoutService
{
    public PaymentResult Checkout(Order order, PaymentMethod method) =>
        method.Pay(order.Total);
}

PaymentMethod[] methods =
    [new CardPayment("tok1"), new UpiPayment("ram@upi"), new CodPayment()];
foreach (var m in methods)
    Console.WriteLine($"{m.Name}: {m.Pay(1000m).Reference}");
// Output: Card: CARD-tok1-1020.00 | UPI: UPI-ram@upi-1000 | Cash on delivery: COD-1040
```

Adding `WalletPayment` means a new subclass; `CheckoutService` and the loop are untouched. The anti-pattern this replaces:

```csharp
// switch on type = every new method edits this function (violates Open/Closed)
decimal fee = method switch { CardPayment => ..., UpiPayment => ..., _ => 0m };
```

:::q Explain compile-time vs run-time polymorphism.
Compile-time: the compiler picks among overloads based on the static types of the arguments. Run-time: a `virtual` call is dispatched through the object's method table to the override of its actual type. Example: `PaymentMethod m = new CardPayment(...); m.Pay(...)` runs `CardPayment`'s logic even though the variable's declared type is the base.
:::

### Method overloading

**Definition.** Several methods with the same name in one type, differing in the **parameter list** (count, types, order, `ref`/`out`/`in` kind). Return type alone does not distinguish overloads.

```csharp
public class PriceCalculator
{
    public decimal Total(decimal price, int qty) => price * qty;
    public decimal Total(decimal price, int qty, decimal discountPct) =>
        price * qty * (1 - discountPct / 100m);
    public decimal Total(IEnumerable<OrderLine> lines) => lines.Sum(l => l.Price * l.Qty);
    public decimal Total(params decimal[] prices) => prices.Sum();

    // Optional/named params are an alternative to many overloads
    public decimal Total2(decimal price, int qty = 1, decimal discountPct = 0m) =>
        price * qty * (1 - discountPct / 100m);
}

var calc = new PriceCalculator();
calc.Total(100m, 2);                      // 200
calc.Total(100m, 2, discountPct: 10m);    // 180 (named argument)
```

Resolution is **at compile time** using the static types of the arguments: exact match beats implicit conversion beats `params`. `Print(object)` vs `Print(string)` with `null` picks `string` (more specific); two equally good candidates give an ambiguity error (CS0121).

### Method overriding, `virtual`, `new` and `sealed`

**Definition.** A derived class replaces a base `virtual` / `abstract` member with `override`. The version that runs is chosen at **run time** from the object's actual type.

| Keyword | Meaning |
|---|---|
| `virtual` | base member that *may* be overridden |
| `abstract` | no body; derived (non-abstract) classes *must* override |
| `override` | replaces the base member; keeps polymorphism |
| `sealed override` | override that cannot be overridden again |
| `new` (hiding) | declares an unrelated member with the same name; **no** polymorphism |

```csharp
class Animal
{
    public virtual string Speak() => "...";
    public string Kind() => "Animal";           // not virtual
}
class Dog : Animal
{
    public override string Speak() => "Woof";   // overrides
    public new string Kind() => "Dog";          // hides (warning CS0108 without `new`)
}

Animal a = new Dog();
Console.WriteLine(a.Speak());          // Woof   (run-time type decides)
Console.WriteLine(a.Kind());           // Animal (compile-time type decides: hiding)
Console.WriteLine(((Dog)a).Kind());    // Dog
```

#### Overload resolution vs override resolution

```csharp
class Printer
{
    public void Print(Animal a) => Console.WriteLine("Animal overload");
    public void Print(Dog d)    => Console.WriteLine("Dog overload");
}
Animal pet = new Dog();
new Printer().Print(pet);              // Animal overload  <- overload = STATIC type
new Printer().Print((Dog)pet);         // Dog overload
new Printer().Print((dynamic)pet);     // Dog overload     <- dynamic binds at run time
```

Rule to say aloud: **overloads are picked at compile time by the declared type; overrides are picked at run time by the actual type.** Combining them (an overloaded method that is also virtual) is where bugs hide.

:::warn Derived overloads win, even when worse
`class B { public virtual void F(int x) {} }  class D : B { public void F(double x) {} }`. `new D().F(1)` calls `D.F(double)`: if any *applicable* method is declared in the more derived class (and is not an override), base-class methods are not even considered. Keep overload sets in one class, or mark intent clearly.
:::

Covariant return types (C# 9) let an override return a more derived type: `public override DigitalProduct Clone() => ...`. Always call `base.Method()` deliberately; overriding without it replaces behaviour entirely.

:::q What is the difference between `override` and `new`?
`override` participates in run-time polymorphism: a base-typed reference runs the derived implementation. `new` hides the base member: which one runs depends on the *variable's* static type, so `Animal a = new Dog(); a.Kind()` still runs the base. Hiding is almost always a design mistake; it is a warning for a reason.
:::

### Abstract class

**Definition.** A class declared `abstract` cannot be instantiated; it may contain fields, constructors, concrete members and `abstract` members that subclasses must implement. It is the right tool for a *family of closely related types sharing code and state*.

```csharp
public abstract class Report(string title)          // shared state + ctor
{
    public string Title { get; } = title;
    protected abstract IEnumerable<string> BuildRows();   // step each report defines

    public string Render()                                // shared algorithm
    {
        var sb = new StringBuilder().AppendLine(Title);
        foreach (var row in BuildRows()) sb.AppendLine(row);
        return sb.ToString();
    }
}
public class SalesReport(IReadOnlyList<Order> orders) : Report("Sales")
{
    protected override IEnumerable<string> BuildRows() =>
        orders.Select(o => $"#{o.Id}: {o.Total:C}");
}
// var r = new Report("x");  // error CS0144: cannot create an instance of abstract type
```

### Interface

**Definition.** A contract: a set of members a type promises to provide, with (mostly) no state. A type can implement many interfaces. Interfaces are the basis of dependency injection, mocking and plug-in designs.

```csharp
public interface INotifier
{
    void Send(string to, string message);                         // abstract

    void SendMany(IEnumerable<string> to, string message)         // default method (C# 8)
    {
        foreach (var t in to) Send(t, message);
    }
}
public class EmailNotifier : INotifier
{
    public void Send(string to, string message) =>
        Console.WriteLine($"Mail {to}: {message}");
}

INotifier n = new EmailNotifier();
n.SendMany(["a@x.com", "b@x.com"], "Order shipped");   // uses default implementation
// new EmailNotifier().SendMany(...)   // error: default members need the interface type

// Explicit implementation resolves name clashes
public interface IPrinter { void Run(); }
public interface IScanner { void Run(); }
public class MultiFunction : IPrinter, IScanner
{
    void IPrinter.Run() => Console.WriteLine("Print");
    void IScanner.Run() => Console.WriteLine("Scan");
}
```

Since C# 11, interfaces may also declare `static abstract` members (basis of generic math: `INumber<T>`, `T.Zero`).

### Abstract class vs Interface

| | Abstract class | Interface |
|---|---|---|
| Instantiate | no | no |
| Inheritance | one base class only | implement many |
| Fields / state | yes | no instance fields |
| Constructors | yes | no |
| Member access modifiers | any | public by default |
| Default implementation | yes (virtual / concrete) | yes, default interface methods (C# 8+) |
| Static members | yes | yes (incl. `static abstract`, C# 11) |
| Versioning | adding a virtual member is safe; abstract breaks subclasses | adding a member breaks implementers unless it has a default body |
| Relationship | **is-a** (shared identity and code) | **can-do** (capability/contract) |
| Testing / DI | harder to mock | trivial to mock |

Rule of thumb: **start with an interface** for the contract; add an abstract base class only when several implementations share real code or state. They combine well: `IPaymentMethod` for consumers, `PaymentMethodBase : IPaymentMethod` for shared plumbing.

:::tip Diamond problem
C# avoids it for classes (single inheritance). With default interface methods, if two interfaces provide the same default, the implementing class must provide its own override or the compiler reports ambiguity.
:::

:::q When do you choose an abstract class over an interface now that interfaces have default methods?
When I need shared *state* (fields), constructors, protected helpers, or a template-method skeleton. Default interface methods are meant for evolving a published interface without breaking implementers, not as a replacement for a base class.
:::

### Composition vs Inheritance

**Definition.** *Inheritance* reuses code via is-a (`VipOrder : Order`). *Composition* reuses code via has-a: an object holds collaborators and delegates to them. Guideline: **favour composition over inheritance.**

**Why.** Inheritance is fixed at compile time, exposes the base's whole surface, couples you to its internals, and explodes combinatorially. Composition lets you change behaviour at run time and combine behaviours freely.

Before: inheritance for code reuse.

```csharp
public class Order { public virtual decimal Total(decimal subtotal) => subtotal; }
public class VipOrder : Order
{
    public override decimal Total(decimal s) => base.Total(s) * 0.90m;
}
public class VipFestivalOrder : VipOrder
{
    public override decimal Total(decimal s) => base.Total(s) - 100m;
}
// Next: GiftOrder? VipGiftFestivalOrder? A customer who BECOMES VIP mid-session
// cannot change class. 2^n subclasses for n independent rules.
```

After: composition with small policy objects.

```csharp
public interface IDiscount { decimal Apply(decimal amount); }

public sealed class PercentDiscount(decimal percent) : IDiscount
{
    public decimal Apply(decimal amount) => amount * (1 - percent / 100m);
}
public sealed class FlatDiscount(decimal off) : IDiscount
{
    public decimal Apply(decimal amount) => Math.Max(0m, amount - off);
}

public sealed class PricedOrder(IReadOnlyList<IDiscount> discounts)
{
    public decimal Total(decimal subtotal) =>
        discounts.Aggregate(subtotal, (running, d) => d.Apply(running));
}

var vipFestival = new PricedOrder([new PercentDiscount(10), new FlatDiscount(100)]);
Console.WriteLine(vipFestival.Total(2000m));   // 1700
// A new rule = a new IDiscount class; any combination = a different list. No subclasses.
```

:::warn Classic bad inheritance
`class Stack<T> : List<T>` exposes `Insert`, `RemoveAt`, `Sort` on a stack and breaks its invariants (and the Liskov Substitution Principle). Wrap a `List<T>` field and expose only `Push`/`Pop`/`Peek`.
:::

Inheritance is still right for a true is-a with stable behaviour, and for framework extension points: `ControllerBase`, `BackgroundService`, `DbContext`, `Exception`.

:::q Why prefer composition over inheritance?
Composition is flexible (swap collaborators at run time, combine them), keeps coupling to an interface rather than a base class's internals, avoids the fragile-base-class problem and makes testing easy (inject a fake). Inheritance is a very strong, compile-time, all-or-nothing coupling. I use it for genuine is-a hierarchies and framework hooks.
:::

### SOLID principles

| Letter | Principle | One-line test |
|---|---|---|
| **S** | Single Responsibility | A class has one reason to change |
| **O** | Open/Closed | Extend by adding code, not by editing working code |
| **L** | Liskov Substitution | Subtypes must be usable wherever the base is, without surprises |
| **I** | Interface Segregation | Clients should not depend on methods they do not use |
| **D** | Dependency Inversion | Depend on abstractions; high-level code must not `new` low-level details |

#### S - Single Responsibility

```csharp
// VIOLATION: four reasons to change (tax rules, SQL, mail provider, message text)
public class OrderService
{
    public void PlaceOrder(Order o)
    {
        var total = o.Lines.Sum(l => l.Price * l.Qty) * 1.18m;          // pricing
        using var con = new SqlConnection("Server=...");                // persistence
        con.Open();
        new SqlCommand("INSERT INTO Orders ...", con).ExecuteNonQuery();
        new SmtpClient("smtp.shop.com").Send("noreply@shop.com", "a@x.com",
            "Thanks", $"Total {total}");                                // notification
    }
}

// FIX: one job each; OrderService only orchestrates
public interface IPriceCalculator { decimal Total(Order o); }
public interface IOrderRepository { Task SaveAsync(Order o, CancellationToken ct); }
public interface IOrderNotifier
{
    Task PlacedAsync(Order o, decimal total, CancellationToken ct);
}

public class OrderService(
    IPriceCalculator pricing, IOrderRepository repo, IOrderNotifier notifier)
{
    public async Task PlaceOrderAsync(Order o, CancellationToken ct = default)
    {
        var total = pricing.Total(o);
        await repo.SaveAsync(o, ct);
        await notifier.PlacedAsync(o, total, ct);
    }
}
```

#### O - Open/Closed

```csharp
// VIOLATION: every new discount edits this method (and re-risks the old ones)
public decimal Discount(Order o, string type) => type switch
{
    "regular"  => 0m,
    "vip"      => o.Subtotal * 0.10m,
    "festival" => o.Subtotal * 0.15m,
    _ => throw new ArgumentException(type),
};

// FIX: closed for modification, open for extension
public record Order(int Id, decimal Subtotal);
public interface IDiscountStrategy { string Code { get; } decimal Discount(Order o); }

public sealed class VipDiscount : IDiscountStrategy
{
    public string Code => "vip";
    public decimal Discount(Order o) => o.Subtotal * 0.10m;
}
public sealed class FestivalDiscount : IDiscountStrategy
{
    public string Code => "festival";
    public decimal Discount(Order o) => o.Subtotal * 0.15m;
}

public sealed class DiscountEngine(IEnumerable<IDiscountStrategy> strategies)
{
    public decimal Discount(Order o, string code) =>
        strategies.FirstOrDefault(s => s.Code == code)?.Discount(o) ?? 0m;
}
// Program.cs - new discount = new class + one registration line:
// builder.Services.AddSingleton<IDiscountStrategy, VipDiscount>();
// builder.Services.AddSingleton<IDiscountStrategy, FestivalDiscount>();
```

#### L - Liskov Substitution

```csharp
// VIOLATION: CodPayment cannot honour the base contract
public abstract class PaymentMethodBase
{
    public abstract void Pay(decimal amount);
    public abstract void Refund(decimal amount);
}
public class CodPayment : PaymentMethodBase
{
    public override void Pay(decimal amount) { /* collected at the door */ }
    public override void Refund(decimal amount) => throw new NotSupportedException();
}
// foreach (var p in methods) p.Refund(10m);   // blows up at run time for COD

// FIX: model the capability explicitly
public interface IPayable   { void Pay(decimal amount); }
public interface IRefundable : IPayable { void Refund(decimal amount); }

public class CardPaymentL : IRefundable
{
    public void Pay(decimal amount)    { /* charge */ }
    public void Refund(decimal amount) { /* reverse */ }
}
public class CodPaymentL : IPayable { public void Pay(decimal amount) { } }

public void RefundAll(IEnumerable<IRefundable> methods, decimal amount)
{
    foreach (var m in methods) m.Refund(amount);       // always safe by construction
}
```

Signs of an LSP violation: overrides that throw `NotSupportedException`, empty overrides, `if (x is DerivedType)` checks in callers, strengthened preconditions (derived demands more) or weakened postconditions. Textbook case: `Square : Rectangle` where setting `Width` also changes `Height`, breaking code that assumes the two are independent.

#### I - Interface Segregation

```csharp
// VIOLATION: a read-only catalogue page must implement import/export it never uses
public interface IProductService
{
    Product? Get(int id);
    IReadOnlyList<Product> GetAll();
    void Add(Product p);
    void Delete(int id);
    void ImportFromCsv(Stream csv);
    Stream ExportToCsv();
}

// FIX: small, role-based interfaces; one class may implement several
public interface IProductReader
{
    Product? Get(int id);
    IReadOnlyList<Product> GetAll();
}
public interface IProductWriter   { void Add(Product p); void Delete(int id); }
public interface IProductImporter { void ImportFromCsv(Stream csv); }

public class ProductRepository
    : IProductReader, IProductWriter, IProductImporter { /* ... */ }
public class CatalogPage(IProductReader products) { /* can only read: least privilege */ }
```

#### D - Dependency Inversion

```csharp
// VIOLATION: high-level policy hard-wired to low-level details; untestable
public class CheckoutService
{
    private readonly SqlOrderRepository _repo = new();      // concrete types
    private readonly SmtpEmailSender    _email = new();
    public void Complete(Order o) { _repo.Save(o); _email.Send(o); }
}

// FIX: both sides depend on abstractions; the container supplies implementations
public interface IOrderRepo   { void Save(Order o); }
public interface IEmailSender { void Send(Order o); }

public class CheckoutService2(IOrderRepo repo, IEmailSender email)
{
    public void Complete(Order o) { repo.Save(o); email.Send(o); }
}
// Program.cs
// builder.Services.AddScoped<IOrderRepo, SqlOrderRepo>();
// builder.Services.AddScoped<IEmailSender, SmtpEmailSender>();
// builder.Services.AddScoped<CheckoutService2>();

// Unit test: no database, no SMTP
// var svc = new CheckoutService2(new FakeRepo(), new FakeEmail());
```

:::q DIP vs DI vs IoC?
DIP (the "D" in SOLID) is a *design principle*: depend on abstractions. Dependency Injection is a *technique*: pass dependencies in (constructor injection) instead of creating them inside. IoC is the broader idea that a framework or container calls your code and controls creation and lifetimes (the ASP.NET Core container). DIP says what to depend on; DI/IoC are how you wire it.
:::

:::q Give a real-world SOLID violation you have fixed.
Say: "A 700-line `OrderManager` calculated tax, wrote SQL, called a courier API and sent emails. Any change risked everything and unit tests needed a real database (SRP, DIP). I extracted `IPriceCalculator`, `IOrderRepository`, `IShippingProvider` and `INotifier`, registered them in DI, and replaced a `switch(courier)` with strategies so adding a courier was a new class (OCP). Tests became fast fakes and regressions dropped."
:::

:::scenario A new payment provider every sprint means editing a 600-line switch
Symptoms: regression bugs in providers you did not touch, merge conflicts, no isolated tests. Diagnosis: OCP and SRP violation, type-switching in the checkout flow. Fix: define `IPaymentProvider` with a `Code`, one class per provider, inject `IEnumerable<IPaymentProvider>` and pick by code (or use keyed services in .NET 8+). Adding a provider now touches one new file and one registration, and each provider gets its own unit tests.
:::
