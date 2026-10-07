## Azure Databases

### Azure SQL Database

**Definition.** Managed SQL Server engine as PaaS: automatic patching, backups, HA, and tuning features. Options: *Azure SQL Database* (single DB / elastic pool), *SQL Managed Instance* (near 100% SQL Server compatibility, VNet-native; for lift-and-shift with SQL Agent, linked servers, cross-DB queries), *SQL Server on VM* (full control).

#### Purchasing models

| | DTU | vCore |
|---|---|---|
| Model | Bundled blend of CPU/IO/memory | Choose vCores, memory and storage independently |
| Tiers | Basic / Standard / Premium | General Purpose / Business Critical / **Hyperscale** |
| Serverless | No | **Yes (GP): auto-scale and auto-pause** — cheap for dev/test |
| Hybrid Benefit / reservations | No | Yes |
| Choose when | Simple, small, predictable | Almost everything new |

**Elastic pool.** Many databases share one pool of resources (eDTUs or vCores). Great for multi-tenant SaaS where tenants peak at different times; wasteful if all databases peak together.

#### Resilience: geo-replication vs failover groups

- **Built-in HA:** local replicas (zone-redundant optionally) give automatic failover inside a region; RPO ~0.
- **Backups:** point-in-time restore (default 7 days, up to 35) plus long-term retention (up to 10 years).
- **Active geo-replication:** up to 4 readable secondaries in other regions, **manual** failover, each DB individually; connection string changes on failover.
- **Auto-failover group:** groups databases, offers automatic or manual failover and two stable listener endpoints — `fg-name.database.windows.net` (read-write) and `fg-name.secondary.database.windows.net` (read-only) — so **the app does not change its connection string**. This is what production apps use.

#### Network and authentication

- **Firewall:** server-level and database-level IP rules. The "Allow Azure services" toggle lets *any* Azure subscription's traffic reach the server's front door — avoid it. Prefer **private endpoints** (private IP in your VNet) and disable public network access.
- **Authentication:** SQL authentication (username/password) vs **Microsoft Entra authentication** (user, group, service principal, managed identity). Set an Entra admin and optionally enable *Entra-only authentication*.

```sql
-- Run as the Entra admin, in the app database. The name is the managed identity's name.
CREATE USER [shop-api-prod] FROM EXTERNAL PROVIDER;
ALTER ROLE db_datareader ADD MEMBER [shop-api-prod];
ALTER ROLE db_datawriter ADD MEMBER [shop-api-prod];
-- DDL migrations should run under a separate, higher-privileged identity (see CI/CD).
```

```csharp
// appsettings: no password anywhere
// "ConnectionStrings:Default":
//  "Server=tcp:sql-shop.database.windows.net,1433;Database=ShopDb;
//   Authentication=Active Directory Default;Encrypt=True;TrustServerCertificate=False"
// Microsoft.Data.SqlClient obtains an Entra token using the same chain as DefaultAzureCredential
// (managed identity in Azure, your az login / Visual Studio account locally).

builder.Services.AddDbContext<ShopDbContext>(o =>
    o.UseSqlServer(builder.Configuration.GetConnectionString("Default"),
        sql => sql.EnableRetryOnFailure(5, TimeSpan.FromSeconds(10), null)));   // transient faults
```

For a *user-assigned* identity use `Authentication=Active Directory Managed Identity;User Id=<client-id>`.

:::warn Gotchas
- Always enable **retry on failure** — Azure SQL throws transient errors (failovers, throttling, error 40613) by design.
- Serverless auto-pause means the first query after idle waits tens of seconds; do not use it for latency-sensitive production APIs.
- Do not scale a DB by "more app instances" if the database is the bottleneck; check DTU/CPU, Query Store and missing indexes first.
:::

:::q How does your .NET API connect to Azure SQL without a password?
The App Service has a system-assigned managed identity. I create a contained database user `FROM EXTERNAL PROVIDER` for that identity, give it the minimum roles, and use `Authentication=Active Directory Default` (or Managed Identity) in the connection string. No secret exists to leak or rotate. Locally, the same connection string uses my `az login` credentials.
:::

:::q Geo-replication vs failover group?
Geo-replication is per-database with manual failover and a changing endpoint. A failover group manages a set of databases together, supports automatic failover and gives read-write and read-only listener endpoints that stay constant, so the application needs no change after a failover.
:::

### Azure Cosmos DB

**Definition.** Globally distributed, multi-model NoSQL database (NoSQL/SQL API, MongoDB, Cassandra, Gremlin, Table) with single-digit-millisecond reads, elastic throughput, and multi-region writes. Account → database → container → items (JSON).

#### Partition key (the most important decision)

Items are placed in **logical partitions** by partition-key value (limit ~20 GB each) and spread across physical partitions. A good key has **high cardinality**, spreads reads/writes evenly, and **appears in your most common queries** so they hit one partition.

| Candidate for Orders | Verdict |
|---|---|
| `/customerId` | Good: "my orders" is the dominant query, high cardinality |
| `/orderId` | Even spread, but "orders per customer" becomes cross-partition |
| `/status` | **Bad**: few values, hot partition |
| `/orderDate` | **Bad**: all today's writes hit one partition |
| Synthetic `/tenantId-month` | Good for multi-tenant time-series |

The key cannot be changed later (you must migrate data). **Hierarchical partition keys** (e.g., tenantId → userId) help with large tenants.

#### Request Units (RUs)

An RU is the normalised cost of an operation (CPU + IO + memory). A point read of a 1 KB item by id + partition key costs **~1 RU**; a write costs several; a cross-partition query costs far more. Capacity models: **provisioned** (manual), **autoscale** (scales between 10% and 100% of max), **serverless** (pay per request; small/dev workloads). Over-limit requests return **HTTP 429**; the SDK retries automatically, but sustained 429s mean you need more RUs or a better partition key.

#### Consistency levels

| Level | Guarantee | Latency / cost | Typical use |
|---|---|---|---|
| **Strong** | Linearizable; always latest committed | Highest latency, single write region (or limits) | Financial ledgers |
| **Bounded staleness** | Reads lag by at most K versions or T time | High | Leaderboards with a known bound |
| **Session** (default) | Read-your-own-writes within a session; monotonic reads | Low | Most apps (a user sees their own order) |
| **Consistent prefix** | Never see out-of-order writes | Low | Social feeds, timelines |
| **Eventual** | No ordering guarantee; fastest | Lowest | Counters, non-critical likes |

```csharp
public record Order(string id, string customerId, decimal total, string status);

var client = new CosmosClient("https://cosmos-shop.documents.azure.com:443/",
    new DefaultAzureCredential(),                 // Entra + Cosmos data-plane RBAC role
    new CosmosClientOptions
    {
        ConnectionMode = ConnectionMode.Direct,
        ApplicationRegion = Regions.WestEurope,
        SerializerOptions = new() { PropertyNamingPolicy = CosmosPropertyNamingPolicy.CamelCase }
    });                                           // singleton for the whole app

Container orders = client.GetContainer("shop", "orders");

await orders.CreateItemAsync(order, new PartitionKey(order.customerId));

// Point read: cheapest operation (~1 RU for 1 KB)
ItemResponse<Order> read = await orders.ReadItemAsync<Order>(
    "o-1001", new PartitionKey("c-42"));
Console.WriteLine($"{read.RequestCharge} RU");

// Single-partition query (partition key supplied)
var q = new QueryDefinition("SELECT * FROM o WHERE o.status = @s").WithParameter("@s", "Paid");
using var it = orders.GetItemQueryIterator<Order>(q,
    requestOptions: new QueryRequestOptions { PartitionKey = new PartitionKey("c-42") });
while (it.HasMoreResults)
    foreach (var o in await it.ReadNextAsync()) Console.WriteLine(o.id);
```

Entra auth for the data plane needs a **Cosmos DB SQL role assignment** (not an ARM RBAC role): `az cosmosdb sql role assignment create --role-definition-id 00000000-0000-0000-0000-000000000002 --principal-id <mi> --scope /` (built-in Data Contributor). Other features: **change feed** (event stream of inserts/updates, consumed by Functions), TTL, multi-region writes, indexing policy (everything indexed by default — exclude large unused paths to cut write RUs). EF Core has a Cosmos provider, but the SDK gives more control.

#### SQL vs Cosmos DB decision

| Need | Azure SQL | Cosmos DB |
|---|---|---|
| Relational integrity, joins, multi-table ACID transactions | **Yes** | Transactions only within one partition |
| Ad-hoc reporting / complex queries | **Yes** | Weak |
| Schema | Rigid, enforced | Flexible JSON |
| Horizontal write scale, global distribution | Limited (Hyperscale, read replicas) | **Native** |
| Predictable single-digit-ms at huge scale | Needs tuning | **Yes** (if keyed well) |
| Cost model | vCores/DTU | RUs (easy to overspend with bad queries) |
| Typical e-commerce use | Orders, payments, inventory (source of truth) | Product catalogue, shopping cart, session/profile, event/telemetry store |

:::example Real-world example
Shop uses Azure SQL for orders and payments (transactions, reporting) and Cosmos DB for the product catalogue (read-heavy, flexible attributes, global reads). The cart lives in Redis. Cosmos change feed triggers a Function that updates the search index.
:::

:::q How do you choose a partition key in Cosmos DB?
I look for a property with high cardinality that appears in the filter of my most frequent queries, and that spreads writes evenly. For orders that is `customerId`. I avoid low-cardinality or monotonically increasing keys like `status` or `date` because they create hot partitions. Because the key cannot be changed, I model access patterns first and use a synthetic or hierarchical key if no single field fits.
:::

:::q What are Cosmos DB consistency levels and which do you default to?
Five levels from strongest to weakest: Strong, Bounded Staleness, Session, Consistent Prefix, Eventual. Session is the default and the sweet spot: a client always sees its own writes with low latency. I only move to Strong for money-critical reads and accept the latency and region constraints.
:::
