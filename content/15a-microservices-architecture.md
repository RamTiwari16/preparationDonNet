## Fundamentals

### Monolith vs Modular Monolith vs Microservices

**Definition.** A *monolith* is one deployable unit containing all features and one database. A *modular monolith* is still one deployable unit, but the code is split into strongly isolated modules (own schema, public API, no cross-module table access). *Microservices* are many small, independently deployable services, each owning its data and one business capability.

**Why it matters.** "Should we use microservices?" is the first architecture question in any senior interview. The honest answer is almost always "it depends on team size, domain clarity and operational maturity" — not "yes".

| | Monolith | Modular monolith | Microservices |
|---|---|---|---|
| Deployment unit | 1 | 1 | N (one per service) |
| Codebase | one big project / tangled | one solution, enforced module boundaries | one repo per service (or mono-repo with separate pipelines) |
| Data | one shared DB, joins everywhere | one DB, one schema per module, no cross-schema joins | one DB per service |
| Call between parts | in-process method call (ns) | in-process via module interface | network call (ms) — can fail |
| Transactions | ACID everywhere | ACID inside a module, careful across | no cross-service ACID — Saga / eventual consistency |
| Scaling | scale the whole app | scale the whole app | scale each service independently |
| Team scaling | hard beyond ~10-15 devs | good for 10-50 devs | designed for many autonomous teams |
| Tech diversity | one stack | one stack | polyglot possible |
| Ops complexity | low | low | high (K8s, tracing, CI/CD per service) |
| Failure mode | one bug takes everything down | same, but easier to reason about | partial failure, cascading failures |
| Best when | MVP, small team, unclear domain | most business apps; **the sane default** | proven scale/team needs, strong DevOps |

```text
Modular monolith (one process)             Microservices (many processes)
+----------------------------------+       +---------+  HTTP/gRPC  +---------+
| Catalog | Orders | Payments |... |       | Catalog |<----------->| Orders  |
|  (own     (own      (own        |       | + DB    |             | + DB    |
|  schema)  schema)   schema)     |       +---------+             +----+----+
|     public interfaces only      |                                    | events
+----------------+-----------------+                               +----v----+
                 |                                                 | Payment |
            One SQL Server                                         | + DB    |
                                                                   +---------+
```

:::warn When NOT to use microservices
- **Small team (under ~8-10 developers)** — you will spend more time on plumbing than features.
- **Domain is not understood yet** — wrong service boundaries are far more expensive to fix than wrong module boundaries.
- **No DevOps maturity** — no CI/CD per service, no centralised logging, no tracing, no container platform.
- **Low or predictable load** — a monolith on 2-3 instances handles most businesses.
- **You need strong consistency across everything** (banking ledger style) — distributed transactions are painful.
- **"Distributed monolith" risk** — services that must be deployed together, share a database or call each other synchronously in long chains give you the cost of both worlds.
:::

:::tip What interviewers look for
Say "I would start with a modular monolith and extract a service only when there is a concrete reason: different scaling profile, different release cadence, a team boundary, or a different technology need." That sentence shows judgement.
:::

### Microservice characteristics

- **Single business capability** — "Orders", "Payments", not "Utilities".
- **Owns its data** — no other service touches its database.
- **Independently deployable** — own pipeline, own version, own release time.
- **Smart endpoints, dumb pipes** — logic lives in services; transport (HTTP, broker) is simple.
- **Loosely coupled, highly cohesive** — change in one rarely forces change in another.
- **Designed for failure** — timeouts, retries, circuit breakers are the default, not an afterthought.
- **Decentralised governance** — teams pick tools within guard-rails (templates, shared libs for logging/auth).
- **Observable** — health endpoints, structured logs, metrics, traces from day one.
- **Automated** — build, test, deploy, scale are all automated.

Size is not "100 lines of code". A good rule: *a service a team of 5-8 can own and rewrite in a few weeks*.

### Service boundaries (DDD)

**Definition.** A *bounded context* is the boundary inside which a domain model and its language are consistent. The same word can mean different things in different contexts. A *service* usually maps to one bounded context (or a subdomain inside one).

```text
"Product" means different things per context
+-----------+   +-------------+  +-----------+  +-----------+
| Catalog   |   | Inventory   |  | Pricing   |  | Shipping  |
| name,desc |   | sku, qty,   |  | price,tax,|  | weight,   |
| images    |   | warehouse   |  | discount  |  | dimensions|
+-----------+   +-------------+  +-----------+  +-----------+
 each has its own Product model keyed by the same ProductId
```

**Aggregate.** A cluster of objects treated as one consistency unit, with one *aggregate root*. Rules: change it in one transaction, other aggregates are referenced **by ID only**, never by object reference. A service typically owns several aggregates; a transaction never spans services.

```csharp
public sealed class Order                       // aggregate root
{
    private readonly List<OrderLine> _lines = new();
    public Guid Id { get; } = Guid.NewGuid();
    public Guid CustomerId { get; }              // reference by ID, not Customer object
    public OrderStatus Status { get; private set; } = OrderStatus.Pending;
    public IReadOnlyList<OrderLine> Lines => _lines;
    public decimal Total => _lines.Sum(l => l.Quantity * l.UnitPrice);

    public Order(Guid customerId) => CustomerId = customerId;

    public void AddLine(Guid productId, int qty, decimal unitPrice)
    {
        if (Status != OrderStatus.Pending) throw new InvalidOperationException("Locked");
        if (qty <= 0) throw new ArgumentOutOfRangeException(nameof(qty));
        _lines.Add(new OrderLine(productId, qty, unitPrice));   // invariant kept here
    }

    public void MarkPaid() => Status = OrderStatus.Paid;
}
public enum OrderStatus { Pending, Paid, Cancelled, Shipped }
public sealed record OrderLine(Guid ProductId, int Quantity, decimal UnitPrice);
```

**How to find boundaries.**
1. Event Storming workshop with domain experts: list domain events (`OrderPlaced`, `PaymentCaptured`), cluster them around aggregates and contexts.
2. Split by **business capability**, not technical layer. Never "DataAccessService" or "ValidationService".
3. Look for different rates of change, scaling needs, data ownership and teams (Conway's law).
4. Prefer boundaries where interaction is mostly one-way and asynchronous. If two services chat on every request, they probably belong together.

#### Splitting a monolith: Strangler Fig

Do not rewrite. Put a facade in front of the monolith and move one capability at a time to a new service; the monolith "shrinks" until it can be retired.

```text
Step 1: facade (YARP) in front            Step 2: route one capability away
 Client -> [Gateway] -> Monolith           Client -> [Gateway] --/api/catalog--> Catalog svc
                                                              \--everything else--> Monolith

Step 3: repeat (Orders, Payments ...)     Step N: monolith is empty -> delete
```

Practical steps:
1. Add the gateway/proxy; all traffic goes through it (no behaviour change).
2. Pick a low-risk, well-bounded capability (Catalog read APIs are a classic first slice).
3. Build the new service with its own DB. Copy data (one-off migration + **CDC** or events to keep in sync). Avoid long-lived dual writes.
4. Use an *anti-corruption layer* so the new service does not inherit the monolith's model.
5. Shift traffic gradually (route by path, header or percentage), then remove the old code.

:::example Strangler fig at an e-commerce company
A 10-year-old ASP.NET MVC monolith is slow during sales. Search/catalog is 80% of traffic. The team extracts **Catalog** first: new service + Elasticsearch, YARP routes `/api/products/*` to it. The monolith keeps checkout. Catalog scales to 20 pods during sales while the monolith stays at 3 instances. Orders are extracted six months later.
:::

### Database per service

**Definition.** Each service has a private database (or schema with its own credentials). Other services access the data only through the owning service's API or events.

**Why it matters.** A shared database is a hidden integration contract: any schema change can break other services, and you can never deploy independently. It also lets each service pick the right store (SQL for Orders, Redis for Cart, Elasticsearch for Search, Cosmos DB for Catalog) — *polyglot persistence*.

```text
Orders svc  -> OrdersDb  (SQL Server)     Catalog svc -> CatalogDb (Cosmos DB)
Cart svc    -> Redis                      Search svc  -> Elasticsearch
Payment svc -> PaymentsDb (SQL Server)    Identity    -> IdentityDb (SQL Server)
```

**The cost: no cross-service joins, no cross-service ACID.** Solutions:

| Need | Solution |
|---|---|
| Show an order with customer name and shipment status | **API composition** — gateway/BFF calls services in parallel and merges |
| Search/filter/sort across data from many services | **CQRS read model** — a denormalised view built from events |
| Company-wide reports, analytics | Stream data (CDC/events) into a **data warehouse / lake** (Synapse, Fabric, Snowflake) |
| Multi-service business transaction | **Saga** (see Distributed Systems) |
| Referential integrity | Reference by ID; accept eventual consistency; tolerate "orphans" |

```csharp
// API composition in a BFF: call in parallel, tolerate partial failure
app.MapGet("/bff/orders/{id:guid}", async (Guid id, IOrderClient orders,
    ICustomerClient customers, IShipmentClient shipments, CancellationToken ct) =>
{
    var order = await orders.GetAsync(id, ct);
    if (order is null) return Results.NotFound();

    var customerTask = TryAsync(() => customers.GetAsync(order.CustomerId, ct));
    var shipmentTask = TryAsync(() => shipments.GetByOrderAsync(id, ct));
    await Task.WhenAll(customerTask, shipmentTask);

    return Results.Ok(new OrderDetailsDto(order, customerTask.Result, shipmentTask.Result,
        Partial: customerTask.Result is null || shipmentTask.Result is null));
});

static async Task<T?> TryAsync<T>(Func<Task<T?>> call) where T : class
{
    try { return await call(); }
    catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
    { return null; }   // degrade gracefully: show the order without shipment info
}
```

**CQRS read model.** Orders, Customers and Shipping publish events. A *Reporting/Query* service subscribes, and keeps a denormalised `OrderSummary` table/index (order id, customer name, city, total, shipment status). Queries then hit one table — no joins, no fan-out calls. Trade-off: the view is eventually consistent and you must handle replays/rebuilds.

:::warn Shared database is an anti-pattern
"Our microservices share one SQL Server so we can still join" = a distributed monolith. A column rename now needs coordinated deployment of five services. Fix: one schema per service with separate DB users, then replace joins with API composition or read models.
:::

### Independent deployment

**Definition.** You can build, test, release and roll back one service without touching or coordinating with any other service.

What makes it possible:
- **Backward-compatible contracts** — add fields, never remove/rename; version APIs (`/v1`, `/v2`) and events; consumers ignore unknown fields (tolerant reader).
- **Expand/contract DB migrations** — add the new column (expand), deploy code that writes both, backfill, switch reads, then drop the old column (contract). Never a breaking change in one deploy.
- **Own pipeline per service** — path-filtered triggers in a mono-repo, or repo-per-service. Own container image and Helm chart.
- **Feature flags** — decouple deploy from release.
- **Progressive delivery** — rolling, blue/green, canary with automatic rollback on error-rate increase.
- **Consumer-driven contract tests** (Pact) so a provider knows it will not break callers.

:::q If three services always have to be released together, what is that called and what do you do?
A distributed monolith. It means boundaries or contracts are wrong: usually a shared DB, a chatty synchronous chain, or breaking contract changes. Fix by making contracts backward-compatible, moving to events for one-way flows, removing shared data, or merging the services back into one.
:::

## Architecture

### API Gateway

**Definition.** A single entry point in front of the services. Clients talk to the gateway; the gateway routes to the right service and handles cross-cutting concerns.

**Why it matters.** Without it, every client must know every service's address, and each service re-implements TLS, auth, rate limiting and CORS.

| Gateway responsibility | Notes |
|---|---|
| Routing / reverse proxy | path, host, header based; load balancing |
| TLS termination | internal traffic may stay HTTP or use mTLS |
| Authentication offloading | validate JWT once at the edge; forward identity claims |
| Rate limiting / quotas / throttling | per client, per IP, per API key |
| Request aggregation | one client call fans out to many services (careful: this is API composition) |
| Caching | cache GET responses at the edge |
| Request/response transformation | path rewrite, header add/remove, protocol translation (REST to gRPC) |
| Observability | generate correlation ID, access logs, metrics |
| Security | WAF, IP allow-lists, request size limits, CORS |
| Resilience | timeouts, retries, circuit breaking to downstreams |
| Versioning / canary | route 5% of traffic to v2 |

:::warn Keep business logic out of the gateway
A gateway with business rules becomes a bottleneck and a single deployment everyone waits on. Routing, security and aggregation only.
:::

#### YARP (Yet Another Reverse Proxy)

Microsoft's reverse-proxy library for ASP.NET Core. Best choice for .NET shops: config-driven, in-process with your auth/rate-limit middleware, actively maintained.

```csharp
// Program.cs of the Gateway project
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddAuthentication("Bearer").AddJwtBearer("Bearer", o =>
{
    o.Authority = "https://login.shop.com";
    o.Audience  = "shop-api";
});
builder.Services.AddAuthorization(o =>
    o.AddPolicy("authenticated", p => p.RequireAuthenticatedUser()));

builder.Services.AddRateLimiter(o =>
{
    o.RejectionStatusCode = StatusCodes.Status429TooManyRequests;
    o.AddFixedWindowLimiter("perClient", l => { l.PermitLimit = 100; l.Window = TimeSpan.FromMinutes(1); });
});

builder.Services.AddReverseProxy()
    .LoadFromConfig(builder.Configuration.GetSection("ReverseProxy"));

var app = builder.Build();
app.UseRateLimiter();
app.UseAuthentication();
app.UseAuthorization();
app.MapReverseProxy();
app.Run();
```

```json
{
  "ReverseProxy": {
    "Routes": {
      "orders": {
        "ClusterId": "orders",
        "AuthorizationPolicy": "authenticated",
        "RateLimiterPolicy": "perClient",
        "Match": { "Path": "/api/orders/{**catch-all}" },
        "Transforms": [ { "PathRemovePrefix": "/api" } ]
      },
      "catalog": {
        "ClusterId": "catalog",
        "AuthorizationPolicy": "anonymous",
        "Match": { "Path": "/api/products/{**catch-all}" }
      }
    },
    "Clusters": {
      "orders": {
        "LoadBalancingPolicy": "LeastRequests",
        "HealthCheck": {
          "Active": { "Enabled": true, "Interval": "00:00:10",
                      "Timeout": "00:00:03", "Path": "/health/ready" }
        },
        "Destinations": {
          "d1": { "Address": "http://orders-1:8080/" },
          "d2": { "Address": "http://orders-2:8080/" }
        }
      },
      "catalog": {
        "Destinations": { "d1": { "Address": "http://catalog:8080/" } }
      }
    }
  }
}
```

#### Ocelot

Older community gateway, pure JSON configuration, built-in aggregation, QoS (Polly), rate limiting. Fine for simple setups; YARP is generally preferred for new work because of Microsoft backing and performance.

```json
{
  "Routes": [
    {
      "UpstreamPathTemplate": "/orders/{everything}",
      "UpstreamHttpMethod": [ "GET", "POST", "PUT", "DELETE" ],
      "DownstreamPathTemplate": "/api/orders/{everything}",
      "DownstreamScheme": "http",
      "DownstreamHostAndPorts": [
        { "Host": "orders-1", "Port": 8080 },
        { "Host": "orders-2", "Port": 8080 }
      ],
      "LoadBalancerOptions": { "Type": "LeastConnection" },
      "AuthenticationOptions": { "AuthenticationProviderKey": "Bearer" },
      "QoSOptions": { "ExceptionsAllowedBeforeBreaking": 3,
                      "DurationOfBreak": 10000, "TimeoutValue": 3000 },
      "RateLimitOptions": { "EnableRateLimiting": true, "Period": "1m",
                            "PeriodTimespan": 30, "Limit": 100 }
    }
  ],
  "GlobalConfiguration": { "BaseUrl": "https://api.shop.com" }
}
```

```csharp
builder.Configuration.AddJsonFile("ocelot.json", optional: false, reloadOnChange: true);
builder.Services.AddOcelot();
// ...
await app.UseOcelot();
```

#### Azure API Management (APIM)

Managed gateway (PaaS): developer portal, subscription keys, policies, versioning, analytics, hybrid/self-hosted gateway. Choose it when you need API productisation, partner onboarding or governance. Behaviour is configured with XML *policies*:

```xml
<policies>
  <inbound>
    <base />
    <validate-jwt header-name="Authorization" failed-validation-httpcode="401">
      <openid-config url="https://login.shop.com/.well-known/openid-configuration" />
      <required-claims>
        <claim name="aud"><value>shop-api</value></claim>
      </required-claims>
    </validate-jwt>
    <rate-limit-by-key calls="100" renewal-period="60"
        counter-key="@(context.Request.IpAddress)" />
    <cache-lookup vary-by-developer="false" vary-by-developer-groups="false" />
    <set-header name="X-Correlation-Id" exists-action="skip">
      <value>@(context.RequestId.ToString())</value>
    </set-header>
  </inbound>
  <outbound><cache-store duration="30" /><base /></outbound>
</policies>
```

| | YARP | Ocelot | Azure APIM |
|---|---|---|---|
| Type | .NET library you host | .NET library you host | Managed Azure service |
| Config | JSON / code, dynamic reload | JSON | Portal / policies / IaC |
| Strengths | fast, extensible, Microsoft-backed | simple, aggregation built in | portal, products, subscriptions, analytics |
| Cost | your compute | your compute | per-tier pricing |
| Use when | .NET microservices, custom logic | small/simple systems | external/partner APIs, governance |

Other options: Azure Front Door/Application Gateway (L7 edge + WAF), Kong, NGINX, Envoy, AWS API Gateway.

#### Backend-for-Frontend (BFF)

**Definition.** A dedicated gateway per client type (web, mobile, partner). Each BFF shapes data to what *that* client needs.

```text
 Web SPA   -> Web BFF    -+
 Mobile app-> Mobile BFF -+--> Catalog | Orders | Payments | Identity
 Partner   -> Public API -+
```

Why: a mobile screen wants one small payload, a web admin page wants a big one; one general gateway ends up with `if (client == mobile)` everywhere. Each BFF is owned by the frontend team. Bonus: the web BFF can hold the OAuth tokens server-side and issue an HttpOnly cookie to the browser (safer than tokens in JavaScript).

:::q Gateway vs Load balancer vs Reverse proxy — what is the difference?
A reverse proxy forwards client requests to backend servers. A load balancer is a reverse proxy focused on spreading traffic across identical instances. An API gateway is a reverse proxy that also understands APIs: auth, rate limiting, aggregation, transformation, versioning. YARP is all three at once.
:::

### Service discovery

**Definition.** The mechanism by which a service finds the network location (host:port) of another service, when instances start, stop and move constantly.

**Why it matters.** In containers, IPs are ephemeral. Hard-coded addresses break on every redeploy or scale-out.

| Approach | How it works | Example |
|---|---|---|
| **DNS / platform (server-side)** | The platform keeps a stable name and load-balances behind it | Kubernetes `Service` + CoreDNS: `http://orders.shop.svc.cluster.local`; ACA/App Service names |
| **Registry (client-side)** | Instances register + heartbeat in a registry; callers query it and pick an instance | Consul, Eureka, etcd |
| **Config-based** | Static list or env vars | `appsettings.json` / `Orders__BaseUrl` |
| **Mesh-based** | Sidecar proxies resolve and route | Istio, Linkerd |

On Kubernetes you almost never need Consul: a `Service` gives you a stable virtual IP and DNS name, and `readinessProbe` removes unhealthy pods from the endpoints.

```yaml
apiVersion: v1
kind: Service
metadata: { name: orders, namespace: shop }
spec:
  selector: { app: orders }
  ports: [ { port: 80, targetPort: 8080 } ]
# callers use http://orders (same namespace) or http://orders.shop
```

.NET has `Microsoft.Extensions.ServiceDiscovery` (used by .NET Aspire) so code uses logical names and the resolver picks the real address from config, DNS or Consul:

```csharp
builder.Services.AddServiceDiscovery();
builder.Services.ConfigureHttpClientDefaults(http => http.AddServiceDiscovery());

builder.Services.AddHttpClient<IInventoryClient, InventoryClient>(c =>
    c.BaseAddress = new Uri("https+http://inventory"));   // logical name, https preferred
```

Consul registration (client-side discovery) conceptually:

```json
{ "service": { "name": "orders", "port": 8080, "tags": ["v1"],
    "check": { "http": "http://orders-1:8080/health/live", "interval": "10s" } } }
```

Client-side discovery = caller picks an instance (needs a client library, smarter balancing). Server-side = a router/load balancer picks (simpler clients). K8s and cloud PaaS use server-side.

### Authentication across services

Four building blocks, usually combined:

| Technique | What it solves | Notes |
|---|---|---|
| **Gateway offloading** | Authenticate the *user* once at the edge | Gateway validates JWT, rate-limits, then forwards the token or a signed internal identity |
| **Token propagation** | Downstream service needs *who the user is* | Forward the user's `Authorization: Bearer` header; each service validates it again (audience/scope) |
| **Token exchange (On-Behalf-Of)** | Narrow the audience per hop | Service swaps the user's token for a new one scoped to the next service (OAuth 2.0 token exchange / Entra ID OBO) |
| **Client credentials** | Service-to-service with **no user** (batch jobs, events) | Each service has its own client id/secret or managed identity and gets a token for the target API's scope |
| **mTLS** | Strong *transport-level* identity between services | Both sides present certificates; usually delivered by a service mesh |

Rule: **never trust the network**. Even behind the gateway, each service validates the token (signature, issuer, audience, expiry) and authorises by scope/role. Zero trust.

```csharp
// 1) Token propagation: forward the caller's bearer token
public sealed class BearerTokenPropagationHandler(IHttpContextAccessor accessor)
    : DelegatingHandler
{
    protected override Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request, CancellationToken ct)
    {
        var auth = accessor.HttpContext?.Request.Headers.Authorization.ToString();
        if (!string.IsNullOrEmpty(auth))
            request.Headers.TryAddWithoutValidation("Authorization", auth);
        return base.SendAsync(request, ct);
    }
}

// 2) Client credentials: the service authenticates as itself (Azure.Identity caches tokens)
public sealed class ServiceTokenHandler(TokenCredential credential, string scope)
    : DelegatingHandler
{
    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request, CancellationToken ct)
    {
        AccessToken token = await credential.GetTokenAsync(new TokenRequestContext([scope]), ct);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token.Token);
        return await base.SendAsync(request, ct);
    }
}

// registration
builder.Services.AddHttpContextAccessor();
builder.Services.AddSingleton<TokenCredential>(new DefaultAzureCredential());
builder.Services.AddHttpClient<IPaymentClient, PaymentClient>(c =>
        c.BaseAddress = new Uri("http://payments/"))
    .AddHttpMessageHandler(sp => new ServiceTokenHandler(
        sp.GetRequiredService<TokenCredential>(), "api://payments/.default"));
```

Each receiving service protects its endpoints by scope or app role:

```csharp
builder.Services.AddAuthorization(o =>
{
    // user token carries a scope (scp); service token carries an app role (roles)
    o.AddPolicy("payments.write", p => p.RequireAssertion(ctx =>
        ctx.User.HasClaim("scp", "payments.write") ||
        ctx.User.HasClaim("roles", "Payments.Write")));
});
app.MapPost("/payments", Charge).RequireAuthorization("payments.write");
```

**mTLS in Kestrel** (normally the mesh does this for you):

```csharp
builder.WebHost.ConfigureKestrel(k => k.ConfigureHttpsDefaults(h =>
    h.ClientCertificateMode = ClientCertificateMode.RequireCertificate));
builder.Services.AddAuthentication(CertificateAuthenticationDefaults.AuthenticationScheme)
    .AddCertificate();   // validate chain + thumbprint/subject in OnCertificateValidated
```

:::warn Do not forward a user token blindly everywhere
A token with a broad audience, replayed to ten services, lets any compromised service impersonate the user to all the others. Prefer narrow-audience tokens (OBO / token exchange) and short lifetimes. For event-driven flows there is no user token at all — carry the user id in the message and use the *service's own* identity.
:::

:::q Where should authentication happen — gateway or each service?
Both. The gateway authenticates users at the edge (reject early, rate-limit, offload TLS). Each service still validates the token and enforces authorisation (defence in depth), because services can be reached from inside the cluster, from other services or from jobs. Service-to-service calls use client credentials or mTLS.
:::

### Synchronous communication: REST vs gRPC

**Definition.** The caller sends a request and waits for the response (request/response). REST over HTTP/JSON is the default; gRPC (HTTP/2 + Protocol Buffers) is the high-performance alternative for internal calls.

| | REST (JSON/HTTP) | gRPC |
|---|---|---|
| Contract | OpenAPI (optional) | `.proto` file (mandatory, strongly typed, code generated) |
| Payload | JSON text | Protobuf binary (small, fast) |
| Transport | HTTP/1.1 or 2 | HTTP/2 only |
| Streaming | limited (SSE, WebSocket) | built-in server, client, bidirectional |
| Browser | native | needs gRPC-Web |
| Debuggability | easy (curl, Postman) | needs tooling (grpcurl) |
| Evolution | add JSON fields | add fields with new numbers, never reuse numbers |
| Best for | public APIs, simple CRUD, browsers | internal service-to-service, low latency, streaming |

`inventory.proto`:

```protobuf
syntax = "proto3";
option csharp_namespace = "Shop.Inventory.Grpc";
package inventory;

service InventoryService {
  rpc GetStock (StockRequest) returns (StockReply);
  rpc Reserve  (ReserveRequest) returns (ReserveReply);
  rpc WatchStock (StockRequest) returns (stream StockReply);   // server streaming
}
message StockRequest { string sku = 1; }
message StockReply   { string sku = 1; int32 available = 2; }
message ReserveRequest { string order_id = 1; string sku = 2; int32 quantity = 3; }
message ReserveReply   { bool reserved = 1; string reason = 2; }
```

```xml
<!-- .csproj (server): Grpc.AspNetCore; (client): Grpc.Net.ClientFactory, Google.Protobuf, Grpc.Tools -->
<ItemGroup>
  <Protobuf Include="Protos\inventory.proto" GrpcServices="Server" />
</ItemGroup>
```

Server:

```csharp
public sealed class InventoryGrpcService(IStockRepository repo, ILogger<InventoryGrpcService> log)
    : InventoryService.InventoryServiceBase
{
    public override async Task<StockReply> GetStock(StockRequest request, ServerCallContext ctx)
    {
        var qty = await repo.GetAvailableAsync(request.Sku, ctx.CancellationToken);
        return new StockReply { Sku = request.Sku, Available = qty };
    }

    public override async Task<ReserveReply> Reserve(ReserveRequest r, ServerCallContext ctx)
    {
        var ok = await repo.TryReserveAsync(r.OrderId, r.Sku, r.Quantity, ctx.CancellationToken);
        return new ReserveReply { Reserved = ok, Reason = ok ? "" : "OUT_OF_STOCK" };
    }
}

// Program.cs
builder.Services.AddGrpc();
app.MapGrpcService<InventoryGrpcService>();
```

Client (generated client registered with `HttpClientFactory`):

```csharp
builder.Services.AddGrpcClient<InventoryService.InventoryServiceClient>(o =>
        o.Address = new Uri("https://inventory:5001"))
    .AddStandardResilienceHandler();          // retries/circuit breaker on the HTTP handler

// usage
public sealed class CheckoutService(InventoryService.InventoryServiceClient inventory)
{
    public async Task<bool> ReserveAsync(Guid orderId, string sku, int qty, CancellationToken ct)
    {
        try
        {
            var reply = await inventory.ReserveAsync(
                new ReserveRequest { OrderId = orderId.ToString(), Sku = sku, Quantity = qty },
                deadline: DateTime.UtcNow.AddSeconds(2),   // always set a deadline
                cancellationToken: ct);
            return reply.Reserved;
        }
        catch (RpcException ex) when (ex.StatusCode == StatusCode.DeadlineExceeded)
        { return false; }
    }
}
```

#### HttpClientFactory typed clients

**Why.** `new HttpClient()` per request exhausts sockets (`TIME_WAIT`); a single static `HttpClient` never refreshes DNS. `IHttpClientFactory` pools and rotates `HttpMessageHandler`s (default lifetime 2 minutes) and gives you a place to attach handlers (auth, logging, resilience).

```csharp
public sealed record StockLevel(string Sku, int Available);

public interface IInventoryClient
{
    Task<StockLevel?> GetStockAsync(string sku, CancellationToken ct);
}

public sealed class InventoryClient(HttpClient http) : IInventoryClient   // typed client
{
    public async Task<StockLevel?> GetStockAsync(string sku, CancellationToken ct)
    {
        using var resp = await http.GetAsync($"api/stock/{Uri.EscapeDataString(sku)}", ct);
        if (resp.StatusCode == HttpStatusCode.NotFound) return null;
        resp.EnsureSuccessStatusCode();
        return await resp.Content.ReadFromJsonAsync<StockLevel>(cancellationToken: ct);
    }
}

builder.Services.AddHttpClient<IInventoryClient, InventoryClient>(c =>
{
    c.BaseAddress = new Uri("http://inventory/");
    c.Timeout = Timeout.InfiniteTimeSpan;   // let the resilience pipeline own timeouts
})
.AddHttpMessageHandler<BearerTokenPropagationHandler>()
.AddStandardResilienceHandler();
```

Named clients (`AddHttpClient("inventory")` + `factory.CreateClient("inventory")`) are fine for ad-hoc use; **typed clients** give a strongly typed façade that is easy to mock in tests.

:::q When do you choose gRPC over REST?
For internal, high-volume, latency-sensitive service-to-service calls, or when you need streaming and a strict contract with generated clients. I keep REST for public/browser-facing APIs and for simple CRUD where debuggability and tooling matter more than raw speed.
:::

:::warn Sync chains create temporal coupling
A → B → C → D synchronously means the availability of A is the *product* of all four (99.9% each gives about 99.6%), and latency adds up. Prefer events for anything that does not need an immediate answer, and keep synchronous chains to depth 2.
:::
