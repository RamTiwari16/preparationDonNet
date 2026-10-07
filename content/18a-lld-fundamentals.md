## LLD Fundamentals

### What LLD is and the process

**Definition.** Low Level Design (LLD) turns a feature into **classes, interfaces, relationships, methods and interactions**: the object model you would actually code. HLD answers "which services and databases"; LLD answers "which classes, with which responsibilities, and how do they collaborate".

**Why it matters.** LLD rounds (often "design a parking lot in 45-60 minutes") test OOP, SOLID, design patterns, clean code, extensibility and concurrency awareness — exactly what a 2-5 year .NET developer uses daily.

A repeatable process:
1. **Clarify requirements** (5 min): actors, core use cases, constraints. Write 4-6 bullet requirements and what is out of scope.
2. **Identify entities**: nouns in the requirements become candidate classes (`Vehicle`, `Spot`, `Ticket`); verbs become methods (`park`, `pay`).
3. **Define relationships**: is-a (inheritance/realization), has-a (composition/aggregation), uses (dependency); multiplicities.
4. **Draw the class diagram** (key fields/methods, not every getter).
5. **Find what varies and apply patterns**: pricing rules -> Strategy; object creation by type -> Factory; lifecycle -> State; notifications -> Observer.
6. **Write the core code**: interfaces first, then the main flow (the 2-3 most important methods). Keep it compilable.
7. **Walk through a use case** (sequence) and **edge cases**.
8. **Discuss concurrency, extensibility, testing** and answer follow-ups ("how would you add EV charging spots?").

:::tip What interviewers grade
Clear responsibilities (each class does one thing), programming to interfaces, the right pattern for the right reason (not pattern-stuffing), handling of edge cases and thread safety, and how easily a new requirement fits (Open/Closed).
:::

### Classes, interfaces and objects

- **Class**: blueprint with state (fields/properties) and behaviour (methods). Encapsulate invariants: private setters, validation in constructors/methods.
- **Interface**: a contract of capabilities with no state (`IPaymentGateway`, `INotificationChannel`). Use it at boundaries and for things that vary.
- **Abstract class**: shared state/behaviour plus abstract members for an "is-a" family (`Vehicle`).
- **Object**: a runtime instance.
- **Value objects vs entities**: an *entity* has identity that persists over time (`Order` with `Id`); a *value object* is defined by its values and immutable (`Money`, `DateRange`, `Address`) — use C# `record`.

```csharp
public readonly record struct Money(decimal Amount, string Currency)      // value object
{
    public static Money operator +(Money a, Money b) =>
        a.Currency == b.Currency ? new(a.Amount + b.Amount, a.Currency)
                                 : throw new InvalidOperationException("Currency mismatch");
}

public sealed record DateRange(DateOnly Start, DateOnly End)              // value object
{
    public bool Overlaps(DateRange other) => Start < other.End && other.Start < End; // half-open
    public int Nights => End.DayNumber - Start.DayNumber;
}
```

### Object relationships and UML notation

| Relationship | Meaning | UML notation | Lifetime | C# mapping |
|---|---|---|---|---|
| **Association** | "knows / uses long-term" | plain line `A ---- B` (arrow for direction) | independent | field referencing another object |
| **Aggregation** | "has-a", whole/part, part can exist alone | hollow diamond at whole `Whole <>---- Part` | part outlives whole | collection of objects passed in from outside |
| **Composition** | "owns", part cannot exist without whole | filled diamond `Whole <#>---- Part` | part dies with whole | whole creates and privately owns parts |
| **Inheritance (generalization)** | "is-a" | hollow triangle arrow `Child ----|> Parent` | n/a | `class Car : Vehicle` |
| **Realization** | implements contract | dashed line + hollow triangle `Class - - -|> Interface` | n/a | `class StripeGateway : IPaymentGateway` |
| **Dependency** | "uses temporarily" (parameter, local) | dashed arrow `A - - -> B` | none | method parameter or local variable |

```csharp
// Association: a Driver is associated with a Vehicle (both live independently)
public class Driver { public Vehicle? CurrentVehicle { get; set; } }

// Aggregation: a Team has Players, but Players exist without the Team
public class Team
{
    private readonly List<Player> _players = new();
    public void Add(Player p) => _players.Add(p);          // created elsewhere, passed in
}

// Composition: a ParkingFloor owns its Spots; they are created by and die with the floor
public class ParkingFloor
{
    private readonly List<ParkingSpot> _spots;
    public ParkingFloor(int count) =>
        _spots = Enumerable.Range(1, count).Select(i => new ParkingSpot(i)).ToList();
}

// Inheritance
public abstract class Vehicle { public required string Plate { get; init; } }
public sealed class Car : Vehicle { }
public sealed class Bike : Vehicle { }
public sealed class Truck : Vehicle { }

// Realization
public interface IPaymentGateway { Task<bool> ChargeAsync(Money amount); }
public sealed class StripeGateway : IPaymentGateway
{ public Task<bool> ChargeAsync(Money amount) => Task.FromResult(true); }

// Dependency: ReceiptPrinter only uses Ticket inside a method
public class ReceiptPrinter { public string Print(Ticket t) => $"Ticket {t.Id}"; }
```

Multiplicity on associations: `1`, `0..1`, `*` / `0..*`, `1..*` (e.g., `ParkingLot 1 <#>---- 1..* ParkingFloor`).

:::q Aggregation vs composition — how do you tell them apart?
Ask "can the part exist without the whole, and who creates it?" Composition: the whole creates and owns the part and it dies with it (Order and its OrderLines, Floor and its Spots). Aggregation: the part is created elsewhere and shared or survives (Team and Players, Department and Employees).
:::

### Class diagrams

UML class box: name, attributes, operations. Visibility: `+` public, `-` private, `#` protected, `~` internal. Abstract names in *italics* (in ASCII write `<<abstract>>`), interfaces as `<<interface>>`.

```text
+---------------------------+            +------------------------+
| <<interface>>             |            | <<abstract>> Vehicle   |
| IPricingStrategy          |            +------------------------+
+---------------------------+            | + Plate: string        |
| + Calculate(t: Ticket,    |            | + Type: VehicleType    |
|   exit: DateTime): Money  |            +-----------^------------+
+-------------^-------------+                        |  (inheritance)
              : (realization)               +--------+--------+
   +----------+-----------+                 |        |        |
   | HourlyPricing        |               Car      Bike     Truck
   +----------------------+
                                  1      1..*                  1      1..*
+---------------------------+  <#>----------- +--------------+ <#>-------- +-------------+
| ParkingLot (singleton?)   |                 | ParkingFloor |             | ParkingSpot |
| - floors: List<Floor>     |                 | + Number     |             | + Id, Size  |
| + Park(v): Ticket         |                 | + FindSpot() |             | + IsFree    |
| + Unpark(t): Money        |                 +--------------+             +-------------+
+---------------------------+
```

Mermaid-like textual form (many teams keep diagrams as code):

```text
classDiagram
  class IPricingStrategy { <<interface>> +Calculate(Ticket, DateTime) Money }
  class Vehicle { <<abstract>> +Plate string }
  Vehicle <|-- Car
  Vehicle <|-- Bike
  IPricingStrategy <|.. HourlyPricing
  ParkingLot "1" *-- "1..*" ParkingFloor : composition
  ParkingFloor "1" *-- "1..*" ParkingSpot
  ParkingLot --> IPricingStrategy : uses
  Ticket --> Vehicle : association
```

### Sequence diagrams

Show **interactions over time** for one use case: lifelines (objects), messages (calls), returns, and optional/alternative blocks.

```text
Use case: car enters and parks

Driver      EntryGate        ParkingLot        ParkingFloor      SpotAllocator
  |  arrive(car) |                 |                  |                  |
  |------------->| Park(car)       |                  |                  |
  |              |---------------->| FindSpot(Car)    |                  |
  |              |                 |----------------->| Allocate(size)   |
  |              |                 |                  |----------------->|
  |              |                 |                  |<-- spot F1-23 ---|
  |              |                 |<-- spot ---------|                  |
  |              |                 | new Ticket(car, spot, now)          |
  |              |<-- ticket ------|                  |                  |
  |<-- ticket ---|                 |                  |                  |
  |   [alt: no free spot] Park returns null -> gate shows "Lot full"     |
```

```text
sequenceDiagram
  Driver->>EntryGate: arrive(car)
  EntryGate->>ParkingLot: Park(car)
  ParkingLot->>ParkingFloor: FindSpot(Car)
  alt spot found
    ParkingFloor-->>ParkingLot: spot
    ParkingLot-->>EntryGate: Ticket
  else lot full
    ParkingLot-->>EntryGate: null
  end
```

## SOLID and Patterns in LLD

### SOLID applied to LLD

| Principle | In an LLD answer |
|---|---|
| **S**ingle Responsibility | `ParkingLot` coordinates; `IPricingStrategy` prices; `TicketRepository` stores. No god class. |
| **O**pen/Closed | add `WeekendPricing` or `EvChargingSpot` by adding classes, not editing `if/switch` chains |
| **L**iskov Substitution | any `Vehicle` subtype works where `Vehicle` is expected; do not throw `NotSupported` in overrides |
| **I**nterface Segregation | `INotificationChannel.SendAsync` only; not one fat `IMessagingEverything` |
| **D**ependency Inversion | services depend on `IPaymentGateway`, injected via constructor; concrete Stripe adapter at the edge |

### Strategy

Encapsulate interchangeable algorithms behind an interface; choose at runtime. **Use for**: pricing, discounts, driver matching, spot allocation, routing.

```csharp
public interface IDiscountStrategy { decimal Apply(decimal subtotal); }
public sealed class NoDiscount : IDiscountStrategy { public decimal Apply(decimal s) => s; }
public sealed class PercentageDiscount(decimal pct) : IDiscountStrategy
{ public decimal Apply(decimal s) => s - s * pct / 100m; }

public sealed class Checkout(IDiscountStrategy discount)
{ public decimal Total(decimal subtotal) => discount.Apply(subtotal); }
```

### Factory

Centralise object creation when the concrete type depends on input. **Use for**: vehicles by type, notification channels by name, payment gateways by country.

```csharp
public enum VehicleType { Bike, Car, Truck }
public static class VehicleFactory
{
    public static Vehicle Create(VehicleType type, string plate) => type switch
    {
        VehicleType.Car => new Car { Plate = plate },
        VehicleType.Bike => new Bike { Plate = plate },
        VehicleType.Truck => new Truck { Plate = plate },
        _ => throw new ArgumentOutOfRangeException(nameof(type))
    };
}
// In ASP.NET Core prefer DI-based factories: IEnumerable<IChannel> or keyed services
// builder.Services.AddKeyedSingleton<INotificationChannel, EmailChannel>("email");
```

### Observer

Subjects notify subscribers of changes without knowing them. **Use for**: display boards updating when spots change, notifying users of order status, domain events. In C#: `event`/`EventHandler<T>`, `IObservable<T>`, or an in-process mediator; across services: a message broker.

```csharp
public sealed class SpotAvailabilityChanged(int floor, int free) : EventArgs
{ public int Floor { get; } = floor; public int Free { get; } = free; }

public sealed class FloorDisplayBoard
{
    public void OnChanged(object? sender, SpotAvailabilityChanged e) =>
        Console.WriteLine($"Floor {e.Floor}: {e.Free} free");
}
// floor.AvailabilityChanged += board.OnChanged;   // subscribe
```

### State

An object changes behaviour when its internal state changes; each state is a class. **Use for**: ATM, order/trip/payment lifecycles, vending machines. Replaces large `switch (status)` blocks and makes illegal transitions impossible.

```csharp
public interface IOrderState
{
    IOrderState Pay(); IOrderState Ship(); IOrderState Cancel();
    string Name { get; }
}
public sealed class Created : IOrderState
{
    public IOrderState Pay() => new Paid();
    public IOrderState Ship() => throw new InvalidOperationException("Pay first");
    public IOrderState Cancel() => new Cancelled();
    public string Name => "Created";
}
// Paid, Shipped, Cancelled implement the allowed transitions similarly
```

For simple lifecycles, an enum plus a **transition table** (`Dictionary<(State, Trigger), State>`) is often clearer — say so in the interview.

### Decorator

Wrap an object to add behaviour without changing it, keeping the same interface. **Use for**: logging/retry/caching around a repository or gateway, adding toppings/add-ons to a price.

```csharp
public sealed class RetryingNotificationChannel(INotificationChannel inner, int attempts)
    : INotificationChannel
{
    public string Name => inner.Name;
    public async Task SendAsync(Notification n, CancellationToken ct)
    {
        for (var i = 1; ; i++)
        {
            try { await inner.SendAsync(n, ct); return; }
            catch when (i < attempts) { await Task.Delay(TimeSpan.FromMilliseconds(200 * i), ct); }
        }
    }
}
```

### Singleton

Exactly one instance with global access. **Use for**: the `ParkingLot` itself in a pure-OOP answer, configuration, ID generators. In .NET apps prefer `services.AddSingleton<T>()` over a static instance (testable, injectable). If you must hand-roll it, use `Lazy<T>` for thread-safe lazy init:

```csharp
public sealed class IdGenerator
{
    private static readonly Lazy<IdGenerator> _instance = new(() => new IdGenerator());
    public static IdGenerator Instance => _instance.Value;
    private long _next;
    private IdGenerator() { }
    public long Next() => Interlocked.Increment(ref _next);    // thread-safe
}
```

:::warn Pattern-stuffing
Do not add a pattern unless something actually varies or a real problem exists. Interviewers penalise a Factory that creates one type, or a Singleton used to share mutable state across requests (a concurrency bug). Name the reason each pattern exists in your design.
:::

| Problem in the requirements | Pattern |
|---|---|
| "Pricing/discount/matching rules may change" | Strategy |
| "Create X based on type/config" | Factory / Abstract Factory |
| "Notify displays/users when Y changes" | Observer (events) |
| "Object behaves differently by status" | State |
| "Add logging/retry/caching without touching class" | Decorator |
| "Integrate third-party API with a different interface" | Adapter |
| "Build complex object step by step" | Builder |
| "Undo / queue operations" | Command |
| "One shared instance" | Singleton (via DI) |
| "Handle request through a series of handlers" | Chain of Responsibility (validation, cash dispensing) |

### Thread safety in LLD answers

Shared mutable state (spots, seats, rooms, account balance) is where LLD answers fail. Options, simplest first:
- `lock` around the critical section (allocate spot + mark occupied atomically).
- `ConcurrentDictionary`, `Interlocked`, `SemaphoreSlim` for async code.
- Optimistic concurrency in the database (`rowversion`, conditional `UPDATE ... WHERE Status = Free`) — the real-world answer when there are multiple app instances; an in-memory lock only protects one process.
- Immutable value objects to avoid sharing mutable data.
