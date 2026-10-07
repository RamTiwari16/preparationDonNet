### What is Dependency Injection? (IoC vs DI vs DIP)

**In simple words:** Dependency Injection (DI) means a class receives the objects it needs from outside, instead of creating them with `new`. DIP (Dependency Inversion Principle) is the design rule: depend on interfaces, not on concrete classes. IoC (Inversion of Control) is the wider idea that the framework creates objects and calls your code. A DI container is the tool that does this work for you.

**Real-life example:** A chef does not build the oven or grow the vegetables. The restaurant supplies them, and the chef just cooks; the manager decides which supplier to use.

**Interview question:** What is the difference between IoC, DI and DIP?

**Simple answer:** DIP is the SOLID principle: high-level code depends on abstractions, not on concrete classes. IoC is the idea that the framework controls object creation and flow. DI is the pattern that implements IoC by passing dependencies in, usually through the constructor, and a container automates it.

### Why DI? Before and after

**In simple words:** Without DI, a class creates its own database and email objects with `new`. Then you cannot test it without a real database, and changing a provider means editing the class. With DI, the class asks for interfaces in its constructor. `Program.cs` chooses the real classes, and tests can pass fakes instead.

**Real-life example:** A lamp with a plug works in any socket. A lamp wired straight into the wall needs an electrician every time you want to move or replace it.

**Interview question:** What are the benefits of dependency injection?

**Simple answer:** Loose coupling, so I can swap an implementation by changing one registration line. Testability, because I can pass fakes or mocks instead of a real database or email server. The container also manages lifetimes and disposal, and all wiring lives in one place, `Program.cs`.

```csharp
public class OrderService(IOrderRepository repo, IEmailSender email) { }

builder.Services.AddScoped<IOrderRepository, EfOrderRepository>();
builder.Services.AddSingleton<IEmailSender, SendGridEmailSender>();
```

### Constructor, property, and method injection

**In simple words:** Constructor injection passes required dependencies through the constructor; this is the default. Property injection sets an optional dependency on a public property, but the built-in container does not support it. Method injection passes a dependency to one method call. ASP.NET Core supports it in `[FromServices]` action parameters, minimal API handlers and middleware `InvokeAsync`.

**Real-life example:** A new employee gets a laptop on day one (constructor). They may get a parking card later, if needed (property), and they borrow a projector for one meeting only (method).

**Interview question:** Why is constructor injection preferred?

**Simple answer:** Dependencies are visible in the constructor, required, and can be read-only, so the object is always complete. Missing registrations show up at startup with `ValidateOnBuild`. It is also the only style the built-in container supports, besides method injection in actions, handlers and middleware.

### How the container works

**In simple words:** At startup, you add registrations to `IServiceCollection`: the service type, the implementation and the lifetime. `Build()` turns this list into an `IServiceProvider`. For each request, ASP.NET Core creates a scope and builds objects from it, resolving constructor parameters one by one. When the request ends, the scope is disposed, together with the disposable objects it created.

**Real-life example:** A restaurant keeps a staff list (registrations). Each table gets its own waiter for the meal (scope), and when the guests leave, the table is cleared.

**Interview question:** What is the difference between `GetService` and `GetRequiredService`?

**Simple answer:** `GetService<T>()` returns `null` if the service is not registered. `GetRequiredService<T>()` throws an exception, so the problem is clear at once. I prefer `GetRequiredService`, and I use these methods only in infrastructure code, not in business classes.

### Service registration APIs

**In simple words:** You register services with `AddSingleton`, `AddScoped` or `AddTransient`, using a class, an instance or a factory. `TryAdd` registers only if nothing is registered yet, so apps can override library defaults. Register several classes for one interface and inject `IEnumerable<T>` to get all of them. In .NET 8 and later, keyed services let you pick one by a key.

**Real-life example:** A taxi company has many drivers. You can ask for any driver (the last one registered), all drivers (`IEnumerable<T>`), or the driver with a specific badge number (keyed service).

**Interview question:** How do you register multiple implementations of one interface and pick one?

**Simple answer:** I register each one and inject `IEnumerable<T>` to get all of them in registration order. Injecting `T` alone gives the last one registered. To pick a specific one, I use keyed services with `[FromKeyedServices("key")]` in .NET 8 and later.

```csharp
builder.Services.AddKeyedScoped<IPaymentGateway, StripeGateway>("card");
builder.Services.AddKeyedScoped<IPaymentGateway, PayPalGateway>("paypal");

public class RefundService([FromKeyedServices("card")] IPaymentGateway gw) { }
```

### Service lifetimes: Singleton, Scoped, Transient

**In simple words:** When ASP.NET Core creates an object for you, the lifetime decides how long that object is reused. Singleton means one object for the whole app. Scoped means one object per web request. Transient means a new object every time someone asks for it.

**Real-life example:** In an office, the building's main door is a singleton — everyone uses the same one. A visitor badge is scoped — you get one when you arrive and return it when you leave. A paper cup at the water cooler is transient — you take a new one each time.

**Interview question:** What is the difference between Singleton, Scoped and Transient?

**Simple answer:** Singleton creates one object and shares it for the app's whole life. Scoped creates one object per HTTP request, so all classes in that request share it — that is why DbContext is scoped. Transient creates a new object every time it is injected, which suits small, stateless services.

```csharp
builder.Services.AddSingleton<IPriceCache, PriceCache>();
builder.Services.AddScoped<IOrderService, OrderService>();
builder.Services.AddTransient<PriceCalculator>();
```

### Captive dependency problem

**In simple words:** A captive dependency happens when a long-lived service holds a shorter-lived one. The classic bug is a singleton that takes a scoped `DbContext` in its constructor. That `DbContext` then lives forever and is shared by all requests at the same time. In Development, ASP.NET Core detects this and throws "Cannot consume scoped service ... from singleton".

**Real-life example:** A visitor badge is meant for one day. If the permanent receptionist keeps one badge forever and lends it to every visitor, nobody knows who is inside.

**Interview question:** What is a captive dependency, and how do you fix it?

**Simple answer:** It is a longer-lived service holding a shorter-lived one, like a singleton holding a scoped `DbContext`. I turn on `ValidateScopes` and `ValidateOnBuild` in all environments to catch it. I fix it by changing the lifetime, creating a scope with `IServiceScopeFactory`, or using `IDbContextFactory`.

```csharp
builder.Host.UseDefaultServiceProvider(o =>
{
    o.ValidateScopes = true;
    o.ValidateOnBuild = true;
});
```

### Transient IDisposable pitfalls

**In simple words:** The container remembers every disposable object it creates, even transient ones. It disposes them only when the scope that created them ends; inside a request, that is the end of the request. If you resolve a transient disposable from the root provider, it stays in memory until the app stops. Doing that again and again is a memory leak.

**Real-life example:** A hotel collects your used towels when you check out. Towels taken by the hotel office itself are never collected, so that pile keeps growing.

**Interview question:** Do transient services that implement `IDisposable` get disposed?

**Simple answer:** Yes, but only when the scope that created them is disposed, for example at the end of the request. If I resolve them from the root provider, they live until app shutdown and leak memory. So I resolve them inside a short scope, and I never call `Dispose` on injected services myself.

### IServiceScopeFactory in BackgroundService

**In simple words:** Hosted services are singletons, so you cannot inject a scoped `DbContext` into their constructor. Instead, inject `IServiceScopeFactory`. In each loop, create a new scope, get the `DbContext` from it, do the work, and dispose the scope. Each loop then gets a fresh `DbContext` and a clean change tracker.

**Real-life example:** A night cleaner takes a fresh bucket of water for each floor. They do not use one dirty bucket for the whole night.

**Interview question:** How do you use a `DbContext` inside a `BackgroundService`?

**Simple answer:** I inject `IServiceScopeFactory`, create an async scope for each unit of work, and resolve the `DbContext` from that scope. The scope is disposed at the end of the iteration, which frees the context. Another option is `IDbContextFactory<T>`, where I create and dispose the context myself.

```csharp
await using var scope = scopeFactory.CreateAsyncScope();
var db = scope.ServiceProvider.GetRequiredService<ShopDbContext>();
// work with db, then the scope disposes it
```

### Built-in container vs Autofac / Scrutor

**In simple words:** The built-in container is fast, works with Native AOT, and covers most needs: lifetimes, factories, open generics, `IEnumerable<T>` and keyed services. Scrutor is an add-on for assembly scanning (registering many classes at once) and decorators. Autofac is a full replacement container with property injection, interception and child scopes.

**Real-life example:** Your phone's built-in camera app is enough for most photos. You install a special app only when you need extra features.

**Interview question:** Would you use the built-in container or Autofac?

**Simple answer:** I stay with the built-in container, because it is fast and covers keyed services, open generics and factories. I add Scrutor for scanning and decorators. I bring in Autofac only for advanced needs like interception or tagged lifetime scopes.

### Service Locator anti-pattern

**In simple words:** Service Locator means a class asks `IServiceProvider` for its dependencies inside its methods, instead of declaring them in the constructor. This hides what the class really needs. Missing registrations fail late, deep in a code path, and unit tests need a container. It is acceptable only in infrastructure code, like factories, middleware or background services that create scopes.

**Real-life example:** A cook who searches the whole building for each ingredient fails at dinner time. A cook with a clear ingredient list gets everything before cooking starts.

**Interview question:** Why is Service Locator considered an anti-pattern?

**Simple answer:** Dependencies are hidden inside method bodies instead of shown in the constructor. Errors appear at runtime, tests are harder, and lifetime bugs stay hidden. I use it only in infrastructure code, such as small factories or scope creation in background services.

### Lifetime demo with a controller and a helper

**In simple words:** This demo gives each service a random `Guid` when it is created. The controller and a helper class both receive a singleton, a scoped and a transient service. The singleton ID never changes, and the scoped ID is shared inside one request but new in the next. The transient ID is different in every place it is injected.

**Real-life example:** The school building is the same for everyone, every day (singleton). Today's timetable is shared by teacher and students but changes tomorrow (scoped), and each worksheet handed out is new (transient).

**Interview question:** What output would you expect from this demo across two requests?

**Simple answer:** The singleton ID is the same everywhere in both requests. The scoped ID matches between the controller and the helper inside one request, but is new in request 2. The transient ID differs between the controller and the helper, even in the same request.

### Why should DbContext be Scoped?

**In simple words:** A `DbContext` is a unit of work: it tracks all changes in one business operation and saves them in one transaction with `SaveChanges`. It is not thread-safe, so two requests must never use it at the same time. In a web API, one request is one operation, so one context per request fits best. All repositories in the request share it and save together.

**Real-life example:** At a supermarket, one basket holds all your items and you pay once. Sharing one basket with every customer, or using a new basket for each item, would both fail.

**Interview question:** Why should `DbContext` be scoped and not singleton or transient?

**Simple answer:** Scoped gives one context per request, so all repositories share tracked entities and save in one transaction. Singleton breaks because the context is not thread-safe, mixes users' changes and grows in memory forever. Transient splits the work across many contexts, so there is no single transaction and more connections are used.

### DbContext in BackgroundService and hosted services

**In simple words:** Hosted services are singletons, so injecting a `DbContext` into their constructor is a captive dependency. Create a new scope for each unit of work, like each message or batch. Never use the request's `DbContext` inside a fire-and-forget `Task.Run`. The request scope ends when the response is sent, and the context is disposed with it.

**Real-life example:** A courier gets a new delivery sheet for each trip. Yesterday's sheet is already filed away and cannot be used.

**Interview question:** Why does a background task throw `ObjectDisposedException` when it uses the request's `DbContext`?

**Simple answer:** The request scope is disposed when the response finishes, so its `DbContext` is disposed too. The background task then touches a disposed context. I fix it by putting a message on a queue or `Channel` and processing it in a `BackgroundService` that creates its own scope per message.

### Testing with DI

**In simple words:** Because classes depend on interfaces, you can unit test them with fakes or mocks (test objects that act like the real ones). For integration tests, `WebApplicationFactory<Program>` runs the real app in memory. In `ConfigureTestServices`, you replace services: for example, the real database with SQLite or Testcontainers, and the email sender with a fake.

**Real-life example:** A driving school car is a real car, but it has an extra brake for the instructor. Some parts are swapped so that practice is safe.

**Interview question:** How do you replace a service in integration tests?

**Simple answer:** I use `WebApplicationFactory<Program>` and, in `ConfigureTestServices`, call `RemoveAll<T>()` and register the fake. It runs after the app's own registrations, so the fake wins. I avoid the EF InMemory provider and prefer SQLite or Testcontainers, because they behave like a real database.

```csharp
builder.ConfigureTestServices(services =>
{
    services.RemoveAll<IEmailSender>();
    services.AddSingleton<IEmailSender, FakeEmailSender>();
});
```
