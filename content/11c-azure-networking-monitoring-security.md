## Azure Networking

### Virtual Network, Subnets, NSG and Private Endpoints

**Definition.** A **Virtual Network (VNet)** is your private, isolated address space in a region (for example `10.10.0.0/16`) divided into **subnets**. Resources inside talk over private IPs. **Network Security Groups (NSGs)** are stateful allow/deny firewalls attached to subnets or NICs. A **private endpoint** gives a PaaS resource (SQL, Storage, Key Vault) a private IP inside your subnet.

**Why it matters.** The default for PaaS is a public endpoint protected only by firewall rules and credentials. Production designs move data services to private IPs so they are unreachable from the internet at all.

```text
VNet 10.10.0.0/16
 |- snet-appgw    10.10.0.0/24   Application Gateway / WAF
 |- snet-app      10.10.1.0/24   App Service VNet integration (outbound), AKS nodes
 |- snet-data     10.10.2.0/24   Private endpoints: SQL, Storage, Key Vault, Redis
 |- AzureBastionSubnet 10.10.3.0/26   Bastion (RDP/SSH without public IPs)
```

| Concept | Key facts |
|---|---|
| **NSG rules** | Priority 100-4096 (lower wins), 5-tuple match (source, port, destination, port, protocol), **service tags** (`Internet`, `VirtualNetwork`, `Sql`, `Storage`). Defaults: allow VNet-to-VNet, allow outbound to Internet, deny all other inbound |
| **VNet peering** | Connects VNets (same or different region) over the Microsoft backbone; **not transitive** |
| **Service endpoint** | Subnet gets an optimised route to a PaaS service; the service keeps its *public* IP. Cheap, but weaker isolation |
| **Private endpoint (Private Link)** | PaaS gets a *private* IP in your subnet; you can disable public access entirely. Requires **private DNS zone** (e.g., `privatelink.database.windows.net`) so the normal hostname resolves to the private IP |
| **App Service VNet integration** | Gives the app *outbound* access into the VNet. Inbound private access to App Service needs a private endpoint on the app |
| **UDR / Azure Firewall / NAT Gateway** | Force traffic through an inspection point; NAT Gateway gives a fixed outbound IP and avoids SNAT exhaustion |

```bash
# Private endpoint for Azure SQL, plus DNS so sql-shop.database.windows.net -> 10.10.2.x
az network private-endpoint create -g rg-shop -n pe-sql --vnet-name vnet-shop \
   --subnet snet-data --private-connection-resource-id $SQL_ID \
   --group-id sqlServer --connection-name sql-conn
az network private-dns zone create -g rg-shop -n privatelink.database.windows.net
az network private-dns link vnet create -g rg-shop -z privatelink.database.windows.net \
   -n link-shop -v vnet-shop -e false
az network private-endpoint dns-zone-group create -g rg-shop --endpoint-name pe-sql \
   -n default --private-dns-zone privatelink.database.windows.net --zone-name sql
az sql server update -g rg-shop -n sql-shop --enable-public-network false
```

:::warn Gotcha
The #1 private-endpoint failure is DNS. If the name still resolves to the public IP, the app is blocked once public access is disabled. Test with `nslookup` from inside the VNet and check the private DNS zone is linked to that VNet.
:::

### Load Balancer vs Application Gateway vs Front Door vs Traffic Manager

| | Load Balancer | Application Gateway | Front Door | Traffic Manager |
|---|---|---|---|---|
| OSI layer | **L4** (TCP/UDP) | **L7** (HTTP/S) | **L7**, global | **DNS** |
| Scope | Regional (cross-region SKU exists) | Regional | **Global** (anycast edge) | Global |
| Routing | 5-tuple hash | URL path, host header, cookie affinity | Path, host, latency, priority, weighted | Priority, weighted, performance, geographic |
| TLS termination | No (pass-through) | **Yes** | **Yes** | No (DNS only) |
| WAF | No | **Yes (WAF v2)** | **Yes** (Premium: managed rule sets, bot) | No |
| Caching / CDN | No | No | **Yes** | No |
| Health probes | TCP/HTTP | HTTP/S | HTTP/S | HTTP/S/TCP (probe from DNS side) |
| Failover speed | Seconds | Seconds | Seconds | Slow: bound by **DNS TTL** and client caches |
| Typical use | VM/AKS TCP traffic, internal LB | Single-region web apps, AKS ingress, WAF | Global SPA + API, multi-region failover, edge acceleration | Non-HTTP multi-region routing, simple DNS failover |

Notes: Basic SKU Load Balancer has been retired — use **Standard** (zone-redundant). Application Gateway **v1 is retired** — use v2. **Application Gateway for Containers** is the newer AKS-native L7 option. Verify retirement dates in the docs.

:::tip Say this
"Load Balancer works at layer 4 inside a region. Application Gateway is a regional layer-7 gateway with WAF and path routing. Front Door is the global layer-7 entry point with edge caching and WAF. Traffic Manager only answers DNS queries, so it never sees the traffic and fails over as fast as the DNS TTL allows. For an SPA plus API in two regions I use Front Door in front of two regional Application Gateways or App Services."
:::

### Azure API Management (APIM)

**Definition.** A managed API gateway + developer portal. It sits in front of your backends (App Service, Functions, AKS, even on-prem) and applies cross-cutting concerns *outside* the code: authentication, throttling, caching, transformation, versioning, analytics.

**Key concepts.** *API* (operations imported from OpenAPI), *Product* (a bundle of APIs with terms), *Subscription* (key pair issued per consumer), *Named values* (config/secrets, can reference Key Vault), *Revisions/Versions*, and **policies** — XML pipelines in four sections: `inbound`, `backend`, `outbound`, `on-error`. Tiers: Consumption (serverless, pay per call), Developer (non-prod), Basic/Standard/Premium (multi-region, VNet, self-hosted gateway) and v2 tiers; verify current tier features.

```xml
<policies>
  <inbound>
    <base />
    <!-- 1. Validate the Entra ID access token before hitting the backend -->
    <validate-jwt header-name="Authorization" failed-validation-httpcode="401"
                  failed-validation-error-message="Unauthorized">
      <openid-config url="https://login.microsoftonline.com/{tenant-id}/v2.0/.well-known/openid-configuration" />
      <audiences><audience>api://shop-api</audience></audiences>
      <required-claims>
        <claim name="roles" match="any"><value>Orders.Read</value></claim>
      </required-claims>
    </validate-jwt>
    <!-- 2. Throttle per subscription (or caller IP when none) -->
    <rate-limit-by-key calls="100" renewal-period="60"
        counter-key="@(context.Subscription?.Id ?? context.Request.IpAddress)" />
    <!-- 3. Serve cached GETs -->
    <cache-lookup vary-by-developer="false" vary-by-developer-groups="false"
                  downstream-caching-type="none" />
    <!-- 4. Hide the real backend and add a correlation id -->
    <set-header name="X-Correlation-Id" exists-action="skip">
      <value>@(Guid.NewGuid().ToString())</value>
    </set-header>
    <set-backend-service base-url="https://shop-api-prod.azurewebsites.net" />
  </inbound>
  <backend><base /></backend>
  <outbound>
    <base />
    <cache-store duration="60" />
    <set-header name="X-Powered-By" exists-action="delete" />
  </outbound>
  <on-error><base /></on-error>
</policies>
```

| Policy | Purpose |
|---|---|
| `rate-limit` / `rate-limit-by-key` | Short-window throttling; `quota-by-key` for long-window (monthly) quotas |
| `validate-jwt` | Verify signature, issuer, audience, claims |
| `cache-lookup` / `cache-store` | Built-in response cache (or external Redis) |
| `set-header`, `rewrite-uri`, `set-body` | Transform requests/responses |
| `validate-content` | Reject requests that do not match the OpenAPI schema |
| `retry`, `forward-request` | Resilience to backends |

:::warn Gotchas
- APIM is an extra hop and a cost centre (Developer/Premium are expensive); do not add it for a single internal API.
- Lock the backend so only APIM can call it (IP restriction, VNet, or validate a header/JWT); otherwise attackers bypass the gateway.
- `rate-limit` is per gateway node approximately; use `rate-limit-by-key` and test the numbers.
:::

### Content Delivery (CDN)

**Definition.** A CDN caches static content (JS/CSS bundles, images, fonts, downloads) at edge locations close to users, cutting latency and origin load. Azure's recommended offering is **Azure Front Door Standard/Premium**, which merges CDN, global load balancing and WAF; legacy Azure CDN SKUs (including Edgio) are retired or being retired — verify current status.

**For a .NET + SPA app.** Put the SPA build in Blob static website or App Service, front it with Front Door/CDN. Use **content-hashed file names** (Angular/React builds do this: `main.3f9a1c.js`) with `Cache-Control: public, max-age=31536000, immutable`, but serve `index.html` with `no-cache` so a new deploy is seen immediately. Purge the CDN only for files that are not versioned.

:::q When would you choose Application Gateway over Front Door?
Application Gateway is regional and can sit inside my VNet in front of private backends such as AKS or internal App Services, with WAF and path routing. Front Door is global edge: it accelerates and fails over across regions and caches content. In multi-region designs I often use both — Front Door at the edge, Application Gateway per region.
:::

## Azure Monitoring

### Azure Monitor, Log Analytics and Application Insights

**Azure Monitor** is the umbrella platform. It collects two data kinds: **metrics** (numeric time-series, near real time, ~93 days) and **logs** (rich records in **Log Analytics workspaces**, queried with KQL). Around them: alerts and action groups, autoscale, workbooks/dashboards, diagnostic settings, and *Insights* experiences (Application Insights, Container Insights, VM Insights).

| Piece | What it is |
|---|---|
| **Log Analytics workspace** | Storage + query engine for logs; tables like `AppRequests`, `AzureDiagnostics`, `ContainerLogV2`; retention configurable (30 days interactive by default; up to years in long-term) |
| **Application Insights** | APM for your *code*: requests, dependencies, exceptions, traces, custom events/metrics. Workspace-based: data lives in Log Analytics |
| **Diagnostic settings** | Route a resource's platform logs/metrics (App Service HTTP logs, SQL audit, Key Vault access) to Log Analytics, Storage or Event Hubs |
| **Activity Log** | Control-plane audit: who created/deleted/changed what |
| **Alerts** | Metric, log-query or activity-log rules → **action group** (email, SMS, webhook, Function, Logic App, ITSM) |

#### Application Insights in ASP.NET Core

Two supported ways. For new projects, use the **Azure Monitor OpenTelemetry distro**. The classic SDK (`AddApplicationInsightsTelemetry`) still works and is common in existing code. Use a **connection string** (instrumentation-key-only ingestion is retired).

```csharp
// Option A - OpenTelemetry distro (recommended for new apps)
// dotnet add package Azure.Monitor.OpenTelemetry.AspNetCore
using Azure.Monitor.OpenTelemetry.AspNetCore;
using OpenTelemetry.Metrics;
using OpenTelemetry.Trace;

builder.Services.AddOpenTelemetry()
    .UseAzureMonitor()                       // reads APPLICATIONINSIGHTS_CONNECTION_STRING
    .WithTracing(t => t.AddSource(Telemetry.SourceName))      // custom spans
    .WithMetrics(m => m.AddMeter(Telemetry.MeterName));       // custom metrics

// Option B - classic SDK (Microsoft.ApplicationInsights.AspNetCore)
builder.Services.AddApplicationInsightsTelemetry();   // connection string from config/env
```

```csharp
// Custom telemetry with the OpenTelemetry / .NET APIs
public static class Telemetry
{
    public const string SourceName = "Shop.Orders";
    public const string MeterName  = "Shop.Orders";
    public static readonly ActivitySource Source = new(SourceName);
    static readonly Meter Meter = new(MeterName);
    public static readonly Counter<long> OrdersPlaced =
        Meter.CreateCounter<long>("orders.placed");
}

using var span = Telemetry.Source.StartActivity("PlaceOrder");
span?.SetTag("order.id", order.Id);
Telemetry.OrdersPlaced.Add(1, new KeyValuePair<string, object?>("channel", "web"));

// Classic SDK equivalent
telemetryClient.TrackEvent("OrderPlaced", new Dictionary<string, string> { ["Channel"] = "web" });
telemetryClient.GetMetric("OrderValue").TrackValue(order.Total);
```

Set a **cloud role name** (`OTEL_SERVICE_NAME=orders-api` or `ConfigureResource`) so each service appears separately on the Application Map. `ILogger` output flows automatically as `traces`; unhandled exceptions as `exceptions`; `HttpClient`/SQL/Azure SDK calls as `dependencies`; W3C `traceparent` stitches a request across services (distributed tracing).

**Features to name.** Live Metrics, Application Map, Transaction Search / end-to-end transaction, Failures and Performance blades, Smart Detection, **Availability tests** (Standard tests ping a URL from multiple regions with SSL/content checks and alert on failure; custom `TrackAvailability` for scripted checks — classic URL ping tests are retired), Profiler and Snapshot Debugger.

**Cost control.** You pay per GB ingested. Use sampling (fixed-rate in the distro; adaptive in the classic SDK), filter noisy health-check requests, set a daily cap and review the biggest tables.

#### KQL basics

KQL reads left to right as a pipeline: table → filters → shaping → aggregation.

```kusto
// Slowest operations in the last hour
requests
| where timestamp > ago(1h)
| summarize count(), avg(duration), p95 = percentile(duration, 95) by name
| order by p95 desc
| take 10

// Failure rate per 5 minutes (render as a chart)
requests
| where timestamp > ago(24h)
| summarize total = count(), failed = countif(success == false) by bin(timestamp, 5m)
| extend failureRate = 100.0 * failed / total
| render timechart

// Which dependency is failing?
dependencies
| where timestamp > ago(1h) and success == false
| summarize count() by target, type, resultCode
| order by count_ desc

// Exceptions grouped by type
exceptions
| where timestamp > ago(1d)
| summarize count() by type, outerMessage
| top 10 by count_

// Follow one request end to end
union requests, dependencies, traces, exceptions
| where operation_Id == "<operation id from a failed request>"
| order by timestamp asc
| project timestamp, itemType, name, message, duration, success
```

In a *workspace-based* resource the same data is in tables `AppRequests`, `AppDependencies`, `AppExceptions`, `AppTraces` with PascalCase columns (`TimeGenerated`, `DurationMs`, `Success`).

:::example Real-world example
Users report "checkout is slow". In App Insights: Performance blade shows `POST /api/orders` p95 = 4.8 s; the end-to-end transaction view shows 4.2 s inside one SQL dependency call. KQL on `dependencies` confirms a missing index on `Orders.CustomerId`. Fix, deploy via slot, create an alert on `requests | where name == "POST /api/orders" and duration > 2000` so it never regresses silently.
:::

:::q What is the difference between Azure Monitor, Application Insights and Log Analytics?
Azure Monitor is the platform for metrics, logs, alerts and autoscale. Log Analytics is the workspace where log data is stored and queried with KQL. Application Insights is the application-performance-monitoring feature that collects telemetry from my code (requests, dependencies, exceptions) and stores it in a Log Analytics workspace.
:::

:::q Metrics vs logs in Azure Monitor?
Metrics are lightweight numeric time-series (CPU %, request count) available in near real time, ideal for fast alerts and autoscale. Logs are richer, schema-based records queried with KQL — good for investigation, correlation and custom analytics, with a bit more latency and cost per GB.
:::

## Azure Security

### Azure Key Vault

**Definition.** A managed store for **secrets** (connection strings, API keys), **keys** (RSA/EC, HSM-backed in Premium/Managed HSM) and **certificates** (with auto-renewal).

**Why it matters.** Secrets stay out of source control, config files and pipelines; access is centrally controlled, versioned and audited.

| Topic | Guidance |
|---|---|
| Permission model | Use **Azure RBAC** (roles `Key Vault Secrets User`, `Secrets Officer`, `Crypto User`, `Certificates Officer`, `Administrator`). Legacy access policies still exist but RBAC is recommended |
| Protection | **Soft delete** (on by default) + **purge protection** (turn on for production) |
| Network | Firewall + private endpoint; disable public access |
| Rotation | New *version* per rotation; apps reading "latest" pick it up |
| Cost/limits | Priced per operation; requests are throttled — cache secrets, do not call per request |

```csharp
// dotnet add package Azure.Extensions.AspNetCore.Configuration.Secrets
// dotnet add package Azure.Identity
builder.Configuration.AddAzureKeyVault(
    new Uri("https://kv-shop-prod.vault.azure.net/"),
    new DefaultAzureCredential(),
    new AzureKeyVaultConfigurationOptions { ReloadInterval = TimeSpan.FromMinutes(30) });

// Secret named  ConnectionStrings--Default  becomes  ConnectionStrings:Default
// (Key Vault names cannot contain ':' so '--' is the separator.)
var cs = builder.Configuration.GetConnectionString("Default");
```

**Alternative with zero code: Key Vault references** in App Service/Functions app settings:

```text
ConnectionStrings__Default = @Microsoft.KeyVault(SecretUri=https://kv-shop-prod.vault.azure.net/secrets/SqlConn/)
Jwt__SigningKey            = @Microsoft.KeyVault(VaultName=kv-shop-prod;SecretName=JwtKey)
```

The app's managed identity needs `Key Vault Secrets User` on the vault. The portal shows a green check when the reference resolves. A reference without a version refreshes periodically (about daily) — verify timing in the docs; restart to force it.

```bash
az keyvault create -n kv-shop-prod -g rg-shop --enable-rbac-authorization true \
   --enable-purge-protection true
az role assignment create --assignee-object-id $PRINCIPAL_ID \
   --assignee-principal-type ServicePrincipal \
   --role "Key Vault Secrets User" --scope $KV_ID
```

:::warn Gotchas
- Key Vault Reference showing "Not resolved": usually missing role assignment, a firewall/private-endpoint DNS issue, or a wrong secret name.
- Do not log secrets or put them in pipeline variables as plain text. In Azure Pipelines use a Key Vault task or secret variables.
- `AddAzureKeyVault` loads at startup. Without `ReloadInterval`, a rotated value needs an app restart.
:::

### Managed Identity and DefaultAzureCredential

**Definition.** A **managed identity** is an Entra ID service principal whose credentials are created and rotated by Azure and available only to the resource it is attached to. The app asks the local identity endpoint for a token — no password, key or certificate in your code.

| | System-assigned | User-assigned |
|---|---|---|
| Lifecycle | Tied to one resource; deleted with it | Standalone resource; reusable |
| Sharing | One resource only | Attach to many resources |
| Role assignments | Re-do on every re-create | Pre-assign once; survives redeploys |
| Choose when | Simple, single app | Many apps need the same access, blue/green, pipelines that recreate resources, or you must grant access *before* the app exists |

**DefaultAzureCredential** is a *chain* that tries credentials in order until one works, so the same code runs locally and in Azure. The order (verify the current list in the docs) is approximately: Environment variables (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`) → Workload Identity (AKS) → **Managed Identity** → Visual Studio → VS Code → **Azure CLI** → Azure PowerShell → Azure Developer CLI → (interactive browser, off by default).

```csharp
// System-assigned: no config needed
var cred = new DefaultAzureCredential();

// User-assigned: tell it which identity
var cred2 = new DefaultAzureCredential(new DefaultAzureCredentialOptions
{
    ManagedIdentityClientId = "11111111-2222-3333-4444-555555555555"
});

// Production hardening: avoid probing the whole chain
TokenCredential prod = builder.Environment.IsProduction()
    ? new ManagedIdentityCredential()           // or new ChainedTokenCredential(...)
    : new DefaultAzureCredential();
```

:::warn Gotchas
- Locally, `DefaultAzureCredential` uses *your* user. Passing locally but "403" in Azure almost always means the managed identity lacks a role assignment (RBAC changes can take a few minutes to propagate).
- Probing the full chain adds latency on first call and can pick an unexpected credential; in production prefer a specific credential.
- Create **one** credential instance and reuse it; it caches tokens.
:::

:::q System-assigned vs user-assigned managed identity?
System-assigned is created with the resource and dies with it, one-to-one. User-assigned is its own resource that I can attach to several apps and whose role assignments survive redeployments. I use user-assigned when several services share access or when my IaC must grant permissions before the app is created.
:::

### Microsoft Entra ID

**Definition.** Microsoft's cloud identity platform (formerly Azure AD). A **tenant** is a dedicated directory of users, groups and apps. Entra issues tokens using **OAuth 2.0** (authorisation) and **OpenID Connect** (authentication on top of OAuth).

| Term | Meaning |
|---|---|
| **App registration** | The *definition* of your application, stored in its home tenant: client ID, redirect URIs, exposed API scopes, **app roles**, credentials (certs/secrets/federated credentials). Created by the developer |
| **Enterprise application** | The *instance* (service principal) of an app **inside a specific tenant**: who is assigned, consent grants, Conditional Access, sign-in logs. Created automatically on first consent/sign-in |
| **Service principal** | The identity used at runtime. Types: application SP, managed identity, legacy |
| **Scopes (delegated permissions)** | "Act on behalf of a signed-in user" — appear in the `scp` claim |
| **App roles / application permissions** | Granted to an app or to users/groups — appear in the `roles` claim |
| **Single vs multi-tenant** | `signInAudience`: own tenant only vs any org (and personal) accounts |

**Flows to know.**

| Flow | Use | Notes |
|---|---|---|
| **Authorization Code + PKCE** | SPA (Angular/React with MSAL), web apps, mobile — a *user* signs in | Current best practice; implicit flow is legacy |
| **Client credentials** | Daemon / service-to-service, no user | Needs app permission (role); secret, cert or federated credential |
| **On-Behalf-Of (OBO)** | API A calls API B using the user's identity | Token exchange |
| **Device code** | CLI/TV without a browser | |
| **Managed identity** | Azure resource to Azure resource | No secret at all |

```csharp
// ASP.NET Core API protected by Entra ID (Microsoft.Identity.Web)
builder.Services.AddMicrosoftIdentityWebApiAuthentication(builder.Configuration, "AzureAd");

builder.Services.AddAuthorizationBuilder()
    .AddPolicy("OrdersRead", p => p.RequireAssertion(ctx =>
        ctx.User.HasClaim("scp", "Orders.Read") ||          // delegated (user) token
        ctx.User.IsInRole("Orders.Read")));                  // app-role (daemon) token

app.MapGet("/orders", () => Results.Ok()).RequireAuthorization("OrdersRead");
```

```json
"AzureAd": {
  "Instance": "https://login.microsoftonline.com/",
  "TenantId": "<tenant-guid>",
  "ClientId": "<api-app-registration-client-id>",
  "Audience": "api://shop-api"
}
```

The Angular/React SPA uses **MSAL** (`@azure/msal-angular` / `@azure/msal-react`) to run Auth Code + PKCE, request the scope `api://shop-api/Orders.Read` and attach the access token as a bearer header. The API validates signature, `iss`, `aud`, `exp` and the scope/role. Customer-facing identities (consumers) use **Microsoft Entra External ID** (the successor to Azure AD B2C for new projects — verify current guidance).

:::q App registration vs enterprise application?
The app registration is the global definition of the application (client id, redirect URIs, scopes, roles, secrets) and lives in the tenant where it was created. An enterprise application is the service principal that represents that app in a particular tenant, where I assign users, grant consent and apply Conditional Access. A multi-tenant app has one registration but an enterprise app in each customer tenant.
:::

:::q Delegated permissions vs application permissions?
Delegated permissions (scopes) let an app act on behalf of a signed-in user and are limited by what that user can do; the token has an `scp` claim. Application permissions (app roles) let a daemon act as itself with no user; the token has a `roles` claim and usually needs admin consent.
:::

### Azure RBAC, Policy and Defender

**RBAC definition.** A **role assignment** = *who* (user, group, service principal, managed identity) + *role definition* (set of allowed actions) + *scope* (management group, subscription, resource group, resource). Permissions inherit downward and are additive.

| Built-in role | Can do |
|---|---|
| **Owner** | Everything, **including granting access** |
| **Contributor** | Create/manage everything, **cannot assign roles** |
| **Reader** | View only |
| **User Access Administrator** | Manage role assignments only |

**Control plane vs data plane roles.** `Contributor` on a storage account can reconfigure it but cannot read blobs unless it also holds a *data* role such as `Storage Blob Data Reader/Contributor/Owner`. Likewise `Key Vault Secrets User`, `Storage Queue Data Contributor`, `Azure Service Bus Data Sender/Receiver`, `Cosmos DB Built-in Data Contributor` (Cosmos's own role system). Data-plane actions appear as `dataActions` in a role definition.

Best practices: assign to **groups**, not people; assign at the **narrowest scope** that works; use **PIM** (Privileged Identity Management) for just-in-time elevation; prefer built-in roles, custom roles only when needed. Do not confuse **Entra roles** (e.g., Global Administrator, manage the directory) with **Azure RBAC roles** (manage resources).

```bash
az role assignment create --assignee-object-id $PRINCIPAL_ID \
   --assignee-principal-type ServicePrincipal \
   --role "Storage Blob Data Contributor" \
   --scope /subscriptions/$SUB/resourceGroups/rg-shop/providers/Microsoft.Storage/storageAccounts/shopstore
az role assignment list --scope $SCOPE -o table
```

```json
{
  "Name": "Orders Reader Operator",
  "IsCustom": true,
  "Actions": ["Microsoft.Web/sites/read", "Microsoft.Web/sites/restart/action"],
  "NotActions": [],
  "AssignableScopes": ["/subscriptions/00000000-0000-0000-0000-000000000000"]
}
```

**Azure Policy.** Enforces organisational rules on resources at deployment and continuously audits them. Effects: `Audit`, `Deny`, `Modify`, `DeployIfNotExists`. Examples: deny storage accounts that allow public blob access, require tag `CostCenter`, allow only `westeurope`/`northeurope`, require HTTPS on App Services. Group them in **initiatives** and assign at management-group scope. **RBAC says who may act; Policy says what state is allowed.**

**Microsoft Defender for Cloud.** CSPM (secure score, recommendations, compliance dashboards) plus workload protection plans — Defender for App Service, SQL, Storage (malware scanning), Key Vault, Containers/AKS. Mention it as "continuous posture assessment and threat detection"; pair with Microsoft Sentinel (SIEM) when asked about SOC use.

:::q Owner vs Contributor vs Reader?
Owner has full control and can assign roles. Contributor can create and manage all resources but cannot grant access. Reader is read-only. For apps I avoid all three at broad scope and give managed identities narrow data-plane roles such as Storage Blob Data Contributor on one account.
:::

:::q RBAC vs Azure Policy?
RBAC controls *who* can perform which actions at which scope. Policy controls *what resource configurations are allowed or required*, regardless of who deploys them — for example denying public storage accounts. They are complementary.
:::
