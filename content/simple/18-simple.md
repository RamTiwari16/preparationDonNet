### What LLD is and the process

**In simple words:** Low Level Design (LLD) means planning the classes you will actually write. You decide the classes, their methods, and how they work together. High Level Design picks services and databases; LLD goes one level deeper, into the code. A good process is: ask questions, find the main objects, link them, draw a diagram, pick patterns, write the core code, then check edge cases.

**Real-life example:** An architect first decides "a house with three floors" (high level). Then a builder plans each room, door and pipe (low level). LLD is the room-by-room plan.

**Interview question:** How do you approach an LLD question like "design a parking lot"?

**Simple answer:** First I ask questions and write 4–6 clear requirements, plus what is out of scope. Then I turn nouns into classes and verbs into methods, draw a class diagram, and use patterns only where something changes. Finally I code the main flow, walk through one use case, and discuss edge cases, thread safety and how to add new features.

### Classes, interfaces and objects

**In simple words:** A *class* is a blueprint with data (fields) and actions (methods). An *object* is one real thing built from it at runtime. An *interface* is a promise of what something can do, like `IPaymentGateway`. An *entity* keeps the same ID over time, like an `Order`. A *value object* is defined only by its values and never changes, like `Money`.

**Real-life example:** A house plan is the class; each built house is an object. Two banknotes of the same value are equal to you — a value object. Your bank account keeps its number while the balance changes — an entity.

**Interview question:** What is the difference between an entity and a value object?

**Simple answer:** An entity has an identity that stays while its data changes, like an `Order` with an `Id`. A value object has no identity: two with the same values are equal, and it should be immutable (not changeable), like `Money` or `DateRange`. In C#, a `record` is a natural fit for value objects.

```csharp
public record Money(decimal Amount, string Currency);              // value object
public class Order { public Guid Id { get; } = Guid.NewGuid(); }   // entity
```

### Object relationships and UML notation

**In simple words:** Classes are linked in a few standard ways. *Association*: one object knows another (a driver and a car). *Aggregation*: a whole has parts that can live alone (a team and its players). *Composition*: the whole owns its parts, and they die with it (a floor and its spots). *Inheritance* is "is-a" (a car is a vehicle). *Realization* means a class implements an interface. *Dependency* means a class uses another only briefly, like a method parameter. UML (a standard drawing language) has a symbol for each.

**Real-life example:** A teacher can move to another school — aggregation. A building owns its rooms; demolish the building and the rooms are gone — composition.

**Interview question:** How do you tell aggregation from composition?

**Simple answer:** I ask: can the part live without the whole, and who creates it? In composition, the whole creates and owns the part, and the part dies with it, like an order and its order lines. In aggregation, the part is made elsewhere and can live alone, like a player in a team.

### Class diagrams

**In simple words:** A class diagram is a picture of your classes and how they connect. Each box has three parts: the class name, its fields, and its methods. Symbols show visibility: `+` public, `-` private, `#` protected. Lines and arrows show relationships, such as inheritance or "owns". You draw only the important fields and methods, not every getter.

**Real-life example:** A city map shows the main roads and buildings, not every brick. In the same way, a class diagram shows the main classes and links, not every line of code.

**Interview question:** What do you show in a class diagram during an LLD interview?

**Simple answer:** I show the main classes and interfaces with their key fields and methods. I also show the relationships: inheritance, interface implementation, composition and simple usage. I add numbers like `1` and `1..*` to show how many of each. I keep it small so the interviewer can follow it quickly.

### Sequence diagrams

**In simple words:** A sequence diagram shows one use case step by step over time. Each object gets a vertical line. Arrows between the lines show method calls and their replies, from top to bottom. You can also show "if/else" branches, like "spot found" or "lot full". It helps you check that your classes really work together.

**Real-life example:** A restaurant order: the customer tells the waiter, the waiter tells the kitchen, the kitchen gives back the food, and the waiter serves it. You read it from top to bottom, in time order.

**Interview question:** When would you draw a sequence diagram instead of a class diagram?

**Simple answer:** A class diagram shows structure: which classes exist and how they are linked. A sequence diagram shows behaviour: who calls whom, in what order, for one use case like "car enters and parks". I draw it to walk the interviewer through the main flow and the failure branch.

### SOLID applied to LLD

**In simple words:** SOLID is five rules for clean classes. S: each class has one job. O: add new features by adding classes, not by editing old ones. L: a child class must work anywhere its parent works. I: keep interfaces small and focused. D: depend on interfaces, and receive the real objects through the constructor. In LLD you show these rules in your class design.

**Real-life example:** In a hospital, the receptionist books, the doctor treats, and the cashier bills — one job each. A new department opens in a new room, without rebuilding the old ones.

**Interview question:** How do you show SOLID in an LLD answer?

**Simple answer:** I give each class one job: for example, `ParkingLot` coordinates and `IPricingStrategy` calculates the fee. New rules like weekend pricing become new classes, not new `if` branches. Services depend on small interfaces like `IPaymentGateway`, injected through the constructor, so I can swap them or use fakes in tests.

### Strategy

**In simple words:** The Strategy pattern puts each version of an algorithm (a set of steps for a task) in its own class. All versions share one interface. The main class uses the interface and does not care which version it gets. You can choose the version at runtime. It suits pricing, discounts, driver matching and spot allocation.

**Real-life example:** To reach the airport you can take a taxi, a bus or a train. The goal is the same; you pick the way based on time and money.

**Interview question:** When do you use the Strategy pattern?

**Simple answer:** I use Strategy when a rule can change or has several versions, like pricing or discounts. Each rule is a class that implements one interface, such as `IDiscountStrategy`, and the service receives it through the constructor. Adding a new rule means adding a new class, without editing existing code.

```csharp
public interface IDiscountStrategy { decimal Apply(decimal subtotal); }
public class NoDiscount : IDiscountStrategy { public decimal Apply(decimal s) => s; }
public class TenPercentOff : IDiscountStrategy { public decimal Apply(decimal s) => s * 0.9m; }
```

### Factory

**In simple words:** A Factory is one place that creates objects for you. You tell it what you need, for example "Car", and it returns the right class. The rest of your code does not need `new Car()` or `new Truck()` everywhere. In ASP.NET Core, the DI container (the built-in object creator) often does this job, for example with keyed services.

**Real-life example:** At a coffee shop you just say "a latte". The barista knows which cup, milk and steps to use. You do not need to know how it is made.

**Interview question:** Why use a Factory instead of calling `new` directly?

**Simple answer:** A Factory keeps the "which class to create" decision in one place, based on input like vehicle type or country. Callers depend only on the base class or interface, so a new type changes only one place. But if there is only one type to create, a factory adds no value, so I skip it.

### Observer

**In simple words:** In the Observer pattern, one object (the subject) tells many listeners when something changes. The subject does not need to know who the listeners are. Listeners subscribe and unsubscribe themselves. In C# you use `event` with `EventHandler<T>`. Between services you use a message broker (a system that passes messages between apps).

**Real-life example:** You subscribe to a newspaper. When a new issue comes out, it is delivered to every subscriber. The newspaper office does not need to know what each reader does with it.

**Interview question:** Where would you use the Observer pattern in an LLD problem?

**Simple answer:** I use it when other parts must react to a change without the main class knowing them. For example, the parking lot raises a `SpotChanged` event, and the display boards update the free-spot count. In a bigger system, the same idea becomes domain events or messages on a queue.

### State

**In simple words:** With the State pattern, an object behaves differently based on its current state. Each state is its own class. It decides which actions are allowed and what the next state is. This replaces big `switch (status)` blocks, and illegal actions like "ship before pay" fail on their own. For simple flows, an enum plus a transition table (a list of allowed moves) is often clearer.

**Real-life example:** A vending machine will not give a snack before you insert money. After you pay, it is in a new state, and the "dispense" button now works.

**Interview question:** Strategy and State look similar. What is the difference?

**Simple answer:** Both put behaviour behind an interface. With Strategy, the caller picks the algorithm, and it rarely changes during the object's life. With State, the object changes its own state as events happen, and each state decides the next one, like an ATM or an order lifecycle.

### Decorator

**In simple words:** A Decorator wraps an object to add extra behaviour, while keeping the same interface. The original class does not change. You can stack several wrappers, such as logging, retry and caching. The caller cannot tell the difference, because it still sees the same interface.

**Real-life example:** You put your phone in a protective case. It is still the same phone and works the same way, but now it has extra protection. You can add a screen guard on top as well.

**Interview question:** What is the difference between Decorator and Adapter?

**Simple answer:** A Decorator keeps the same interface and adds behaviour, like a `RetryingNotificationChannel` that adds retries to any channel. An Adapter changes one interface into the one your code expects, like wrapping a vendor SDK behind `IPaymentGateway`. Both wrap an object, but for different reasons.

### Singleton

**In simple words:** A Singleton means only one object of a class exists, and everyone shares it. Examples are configuration or an ID generator. In .NET apps, register the class with `AddSingleton` in DI instead of writing a static instance. If you must write it by hand, use `Lazy<T>`, so it is created once, safely, even with many threads.

**Real-life example:** A school has one main bell. Every classroom hears the same bell; no class installs its own.

**Interview question:** What is wrong with a hand-written Singleton in an ASP.NET Core app?

**Simple answer:** It hides dependencies and is hard to replace in tests. It often holds shared data that many threads change at once, which causes bugs. I register the class with `AddSingleton` and inject it, and I keep it stateless (no changing data) or protect its data with proper locking.

### Thread safety in LLD answers

**In simple words:** Many LLD problems have shared data that many users change at once: parking spots, seats, rooms, account balance. If two requests ask "is it free?" at the same moment, both may take it. So "check and take" must be one atomic step (a step that cannot be split). In one process, use `lock`, `Interlocked` or `SemaphoreSlim`. With many servers, use the database: a unique key or a conditional update.

**Real-life example:** Two cashiers sell the last concert ticket at the same moment. Without one shared check, both sell it, and two people arrive for one seat.

**Interview question:** How do you stop two users from booking the same seat or spot?

**Simple answer:** I make "check availability and reserve" one atomic operation. In a single app I use a `lock` or compare-and-swap (`Interlocked.CompareExchange`). With several servers, a memory lock protects only one process, so I use the database: a unique constraint or a conditional `UPDATE`, and I check how many rows changed.

```sql
UPDATE Spot SET VehicleId = @v
WHERE Id = @id AND VehicleId IS NULL;   -- 0 rows changed = already taken
```

### Parking Lot

**In simple words:** This design models a multi-floor parking lot. The lot owns floors, floors own spots, and each spot has a size: small, compact or large. A vehicle can park in a spot of its size or bigger. Entry gives a ticket; exit calculates the fee and frees the spot. Strategy handles spot choice and pricing, and Observer updates the display boards.

**Real-life example:** A mall car park: the gate gives you a ticket, a board shows "Floor 2: 15 free", and at exit the machine charges you by the hours you parked.

**Interview question:** How would you design a parking lot system?

**Simple answer:** I create `Vehicle` subclasses, `ParkingSpot`, `ParkingFloor`, `Ticket`, and a `ParkingLot` that coordinates them. Spot allocation and pricing are strategies, so a weekend rate is just a new class. "Find a spot and occupy it" is atomic with a lock, or a conditional database update with many servers, and display boards listen to a `SpotChanged` event.

### Library Management

**In simple words:** This design manages books, copies, members, loans and reservations. A `Book` is the title; a `BookItem` is one physical copy with a barcode. In this design, members borrow up to 5 items for 14 days. If no copy is free, they join a FIFO queue (first in, first out). When a copy comes back, it is held for the first person, who gets a notice. Late returns create a fine through a fine policy class.

**Real-life example:** Your local library: you borrow with your card, pay a small fine if you are late, and get a message when a book you reserved comes back.

**Interview question:** Why do you separate `Book` and `BookItem`?

**Simple answer:** `Book` holds shared details like title, author and ISBN. `BookItem` is one physical copy with its own barcode and status: Available, Loaned or OnHold. A library has many copies of one book, and each loan points to one specific copy, so they must be separate classes.

### ATM (State pattern)

**In simple words:** An ATM moves through clear states: Idle, CardInserted and Authenticated. Each state is a class that allows only the right actions. For example, you cannot withdraw before the PIN is correct, and after 3 wrong PINs the card is kept. To withdraw, the ATM first plans the notes, then debits the account, then gives the cash. If the cash cannot come out, it reverses the debit (an "undo" step).

**Real-life example:** Any bank ATM: insert card, enter PIN, choose "withdraw", take the cash, take the card. Pressing "withdraw" before entering the PIN does nothing.

**Interview question:** What happens if the ATM debits the account but fails to give the cash?

**Simple answer:** Each debit has a unique transaction id. If dispensing fails, the ATM asks the bank to reverse that transaction. The bank handles the reversal idempotently (doing it twice has the same effect as once). A daily reconciliation job also matches ATM logs with account debits, to catch anything missed.

### E-commerce (cart, order, pricing and discounts)

**In simple words:** This design covers a cart, a pricing engine, discounts and orders. Each discount type (coupon, flat amount, buy-X-get-Y) is a strategy behind `IDiscountRule`, so new offers are easy to add. At checkout, the system prices the cart again, reserves stock, takes payment, and creates an order. The order copies each name and price at that moment (a snapshot). If payment fails, the stock is released.

**Real-life example:** A supermarket bill: items are scanned, offers like "buy 2 get 1 free" are applied, and tax is added. The printed receipt keeps today's price, even if prices change tomorrow.

**Interview question:** Why does an order store a copy of the product price?

**Simple answer:** Product prices change over time, but an order must show what the customer actually paid. So each order line copies the product name and unit price at checkout. Invoices, refunds and reports then stay correct, even after the catalog price changes.

### Hotel Booking

**In simple words:** This design lets guests search rooms by type and dates, book a room, and cancel. A `DateRange` value object holds check-in and check-out and answers "do these dates overlap?". The most important rule is no double booking, even when two requests arrive at the same time. Room rates and refund rules are strategies, so they are easy to change.

**Real-life example:** Booking a hotel online: you pick dates, the site shows free rooms, and two guests never get the same room for the same night.

**Interview question:** How do you prevent double booking of a hotel room?

**Simple answer:** "Check the room is free" and "save the booking" must be one atomic step. In one process, a lock around both works. With many servers, I store one row per room per night with a unique key on (room, night), so a second booking for that night fails with a duplicate-key error.

```csharp
// [start, end): the check-out day is free for the next guest
bool Overlaps(DateRange a, DateRange b) => a.Start < b.End && b.Start < a.End;
```

### Cab Booking

**In simple words:** A rider asks for a ride, and the system finds a nearby free driver with a matching strategy (nearest, best rated, or fastest arrival). The trip moves through states: Requested, DriverAssigned, InProgress, then Completed or Cancelled. The fare is base price plus per km plus per minute, times a surge multiplier. A driver can take only one trip at a time, so claiming a driver must be atomic.

**Real-life example:** A taxi app: you request a cab, the nearest driver gets your ride, you watch the car come, and the fare is higher when demand is high.

**Interview question:** How do you stop two riders from getting the same driver?

**Simple answer:** Claiming a driver is one flag change, so I use compare-and-swap (`Interlocked.CompareExchange`). Only the first request that switches "free" to "busy" wins; the other request just tries the next driver. Across many servers, the same idea becomes a conditional database update or Redis `SET NX` (set only if the key does not exist).

### Notification Service

**In simple words:** This design sends messages by email, SMS and push, and new channels are easy to add. Each channel is a class behind `INotificationChannel`. Producers put messages in a queue and return quickly; background workers send them. Failed sends are retried with longer and longer waits. After too many failures, a message goes to a dead-letter queue (a place for messages that keep failing). A dedup key stops the same message going out twice.

**Real-life example:** A post office: you drop a letter in the box and leave. The postman delivers it later, tries again if nobody is home, and sends undeliverable letters to a special office.

**Interview question:** How would you add WhatsApp as a new channel?

**Simple answer:** I create a `WhatsAppChannel` class that implements `INotificationChannel` and wraps the provider's SDK. I register it in DI and add it to user preferences. The worker finds channels from a registry by type, so no existing sending code changes — that is the Open/Closed principle.

### Payment System

**In simple words:** This design takes payments through several gateways, like Stripe or PayPal. Each gateway's SDK is wrapped in an adapter behind one `IPaymentGateway` interface. A payment has a clear lifecycle: Created, Authorized, Captured, Refunded, or Failed. An idempotency key (a unique id for each request) makes sure a retry never charges twice. Amounts are stored as whole minor units, like cents, to avoid rounding errors.

**Real-life example:** A travel plug adapter lets one charger work with sockets in many countries. Here, the adapter lets one payment service work with many different gateways.

**Interview question:** The gateway call timed out. Do you retry the charge?

**Simple answer:** Not blindly, because the charge may have succeeded. I retry with the same idempotency key, so the gateway returns the first result instead of charging again, or I first ask the gateway for the status. The payment stays pending until a webhook or a reconciliation job confirms it.
