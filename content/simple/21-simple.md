### Logs vs metrics vs traces

**In simple words:** These are the three main signals your app sends out so you can understand it in production. *Logs* are text events that say what happened. *Metrics* are numbers over time, like requests per second or error rate. *Traces* follow one request as it moves through all your services and show where the time went. They are linked by a shared *trace id* (one id for the whole request).

**Real-life example:** For a parcel delivery: logs are the driver's notes ("left at door"), metrics are the daily count of delivered parcels, and the trace is the tracking page showing every stop the parcel made.

**Interview question:** What is the difference between logs, metrics and traces?

**Simple answer:** Logs tell me what happened, with details. Metrics tell me how much and how often, and they are cheap to store, so I use them for dashboards and alerts. Traces tell me where a request travelled and which step was slow. I alert on metrics, investigate with traces, and get details from logs, all linked by the trace id.

### ILogger in ASP.NET Core

**In simple words:** `ILogger<T>` is the built-in logging interface in .NET. Your code writes logs through it, and *providers* decide where the logs go, such as Console, Application Insights, Serilog or OpenTelemetry. The *category* is the class name `T`. This lets you set the log level per namespace in `appsettings.json`.

**Real-life example:** You drop a letter in the post box. You do not care which truck or plane carries it; the post office (the provider) handles that.

**Interview question:** How does logging work in ASP.NET Core?

**Simple answer:** I inject `ILogger<T>` and write logs with message templates. Providers send the logs to places like the console or Application Insights. I control levels per category in configuration, for example `Warning` for `Microsoft.AspNetCore` and `Information` for my own code. Because the code depends only on `ILogger`, I can change providers without changing code.

```csharp
logger.LogInformation("Placing order for {CustomerId} with {ItemCount} items",
    req.CustomerId, req.Items.Count);
```

### Structured logging: message templates vs string interpolation

**In simple words:** *Structured logging* saves each value as a named field, not only as part of a sentence. With a template like `"Order {OrderId} placed"`, `OrderId` is stored separately, so you can search and group by it. With string interpolation (`$"Order {id} placed"`), you get only a flat string. The string is also built even when that log level is turned off.

**Real-life example:** A form with separate boxes for name, phone and city is easy to sort and search. A single paragraph with all the details mixed together is not.

**Interview question:** Why should you not use string interpolation in log messages?

**Simple answer:** With interpolation, the message becomes one plain string. Fields like `OrderId` are lost, every message is unique so I cannot group by event type, and the string is built even when the level is off. Message templates keep named properties and are cheaper. I also pass the exception as the first argument so the stack trace is saved.

```csharp
// Bad:  logger.LogInformation($"Order {order.Id} placed");
logger.LogInformation("Order {OrderId} placed", order.Id);
```

### Log levels: what to use when

**In simple words:** Log levels show how important a message is. `Trace` and `Debug` are for developer details and are usually off in production. `Information` marks normal business steps, like "order placed". `Warning` means something unexpected happened but was handled. `Error` means the current operation failed. `Critical` means the whole app or a key feature is down.

**Real-life example:** In a hospital, a routine check is information, a slightly high temperature is a warning, a failed treatment is an error, and a cardiac arrest is critical.

**Interview question:** Which log level would you use for a declined card payment?

**Simple answer:** Not `Error`, because a declined card is an expected business result. I log it as `Information` or `Warning` with the reason, and I count it in a metric. I keep `Error` for real failures of our operation, such as the payment provider being unreachable after retries.

### Scopes and enrichment

**In simple words:** A *scope* adds the same properties, like `OrderId`, to every log written inside a block of code. You do not have to pass them to each log call. *Enrichment* adds properties to all logs in the app, like machine name, environment, app version or tenant. ASP.NET Core adds `TraceId` and `SpanId` to the scope automatically, which links logs to traces.

**Real-life example:** At a conference, every attendee wears a badge with their name and company. Everything they do there is linked to that badge without saying their name each time.

**Interview question:** How do you add the same context to many log lines?

**Simple answer:** I use `logger.BeginScope` with properties like `OrderId` and `TenantId`. Every log inside the `using` block then carries them. For app-wide values like environment or version I use enrichers, for example Serilog's `Enrich.FromLogContext()` and `WithMachineName`.

```csharp
using (logger.BeginScope(new Dictionary<string, object> { ["OrderId"] = order.Id }))
{
    logger.LogInformation("Charging payment");   // includes OrderId
}
```

### High-performance logging: the LoggerMessage source generator

**In simple words:** The `[LoggerMessage]` attribute lets the compiler create fast, strongly typed log methods for you. The message template is parsed once at build time, not on every call. Value types are not boxed (wrapped as objects). The log level is checked before any work is done. Use it for logs in code that runs very often.

**Real-life example:** A shop prints ready-made price labels once, instead of hand-writing each label every time a customer buys something.

**Interview question:** How do you make logging faster in hot code paths?

**Simple answer:** I use the `[LoggerMessage]` source generator. It creates typed log methods at compile time, so there is no template parsing or boxing at runtime, and nothing happens if the level is disabled. I also give each event a stable `EventId`, which makes it easy to search and alert on.

```csharp
[LoggerMessage(EventId = 1001, Level = LogLevel.Information,
    Message = "Order {OrderId} placed")]
public static partial void OrderPlaced(ILogger logger, Guid orderId);
```

### PII and secret redaction

**In simple words:** *PII* means personally identifiable information, like name, email, phone or ID number. Logs are copied to many systems and kept for months, so leaked data in logs is a real risk. Never log passwords, tokens, full card numbers or full request bodies of login and payment calls. Log ids instead of personal data, and mask or hash data when you must log it. *Redaction* means hiding sensitive parts automatically.

**Real-life example:** A bank receipt shows only the last four digits of your card number. The rest is hidden with stars.

**Interview question:** How do you keep sensitive data out of logs?

**Simple answer:** I log ids like `CustomerId` instead of emails or names, and I mask anything sensitive I must log. I never log passwords, tokens or card data, and I exclude auth headers and sensitive bodies from HTTP logging. I can also use the Microsoft redaction libraries to classify and hide data automatically, with short retention and limited access to log stores.

### Complete Serilog setup (appsettings-driven)

**In simple words:** Serilog is a popular structured logging library. It plugs into `ILogger<T>`, so your code does not change. You set levels, *sinks* (where logs go) and *enrichers* (extra properties) in `appsettings.json`. A *bootstrap logger* catches errors during startup, and `Log.CloseAndFlush()` makes sure buffered logs are written when the app stops.

**Real-life example:** A mail sorting centre gets all letters at one desk. Then, based on written rules, it sends each one to the right city.

**Interview question:** Should you use Serilog or the built-in logger?

**Simple answer:** Both use the same `ILogger<T>` in app code, so it is only a provider choice. The built-in logger with OpenTelemetry export is enough for many cloud apps. I pick Serilog when the team wants config-driven sinks like Seq or Elasticsearch, rich enrichers and compact request logging.

```csharp
builder.Services.AddSerilog((sp, cfg) => cfg
    .ReadFrom.Configuration(builder.Configuration)
    .Enrich.FromLogContext());
```

### Sinks, enrichers and request logging

**In simple words:** A *sink* is a place where Serilog writes logs: Console, File, Seq, Elasticsearch, Application Insights or OpenTelemetry. In containers, writing JSON to the console is the best default. *Enrichers* add properties like machine name or tenant to every log. `UseSerilogRequestLogging` replaces many framework log lines with one clear event per request: method, path, status and time taken.

**Real-life example:** A sink is like choosing where a photo is saved: your phone, the cloud, or a printed album. Enrichers are the date and location stamped on each photo.

**Interview question:** What does UseSerilogRequestLogging do?

**Simple answer:** It writes one structured event per HTTP request with the method, path, status code and elapsed time. This replaces several noisy framework log lines. I can add values like user id through the diagnostic context. I also avoid destructuring EF entities, because it can log whole object graphs with personal data.

### What it is: classic SDK vs OpenTelemetry-based distro

**In simple words:** Application Insights is the APM (Application Performance Monitoring) part of Azure Monitor. It collects requests, calls to other services, exceptions and logs, and lets you search them. There are two ways to send data. The classic SDK uses its own `TelemetryClient`. The newer Azure Monitor OpenTelemetry distro uses standard .NET APIs and is recommended for new apps.

**Real-life example:** The classic SDK is like a phone charger that fits only one brand. The OpenTelemetry distro is like a USB-C charger that works with many devices.

**Interview question:** For a new project, would you use the classic Application Insights SDK or the OpenTelemetry distro?

**Simple answer:** I would use the Azure Monitor OpenTelemetry distro with `UseAzureMonitor()`. It uses standard .NET APIs like `ActivitySource`, `Meter` and `ILogger`, and Microsoft recommends it for new apps. It also avoids lock-in, because the same instrumentation can send data to other tools. I keep the connection string in configuration or Key Vault.

```csharp
builder.Services.AddOpenTelemetry().UseAzureMonitor();
```

### Auto-collected telemetry and custom telemetry

**In simple words:** *Telemetry* is data your app sends about itself. Application Insights collects some of it automatically: incoming requests, *dependencies* (outgoing calls to HTTP, SQL and Azure services), exceptions, logs and runtime metrics. *Custom telemetry* is data you add yourself, like a business event "CheckoutStarted" or a metric for order amount. Add the JavaScript SDK to also see page views from the browser.

**Real-life example:** A car's dashboard shows speed and fuel automatically. A taxi driver also writes down each fare in a notebook; that is custom data.

**Interview question:** What does Application Insights collect automatically for an ASP.NET Core API?

**Simple answer:** It collects incoming requests, outgoing dependencies like HTTP, SQL and Azure SDK calls, exceptions, `ILogger` logs above the set level, and runtime metrics. I add the JavaScript SDK for page views. I add custom events and metrics for business signals, using `TelemetryClient` or, with OpenTelemetry, `ActivitySource` and `Meter`.

### Sampling

**In simple words:** Busy apps create too much telemetry to keep all of it. *Sampling* keeps only a percentage, for example 20%, and remembers the rate so totals can be scaled back up. Good sampling is decided per trace, so a kept request is kept complete across all services. The risk: the exact request a customer complains about may have been dropped.

**Real-life example:** A factory checks 1 bottle in every 100 for quality. It does not test every bottle, but it still knows the overall quality.

**Interview question:** What is sampling and what problems can it cause?

**Simple answer:** Sampling keeps a share of telemetry to control cost and records the rate so counts can be corrected. One problem is that a specific failed request may be missing. Another is wrong totals, unless I use `sum(itemCount)` in KQL. I use trace-consistent sampling, keep errors when possible, and base alerts on metrics, not sampled events.

### Live Metrics, Application Map, Failures and Performance blades

**In simple words:** These are screens in Application Insights. *Live Metrics* shows requests, failures and CPU almost in real time, which is good during a deployment. *Application Map* draws your services and their dependencies, and shows slow or failing links in red. *Failures* groups errors by operation and exception type. *Performance* lists the slowest operations with p50, p95 and p99 times. *End-to-end transaction details* shows one request's full path.

**Real-life example:** Application Map is like a city traffic map where jammed roads turn red. Live Metrics is like the live speedometer in your car.

**Interview question:** Which Application Insights features do you use to investigate a production problem?

**Simple answer:** I start with Failures or Performance to find the worst operation. Application Map shows which dependency is red or slow. Then I open one sample in End-to-end transaction details to see the full waterfall with logs and exceptions. During a deployment I watch Live Metrics.

### KQL examples

**In simple words:** *KQL* (Kusto Query Language) is the query language for Application Insights and Log Analytics. You start from a table, like `requests`, `dependencies`, `exceptions` or `traces`. Then you add steps with the pipe `|`: filter, summarize, sort. It is a fast way to find p95 latency, error rates or everything that happened in one request.

**Real-life example:** It is like asking a librarian: "From the history section, give me books from 2020, grouped by author, sorted by count".

**Interview question:** How would you find the slowest endpoints in Application Insights with KQL?

**Simple answer:** I query the `requests` table for a time range, group by `name`, and compute `percentile(duration, 95)` and the failure count. Because of sampling, I count with `sum(itemCount)`. To see one request end to end, I union `requests`, `dependencies`, `exceptions` and `traces` and filter by `operation_Id`.

```text
requests
| where timestamp > ago(24h)
| summarize p95 = percentile(duration, 95), calls = sum(itemCount) by name
| order by p95 desc
```

### OpenTelemetry in .NET

**In simple words:** *OpenTelemetry* (OTel) is an open, vendor-neutral standard for traces, metrics and logs. You add instrumentation once and can send the data to any backend, like Azure Monitor, Jaeger, Prometheus or Grafana, by changing configuration. In .NET, the built-in APIs already match OTel: `ActivitySource` for traces, `Meter` for metrics and `ILogger` for logs. ASP.NET Core, `HttpClient` and SqlClient already produce this data.

**Real-life example:** It is like a universal power adapter. You plug in once, and it works in any country's socket.

**Interview question:** What is OpenTelemetry and how do you add it to a .NET app?

**Simple answer:** OpenTelemetry is the standard way to produce and export traces, metrics and logs without vendor lock-in. I call `AddOpenTelemetry()`, add ASP.NET Core, HttpClient and SQL instrumentation, register my own sources and meters, and export with OTLP or `UseAzureMonitor()`. In production I often send data to an OpenTelemetry Collector, which filters and forwards it.

```csharp
builder.Services.AddOpenTelemetry()
    .WithTracing(t => t.AddAspNetCoreInstrumentation().AddHttpClientInstrumentation())
    .WithMetrics(m => m.AddAspNetCoreInstrumentation())
    .UseOtlpExporter();
```

### Custom instrumentation with ActivitySource and Meter

**In simple words:** Sometimes you want your own spans and metrics for business steps. An `ActivitySource` creates *spans* (timed steps inside a trace), like "Checkout.Place". A `Meter` creates metrics like counters and histograms, for example "orders placed". Keep high-cardinality values (values with many unique options, like order id) on spans and logs, never as metric tags.

**Real-life example:** A runner's watch records each lap time (spans) and also the total number of runs this month (a counter).

**Interview question:** Why should you not put user id or order id as a tag on a metric?

**Simple answer:** Each unique tag value creates a new time series. Millions of user or order ids would create millions of series, so cost and query time explode. I put such ids on spans and logs. On metrics I use tags with few values, like payment method.

```csharp
using var activity = Source.StartActivity("Checkout.Place");
activity?.SetTag("order.id", order.Id);
ordersPlaced.Add(1, new KeyValuePair<string, object?>("payment.method", method));
```

### Distributed tracing and W3C trace context

**In simple words:** A *trace* is the full journey of one request across many services. It is a tree of *spans*. Each span has its own span id, its parent's id and the shared trace id. Services pass this context in the W3C `traceparent` HTTP header. ASP.NET Core and `HttpClient` do this automatically. For message queues, you put the context in the message properties.

**Real-life example:** A parcel has one tracking number (trace id). Each stop, like the warehouse, the truck or the local office, has its own scan record (span) linked to that number.

**Interview question:** What is the difference between a trace id and a span id?

**Simple answer:** The trace id identifies the whole request journey and is shared by every span in every service. A span id identifies one step, like an HTTP handler or a SQL call. Each span stores its parent span id, which is how the tree is built. The context travels in the W3C `traceparent` header.

### Metric types

**In simple words:** There are four main metric types. A *counter* only goes up, like requests served; you look at its rate. An *UpDownCounter* goes up and down, like active connections. A *gauge* is a current value at one moment, like CPU % or queue length. A *histogram* records a spread of values, like request durations, so you can calculate percentiles.

**Real-life example:** A car's odometer is a counter; it only goes up. The speedometer is a gauge. A record of all your trip times, so you can see your slowest 5%, is a histogram.

**Interview question:** Counter vs gauge vs histogram?

**Simple answer:** A counter only increases, like requests or errors, and I chart its rate. A gauge shows a current value, like queue depth or memory. A histogram records a distribution, like latency, so I can get p95 and p99. Percentiles must come from histograms, not from averaging averages.

### RED, USE and the four golden signals

**In simple words:** These are simple checklists for what to monitor. *RED* is for services that handle requests: Rate, Errors, Duration. *USE* is for resources like CPU, memory or connection pools: Utilization, Saturation (waiting work), Errors. Google's *four golden signals* are Latency, Traffic, Errors and Saturation. Add business metrics too, like orders per minute; they often catch problems that technical metrics miss.

**Real-life example:** For a restaurant: RED is how many customers come, how many complain, and how long they wait. USE is how busy the kitchen is and how long the order queue is.

**Interview question:** What are the RED and USE methods?

**Simple answer:** RED (Rate, Errors, Duration) is for request-driven services like APIs. USE (Utilization, Saturation, Errors) is for resources like CPU, memory, thread pool and database connections. Together with the four golden signals, they tell me what goes on a service dashboard, plus a few business metrics.

### Liveness vs readiness

**In simple words:** Health checks are endpoints that Kubernetes or a load balancer calls to check your app. *Liveness* asks "is the process alive and not stuck?". If it fails, the container is restarted. *Readiness* asks "can this instance take traffic now?". If it fails, traffic stops going to it until it recovers. *Startup* probes give slow apps time to start. Never put the database in the liveness check.

**Real-life example:** Liveness is checking if a shop worker is awake. Readiness is checking if the worker has their tools and can serve customers right now.

**Interview question:** What is the difference between liveness and readiness probes?

**Simple answer:** Liveness checks only if the app process is alive; a failure restarts the container. So it must not check external dependencies, or a short database blip would restart every pod. Readiness checks critical dependencies like the database and cache; a failure only removes the instance from the load balancer until it recovers.

```csharp
app.MapHealthChecks("/health/live",  new() { Predicate = c => c.Tags.Contains("live") });
app.MapHealthChecks("/health/ready", new() { Predicate = c => c.Tags.Contains("ready") });
```

### Alert rules: thresholds vs anomaly detection

**In simple words:** An *alert* is a rule that notifies a person when a signal crosses a limit. A *static threshold* is a fixed limit, like "p95 latency above 800 ms for 5 minutes". It is simple and clear. *Dynamic thresholds* (anomaly detection) learn normal patterns, like busy mornings and quiet nights, and alert when values are unusual. In Azure Monitor, alerts send notifications through *action groups* (email, SMS, Teams, PagerDuty).

**Real-life example:** A static threshold is a smoke alarm that rings at a fixed smoke level. Anomaly detection is a neighbour who knows your routine and notices when something is strange.

**Interview question:** When would you use a static threshold and when anomaly detection?

**Simple answer:** I use static thresholds for clear limits like SLO error rates, latency targets or disk at 90%, because they are predictable. I use dynamic thresholds for signals with daily or weekly patterns, like traffic drops or business KPIs. I also add a minimum volume condition, so a few failures at night do not wake people up.

### SLI, SLO, SLA and error budgets

**In simple words:** An *SLI* (service level indicator) is a measured value, like "% of checkouts that succeed in under 1 second". An *SLO* (objective) is your internal target, like 99.9% over 30 days. An *SLA* (agreement) is a contract with customers, with penalties; it is usually looser than the SLO. The *error budget* is the failure you are allowed: 100% minus the SLO. For 99.9% over 30 days, that is about 43 minutes.

**Real-life example:** A bus company measures on-time arrivals (SLI), aims for 99% internally (SLO), and promises customers 95% with refunds if missed (SLA).

**Interview question:** What is an error budget and how is it used?

**Simple answer:** It is the unreliability allowed by the SLO. For 99.9% over 30 days, it is about 43 minutes of downtime. While budget remains, the team can ship features faster. When it is used up, we pause risky releases and work on reliability. Burn-rate alerts warn us when the budget is being used too fast.

### Avoiding alert fatigue and writing runbooks

**In simple words:** *Alert fatigue* happens when there are so many alerts that people start ignoring them. Alert on symptoms users feel, like errors and slow responses, not on every cause like CPU on one server. Every alert that wakes someone must need action now. A *runbook* is a short guide linked to the alert: what it means, what to check and how to fix it.

**Real-life example:** A car alarm that goes off every time a cat walks by soon gets ignored by everyone, even when a real thief comes.

**Interview question:** How do you avoid alert fatigue?

**Simple answer:** I alert on user-facing symptoms tied to SLOs and add minimum volume and duration conditions. I route alerts by severity, group duplicates, and link a runbook to every alert. Every month I delete or tune alerts that nobody acted on.

### Performance monitoring and dashboards

**In simple words:** Performance monitoring combines several tools: APM traces, availability tests (automatic pings from many regions), real-user monitoring in the browser, database monitoring and load tests. Dashboards show this in one place, using Azure Workbooks or Grafana. A good layout shows golden signals and SLO status at the top, then dependencies, then resources, then business KPIs. Deployment markers help you link problems to releases.

**Real-life example:** A pilot's cockpit shows the most important instruments in the centre and less urgent ones around the sides.

**Interview question:** What would you put on a service dashboard?

**Simple answer:** At the top, I put rate, errors, p95 latency and SLO status. Below that, I show dependency health like the database, cache and external APIs. Then resources like CPU, memory, GC and thread pool queue. At the bottom, business KPIs like orders per minute. I add deployment markers so regressions line up with releases.

### Incident response flow

**In simple words:** An incident is a production problem that hurts users. The flow is: detect, triage, communicate, mitigate, resolve, then learn. *Triage* means deciding how serious it is and who owns it. *Mitigate first* means restoring service quickly, for example by rolling back, before finding the root cause. Afterwards, hold a *blameless postmortem* (a review that focuses on fixing systems, not blaming people).

**Real-life example:** When there is a fire, firefighters first put it out and get people safe. Investigators find out the cause later.

**Interview question:** What do you do during and after a production incident?

**Simple answer:** I make sure an owner and a severity are set, and status updates go out in one channel. I mitigate first by rolling back, turning off a feature flag, scaling out or failing over. Then I find and fix the root cause. Finally I write a blameless postmortem with a timeline, impact, root cause, and action items with owners and dates.
