## Kubernetes Architecture

### What Kubernetes Is and Why It Exists

**Definition.** Kubernetes (K8s) is an open-source **container orchestrator**. You declare the *desired state* ("run 3 replicas of `orders-api:1.4.2`, expose it on `/api`") and Kubernetes continuously works to make the *actual state* match, restarting failed containers, rescheduling them off dead machines, scaling and rolling out updates.

**Why it matters.** Docker runs containers on one machine. Production needs many machines, self-healing, service discovery, rolling updates, secrets, autoscaling and a standard API. Kubernetes provides that and is portable across clouds (**AKS** on Azure).

**Terms.** A **cluster** = control plane + worker **nodes** (VMs). Workloads run as **Pods** on nodes. You interact only with the **API server**, typically through `kubectl` or CI/CD.

### Control Plane and Node Components

```text
                     kubectl / CI-CD / Helm
                              |  (HTTPS, authn/authz)
  +---------------------------v------------------------------+
  |                     CONTROL PLANE                         |
  |  +-------------+   +--------+   +-----------+  +-------+ |
  |  | API server  |<->|  etcd  |   | Scheduler |  |Controller| |
  |  | (front door)|   | (state)|   | (pod->node)| |Manager  | |
  |  +------+------+   +--------+   +-----------+  +-------+ |
  +---------|-------------------------------------------------+
            | watches / reports
  +---------v---------------------------+   +--------------------------+
  | NODE 1                              |   | NODE 2 ...               |
  |  kubelet  (runs/ monitors pods)     |   |  kubelet                 |
  |  kube-proxy (Service networking)    |   |  kube-proxy              |
  |  container runtime (containerd)     |   |  containerd              |
  |  [Pod: api][Pod: api][Pod: redis]   |   |  [Pod: api] [Pod: ...]   |
  +-------------------------------------+   +--------------------------+
```

| Component | Role |
|---|---|
| **kube-apiserver** | The only entry point; validates, authenticates, authorises and persists every request; everything else talks *through* it |
| **etcd** | Consistent key-value store holding all cluster state; back it up; AKS manages it for you |
| **kube-scheduler** | Picks a node for each unscheduled Pod based on requests, affinity, taints/tolerations, topology |
| **kube-controller-manager** | Runs control loops (ReplicaSet, Node, Job, Endpoints controllers) that reconcile actual vs desired state |
| **cloud-controller-manager** | Talks to the cloud API: creates Azure load balancers, routes, disks |
| **kubelet** | Agent on every node; makes sure containers described in Pod specs are running and healthy; runs probes; reports status |
| **kube-proxy** | Programs iptables/IPVS rules so a Service's virtual IP load-balances to Pod IPs |
| **Container runtime** | Actually runs containers via CRI (**containerd**; Docker Engine is no longer used as the runtime) |

**What happens on `kubectl apply -f deployment.yaml`:** kubectl → API server (auth, validation) → stored in etcd → Deployment controller creates a ReplicaSet → ReplicaSet controller creates Pods → scheduler assigns nodes → kubelet pulls the image and starts containers → kube-proxy/endpoints route traffic to ready Pods.

:::tip Interview line
"Kubernetes is a reconciliation engine: controllers watch the API server for desired state and keep nudging the real world towards it. That's why a deleted Pod comes back."
:::

## Core Objects

### Pod

**Definition.** The smallest deployable unit: one or more containers that share a network namespace (one IP, they talk over `localhost`) and can share volumes. Pods are **ephemeral**: when one dies it is replaced by a *new* Pod with a new IP, so you never rely on a Pod IP.

Multi-container patterns: **sidecar** (log shipper, Envoy/Dapr proxy), **init container** (runs to completion first, e.g., wait for DB, run migrations), **ambassador**/adapter. Do not create bare Pods in production; use a controller (Deployment, StatefulSet, Job).

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: orders-api-debug
  labels: { app: orders-api }
spec:
  containers:
  - name: api
    image: acrshop.azurecr.io/shop/orders-api:1.4.2
    ports: [ { containerPort: 8080 } ]
```

### ReplicaSet and Deployment

A **ReplicaSet** keeps N identical Pods running. You rarely create one directly. A **Deployment** manages ReplicaSets and gives you **declarative updates**: change the image and the Deployment creates a new ReplicaSet and shifts Pods over gradually, keeping the old ReplicaSet around for rollback.

**Rolling update parameters:**

| Field | Meaning | Example (replicas: 4) |
|---|---|---|
| `maxSurge` | Extra Pods allowed above desired during update (number or %) | `1` → up to 5 Pods |
| `maxUnavailable` | Pods allowed to be unavailable during update | `0` → always 4 ready (zero-downtime, needs spare capacity) |

```yaml
spec:
  replicas: 4
  strategy:
    type: RollingUpdate            # alternative: Recreate (kill all, then start)
    rollingUpdate: { maxSurge: 1, maxUnavailable: 0 }
  revisionHistoryLimit: 5          # old ReplicaSets kept for rollback
```

A rollout only proceeds when new Pods become **Ready** (readiness probe) — so a broken release stalls instead of taking down the site.

```bash
kubectl set image deployment/orders-api api=acrshop.azurecr.io/shop/orders-api:1.4.3
kubectl rollout status  deployment/orders-api       # watch progress
kubectl rollout history deployment/orders-api
kubectl rollout undo    deployment/orders-api       # back to the previous revision
kubectl rollout undo    deployment/orders-api --to-revision=3
kubectl rollout restart deployment/orders-api       # rolling restart (e.g., pick up new ConfigMap)
```

:::warn Gotcha
`rollout undo` reverts to the previous *pod template*. If you deployed `:latest`, "previous" may pull the same image again. Use immutable tags (`1.4.3`, SHA, digest) so rollbacks are real.
:::

### Services

**Definition.** Pods come and go, so a **Service** gives a set of Pods (selected by labels) a **stable virtual IP and DNS name** and load-balances across the *ready* ones.

| Type | Reachable from | How | Use |
|---|---|---|---|
| **ClusterIP** (default) | Inside the cluster | Virtual IP + DNS `orders-api.shop.svc.cluster.local` | Internal service-to-service calls |
| **NodePort** | Outside, via any node IP | Opens a port 30000-32767 on every node | Dev/test, or behind your own LB |
| **LoadBalancer** | Internet or VNet | Cloud controller provisions an Azure Load Balancer + public (or internal) IP | One service per public IP; TCP/UDP |
| ExternalName | Inside | DNS CNAME to an external host | Alias to Azure SQL, etc. |
| Headless (`clusterIP: None`) | Inside | DNS returns Pod IPs | StatefulSets, client-side balancing |

```yaml
apiVersion: v1
kind: Service
metadata: { name: orders-api, namespace: shop }
spec:
  type: ClusterIP
  selector: { app: orders-api }          # must match Pod labels, or endpoints stay empty
  ports:
  - { name: http, port: 80, targetPort: 8080 }   # Service port -> container port
```

### Ingress and Ingress Controllers

**Definition.** **Ingress** is an API object with layer-7 routing rules (host and path → Service) and TLS settings. It does nothing by itself: an **ingress controller** (NGINX, Traefik, Azure Application Gateway Ingress Controller, Istio gateway, ...) watches Ingress objects and configures a real proxy. One public IP then serves many services, with TLS termination (certificates via **cert-manager** + Let's Encrypt, or Key Vault).

```text
Internet -> Azure LB (1 public IP) -> Ingress controller pods
             /api/*   -> Service orders-api    -> Pods
             /        -> Service web-spa       -> Pods
```

:::warn Currency note
The community **ingress-nginx** project was retired (upstream maintenance ended around March 2026) and Microsoft announced support for the AKS *application routing* managed NGINX only through about November 2026, steering users towards the **Kubernetes Gateway API** (including Istio-based gateway and *Application Gateway for Containers*). The `Ingress` API itself remains valid. Verify the current AKS guidance before choosing a controller for a new cluster.
:::

### ConfigMap and Secret

| | ConfigMap | Secret |
|---|---|---|
| Holds | Non-sensitive config | Sensitive values (passwords, tokens, TLS keys) |
| Encoding | Plain text | **base64 (not encryption!)** |
| Consumed as | Env vars, `envFrom`, mounted files | Same, plus `imagePullSecrets`, TLS |
| Updates | Mounted files update eventually; env vars need Pod restart | Same |

**base64 is not encryption.** Anyone who can `kubectl get secret -o yaml` or read etcd can decode it with `base64 -d`. Protect with RBAC, enable **encryption at rest** (AKS can use customer-managed keys), never commit manifests with real values, and prefer an external store: the **Secrets Store CSI driver** with the **Azure Key Vault provider** mounts Key Vault secrets as files (and can sync to a Kubernetes Secret) using a workload identity.

```yaml
# Consuming config in the .NET Pod: '__' becomes ':' in IConfiguration
env:
- name: ConnectionStrings__Default
  valueFrom: { secretKeyRef: { name: orders-api-secrets, key: sql-connection } }
envFrom:
- configMapRef: { name: orders-api-config }
```

```yaml
# Key Vault via the CSI driver (Azure provider)
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata: { name: kv-shop, namespace: shop }
spec:
  provider: azure
  parameters:
    clientID: "<workload-identity-client-id>"
    keyvaultName: kv-shop-prod
    tenantId: "<tenant-id>"
    objects: |
      array:
        - |
          objectName: SqlConnection
          objectType: secret
  secretObjects:                       # optional: also create a K8s Secret
  - secretName: orders-api-secrets
    type: Opaque
    data: [ { objectName: SqlConnection, key: sql-connection } ]
```

The Pod mounts a `csi` volume referencing `kv-shop` (driver `secrets-store.csi.k8s.io`); the secrets appear under the mount path and the Secret object is created once the Pod mounts it.

### Namespaces

**Definition.** A **Namespace** is a logical partition of one cluster for names, access control and quotas: `dev`, `staging`, `shop`, `monitoring`. Defaults: `default`, `kube-system`, `kube-public`, `kube-node-lease`. Use them to separate teams or environments (small clusters) and attach **RBAC**, **ResourceQuota** (caps total CPU/memory/pods), **LimitRange** (default requests/limits) and **NetworkPolicy**. Namespaces are *not* a hard security boundary; production vs non-production usually deserve separate clusters. Cross-namespace DNS: `orders-api.shop.svc.cluster.local`.

### Resource Requests and Limits

| | Request | Limit |
|---|---|---|
| Meaning | **Guaranteed** minimum; used by the scheduler to place the Pod | **Hard cap** the container may use |
| CPU over limit | — | **Throttled** (slower) |
| Memory over limit | — | **OOMKilled** (container restarted, exit 137) |

QoS classes derive from them: **Guaranteed** (requests = limits), **Burstable**, **BestEffort** (none; first evicted). Without requests the scheduler overpacks nodes; without limits one noisy Pod starves its neighbours.

.NET specifics: the runtime reads the cgroup memory limit and sizes the GC heap from it (default heap hard limit about 75% of the limit), so set the memory limit comfortably above the app's working set; `Environment.ProcessorCount` reflects the CPU limit (rounded up), which drives thread-pool and server-GC sizing — a limit of `100m` makes the app behave single-core. Typical API start: `requests: 250m / 256Mi`, `limits: 1 CPU / 512Mi`, then tune from metrics.

### Horizontal Pod Autoscaler (HPA)

**Definition.** Adds or removes Pod replicas based on metrics (CPU or memory utilisation *relative to the request*, or custom/external metrics). It needs the **metrics-server** (built into AKS) and **resource requests** set.

Formula: `desiredReplicas = ceil(currentReplicas × currentMetric / targetMetric)`. Scale-up is quick; scale-down has a **stabilisation window** (default 5 min) to avoid flapping.

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: { name: orders-api, namespace: shop }
spec:
  scaleTargetRef: { apiVersion: apps/v1, kind: Deployment, name: orders-api }
  minReplicas: 3
  maxReplicas: 12
  metrics:
  - type: Resource
    resource: { name: cpu, target: { type: Utilization, averageUtilization: 70 } }
  behavior:
    scaleDown: { stabilizationWindowSeconds: 300 }
```

Related: **Cluster Autoscaler** adds *nodes* when Pods are Pending for lack of capacity; **VPA** tunes requests; **KEDA** scales on events (Service Bus queue length, Kafka lag, cron) including down to zero.

### Probes: Liveness, Readiness, Startup

| Probe | Question | On failure | Typical content |
|---|---|---|---|
| **Liveness** | "Is the process stuck/deadlocked?" | kubelet **restarts** the container | Cheap self-check; **no dependencies** |
| **Readiness** | "Can it serve traffic right now?" | Pod is **removed from Service endpoints** (no restart) | App initialised, critical dependencies (DB/cache) reachable |
| **Startup** | "Has it finished booting?" | Restarts if it never succeeds; **disables liveness/readiness until success** | Slow-starting apps (big warm-up, migrations) |

```csharp
// Program.cs - two endpoints, two purposes
builder.Services.AddHealthChecks()
    .AddCheck("self", () => HealthCheckResult.Healthy(), tags: ["live"])
    .AddDbContextCheck<ShopDbContext>("sql", tags: ["ready"])   // EF Core health check pkg
    .AddRedis(builder.Configuration["Redis"]!, name: "redis", tags: ["ready"]);

app.MapHealthChecks("/health/live",  new HealthCheckOptions { Predicate = r => r.Tags.Contains("live") });
app.MapHealthChecks("/health/ready", new HealthCheckOptions { Predicate = r => r.Tags.Contains("ready") });
```

```yaml
startupProbe:                         # up to 30 x 5s = 150 s to start
  httpGet: { path: /health/live, port: 8080 }
  periodSeconds: 5
  failureThreshold: 30
livenessProbe:
  httpGet: { path: /health/live, port: 8080 }
  periodSeconds: 10
  timeoutSeconds: 2
  failureThreshold: 3
readinessProbe:
  httpGet: { path: /health/ready, port: 8080 }
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
```

:::warn Probe anti-patterns
- Putting the database check in the **liveness** probe: a SQL outage makes Kubernetes restart every healthy API Pod, turning an incident into an outage. Dependencies belong in readiness.
- No readiness probe: traffic reaches Pods that are still starting, causing 502/503 during rollouts.
- Liveness too aggressive (timeout 1 s) on a busy API: restart loops under load.
- Health endpoints behind authentication or HTTPS redirection: the kubelet sends plain HTTP to the Pod port.
:::

:::q Liveness vs readiness probe?
Liveness decides whether to restart the container; readiness decides whether the Pod receives traffic. A failing liveness means "I'm broken, restart me"; a failing readiness means "I'm temporarily unable to serve, stop sending me requests" — for example while the database is unreachable. I keep dependency checks in readiness only.
:::
