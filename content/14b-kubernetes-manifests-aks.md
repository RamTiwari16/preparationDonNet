## Deploying the .NET API to Kubernetes

### Complete Manifests for the Orders API

A full, production-style set for one ASP.NET Core API in namespace `shop`: ConfigMap, Deployment, Service, Ingress and HPA. Apply them all with `kubectl apply -f k8s/`. The Secret `orders-api-secrets` is created out-of-band (CSI driver from Key Vault, or `kubectl create secret`), never committed.

```yaml
# k8s/00-namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: shop
```

```yaml
# k8s/01-configmap.yaml  - non-secret settings; '__' maps to ':' in .NET config
apiVersion: v1
kind: ConfigMap
metadata:
  name: orders-api-config
  namespace: shop
data:
  ASPNETCORE_ENVIRONMENT: "Production"
  Logging__LogLevel__Default: "Information"
  Redis: "redis.shop.svc.cluster.local:6379"
  Features__NewCheckout: "false"
```

```yaml
# k8s/02-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders-api
  namespace: shop
  labels: { app: orders-api }
spec:
  replicas: 3                         # omit if the HPA owns replica count (GitOps)
  revisionHistoryLimit: 5
  selector:
    matchLabels: { app: orders-api }  # immutable; must match template labels
  strategy:
    type: RollingUpdate
    rollingUpdate: { maxSurge: 1, maxUnavailable: 0 }   # zero-downtime rollout
  template:
    metadata:
      labels:
        app: orders-api
        azure.workload.identity/use: "true"   # AKS workload identity (Key Vault, SQL)
    spec:
      serviceAccountName: orders-api          # federated with an Entra managed identity
      terminationGracePeriodSeconds: 30
      securityContext:
        runAsNonRoot: true
        runAsUser: 1654                       # APP_UID of .NET 8+ images
        fsGroup: 1654
      topologySpreadConstraints:              # spread replicas across zones
      - maxSkew: 1
        topologyKey: topology.kubernetes.io/zone
        whenUnsatisfiable: ScheduleAnyway
        labelSelector: { matchLabels: { app: orders-api } }
      containers:
      - name: api
        image: acrshop.azurecr.io/shop/orders-api:1.4.2   # immutable tag, never latest
        imagePullPolicy: IfNotPresent
        ports:
        - { name: http, containerPort: 8080 }
        envFrom:
        - configMapRef: { name: orders-api-config }
        env:
        - name: ConnectionStrings__Default
          valueFrom:
            secretKeyRef: { name: orders-api-secrets, key: sql-connection }
        resources:
          requests: { cpu: 250m, memory: 256Mi }
          limits:   { cpu: "1",  memory: 512Mi }
        startupProbe:
          httpGet: { path: /health/live, port: http }
          periodSeconds: 5
          failureThreshold: 30
        livenessProbe:
          httpGet: { path: /health/live, port: http }
          periodSeconds: 10
          timeoutSeconds: 2
          failureThreshold: 3
        readinessProbe:
          httpGet: { path: /health/ready, port: http }
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        lifecycle:
          preStop:                 # let endpoints/LB stop routing before SIGTERM lands
            sleep: { seconds: 5 }  # (older clusters: exec ["sleep","5"] needs a shell)
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities: { drop: [ "ALL" ] }
        volumeMounts:
        - { name: tmp, mountPath: /tmp }      # writable scratch for a read-only root FS
      volumes:
      - name: tmp
        emptyDir: {}
```

```yaml
# k8s/03-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: orders-api
  namespace: shop
spec:
  type: ClusterIP
  selector: { app: orders-api }
  ports:
  - { name: http, port: 80, targetPort: http }
```

```yaml
# k8s/04-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: shop-ingress
  namespace: shop
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod   # if cert-manager is installed
spec:
  ingressClassName: nginx     # AKS app routing: webapprouting.kubernetes.azure.com
  tls:
  - hosts: [ shop.contoso.com ]
    secretName: shop-tls
  rules:
  - host: shop.contoso.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service: { name: orders-api, port: { name: http } }
      - path: /
        pathType: Prefix
        backend:
          service: { name: web-spa, port: { number: 80 } }
```

```yaml
# k8s/05-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: orders-api
  namespace: shop
spec:
  scaleTargetRef: { apiVersion: apps/v1, kind: Deployment, name: orders-api }
  minReplicas: 3
  maxReplicas: 12
  metrics:
  - type: Resource
    resource: { name: cpu, target: { type: Utilization, averageUtilization: 70 } }
  - type: Resource
    resource: { name: memory, target: { type: Utilization, averageUtilization: 80 } }
  behavior:
    scaleDown: { stabilizationWindowSeconds: 300 }
```

```yaml
# k8s/06-pdb.yaml - keep at least 2 Pods during node drains/upgrades
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: { name: orders-api, namespace: shop }
spec:
  minAvailable: 2
  selector: { matchLabels: { app: orders-api } }
```

The API must handle **SIGTERM gracefully**: ASP.NET Core stops accepting requests and drains in-flight ones within `HostOptions.ShutdownTimeout`; keep that shorter than `terminationGracePeriodSeconds`. Because TLS ends at the ingress, call `app.UseForwardedHeaders()` so the app sees the original scheme and client IP.

:::example Real-world example
Release 1.4.3 has a bug that makes `/health/ready` fail. With `maxUnavailable: 0`, the first new Pod never becomes Ready, so the rollout stalls with all three old Pods still serving. The pipeline's `kubectl rollout status --timeout=5m` fails and runs `kubectl rollout undo`. Users never notice.
:::

### kubectl Cheat Sheet

| Command | Purpose |
|---|---|
| `kubectl config get-contexts` / `use-context aks-shop` | Which cluster am I talking to? Switch |
| `kubectl get pods -n shop -o wide` | Pods with node and IP (`-A` = all namespaces) |
| `kubectl get deploy,rs,svc,ing,hpa -n shop` | Several resource types at once |
| `kubectl describe pod <pod> -n shop` | Spec, status, **Events** (first stop for problems) |
| `kubectl logs <pod> -c api -f` / `--previous` | Follow logs / logs of the crashed previous container |
| `kubectl logs -l app=orders-api --tail 50` | Logs from all Pods with a label |
| `kubectl exec -it <pod> -- sh` | Shell in a container (not in chiseled images) |
| `kubectl debug -it <pod> --image=busybox --target=api` | Ephemeral debug container sharing the process namespace |
| `kubectl apply -f k8s/` / `kubectl diff -f k8s/` | Declarative create/update / preview changes |
| `kubectl delete -f k8s/04-ingress.yaml` | Remove resources |
| `kubectl port-forward svc/orders-api 5000:80 -n shop` | Reach a ClusterIP service from your laptop |
| `kubectl rollout status/history/undo deploy/orders-api` | Watch, inspect, roll back |
| `kubectl scale deploy/orders-api --replicas=5` | Manual scale (HPA will override) |
| `kubectl set image deploy/orders-api api=<image:tag>` | Imperative image update |
| `kubectl top pods -n shop` / `kubectl top nodes` | CPU/memory usage (metrics-server) |
| `kubectl get events -n shop --sort-by=.lastTimestamp` | Recent cluster events |
| `kubectl get secret orders-api-secrets -o jsonpath='{.data.sql-connection}' \| base64 -d` | Proves secrets are only base64 |
| `kubectl create deploy x --image=nginx --dry-run=client -o yaml` | Generate manifest skeletons |
| `kubectl explain deployment.spec.strategy` | Built-in field documentation |

### Troubleshooting Pods

```text
kubectl get pods  ->  STATUS?
   Pending            -> describe pod: Events (scheduling)
   ImagePullBackOff   -> describe pod: image name/tag, registry auth
   CrashLoopBackOff   -> logs --previous, exit code, describe
   Running, not Ready -> readiness probe; describe + logs; check dependencies
   Running + Ready but no traffic -> Service selector, endpoints, Ingress, DNS
```

| Status / symptom | Typical causes | How to confirm | Fix |
|---|---|---|---|
| **Pending** | Not enough CPU/memory for the **requests**, node selector/affinity/taint mismatch, PVC not bound, quota exceeded | `describe pod` → `FailedScheduling: 0/3 nodes available: insufficient memory` | Lower requests, add nodes/enable Cluster Autoscaler, fix selectors/tolerations, fix the PVC |
| **ImagePullBackOff / ErrImagePull** | Wrong image name/tag, private registry without permission, registry unreachable, rate limited | `describe pod` → `pull access denied` / `not found` | Fix the tag; `az aks update --attach-acr`; `imagePullSecrets`; check firewall/private endpoint |
| **CrashLoopBackOff** | App exits on startup: missing config/secret, bad connection string, unhandled exception, wrong `ENTRYPOINT`, liveness probe killing it | `logs --previous`; `describe` → Last State exit code (1 = app error, 137 = killed, 139 = segfault) | Fix config; check probes and startup time (add startupProbe) |
| **OOMKilled** (exit code 137) | Memory **limit** too low, memory leak, large payloads buffered in memory | `describe pod` → `Reason: OOMKilled`; `kubectl top pod` | Raise the limit, find the leak (`dotnet-counters`, dumps), stream large data |
| **CreateContainerConfigError** | Referenced ConfigMap/Secret or key does not exist | `describe pod` | Create it or fix the name/key |
| **Running but 0/1 Ready** | Readiness failing (DB unreachable, wrong path/port, HTTPS redirect) | `describe` → `Readiness probe failed: HTTP 503` | Fix dependency or probe config |
| **Service returns nothing / 502** | Selector does not match Pod labels, wrong `targetPort`, no ready Pods | `kubectl get endpoints orders-api` is empty | Align labels and ports |
| **Evicted** | Node under memory/disk pressure; BestEffort Pods go first | `describe pod`, node conditions | Set requests/limits, clean disk, bigger nodes |

:::scenario After a deployment, half the requests fail with 502 for a minute
Pods are receiving traffic before they are ready, or being killed while still serving. Add a readiness probe that checks the app is initialised; use `maxUnavailable: 0`; add a `preStop` sleep so the load balancer stops routing before SIGTERM; ensure the app handles SIGTERM and drains connections; keep `terminationGracePeriodSeconds` larger than the drain time.
:::

## Other Workloads, Helm and AKS

### StatefulSet, DaemonSet, Job, CronJob

| Object | What it guarantees | Use |
|---|---|---|
| **StatefulSet** | Stable Pod names (`redis-0`, `redis-1`), ordered start/stop, a **persistent volume per Pod** (`volumeClaimTemplates`), stable DNS via a headless Service | Databases, Kafka, Redis clusters, Elasticsearch (prefer managed Azure services where possible) |
| **DaemonSet** | Exactly one Pod **per node** (or per matching node) | Log/metrics agents, CSI drivers, kube-proxy, security agents |
| **Job** | Runs Pods **to completion**, with retries (`backoffLimit`) and parallelism | EF Core migration bundle before a deploy, one-off data fixes |
| **CronJob** | Creates Jobs on a cron schedule; `concurrencyPolicy: Forbid` prevents overlaps | Nightly reports, cleanup tasks |

```yaml
apiVersion: batch/v1
kind: CronJob
metadata: { name: nightly-report, namespace: shop }
spec:
  schedule: "0 2 * * *"              # 02:00 every day (cluster time zone, usually UTC)
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      backoffLimit: 2
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: report
            image: acrshop.azurecr.io/shop/report-job:1.0.7
```

### Helm

**Definition.** Helm is the package manager for Kubernetes. A **chart** is a folder of templated manifests plus a `values.yaml`; installing it creates a **release** with versioned history, so `upgrade` and `rollback` work on the whole application at once.

```text
orders-api/
  Chart.yaml          # name, version, appVersion
  values.yaml         # defaults: image.tag, replicaCount, resources...
  values-prod.yaml    # environment overrides
  templates/
    deployment.yaml   # image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
    service.yaml
    ingress.yaml
    hpa.yaml
```

```bash
helm lint ./orders-api
helm template ./orders-api -f values-prod.yaml          # render locally, no cluster
helm upgrade --install orders-api ./orders-api -n shop \
   -f values-prod.yaml --set image.tag=1.4.2 --atomic --wait   # atomic = auto-rollback
helm history orders-api -n shop
helm rollback orders-api 3 -n shop
```

Alternatives: **Kustomize** (built into kubectl, `kubectl apply -k`) patches plain YAML with overlays per environment; **GitOps** (Flux, Argo CD; Flux is an AKS extension) pulls the desired state from Git instead of pipelines pushing it.

### AKS Specifics

**Azure Kubernetes Service** is managed Kubernetes: Azure runs (and patches) the control plane; you pay for the worker nodes (plus an uptime-SLA tier if chosen). Key features for a .NET team:

| Area | What to know |
|---|---|
| **Node pools** | A *system* pool (CoreDNS, metrics-server; tainted for critical add-ons) and one or more *user* pools for apps. Each pool is a VM Scale Set with its own VM size, OS (Linux/Windows), zones, Spot pricing, and autoscaler min/max |
| **Cluster Autoscaler** | Adds/removes nodes when Pods are Pending or nodes are underused; works with HPA |
| **ACR integration** | `az aks create/update --attach-acr acrshop` grants `AcrPull` to the kubelet identity — no `imagePullSecrets` |
| **Managed identity** | The cluster's control-plane identity manages Azure resources (LBs, disks); the **kubelet identity** pulls images |
| **Workload identity** | Pods get Entra tokens via a Kubernetes ServiceAccount federated with a managed identity (OIDC issuer). `DefaultAzureCredential` picks it up automatically. Replaces the retired AAD Pod Identity |
| **Secrets** | Key Vault Secrets Store CSI driver add-on |
| **Networking** | Azure CNI (overlay is the common default), network policies (Azure/Calico/Cilium), private clusters, internal load balancers |
| **Ingress** | Application routing add-on, Application Gateway Ingress Controller, **Application Gateway for Containers**, Istio-based gateway (Gateway API) — see the ingress-nginx retirement note |
| **Observability** | Container Insights, Azure Monitor managed Prometheus + Managed Grafana |
| **Upgrades** | Kubernetes minor versions are supported for roughly a year; upgrade control plane then node pools with surge nodes; PDBs keep apps available; enable auto-upgrade channels |
| **Governance** | Azure Policy add-on (e.g., deny privileged containers), Entra ID integration + Kubernetes RBAC, Defender for Containers |

```bash
az aks create -g rg-shop -n aks-shop --node-count 3 --zones 1 2 3 \
   --enable-managed-identity --enable-oidc-issuer --enable-workload-identity \
   --attach-acr acrshop --network-plugin azure --network-plugin-mode overlay \
   --enable-cluster-autoscaler --min-count 3 --max-count 10 \
   --enable-addons azure-keyvault-secrets-provider,monitoring
az aks get-credentials -g rg-shop -n aks-shop
az aks nodepool add -g rg-shop --cluster-name aks-shop -n apppool \
   --node-vm-size Standard_D4s_v5 --mode User --zones 1 2 3 \
   --enable-cluster-autoscaler --min-count 2 --max-count 20

# Workload identity: user-assigned identity + federated credential for the ServiceAccount
az identity create -g rg-shop -n id-orders-api
az identity federated-credential create -g rg-shop --identity-name id-orders-api \
   -n orders-api-fc --issuer "$(az aks show -g rg-shop -n aks-shop \
   --query oidcIssuerProfile.issuerUrl -o tsv)" \
   --subject system:serviceaccount:shop:orders-api --audiences api://AzureADTokenExchange
```

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: orders-api
  namespace: shop
  annotations:
    azure.workload.identity/client-id: "<id-orders-api client id>"
# Pods using this SA with label azure.workload.identity/use: "true" get AZURE_* env vars
# and a projected token; new DefaultAzureCredential() then works with no code change.
```

:::q How does a Pod in AKS access Key Vault or Azure SQL without secrets?
With Entra workload identity: the cluster exposes an OIDC issuer, a user-assigned managed identity has a federated credential trusting the Pod's Kubernetes ServiceAccount, and the Pod is labelled to use it. The webhook injects a token file and env vars, so `DefaultAzureCredential` gets Entra tokens. I then grant that identity Key Vault Secrets User or a SQL contained user.
:::

## Quick-fire Q&A

:::q Explain the Kubernetes architecture in 30 seconds.
A control plane (API server as the single entry point, etcd for state, scheduler to place Pods, controller manager for reconciliation loops) and worker nodes running kubelet, kube-proxy and a container runtime such as containerd. Everything is declarative: controllers keep actual state equal to desired state.
:::

:::q Pod vs Deployment vs ReplicaSet?
A Pod is one or more co-located containers sharing network and storage. A ReplicaSet keeps N Pods running. A Deployment manages ReplicaSets to give rolling updates and rollbacks; it is what I actually write.
:::

:::q ClusterIP vs NodePort vs LoadBalancer?
ClusterIP is an internal virtual IP and DNS name, the default. NodePort opens a port on every node. LoadBalancer asks the cloud for an external (or internal) load balancer with its own IP. For HTTP I usually keep services ClusterIP and expose them through one Ingress or Gateway.
:::

:::q What is an Ingress and why do you need an ingress controller?
Ingress is a set of layer-7 routing rules (host/path to Service, TLS). The rules do nothing until an ingress controller such as NGINX, Application Gateway or an Istio gateway reads them and configures a proxy. It lets many services share one public IP and certificate.
:::

:::q Is a Kubernetes Secret secure?
Not by itself. It is only base64-encoded. Security comes from RBAC, encryption at rest for etcd, not committing values to Git and, ideally, sourcing secrets from Key Vault through the CSI driver with workload identity.
:::

:::q ConfigMap vs Secret?
Both inject configuration as env vars or files. ConfigMap is for non-sensitive settings; Secret is for sensitive data and gets slightly stricter handling (base64, can be encrypted at rest, separate RBAC). Env-var values need a Pod restart to change.
:::

:::q Requests vs limits?
Requests are what the scheduler reserves and guarantees; limits are a hard cap. Exceeding the CPU limit throttles the container; exceeding the memory limit gets it OOMKilled with exit code 137.
:::

:::q How does the HPA decide how many Pods to run?
It compares the current metric, such as average CPU utilisation relative to requests, with the target and computes `ceil(current replicas × current / target)`, bounded by min and max replicas, with a stabilisation window for scale-down. It needs metrics-server and resource requests.
:::

:::q How does a rolling update achieve zero downtime?
The Deployment creates new Pods (up to `maxSurge`) and only removes old ones when new ones pass readiness, never dropping below `replicas - maxUnavailable`. With `maxUnavailable: 0`, good readiness probes and graceful SIGTERM handling, users see no errors.
:::

:::q How do you roll back a bad release?
`kubectl rollout undo deployment/orders-api` (or `--to-revision`), or `helm rollback`, or redeploy the previous immutable image tag from the pipeline. Database changes must be backward compatible for that to be safe.
:::

:::q Your Pod is in CrashLoopBackOff. What do you do?
`kubectl describe pod` for the exit code and events, then `kubectl logs --previous` to see why the last container died. Usually it is missing configuration or secrets, a bad connection string, or an over-eager liveness probe; exit code 137 points to OOMKilled.
:::

:::q Liveness vs readiness vs startup probe?
Liveness restarts a stuck container, readiness removes a Pod from load balancing while it cannot serve, and startup gives slow-starting apps time before the other probes begin. In ASP.NET Core I expose `/health/live` (self only) and `/health/ready` (dependencies) with tagged health checks.
:::
