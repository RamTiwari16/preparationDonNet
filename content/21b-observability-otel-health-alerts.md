## OpenTelemetry and Distributed Tracing

### OpenTelemetry in .NET

**Definition.** OpenTelemetry (OTel) is the vendor-neutral CNCF standard for producing and exporting traces, metrics and logs. Instrument once, then export to any backend (Azure Monitor, Jaeger, Tempo, Prometheus, Grafana, Datadog, Elastic) by configuration.

**Why it matters.** .NET's own APIs *are* the OTel APIs: `ActivitySource`/`Activity` for traces, `Meter` for metrics and `ILogger` for logs. ASP.NET Core, `HttpClient`, SqlClient and the Azure SDKs already emit them. The OTel SDK just listens and exports.

| OTel concept | .NET type |
|---|---|
| Tracer | `ActivitySource` |
| Span | `Activity` |
| Span attributes / events / status | `Activity.SetTag`, `AddEvent`, `SetStatus` |
| Meter, Counter, Histogram, Gauge | `Meter`, `Counter<T>`, `Histogram<T>`, `ObservableGauge<T>` / `Gauge<T>` (.NET 9+) |
| Log record | `ILogger` |
| Resource (who emitted it) | `ResourceBuilder.AddService("orders-api")` |

Packages: `OpenTelemetry.Extensions.Hosting`, `OpenTelemetry.Instrumentation.AspNetCore`, `OpenTelemetry.Instrumentation.Http`, `OpenTelemetry.Instrumentation.SqlClient` (or the EF Core instrumentation), `OpenTelemetry.Instrumentation.Runtime`, `OpenTelemetry.Exporter.OpenTelemetryProtocol` (OTLP). Some instrumentation packages are still pre-release; verify versions.

```csharp
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenTelemetry()
    .ConfigureResource(r => r
        .AddService(serviceName: "orders-api", serviceVersion: "1.4.2")
        .AddAttributes([new("deployment.environment", builder.Environment.EnvironmentName)]))
    .WithTracing(t => t
        .AddAspNetCoreInstrumentation(o => o.Filter = ctx =>
            !ctx.Request.Path.StartsWithSegments("/health"))     // do not trace probes
        .AddHttpClientInstrumentation()
        .AddSqlClientInstrumentation()
        .AddSource(CheckoutTelemetry.SourceName)                 // our custom spans
        .SetSampler(new ParentBasedSampler(new TraceIdRatioBasedSampler(0.2))))
    .WithMetrics(m => m
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddRuntimeInstrumentation()                             // GC, thread pool, exceptions
        .AddMeter(CheckoutTelemetry.MeterName))
    .WithLogging()                                               // ILogger -> OTel log records
    .UseOtlpExporter();          // one exporter for all signals; endpoint from OTEL_EXPORTER_OTLP_ENDPOINT

// Azure alternative: .UseAzureMonitor() instead of .UseOtlpExporter()
```

A common production topology sends OTLP to an **OpenTelemetry Collector** (sidecar or gateway) that batches, filters, redacts and fans out to one or more backends, so apps never hold backend credentials. The **.NET Aspire dashboard** is a convenient local OTLP viewer during development.

### Custom instrumentation with ActivitySource and Meter

```csharp
public sealed class CheckoutTelemetry : IDisposable
{
    public const string SourceName = "Orders.Checkout";
    public const string MeterName = "Orders.Checkout";
    public static readonly ActivitySource Source = new(SourceName, "1.0.0");

    private readonly Meter _meter;
    public Counter<long> OrdersPlaced { get; }
    public Counter<long> PaymentsFailed { get; }
    public Histogram<double> CheckoutDuration { get; }

    public CheckoutTelemetry(IMeterFactory meterFactory)        // DI-friendly meter creation
    {
        _meter = meterFactory.Create(MeterName);
        OrdersPlaced = _meter.CreateCounter<long>("orders.placed", unit: "{order}");
        PaymentsFailed = _meter.CreateCounter<long>("payments.failed", unit: "{payment}");
        CheckoutDuration = _meter.CreateHistogram<double>("checkout.duration", unit: "s");
    }
    public void Dispose() => _meter.Dispose();
}
// builder.Services.AddSingleton<CheckoutTelemetry>();

public sealed class CheckoutService(CheckoutTelemetry telemetry, IPaymentClient payments,
    ILogger<CheckoutService> logger)
{
    public async Task PlaceAsync(Order order, CancellationToken ct)
    {
        using var activity = CheckoutTelemetry.Source.StartActivity("Checkout.Place");
        activity?.SetTag("order.id", order.Id);                  // low-cardinality ids OK on spans
        activity?.SetTag("payment.method", order.PaymentMethod);
        var sw = Stopwatch.StartNew();
        try
        {
            using (CheckoutTelemetry.Source.StartActivity("Payment.Charge"))
                await payments.ChargeAsync(order, ct);           // HttpClient span nests below

            telemetry.OrdersPlaced.Add(1, new KeyValuePair<string, object?>("payment.method",
                order.PaymentMethod));
        }
        catch (Exception ex)
        {
            activity?.SetStatus(ActivityStatusCode.Error, ex.Message);
            activity?.AddException(ex);                          // .NET 9+; else AddEvent
            telemetry.PaymentsFailed.Add(1, new KeyValuePair<string, object?>("reason",
                ex.GetType().Name));
            logger.LogError(ex, "Checkout failed for {OrderId}", order.Id);
            throw;
        }
        finally
        {
            telemetry.CheckoutDuration.Record(sw.Elapsed.TotalSeconds);
        }
    }
}
```

`StartActivity` returns `null` when nobody is listening (no SDK, or not sampled), hence the `?.`. Spans are cheap when unsampled.

:::warn Cardinality on metrics
Metric dimensions (tags) multiply time series. `payment.method` (5 values) is fine; `order.id` or `user.id` on a **metric** creates millions of series and explodes cost. Put high-cardinality ids on spans and logs, never on metrics.
:::

### Distributed tracing and W3C trace context

**Definition.** A **trace** is the whole journey of one request across services. It is a tree of **spans**; each span has a `span id`, its parent span id and the shared `trace id`. Context travels between services in the W3C `traceparent` header.

```text
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
             |  |                                |                |
          version  trace-id (16 bytes hex)       parent span id   flags (01 = sampled)
tracestate:  vendor-specific data          baggage: key=value pairs for app context

Trace 4bf92f35...  (POST /checkout, 912 ms)
 +- orders-api: POST /api/checkout              912 ms
    +- orders-api: Checkout.Place               880 ms
       +- SQL: INSERT Orders                     12 ms
       +- HTTP POST inventory-api/reserve        41 ms
       |   +- inventory-api: POST /reserve       38 ms
       |       +- Redis EVALSHA                   2 ms
       +- Payment.Charge                        790 ms   <-- the slow hop
           +- HTTP POST psp.example.com          785 ms
```

- **HTTP:** ASP.NET Core reads incoming `traceparent`; `HttpClient` injects it on outgoing calls automatically. Nothing to code.
- **Messaging:** queues break the HTTP chain. Azure SDK (Service Bus, Event Hubs) propagates `Diagnostic-Id`/`traceparent` in application properties; for other brokers inject and extract manually with `Propagators.DefaultTextMapPropagator`.
- **Correlation ID:** older systems use a custom `X-Correlation-ID` header; a small middleware reads it (or uses `Activity.Current.TraceId`), returns it in the response, and pushes it into the log scope. With W3C tracing the trace id *is* the correlation id; see the correlation-ID middleware in the Microservices section.
- **Return the trace id to clients** in error responses (`ProblemDetails.Extensions["traceId"]`) so support can paste it into a search.

```csharp
// Manual propagation for a custom message bus
var props = new Dictionary<string, string>();
Propagators.DefaultTextMapPropagator.Inject(
    new PropagationContext(Activity.Current?.Context ?? default, Baggage.Current),
    props, (carrier, key, value) => carrier[key] = value);
message.Headers = props;                                       // producer side

var parent = Propagators.DefaultTextMapPropagator.Extract(default, message.Headers,
    (carrier, key) => carrier.TryGetValue(key, out var v) ? [v] : []);
using var span = Source.StartActivity("ProcessOrderMessage", ActivityKind.Consumer,
    parent.ActivityContext);                                   // consumer side continues trace
```

:::q What is the difference between a trace id and a span id?
The trace id identifies the entire request journey and is shared by every span in every service. A span id identifies one operation (an HTTP handler, a SQL call) within that trace; each span records its parent span id, which is how the tree is rebuilt.
:::

## Metrics and Monitoring Signals

### Metric types

| Type | Behaviour | .NET API | Example |
|---|---|---|---|
| **Counter** | Only goes up; you look at its rate | `Counter<T>.Add` | requests served, orders placed, errors |
| **UpDownCounter** | Goes up and down | `UpDownCounter<T>.Add(+1/-1)` | active connections, items in an in-memory queue |
| **Gauge** | Current value sampled at a point in time | `ObservableGauge<T>` (callback), `Gauge<T>.Record` (.NET 9+) | CPU %, queue depth, cache size |
| **Histogram** | Distribution of values in buckets; gives percentiles | `Histogram<T>.Record` | request duration, payload size, checkout amount |

Percentiles (p95/p99) must come from histograms, not from averaging averages.

### RED, USE and the four golden signals

| Method | Signals | Apply to |
|---|---|---|
| **RED** | **R**ate (req/s), **E**rrors (failed req/s), **D**uration (latency distribution) | Request-driven services: APIs, microservices |
| **USE** | **U**tilization (% busy), **S**aturation (queued work), **E**rrors | Resources: CPU, memory, disks, DB, thread pool, connection pools |
| **Four golden signals** (Google SRE) | Latency, Traffic, Errors, Saturation | Any user-facing system; superset of RED plus saturation |

A practical .NET service dashboard: request rate, error rate and p50/p95/p99 by endpoint (RED); CPU, memory, GC pause, thread pool queue length, DB connection pool and DTU (USE); dependency latency/error per downstream; plus **business metrics** (orders per minute, payment success rate) which often detect problems that technical metrics miss.

## Health Checks

### Liveness vs readiness

**Definition.** Health checks are endpoints that orchestrators and load balancers call to decide what to do with an instance.

| Probe | Question | Failure action | Should check |
|---|---|---|---|
| **Liveness** | Is the process alive and not deadlocked? | Restart the container | Only the app itself; **no** external dependencies |
| **Readiness** | Can this instance serve traffic right now? | Remove from the load balancer until it recovers | Critical dependencies (DB, cache), warm-up done |
| **Startup** | Has the app finished starting? | Delay liveness/readiness until done | Migrations, cache warm-up for slow starters |

:::warn Do not put the database in the liveness probe
If SQL has a 30-second blip and liveness checks SQL, Kubernetes restarts *every* pod at once, turning a small dependency issue into a full outage with cold starts. Dependencies belong in readiness.
:::

```csharp
builder.Services.AddHealthChecks()
    .AddCheck("self", () => HealthCheckResult.Healthy(), tags: ["live"])
    .AddSqlServer(builder.Configuration.GetConnectionString("Orders")!,
                  name: "sql", tags: ["ready"])                     // AspNetCore.HealthChecks.SqlServer
    .AddRedis(builder.Configuration.GetConnectionString("Redis")!,
              name: "redis", tags: ["ready"])                       // AspNetCore.HealthChecks.Redis
    .AddCheck<PaymentGatewayHealthCheck>("psp", HealthStatus.Degraded, tags: ["ready"]);

app.MapHealthChecks("/health/live", new HealthCheckOptions
{
    Predicate = c => c.Tags.Contains("live")
});
app.MapHealthChecks("/health/ready", new HealthCheckOptions
{
    Predicate = c => c.Tags.Contains("ready"),
    ResponseWriter = UIResponseWriter.WriteHealthCheckUIResponse    // JSON detail per check
}).RequireHost("*:8081");          // optionally expose detailed health only on an internal port

public sealed class PaymentGatewayHealthCheck(IHttpClientFactory http) : IHealthCheck
{
    public async Task<HealthCheckResult> CheckHealthAsync(HealthCheckContext ctx,
        CancellationToken ct = default)
    {
        try
        {
            using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
            cts.CancelAfter(TimeSpan.FromSeconds(2));               // health checks must be fast
            var res = await http.CreateClient("psp").GetAsync("/status", cts.Token);
            return res.IsSuccessStatusCode
                ? HealthCheckResult.Healthy()
                : HealthCheckResult.Degraded($"PSP returned {(int)res.StatusCode}");
        }
        catch (Exception ex) { return HealthCheckResult.Degraded("PSP unreachable", ex); }
    }
}
```

The `AddSqlServer`/`AddRedis` extensions and `UIResponseWriter` come from the community **AspNetCore.Diagnostics.HealthChecks** (Xabaril) packages, which also provide **HealthChecks UI** (`AddHealthChecksUI().AddInMemoryStorage()` + `MapHealthChecksUI()`), a small dashboard that polls endpoints. A non-critical dependency (the PSP above) reports `Degraded` rather than `Unhealthy` so the instance keeps serving other features.

```yaml
# Kubernetes probes
livenessProbe:
  httpGet: { path: /health/live, port: 8080 }
  periodSeconds: 10
  failureThreshold: 3
readinessProbe:
  httpGet: { path: /health/ready, port: 8080 }
  periodSeconds: 5
  failureThreshold: 2
startupProbe:
  httpGet: { path: /health/live, port: 8080 }
  failureThreshold: 30
  periodSeconds: 2
```

On Azure App Service configure the *Health check* path so unhealthy instances are taken out of rotation; on Azure Container Apps configure probes similarly. Keep health endpoints anonymous but cheap and free of secrets; cache expensive check results for a few seconds.

## Alerting, SLOs and Incident Response

### Alert rules: thresholds vs anomaly detection

**Definition.** An alert is an automated rule that notifies a human (or triggers automation) when a signal crosses a condition. In Azure Monitor: **metric alerts** (near real-time on platform/custom metrics), **log search alerts** (a KQL query on a schedule), **activity log alerts** (resource changes, service health), routed through **action groups** (email, SMS, Teams, PagerDuty/Opsgenie webhooks, Logic Apps, runbooks).

| | Static threshold | Dynamic threshold / anomaly detection |
|---|---|---|
| Rule | `p95 latency > 800 ms for 5 min` | "Significantly above the learned baseline for this hour/day" |
| Pros | Simple, predictable, maps to SLOs | Handles daily/weekly seasonality, no manual tuning |
| Cons | Needs tuning; seasonal traffic causes noise | Less explainable; needs history; can miss slow drifts |
| Use for | SLO burn, error rate, hard limits (disk 90%) | Traffic drops, unusual patterns, business KPIs |

```text
// Log search alert: checkout error rate above 5% in the last 10 minutes
requests
| where timestamp > ago(10m) and name has "checkout"
| summarize total = sum(itemCount), failed = sumif(itemCount, success == false)
| extend errorPct = 100.0 * failed / total
| where total > 50 and errorPct > 5          // minimum volume avoids noise at night
```

### SLI, SLO, SLA and error budgets

| Term | Meaning | Example |
|---|---|---|
| **SLI** (indicator) | A measured ratio of good events | % of checkout requests that succeed in < 1 s |
| **SLO** (objective) | Internal target for the SLI over a window | 99.9% over 30 days |
| **SLA** (agreement) | Contract with customers, with penalties | 99.5% monthly or service credits (looser than the SLO) |
| **Error budget** | Allowed unreliability = 100% - SLO | 0.1% of requests, about **43 minutes** of full downtime per 30 days |

The error budget turns reliability into a decision tool: budget left means you can ship faster; budget burnt means freeze risky releases and fix reliability. **Burn-rate alerts** ("we are consuming the monthly budget 14x faster than sustainable over the last hour") page on real user impact and ignore harmless blips.

### Avoiding alert fatigue and writing runbooks

- **Alert on symptoms users feel** (error rate, latency SLO, checkout success), not on every cause (CPU 80% on one node). Causes go on dashboards.
- **Every page must be actionable and urgent.** If nobody needs to act now, make it a ticket or a daily report.
- **Severity levels:** Sev1 page 24x7 (customer impact), Sev2 page in working hours, Sev3 ticket.
- **Minimum volume and duration** conditions (`total > 50`, "for 5 minutes") stop night-time noise.
- **Deduplicate and group** related alerts; auto-resolve when the condition clears.
- **Review alerts monthly:** delete ones nobody acted on, tune noisy ones.
- **Runbook link in every alert:** what the alert means, dashboards to open, KQL queries to run, common causes, mitigation steps (rollback, scale out, failover, disable feature flag), escalation contacts.

### Performance monitoring and dashboards

Continuous performance monitoring combines: APM (App Insights Performance blade, Profiler), **availability tests** (synthetic probes from several regions every 5 min), **real-user monitoring** (browser SDK, Web Vitals), database monitoring (Query Store, Azure SQL Insights), load tests in CI for key endpoints, and capacity trends (CPU, memory, DTU, queue length) for planning.

Dashboards:
- **Azure:** Azure Dashboards (pinned charts), **Azure Monitor Workbooks** (interactive KQL reports, SLO reports), Application Insights blades.
- **Grafana** (self-hosted or **Azure Managed Grafana**) on Prometheus/Azure Monitor/Loki/Tempo data: rich, multi-source, popular for Kubernetes.
- **Layout that works:** top row = golden signals and SLO status for the service; second row = dependencies (DB, cache, external APIs); third row = resources (CPU, memory, GC, thread pool, pods); fourth row = business KPIs. One dashboard per service plus one "system overview". Show deployment markers on charts so regressions line up with releases.

### Incident response flow

```text
Detect  ->  Triage  ->  Communicate  ->  Mitigate  ->  Resolve  ->  Post-incident review
(alert,     (severity,   (incident      (rollback,     (root-cause   (blameless postmortem,
customer)    owner)       channel,       scale, flag    fix, verify)  action items with owners,
                          status page)   off, failover)               alerts/runbooks updated)
```

1. **Detect:** ideally your alert fires before customers notice.
2. **Triage:** assign an incident commander, set severity by impact (how many users, which features, money at risk).
3. **Communicate:** one incident channel, regular status updates to stakeholders and customers.
4. **Mitigate first:** restore service fast (roll back the deploy, turn off the feature flag, scale out, fail over). Root cause can wait an hour; customers cannot.
5. **Resolve:** find and fix the root cause; verify with metrics.
6. **Learn:** blameless postmortem with timeline, impact, root cause (5 whys), what went well, action items (owner + date), and new or tuned alerts so the same failure is detected faster.

## Scenario: "Checkout failed at 10:42"

:::scenario A customer says checkout failed at 10:42. How do you find out why?
**1. Get identifiers and fix the time.** Ask for user id/email, order id or cart id, and *timezone* (10:42 IST is 05:12 UTC; telemetry is stored in UTC). Ask what they saw (error message, trace id if the error page shows one).

**2. Is it just them or everyone?** Open the Failures blade or run an error-rate query for checkout around that time. A spike means an incident affecting many users; a flat line means something specific to this user (card, data, tenant, feature flag).

```text
requests
| where timestamp between (datetime(2026-10-06 05:07) .. datetime(2026-10-06 05:17))
| where name has "checkout"
| where customDimensions.UserId == "u-42" or user_AuthenticatedId == "u-42"
| project timestamp, operation_Id, name, resultCode, duration, success
```

**3. Follow the trace.** Take the `operation_Id` (trace id) and open *End-to-end transaction details*, or union the tables by `operation_Id`. The waterfall shows which hop failed, for example `POST psp.example.com/charge` returned 504 after 10 s, and the request returned 502.

```text
union requests, dependencies, exceptions, traces
| where operation_Id == "<operation id from step 2>"
| project timestamp, itemType, cloud_RoleName, name, target, resultCode, duration,
          message, outerMessage
| order by timestamp asc
```

**4. Read the logs for that trace id** in Seq/Kibana/App Insights `traces`: `Payment timed out for Order o-7788 after 3 retries`, plus the exception and stack trace.

**5. Check business state.** Was the customer charged? Query the payment table and the PSP dashboard by order id. If the PSP charged but we recorded a timeout, the reconciliation process or a manual status inquiry settles it; refund or confirm the order.

**6. Root cause and scope.** Dependency telemetry shows PSP latency spiked 10:35-10:50 for all users; our timeout plus retries made it worse. Mitigations: circuit breaker, mark payment `Pending` instead of failed, status inquiry job.

**7. Close the loop.** Reply to the customer with the outcome; create action items: alert on PSP dependency failure rate, show a friendly "payment pending" page, add a runbook. Without trace ids in error responses and structured logs with `OrderId`, this investigation would be guesswork, which is the whole point of observability.
:::

## Quick-fire Q&A

:::q Logs vs metrics vs traces in one line each?
Logs answer what happened (discrete events with context). Metrics answer how much and how often (cheap numeric time series for dashboards and alerts). Traces answer where the request travelled and where time was spent across services.
:::

:::q What is structured logging?
Logging events as message templates with named properties (`Order {OrderId} placed`) so each property is stored as a queryable field. It enables filtering, grouping by event type and correlation, unlike flat strings.
:::

:::q Which log level for a declined card payment?
Not `Error`: it is an expected business outcome. Log `Information` or `Warning` with the reason and count it in a metric. Reserve `Error` for failures of our operation, such as the PSP being unreachable after retries.
:::

:::q What does UseSerilogRequestLogging do?
It replaces ASP.NET Core's multiple per-request log lines with a single structured event containing method, path, status code and elapsed time, which you can enrich with user or tenant via the diagnostic context. It cuts noise and makes request logs queryable.
:::

:::q Application Insights classic SDK or OpenTelemetry distro for a new project?
The Azure Monitor OpenTelemetry distro (`UseAzureMonitor()`). It uses standard .NET APIs (`ActivitySource`, `Meter`, `ILogger`), is Microsoft's recommended path for new apps, and avoids vendor lock-in because the same instrumentation can export elsewhere.
:::

:::q How is a trace propagated between services?
Via the W3C `traceparent` header containing the trace id, parent span id and sampling flag. ASP.NET Core and `HttpClient` handle it automatically; for queues the context goes into message properties and the consumer starts a span with the extracted parent.
:::

:::q Counter vs gauge vs histogram?
A counter only increases (requests, errors) and you chart its rate. A gauge is a current value (queue depth, memory). A histogram records a distribution (latency) so you can compute percentiles like p95 and p99.
:::

:::q What are the RED and USE methods?
RED (Rate, Errors, Duration) monitors request-driven services. USE (Utilization, Saturation, Errors) monitors resources such as CPU, memory, connection pools and thread pools. Together with the golden signals they define what goes on a service dashboard.
:::

:::q Liveness vs readiness probe?
Liveness asks "is the process alive" and a failure restarts the container, so it should not check external dependencies. Readiness asks "can I take traffic now" and a failure removes the instance from the load balancer; it checks critical dependencies.
:::

:::q What is an error budget?
The allowed unreliability implied by an SLO: 99.9% over 30 days allows about 43 minutes of downtime. While budget remains, the team ships features; when it is consumed, priority shifts to reliability work. Burn-rate alerts page when the budget is being consumed too fast.
:::

:::q How do you avoid alert fatigue?
Alert on user-facing symptoms tied to SLOs, require minimum volume and duration, route by severity, make every page actionable with a runbook, group duplicates, and regularly delete or tune alerts that nobody acts on.
:::

:::q Why should high-cardinality values not be metric dimensions?
Each unique combination of dimension values creates a new time series. User ids or order ids produce millions of series, exploding storage cost and query time. Put them on spans and logs instead.
:::

:::q What do you include in a postmortem?
Timeline, customer impact, detection (how and how fast), root cause and contributing factors, what went well, and concrete action items with owners and dates. It is blameless: the focus is on system and process fixes, not on individuals.
:::
