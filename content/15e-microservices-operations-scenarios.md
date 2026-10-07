## Operating Microservices

### Service mesh

**Definition.** A dedicated infrastructure layer for service-to-service traffic. A small proxy (*sidecar*, usually Envoy; or a per-node proxy in Istio *ambient* mode) runs next to every service instance and handles networking so the application code does not have to.

**What it gives you without code changes:** automatic **mTLS** and workload identity, retries/timeouts/circuit breaking policies, load balancing, **traffic splitting** (canary 5%/95%), fault injection, uniform metrics and traces for every hop, authorisation policies ("only Orders may call Payments").

```text
 Pod A                         Pod B
 +----------+  +---------+     +---------+  +----------+
 | Orders   |->| sidecar |=mTLS=>| sidecar |->| Payments |
 +----------+  +----+----+     +----+----+  +----------+
                    '--- control plane (Istio / Linkerd): certs, routing policy ---'
```

Options: Istio, Linkerd, Consul Connect, Cilium service mesh. Dapr is related (building blocks: pub/sub, state, service invocation) but is an application runtime, not a pure mesh.

Trade-offs: extra CPU/memory per pod, added latency (small), operational complexity, learning curve. Adopt it when you have dozens of services and need uniform mTLS/policies; do not adopt it for 5 services. Application-level resilience (Polly) is still useful because the app knows the business meaning of failure (fallbacks).

### Observability for microservices

**Why.** One user request touches 8 services. Without correlation you cannot answer "why was this checkout slow?". The three pillars: **logs, metrics, traces** (deep dive in Section 21).

- **Correlation ID / trace ID** — generated at the edge (gateway) and propagated through every HTTP call and message header. Put it in every log line.
- **Distributed tracing** — each hop is a *span*; the full request is a *trace*. .NET uses `System.Diagnostics.Activity` and the W3C `traceparent` header; `HttpClient`, ASP.NET Core, SqlClient, MassTransit and Azure SDKs propagate it automatically when OpenTelemetry instrumentation is on.
- **Metrics (RED/USE)** — Rate, Errors, Duration per endpoint; saturation (queue depth, consumer lag, thread-pool, circuit-breaker state).
- **Structured logs** with Serilog / `ILogger` scopes (`CorrelationId`, `OrderId`, `UserId`), shipped to Seq/ELK/Loki/App Insights.
- **Health checks** — `/health/live` (process is up; no dependency checks) and `/health/ready` (dependencies reachable) for Kubernetes probes.

```csharp
builder.Services.AddOpenTelemetry()
    .ConfigureResource(r => r.AddService("orders-api", serviceVersion: "1.4.2"))
    .WithTracing(t => t
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddSqlClientInstrumentation()
        .AddSource("MassTransit")
        .AddOtlpExporter())                       // to OpenTelemetry Collector / App Insights
    .WithMetrics(m => m
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddMeter("Polly")                        // resilience telemetry (retries, breaker)
        .AddOtlpExporter());

builder.Services.AddHealthChecks()
    .AddSqlServer(connStr, tags: ["ready"])
    .AddCheck("self", () => HealthCheckResult.Healthy(), tags: ["live"]);

app.MapHealthChecks("/health/live",  new() { Predicate = c => c.Tags.Contains("live") });
app.MapHealthChecks("/health/ready", new() { Predicate = c => c.Tags.Contains("ready") });
```

```csharp
// Correlation id: accept from the caller (or create), echo back, put in log scope
app.Use(async (ctx, next) =>
{
    var logger = ctx.RequestServices.GetRequiredService<ILogger<Program>>();
    var id = ctx.Request.Headers["X-Correlation-Id"].FirstOrDefault()
             ?? Activity.Current?.TraceId.ToString()
             ?? Guid.NewGuid().ToString("N");
    ctx.Response.Headers["X-Correlation-Id"] = id;
    using (logger.BeginScope(new Dictionary<string, object> { ["CorrelationId"] = id }))
        await next();
});

// Forward it on outgoing HTTP calls
public sealed class CorrelationIdHandler(IHttpContextAccessor accessor) : DelegatingHandler
{
    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage req, CancellationToken ct)
    {
        var id = accessor.HttpContext?.Response.Headers["X-Correlation-Id"].ToString();
        if (!string.IsNullOrEmpty(id)) req.Headers.TryAddWithoutValidation("X-Correlation-Id", id);
        return base.SendAsync(req, ct);
    }
}
```

For messages, copy the trace context into message headers (MassTransit and the Service Bus SDK do this automatically) so a trace continues across the broker; use the `OrderId` as the saga correlation id so you can search one order across all logs.

### Testing microservices

| Layer | What | Tools |
|---|---|---|
| Unit | domain logic, aggregates, handlers | xUnit, NSubstitute/Moq, FluentAssertions |
| Integration (service-level) | API + real DB + real broker | `WebApplicationFactory`, **Testcontainers** (SQL Server, RabbitMQ, Redis) |
| Component | one service with other services stubbed | WireMock.Net, in-memory broker (MassTransit test harness) |
| **Contract** | consumer and provider agree on the API/message shape | **Pact** (PactNet), Spring-style provider contracts, OpenAPI diffing |
| End-to-end | few critical journeys across the deployed system | Playwright/API tests in a staging env |
| Resilience/chaos | behaviour under faults | Polly chaos strategies, Toxiproxy, Chaos Mesh |

**Consumer-driven contract testing (Pact).** The *consumer* writes a test describing what it needs from the provider; that generates a contract (pact file) published to a Pact Broker. The *provider's* CI verifies it can satisfy every consumer's contract. A provider change that would break a consumer fails the provider's build before deployment — which is what makes independent deployment safe. Use `can-i-deploy` in the pipeline.

```csharp
// Consumer side (Orders calls Inventory) — PactNet 4/5 style
var pact = Pact.V4("OrdersApi", "InventoryApi", new PactConfig { PactDir = "pacts" });
var http = pact.WithHttpInteractions();

http.UponReceiving("a request for the stock of an existing SKU")
    .Given("SKU-1 has 5 units in stock")                       // provider state
    .WithRequest(HttpMethod.Get, "/api/stock/SKU-1")
    .WillRespond()
    .WithStatus(HttpStatusCode.OK)
    .WithJsonBody(new { sku = "SKU-1", available = 5 });

await http.VerifyAsync(async ctx =>
{
    var client = new InventoryClient(new HttpClient { BaseAddress = ctx.MockServerUri });
    var stock = await client.GetStockAsync("SKU-1", CancellationToken.None);
    Assert.Equal(5, stock!.Available);
});
// Output: pacts/OrdersApi-InventoryApi.json -> publish to the Pact Broker
```

For messages, Pact also supports *message pacts* so event shape changes are verified the same way.

### Deployment on Kubernetes

Each service = one container image + one Deployment + one Service (+ HPA, ConfigMap/Secret, Ingress at the edge). More in Sections 13-14.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: orders, namespace: shop }
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate: { maxSurge: 1, maxUnavailable: 0 }     # zero-downtime
  selector: { matchLabels: { app: orders } }
  template:
    metadata: { labels: { app: orders } }
    spec:
      containers:
        - name: orders
          image: shopacr.azurecr.io/orders:1.4.2           # immutable tag
          ports: [ { containerPort: 8080 } ]
          envFrom:
            - configMapRef: { name: orders-config }
            - secretRef:    { name: orders-secrets }
          resources:
            requests: { cpu: 200m, memory: 256Mi }
            limits:   { memory: 512Mi }
          readinessProbe: { httpGet: { path: /health/ready, port: 8080 }, periodSeconds: 5 }
          livenessProbe:  { httpGet: { path: /health/live,  port: 8080 }, periodSeconds: 10 }
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: { name: orders, namespace: shop }
spec:
  scaleTargetRef: { apiVersion: apps/v1, kind: Deployment, name: orders }
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource: { name: cpu, target: { type: Utilization, averageUtilization: 70 } }
```

Deployment practices: one pipeline per service (build, test, scan, push image, deploy), **GitOps** (Argo CD/Flux) with Helm/Kustomize, **canary or blue/green** with automatic rollback on SLO breach, graceful shutdown (`terminationGracePeriodSeconds`, finish in-flight messages, stop accepting new), database migrations with **expand/contract**, secrets from Key Vault. Consumers scale on **queue length / consumer lag** with KEDA, not only CPU.

## Putting It Together

### Full e-commerce microservices architecture

```text
 Web SPA / Mobile
        |  HTTPS
 +------v-----------------+
 | CDN + WAF (Front Door) |  static assets, DDoS, geo filtering
 +------+-----------------+
        |
 +------v-----------------+   token   +-----------------------+
 | API Gateway / BFF      |<--------->| Identity (OIDC/OAuth) |
 | YARP: TLS, JWT, rate   |           | Entra ID / Duende     |
 | limit, route, corr-id  |           +-----------------------+
 +--+------+------+------+-------+------+--+
    |      |      |      |       |      |      sync: REST / gRPC
    |      |      |      |       |      |      (timeouts, retries, breaker)
 +--v---+ +v----+ +v----+ +v-----+ +v-----+ +v-------+
 |Catalog| |Cart | |Orders| |Payment| |Invent.| |Shipping|
 |Cosmos | |Redis| |SQL   | |SQL    | |SQL    | |SQL     |
 +--+----+ +-----+ +--+---+ +--+----+ +--+----+ +---+----+
    |  events        | outbox   | outbox  | outbox   | outbox
 ===v================v==========v=========v==========v=========================
   Event bus: Azure Service Bus topics (or Kafka): OrderSubmitted, PaymentCompleted,
   StockReserved, ShipmentCreated ...   (one DLQ per subscription)
 ===^================^==========^=========^==========^=========================
    |                |          |         |          |
 +--+------+ +-------+--+ +-----+-------+ +----------+---+
 | Search  | | Notific. | | Order Saga  | | Reporting /  |
 | Elastic | | email/SMS| | orchestrator| | read models  |
 +---------+ +----------+ +-------------+ +--------------+

 Cross-cutting
   Observability : OpenTelemetry -> Collector -> Prometheus/Grafana, Jaeger / App Insights
   Platform      : AKS + HPA/KEDA, ACR, Key Vault, App Configuration, GitOps CI/CD
   Resilience    : Polly on every outbound call, DLQ + alerting, idempotent consumers
```

Place-order flow (happy path):
1. SPA -> Gateway (`POST /api/orders`, `Idempotency-Key`) -> JWT validated, rate limited.
2. Orders validates the cart, writes `Order(Pending)` + `OrderSubmitted` to the **outbox** in one transaction, returns `202 Accepted` with the order id.
3. Relay publishes `OrderSubmitted`; the saga orchestrator sends `ChargePayment`.
4. Payments charges the gateway (idempotency key = OrderId) and publishes `PaymentCompleted`.
5. Saga sends `ReserveStock`; Inventory does an atomic conditional decrement and publishes `StockReserved`.
6. Orders marks `Confirmed`; Notification emails the customer; Shipping creates the shipment; Reporting updates read models.
7. Failure at step 5 -> `RefundPayment` compensation -> `Order Cancelled`.
8. The UI polls `GET /api/orders/{id}` or receives SignalR updates.

### Scenarios

:::scenario Payment succeeded but the Order service is down
**Situation.** Payments captured the money and tries to notify Orders, but Orders is down (deploy, crash). The customer is charged and no order exists/confirmed.

**Wrong approach.** Payments calls Orders synchronously; the call fails; the money is gone and nobody knows.

**Right approach.**
1. Payments commits `Payment(Captured)` + `PaymentCompleted` into its **outbox** in one transaction. The money state is durable and the event is guaranteed to exist.
2. The relay publishes to the broker. The broker holds the message while Orders is down (durable queue/subscription).
3. When Orders returns, it consumes `PaymentCompleted` and confirms the order (idempotent via inbox).
4. If Orders never confirms (e.g., order was cancelled), the saga/timeout triggers the compensation: **refund**.
5. Monitor outbox age and consumer lag; reconcile daily payments vs orders (a reconciliation job catches anything missed).

Key line: *"The event is stored with the state change, so a downstream outage delays the outcome but never loses it."*
:::

:::scenario Events arrive out of order
**Situation.** Inventory receives `OrderCancelled` before `OrderPlaced` (different partitions/retries), or two `PriceChanged` events swap places and the older price wins.

**Fix.** (1) Partition/session by the aggregate key (`OrderId`, `ProductId`) so one aggregate's events stay ordered. (2) Include a monotonic `Version`/`SequenceNumber` or `OccurredAt` on events; the consumer applies an event only if it is newer than the stored version and parks or ignores stale ones. (3) For "cancel before create", store a tombstone so the late `OrderPlaced` is recognised as already cancelled. (4) Prefer idempotent state-setting events ("price is now 99") over deltas ("price + 5").
:::

:::scenario A breaking change to an event contract takes consumers down
**Situation.** Orders renames `total` to `grandTotal` in `OrderPlaced` and deploys. Billing and Reporting throw deserialisation errors; messages pile up in DLQs.

**Fix and prevention.** Roll back or hot-fix by publishing both fields. Contract rules: additive changes only; new type/version for breaking changes (`OrderPlacedV2`) published in parallel during migration; tolerant readers; schema registry with compatibility checks and **consumer-driven contract tests** in CI; consumers dead-letter bad messages so the rest flows, then replay after the fix.
:::

:::scenario The report needs data from five services
**Situation.** Finance wants a daily sales report joining orders, customers, products, payments and refunds.

**Answer.** Do not query five service databases. Stream events/CDC into a **data warehouse or lake** (Fabric/Synapse/Snowflake) or build a **CQRS read model** (Reporting service with a denormalised table). For interactive screens with limited data, use **API composition** in a BFF. Accept that the numbers are eventually consistent and add a "data as of" timestamp.
:::

:::scenario Consumer lag and outbox backlog keep growing
**Situation.** Alerts show Kafka consumer lag / Service Bus active messages rising for 30 minutes, outbox age is 10 minutes.

**Diagnose.** Check consumer exceptions (poison message retrying forever?), downstream slowness (DB locks, a dependency with an open breaker), too few consumers/partitions, long processing time causing rebalances, a relay that crashed or is blocked on one failing row. **Fix.** DLQ the poison message, scale consumers (up to partition count; KEDA on lag), batch/parallelise safely, raise partitions for future parallelism, fix the slow dependency, add backpressure/rate limits to the producer. Alert on lag *trend* and on oldest-message age, not only on absolute depth.
:::

:::scenario Order needs the product name and price: call Catalog every time?
**Situation.** The Orders page shows product names/prices. Calling Catalog for each line is slow and breaks when Catalog is down. Prices also change after purchase.

**Answer.** An order is a historical record: **snapshot** the product name, SKU and unit price into the order line at purchase time (event-carried state / data copied at the boundary). For live data that Orders needs (e.g., current stock label), subscribe to Catalog events and keep a local read-only projection. Use sync calls only for decisions that must be current at that instant (price validation at checkout).
:::

:::scenario The API gateway becomes a bottleneck and single point of failure
**Situation.** Every request goes through one gateway instance; it saturates during a sale and one crash takes the site down.

**Fix.** Run multiple stateless gateway instances behind a load balancer/Front Door with health probes and autoscaling; keep it stateless (tokens, not sessions; rate-limit counters in Redis); offload static content and caching to the CDN; avoid heavy aggregation/business logic in it; split by audience (BFF per client) so one noisy client cannot starve others; set timeouts and bulkheads per downstream route.
:::

## Quick-fire Q&A

:::q What is the difference between a modular monolith and microservices?
Both enforce module boundaries, but a modular monolith deploys as one unit with in-process calls and one database (separate schemas), while microservices deploy separately, communicate over the network and own their data. The modular monolith is my default start; microservices only when team size, scaling or release cadence demands it.
:::

:::q What is a bounded context and how does it relate to a microservice?
A bounded context is the boundary within which a domain model and its terms are consistent (Catalog's "Product" is not Shipping's "Product"). A microservice usually implements one bounded context (or a subdomain of it), owning its model and data.
:::

:::q How do you query data that lives in several services?
API composition for small, interactive queries (gateway/BFF calls services in parallel and merges); a CQRS read model built from events for search and lists; a data warehouse fed by CDC/events for analytics. Never join across service databases.
:::

:::q Sync or async communication between services — how do you choose?
Sync (REST/gRPC) when the caller needs the answer now and can tolerate coupling; async events/commands when the work can happen later, when multiple consumers react, or when I want to decouple availability. I limit sync chains to a depth of two and protect them with timeouts, retries and breakers.
:::

:::q What is the difference between a command and an event?
A command asks one service to do something and can be rejected (`ReserveStock`). An event states a fact that already happened and has any number of subscribers (`OrderPlaced`). Commands are named imperatively, events in past tense.
:::

:::q How do you make message processing safe when delivery is at-least-once?
Make handlers idempotent: an inbox/dedup table keyed by `MessageId` in the same transaction as the business change, natural unique keys, conditional updates, and idempotency keys when calling external APIs.
:::

:::q What is the outbox pattern and what problem does it solve?
It solves the dual-write problem. I write the business data and the outgoing event to an outbox table in one local transaction; a relay publishes the rows and marks them sent. No lost events, at-least-once publishing, so consumers must be idempotent.
:::

:::q Saga: choreography or orchestration?
Choreography for short, simple flows because it is loosely coupled; orchestration (a state machine such as MassTransit's) for longer, branching flows with compensation and timeouts because the process is visible in one place. Both need idempotent steps, an outbox and timeouts.
:::

:::q Explain circuit breaker states.
Closed: calls flow and failures are counted. Open: after the failure ratio crosses the threshold, calls fail immediately for the break duration. Half-open: a trial call is allowed; success closes the circuit, failure reopens it. It stops me hammering a dead dependency and frees resources quickly.
:::

:::q Why add jitter to retries?
Without jitter, many clients retry at the same instants and re-overload the recovering service (thundering herd). Randomising delays spreads the load. I use exponential backoff plus jitter, a small attempt cap and retry only idempotent operations.
:::

:::q Explain CAP and what it means for your design.
During a network partition a system must choose consistency or availability. Partitions are unavoidable, so I choose per use case: CP for balances and inventory counts, AP for carts and feeds. PACELC adds that, even without partitions, lower latency means weaker consistency (replicas, caches).
:::

:::q Why avoid distributed transactions (2PC) between microservices?
It blocks resources during the voting phase, ties availability to the slowest participant, adds latency and is unsupported by brokers, HTTP APIs and most PaaS. I use local transactions, sagas with compensations, the outbox and eventual consistency.
:::

:::q How do you secure service-to-service calls?
Validate JWTs in every service (zero trust), use client-credentials or managed identity tokens for service identities, narrow audiences via token exchange/OBO for user-delegated calls, and mTLS (often via a mesh) for transport identity and encryption.
:::

:::q How do you trace one request across ten services?
Generate or accept a correlation/trace id at the gateway, propagate W3C `traceparent` through HTTP and message headers, instrument with OpenTelemetry, include the id in every structured log line, and view traces in Jaeger or Application Insights.
:::

:::q What is a distributed monolith and how do you avoid it?
Services that must be deployed together, share a database or call each other in long synchronous chains. Avoid by drawing boundaries around business capabilities, owning data per service, preferring events, keeping contracts backward-compatible and testing them with consumer-driven contracts.
:::
