## LLD Practice Problems (Part 2)

### Hotel Booking

**Requirements.**
- Search available rooms by type for a stay `[checkIn, checkOut)`.
- Book a room; **no double booking** even with concurrent requests.
- Price per night with rules (weekend surcharge, seasonal rates).
- Cancel with a refund policy (full refund up to 48 h before check-in, else 50%).

**Clarifying questions.** One hotel or a chain? Overbooking allowed? Hold rooms during payment? Partial-day / hourly stays? Multiple rooms in one booking?

**Entities.** `Room`, `RoomType`, `DateRange` (value object with `Overlaps`), `Booking`, `BookingStatus`, `IRatePolicy`, `ICancellationPolicy`, `HotelBookingService`.

```text
HotelBookingService --has--> Room 1..* (Number, Type, BaseRate)
HotelBookingService --has--> Booking 0..* (Id, RoomNumber, GuestId, Stay: DateRange, Status)
HotelBookingService --uses--> IRatePolicy <|.. WeekendSurchargePolicy
HotelBookingService --uses--> ICancellationPolicy <|.. TieredRefundPolicy
DateRange (value object): Start, End, Overlaps(other), Nights, EachNight()
```

```csharp
public enum RoomType { Single, Double, Suite }
public enum BookingStatus { Confirmed, Cancelled }

public sealed record Room(int Number, RoomType Type, decimal BaseRate);

public sealed record DateRange
{
    public DateOnly Start { get; }
    public DateOnly End { get; }                          // exclusive: the check-out day
    public DateRange(DateOnly start, DateOnly end)
    {
        if (end <= start) throw new ArgumentException("Check-out must be after check-in");
        (Start, End) = (start, end);
    }
    // half-open intervals: [10,12) and [12,14) do NOT overlap (same-day turnover)
    public bool Overlaps(DateRange o) => Start < o.End && o.Start < End;
    public int Nights => End.DayNumber - Start.DayNumber;
    public IEnumerable<DateOnly> EachNight() => Enumerable.Range(0, Nights).Select(Start.AddDays);
}

public sealed class Booking(Guid guestId, int roomNumber, DateRange stay, decimal total)
{
    public Guid Id { get; } = Guid.NewGuid();
    public Guid GuestId { get; } = guestId;
    public int RoomNumber { get; } = roomNumber;
    public DateRange Stay { get; } = stay;
    public decimal Total { get; } = total;
    public BookingStatus Status { get; internal set; } = BookingStatus.Confirmed;
}

public interface IRatePolicy { decimal PriceFor(Room room, DateOnly night); }
public sealed class WeekendSurchargePolicy(decimal percent) : IRatePolicy
{
    public decimal PriceFor(Room r, DateOnly night) =>
        night.DayOfWeek is DayOfWeek.Friday or DayOfWeek.Saturday
            ? r.BaseRate * (1 + percent / 100m) : r.BaseRate;
}

public interface ICancellationPolicy { decimal RefundFor(Booking b, DateTimeOffset now); }
// TieredRefundPolicy: full refund if >= 48 h before check-in (hotel-local 14:00), else 50%

public sealed class HotelBookingService(IEnumerable<Room> rooms, IRatePolicy rates,
    ICancellationPolicy cancellation, TimeProvider clock)
{
    private readonly IReadOnlyList<Room> _rooms = rooms.ToList();
    private readonly List<Booking> _bookings = new();
    private readonly object _sync = new();          // one hotel: a single lock is fine

    public IReadOnlyList<Room> SearchAvailable(RoomType type, DateRange stay)
    {
        lock (_sync) return _rooms.Where(r => r.Type == type && IsFree(r.Number, stay)).ToList();
    }

    public Booking Book(Guid guestId, RoomType type, DateRange stay)
    {
        lock (_sync)                                 // check + insert must be atomic
        {
            var room = _rooms.FirstOrDefault(r => r.Type == type && IsFree(r.Number, stay))
                       ?? throw new InvalidOperationException("No room of this type is available");
            var total = stay.EachNight().Sum(n => rates.PriceFor(room, n));
            var booking = new Booking(guestId, room.Number, stay, total);
            _bookings.Add(booking);
            return booking;
        }
    }

    public decimal Cancel(Guid bookingId)
    {
        lock (_sync)
        {
            var b = _bookings.Single(x => x.Id == bookingId);
            if (b.Status == BookingStatus.Cancelled) return 0m;            // idempotent
            b.Status = BookingStatus.Cancelled;
            return cancellation.RefundFor(b, clock.GetUtcNow());
        }
    }

    private bool IsFree(int roomNumber, DateRange stay) =>
        !_bookings.Any(b => b.RoomNumber == roomNumber &&
                            b.Status == BookingStatus.Confirmed && b.Stay.Overlaps(stay));
}
```

**Concurrency with a real database (multiple API instances).** An in-memory lock protects one process only. Option 1 below makes double booking impossible by design; option 2 is a range check `SELECT ... WITH (UPDLOCK, HOLDLOCK) WHERE CheckIn < @out AND @in < CheckOut` followed by the insert in the same transaction (key-range locks block concurrent inserts).

```sql
-- Option 1: one row per room per night; the unique key makes double booking impossible
CREATE TABLE RoomNight (
    RoomNumber INT NOT NULL, Night DATE NOT NULL, BookingId UNIQUEIDENTIFIER NOT NULL,
    CONSTRAINT PK_RoomNight PRIMARY KEY (RoomNumber, Night));
-- insert all nights of the stay in one transaction; a duplicate-key error = room taken

```

**Patterns used.** Strategy (rate and cancellation policies), value object (`DateRange` encapsulates the overlap rule), Facade service. **Edge cases.** Check-out before check-in; same-day turnover (half-open ranges); booking in the past; cancelling twice (idempotent); price changes after booking (total is snapshotted); time zones (store hotel-local dates, convert deadlines with the hotel's zone); hold during payment (status `Held` with expiry, released by a job).

:::q How do you check if two date ranges overlap?
Treat them as half-open `[start, end)`; they overlap when `a.Start < b.End && b.Start < a.End`. That one condition covers containment, partial overlap and equality, and allows check-out and check-in on the same day.
:::

:::q How would you support overbooking by 5%?
Make availability a policy: `IAvailabilityPolicy.CanBook(type, stay, confirmedCount, capacity)` with a default "count < capacity" and an overbooking implementation "count < capacity x 1.05". Bookings are then assigned to physical rooms at check-in. The service stays unchanged.
:::

### Cab Booking

**Requirements.**
- Rider requests a ride (pickup, drop). System finds a nearby available driver using a **matching strategy** (nearest, best-rated, lowest ETA).
- Driver accepts; trip moves through `Requested -> DriverAssigned -> InProgress -> Completed`, or `Cancelled`.
- Fare = base + per km + per minute, times a surge multiplier.
- A driver can be on only one trip at a time.

**Clarifying questions.** Vehicle categories (mini, sedan)? Pooling? Driver rejection and timeout? Cancellation fees? Scale of driver location updates?

**Entities.** `Location`, `Rider`, `Driver` (+ availability), `Trip` (state machine), `IDriverMatchingStrategy`, `IFareStrategy`, `RideService`.

```text
RideService --uses--> IDriverMatchingStrategy <|.. NearestDriverStrategy, BestRatedNearbyStrategy
RideService --uses--> IFareStrategy <|.. StandardFare (base + km + min) x surge
RideService --creates--> Trip (Rider, Driver?, Pickup, Drop, Status, Fare)
Trip states: Requested -> DriverAssigned -> InProgress -> Completed
                 \---------------\--------> Cancelled (before InProgress)
Driver: Id, Location, Rating, TryReserve()/Release()  (atomic availability)
```

```csharp
public readonly record struct Location(double Lat, double Lon)
{
    public double DistanceKm(Location o)                       // haversine
    {
        static double Rad(double d) => d * Math.PI / 180;
        double dLat = Rad(o.Lat - Lat), dLon = Rad(o.Lon - Lon);
        double a = Math.Pow(Math.Sin(dLat / 2), 2) +
                   Math.Cos(Rad(Lat)) * Math.Cos(Rad(o.Lat)) * Math.Pow(Math.Sin(dLon / 2), 2);
        return 2 * 6371 * Math.Asin(Math.Sqrt(a));
    }
}

public sealed record Rider(Guid Id, string Name);

public sealed class Driver(Guid id, string name, double rating)
{
    private int _busy;                                         // 0 = available, 1 = busy
    public Guid Id { get; } = id;
    public string Name { get; } = name;
    public double Rating { get; } = rating;
    public Location Location { get; set; }                     // updated by GPS pings
    public bool IsAvailable => Volatile.Read(ref _busy) == 0;
    public bool TryReserve() => Interlocked.CompareExchange(ref _busy, 1, 0) == 0;   // atomic claim
    public void Release() => Volatile.Write(ref _busy, 0);
}

public interface IDriverMatchingStrategy
{
    IEnumerable<Driver> Rank(IEnumerable<Driver> available, Location pickup);
}
public sealed class NearestDriverStrategy(double maxKm = 5) : IDriverMatchingStrategy
{
    public IEnumerable<Driver> Rank(IEnumerable<Driver> drivers, Location pickup) =>
        drivers.Select(d => (d, km: d.Location.DistanceKm(pickup)))
               .Where(x => x.km <= maxKm).OrderBy(x => x.km).Select(x => x.d);
}
// BestRatedNearbyStrategy: filter within 3 km, OrderByDescending(d => d.Rating)

public interface IFareStrategy { decimal Calculate(double km, TimeSpan duration, decimal surge); }
public sealed class StandardFare(decimal baseFare, decimal perKm, decimal perMinute) : IFareStrategy
{
    public decimal Calculate(double km, TimeSpan d, decimal surge) =>
        Math.Round((baseFare + perKm * (decimal)km + perMinute * (decimal)d.TotalMinutes) * surge, 2);
}

public enum TripStatus { Requested, DriverAssigned, InProgress, Completed, Cancelled }

public sealed class Trip(Rider rider, Location pickup, Location drop)
{
    private static readonly Dictionary<TripStatus, TripStatus[]> Next = new()
    {
        [TripStatus.Requested] = [TripStatus.DriverAssigned, TripStatus.Cancelled],
        [TripStatus.DriverAssigned] = [TripStatus.InProgress, TripStatus.Cancelled],
        [TripStatus.InProgress] = [TripStatus.Completed],
        [TripStatus.Completed] = [], [TripStatus.Cancelled] = []
    };
    public Guid Id { get; } = Guid.NewGuid();
    public Rider Rider { get; } = rider;
    public Location Pickup { get; } = pickup;
    public Location Drop { get; } = drop;
    public Driver? Driver { get; private set; }
    public TripStatus Status { get; private set; } = TripStatus.Requested;
    public DateTimeOffset? StartedAt { get; private set; }
    public decimal? Fare { get; private set; }

    private void MoveTo(TripStatus s)
    {
        if (!Next[Status].Contains(s)) throw new InvalidOperationException($"{Status} -> {s}");
        Status = s;
    }
    public void Assign(Driver d) { MoveTo(TripStatus.DriverAssigned); Driver = d; }
    public void Start(DateTimeOffset now) { MoveTo(TripStatus.InProgress); StartedAt = now; }
    public void Complete(decimal fare) { MoveTo(TripStatus.Completed); Fare = fare; Driver!.Release(); }
    public void Cancel() { MoveTo(TripStatus.Cancelled); Driver?.Release(); }
}

public sealed class RideService(IEnumerable<Driver> drivers, IDriverMatchingStrategy matching,
    IFareStrategy fares, TimeProvider clock)
{
    private readonly List<Driver> _drivers = drivers.ToList();

    public Trip RequestRide(Rider rider, Location pickup, Location drop)
    {
        var trip = new Trip(rider, pickup, drop);
        foreach (var d in matching.Rank(_drivers.Where(x => x.IsAvailable), pickup))
        {
            if (!d.TryReserve()) continue;           // lost the race to another request
            trip.Assign(d);                          // (real system: send offer, wait for accept)
            return trip;
        }
        trip.Cancel();
        throw new InvalidOperationException("No drivers available nearby");
    }

    public void StartTrip(Trip t) => t.Start(clock.GetUtcNow());

    public decimal EndTrip(Trip t, decimal surge = 1m)
    {
        var duration = clock.GetUtcNow() - t.StartedAt!.Value;
        var fare = fares.Calculate(t.Pickup.DistanceKm(t.Drop), duration, surge);
        t.Complete(fare);
        return fare;
    }
}
```

**Patterns used.** Strategy (matching, fare, surge), State via transition table (trip), atomic compare-and-swap for driver claims (no global lock), Observer for real-time updates (trip status events pushed to rider/driver apps).

**Edge cases.** Two riders matched to the same driver (CAS `TryReserve`); driver rejects or times out (release and try the next ranked driver); rider cancels after assignment (fee policy, release driver); no drivers (expand radius, queue the request); driver goes offline mid-trip; GPS jitter (snap to roads; use actual route distance for the fare, not straight-line).

:::q How do you find nearby drivers efficiently at scale?
Do not scan all drivers. Index locations with a geospatial structure: geohash or H3 cells, a quadtree, or Redis `GEOADD`/`GEOSEARCH`. Query the rider's cell and neighbours, then rank the small candidate set with the matching strategy. Driver pings update the index every few seconds.
:::

:::q Why use compare-and-swap instead of a lock for driver reservation?
Reservation is a single flag change, so `Interlocked.CompareExchange` makes it atomic without blocking other threads; many requests can try different drivers concurrently and the loser simply moves on. Across services the same idea becomes a conditional update in the database or a Redis `SET NX`.
:::

### Notification Service

**Requirements.**
- Send notifications over Email, SMS, Push, In-app; new channels must be easy to add.
- Respect user preferences (opt-out per channel/category) and quiet hours; OTPs ignore quiet hours.
- Templates with placeholders.
- Asynchronous: producers enqueue and return; workers send with **retry + backoff**, then dead-letter after N attempts.
- Deduplicate (same order event must not send two emails); priority (OTP before marketing).

**Clarifying questions.** Volumes? Delivery receipts? Per-user rate limits? Localisation? Scheduling?

**Entities.** `Notification`, `NotificationRequest`, `INotificationChannel` (+ `EmailChannel`, `SmsChannel`, `PushChannel`), `IPreferenceStore`, `ITemplateRenderer`, `NotificationService` (producer/observer), `NotificationWorker` (consumer, retry, DLQ).

```text
Domain events (OrderShipped, OtpRequested) --observed by--> NotificationService
NotificationService --uses--> IPreferenceStore, ITemplateRenderer
NotificationService --enqueues--> Channel<Notification> (bounded, priority lanes)
NotificationWorker (BackgroundService) --dequeues--> picks INotificationChannel by Kind
INotificationChannel <|.. EmailChannel, SmsChannel, PushChannel   (Strategy)
NotificationWorker --on N failures--> IDeadLetterStore
```

```csharp
public enum ChannelKind { Email, Sms, Push }
public enum Priority { High, Normal }

public sealed record Notification(Guid Id, Guid UserId, ChannelKind Channel, string Subject,
    string Body, Priority Priority, string DedupKey)
{
    public int Attempts { get; init; }
}

public interface INotificationChannel
{
    ChannelKind Kind { get; }
    Task SendAsync(Notification n, CancellationToken ct);       // throws on failure
}
public sealed class EmailChannel(IEmailSender smtp) : INotificationChannel
{
    public ChannelKind Kind => ChannelKind.Email;
    public Task SendAsync(Notification n, CancellationToken ct) => smtp.SendAsync(n.UserId, n.Subject, n.Body, ct);
}
// SmsChannel, PushChannel follow the same shape (Adapter over Twilio / FCM SDKs)

public interface IEmailSender { Task SendAsync(Guid userId, string subject, string body, CancellationToken ct); }
public interface IPreferenceStore { IReadOnlySet<ChannelKind> EnabledChannels(Guid userId, string category); }
public interface ITemplateRenderer { (string Subject, string Body) Render(string template, object model); }
public interface IDedupStore { bool TryMark(string key); }         // e.g. Redis SET NX with TTL
public interface IDeadLetterStore { void Add(Notification n, Exception error); }

public sealed class NotificationQueue
{
    // two bounded lanes = simple priority + backpressure
    public Channel<Notification> High { get; } = Channel.CreateBounded<Notification>(10_000);
    public Channel<Notification> Normal { get; } = Channel.CreateBounded<Notification>(100_000);
    public ValueTask EnqueueAsync(Notification n, CancellationToken ct) =>
        (n.Priority == Priority.High ? High : Normal).Writer.WriteAsync(n, ct);   // waits when full
}

public sealed class NotificationService(IPreferenceStore prefs, ITemplateRenderer templates,
    IDedupStore dedup, NotificationQueue queue)
{
    // observer entry point: called by domain-event handlers (OrderShipped, OtpRequested, ...)
    public async Task NotifyAsync(Guid userId, string category, string template, object model,
        Priority priority, string eventId, CancellationToken ct)
    {
        var (subject, body) = templates.Render(template, model);
        foreach (var channel in prefs.EnabledChannels(userId, category))
        {
            var key = $"{eventId}:{userId}:{channel}";
            if (!dedup.TryMark(key)) continue;                       // already sent/queued
            await queue.EnqueueAsync(new Notification(Guid.NewGuid(), userId, channel,
                subject, body, priority, key), ct);
        }
    }
}

public sealed class NotificationWorker(NotificationQueue queue, IEnumerable<INotificationChannel> channels,
    IDeadLetterStore dlq, ILogger<NotificationWorker> log) : BackgroundService
{
    private const int MaxAttempts = 5;
    private readonly Dictionary<ChannelKind, INotificationChannel> _channels =
        channels.ToDictionary(c => c.Kind);                          // registry instead of switch

    protected override async Task ExecuteAsync(CancellationToken stop)
    {
        while (!stop.IsCancellationRequested)
        {
            // prefer the high-priority lane; otherwise wait for either lane
            if (!queue.High.Reader.TryRead(out var n) && !queue.Normal.Reader.TryRead(out n))
            {
                await Task.WhenAny(queue.High.Reader.WaitToReadAsync(stop).AsTask(),
                                   queue.Normal.Reader.WaitToReadAsync(stop).AsTask());
                continue;
            }
            await SendWithRetryAsync(n, stop);
        }
    }

    private async Task SendWithRetryAsync(Notification n, CancellationToken ct)
    {
        try { await _channels[n.Channel].SendAsync(n, ct); }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            var next = n with { Attempts = n.Attempts + 1 };
            if (next.Attempts >= MaxAttempts) { dlq.Add(next, ex); return; }
            var delay = TimeSpan.FromSeconds(Math.Pow(2, next.Attempts))      // 2,4,8,16 s
                      + TimeSpan.FromMilliseconds(Random.Shared.Next(0, 500)); // jitter
            log.LogWarning(ex, "Retry {Attempt} for {Id} in {Delay}", next.Attempts, n.Id, delay);
            _ = Task.Delay(delay, ct).ContinueWith(_ => queue.EnqueueAsync(next, ct).AsTask(),
                ct, TaskContinuationOptions.OnlyOnRanToCompletion, TaskScheduler.Default); // re-queue later
        }
    }
}
```

In a distributed deployment the in-process `Channel<T>` becomes a broker queue per channel (Service Bus/RabbitMQ) with scheduled redelivery and a real DLQ; the classes keep the same responsibilities.

**Patterns used.** Strategy (one class per channel; registry by `Kind`), Observer (domain events trigger notifications; the producer does not know channels), Adapter (channels wrap Twilio/SendGrid/FCM SDKs), Decorator (rate-limiting or logging channel wrappers), producer-consumer queue with backpressure, retry with exponential backoff + jitter, dead-letter.

**Edge cases.** Duplicate events (dedup key with TTL); user opted out after enqueue (re-check preferences in the worker for marketing); provider outage (circuit breaker per provider, failover to a secondary SMS provider); invalid address (permanent error: DLQ immediately, don't retry); quiet hours (schedule for later unless `High`); message ordering is not guaranteed and usually not needed.

:::q How would you add WhatsApp as a new channel?
Add `ChannelKind.WhatsApp` and a `WhatsAppChannel : INotificationChannel` adapter over the provider's SDK, register it in DI, and expose it in user preferences. The worker resolves channels from the registry, so no dispatching code changes — Open/Closed.
:::

:::q How do you avoid sending the same notification twice?
Give each logical notification a deterministic key (event id + user + channel) and atomically record it (`SET key NX EX 86400` in Redis or a unique index) before enqueuing; providers that accept idempotency keys get the same key. At-least-once queues still redeliver, so the worker also checks a "sent" marker before calling the provider.
:::

### Payment System

**Requirements.**
- Create a payment for an order (amount, currency, method) through one of several gateways (Stripe, PayPal, Razorpay) chosen by country/method.
- Lifecycle: `Created -> Authorized -> Captured -> (Partially)Refunded`, or `Failed`/`Cancelled`.
- **Idempotent** API: retries with the same idempotency key never charge twice.
- Gateway webhooks update the status; amounts handled in minor units; full audit trail.

**Clarifying questions.** Auth+capture or direct sale? Partial captures/refunds? Currencies? PCI scope (tokenised card data only)? Retry on unknown outcome?

**Entities.** `Payment` (state machine), `PaymentStatus`, `Money`, `IPaymentGateway` (our port), `StripeGatewayAdapter` (adapter over a vendor SDK), `IGatewayRouter`, `IIdempotencyStore`, `PaymentService`.

```text
PaymentService --uses--> IIdempotencyStore, IGatewayRouter, IPaymentRepository
IGatewayRouter --returns--> IPaymentGateway <|.. StripeGatewayAdapter, PayPalGatewayAdapter
StripeGatewayAdapter --wraps--> IStripeClient (3rd-party SDK, different interface)  [Adapter]
Payment: Id, OrderId, Amount(Money), Status, GatewayRef, Refunded, History
States: Created -> Authorized -> Captured -> PartiallyRefunded -> Refunded
           \-> Failed        \-> Cancelled
```

```csharp
public readonly record struct Money(long MinorUnits, string Currency);      // 1999 = 19.99 USD

public enum PaymentStatus { Created, Authorized, Captured, PartiallyRefunded, Refunded, Failed, Cancelled }

public sealed record GatewayResult(bool Success, string? GatewayRef, string? Error);

public interface IPaymentGateway                                      // our port
{
    string Name { get; }
    Task<GatewayResult> AuthorizeAsync(Guid paymentId, Money amount, string methodToken, CancellationToken ct);
    Task<GatewayResult> CaptureAsync(string gatewayRef, Money amount, CancellationToken ct);
}

// --- vendor SDK (shape we do not control) ---
public sealed record StripeIntent(string Id, string Status);
public interface IStripeClient   // stands in for the vendor SDK
{
    Task<StripeIntent> CreateIntentAsync(long amount, string currency, string pm,
                                         bool captureLater, string idempotencyKey);
    Task<StripeIntent> CaptureIntentAsync(string id, long amount);
}

// --- Adapter: translate our port to the vendor API ---
public sealed class StripeGatewayAdapter(IStripeClient stripe) : IPaymentGateway
{
    public string Name => "stripe";

    public async Task<GatewayResult> AuthorizeAsync(Guid paymentId, Money m, string token, CancellationToken ct)
    {
        var i = await stripe.CreateIntentAsync(m.MinorUnits, m.Currency.ToLowerInvariant(), token,
                                               captureLater: true, idempotencyKey: paymentId.ToString());
        return i.Status == "requires_capture" ? new(true, i.Id, null) : new(false, i.Id, i.Status);
    }
    public async Task<GatewayResult> CaptureAsync(string gatewayRef, Money m, CancellationToken ct)
    {
        var i = await stripe.CaptureIntentAsync(gatewayRef, m.MinorUnits);
        return new(i.Status == "succeeded", i.Id, i.Status == "succeeded" ? null : i.Status);
    }
}

public sealed class Payment(Guid orderId, Money amount, string gateway)
{
    private static readonly Dictionary<PaymentStatus, PaymentStatus[]> Allowed = new()
    {
        [PaymentStatus.Created] = [PaymentStatus.Authorized, PaymentStatus.Failed],
        [PaymentStatus.Authorized] = [PaymentStatus.Captured, PaymentStatus.Cancelled, PaymentStatus.Failed],
        [PaymentStatus.Captured] = [PaymentStatus.PartiallyRefunded, PaymentStatus.Refunded],
        [PaymentStatus.PartiallyRefunded] = [PaymentStatus.PartiallyRefunded, PaymentStatus.Refunded],
        [PaymentStatus.Refunded] = [], [PaymentStatus.Failed] = [], [PaymentStatus.Cancelled] = []
    };
    public Guid Id { get; } = Guid.NewGuid();
    public Guid OrderId { get; } = orderId;
    public Money Amount { get; } = amount;
    public string Gateway { get; } = gateway;
    public string? GatewayRef { get; private set; }
    public long RefundedMinor { get; private set; }
    public PaymentStatus Status { get; private set; } = PaymentStatus.Created;
    public List<string> History { get; } = new();                   // audit trail

    public void Transition(PaymentStatus next, string? gatewayRef = null, string? note = null)
    {
        if (!Allowed[Status].Contains(next)) throw new InvalidOperationException($"{Status} -> {next}");
        History.Add($"{DateTime.UtcNow:O} {Status} -> {next} {note}");
        Status = next; GatewayRef ??= gatewayRef;
    }

    public void ApplyRefund(long minor)
    {
        if (minor <= 0 || RefundedMinor + minor > Amount.MinorUnits)
            throw new InvalidOperationException("Refund exceeds captured amount");
        RefundedMinor += minor;
        Transition(RefundedMinor == Amount.MinorUnits ? PaymentStatus.Refunded : PaymentStatus.PartiallyRefunded);
    }
}

public interface IGatewayRouter { IPaymentGateway For(string country, string method); }   // Strategy/Factory
public interface IIdempotencyStore
{
    Task<Guid?> TryGetAsync(string key, CancellationToken ct);
    Task<bool> TryAddAsync(string key, Guid paymentId, CancellationToken ct);  // unique key
}
public interface IPaymentRepository
{
    Task AddAsync(Payment p, CancellationToken ct);
    Task<Payment> GetAsync(Guid id, CancellationToken ct);
    Task SaveAsync(Payment p, CancellationToken ct);               // optimistic concurrency
}

public sealed class PaymentService(IGatewayRouter router, IEnumerable<IPaymentGateway> gateways,
    IIdempotencyStore idempotency, IPaymentRepository repo)
{
    public async Task<Payment> AuthorizeAsync(string idemKey, Guid orderId, Money amount,
        string country, string method, string methodToken, CancellationToken ct)
    {
        if (await idempotency.TryGetAsync(idemKey, ct) is { } existingId)
            return await repo.GetAsync(existingId, ct);                    // replay: same result

        var gateway = router.For(country, method);
        var payment = new Payment(orderId, amount, gateway.Name);
        if (!await idempotency.TryAddAsync(idemKey, payment.Id, ct))       // lost a concurrent race
            return await repo.GetAsync((await idempotency.TryGetAsync(idemKey, ct))!.Value, ct);
        await repo.AddAsync(payment, ct);

        var result = await gateway.AuthorizeAsync(payment.Id, amount, methodToken, ct);
        payment.Transition(result.Success ? PaymentStatus.Authorized : PaymentStatus.Failed,
                           result.GatewayRef, result.Error);
        await repo.SaveAsync(payment, ct);
        return payment;
    }

    public async Task CaptureAsync(Guid paymentId, CancellationToken ct)
    {
        var p = await repo.GetAsync(paymentId, ct);
        if (p.Status == PaymentStatus.Captured) return;                    // idempotent
        var result = await Gateway(p).CaptureAsync(p.GatewayRef!, p.Amount, ct);
        p.Transition(result.Success ? PaymentStatus.Captured : PaymentStatus.Failed, note: result.Error);
        await repo.SaveAsync(p, ct);
    }

    private IPaymentGateway Gateway(Payment p) => gateways.Single(g => g.Name == p.Gateway);
}
```

Refunds follow the same shape: call the gateway's refund with a refund-specific idempotency key, then `payment.ApplyRefund(minor)` enforces "never refund more than captured" and moves to `PartiallyRefunded`/`Refunded`.

**Patterns used.** Adapter (each vendor SDK behind `IPaymentGateway`), Strategy/Factory (`IGatewayRouter` picks a gateway by country/method/cost/health), State via transition table (illegal transitions impossible), idempotency keys end to end (API -> our store -> gateway), Repository, audit log.

**Edge cases.** Timeout with unknown outcome (never blindly re-charge: query the gateway by our payment id/idempotency key, or wait for the webhook); duplicate or out-of-order webhooks (verify signature, check the transition is legal, ignore repeats); refund larger than captured; currency rounding (integers in minor units); authorisation expiry (capture within N days, else re-authorise); concurrent capture and cancel (optimistic concurrency on the payment row); gateway outage (circuit breaker + route to a secondary gateway for new payments only).

:::q Why use the Adapter pattern for payment gateways?
Every provider has a different API shape, status names and error codes. An adapter per provider translates them into our single `IPaymentGateway` port, so `PaymentService` never references a vendor SDK, switching or adding a provider is one class, and tests use a fake gateway.
:::

:::q The gateway call timed out. Do you retry the charge?
Not blindly — the charge may have succeeded. I retry with the *same* idempotency key (the provider returns the original result), or first query the provider for the payment's status, and rely on webhooks plus a reconciliation job to settle anything still unknown. The payment stays in a pending state until confirmed.
:::

## Quick-fire Q&A

:::q How do you approach an LLD question?
Clarify requirements and scope, list entities and relationships, sketch a class diagram, identify what varies and apply a fitting pattern, code the interfaces and the core flow, walk through a use case, then cover edge cases, concurrency and extensibility.
:::

:::q Strategy vs State — they look similar; what is the difference?
Both delegate to an interface. With Strategy the *client* chooses an algorithm and it rarely changes during the object's life (pricing, matching). With State the object *itself* switches its state object as events happen, and each state decides the next one (ATM, trip, order).
:::

:::q Composition or inheritance?
Prefer composition: build behaviour from small injected parts (strategies, decorators), which is flexible at runtime and avoids fragile base classes. Use inheritance only for a true "is-a" with a stable base (`Car : Vehicle`) and keep hierarchies shallow.
:::

:::q How do you make an LLD extensible?
Program to interfaces, put varying behaviour behind strategies, create objects through factories or DI registries instead of `switch` statements, raise events for side effects, and keep classes single-purpose. A new requirement should mean a new class, not edits across existing ones.
:::

:::q How do you handle concurrency in booking-type problems?
Make "check availability + reserve" atomic: a `lock` or compare-and-swap in a single process, and in real systems a database guarantee — unique constraint (room-night, show-seat), conditional `UPDATE ... WHERE status = Free`, or optimistic concurrency with `rowversion`. Add idempotency keys so retries do not create duplicates.
:::

:::q Adapter vs Decorator vs Proxy?
Adapter changes an interface into another one the client expects (vendor SDK -> `IPaymentGateway`). Decorator keeps the same interface and adds behaviour (retry, logging, caching). Proxy keeps the same interface and controls access (lazy loading, remote calls, authorisation).
:::

:::q What is wrong with a hand-written Singleton in an ASP.NET Core app?
It hides dependencies, is hard to replace in tests and often holds shared mutable state that becomes a thread-safety bug. Register the class with `AddSingleton` instead, keep it stateless or internally synchronised, and inject it.
:::

:::q Entity vs value object?
An entity has an identity that persists while its attributes change (`Order`, `Booking`). A value object is defined only by its values, is immutable and compared by value (`Money`, `DateRange`, `Location`) — C# records are a natural fit.
:::

:::q How do you make LLD code testable?
Inject dependencies through constructors (gateways, repositories, notifiers), inject time with `TimeProvider`, keep domain logic in plain classes without I/O, and expose behaviour through interfaces so tests can supply fakes. Then the core rules (pricing, transitions, overlap checks) are unit-testable in isolation.
:::

:::q When would you use an enum with a transition table instead of the State pattern?
When states differ only in which transitions are allowed, not in behaviour. A `Dictionary<State, State[]>` is compact, easy to read and to persist. When each state has substantial different behaviour (ATM operations, vending machine), separate state classes are clearer.
:::
