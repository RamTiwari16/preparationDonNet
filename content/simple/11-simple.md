### Azure App Service

**In simple words:** App Service is a managed place to host web apps and APIs. You upload your code or a container, and Azure handles the servers, OS updates, HTTPS and scaling. You pay for an *App Service plan* (the computers you rent), and many apps can share one plan. *Deployment slots* let you test a new version and then swap it into production with no downtime.

**Real-life example:** It is like renting a fully serviced office. You bring your team and work; the building handles electricity, security and cleaning.

**Interview question:** How do you deploy to App Service with zero downtime and roll back quickly?

**Simple answer:** I deploy to a staging slot, let it warm up, then swap it with production. The swap just moves traffic to the already-running staging instances, so users see no downtime. To roll back, I swap back. Settings like the environment name are marked as slot settings so they do not move with the swap.

```bash
az webapp deployment slot swap -g rg-shop-prod -n shop-api \
   --slot staging --target-slot production
```

### Azure Virtual Machines and Scale Sets

**In simple words:** A Virtual Machine (VM) is a full computer in Azure. This is *IaaS* (Infrastructure as a Service): you manage the OS, updates, runtime and backups yourself. A *Virtual Machine Scale Set* (VMSS) is a group of identical VMs that can grow or shrink automatically. Use VMs for old apps or software that needs full control of the OS.

**Real-life example:** A VM is like renting an empty apartment. You get the walls and the electricity, but you buy the furniture and fix things yourself.

**Interview question:** What is the difference between an availability set and an availability zone?

**Simple answer:** An availability set spreads VMs across different racks and update groups inside one datacenter, protecting against hardware and maintenance failures. Availability zones are separate datacenters in one region, so they survive a whole datacenter failure. I prefer zones when the region supports them. Also, a VM must be *deallocated*, not just stopped, to stop compute billing.

### Azure Functions

**In simple words:** Azure Functions is *serverless* computing: you write small pieces of code that run when something happens. That "something" is a *trigger*, like an HTTP call, a timer, a new queue message or a new file. *Bindings* let you read or write other services with very little code. You can pay only when the code runs.

**Real-life example:** It is like a motion-sensor light. It turns on only when someone walks in, and you pay only for the time it is on.

**Interview question:** What are the differences between the Consumption, Flex Consumption and Premium plans?

**Simple answer:** Consumption scales to zero and charges per run, but has cold starts and no VNet. Premium keeps warm instances ready and supports VNet and long runs, but you always pay a base cost. Flex Consumption is the newer serverless plan with scale to zero, VNet support and optional always-ready instances. New code should use the isolated worker model.

```csharp
[Function("ProcessOrder")]
public Task Process(
    [QueueTrigger("orders-incoming")] OrderMessage msg)
    => orders.FulfilAsync(msg);
```

### Container Apps vs AKS vs App Service

**In simple words:** All three can run your API, with different levels of control. App Service is the simplest: you deploy a web app. Azure Container Apps runs containers without you managing Kubernetes, and can scale to zero based on HTTP traffic or queue length. AKS (Azure Kubernetes Service) gives you full Kubernetes, with the most control and the most work.

**Real-life example:** App Service is a hotel room. Container Apps is a serviced apartment. AKS is buying a building — you control everything, but you also maintain everything.

**Interview question:** How do you choose between App Service, Container Apps and AKS?

**Simple answer:** I start with App Service for a simple API or website. I move to Container Apps when I have several containerised microservices or need event-driven scaling and scale to zero. I choose AKS only when I need Kubernetes features like custom operators or a service mesh, and have a team to run it.

### Blob Storage

**In simple words:** Blob Storage stores files like images, PDFs, backups and logs. The structure is: storage account, then container, then blob (file). *Access tiers* (Hot, Cool, Cold, Archive) trade storage price against access price. Your server code should use a managed identity to access it, and you can give a browser a short-lived *SAS* link (a signed URL with an expiry).

**Real-life example:** It is like a storage warehouse with shelves (containers) and boxes (blobs). Boxes you rarely need go to the cheaper back room (Archive), but fetching them takes hours.

**Interview question:** How should your app and your users access files in Blob Storage?

**Simple answer:** Server code uses managed identity with an RBAC role like Storage Blob Data Contributor, so there is no secret. For a browser download or upload, the API creates a short-lived user delegation SAS URL. I avoid account keys because if they leak, the whole account is exposed.

```csharp
var service = new BlobServiceClient(
    new Uri("https://shopstore.blob.core.windows.net"),
    new DefaultAzureCredential());
var blob = service.GetBlobContainerClient("invoices").GetBlobClient("1001.pdf");
await blob.UploadAsync(stream);
```

### Queue Storage vs Service Bus

**In simple words:** Both are queues: one part of the system leaves a message and another part processes it later. Queue Storage is very simple and cheap. Service Bus is a full message broker with topics (one message to many subscribers), sessions for ordering (FIFO), a dead-letter queue for failed messages, and duplicate detection.

**Real-life example:** Queue Storage is like a simple suggestion box. Service Bus is like a post office with tracking, priority lanes and a desk for undeliverable letters.

**Interview question:** When would you choose Service Bus over Queue Storage?

**Simple answer:** I use Queue Storage for simple, cheap background work. I choose Service Bus when I need topics for publish/subscribe, guaranteed order with sessions, a built-in dead-letter queue, duplicate detection or transactions — for example, order and payment messages. Both deliver at least once, so my handlers must be safe to run twice.

### Table Storage and Azure Files

**In simple words:** Table Storage is a cheap NoSQL store for simple records. Each record has a `PartitionKey` and `RowKey`, and lookups by these keys are fast, but there are no joins or rich queries. Azure Files gives you managed network file shares (SMB or NFS) that machines can mount like a normal drive.

**Real-life example:** Table Storage is like a big address book sorted by city and name — fast to look up, but you cannot ask complex questions. Azure Files is like a shared office drive everyone can open.

**Interview question:** When would you use Table Storage, and when Azure Files?

**Simple answer:** I use Table Storage for cheap key-value data like audit logs or telemetry. If I need global distribution or indexes, I use Cosmos DB instead. I use Azure Files when an older app expects a shared network drive, or when containers need a shared persistent folder.

### Azure SQL Database

**In simple words:** Azure SQL Database is SQL Server managed by Azure. Azure handles patching, backups and high availability. You choose a *purchasing model*: DTU (a simple bundle) or vCore (choose CPU and memory separately). A *failover group* copies your database to another region and keeps the same connection string after a failover.

**Real-life example:** It is like keeping your money in a bank instead of under your bed. The bank handles security, copies of records and opening hours.

**Interview question:** How does your .NET API connect to Azure SQL without a password?

**Simple answer:** The App Service has a managed identity. I create a database user for it with `FROM EXTERNAL PROVIDER` and give it the minimum roles. The connection string uses `Authentication=Active Directory Default`, so there is no secret to leak. I also enable retry on failure, because Azure SQL can return short temporary errors.

```sql
CREATE USER [shop-api-prod] FROM EXTERNAL PROVIDER;
ALTER ROLE db_datareader ADD MEMBER [shop-api-prod];
ALTER ROLE db_datawriter ADD MEMBER [shop-api-prod];
```

### Azure Cosmos DB

**In simple words:** Cosmos DB is a NoSQL database that stores JSON documents and can copy them to many regions worldwide. The *partition key* decides how data is spread across machines, and it cannot be changed later. Cost is measured in *Request Units* (RUs). It offers five *consistency levels*; Session is the default.

**Real-life example:** The partition key is like how a post office sorts mail by area code. If everyone uses the same area code, one counter is overloaded while the others are idle.

**Interview question:** How do you choose a partition key in Cosmos DB?

**Simple answer:** I pick a property with many different values that appears in my most common queries and spreads writes evenly. For orders, `customerId` is usually good. I avoid keys like `status` or date, because they create a "hot" partition. Since the key cannot change, I plan the access patterns first.

```csharp
await orders.CreateItemAsync(order, new PartitionKey(order.customerId));
var read = await orders.ReadItemAsync<Order>("o-1001", new PartitionKey("c-42"));
```

### Virtual Network, Subnets, NSG and Private Endpoints

**In simple words:** A *Virtual Network* (VNet) is your private network in Azure, split into smaller ranges called *subnets*. A *Network Security Group* (NSG) is a firewall with allow and deny rules. A *private endpoint* gives a service like Azure SQL a private IP inside your VNet, so you can turn off its public internet access completely.

**Real-life example:** A VNet is like a gated housing complex. Subnets are the separate blocks, the NSG is the security guard at each block, and a private endpoint is an inside door so you never need to use the public street.

**Interview question:** After adding a private endpoint, my API cannot reach Azure SQL. What do you check first?

**Simple answer:** I check DNS first. The SQL hostname must resolve to the private `10.x` IP, which needs a private DNS zone like `privatelink.database.windows.net` linked to the VNet. The App Service also needs VNet integration for outbound traffic. Then I check NSG rules.

### Load Balancer vs Application Gateway vs Front Door vs Traffic Manager

**In simple words:** All four spread traffic, at different levels. Load Balancer works at layer 4 (TCP/UDP) inside one region. Application Gateway works at layer 7 (HTTP) in one region and can have a *WAF* (web application firewall). Front Door is a global layer 7 entry point with caching and WAF. Traffic Manager only answers DNS lookups to send users to a region.

**Real-life example:** Traffic Manager is a road sign pointing to the nearest city. Front Door is the international airport. Application Gateway is the city's main reception desk. Load Balancer is the person sending cars to free parking lanes.

**Interview question:** What is the difference between these four load-balancing services?

**Simple answer:** Load Balancer is regional layer 4. Application Gateway is regional layer 7 with path routing and WAF. Front Door is global layer 7 with CDN caching and WAF. Traffic Manager is DNS-only, so failover depends on DNS cache time. For an app in two regions, I use Front Door in front of the regional apps.

### Azure API Management (APIM)

**In simple words:** API Management is a gateway that sits in front of your APIs. It handles common tasks outside your code: checking tokens, rate limiting, caching, changing requests and versioning. These rules are called *policies* and are written in XML. It also gives a developer portal where others can find and test your APIs.

**Real-life example:** It is like the reception desk of a big company. It checks visitor IDs, limits how many people enter per hour and directs them to the right department.

**Interview question:** What does API Management add that your API does not?

**Simple answer:** It adds gateway features without code changes: JWT validation, rate limits, caching, request changes, versions, subscription keys, analytics and a developer portal. I must also lock the backend so only APIM can call it. Otherwise, people could skip the gateway.

### Content Delivery (CDN)

**In simple words:** A *CDN* (Content Delivery Network) keeps copies of static files like JavaScript, CSS and images on servers close to users. This makes pages load faster and reduces load on your server. In Azure, Front Door Standard or Premium is the recommended CDN.

**Real-life example:** A big shop chain keeps popular items in local stores, so customers do not have to travel to the main warehouse.

**Interview question:** How do you cache an Angular or React app on a CDN and still release new versions safely?

**Simple answer:** The build gives files hashed names like `main.3f9a1c.js`, so I can cache them for a long time. I serve `index.html` with `no-cache`, so users get the new file list right after a deploy. Then I only need to purge files that have no version in their name.

### Azure Monitor, Log Analytics and Application Insights

**In simple words:** *Azure Monitor* is the main monitoring platform. It collects *metrics* (numbers over time, like CPU) and *logs* (detailed records). *Log Analytics* is where logs are stored and searched with *KQL* (Kusto Query Language). *Application Insights* collects data from your code: requests, slow calls, errors and traces across services.

**Real-life example:** Azure Monitor is the hospital's monitoring system. Metrics are the heart-rate screen. Logs are the patient's full medical notes. Application Insights is the doctor who studies your app's health in detail.

**Interview question:** What is the difference between Azure Monitor, Log Analytics and Application Insights?

**Simple answer:** Azure Monitor is the overall platform for metrics, logs and alerts. Log Analytics is the workspace where logs are stored and queried with KQL. Application Insights is the performance monitoring part for my code, and it stores its data in Log Analytics. For new ASP.NET Core apps, I use the Azure Monitor OpenTelemetry distro.

```text
requests
| where timestamp > ago(1h)
| summarize count(), p95 = percentile(duration, 95) by name
| order by p95 desc
```

### Azure Key Vault

**In simple words:** Key Vault is a safe place to store secrets (like connection strings), encryption keys and certificates. Secrets stay out of your code and config files. Access is controlled with Azure RBAC and every access is logged. Your app reads secrets using its managed identity.

**Real-life example:** It is like a bank locker. Only people on the approved list can open it, and the bank records every visit.

**Interview question:** How do you read Key Vault secrets in an ASP.NET Core app?

**Simple answer:** I give the app's managed identity the `Key Vault Secrets User` role. Then I either add Key Vault as a configuration source with `AddAzureKeyVault`, or use Key Vault references in App Service settings with no code at all. A secret named `ConnectionStrings--Default` becomes `ConnectionStrings:Default`.

```csharp
builder.Configuration.AddAzureKeyVault(
    new Uri("https://kv-shop-prod.vault.azure.net/"),
    new DefaultAzureCredential());
```

### Managed Identity and DefaultAzureCredential

**In simple words:** A *managed identity* is an identity for your Azure resource, like an App Service. Azure creates and rotates its credentials, so your code has no password. *System-assigned* identities live and die with one resource. *User-assigned* identities are separate and can be shared. `DefaultAzureCredential` tries several login methods in order, so the same code works on your laptop and in Azure.

**Real-life example:** A managed identity is like a staff ID card the company issues and renews for you. You never have to remember a password to enter the building.

**Interview question:** My code works locally but gets 403 in Azure. Why?

**Simple answer:** Locally, `DefaultAzureCredential` uses my own account, which has permissions. In Azure, it uses the app's managed identity, which probably has no role on the resource. I assign the correct data role, like Storage Blob Data Contributor, and wait a few minutes for it to apply.

```csharp
var cred = new DefaultAzureCredential(); // local: az login, Azure: managed identity
var client = new SecretClient(new Uri(vaultUrl), cred);
```

### Microsoft Entra ID

**In simple words:** Microsoft Entra ID (formerly Azure AD) is Microsoft's cloud identity service. It signs in users and apps and gives out tokens using OAuth 2.0 and OpenID Connect. An *app registration* defines your app (client ID, redirect URIs, scopes, roles). An *enterprise application* is that app's instance inside a specific tenant (organisation directory).

**Real-life example:** Entra ID is like a passport office. It checks who you are and gives you a passport (token) that other countries (APIs) trust.

**Interview question:** What is the difference between delegated permissions and application permissions?

**Simple answer:** Delegated permissions (scopes) let an app act for a signed-in user, limited to what that user can do; the token has an `scp` claim. Application permissions (app roles) let a background service act as itself, with no user; the token has a `roles` claim and usually needs admin consent. SPAs use the Authorization Code flow with PKCE.

### Azure RBAC, Policy and Defender

**In simple words:** *RBAC* (role-based access control) decides who can do what, on which scope. A role assignment is: who + role + scope. *Azure Policy* decides which resource settings are allowed, for example "no public storage accounts". *Microsoft Defender for Cloud* checks your security posture and detects threats.

**Real-life example:** RBAC is the list of which employees have keys to which rooms. Policy is the building rules, like "no fire doors may be locked", which apply no matter who does the work.

**Interview question:** What is the difference between Owner, Contributor and Reader, and between RBAC and Policy?

**Simple answer:** Owner can do everything, including giving access. Contributor can manage resources but cannot give access. Reader can only view. RBAC controls who can act, while Policy controls what configurations are allowed. For apps, I give managed identities narrow data roles instead of broad roles like Contributor.

```bash
az role assignment create --assignee-object-id $PRINCIPAL_ID \
   --assignee-principal-type ServicePrincipal \
   --role "Storage Blob Data Contributor" --scope $STORAGE_ID
```

### Typical .NET Three-Tier App on Azure

**In simple words:** A common Azure setup for an Angular or React app with an ASP.NET Core API looks like this. Front Door with WAF is the entry point. The SPA lives in Blob static website hosting. The API runs on App Service with 2 or more instances. Data lives in Azure SQL, Redis and Blob Storage behind private endpoints. Secrets use managed identity and Key Vault, and Application Insights monitors everything.

**Real-life example:** It is like a well-run hotel: a security gate at the entrance (Front Door), a reception desk (API), a locked store room only staff can reach (private data tier) and cameras everywhere (monitoring).

**Interview question:** How would you design a production .NET web app on Azure?

**Simple answer:** I walk the request path: Front Door with WAF, then the SPA from Blob storage and the API on App Service with slots and autoscale. The data tier is Azure SQL with a failover group, behind private endpoints. Background work goes through Service Bus to Functions. I use managed identity, Key Vault, Application Insights and CI/CD with Bicep.
