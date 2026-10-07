## LLD Practice Problems (Part 1)

Each solution follows the interview flow: requirements, entities, class diagram, compact C# (persistence omitted), patterns, edge cases, follow-ups. In the interview, write interfaces and the 2-3 core methods first.

### Parking Lot

**Requirements (agreed with the interviewer).**
- Multi-level lot; each floor has spots of sizes Small (motorcycle), Compact (car), Large (truck/bus).
- A vehicle may park in a spot of its size **or larger**.
- Entry issues a ticket; exit calculates the fee by duration and spot size, takes payment, frees the spot.
- Display boards show free spots per floor; the lot rejects vehicles when full.
- Pricing rules must be easy to change (hourly, weekend, flat night rate).

**Clarifying questions to ask.** How many entry/exit gates (concurrency)? Can one vehicle occupy several spots? Do we need reservations or EV charging? Payment methods? Lost ticket policy?

**Entities.** `Vehicle` (abstract) + `Motorcycle`/`Car`/`Truck`, `ParkingSpot`, `ParkingFloor`, `Ticket`, `ParkingLot`, `ISpotAllocationStrategy`, `IPricingStrategy`, `IPaymentProcessor`.

```text
+---------------------------+ 1   1..* +--------------+ 1   1..* +-------------+
| ParkingLot                |<#>------>| ParkingFloor |<#>------>| ParkingSpot |
| + Park(v): Ticket?        |          +--------------+          | Id, Size    |
| + Unpark(id, pay): decimal|                                    | Vehicle?    |
| + event SpotChanged       |--uses--> ISpotAllocationStrategy   +-------------+
+-------------+-------------+--uses--> IPricingStrategy  (Strategy)
              | creates
           Ticket ----> Vehicle <<abstract>> <|-- Motorcycle, Car, Truck
```

```csharp
public enum SpotSize { Small = 1, Compact = 2, Large = 3 }

public abstract class Vehicle(string plate)
{
    public string Plate { get; } = plate;
    public abstract SpotSize RequiredSize { get; }
}
public sealed class Motorcycle(string plate) : Vehicle(plate) { public override SpotSize RequiredSize => SpotSize.Small; }
public sealed class Car(string plate) : Vehicle(plate)        { public override SpotSize RequiredSize => SpotSize.Compact; }
public sealed class Truck(string plate) : Vehicle(plate)      { public override SpotSize RequiredSize => SpotSize.Large; }

public sealed class ParkingSpot(string id, int floor, SpotSize size)
{
    public string Id { get; } = id;
    public int Floor { get; } = floor;
    public SpotSize Size { get; } = size;
    public Vehicle? Vehicle { get; private set; }
    public bool IsFree => Vehicle is null;
    public bool CanFit(Vehicle v) => IsFree && Size >= v.RequiredSize;
    internal void Occupy(Vehicle v) => Vehicle = v;
    internal void Release() => Vehicle = null;
}

public sealed class ParkingFloor(int number, IEnumerable<ParkingSpot> spots)
{
    public int Number { get; } = number;
    public IReadOnlyList<ParkingSpot> Spots { get; } = spots.ToList();
    public int FreeCount => Spots.Count(s => s.IsFree);
}

public sealed class Ticket(Vehicle vehicle, ParkingSpot spot, DateTimeOffset entry)
{
    public Guid Id { get; } = Guid.NewGuid();
    public Vehicle Vehicle { get; } = vehicle;
    public ParkingSpot Spot { get; } = spot;
    public DateTimeOffset Entry { get; } = entry;
    public DateTimeOffset? Exit { get; internal set; }
    public decimal? Fee { get; internal set; }
}

public interface ISpotAllocationStrategy
{
    ParkingSpot? FindSpot(IReadOnlyList<ParkingFloor> floors, Vehicle vehicle);
}

// lowest floor first, and the smallest spot that fits (keeps large spots for trucks)
public sealed class NearestFirstAllocation : ISpotAllocationStrategy
{
    public ParkingSpot? FindSpot(IReadOnlyList<ParkingFloor> floors, Vehicle v) =>
        floors.OrderBy(f => f.Number)
              .SelectMany(f => f.Spots)
              .Where(s => s.CanFit(v))
              .OrderBy(s => s.Size).ThenBy(s => s.Floor)
              .FirstOrDefault();
}

public interface IPricingStrategy { decimal Calculate(Ticket ticket, DateTimeOffset exit); }

public sealed class HourlyPricing(IReadOnlyDictionary<SpotSize, decimal> ratePerHour) : IPricingStrategy
{
    public decimal Calculate(Ticket t, DateTimeOffset exit)
    {
        var hours = Math.Max(1, (int)Math.Ceiling((exit - t.Entry).TotalHours));  // first hour minimum
        return hours * ratePerHour[t.Spot.Size];
    }
}

public interface IPaymentProcessor { bool Charge(Guid ticketId, decimal amount); }

public sealed record SpotChangedEventArgs(int Floor, int FreeSpots);

public sealed class ParkingLot(
    IReadOnlyList<ParkingFloor> floors, ISpotAllocationStrategy allocation,
    IPricingStrategy pricing, TimeProvider clock)
{
    private readonly object _sync = new();
    private readonly Dictionary<Guid, Ticket> _activeByTicket = new();
    private readonly Dictionary<string, Ticket> _activeByPlate = new(StringComparer.OrdinalIgnoreCase);

    public event EventHandler<SpotChangedEventArgs>? SpotChanged;     // Observer: display boards

    public Ticket? Park(Vehicle vehicle)
    {
        Ticket ticket;
        lock (_sync)                                                  // find + occupy is atomic
        {
            if (_activeByPlate.ContainsKey(vehicle.Plate))
                throw new InvalidOperationException($"{vehicle.Plate} is already parked");
            var spot = allocation.FindSpot(floors, vehicle);
            if (spot is null) return null;                            // lot full for this size
            spot.Occupy(vehicle);
            ticket = new Ticket(vehicle, spot, clock.GetUtcNow());
            _activeByTicket[ticket.Id] = ticket;
            _activeByPlate[vehicle.Plate] = ticket;
        }
        Raise(ticket.Spot.Floor);                                     // notify outside the lock
        return ticket;
    }

    public decimal Unpark(Guid ticketId, IPaymentProcessor payment)
    {
        Ticket ticket;
        lock (_sync)
        {
            if (!_activeByTicket.TryGetValue(ticketId, out ticket!))
                throw new KeyNotFoundException("Unknown or already closed ticket");
            var exit = clock.GetUtcNow();
            var fee = pricing.Calculate(ticket, exit);
            if (!payment.Charge(ticket.Id, fee))
                throw new InvalidOperationException("Payment failed; barrier stays closed");
            ticket.Exit = exit; ticket.Fee = fee;
            ticket.Spot.Release();
            _activeByTicket.Remove(ticketId);
            _activeByPlate.Remove(ticket.Vehicle.Plate);
        }
        Raise(ticket.Spot.Floor);
        return ticket.Fee!.Value;
    }

    private void Raise(int floor) =>
        SpotChanged?.Invoke(this, new SpotChangedEventArgs(floor,
            floors.Single(f => f.Number == floor).FreeCount));
}
```

**Patterns used.** Strategy (allocation, pricing), Observer (`SpotChanged` for display boards), Factory (create the right `Vehicle` from the gate's vehicle-type input), composition (lot owns floors owns spots), `TimeProvider` injected for testable time. A Singleton `ParkingLot` is acceptable in a pure-OOP answer; in ASP.NET Core register it with `AddSingleton`.

**Edge cases and concurrency.**
- Two gates grabbing the last spot: the `lock` makes "find + occupy" atomic. With several instances and a DB, use `UPDATE Spot SET VehicleId=@v WHERE Id=@id AND VehicleId IS NULL` and retry on 0 rows.
- Charging inside the lock blocks other exits; in production compute the fee, release the lock, charge, then close the ticket (`PaymentPending` state).
- Lost ticket: find by plate, apply a lost-ticket fee. Overnight stays: UTC times, daily cap in the pricing strategy. Duplicate plate: rejected.

:::q How would you add EV charging spots and a different price for them?
Add `SpotSize`-independent features to the spot (e.g., `bool HasCharger` or a `SpotFeature` flag), extend the allocation strategy to honour a vehicle preference (`RequiresCharger`), and wrap pricing with a decorator `ChargingFeePricing(IPricingStrategy inner)` that adds kWh cost. No existing class needs editing beyond the spot data — Open/Closed.
:::

:::q How do you scale this to 100 lots with a central system?
Keep per-lot state in a database partitioned by `LotId`; gates call a stateless Parking API; spot allocation uses an atomic conditional update or a per-lot queue; display boards subscribe to `SpotChanged` events over SignalR. Payments go through a payment service with idempotency keys = ticket id.
:::

### Library Management

**Requirements.**
- Catalogue of books (title, author, ISBN); each book has several physical copies (`BookItem`, barcode).
- Members borrow up to 5 items for 14 days; can renew once if nobody reserved it.
- If no copy is available, a member can reserve the book (FIFO queue); when a copy is returned it is held for the first in the queue for 2 days and the member is notified.
- Return calculates an overdue fine (e.g., 10 per day); members with unpaid fines over a limit cannot borrow.
- Search by title, author, ISBN.

**Clarifying questions.** Multiple branches? Digital items? Fine policy per member type (student/staff)? Can librarians override limits?

**Entities.** `Book`, `BookItem` (+ `ItemStatus`), `Member`, `Loan`, `Reservation`, `LibraryService` (use cases), `IFinePolicy`, `INotifier`.

```text
+-------+ 1   1..* +-----------+        +---------+ 1   0..5 +------+
| Book  |<#>------>| BookItem  |<-------| Loan    |--------->|Member|
| ISBN  |          | Barcode   |        | Due,    |          | Id   |
| Title |          | Status    |        | Returned|          | Fines|
+---+---+          +-----------+        +---------+          +--+---+
    | 1..*                                                      |
    +-------- Reservation (Book, Member, CreatedAt, HoldUntil) --+
LibraryService --uses--> Catalog, IFinePolicy, INotifier, TimeProvider
```

```csharp
public enum ItemStatus { Available, Loaned, OnHold, Lost }

public sealed class Book(string isbn, string title, string author)
{
    public string Isbn { get; } = isbn;
    public string Title { get; } = title;
    public string Author { get; } = author;
    public List<BookItem> Items { get; } = new();
    public Queue<Reservation> Reservations { get; } = new();          // FIFO waiting list
}

public sealed class BookItem(string barcode, Book book)
{
    public string Barcode { get; } = barcode;
    public Book Book { get; } = book;
    public ItemStatus Status { get; internal set; } = ItemStatus.Available;
    public Member? HeldFor { get; internal set; }
}

public sealed class Member(int id, string name)
{
    public int Id { get; } = id;
    public string Name { get; } = name;
    public decimal OutstandingFines { get; internal set; }
    public List<Loan> ActiveLoans { get; } = new();
}

public sealed class Loan(BookItem item, Member member, DateOnly borrowed, DateOnly due)
{
    public BookItem Item { get; } = item;
    public Member Member { get; } = member;
    public DateOnly Borrowed { get; } = borrowed;
    public DateOnly Due { get; internal set; } = due;
    public bool Renewed { get; internal set; }
}

public sealed record Reservation(Book Book, Member Member, DateTimeOffset CreatedAt);

public interface IFinePolicy { decimal FineFor(Loan loan, DateOnly returnedOn); }
public sealed class PerDayFine(decimal perDay) : IFinePolicy
{
    public decimal FineFor(Loan l, DateOnly on) => Math.Max(0, on.DayNumber - l.Due.DayNumber) * perDay;
}

public interface INotifier { void Notify(Member member, string message); }

public sealed class LibraryService(IFinePolicy fines, INotifier notifier, TimeProvider clock)
{
    private const int MaxLoans = 5, LoanDays = 14, HoldDays = 2;
    private const decimal MaxFines = 100m;
    private readonly object _sync = new();
    private DateOnly Today => DateOnly.FromDateTime(clock.GetUtcNow().UtcDateTime);

    public Loan Borrow(Member m, Book book)
    {
        lock (_sync)
        {
            if (m.ActiveLoans.Count >= MaxLoans) throw new InvalidOperationException("Loan limit reached");
            if (m.OutstandingFines > MaxFines) throw new InvalidOperationException("Pay fines first");

            var item = book.Items.FirstOrDefault(i => i.Status == ItemStatus.OnHold && i.HeldFor == m)
                    ?? book.Items.FirstOrDefault(i => i.Status == ItemStatus.Available)
                    ?? throw new InvalidOperationException("No copy available; reserve instead");

            item.Status = ItemStatus.Loaned; item.HeldFor = null;
            var loan = new Loan(item, m, Today, Today.AddDays(LoanDays));
            m.ActiveLoans.Add(loan);
            return loan;
        }
    }

    public void Reserve(Member m, Book book)
    {
        lock (_sync)
        {
            if (book.Items.Any(i => i.Status == ItemStatus.Available))
                throw new InvalidOperationException("A copy is available; borrow it");
            if (book.Reservations.Any(r => r.Member == m)) return;           // idempotent
            book.Reservations.Enqueue(new Reservation(book, m, clock.GetUtcNow()));
        }
    }

    public decimal Return(Loan loan)
    {
        Member? next = null;
        decimal fine;
        lock (_sync)
        {
            fine = fines.FineFor(loan, Today);
            loan.Member.OutstandingFines += fine;
            loan.Member.ActiveLoans.Remove(loan);

            var item = loan.Item;
            if (item.Book.Reservations.TryDequeue(out var r))                 // hold for next in line
            {
                item.Status = ItemStatus.OnHold; item.HeldFor = next = r.Member;
            }
            else item.Status = ItemStatus.Available;
        }
        if (next is not null)
            notifier.Notify(next, $"'{loan.Item.Book.Title}' is held for you for {HoldDays} days");
        return fine;
    }
}
```

**Patterns used.** Strategy (`IFinePolicy` per member type), Observer/notification (`INotifier` when a hold becomes available), Facade (`LibraryService` exposes the use cases). Search is a `Catalog` repository (`Where(title/author/ISBN matches)`), backed by a search index in production. `Renew` follows the same shape: allowed once, only if `Book.Reservations` is empty, then `Due += 14 days`.

**Edge cases.** Two members borrowing the last copy (lock / DB unique "one active loan per BookItem"); uncollected hold (daily job passes it on); reservation cancelled; lost book (charge replacement); renew blocked by a reservation; returning an item not on loan (validate).

:::q How would you support different borrowing rules for students and staff?
Introduce a `MembershipType` and a `IBorrowingPolicy` (max loans, loan days, fine rate) resolved per member — Strategy again. `LibraryService` asks the policy instead of using constants, so a new membership type is a new class, not more `if` statements.
:::

:::q How do you expire holds that were never collected?
A background job (hosted service) runs daily: for each `OnHold` item whose hold date passed, dequeue the next reservation and notify, or mark it `Available`. Store `HoldUntil` on the item; the job is idempotent so reruns are safe.
:::

### ATM (State pattern)

**Requirements.**
- Insert card -> enter PIN (max 3 attempts, then the card is retained) -> choose operation (withdraw, balance) -> eject card.
- Withdrawal in multiples of the smallest note; the ATM must have enough notes; the account must have enough balance (checked by the bank).
- Cash is dispensed with the fewest notes using available denominations.
- Operations not valid in the current state are rejected (e.g., withdraw before PIN).

**Clarifying questions.** Deposits? Multiple accounts per card? Daily withdrawal limit (bank side)? What if dispensing fails after the debit?

**Entities.** `Atm` (context), abstract `AtmState` + `IdleState`, `CardInsertedState`, `AuthenticatedState`, `Card`, `IBankService`, `CashDispenser`.

```text
          InsertCard            EnterPin (ok)            Withdraw / Balance
 [Idle] ------------> [CardInserted] ------------> [Authenticated] ----+
   ^                    |  EnterPin (wrong x3: retain card)           |
   |                    v                                              |
   +------------- EjectCard / retain <---------------------------------+

+-----------------+ state  +-------------------+
| Atm (context)   |------->| <<abstract>>      |<|-- IdleState, CardInsertedState,
| Card, Attempts  |        | AtmState          |      AuthenticatedState
| Bank, Dispenser |        +-------------------+
+-----------------+--uses--> IBankService, CashDispenser
```

```csharp
public sealed record Card(string Number, string AccountId);

public interface IBankService
{
    bool VerifyPin(Card card, string pin);
    decimal GetBalance(string accountId);
    bool TryDebit(string accountId, decimal amount, string txnId);     // idempotent by txnId
    void Reverse(string txnId);                                         // compensation
}

public abstract class AtmState                         // default: every operation is invalid
{
    private InvalidOperationException Invalid(string op) => new($"{op} not allowed in {GetType().Name}");
    public virtual void InsertCard(Atm atm, Card card) => throw Invalid(nameof(InsertCard));
    public virtual void EnterPin(Atm atm, string pin) => throw Invalid(nameof(EnterPin));
    public virtual void Withdraw(Atm atm, int amount) => throw Invalid(nameof(Withdraw));
    public virtual decimal Balance(Atm atm) => throw Invalid(nameof(Balance));
    public virtual void EjectCard(Atm atm) => throw Invalid(nameof(EjectCard));
}

public sealed class IdleState : AtmState
{
    public static readonly IdleState Instance = new();               // stateless => shared
    public override void InsertCard(Atm atm, Card card)
    {
        atm.Card = card; atm.PinAttempts = 0;
        atm.State = CardInsertedState.Instance;
    }
}

public sealed class CardInsertedState : AtmState
{
    public static readonly CardInsertedState Instance = new();
    public override void EnterPin(Atm atm, string pin)
    {
        if (atm.Bank.VerifyPin(atm.Card!, pin)) { atm.State = AuthenticatedState.Instance; return; }
        if (++atm.PinAttempts >= 3)
        {
            atm.Display("Card retained. Contact your bank.");
            atm.Card = null; atm.State = IdleState.Instance;           // card kept in the machine
            return;
        }
        atm.Display($"Wrong PIN. {3 - atm.PinAttempts} attempt(s) left.");
    }
    public override void EjectCard(Atm atm) => atm.Reset();
}

public sealed class AuthenticatedState : AtmState
{
    public static readonly AuthenticatedState Instance = new();

    public override decimal Balance(Atm atm) => atm.Bank.GetBalance(atm.Card!.AccountId);

    public override void Withdraw(Atm atm, int amount)
    {
        if (amount <= 0 || amount % atm.Dispenser.SmallestNote != 0)
            throw new ArgumentException($"Amount must be a multiple of {atm.Dispenser.SmallestNote}");
        var plan = atm.Dispenser.Plan(amount)
                   ?? throw new InvalidOperationException("ATM cannot dispense this amount");
        var txnId = Guid.NewGuid().ToString("N");
        if (!atm.Bank.TryDebit(atm.Card!.AccountId, amount, txnId))
            throw new InvalidOperationException("Insufficient funds or limit exceeded");
        try { atm.Dispenser.Dispense(plan); }
        catch { atm.Bank.Reverse(txnId); throw; }                     // hardware failure => refund
        atm.Reset();                                                   // eject card after cash
    }
    public override void EjectCard(Atm atm) => atm.Reset();
}

public sealed class CashDispenser(Dictionary<int, int> notes)        // denomination -> count
{
    private readonly object _sync = new();
    public int SmallestNote => notes.Keys.Min();

    // greedy is optimal for canonical note systems (e.g. 2000/500/200/100)
    public IReadOnlyDictionary<int, int>? Plan(int amount)
    {
        lock (_sync)
        {
            var plan = new Dictionary<int, int>();
            foreach (var (note, count) in notes.OrderByDescending(n => n.Key))
            {
                var use = Math.Min(amount / note, count);
                if (use > 0) { plan[note] = use; amount -= use * note; }
            }
            return amount == 0 ? plan : null;
        }
    }

    public void Dispense(IReadOnlyDictionary<int, int> plan)
    {
        lock (_sync)
        {
            if (plan.Any(p => notes[p.Key] < p.Value)) throw new InvalidOperationException("Notes changed");
            foreach (var (note, count) in plan) notes[note] -= count;   // then drive the hardware
        }
    }
}

public sealed class Atm(IBankService bank, CashDispenser dispenser)
{
    internal AtmState State { get; set; } = IdleState.Instance;
    internal Card? Card { get; set; }
    internal int PinAttempts { get; set; }
    internal IBankService Bank { get; } = bank;
    internal CashDispenser Dispenser { get; } = dispenser;

    public void InsertCard(Card card) => State.InsertCard(this, card);
    public void EnterPin(string pin) => State.EnterPin(this, pin);
    public void Withdraw(int amount) => State.Withdraw(this, amount);
    public decimal Balance() => State.Balance(this);
    public void EjectCard() => State.EjectCard(this);

    internal void Reset() { Card = null; PinAttempts = 0; State = IdleState.Instance; }
    internal void Display(string message) => Console.WriteLine(message);
}
```

**Patterns used.** State (each state allows only legal operations; stateless states shared as singletons), Facade (`Atm`), compensation (reverse the debit if dispensing fails), idempotent bank calls (`txnId`). Chain of Responsibility is a common alternative for the dispenser (2000 -> 500 -> 100 handlers).

**Edge cases.** Three wrong PINs (retain card); amount not a multiple of the smallest note; not enough notes (plan *before* debit); debit ok but dispenser jams (reverse); bank timeout (retry `TryDebit` with the same `txnId`); inactivity timeout (eject card); two cards on one account (bank DB handles atomically).

:::q Why use the State pattern instead of a switch on an enum?
Each state's allowed actions live in one class, illegal actions fail by default, and adding a state (e.g., `MaintenanceState` or `DepositState`) means adding a class rather than touching every `switch`. For a 3-state flow an enum + transition table is fine too; State pays off as states and behaviours grow.
:::

:::q What happens if the ATM loses connection after debiting but before dispensing?
The debit carries a transaction id. On recovery the ATM sends a reversal for any transaction without a "dispensed" confirmation; the bank applies it idempotently. Banks also run end-of-day reconciliation between ATM journals and account debits.
:::

### E-commerce (cart, order, pricing and discounts)

**Requirements.**
- Customers add/remove/update items in a cart (quantity limits, product must be active).
- Pricing: subtotal, discounts (percentage coupon, flat amount over a threshold, buy-X-get-Y), tax, shipping.
- Checkout validates stock, reserves inventory, takes payment, creates an order with **price snapshots**; order status lifecycle `Created -> Paid -> Shipped -> Delivered`, or `Cancelled`.
- Discount rules change often (marketing), so they must be pluggable.

**Clarifying questions.** Can coupons stack? Best-discount-only? Guest checkout? Multi-currency? Partial shipments?

**Entities.** `Product`, `Cart`, `CartItem`, `IDiscountRule` (+ implementations), `PricingEngine`, `PriceBreakdown`, `Order`, `OrderLine`, `OrderStatus`, `IInventoryService`, `IPaymentService`, `CheckoutService`.

```text
Cart <#>-- 1..* CartItem(Product, Qty)
CheckoutService --uses--> PricingEngine --uses--> IDiscountRule
                                       <|.. PercentageCoupon, FlatOverThreshold, BuyXGetY
CheckoutService --uses--> IInventoryService, IPaymentService
CheckoutService --creates--> Order(Status) <#>-- 1..* OrderLine (name/price snapshot)
```

```csharp
public sealed record Product(int Id, string Name, decimal Price, bool IsActive = true);

public sealed class CartItem(Product product, int quantity)
{
    public Product Product { get; } = product;
    public int Quantity { get; internal set; } = quantity;
    public decimal LineTotal => Product.Price * Quantity;
}

public sealed class Cart(Guid userId)
{
    private readonly Dictionary<int, CartItem> _items = new();
    public Guid UserId { get; } = userId;
    public IReadOnlyCollection<CartItem> Items => _items.Values;
    public string? CouponCode { get; set; }

    public void Add(Product p, int qty = 1)
    {
        if (!p.IsActive) throw new InvalidOperationException("Product unavailable");
        if (qty <= 0) throw new ArgumentOutOfRangeException(nameof(qty));
        var current = _items.TryGetValue(p.Id, out var item) ? item.Quantity : 0;
        if (current + qty > 10) throw new InvalidOperationException("Max 10 per product");
        if (item is not null) item.Quantity += qty;
        else _items[p.Id] = new CartItem(p, qty);
    }
    public void Remove(int productId) => _items.Remove(productId);
    public void Clear() => _items.Clear();
}

public sealed record PriceBreakdown(decimal Subtotal, decimal Discount, decimal Tax,
                                    decimal Shipping, IReadOnlyList<string> Applied)
{
    public decimal Total => Subtotal - Discount + Tax + Shipping;
}

public interface IDiscountRule
{
    string Name { get; }
    decimal DiscountFor(Cart cart, decimal subtotal);                // 0 if not applicable
}

public sealed class PercentageCoupon(string code, decimal percent) : IDiscountRule
{
    public string Name => $"Coupon {code}";
    public decimal DiscountFor(Cart c, decimal subtotal) =>
        string.Equals(c.CouponCode, code, StringComparison.OrdinalIgnoreCase) ? subtotal * percent / 100m : 0m;
}

public sealed class FlatOffOverThreshold(decimal threshold, decimal off) : IDiscountRule
{
    public string Name => $"{off} off over {threshold}";
    public decimal DiscountFor(Cart c, decimal subtotal) => subtotal >= threshold ? off : 0m;
}

public sealed class BuyXGetYFree(int productId, int buy, int free) : IDiscountRule
{
    public string Name => $"Buy {buy} get {free} free";
    public decimal DiscountFor(Cart c, decimal _)
    {
        var item = c.Items.FirstOrDefault(i => i.Product.Id == productId);
        if (item is null) return 0m;
        var freeUnits = item.Quantity / (buy + free) * free;
        return freeUnits * item.Product.Price;
    }
}

public sealed class PricingEngine(IEnumerable<IDiscountRule> rules, decimal taxRate)
{
    // policy: apply the single best discount (no stacking) - agree this with the interviewer
    public PriceBreakdown Price(Cart cart)
    {
        var subtotal = cart.Items.Sum(i => i.LineTotal);
        var best = rules.Select(r => (Rule: r, Amount: r.DiscountFor(cart, subtotal)))
                        .Where(x => x.Amount > 0)
                        .OrderByDescending(x => x.Amount)
                        .FirstOrDefault();
        var discount = Math.Min(best.Amount, subtotal);                 // never negative totals
        var taxable = subtotal - discount;
        var tax = Math.Round(taxable * taxRate, 2, MidpointRounding.AwayFromZero);
        var shipping = taxable >= 500m || taxable == 0 ? 0m : 40m;
        return new PriceBreakdown(subtotal, discount, tax, shipping,
            best.Rule is null ? [] : [best.Rule.Name]);
    }
}

public enum OrderStatus { Created, Paid, Shipped, Delivered, Cancelled }
public sealed record OrderLine(int ProductId, string Name, decimal UnitPrice, int Quantity);

public sealed class Order(Guid userId, IReadOnlyList<OrderLine> lines, PriceBreakdown price)
{
    private static readonly Dictionary<OrderStatus, OrderStatus[]> Allowed = new()
    {
        [OrderStatus.Created] = [OrderStatus.Paid, OrderStatus.Cancelled],
        [OrderStatus.Paid] = [OrderStatus.Shipped, OrderStatus.Cancelled],
        [OrderStatus.Shipped] = [OrderStatus.Delivered],
        [OrderStatus.Delivered] = [], [OrderStatus.Cancelled] = []
    };
    public Guid Id { get; } = Guid.NewGuid();
    public Guid UserId { get; } = userId;
    public IReadOnlyList<OrderLine> Lines { get; } = lines;        // price snapshot
    public PriceBreakdown Price { get; } = price;
    public OrderStatus Status { get; private set; } = OrderStatus.Created;

    public void MoveTo(OrderStatus next)                             // transition table
    {
        if (!Allowed[Status].Contains(next))
            throw new InvalidOperationException($"{Status} -> {next} not allowed");
        Status = next;
    }
}

public interface IInventoryService
{
    bool TryReserve(Guid orderId, IEnumerable<(int ProductId, int Qty)> items);
    void Release(Guid orderId);
}
public interface IPaymentService { bool Charge(Guid orderId, Guid userId, decimal amount); }

public sealed class CheckoutService(PricingEngine pricing, IInventoryService inventory,
                                    IPaymentService payments)
{
    public Order Checkout(Cart cart)
    {
        if (cart.Items.Count == 0) throw new InvalidOperationException("Cart is empty");
        var price = pricing.Price(cart);                                  // re-price at checkout
        var order = new Order(cart.UserId,
            cart.Items.Select(i => new OrderLine(i.Product.Id, i.Product.Name,
                                                 i.Product.Price, i.Quantity)).ToList(), price);

        if (!inventory.TryReserve(order.Id, cart.Items.Select(i => (i.Product.Id, i.Quantity))))
            throw new InvalidOperationException("Some items are out of stock");

        if (!payments.Charge(order.Id, cart.UserId, price.Total))         // order id = idempotency key
        {
            inventory.Release(order.Id);                                   // compensation
            order.MoveTo(OrderStatus.Cancelled);
            return order;
        }
        order.MoveTo(OrderStatus.Paid);
        cart.Clear();
        return order;
    }
}
```

**Patterns used.** Strategy (`IDiscountRule`, could add `ITaxStrategy`/`IShippingStrategy`), Composite (a `StackedDiscount` rule that combines rules if stacking is allowed), State via transition table for the order, Facade (`CheckoutService`), snapshot (order lines copy name/price), compensation on payment failure.

**Edge cases.** Price changed since add-to-cart (re-price at checkout, show the difference); expired/over-used coupon (validity window + usage counter in the rule); discount > subtotal (clamped); `decimal` with explicit rounding; double-click checkout (idempotency key); stock race (atomic conditional reservation); payment timeout (query the provider by idempotency key before retrying).

:::q How would you allow stacking some discounts but not others?
Give rules a `Priority` and a `Stackable` flag, and a `DiscountPolicy` strategy: apply non-stackable best-of first, then all stackable rules in priority order on the remaining amount, with a global cap (e.g., max 50%). The engine stays the same; only the policy object changes.
:::

:::q How does this design change in a microservices architecture?
Cart lives in Redis (Cart service), pricing becomes a Pricing service, inventory reservation and payment become steps of an order saga (Order -> Inventory -> Payment) with compensations, and the order is created with an outbox event. The class design inside each service stays the same.
:::
