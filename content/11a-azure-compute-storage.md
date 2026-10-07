## Azure Mental Model

**Definition.** Azure is a hierarchy of scopes: *tenant* (Microsoft Entra directory) → *management groups* → *subscriptions* (billing + quota boundary) → *resource groups* (lifecycle container) → *resources*. Everything is created through **Azure Resource Manager (ARM)**, which is what the portal, CLI, PowerShell, Bicep/Terraform and SDKs all call.

**Why it matters.** RBAC, Policy, budgets and tags all inherit down this tree. Interviewers often start with "how would you organise Azure for a team?" — the answer is one subscription per environment (or per workload + env), one resource group per deployable unit, and everything defined as code.

**Control plane vs data plane.** Control plane = managing the resource (create a storage account, change a SKU) via ARM. Data plane = using it (read a blob, send a queue message, query Cosmos). They have *separate* RBAC roles — `Contributor` can create a storage account but cannot read its blobs; that needs `Storage Blob Data Reader`.

```bash
# A typical bootstrap: group + plan + web app, all from the CLI
az group create -n rg-shop-dev -l westeurope
az appservice plan create -g rg-shop-dev -n plan-shop-dev --sku P1v3 --is-linux
az webapp create -g rg-shop-dev -p plan-shop-dev -n shop-api-dev \
   --runtime "DOTNETCORE:9.0"
```

:::tip What interviewers look for
Say "infrastructure as code (Bicep), managed identity instead of secrets, private networking for data services, and monitoring from day one". Those four phrases signal real production experience.
:::

## Azure Compute

### Azure App Service

**Definition.** A fully managed PaaS for hosting web apps, REST APIs and WebJobs on Windows or Linux (or a custom container). You push code or an image; Azure handles OS patching, load balancing, TLS, custom domains and scaling.

**When to choose.** The default home for an ASP.NET Core API or a server-rendered site: low ops overhead, slots for zero-downtime deploys, built-in autoscale. Choose something else if you need many small services with scale-to-zero (Container Apps), full OS control (VM) or custom orchestration (AKS).

#### Plans, tiers and the billing gotcha

An **App Service plan** is the *compute you rent* (region, OS, size, instance count). Many apps can share one plan. **You pay for the plan, not for each app** — and a stopped app still costs money because the plan is still allocated.

| Tier | Typical use | Notable features |
|---|---|---|
| Free / Shared (F1, D1) | Demos | CPU quota, no custom TLS, no Always On |
| Basic (B1-B3) | Dev/test | Custom domains + TLS, manual scale only, **no slots**, no autoscale |
| Standard (S1-S3) | Small production | Autoscale, deployment slots (5), VNet integration |
| Premium v3 / v4 | Production | More slots, faster CPU/memory, zone redundancy, private endpoints |
| Isolated v2 (ASE) | Compliance, very high scale | Dedicated single-tenant environment inside your VNet |

Slot counts and tier names change; verify current limits in the docs before quoting numbers.

#### Scale up vs scale out

| | Scale up (vertical) | Scale out (horizontal) |
|---|---|---|
| What | Bigger SKU (P1v3 → P2v3) | More instances (2 → 5) |
| Downtime | Brief restart | None |
| Needs stateless app | No | **Yes** |
| Limit | Largest SKU | Per-tier instance cap (e.g., 30 on Premium) |
| Fixes | CPU/memory bound apps | Throughput, availability |

**Autoscale** adds or removes instances from rules: a metric (CPU, memory, HTTP queue length, or a custom App Insights metric), a threshold, a duration, an amount and a **cooldown**. Always set both a scale-out and a scale-in rule and a sensible min/max, or you get flapping or surprise bills. Schedule-based profiles (e.g., 5 instances weekdays 9-18) are cheaper than reacting late. Premium tiers also offer *automatic scaling* (platform-managed, with pre-warmed instances), which is separate from rule-based autoscale.

```bash
az monitor autoscale create -g rg-shop-prod --resource plan-shop-prod \
   --resource-type Microsoft.Web/serverfarms --name as-shop \
   --min-count 2 --max-count 6 --count 2
az monitor autoscale rule create -g rg-shop-prod --autoscale-name as-shop \
   --condition "CpuPercentage > 70 avg 10m" --scale out 1 --cooldown 10
az monitor autoscale rule create -g rg-shop-prod --autoscale-name as-shop \
   --condition "CpuPercentage < 30 avg 10m" --scale in 1 --cooldown 10
```

#### Deployment slots and swap

A slot is a live app with its own hostname (`shop-api-staging.azurewebsites.net`) running on the *same plan*. Flow: deploy to staging → warm it up → **swap**. A swap does not copy files; it re-routes the production hostname to the already-warm staging instances, so there is no cold start and no downtime. If something is wrong, **swap back** — that is your instant rollback.

```bash
az webapp deployment slot create -g rg-shop-prod -n shop-api --slot staging
# deploy a package to the slot, then:
az webapp deployment slot swap -g rg-shop-prod -n shop-api \
   --slot staging --target-slot production
```

Key points:
- Mark settings that must not move (e.g., `ASPNETCORE_ENVIRONMENT`, a staging DB connection string) as **Deployment slot setting** (sticky). Everything else swaps with the code.
- Swap performs warm-up: it restarts the staging instances with production settings and pings the root (or `WEBSITE_SWAP_WARMUP_PING_PATH`) before routing traffic.
- *Swap with preview* applies production settings to the staging slot first so you can test before completing.
- Both slots share one database — a breaking schema change breaks the old code if you swap back. Use expand/contract migrations.
- Slots share the plan's CPU/memory, so heavy testing on staging slows production.

#### Settings that matter

| Setting | Purpose |
|---|---|
| App settings | Become environment variables and override `appsettings.json` (`ConnectionStrings__Default`, `Jwt__Issuer`; double underscore = `:`) |
| `ASPNETCORE_ENVIRONMENT` | Selects `appsettings.{Env}.json` |
| `WEBSITE_RUN_FROM_PACKAGE=1` | Mount the deployed zip read-only; atomic deploy, faster cold start |
| `WEBSITES_PORT` | Port your **custom container** listens on (use `8080` for .NET 8+ images) |
| `WEBSITES_ENABLE_APP_SERVICE_STORAGE` | Persist `/home` for containers |
| `WEBSITE_SWAP_WARMUP_PING_PATH` | Endpoint hit before a swap completes |
| Key Vault reference | `@Microsoft.KeyVault(SecretUri=https://kv-shop.vault.azure.net/secrets/SqlPwd/)` |

**Always On.** Without it, an app idle for ~20 minutes is unloaded and the next request pays a cold start. Turn it on for production APIs and anything with background work (Basic tier and above).

**Health check.** Set a path such as `/health/ready` in *Monitoring → Health check*. The platform pings it; instances that keep failing are taken out of load-balancer rotation (and eventually replaced). It only helps if you run **2 or more instances**, and the endpoint should check real dependencies cheaply.

```bicep
resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: 'plan-shop-prod'
  location: resourceGroup().location
  sku: { name: 'P1v3', capacity: 2 }
  kind: 'linux'
  properties: { reserved: true }
}

resource api 'Microsoft.Web/sites@2023-12-01' = {
  name: 'shop-api-prod'
  location: resourceGroup().location
  identity: { type: 'SystemAssigned' }          // managed identity
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'DOTNETCORE|9.0'
      alwaysOn: true
      healthCheckPath: '/health/ready'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
    }
  }
}

resource staging 'Microsoft.Web/sites/slots@2023-12-01' = {
  parent: api
  name: 'staging'
  location: resourceGroup().location
  properties: { serverFarmId: plan.id }
}
```

:::warn Gotchas
- **ARR Affinity** (sticky cookie) is on by default; turn it off for stateless APIs or load spreads unevenly after scale-out.
- All apps in a plan share outbound IPs and **SNAT ports**; many outbound HTTP calls without `HttpClientFactory` cause port exhaustion. Use VNet integration + NAT Gateway for stable outbound IPs.
- Local disk is ephemeral except `/home`. Never write uploads to local disk — use Blob Storage.
:::

:::q How do you deploy to App Service with zero downtime and roll back fast?
Deploy to a *staging slot*, let the swap warm it up, then swap into production. Swap re-points traffic to already-running instances, so there is no cold start. For rollback I swap back, which is instant. I keep environment-specific settings as sticky slot settings and use backward-compatible DB migrations because both slots share the database.
:::

### Azure Virtual Machines and Scale Sets

**Definition.** IaaS: you get a VM (OS + disks + NIC) and own everything above the hypervisor — patching, antivirus, runtime, backups.

**When to choose.** Lift-and-shift of legacy .NET Framework / Windows-service apps, software that needs a specific OS or kernel, licensing constraints (Azure Hybrid Benefit), GPU or very large memory, self-hosted CI agents, or a third-party product that only ships as an installer. For a greenfield ASP.NET Core API, PaaS is almost always better.

| Concept | What it gives you |
|---|---|
| **Availability set** | Spreads VMs across *fault domains* (racks) and *update domains* (maintenance batches) inside one datacenter; 99.95% SLA with 2+ VMs |
| **Availability zones** | Separate physical datacenters in a region; VMs in 2-3 zones; 99.99% SLA. Preferred over availability sets where the region supports zones |
| **VM Scale Set (VMSS)** | A group of identical VMs with autoscale and a load balancer; flexible orchestration mode spreads across zones |
| **Managed disks** | Premium SSD v2/Premium SSD/Standard; snapshots; disk encryption |
| **Cost levers** | Reserved instances / Savings Plans (1-3 yr), Spot VMs (evictable), Hybrid Benefit, auto-shutdown for dev VMs |

```bash
az vm create -g rg-legacy -n vm-erp01 --image Win2022Datacenter \
   --size Standard_D4s_v5 --zone 1 --admin-username azureadmin \
   --assign-identity --public-ip-address ""   # no public IP; use Bastion
az vm auto-shutdown -g rg-legacy -n vm-erp01 --time 1900   # dev cost saver
```

:::warn Billing gotcha
"Stopped" from inside the OS (or portal "Stop" on some states) keeps compute reserved and **still bills**. Only **Deallocated** stops compute charges. Disks and public IPs bill regardless.
:::

:::q Availability set vs availability zone?
An availability set protects against rack and maintenance failures inside one datacenter (99.95%). Zones are separate datacenters with independent power and cooling, so they survive a datacenter failure (99.99%). I use zones when the region supports them and combine them with a zone-redundant load balancer.
:::

### Azure Functions

**Definition.** Event-driven serverless compute: small units of code (functions) fired by a **trigger** (HTTP, timer, queue, blob, Service Bus, Event Hubs, Cosmos change feed) with optional declarative **input/output bindings** that read/write other services without SDK boilerplate.

**When to choose.** Background jobs, webhooks, queue consumers, scheduled tasks, glue between services, spiky workloads. Avoid for long-running CPU-heavy jobs on the Consumption plan, or when you need a rich ASP.NET Core pipeline (use App Service/Container Apps).

#### Isolated worker model (the only future)

The **isolated worker** model runs your function app as a separate .NET process with its own `Program.cs`, DI and middleware, decoupled from the Functions host. The older **in-process** model is being retired — support ends **10 November 2026** — so new code must use isolated (supports .NET 8, 9, 10 and .NET Framework). Verify the support matrix in the docs.

```csharp
// Program.cs
using Microsoft.Azure.Functions.Worker.Builder;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

var builder = FunctionsApplication.CreateBuilder(args);
builder.ConfigureFunctionsWebApplication();          // ASP.NET Core integration
builder.Services
    .AddApplicationInsightsTelemetryWorkerService()
    .ConfigureFunctionsApplicationInsights();
builder.Services.AddSingleton<IOrderService, OrderService>();   // normal DI
builder.Build().Run();
```

```csharp
// OrderFunctions.cs  (HTTP + Queue + Timer in one class)
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Extensions.Logging;

public record OrderMessage(Guid OrderId, string CustomerId, decimal Total);

public class OrderFunctions(ILogger<OrderFunctions> log, IOrderService orders)
{
    // 1. HTTP trigger: accept an order, enqueue it for async processing
    [Function("CreateOrder")]
    public async Task<CreateOrderOutput> Create(
        [HttpTrigger(AuthorizationLevel.Function, "post", Route = "orders")] HttpRequest req)
    {
        var dto = await req.ReadFromJsonAsync<OrderMessage>();
        return new CreateOrderOutput
        {
            Message = System.Text.Json.JsonSerializer.Serialize(dto),   // goes to the queue
            HttpResponse = new AcceptedResult($"/orders/{dto!.OrderId}", dto)
        };
    }

    // 2. Queue trigger: process messages (identity-based connection)
    [Function("ProcessOrder")]
    public async Task Process(
        [QueueTrigger("orders-incoming", Connection = "StorageConn")] OrderMessage msg,
        CancellationToken ct)
    {
        log.LogInformation("Processing order {OrderId}", msg.OrderId);
        await orders.FulfilAsync(msg, ct);   // throw => retry; after 5 tries => poison queue
    }

    // 3. Timer trigger: NCRONTAB {sec} {min} {hour} {day} {month} {dow}
    [Function("NightlyReport")]
    public Task Nightly([TimerTrigger("0 0 2 * * *")] TimerInfo timer)
    {
        log.LogInformation("Report run; next at {Next}", timer.ScheduleStatus?.Next);
        return orders.BuildDailyReportAsync();
    }
}

// Multi-output binding: one return type, two destinations
public class CreateOrderOutput
{
    [QueueOutput("orders-incoming", Connection = "StorageConn")]
    public string? Message { get; set; }

    [HttpResult]
    public IActionResult? HttpResponse { get; set; }
}
```

Identity-based connection: instead of a connection string, set app settings `StorageConn__queueServiceUri = https://shopstore.queue.core.windows.net` (and `__credential = managedidentity` for user-assigned) and grant the function's identity `Storage Queue Data Contributor`. Packages: `Microsoft.Azure.Functions.Worker`, `.Worker.Sdk`, `.Worker.Extensions.Http.AspNetCore`, `.Worker.Extensions.Storage.Queues`, `.Worker.Extensions.Timer`.

#### Hosting plans

| Plan | Scale | Cold start | VNet | Billing | Use when |
|---|---|---|---|---|---|
| **Consumption** (legacy) | 0 → 200 instances | Yes | No | Per execution + GB-s, free grant | Cheap, low-traffic jobs |
| **Flex Consumption** | 0 → up to ~1000, per-function scaling | Reduced; optional *always-ready* instances | **Yes** | Per execution (+ always-ready baseline) | Default serverless choice now |
| **Premium (EP1-3)** | Pre-warmed, min instances | None | Yes | Per vCPU/memory-second, always at least 1 instance | Steady load, no cold start, long runtime |
| **Dedicated (App Service plan)** | Plan instances | Always On needed | Yes | Plan price | You already pay for an idle plan |

Defaults: Consumption timeout 5 min (max 10); Premium/Flex allow much longer. Microsoft has announced the Linux Consumption plan's retirement in favour of Flex — verify dates in the docs.

**Cold start** = the delay while a new instance is allocated, the host starts and your assemblies load. Reduce it with Flex/Premium always-ready or pre-warmed instances, smaller packages, `WEBSITE_RUN_FROM_PACKAGE=1`, avoiding heavy static initialisation, and ReadyToRun compilation.

#### Durable Functions

An extension for **stateful workflows** in code: an *orchestrator* function calls *activity* functions, and the framework checkpoints state (event sourcing in storage) so it can sleep for days and replay deterministically.

| Pattern | Example |
|---|---|
| Function chaining | Validate → charge payment → reserve stock → email |
| Fan-out / fan-in | Resize 500 product images in parallel, then aggregate |
| Async HTTP API | Start long job, return 202 + status URL |
| Human interaction | Wait for manager approval event with a timeout |
| Monitor | Poll an external system until a condition |

```csharp
[Function(nameof(OrderOrchestrator))]
public static async Task<string> OrderOrchestrator(
    [OrchestrationTrigger] TaskOrchestrationContext ctx)
{
    var order = ctx.GetInput<OrderMessage>()!;
    await ctx.CallActivityAsync("ChargePayment", order);
    await ctx.CallActivityAsync("ReserveStock", order);
    return "Completed";            // orchestrator code must be deterministic: no DateTime.Now,
}                                  // no Guid.NewGuid(), no direct I/O - use ctx.CurrentUtcDateTime
```

:::q Consumption vs Premium vs Flex Consumption?
Consumption is pay-per-execution with scale-to-zero but has cold starts and no VNet. Premium keeps pre-warmed always-on instances, supports VNet and long runs, but you pay a baseline. Flex Consumption is the newer serverless plan: scale to zero, VNet integration, fast per-function scaling and optional always-ready instances. For new work I start with Flex unless I need Premium's guarantees.
:::

:::q Why must orchestrator functions be deterministic?
Durable orchestrators are replayed from history every time they resume. If the code yields different results on replay (current time, random, network calls), the replay diverges from the recorded history and fails. Non-deterministic work goes into activities, and time comes from `context.CurrentUtcDateTime`.
:::

### Container Apps vs AKS vs App Service

**Azure Container Apps (ACA)** is serverless containers on a managed Kubernetes you never see. You define *environments*, *apps* with *revisions*, ingress, secrets and scale rules. Scaling uses **KEDA**, so you can scale on HTTP concurrency *or* on queue length, Service Bus messages, Kafka lag, cron, and **scale to zero**. Optional **Dapr** sidecars give service invocation, pub/sub, state stores and secrets across languages. *Jobs* run batch containers.

```bash
az containerapp env create -n cae-shop -g rg-shop --location westeurope
az containerapp create -n orders-api -g rg-shop --environment cae-shop \
   --image acrshop.azurecr.io/orders-api:1.4.2 --target-port 8080 --ingress external \
   --registry-server acrshop.azurecr.io --registry-identity system \
   --min-replicas 0 --max-replicas 10 \
   --scale-rule-name http --scale-rule-type http --scale-rule-http-concurrency 50
```

| | App Service | Container Apps | AKS | Functions |
|---|---|---|---|---|
| Unit | Web app (code or container) | Container | Pod (any K8s object) | Function |
| Ops effort | Lowest | Low | **High** | Lowest |
| Scale to zero | No | **Yes** | Via KEDA add-on, nodes remain | Yes (Consumption/Flex) |
| Event-driven scaling | Rule-based | **KEDA built in** | Install KEDA | Native |
| Kubernetes API access | No | No | **Full** | No |
| Microservices/sidecars | Weak | Good (+Dapr) | Best (service mesh, operators) | Weak |
| Custom networking, GPUs, daemonsets | Limited | Limited | **Full** | No |
| Typical pick | Monolith / simple API + SPA | Microservices without K8s expertise | Large platform teams, portability | Event glue, jobs |

:::tip Decision rule to say aloud
"Start with App Service. Move to Container Apps when I have several containerised services or need scale-to-zero and event-driven scaling. Choose AKS only when I need Kubernetes APIs, custom operators, service mesh or fine-grained control and have a team to run it."
:::

## Azure Storage

### Blob Storage

**Definition.** Massively scalable object store for unstructured data: images, PDFs, backups, logs, static website assets. Hierarchy: *storage account → container → blob*. Blob types: **block** (files; default), **append** (logs) and **page** (VM disks).

**Redundancy.** LRS (3 copies in one datacenter), ZRS (3 zones), GRS/RA-GRS (async copy to paired region; RA = readable), GZRS/RA-GZRS (zones + geo). Pick ZRS or GZRS for production.

#### Access tiers

| Tier | Use | Storage cost | Access cost | Min retention |
|---|---|---|---|---|
| Hot | Frequently used (product images) | Highest | Lowest | None |
| Cool | Infrequent (last year's invoices) | Lower | Higher | 30 days |
| Cold | Rare (compliance copies) | Lower still | Higher | 90 days |
| Archive | Offline backups | Lowest | **Rehydrate** takes hours (standard) | 180 days |

Deleting or moving a blob before the minimum retention triggers an **early deletion fee**. Archive blobs cannot be read until rehydrated to hot/cool. Automate with a **lifecycle management policy** (e.g., move to cool after 30 days since last modified, delete after 365).

#### Authorising access: keys vs SAS vs managed identity

| Method | How | Risk | Verdict |
|---|---|---|---|
| **Account key** | Shared secret, full control | Leaks = total compromise; cannot be scoped | Avoid; disable shared-key access |
| **SAS token** | Signed URL with permissions + expiry (service, account, or **user delegation**) | Anyone with the URL has access until expiry | Use short-lived, for handing a *browser* direct upload/download |
| **Managed identity + RBAC** | Entra token; role such as `Storage Blob Data Contributor` | None to store; audited | **Default for server-side code** |

A **user delegation SAS** is signed with an Entra-issued key rather than the account key, so it can be revoked and audited — prefer it over account-key SAS.

```csharp
using Azure.Identity;
using Azure.Storage.Blobs;
using Azure.Storage.Blobs.Models;
using Azure.Storage.Sas;

var service = new BlobServiceClient(
    new Uri("https://shopstore.blob.core.windows.net"),
    new DefaultAzureCredential());                    // MI in Azure, az login locally

var container = service.GetBlobContainerClient("invoices");
await container.CreateIfNotExistsAsync(PublicAccessType.None);

// Upload (streams, chunks big files automatically)
var blob = container.GetBlobClient($"2026/{orderId}.pdf");
await using (var fs = File.OpenRead(path))
{
    await blob.UploadAsync(fs, new BlobUploadOptions
    {
        HttpHeaders = new BlobHttpHeaders { ContentType = "application/pdf" },
        AccessTier = AccessTier.Cool,
        Metadata = new Dictionary<string, string> { ["orderId"] = orderId.ToString() }
    });
}

// Download as a stream (do not buffer big blobs in memory)
BlobDownloadStreamingResult dl = await blob.DownloadStreamingAsync();
await dl.Content.CopyToAsync(Response.Body);

// Short-lived read-only SAS for the browser (user delegation, no account key)
var key = await service.GetUserDelegationKeyAsync(
    DateTimeOffset.UtcNow, DateTimeOffset.UtcNow.AddMinutes(15));
var sas = new BlobSasBuilder(BlobSasPermissions.Read, DateTimeOffset.UtcNow.AddMinutes(10))
{
    BlobContainerName = container.Name, BlobName = blob.Name, Resource = "b"
};
var uri = new BlobUriBuilder(blob.Uri)
{
    Sas = sas.ToSasQueryParameters(key.Value, service.AccountName)
}.ToUri();                                            // give this to the Angular/React client
```

DI registration: `builder.Services.AddAzureClients(c => { c.AddBlobServiceClient(new Uri(url)); c.UseCredential(new DefaultAzureCredential()); });` (package `Microsoft.Extensions.Azure`).

**SPA hosting.** The `$web` container with *static website* enabled can serve an Angular/React build for pennies; put Front Door or CDN in front for custom domain, HTTPS and caching, and set CORS on the API.

:::example Real-world example
Order PDFs are written to a `Cool` tier container by the API (managed identity). A lifecycle rule archives anything older than 1 year. When a customer clicks "Download invoice", the API returns a 10-minute user delegation SAS URL so the file streams from Storage, not through the API.
:::

:::warn Gotchas
- Creating `new BlobServiceClient` per request wastes sockets; register it as a singleton.
- Public blob access can be disabled at account level — do it.
- A container-level "Reader" role does not allow listing at account level; scope RBAC deliberately.
- Archive tier: reading requires hours of rehydration — never put user-facing files there.
:::

### Queue Storage vs Service Bus

**Queue Storage** is a very simple, cheap queue inside a storage account (messages up to 64 KB, at-least-once, ~7-day default TTL, no ordering guarantee, no topics). **Service Bus** is an enterprise message broker.

| Feature | Queue Storage | Service Bus (queues/topics) |
|---|---|---|
| Message size | 64 KB | 256 KB standard, up to 100 MB premium |
| Ordering / FIFO | No guarantee | **Sessions** give FIFO |
| Pub/sub | No | **Topics + subscriptions + filters** |
| Dead-letter queue | Poison queue (manual) | **Built-in DLQ** |
| Duplicate detection | No | Yes |
| Transactions, scheduled delivery | No | Yes |
| Delivery | At-least-once (visibility timeout) | At-least-once or at-most-once, peek-lock |
| Capacity | 500 TB (account limit) | 1-80 GB per entity (Premium bigger) |
| Cost | Very low | Higher; Standard/Premium tiers |
| Pick for | Simple background work, decoupling | Orders, payments, ordered workflows, fan-out |

Rule: if you need topics, sessions, dead-lettering or exactly-once-ish semantics (duplicate detection + idempotent consumers) choose Service Bus; otherwise Queue Storage is fine and far cheaper. For event streaming at scale use **Event Hubs**; for reacting to Azure resource events use **Event Grid**.

```csharp
await using var client = new ServiceBusClient("sb-shop.servicebus.windows.net",
                                              new DefaultAzureCredential());
ServiceBusSender sender = client.CreateSender("orders");
await sender.SendMessageAsync(new ServiceBusMessage(BinaryData.FromObjectAsJson(order))
{
    MessageId = order.Id.ToString(),        // duplicate detection key
    SessionId = order.CustomerId            // FIFO per customer
});
```

### Table Storage and Azure Files

**Table Storage.** Cheap NoSQL key/attribute store. Each entity has `PartitionKey` + `RowKey` (together the primary key). Point lookups and partition scans are fast; there are no joins, secondary indexes or rich queries. Use it for audit logs, device telemetry, lookups. If you need global distribution, indexing and SLA-backed latency, use Cosmos DB for Table or Cosmos NoSQL.

```csharp
var table = new TableClient(new Uri("https://shopstore.table.core.windows.net"),
                            "AuditLog", new DefaultAzureCredential());
await table.AddEntityAsync(new TableEntity("order-1001", Guid.NewGuid().ToString())
{ ["Action"] = "Shipped", ["By"] = "alice" });
```

**Azure Files.** Managed SMB (and NFS) file shares. Use for lift-and-shift apps that expect a drive letter, shared config between VMs, or persistent volumes in AKS/Container Apps. Premium shares use SSD. **Azure File Sync** caches a share on on-prem Windows Servers.

| Need | Pick |
|---|---|
| Images, PDFs, backups, SPA files | Blob |
| Simple async work queue | Queue Storage |
| Cheap key/value audit data | Table |
| Shared network drive | Files |

