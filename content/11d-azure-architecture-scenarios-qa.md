## Azure Reference Architecture

### Typical .NET Three-Tier App on Azure

**Definition.** A production-grade layout for an Angular/React SPA + ASP.NET Core API + SQL database: global edge in front, private data tier, identity without secrets, observability everywhere.

```text
                        Users (browser / mobile)
                                 |
                   Entra ID <----+----> Azure Front Door (WAF, TLS, CDN, global LB)
                 (MSAL sign-in)  |            |                       |
                                 |   static   |                       | /api/*
                                 |            v                       v
                                 |   Blob static website      Application Gateway (WAF v2)
                                 |   ($web, Angular/React)    or direct to App Service
                                 |                                    |
        +------------------------+------------------------------------+------------------+
        |                                  VNet                                          |
        |   snet-app                                  snet-data (private endpoints)      |
        |   +-------------------------------+         +--------------------------------+ |
        |   | App Service (Premium v3, 2+)  |-------->| Azure SQL (failover group)     | |
        |   |  ASP.NET Core API + slots     |-------->| Blob Storage (invoices/images) | |
        |   |  system-assigned MI           |-------->| Key Vault (secrets, certs)     | |
        |   +---------------+---------------+-------->| Azure Cache for Redis          | |
        |                   | enqueue                 | Cosmos DB (catalogue)          | |
        |                   v                         +--------------------------------+ |
        |        Service Bus (orders topic)                                              |
        |                   |                                                            |
        |                   v                                                            |
        |        Azure Functions (Flex) - order processing, emails, nightly jobs         |
        +--------------------------------------------------------------------------------+
                                 |
      App Insights + Log Analytics (traces, metrics, alerts) | Defender | Policy | Cost Mgmt
      Azure DevOps / GitHub Actions -> ACR / package -> slot swap (OIDC, no secrets)
```

| Concern | Choice | Why |
|---|---|---|
| Edge | Front Door + WAF | Global TLS, caching, DDoS and OWASP rules, multi-region failover |
| SPA | Blob static website (or Static Web Apps) | Cheap, CDN-friendly, no server |
| API | App Service Premium v3, 2+ instances, autoscale, slots | Simplest PaaS, zero-downtime swaps |
| Async work | Service Bus + Functions | Decouple spikes, retries, dead-lettering |
| Data | Azure SQL (source of truth), Redis cache, Cosmos (catalogue, optional) | Right store per access pattern |
| Secrets | Managed identity + Key Vault, no passwords in config | Nothing to leak or rotate |
| Network | Private endpoints + VNet integration, public access disabled on data services | Reduces attack surface |
| Observability | App Insights (OpenTelemetry) + alerts + availability tests | Detect before users do |
| Delivery | CI/CD with OIDC federation, IaC (Bicep) | Repeatable, auditable |
| Resilience | Zone-redundant tiers; SQL failover group; Front Door to a second region for DR | Meets the stated RTO/RPO |

:::tip How to present it
Walk the request path left to right (edge → compute → data), then the cross-cutting layers (identity, network, monitoring, delivery). End by stating the non-functional trade-offs: availability target, RTO/RPO, and monthly cost drivers.
:::

## Azure Scenario Questions

:::scenario 1. API latency spikes during a flash sale on App Service
**Symptoms:** p95 jumps from 200 ms to 6 s, CPU 95% on both instances.
**Approach:** Check App Insights Performance and Live Metrics first: is the time in my code, SQL or a dependency? CPU-bound code means scale out (autoscale rule on CPU, raise the max, pre-scale by schedule before known events). If the SQL dependency dominates, scale/tune the database (indexes, Query Store) — adding web instances will make it worse. Confirm the app is stateless (ARR affinity off, no in-memory sessions), cache hot reads in Redis, and move non-urgent work to a Service Bus queue.
**Fix:** schedule-based autoscale for the sale, rule-based as safety net, Redis for catalogue reads, queue for emails/invoices.
:::

:::scenario 2. A developer committed a database password to the repo
**Approach:** Treat it as compromised immediately: **rotate the credential first**, then remove it from history (git filter-repo/BFG) and invalidate cached clones. Move the secret to Key Vault and read it through a Key Vault reference or `AddAzureKeyVault`. Better: switch SQL to **Entra auth with managed identity** so no password exists. Add secret scanning (GitHub secret scanning/push protection or a pipeline scanner) and a pre-commit hook so it cannot recur.
:::

:::scenario 3. After enabling a private endpoint, the API cannot reach Azure SQL
**Approach:** Almost always DNS. From the App Service console (`nameresolver` / Kudu) check that `sql-shop.database.windows.net` resolves to a `10.x` address. If it returns the public IP: the `privatelink.database.windows.net` private DNS zone is missing, not linked to the VNet, or the app has no VNet integration (outbound) / is using custom DNS. Also check NSG/UDR rules and that public access disabled is intended.
:::

:::scenario 4. Deploy with a breaking DB change and zero downtime
**Approach:** Use **expand/contract**. Release 1: add the new nullable column/table (expand), code writes both old and new. Backfill data. Release 2: code reads only the new shape. Release 3: drop the old column (contract). Deploy each release to a staging slot, smoke test, swap. Because the old and new versions both run against one database during the swap, every migration must be backward compatible; the swap-back rollback also stays safe.
:::

:::scenario 5. An Azure Function creates duplicate invoices
**Approach:** Queue and Service Bus triggers are **at-least-once**: a message can be processed twice (timeout, scale-in, retry). Make the handler **idempotent**: use a natural key (OrderId) with a unique constraint or an "already processed" check, or use Service Bus duplicate detection on `MessageId`. Set sensible `maxDequeueCount`/retries, and watch the poison queue or dead-letter queue with an alert. Never rely on "exactly once".
:::

:::scenario 6. Cosmos DB returns 429s and RU cost is huge
**Approach:** Look at *Insights → Throughput → normalised RU consumption by partition key range*. One partition at 100% while others idle = **hot partition** (bad key such as `status` or date). Check `RequestCharge` on slow queries: cross-partition queries and `SELECT *` without a filter on the key are expensive. Fix by choosing a better or synthetic key (requires data migration), adding the partition key to queries, trimming the indexing policy, and using point reads. Only then raise RUs or enable autoscale.
:::

:::scenario 7. The Azure bill doubled this month
**Approach:** Open **Cost Management → Cost analysis**, group by service, resource group and tag. Usual culprits: VMs stopped but not **deallocated**, Premium plans idle, a forgotten AKS/ APIM Developer tier, App Insights/Log Analytics ingestion explosion (verbose logging, no sampling), data egress between regions, orphaned disks/public IPs, Cosmos RU over-provisioning. Fix with budgets and alerts, tags + Policy requiring them, auto-shutdown, reservations/savings plans for steady workloads, and sampling/daily caps.
:::

:::scenario 8. Design multi-region disaster recovery for the API and SQL
**Approach:** Agree RTO and RPO first. Active-passive: Front Door routes to the primary App Service and fails over to the secondary region (health probes, priority routing); Azure SQL **auto-failover group** replicates asynchronously (RPO of seconds) and keeps one connection string; blob data uses GZRS/RA-GZRS; Key Vault and App Config are replicated per region by IaC. Practise the failover with game-days. State the trade-off: active-active is faster but costs more and complicates data consistency.
:::

:::scenario 9. Blob upload works locally but returns 403 in Azure
**Approach:** Locally `DefaultAzureCredential` used *my* identity (with rights). In Azure it uses the app's managed identity, which has no data-plane role. Assign `Storage Blob Data Contributor` to the identity at the storage account/container scope and wait a few minutes for propagation. Also check storage firewall / private endpoint settings and that the code uses the blob URL with the right account.
:::

:::scenario 10. First request after idle is very slow
**Approach:** App Service: enable **Always On**, add a warm-up path/health check, use slots so swaps are pre-warmed, consider ReadyToRun/tiered compilation. Functions: move from Consumption to **Flex/Premium with always-ready instances**. Azure SQL serverless: auto-pause is the cause — disable it or move to provisioned. Check that DI singletons are not doing slow I/O on first use; initialise them at startup.
:::

## Quick-fire Q&A

:::q What is the difference between IaaS, PaaS and SaaS in Azure terms?
IaaS (VMs) — you manage OS and up. PaaS (App Service, Azure SQL, Functions) — Azure manages OS and runtime, you manage app and data. SaaS (Microsoft 365) — you only use it. For most .NET APIs PaaS gives the best ops-to-control ratio.
:::

:::q Resource group, subscription, tenant?
A tenant is the Entra directory; a subscription is a billing and quota boundary tied to one tenant; a resource group is a logical container for resources that share a lifecycle. RBAC, Policy and tags inherit down that hierarchy.
:::

:::q Scale up vs scale out on App Service?
Scale up changes the SKU (bigger VM); scale out adds instances behind the load balancer. Scale out needs a stateless app and gives availability; scale up helps CPU- or memory-bound code. I configure autoscale for scale out.
:::

:::q What are deployment slots good for?
Staging a new version on the same plan, warming it up, then swapping with production for zero downtime and instant rollback by swapping back. Slot-sticky settings keep environment-specific values from moving.
:::

:::q Consumption plan vs Premium plan for Functions?
Consumption scales to zero and bills per execution but has cold starts and limited networking. Premium keeps pre-warmed instances, supports VNet and long executions, at a baseline cost. Flex Consumption is the newer serverless option combining scale-to-zero, VNet and optional always-ready instances.
:::

:::q Queue Storage or Service Bus?
Queue Storage for simple, cheap, high-volume background work. Service Bus when I need topics, FIFO sessions, dead-lettering, duplicate detection, transactions or scheduled delivery.
:::

:::q SAS token vs managed identity for Blob access?
Server-side code should use managed identity with an RBAC role — no secret. SAS tokens are for delegating short-lived access to a client such as the browser; prefer user-delegation SAS with a short expiry over account-key SAS.
:::

:::q DTU vs vCore for Azure SQL?
DTU is a bundled performance unit and is simple; vCore lets me choose compute, memory and storage separately, supports serverless, Hyperscale, reservations and Hybrid Benefit. New workloads normally use vCore.
:::

:::q When do you pick Cosmos DB over SQL?
When I need massive horizontal scale, global distribution, flexible schema and predictable low-latency access by key. For relational integrity, joins and reporting, SQL stays the source of truth.
:::

:::q Application Gateway vs Front Door vs Load Balancer vs Traffic Manager?
Load Balancer is L4 regional; Application Gateway is regional L7 with WAF and path routing; Front Door is global L7 with CDN and WAF; Traffic Manager is DNS-level routing only, so failover depends on DNS TTL.
:::

:::q What does API Management add that your API does not?
Cross-cutting policy at the gateway: JWT validation, rate limiting, caching, transformation, versioning, subscription keys, analytics and a developer portal — without touching backend code.
:::

:::q How do you keep secrets out of an ASP.NET Core app on Azure?
Use managed identity for Azure resources, store remaining secrets in Key Vault and surface them via Key Vault references or the `AddAzureKeyVault` configuration provider, and never commit secrets or put them in plain pipeline variables.
:::

:::q What is DefaultAzureCredential?
A credential chain from `Azure.Identity` that tries environment variables, workload identity, managed identity, then developer tools such as Visual Studio and Azure CLI, so the same code works locally and in Azure. In production I prefer a specific credential to avoid probing the chain.
:::

:::q App Insights: how do you trace one request across services?
Telemetry carries W3C trace context (`traceparent`), so `operation_Id` is shared. I search by that id or use the end-to-end transaction view; `dependencies` show the downstream calls, and each service sets its own cloud role name for the Application Map.
:::

:::q Contributor vs Owner, and what is a data-plane role?
Owner can grant access; Contributor cannot. Data-plane roles (such as Storage Blob Data Reader) control what you can do *with* the data inside a resource, and are separate from control-plane roles that manage the resource itself.
:::
