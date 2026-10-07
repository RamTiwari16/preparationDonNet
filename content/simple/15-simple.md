### Monolith vs Modular Monolith vs Microservices

**In simple words:** A *monolith* is one app with all features and one database, deployed as one unit. A *modular monolith* is still one app, but the code is split into strict modules, each with its own data and a public interface. *Microservices* are many small apps, each owning one business area and its own database, deployed separately. Microservices help big teams scale, but they add a lot of complexity.

**Real-life example:** A monolith is one big kitchen where everyone cooks everything. A modular monolith is the same kitchen with separate stations: grill, salads, desserts. Microservices are a food court: separate shops, each with its own staff and fridge.

**Interview question:** Should we use microservices? When should we not?

**Simple answer:** Not by default. I would start with a modular monolith and extract a service only for a clear reason: different scaling needs, a different release speed, a separate team or a different technology. With a small team, an unclear domain or weak DevOps, microservices cost more than they give.

### Microservice characteristics

**In simple words:** A good microservice does one business job, like Orders or Payments. It owns its data, so no other service touches its database. It can be deployed on its own, without waiting for other services. It expects failure, so it uses timeouts and retries, and it has logs, metrics and health checks from day one. Size is not about lines of code: one team of 5–8 people should be able to own it.

**Real-life example:** Shops in a mall. Each has its own owner, stock and opening hours. One shop can renovate without closing the whole mall.

**Interview question:** What are the key characteristics of a microservice?

**Simple answer:** It has one business capability, owns its data and is deployed independently. It is loosely coupled to other services and designed for failure, with timeouts, retries and circuit breakers. It is observable, and its build, test and deploy steps are fully automated.

### Service boundaries (DDD)

**In simple words:** DDD (Domain-Driven Design) helps you decide where one service ends and the next begins. A *bounded context* is an area where each word has one clear meaning. "Product" means different things in Catalog, Pricing and Shipping. A service usually matches one bounded context. To leave a monolith, use the *Strangler Fig* approach: put a gateway in front and move one feature at a time.

**Real-life example:** In a hospital, "patient" means payment details to the accounts team and medical history to the doctors. Each department keeps its own file about the same person.

**Interview question:** How do you find good service boundaries?

**Simple answer:** I look for bounded contexts, often in an Event Storming workshop with domain experts. I split by business capability, not by technical layer like "DataAccessService". I also look at data ownership, teams and how often things change. If two services must talk on every request, they probably belong together.

### Database per service

**In simple words:** Each service has its own private database. Other services get the data only through its API or its events. So a team can change its schema and deploy without breaking others. Each service can also choose the best store, like SQL Server, Redis or Cosmos DB. The cost is no joins and no ACID transactions across services.

**Real-life example:** Each family in a building has its own fridge. If you need milk from a neighbour, you knock and ask. You do not open their fridge yourself.

**Interview question:** Why should each microservice have its own database, and how do you get data across services?

**Simple answer:** A shared database is a hidden contract: one column rename can break five services. For combined data I use *API composition*, where a gateway or BFF calls services in parallel and merges the results. For search and reports I build a *CQRS read model* (a ready-made view) from events. For multi-step business transactions I use a saga.

### Independent deployment

**In simple words:** Independent deployment means you can release or roll back one service without changing or coordinating with any other. For this, contracts must stay backward-compatible: add fields, never remove or rename them. Database changes use *expand/contract*: add the new column, move the data, and remove the old column in a later release. Each service has its own pipeline, plus feature flags and contract tests.

**Real-life example:** A bus company can repaint one bus without stopping the whole fleet, as long as the bus still fits the same bus stops.

**Interview question:** If three services must always be released together, what is that and how do you fix it?

**Simple answer:** That is a *distributed monolith*: you pay the cost of microservices without the benefits. The usual causes are a shared database, chains of synchronous calls or breaking contract changes. I fix it with backward-compatible contracts, events for one-way flows and separate data — or I merge the services back into one.

### API Gateway

**In simple words:** An API gateway is one entry point in front of all your services. Clients call only the gateway, and it routes each request to the right service. It also handles shared jobs: HTTPS, token checks, rate limiting, CORS, logging and caching. In .NET, YARP is the usual choice; Azure API Management is the managed option. A *BFF* (Backend-for-Frontend) is a separate gateway for each client type, like web or mobile.

**Real-life example:** The reception desk of a big company. Visitors talk only to reception, which checks their ID and sends them to the right department.

**Interview question:** What does an API gateway do, and what should it not do?

**Simple answer:** It does routing, TLS termination, token checks, rate limiting, request aggregation and logging at the edge. It must not contain business logic, or it becomes a bottleneck that every team waits on. In .NET I use YARP; for partner APIs with a developer portal I use Azure APIM.

```csharp
builder.Services.AddReverseProxy()
    .LoadFromConfig(builder.Configuration.GetSection("ReverseProxy"));
app.MapReverseProxy();
```

### Service discovery

**In simple words:** Service discovery is how one service finds the address of another. In containers, IP addresses change on every restart or scale-out, so fixed addresses break. On Kubernetes, a Service object gives a stable DNS name, like `http://orders`, and sends traffic only to healthy Pods. Other options are a registry like Consul, or a service mesh.

**Real-life example:** You call a taxi company's one phone number, not a driver's mobile. The company sends whichever driver is free.

**Interview question:** How does service discovery work in Kubernetes?

**Simple answer:** Kubernetes uses server-side discovery. A Service gets a stable virtual IP and DNS name, and readiness probes remove unhealthy Pods from it. So callers simply use `http://orders`. In .NET, `Microsoft.Extensions.ServiceDiscovery`, used by .NET Aspire, also lets code use logical names.

### Authentication across services

**In simple words:** The gateway checks the user's token once at the edge. But each service still checks the token again, because you should never trust the internal network (*zero trust*). When a service calls another for a user, it forwards the token or swaps it for a narrower one (*On-Behalf-Of*). When there is no user, like in a background job, the service uses its own identity (*client credentials* or a managed identity).

**Real-life example:** Security checks your badge at the building's main door. Each secure room still has its own badge reader.

**Interview question:** Where should authentication happen — at the gateway or in each service?

**Simple answer:** In both places. The gateway rejects bad requests early and applies rate limits. Each service still checks the token's signature, issuer, audience and expiry, and authorises by scope or role. Calls between services without a user use client credentials, a managed identity or mTLS (both sides show certificates).

### Synchronous communication: REST vs gRPC

**In simple words:** In synchronous communication, the caller sends a request and waits for the answer. REST uses HTTP and JSON; it is easy to read and works in every browser. gRPC uses HTTP/2 and Protocol Buffers (a small binary format), with a strict `.proto` contract and generated code. It is faster and supports streaming, so it suits internal calls. In .NET, use `IHttpClientFactory` typed clients, not `new HttpClient()` per request.

**Real-life example:** REST is a letter in plain language that anyone can read. gRPC is a fixed form with numbered boxes: faster to process, but both sides need the same form.

**Interview question:** When do you choose gRPC over REST?

**Simple answer:** For internal, high-volume, low-latency calls between services, or when I need streaming and a strict contract. I keep REST for public and browser APIs, where easy debugging matters more. I also avoid long chains of synchronous calls, because each extra hop adds latency and lowers availability.

### Events vs commands vs queries

**In simple words:** Services can talk with messages instead of waiting for replies. A *command* says "do this", like `ReserveStock`, and goes to exactly one receiver. An *event* says "this happened", like `OrderPlaced`, and any number of services can listen. A *query* asks "tell me this" and expects an answer. Events keep services loosely coupled, but the data becomes *eventually consistent* (correct after a short delay).

**Real-life example:** A command is a manager telling one cook, "make a pizza". An event is an announcement, "the shop is now open" — anyone interested can react.

**Interview question:** What is the difference between a command and an event?

**Simple answer:** A command is an intent, named like an order, sent to one receiver that may reject it. An event is a fact, named in the past tense, published to zero or many subscribers, and it cannot be rejected because it already happened. With events I can add a new consumer, like a Loyalty service, without changing the publisher.

### Broker comparison: RabbitMQ vs Kafka vs Azure Service Bus

**In simple words:** A message broker is a server in the middle that stores and delivers messages between services. RabbitMQ is a smart broker that routes messages into queues; it fits task queues and flexible routing. Kafka is a distributed log: messages stay for days, and each consumer group tracks its own position, so you can replay. Azure Service Bus is a fully managed broker with queues, topics, sessions and a built-in dead-letter queue.

**Real-life example:** RabbitMQ and Service Bus are like a post office: each letter is delivered and then removed. Kafka is like a newspaper archive: many readers read the same pages at their own pace and can go back to old issues.

**Interview question:** RabbitMQ vs Kafka — when would you choose each?

**Simple answer:** RabbitMQ for task or command queues with per-message acknowledgement, priorities and flexible routing. Kafka for a high-volume event stream that several consumer groups read independently and may replay. In an Azure company, Service Bus is a good managed choice for business workflows.

### MassTransit (abstraction over brokers)

**In simple words:** MassTransit is a .NET library that gives one programming model over brokers like RabbitMQ and Azure Service Bus. You write *consumers* (classes that handle one message type) and publish messages. It handles retries, error queues, the outbox and sagas for you. Note: version 8 is open source, but version 9 has a commercial license, so check the terms first.

**Real-life example:** A universal travel adapter. Your charger works in any country's socket without changing the charger.

**Interview question:** Why use MassTransit instead of the raw broker client?

**Simple answer:** It removes plumbing code: serialization, retry policies, error queues, outbox and saga state machines. My code mostly stays the same if I move from RabbitMQ to Service Bus. After retries run out, a failed message goes to the `_error` queue. Alternatives are Wolverine, NServiceBus and Rebus.

```csharp
public sealed class OrderPlacedConsumer : IConsumer<OrderPlaced>
{
    public Task Consume(ConsumeContext<OrderPlaced> ctx) =>
        Console.Out.WriteLineAsync($"Charging order {ctx.Message.OrderId}");
}
```

### RabbitMQ essentials

**In simple words:** In RabbitMQ, a publisher sends a message to an *exchange*, not straight to a queue. The exchange uses bindings and a *routing key* to put the message into queues. Exchange types are direct (exact key), topic (key patterns), fanout (all queues) and headers. The consumer sends an *ack* (confirmation) after processing; unacked messages are delivered again. `prefetch` limits how many messages one consumer holds at once.

**Real-life example:** A mail sorting room. Letters arrive at the sorting desk (exchange), which puts them into the right postboxes (queues) based on the address (routing key).

**Interview question:** How do you make sure RabbitMQ does not lose messages?

**Simple answer:** I use a durable exchange, a durable or quorum queue and persistent messages. *Publisher confirms* tell me the broker has stored the message. Consumers ack manually only after processing, so a crash causes redelivery, not loss.

### Kafka essentials

**In simple words:** Kafka stores messages in *topics*, and each topic is split into *partitions* (ordered logs). The message key decides the partition, so messages with the same key stay in order. In a *consumer group*, each partition is read by only one consumer. Consumers track their *offset* (position in the log) and commit it after processing. Messages are kept for a set time, so you can replay them.

**Real-life example:** A bank with several counters. Customers with the same account number always go to the same counter, so their requests are handled in order.

**Interview question:** How does Kafka keep order and scale consumers?

**Simple answer:** Order is guaranteed only inside one partition, so I use a key like `OrderId` to keep related events together. The maximum parallelism equals the number of partitions; extra consumers sit idle. For safety I use `acks=all` and an idempotent producer, and I commit offsets only after successful processing.

### Azure Service Bus essentials

**In simple words:** Azure Service Bus has *queues* for one receiver, and *topics with subscriptions* for many receivers. By default it uses *peek-lock*: the message is locked while you work on it, then you complete, abandon or dead-letter it. After `MaxDeliveryCount` failed tries (10 by default), it moves to the dead-letter queue. *Sessions* keep first-in-first-out order per key, and duplicate detection drops repeated `MessageId`s.

**Real-life example:** A library lends you a book for a fixed time. Return it and you are done. If you do not return it in time, it goes back on the shelf for someone else.

**Interview question:** How does peek-lock work in Service Bus?

**Simple answer:** The receiver locks the message, by default for 30 seconds. On success I complete it. On a temporary error I abandon it, so it is delivered again; on a permanent error I dead-letter it. If the lock expires, the message comes back and its delivery count goes up. I connect with managed identity, not connection strings.

### Delivery guarantees

**In simple words:** Brokers offer three levels. *At-most-once*: a message may be lost but never repeats. *At-least-once*: a message is never lost but may repeat; this is the normal choice. *Exactly-once processing* means at-least-once delivery plus an *idempotent* consumer (doing the same work twice gives the same result as once). True exactly-once delivery between two different systems is not possible in general.

**Real-life example:** A courier keeps coming back until someone signs. If the signature gets lost, the same parcel may arrive twice, so the receiver checks the parcel number first.

**Interview question:** Can you get exactly-once delivery?

**Simple answer:** Not across a network and two systems in general. I use at-least-once delivery, acking after processing, and I make the consumer idempotent with a dedup or inbox table keyed by `MessageId`. Kafka's exactly-once feature only covers read-process-write inside Kafka.

### Message contracts and versioning

**In simple words:** The shape of a message is a public contract, just like an API. You may add new optional fields, but never remove fields or change their meaning. Consumers should ignore fields they do not know (*tolerant reader*). For a breaking change, create a new message version and publish both until every consumer has moved. Add metadata such as `messageId`, `correlationId`, type, version and time.

**Real-life example:** A bank form. Adding a new optional box is fine. But if you change what box 3 means, old forms are processed wrongly.

**Interview question:** How do you change a message contract without breaking consumers?

**Simple answer:** I only add optional fields, and consumers ignore unknown ones. A breaking change becomes a new type, like `OrderPlacedV2`, and I publish both until all consumers migrate. A schema registry can check compatibility in CI. Contracts are shared as a versioned NuGet package, not as domain classes.

### Dead-letter queues and poison messages

**In simple words:** A *poison message* is one that can never be processed, because of bad data or a bug. If you retry it forever, it blocks the queue. A *dead-letter queue* (DLQ) is a side queue that holds such messages, so the rest keep flowing. Retry temporary errors with backoff, send permanent errors to the DLQ, and alert when the DLQ is not empty. After a fix, you can replay them.

**Real-life example:** At the post office, a letter with an unreadable address goes to a special "undeliverable" shelf, so the rest of the mail is not delayed.

**Interview question:** How do you handle poison messages?

**Simple answer:** I separate temporary errors from permanent ones. Temporary errors get a few retries with backoff. Permanent errors, or messages that keep failing, go to the DLQ with the reason. I alert on DLQ depth, fix the cause and replay the messages. Handlers are idempotent, because a replayed message may repeat work.

### Why resilience patterns exist

**In simple words:** Resilience means your system still works well enough when other services are slow, failing or overloaded. Over a network, a call can be slow, get lost or run twice. Without protection, one slow service makes threads and connections pile up, and the failure spreads to every caller (a *cascading failure*). Patterns like timeout, retry, circuit breaker and bulkhead stop this. In .NET they come from Polly v8 and `Microsoft.Extensions.Http.Resilience`.

**Real-life example:** Fuses in your home. If one device has a fault, its fuse trips, and the rest of the house keeps its power.

**Interview question:** Why do microservices need resilience patterns?

**Simple answer:** Network calls fail in ways a normal method call does not: they can be slow, lost or repeated. One slow dependency can block all threads in its callers and take down the whole site. Timeouts, retries, circuit breakers, bulkheads and fallbacks keep the failure small. In .NET I build these with Polly v8 pipelines.

### Retry with exponential backoff and jitter

**In simple words:** Retry means trying a failed call again. *Exponential backoff* makes the wait grow each time: 1 s, 2 s, 4 s. *Jitter* adds a small random amount, so thousands of clients do not retry at the same moment. Retry only temporary errors (timeouts, 429, 5xx) and only *idempotent* operations (safe to repeat). Keep the number of tries small, and retry in one layer only.

**Real-life example:** If a shop's phone line is busy, you wait a bit longer before each new call. If everyone redialled at the exact same second, the line would stay busy.

**Interview question:** Why add jitter to retries?

**Simple answer:** Without jitter, many clients retry at the same moments and overload the service again just as it recovers (a *thundering herd*). Random delays spread the load. I use exponential backoff with jitter and 3–5 tries at most. I never retry a POST like "charge card" without an idempotency key.

### Timeout

**In simple words:** A timeout is the longest time you wait for a call. Every remote call needs one; the default `HttpClient.Timeout` is 100 seconds, which is far too long. Use two levels: an *attempt timeout* for one try, and a *total timeout* for all tries together. Services deeper in the chain should have shorter timeouts than their callers. Pass the `CancellationToken` down, so abandoned work really stops.

**Real-life example:** If your food delivery has not arrived after an hour, you cancel it and cook something else. You do not wait all night.

**Interview question:** How do you set timeouts in a chain of services?

**Simple answer:** Every outgoing call has a per-attempt and a total timeout. Timeouts get shorter as you go deeper, for example 8 s at the caller, 4 s in the middle and 2 s at the last service. I pass the `CancellationToken` down to database calls, so work stops when the caller gives up.

### Circuit breaker

**In simple words:** A circuit breaker counts failures for one dependency. When failures pass a limit, it *opens* and fails new calls at once, without calling the broken service. After a break time, it becomes *half-open* and lets a test call through. If the test works, it *closes* again; if not, it opens again.

**Real-life example:** The electrical breaker in your home trips when there is a fault, so the wires do not burn. After the fault is fixed, you switch it back on.

**Interview question:** Explain the circuit breaker states.

**Simple answer:** Closed: calls go through and failures are counted. Open: after the failure rate passes the limit, calls fail fast for the break time. Half-open: one trial call is allowed; success closes the circuit, failure opens it again. It gives the failing service time to recover and frees my threads quickly.

### Bulkhead

**In simple words:** A bulkhead gives each dependency its own limited set of slots. If one dependency hangs, it can only use its own slots, so calls to other services keep working. In Polly v8, a bulkhead is a *concurrency limiter*: a maximum number of parallel calls plus a small queue. Extra calls are rejected at once instead of piling up.

**Real-life example:** A ship is split into watertight rooms. If one room floods, the water stays there and the ship still floats.

**Interview question:** What is the bulkhead pattern?

**Simple answer:** It isolates resources per dependency, so one slow service cannot use up all threads or connections. For example, calls to Recommendations get 20 parallel slots. If it hangs, checkout calls still have their own capacity, and calls over the limit fail fast.

```csharp
pipeline.AddConcurrencyLimiter(permitLimit: 20, queueLimit: 10);
```

### Rate limiting

**In simple words:** Rate limiting controls how many requests are allowed in a time period. On the server side, it protects your API from too many calls per user, IP or API key, and returns HTTP 429 with a `Retry-After` header. On the client side, it keeps your outgoing calls under a partner's quota. ASP.NET Core has `AddRateLimiter` with fixed window, sliding window, token bucket and concurrency limiters.

**Real-life example:** A theme park ride lets in only 20 people every 5 minutes. Everyone else waits in line or comes back later.

**Interview question:** How do you add rate limiting in ASP.NET Core?

**Simple answer:** I register `AddRateLimiter` with a policy, for example a token bucket per user or per IP. I add `app.UseRateLimiter()` and attach the policy to endpoints with `RequireRateLimiting`. Rejected calls get 429 and a Retry-After header. I often add a limit at the gateway too.

### Fallback and hedging

**In simple words:** A *fallback* returns a reduced but useful answer when a call fails, such as a cached price or an empty recommendations list. Decide per feature what "reduced" means, and never fall back silently on money operations. *Hedging* sends a second request if the first one is slow, and uses whichever answers first. It cuts slow responses, but only for read-only, idempotent calls, because it adds load.

**Real-life example:** Fallback: your dish is sold out, so the waiter offers a similar one. Hedging: you call two taxi companies and take the first car that arrives.

**Interview question:** When would you use a fallback, and when hedging?

**Simple answer:** I use a fallback when a feature can degrade gracefully, like showing the last known price when the price service is down. I use hedging for idempotent reads where the slowest 1% of responses matter and the downstream has spare capacity. I never hedge or silently fall back on payments.

### Complete setup with Microsoft.Extensions.Http.Resilience

**In simple words:** `Microsoft.Extensions.Http.Resilience` adds Polly v8 pipelines to `HttpClient`. One line, `AddStandardResilienceHandler()`, adds a rate limiter, total timeout, retry with backoff and jitter, circuit breaker and attempt timeout, with sensible defaults. You can tune each part, or build your own pipeline with `AddResilienceHandler`. Order matters: the first strategy you add is the outermost.

**Real-life example:** A car's standard safety pack: airbags, ABS and seat belts come together, and you can still adjust each one.

**Interview question:** What does `AddStandardResilienceHandler` give you, and what would you change?

**Simple answer:** It adds a rate limiter, total timeout, retry, circuit breaker and attempt timeout with safe defaults. I tune the timeouts to my service goals and disable retries for unsafe methods like POST, unless there is an idempotency key. I adjust the breaker limits based on real traffic.

```csharp
builder.Services.AddHttpClient<IInventoryClient, InventoryClient>(c =>
        c.BaseAddress = new Uri("http://inventory/"))
    .AddStandardResilienceHandler(o =>
    {
        o.AttemptTimeout.Timeout = TimeSpan.FromSeconds(2);
        o.Retry.DisableForUnsafeHttpMethods();
    });
```

### Distributed transactions and why 2PC is hard

**In simple words:** A distributed transaction changes data in several databases or services as one unit: all commit or all roll back. *Two-Phase Commit* (2PC) does this in two steps: every participant locks its data and votes "yes", then the coordinator says "commit". Microservices avoid it: locks are held across network calls, one slow participant blocks everyone, and brokers and most cloud services do not support it. The common real bug is the *dual write*: save to the database, then publish an event, and crash in between.

**Real-life example:** Five friends plan a dinner, and nobody may book anything until all five confirm. If one friend's phone dies, everyone waits with their evening on hold.

**Interview question:** Why not use a distributed transaction across microservices?

**Simple answer:** 2PC holds locks during network calls and makes availability depend on every participant. It is not supported by brokers, HTTP APIs or most PaaS, and in Linux containers `TransactionScope` cannot use MSDTC. Instead I use local transactions, sagas with compensations, the outbox pattern and idempotent consumers.

### Eventual consistency

**In simple words:** Eventual consistency means that after a change, services or copies of data may disagree for a short time. If no new changes arrive, they all end up with the same data. It is the price of separate services, async messages, caches and read replicas. You design for it: show "pending" states, use compensating actions, and make updates safe if they arrive late or twice.

**Real-life example:** You send money to a friend at another bank. Your balance drops at once, but your friend's balance updates a little later.

**Interview question:** How do you handle eventual consistency in the user interface?

**Simple answer:** I show honest pending states, like "Confirming your payment", instead of pretending the result is final. The UI polls or gets a SignalR push when the status changes. After a user's own write, I return the saved data or read from the primary database, so they see their own change (*read-your-writes*).

### CAP theorem and PACELC

**In simple words:** CAP says that when the network splits (a *Partition*), a distributed data store must choose *Consistency* (every read sees the latest write) or *Availability* (every node still answers). Partitions will happen, so the real choice is what to do during one. PACELC adds: Else, in normal times, you trade *Latency* against *Consistency*. That is why read replicas and caches are always slightly behind.

**Real-life example:** Two bank branches lose their phone line. They can stop withdrawals to stay accurate (consistency), or keep serving customers and fix the totals later (availability).

**Interview question:** Explain CAP and how it affects your design.

**Simple answer:** During a network partition, a system must pick consistency or availability. I choose per use case: consistency for balances and stock counts, availability for carts and feeds. PACELC adds that even without failures, lower latency means weaker consistency. Cosmos DB shows this well with its five consistency levels.

### Idempotency

**In simple words:** An operation is *idempotent* if doing it many times has the same effect as doing it once. Retries, repeated messages and double-clicks all create duplicates, so this matters a lot. GET, PUT, DELETE and "set status = Paid" are naturally idempotent. POST /payments and "balance += 10" are not. Common fixes are an *idempotency key* from the client, a unique database constraint, an inbox table or a conditional update.

**Real-life example:** Pressing the lift button five times still brings only one lift.

**Interview question:** Is PUT idempotent? Is POST? How do you make a POST safe to retry?

**Simple answer:** PUT replaces the resource, so repeating it gives the same state — it is idempotent. POST creates something new each time, so it is not. To make it safe, the client sends an `Idempotency-Key` header. The server stores the key with the result and returns the saved result when the same key comes again.

### Saga pattern

**In simple words:** A saga is a business transaction made of several local transactions, one per service. Each step triggers the next with an event or command. If a step fails, the saga runs *compensating actions* for the steps already done, like a refund instead of a rollback. In *choreography*, each service reacts to events, with no central controller. In *orchestration*, a central state machine sends commands and tracks progress.

**Real-life example:** Booking a holiday: flight, then hotel, then car. If no car is available, you cancel the hotel and the flight. You do not erase them; you cancel them.

**Interview question:** Saga: choreography or orchestration?

**Simple answer:** Choreography for short, simple flows, because services stay loosely coupled. Orchestration, for example a MassTransit state machine, for long flows with branches, compensations and timeouts, because the whole process is visible in one place. Either way, each step needs idempotent handlers, an outbox and timeouts.

### Outbox pattern (and Inbox)

**In simple words:** The outbox pattern fixes the *dual-write* problem: saving data and publishing an event as two separate steps can lose the event. Instead, you save the business data and the event into an *outbox table* in the same database transaction. A background *relay* reads the outbox, publishes the events and marks them sent. On the receiving side, an *inbox* table stores processed message IDs, so duplicates are ignored.

**Real-life example:** A shop writes each sale and a "send receipt" note in the same ledger at the same time. Later a clerk goes through the notes, posts every receipt and ticks each one off.

**Interview question:** What is the outbox pattern and what problem does it solve?

**Simple answer:** It solves the dual-write problem between the database and the broker. I write the data and the event in one local transaction, and a relay publishes the rows and marks them sent. Publishing is at-least-once, so consumers use an inbox or another idempotency check. MassTransit has a built-in EF Core outbox.

```csharp
db.Orders.Add(order);
db.Enqueue(new OrderPlaced(order.Id, order.CustomerId, order.Total, DateTime.UtcNow));
await db.SaveChangesAsync(ct); // both rows are saved, or neither
```

### Distributed locking

**In simple words:** A distributed lock lets only one instance, across many servers, run some work at a time, like a nightly job. Common tools are Redis (`SET NX` with an expiry), SQL Server `sp_getapplock`, Azure Blob leases and etcd. It is tricky: a lock holder can pause or crash, and the lock can expire while it is still working. So use locks to avoid duplicate work, and protect data with unique constraints, optimistic concurrency or *fencing tokens* (rising numbers that reject an old lock holder).

**Real-life example:** A meeting room booking. If your booking runs out while you are still inside, someone else may walk in, so you also need a lock on the door.

**Interview question:** Two customers buy the last item at the same time. How do you stop overselling?

**Simple answer:** I do not need a distributed lock for that. I use one atomic conditional update in the Inventory database, then check that exactly one row changed. Optimistic concurrency with `rowversion` also works. A lock per SKU is only my last resort.

```sql
UPDATE Stock SET Available = Available - @q
WHERE Sku = @s AND Available >= @q;
-- success only if 1 row was affected
```

### Service mesh

**In simple words:** A service mesh is an infrastructure layer that handles traffic between services. A small proxy (a *sidecar*, usually Envoy) runs next to each service and does the networking work. Without code changes you get mTLS encryption, retries, timeouts, traffic splitting for canary releases and the same metrics for every call. Examples are Istio and Linkerd. It costs extra CPU, memory and complexity, so it suits systems with many services.

**Real-life example:** Each office worker gets a personal assistant who handles all their mail: checks IDs, seals letters and keeps a log. The worker only does the real job.

**Interview question:** What is a service mesh and when would you use one?

**Simple answer:** It puts a proxy next to every service to handle mTLS, retries, timeouts, traffic splitting and telemetry in the same way everywhere. I would use it with dozens of services that need the same security policies. For five services it is too much overhead. Polly in the app is still useful, because the app knows the business meaning of a failure.

### Observability for microservices

**In simple words:** One user request may touch eight services, so you must follow it from start to end. Observability has three pillars: *logs*, *metrics* and *traces*. A trace ID (correlation ID) is created at the gateway and passed through every HTTP call and message. In .NET, OpenTelemetry collects traces and metrics, and the W3C `traceparent` header carries the ID. Put the ID in every structured log line.

**Real-life example:** A parcel tracking number. Every depot scans it, so you can see where the parcel went and where it was delayed.

**Interview question:** How do you trace one request across ten services?

**Simple answer:** I create or accept a trace ID at the gateway and pass the W3C `traceparent` header through HTTP calls and message headers. OpenTelemetry instruments ASP.NET Core, HttpClient, SQL and MassTransit for me. The ID is in every log line, and I view the full trace in Jaeger or Application Insights.

### Testing microservices

**In simple words:** You test microservices at several levels. *Unit tests* check domain logic. *Integration tests* run the API with a real database and broker in containers, using Testcontainers. *Contract tests* (Pact) check that a provider still gives each consumer the data shape it expects. A few *end-to-end tests* cover the key user journeys, and chaos tests check behaviour when things fail.

**Real-life example:** Before two companies connect their systems, they sign an agreement on the data format. Each side tests against the agreement, not against the other company's live system.

**Interview question:** What is consumer-driven contract testing and why does it matter?

**Simple answer:** The consumer writes a test that describes what it needs from the provider, and this creates a contract file. The provider's CI checks that it still meets every consumer's contract. A breaking change then fails the provider's build before deployment, which makes independent deployment safe.

### Deployment on Kubernetes

**In simple words:** On Kubernetes, each microservice usually has one container image, one Deployment, one Service and an HPA for scaling. Each service has its own pipeline: build, test, scan, push and deploy. Use rolling, canary or blue/green releases with automatic rollback. Database changes follow expand/contract. Message consumers can scale on queue length with KEDA, not only on CPU.

**Real-life example:** Each food truck at a festival has its own licence, menu and staff. One truck can change its menu without stopping the others.

**Interview question:** How do you deploy microservices safely on Kubernetes?

**Simple answer:** Each service has its own pipeline and an immutable image tag. I deploy with a rolling update or canary, readiness probes and automatic rollback if errors rise, often with GitOps tools like Argo CD or Flux. Secrets come from Key Vault, and migrations follow expand/contract, so old and new versions both work.

### Full e-commerce microservices architecture

**In simple words:** A typical online shop has a CDN and firewall at the edge, then an API gateway or BFF that checks tokens and routes requests. Behind it are services like Catalog, Cart, Orders, Payments, Inventory and Shipping, each with its own database. They publish events through an outbox to a broker like Service Bus. A saga runs the order flow, and read models power search and reports.

**Real-life example:** A big shopping centre: one main entrance with security, separate shops inside, and an internal radio that tells each shop when something happens.

**Interview question:** Walk me through placing an order in a microservices e-commerce system.

**Simple answer:** The SPA calls the gateway with an idempotency key, and the token is checked. Orders saves a Pending order and an `OrderSubmitted` event in its outbox, then returns 202 Accepted. The saga charges the payment and reserves stock. If stock fails, it refunds the payment and cancels the order. The UI polls or gets a SignalR update.

### Scenarios

**In simple words:** Interviewers like real failure cases. Common ones are: payment succeeded but the Order service is down, events arrive out of order, a contract change breaks consumers, a report needs data from five services, consumer lag keeps growing, and the gateway becomes a bottleneck. The answers reuse the same tools: outbox, durable queues, idempotency, versioning, read models, dead-letter queues and scaling.

**Real-life example:** A fire drill. You practise what to do in each emergency before it really happens.

**Interview question:** Payment succeeded but the Order service is down. What happens?

**Simple answer:** Payments saves the payment and a `PaymentCompleted` event in its outbox in one transaction, so the event is never lost. The broker keeps the message until Orders is back, and Orders handles it idempotently. If the order cannot be confirmed, the saga's timeout triggers a refund. A daily reconciliation job catches anything missed.
