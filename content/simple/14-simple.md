### What Kubernetes Is and Why It Exists

**In simple words:** Kubernetes (K8s) is a *container orchestrator* (a system that runs and manages containers on many machines). You write the *desired state*, for example "run 3 copies of my API". Kubernetes keeps checking and makes the real state match it. It restarts failed containers, moves them off dead machines, scales them and rolls out new versions. On Azure, the managed version is AKS.

**Real-life example:** A restaurant manager is told "always have 3 cooks in the kitchen". If one goes home sick, the manager calls in another cook without being asked.

**Interview question:** What is Kubernetes and why do we need it?

**Simple answer:** Docker runs containers on one machine, but production needs many machines. Kubernetes manages containers across a *cluster* (a group of machines). It gives self-healing, scaling, rolling updates, service discovery and secrets through one standard API. I only describe what I want, and its controllers keep the system in that state.

### Control Plane and Node Components

**In simple words:** A cluster has a *control plane* (the brain) and *worker nodes* (the machines that run your apps). The control plane has the API server (the only front door), etcd (the database of cluster state), the scheduler (picks a node for each Pod) and the controller manager (loops that fix differences). Each node runs the kubelet (starts and checks Pods), kube-proxy (Service networking) and a container runtime like containerd.

**Real-life example:** In an airport, the control tower decides which plane uses which gate. Ground staff at each gate then do the actual work and report back.

**Interview question:** Explain the Kubernetes architecture briefly.

**Simple answer:** All requests go through the API server, and the state is stored in etcd. The scheduler places Pods on nodes, and controllers keep the actual state equal to the desired state. On each node, the kubelet runs the containers through containerd, and kube-proxy routes Service traffic. That is why a deleted Pod comes back: a controller notices and recreates it.

### Pod

**In simple words:** A Pod is the smallest thing Kubernetes runs. It holds one or more containers that share one IP address and can share storage. Pods are temporary: when one dies, a new Pod with a new IP replaces it. So never depend on a Pod's IP, and do not create bare Pods in production; let a Deployment manage them.

**Real-life example:** A Pod is like a hotel room for your containers. Guests in the same room share one room number. When they check out, the next guests get a different room.

**Interview question:** What is a Pod, and when would you put two containers in one Pod?

**Simple answer:** A Pod is one or more containers that run together, share the network and can share volumes. Usually it has one app container. I add a second one only for a helper, such as a *sidecar* (a log shipper or proxy) or an *init container* that runs first, for example to wait for the database.

### ReplicaSet and Deployment

**In simple words:** A ReplicaSet keeps a fixed number of identical Pods running. A Deployment manages ReplicaSets and adds safe updates. When you change the image, it creates a new ReplicaSet and moves Pods over step by step. `maxSurge` sets how many extra Pods may exist, and `maxUnavailable` sets how many may be down. The old ReplicaSet is kept, so you can roll back.

**Real-life example:** A shop replaces its cashiers one at a time during the day, so at least four tills are always open.

**Interview question:** How does a rolling update give zero downtime, and how do you roll back?

**Simple answer:** The Deployment starts new Pods and removes old ones only after the new ones pass the readiness probe. With `maxUnavailable: 0`, capacity never drops. If a release is bad, I run `kubectl rollout undo`. I use fixed image tags, not `latest`, so a rollback really goes to the old version.

```bash
kubectl set image deployment/orders-api api=acrshop.azurecr.io/shop/orders-api:1.4.3
kubectl rollout status deployment/orders-api
kubectl rollout undo deployment/orders-api
```

### Services

**In simple words:** Pods come and go, and their IPs change. A Service gives a group of Pods (chosen by labels) one stable IP address and DNS name, and spreads traffic across the ready Pods. `ClusterIP` is internal only and is the default. `NodePort` opens a port on every node. `LoadBalancer` asks Azure for a real load balancer with its own IP.

**Real-life example:** A company's main phone number stays the same, even when the staff answering the calls change.

**Interview question:** What is the difference between ClusterIP, NodePort and LoadBalancer?

**Simple answer:** ClusterIP is an internal IP and DNS name for calls inside the cluster. NodePort opens the same port on every node. LoadBalancer creates a cloud load balancer with an external or internal IP. For HTTP APIs I keep Services as ClusterIP and expose them through one Ingress or Gateway.

```yaml
kind: Service
spec:
  selector: { app: orders-api }   # must match the Pod labels
  ports:
  - { port: 80, targetPort: 8080 }
```

### Ingress and Ingress Controllers

**In simple words:** An Ingress is a set of HTTP routing rules, such as "`/api` goes to the orders Service". It also holds TLS (HTTPS certificate) settings. The rules do nothing alone. An *ingress controller*, like NGINX or Azure Application Gateway, reads them and sets up a real proxy. Many Services can then share one public IP and one certificate. Note: the community ingress-nginx project was retired, and Azure is moving to the newer Gateway API.

**Real-life example:** A hotel receptionist reads the booking list and sends each guest to the right floor and room.

**Interview question:** What is an Ingress and why do you need an ingress controller?

**Simple answer:** Ingress defines layer-7 (HTTP) rules: host and path to Service, plus TLS. A controller such as NGINX, Application Gateway or an Istio gateway reads those rules and configures the proxy. Without a controller, the Ingress object does nothing.

### ConfigMap and Secret

**In simple words:** A ConfigMap holds normal settings, and a Secret holds sensitive values like passwords. Both reach the Pod as environment variables or files. A Secret is only base64-encoded (a text format), which is not encryption, so anyone with access can decode it. Protect Secrets with RBAC (access rules) and encryption at rest, or load them from Azure Key Vault with the CSI driver.

**Real-life example:** A ConfigMap is the notice board in the staff room. A Secret is an envelope with the safe code — but the envelope is not locked, so you must control who can open it.

**Interview question:** Is a Kubernetes Secret secure?

**Simple answer:** Not by itself, because base64 is easy to decode. Security comes from RBAC, encryption of etcd at rest and never committing real values to Git. In AKS I prefer Key Vault through the Secrets Store CSI driver with workload identity. Env-var values need a Pod restart to change.

```yaml
env:
- name: ConnectionStrings__Default
  valueFrom: { secretKeyRef: { name: orders-api-secrets, key: sql-connection } }
envFrom:
- configMapRef: { name: orders-api-config }
```

### Namespaces

**In simple words:** A Namespace splits one cluster into logical groups, such as `dev`, `staging` or `shop`. Names must be unique only inside a namespace. You can attach access rules (RBAC), quotas (total CPU and memory caps) and network policies per namespace. Namespaces are not a hard security wall, so production usually gets its own cluster.

**Real-life example:** Departments in one office building. Each has its own room and budget, but they all share the same building and lifts.

**Interview question:** What are namespaces used for?

**Simple answer:** They group resources for teams or environments, and they let me apply RBAC, ResourceQuota and NetworkPolicy per group. A Service in another namespace is reached as `orders-api.shop.svc.cluster.local`. For strong separation, like production vs test, I use separate clusters.

### Resource Requests and Limits

**In simple words:** A *request* is the CPU and memory the Pod is promised; the scheduler uses it to pick a node. A *limit* is the hard maximum. If a container goes over its CPU limit, it is slowed down (throttled). If it goes over its memory limit, it is killed (OOMKilled, exit code 137) and restarted. .NET reads the memory limit and sizes its GC heap from it.

**Real-life example:** A parking lot reserves one space for you (request). The barrier stops you from using more than two spaces (limit).

**Interview question:** What is the difference between requests and limits?

**Simple answer:** Requests are reserved and guaranteed, and they decide where the Pod is placed. Limits are a cap. Over the CPU limit, the app is throttled; over the memory limit, it is OOMKilled. Without requests, nodes get overloaded; without limits, one bad Pod can starve the others.

```yaml
resources:
  requests: { cpu: 250m, memory: 256Mi }
  limits:   { cpu: "1",  memory: 512Mi }
```

### Horizontal Pod Autoscaler (HPA)

**In simple words:** The HPA adds or removes Pod copies based on a metric, usually average CPU use compared to the request. It needs metrics-server and resource requests on the Pods. It scales up quickly, but waits about 5 minutes before scaling down, to avoid going up and down too often. If nodes are full, the Cluster Autoscaler adds new machines. KEDA can scale on events like queue length.

**Real-life example:** A supermarket opens more checkout counters when the queues get long, and closes some when the shop is quiet.

**Interview question:** How does the HPA decide how many Pods to run?

**Simple answer:** It compares the current metric with the target, for example 70% CPU. It calculates `ceil(current replicas × current value / target)`, within the min and max replicas. It needs resource requests, because utilisation is measured against them.

```yaml
minReplicas: 3
maxReplicas: 12
metrics:
- type: Resource
  resource: { name: cpu, target: { type: Utilization, averageUtilization: 70 } }
```

### Probes: Liveness, Readiness, Startup

**In simple words:** Probes are health checks that the kubelet runs on your container. *Liveness* asks "is it stuck?" — if it fails, the container is restarted. *Readiness* asks "can it take traffic now?" — if it fails, the Pod stops getting requests but is not restarted. *Startup* gives slow apps time to boot before the other probes begin.

**Real-life example:** A shop sign. "Closed for a short break" is readiness — customers wait, nobody is fired. A cashier who has fainted needs help — that is liveness, and the cashier is replaced.

**Interview question:** What is the difference between liveness and readiness probes?

**Simple answer:** Liveness decides whether to restart the container, and readiness decides whether it gets traffic. I keep database and cache checks only in readiness. If SQL is down and liveness checks it, Kubernetes would restart every healthy Pod and make the outage worse. In ASP.NET Core I expose `/health/live` and `/health/ready`.

```csharp
app.MapHealthChecks("/health/live",
    new HealthCheckOptions { Predicate = r => r.Tags.Contains("live") });
app.MapHealthChecks("/health/ready",
    new HealthCheckOptions { Predicate = r => r.Tags.Contains("ready") });
```

### Complete Manifests for the Orders API

**In simple words:** A real API usually needs several YAML files: a Namespace, a ConfigMap, a Deployment, a Service, an Ingress, an HPA and a PodDisruptionBudget (PDB, a rule that keeps some Pods running during maintenance). The Deployment sets the image tag, resources, probes, non-root security and a rolling-update strategy. Secrets are created separately and never committed. You apply them all with `kubectl apply -f k8s/`.

**Real-life example:** Opening a new shop needs several papers: the lease, the staff plan, the opening hours and the fire safety plan. Together they describe the full shop.

**Interview question:** What do you include when deploying an ASP.NET Core API to Kubernetes?

**Simple answer:** A Deployment with a fixed image tag, requests and limits, three probes and a non-root security context. A ClusterIP Service, an Ingress for HTTPS routing, an HPA and a PDB. The app must handle SIGTERM (the stop signal) gracefully, and a short `preStop` sleep lets traffic stop before shutdown.

### kubectl Cheat Sheet

**In simple words:** `kubectl` is the command-line tool that talks to the API server. `get` lists resources, `describe` shows details and recent events, and `logs` shows container output. `apply -f` creates or updates resources from YAML files. `port-forward` lets you call an internal Service from your laptop. `rollout` watches, lists and undoes Deployment changes.

**Real-life example:** It is like the control panel of a building's security system. One panel lets you see every room, open doors and read the alarm history.

**Interview question:** Which kubectl commands do you use most for daily work and troubleshooting?

**Simple answer:** I use `kubectl get pods -n shop`, then `kubectl describe pod` to read the Events. `kubectl logs --previous` shows why a crashed container died. I deploy with `kubectl apply -f`, check with `kubectl rollout status`, and test internal services with `kubectl port-forward`.

```bash
kubectl get pods -n shop -o wide
kubectl describe pod <pod> -n shop
kubectl logs <pod> -n shop --previous
kubectl port-forward svc/orders-api 5000:80 -n shop
```

### Troubleshooting Pods

**In simple words:** Start with the Pod status. *Pending* means no node has enough room, or a rule does not match. *ImagePullBackOff* means a wrong image name or no permission to the registry. *CrashLoopBackOff* means the app keeps crashing at startup. *Running but not Ready* means the readiness probe fails. If everything is Ready but no traffic arrives, check that the Service selector matches the Pod labels.

**Real-life example:** A doctor checks symptoms in order: temperature, then blood test, then X-ray. Each result tells you where to look next.

**Interview question:** Your Pod is in CrashLoopBackOff. What do you do?

**Simple answer:** I run `kubectl describe pod` to see the exit code and events. Then `kubectl logs --previous` shows why the last container died. Usually it is a missing config or secret, a bad connection string or a liveness probe that is too strict. Exit code 137 means it was killed, often OOMKilled for using too much memory.

### StatefulSet, DaemonSet, Job, CronJob

**In simple words:** Besides Deployments, Kubernetes has other workload types. A *StatefulSet* gives each Pod a fixed name and its own disk, for databases or Kafka. A *DaemonSet* runs exactly one Pod on each node, for log or monitoring agents. A *Job* runs a task until it finishes, like a database migration. A *CronJob* runs Jobs on a schedule, like a nightly report.

**Real-life example:** StatefulSet is assigned seats on a train. DaemonSet is one security guard per building floor. A Job is a one-time delivery. A CronJob is the bin collection every Monday morning.

**Interview question:** When would you use a StatefulSet instead of a Deployment?

**Simple answer:** I use a StatefulSet when each Pod needs a stable name, a stable DNS name and its own persistent disk, such as Redis or Kafka. Deployment Pods are interchangeable and have no fixed identity. For databases in Azure, I usually prefer a managed service instead.

### Helm

**In simple words:** Helm is a package manager for Kubernetes. A *chart* is a folder of YAML templates plus a `values.yaml` file with default settings. Installing a chart creates a *release* with a version history. So you can upgrade or roll back the whole app with one command. You keep one values file per environment.

**Real-life example:** A cake recipe with blanks: "add ___ grams of sugar". Each customer fills in their own amounts, but the recipe stays the same.

**Interview question:** What is Helm and why use it?

**Simple answer:** Helm packages all the manifests of an app as one templated chart. I set different values per environment, like the image tag or replica count. `helm upgrade --install --atomic` deploys and rolls back automatically if it fails. `helm rollback` returns the whole release to an earlier version.

```bash
helm upgrade --install orders-api ./orders-api -n shop \
  -f values-prod.yaml --set image.tag=1.4.2 --atomic --wait
helm rollback orders-api 3 -n shop
```

### AKS Specifics

**In simple words:** Azure Kubernetes Service (AKS) is managed Kubernetes: Azure runs and patches the control plane, and you pay for the worker nodes. Nodes are grouped into *node pools* (groups of VMs of the same size). AKS can pull from ACR without passwords, using `--attach-acr`. With *workload identity*, Pods get Entra ID tokens, so they reach Key Vault or Azure SQL with no stored secrets.

**Real-life example:** It is like renting a flat in a managed building. The owner looks after the lifts and security; you only furnish and run your own flat.

**Interview question:** How does a Pod in AKS access Key Vault without storing a secret?

**Simple answer:** I use Entra workload identity. A managed identity trusts the Pod's Kubernetes ServiceAccount through a federated credential. The Pod gets a token file, and `DefaultAzureCredential` uses it automatically. Then I give that identity access to Key Vault or SQL.
