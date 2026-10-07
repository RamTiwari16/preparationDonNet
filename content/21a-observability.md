## Observability Fundamentals

**Definition.** *Monitoring* tells you **whether** the system is healthy (known questions, dashboards, alerts). *Observability* is the ability to answer **new** questions about the system from its outputs without shipping new code. The outputs are the three pillars: **logs, metrics and traces**.

**Why it matters.** In production you cannot attach a debugger. When a customer says "checkout failed", the only things you have are the signals you decided to emit *before* the failure. Interviewers ask about observability to see whether you have actually run software in production.

### Logs vs metrics vs traces

| | Logs | Metrics | Traces |
|---|---|---|---|
| Question answered | **What happened?** | **How much / how often?** | **Where did the request travel?** |
| Shape | Timestamped event with message and properties | Numeric time series (value + dimensions) | Tree of spans (operations) sharing one trace id |
| Example | `Payment declined for Order 7788: insufficient funds` | `http.server.request.duration` p95 = 420 ms; 12 errors/min | `POST /checkout` 900 ms -> Inventory 40 ms -> Payment 780 ms -> SQL 30 ms |
| Cost | High volume, expensive to store and query | Cheap: pre-aggregated, fixed cardinality | Medium: usually sampled |
| Best for | Debugging details, audit, errors with context | Dashboards, alerting, trends, capacity | Latency breakdown across services, finding the failing hop |
| .NET API | `ILogger<T>` | `System.Diagnostics.Metrics.Meter` | `System.Diagnostics.ActivitySource` / `Activity` |
| Typical tools | Seq, Elastic/Kibana, Loki, App Insights `traces` | Prometheus, Azure Monitor metrics, App Insights `customMetrics` | Jaeger, Zipkin, Tempo, App Insights `requests`+`dependencies` |

How they work together: an **alert** fires on a metric (error rate up) -> a **trace** of a failing request shows the payment call timed out -> the **logs** correlated by the same trace id show the exact exception and order id.

:::tip Say this in the interview
"Logs tell me what happened, metrics tell me how much and how often, and traces tell me where the request went. I alert on metrics, investigate with traces, and get the details from logs, all correlated by the trace id."
:::

## Logging in .NET

### ILogger in ASP.NET Core

**Definition.** `Microsoft.Extensions.Logging` is the built-in logging abstraction. Code depends on `ILogger<T>`; *providers* (Console, Debug, EventSource, Application Insights, Serilog, OpenTelemetry) decide where logs go. The **category** is the type name `T`, which lets you filter per namespace.

```csharp
public sealed class OrdersController(IOrderService orders, ILogger<OrdersController> logger)
    : ControllerBase
{
    [HttpPost]
    public async Task<IActionResult> Place(PlaceOrderRequest req, CancellationToken ct)
    {
        logger.LogInformation("Placing order for {CustomerId} with {ItemCount} items",
            req.CustomerId, req.Items.Count);
        try
        {
            var order = await orders.PlaceAsync(req, ct);
            return CreatedAtAction(nameof(Get), new { id = order.Id }, order);
        }
        catch (PaymentDeclinedException ex)
        {
            logger.LogWarning(ex, "Payment declined for {OrderId}: {Reason}", ex.OrderId, ex.Reason);
            return UnprocessableEntity();
        }
    }
}
```

```json
// appsettings.json: level per category; more specific prefix wins
{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.AspNetCore": "Warning",
      "Microsoft.EntityFrameworkCore.Database.Command": "Warning",
      "Orders": "Debug"
    },
    "Console": { "FormatterName": "json" }
  }
}
```

Built-in extras worth knowing: `builder.Services.AddHttpLogging(...)` + `app.UseHttpLogging()` logs request/response metadata (careful with bodies and headers: PII and secrets), and `AddW3CLogging` writes W3C-format access logs.

### Structured logging: message templates vs string interpolation

**Definition.** Structured logging records events as **named properties** plus a message template, not just a flat string. `"Order {OrderId} placed"` keeps `OrderId = 7788` as a queryable field.

```csharp
// BAD: interpolation. The template is different every time, OrderId is lost as a field,
// and the string is built even when the level is disabled.
logger.LogInformation($"Order {order.Id} placed by {customer.Id}");

// GOOD: message template. Properties OrderId and CustomerId are stored separately.
logger.LogInformation("Order {OrderId} placed by {CustomerId}", order.Id, customer.Id);
// Query later: OrderId = 7788, or "count of 'Order {OrderId} placed' per hour"
```

| | String interpolation `$"..."` | Message template |
|---|---|---|
| Queryable fields | No (one string) | Yes (`OrderId`, `CustomerId`) |
| Group by event type | No (every message unique) | Yes (same template = same event) |
| Cost when level disabled | String still formatted | Skipped (args may still be boxed) |
| Analyzer | CA2254 warns about it | Recommended |

Rules: PascalCase placeholder names, consistent names across services (`OrderId` everywhere, not `orderId`/`order_id`/`Id`), pass the exception as the **first argument** (`LogError(ex, "...")`) so the stack trace is captured as a field, and do not log the same exception at every layer (log once where you handle it).

### Log levels: what to use when

| Level | Use for | Production default? |
|---|---|---|
| `Trace` | Very detailed internals, may include sensitive data | Off |
| `Debug` | Developer diagnostics (values, branches taken) | Off (enable per category temporarily) |
| `Information` | Normal business flow milestones: order placed, job finished | On, but not per-item in tight loops |
| `Warning` | Unexpected but handled: retry happened, fallback used, validation failure from a partner | On |
| `Error` | The current operation failed: unhandled exception, payment call failed after retries | On, usually alerted on rate |
| `Critical` | The whole app or a key capability is down: cannot connect to DB at startup, data corruption | On, page someone |

:::warn Common logging mistakes
Logging at `Information` inside a loop over 100K items (cost and noise); logging full request bodies (PII, card data, tokens); `catch (Exception ex) { _logger.LogError(ex.Message); }` without the exception object (stack trace lost); logging and rethrowing at every layer (duplicate errors); using `Error` for expected business outcomes such as "card declined" (should be `Warning` or `Information` with a metric).
:::

### Scopes and enrichment

**Scopes** attach properties to *every* log written inside a block, without passing them to each call. **Enrichment** adds environment-wide properties (machine, environment, app version, trace id, tenant).

```csharp
using (logger.BeginScope(new Dictionary<string, object>
{
    ["OrderId"] = order.Id,
    ["TenantId"] = tenant.Id
}))
{
    logger.LogInformation("Reserving inventory");      // has OrderId and TenantId
    await inventory.ReserveAsync(order, ct);
    logger.LogInformation("Charging payment");         // has OrderId and TenantId
}
```

Console/JSON providers include scopes when `IncludeScopes` is true; Serilog uses `LogContext` (`Enrich.FromLogContext()`); OpenTelemetry logging can include scopes as attributes (`IncludeScopes = true`). ASP.NET Core automatically adds scope data such as `RequestId`, `RequestPath`, `TraceId` and `SpanId`, which is how logs are correlated with traces.

### High-performance logging: the LoggerMessage source generator

For hot paths, `[LoggerMessage]` generates strongly typed methods at compile time: the template is parsed once, there is no boxing of value-type arguments, and the level check happens before any work.

```csharp
public static partial class CheckoutLog
{
    [LoggerMessage(EventId = 1001, Level = LogLevel.Information,
        Message = "Order {OrderId} placed with total {Total} {Currency}")]
    public static partial void OrderPlaced(ILogger logger, Guid orderId, decimal total, string currency);

    [LoggerMessage(EventId = 1002, Level = LogLevel.Warning,
        Message = "Payment declined for order {OrderId}: {Reason}")]
    public static partial void PaymentDeclined(ILogger logger, Guid orderId, string reason);
}

// Usage
CheckoutLog.OrderPlaced(logger, order.Id, order.Total, "INR");
```

Stable **EventIds** make it easy to alert or query on a specific event regardless of message wording changes.

### PII and secret redaction

Logs are copied to many systems and kept for months; treat them as a data-leak surface (GDPR, PCI, HIPAA).

- **Never log:** passwords, tokens/API keys, full card numbers or CVV, national IDs, full request bodies of auth/payment endpoints.
- **Prefer ids over personal data:** `CustomerId=42`, not the email or address. If you need the email, mask it (`r***@example.com`) or hash it.
- **Use redaction tooling:** the `Microsoft.Extensions.Compliance.Redaction` and `Microsoft.Extensions.Telemetry` libraries let you classify data (attributes on properties) and redact or hash it automatically in logs (`builder.Logging.EnableRedaction()`; verify current package names and APIs). Serilog supports destructuring policies and masking enrichers.
- **Configure HTTP logging carefully:** exclude `Authorization`, cookies and bodies on sensitive routes.
- **Retention and access:** shorter retention for verbose logs, role-based access to log stores.

```csharp
// Simple manual masking helper for the rare case you must log an email
public static string MaskEmail(string email)
{
    int at = email.IndexOf('@');
    return at <= 1 ? "***" : $"{email[0]}***{email[at..]}";
}
logger.LogInformation("Password reset requested for {EmailMasked}", MaskEmail(req.Email));
```

:::q Why should you not use string interpolation in log messages?
Because the message becomes a plain string: properties like `OrderId` are not stored as fields, every message is unique so you cannot group by event type, and the string is formatted even if that level is disabled. Message templates keep structured properties and are cheaper; `[LoggerMessage]` is cheapest for hot paths.
:::

:::q How do you correlate logs from one request across services?
Use W3C trace context. ASP.NET Core and `HttpClient` propagate `traceparent` automatically and put `TraceId`/`SpanId` into log scopes, so every log line from every service carries the same trace id. For messages on queues, propagate the trace context in message properties. Then search logs by trace id.
:::

## Serilog

### Complete Serilog setup (appsettings-driven)

**Definition.** Serilog is a popular structured-logging library with many *sinks* (destinations) and *enrichers*. It plugs into `Microsoft.Extensions.Logging`, so application code still uses `ILogger<T>`.

**Why teams pick it:** rich configuration from `appsettings.json`, many sinks (Console, File, Seq, Elasticsearch, Application Insights, OpenTelemetry), enrichers, compact request logging.

Packages: `Serilog.AspNetCore` (includes Console, File, Debug sinks and settings support), plus sinks as needed: `Serilog.Sinks.Seq`, `Elastic.Serilog.Sinks` (newer Elastic-maintained sink; older `Serilog.Sinks.Elasticsearch` is legacy), `Serilog.Sinks.ApplicationInsights`, `Serilog.Sinks.OpenTelemetry`, enrichers `Serilog.Enrichers.Environment`, `Serilog.Enrichers.Thread`. Verify package versions for your .NET version.

```csharp
// Program.cs
using Serilog;

// Bootstrap logger: captures errors that happen before configuration is loaded
Log.Logger = new LoggerConfiguration()
    .WriteTo.Console()
    .CreateBootstrapLogger();

try
{
    var builder = WebApplication.CreateBuilder(args);

    builder.Services.AddSerilog((services, cfg) => cfg
        .ReadFrom.Configuration(builder.Configuration)   // sinks, levels, enrichers from JSON
        .ReadFrom.Services(services)
        .Enrich.FromLogContext());

    builder.Services.AddControllers();
    var app = builder.Build();

    app.UseSerilogRequestLogging(o =>
    {
        // One summary event per request instead of many framework logs
        o.MessageTemplate =
            "HTTP {RequestMethod} {RequestPath} responded {StatusCode} in {Elapsed:0.0} ms";
        o.EnrichDiagnosticContext = (diag, http) =>
        {
            diag.Set("UserId", http.User.FindFirst("sub")?.Value ?? "anonymous");
            diag.Set("ClientIp", http.Connection.RemoteIpAddress?.ToString());
        };
        o.GetLevel = (http, elapsed, ex) =>
            ex is not null || http.Response.StatusCode >= 500 ? Serilog.Events.LogEventLevel.Error
            : elapsed > 2000 ? Serilog.Events.LogEventLevel.Warning
            : Serilog.Events.LogEventLevel.Information;
    });

    app.MapControllers();
    app.Run();
}
catch (Exception ex)
{
    Log.Fatal(ex, "Application terminated unexpectedly");
}
finally
{
    Log.CloseAndFlush();                                // flush buffered sinks on shutdown
}
```

`builder.Host.UseSerilog((ctx, services, cfg) => ...)` is the older equivalent registration and is still common in existing codebases.

```json
// appsettings.json
{
  "Serilog": {
    "Using": [ "Serilog.Sinks.Console", "Serilog.Sinks.File", "Serilog.Sinks.Seq" ],
    "MinimumLevel": {
      "Default": "Information",
      "Override": {
        "Microsoft.AspNetCore": "Warning",
        "Microsoft.EntityFrameworkCore": "Warning",
        "System.Net.Http.HttpClient": "Warning"
      }
    },
    "WriteTo": [
      { "Name": "Console",
        "Args": { "formatter": "Serilog.Formatting.Compact.RenderedCompactJsonFormatter, Serilog.Formatting.Compact" } },
      { "Name": "File",
        "Args": { "path": "logs/orders-.log", "rollingInterval": "Day",
                  "retainedFileCountLimit": 14, "fileSizeLimitBytes": 104857600,
                  "rollOnFileSizeLimit": true } },
      { "Name": "Seq", "Args": { "serverUrl": "http://seq:5341" } }
    ],
    "Enrich": [ "FromLogContext", "WithMachineName", "WithEnvironmentName", "WithThreadId" ],
    "Properties": { "Application": "Orders.Api" }
  }
}
```

### Sinks, enrichers and request logging

| Sink | Use when | Notes |
|---|---|---|
| Console (JSON) | Containers/Kubernetes: the platform collects stdout | Best default for cloud-native; no file management |
| File (rolling) | VMs/on-prem, local debugging | Set size limits and retention or disks fill up |
| Seq | Dev/test or small teams wanting great structured search | Self-hosted; free single-user licence for dev |
| Elasticsearch/OpenSearch (ELK) | Central log platform with Kibana dashboards | Mind index mappings and retention costs |
| Application Insights | Azure-hosted apps already using App Insights | Logs land in `traces`/`exceptions` correlated with requests |
| OpenTelemetry (OTLP) | Vendor-neutral pipeline to a collector | Lets you switch backends without code changes |

- **Enrichers** add properties to every event: `WithMachineName`, `WithEnvironmentName`, `WithThreadId`, `WithCorrelationId` (community), custom enrichers (`ILogEventEnricher`) for `TenantId` or app version.
- **`LogContext.PushProperty("OrderId", id)`** is Serilog's scope equivalent (requires `Enrich.FromLogContext()`).
- **`UseSerilogRequestLogging`** replaces the noisy multi-line ASP.NET Core request logs with one structured event per request (method, path, status, elapsed). Place it **after** `UseStaticFiles` if you do not want static file requests logged, and before the endpoints you want covered.
- **Asynchronous/batched sinks:** network sinks batch internally; wrap slow sinks with `Serilog.Sinks.Async` so logging never blocks requests. Always `Log.CloseAndFlush()` on shutdown.
- **Destructuring:** `{@Order}` serialises an object's properties, `{Order}` calls `ToString()`. Destructure only small DTOs, never entities with navigation properties (huge logs, PII).

:::warn Serilog pitfalls
Destructuring EF entities (`{@order}`) can serialise whole graphs including customer PII; forgetting `Enrich.FromLogContext()` makes `LogContext` and request scopes silently disappear; synchronous file logging on slow disks adds latency to every request; leaving `MinimumLevel` at `Debug` in production multiplies log cost.
:::

:::q Serilog or the built-in logger?
Both use the same `ILogger<T>` in application code, so it is a provider choice. Built-in plus OpenTelemetry export is enough for many cloud apps. Serilog adds configuration-driven sinks, enrichers, request logging and destructuring; I pick it when the team wants Seq/ELK or richer enrichment. Code does not change either way.
:::

## Application Insights

### What it is: classic SDK vs OpenTelemetry-based distro

**Definition.** Application Insights is the APM (Application Performance Monitoring) feature of **Azure Monitor**. It collects requests, dependencies, exceptions, traces (logs), page views, custom events and metrics, stores them in a Log Analytics workspace and gives you blades, Application Map, Live Metrics and KQL queries.

| | Classic Application Insights SDK | Azure Monitor OpenTelemetry Distro |
|---|---|---|
| Package | `Microsoft.ApplicationInsights.AspNetCore` | `Azure.Monitor.OpenTelemetry.AspNetCore` |
| Registration | `builder.Services.AddApplicationInsightsTelemetry();` | `builder.Services.AddOpenTelemetry().UseAzureMonitor();` |
| Custom telemetry API | `TelemetryClient` (`TrackEvent`, `TrackMetric`, `TrackDependency`) | Standard .NET APIs: `ActivitySource`, `Meter`, `ILogger` |
| Vendor lock-in | App Insights-specific | Standard OTel; can also export elsewhere |
| Status | Supported in existing apps; Microsoft points new apps to OpenTelemetry (newer SDK versions are being rebuilt on OTel; verify current guidance) | **Recommended for new apps** |

```csharp
// Option A: OpenTelemetry-based (new projects)
builder.Services.AddOpenTelemetry().UseAzureMonitor();   // connection string from config:
// "APPLICATIONINSIGHTS_CONNECTION_STRING" env var or AzureMonitor:ConnectionString

// Option B: classic SDK (common in existing codebases)
builder.Services.AddApplicationInsightsTelemetry();      // ApplicationInsights:ConnectionString
```

Use the **connection string** (not the old instrumentation key alone), and keep it in configuration or Key Vault. With managed identity you can also use Entra ID authentication for ingestion.

### Auto-collected telemetry and custom telemetry

Collected automatically for ASP.NET Core:
- **Requests** (incoming HTTP: URL, duration, status, success).
- **Dependencies** (outgoing `HttpClient` calls, SQL via SqlClient, Azure SDK calls such as Service Bus, Storage, Cosmos DB) with duration and result.
- **Exceptions** (unhandled and logged with an exception).
- **Traces** (your `ILogger` output, by default Warning and above for the App Insights provider; adjust the filter).
- **Performance counters / runtime metrics** (CPU, memory, request rate).
- **Page views and browser timings** when the JavaScript SDK is added to the frontend.

Custom telemetry with the classic SDK:

```csharp
public sealed class CheckoutService(TelemetryClient telemetry, IPaymentClient payments)
{
    public async Task<PaymentResult> PayAsync(Order order, CancellationToken ct)
    {
        // Business event: shows in customEvents, filterable by properties
        telemetry.TrackEvent("CheckoutStarted", new Dictionary<string, string>
        {
            ["OrderId"] = order.Id.ToString(), ["PaymentMethod"] = order.PaymentMethod
        });

        // Custom dependency for a call the SDK cannot see (e.g. a raw TCP/legacy client)
        var started = DateTimeOffset.UtcNow;
        var sw = Stopwatch.StartNew();
        bool success = false;
        try
        {
            var result = await payments.ChargeAsync(order, ct);
            success = result.Succeeded;
            return result;
        }
        finally
        {
            telemetry.TrackDependency("PSP", "Razorpay", "charge", started, sw.Elapsed, success);
            // Metric: pre-aggregated by the SDK before sending
            telemetry.GetMetric("CheckoutAmount", "Currency").TrackValue((double)order.Total, "INR");
        }
    }
}
```

With the OpenTelemetry distro you do the same with standard APIs: `ActivitySource.StartActivity` for dependencies/operations, `Meter` counters/histograms for metrics, and `ILogger` for events (covered in the next file).

### Sampling

High-traffic apps produce too much telemetry to keep everything. **Sampling** keeps a representative percentage and records the sampling rate so counts can be re-scaled in queries.

- **Adaptive sampling** (classic SDK default): automatically adjusts the rate to stay under a target volume of items per second.
- **Fixed-rate sampling**: keep e.g. 20% of traces; with OTel this is a sampler (e.g. `TraceIdRatioBasedSampler`) and is consistent across services because it is decided by trace id, so a sampled trace is complete end to end.
- **Ingestion sampling**: dropped at the service side; saves storage but not network.
- Keep sampling **consistent per trace** (parent-based) and consider not sampling errors or critical operations. Metrics should be pre-aggregated, not derived from sampled traces.

:::warn Sampling surprises
"I cannot find the failed request the customer reported" is often sampling. Use `itemCount` in KQL to re-scale counts (`summarize sum(itemCount)`), exclude important telemetry types from sampling, and make sure alerts are based on metrics (not sampled events).
:::

### Live Metrics, Application Map, Failures and Performance blades

| Blade / feature | What it shows | Use it to |
|---|---|---|
| **Live Metrics** | Near-real-time (about 1 s) request rate, failure rate, dependency calls, CPU/memory per instance, sample failures | Watch a deployment or an incident as it happens; not stored |
| **Application Map** | Auto-drawn topology of components (your services, SQL, Redis, external HTTP) with call counts, average duration and failure % on each edge | Spot which dependency is red/slow and how services connect |
| **Failures** | Failed requests, dependency failures and exceptions grouped by operation, response code and exception type, with counts over time; drill to samples | Find the top failing operations and the exception behind them |
| **Performance** | Operations ranked by duration and count with p50/p95/p99, distribution chart, dependency breakdown; drill into samples and the Profiler | Find slow endpoints and which dependency dominates their time |
| **Transaction search / End-to-end transaction details** | One operation's full waterfall: request, all dependencies, logs, exceptions across services sharing the operation id | Root-cause a single request ("checkout at 10:42") |
| **Availability** | Synthetic tests (URL pings or standard tests) from several regions | Know about outages before customers do |
| **Profiler / Snapshot Debugger** | Sampled code-level traces of slow requests; locals at the moment of an exception | Find the slow method or the bad state in production |
| **Workbooks / Dashboards** | Custom interactive reports over KQL | Team dashboards, SLO reports |

### KQL examples

KQL (Kusto Query Language) is how you query App Insights / Log Analytics. In the App Insights *Logs* blade the classic table names are `requests`, `dependencies`, `exceptions`, `traces`, `customEvents`, `customMetrics`, `pageViews` (the workspace equivalents are `AppRequests`, `AppDependencies`, and so on).

```text
// p95 latency and failure rate per endpoint, last 24 h
requests
| where timestamp > ago(24h)
| summarize count_ = sum(itemCount),
            p95_ms = percentile(duration, 95),
            failed = sumif(itemCount, success == false)
          by name
| extend failRate = round(100.0 * failed / count_, 2)
| order by p95_ms desc

// Which dependencies are slow or failing?
dependencies
| where timestamp > ago(1h)
| summarize calls = sum(itemCount), avg_ms = avg(duration),
            failures = sumif(itemCount, success == false) by target, type, name
| order by failures desc, avg_ms desc

// Top exceptions with a sample message
exceptions
| where timestamp > ago(24h)
| summarize n = sum(itemCount), sample = any(outerMessage) by type, problemId
| top 10 by n

// Everything that happened in ONE request (end-to-end), given its operation id
union requests, dependencies, exceptions, traces
| where operation_Id == "4bf92f3577b34da6a3ce929d0e0e4736"
| project timestamp, itemType, name, target, resultCode, duration, message, outerMessage
| order by timestamp asc

// Error rate over time, 5-minute bins (good for a chart or an alert rule)
requests
| where timestamp > ago(6h)
| summarize total = sum(itemCount), failed = sumif(itemCount, success == false)
          by bin(timestamp, 5m)
| extend errorPct = 100.0 * failed / total
| render timechart
```

:::example Real-world example
After a release, the Failures blade showed a jump in `500` on `POST /api/orders`, grouped under `SqlException: Timeout expired`. Application Map showed the SQL edge red with average duration up from 15 ms to 4 s. The Performance blade's dependency breakdown pointed at a new query; its plan revealed a missing index on a column added in the release. Adding the index fixed it within the hour. The whole investigation used only telemetry already being collected.
:::

:::q What does Application Insights collect automatically for an ASP.NET Core API?
Incoming requests, outgoing dependencies (HTTP, SQL, Azure SDK calls), exceptions, `ILogger` traces above the configured level, and runtime/performance metrics. Add the JavaScript SDK for page views and browser timings, and add custom events, metrics and dependencies for business-level signals.
:::

:::q What is sampling and what problems can it cause?
Sampling keeps a percentage of telemetry to control cost, recording the rate so totals can be re-scaled. Problems: the specific request a customer reports may have been dropped, and naive counts are wrong unless you sum `itemCount`. Use trace-consistent sampling, keep errors, and alert on pre-aggregated metrics.
:::
