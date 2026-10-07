## Docker Compose, Storage and Networking

### Docker Compose: API + SQL Server + Redis

**Definition.** Docker Compose describes a multi-container application in one `compose.yaml` and runs it with one command. It creates a private network, volumes and containers, and gives each service a DNS name equal to its service name.

**Why it matters.** It is the standard way to give every developer an identical local stack (API + database + cache) and to run integration tests in CI.

```yaml
# compose.yaml  (secrets come from .env which is NOT committed)
name: shop

services:
  api:
    build:
      context: .
      dockerfile: src/Shop.Api/Dockerfile
    image: shop/orders-api:dev
    ports:
      - "5000:8080"                       # host:container
    env_file:
      - .env                              # SA_PASSWORD=...
    environment:
      ASPNETCORE_ENVIRONMENT: Development
      # '__' maps to ':' in .NET configuration; host name = service name
      ConnectionStrings__Default: "Server=sql,1433;Database=ShopDb;User Id=sa;Password=${SA_PASSWORD};TrustServerCertificate=True"
      ConnectionStrings__Redis: "redis:6379"
    depends_on:
      sql:
        condition: service_healthy        # wait for the healthcheck, not just "started"
      redis:
        condition: service_healthy
    networks: [ backend ]
    restart: unless-stopped

  sql:
    image: mcr.microsoft.com/mssql/server:2022-latest
    environment:
      ACCEPT_EULA: "Y"
      MSSQL_SA_PASSWORD: ${SA_PASSWORD}
    ports:
      - "1433:1433"                       # optional: lets SSMS connect from the host
    volumes:
      - sqldata:/var/opt/mssql            # named volume: data survives `down`
    healthcheck:
      test: ["CMD-SHELL", "/opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P \"$$MSSQL_SA_PASSWORD\" -Q 'SELECT 1' || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s
    networks: [ backend ]

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks: [ backend ]

volumes:
  sqldata:
  redisdata:

networks:
  backend:
```

```bash
docker compose up -d --build        # build images, create network/volumes, start all
docker compose ps                   # status incl. health
docker compose logs -f api          # follow one service
docker compose exec sql bash        # shell into a service
docker compose down                 # stop + remove containers/network (keeps volumes)
docker compose down -v              # ...and delete volumes (wipes the database)
docker compose config               # validate and print the resolved file
```

Tips: `compose.override.yaml` is merged automatically (dev-only settings); use `--profile` to start optional services (for example a `mailhog` profile); `docker compose watch` can sync or rebuild on file changes.

:::warn depends_on is not readiness
Plain `depends_on` only orders *start*. SQL Server takes 15-30 seconds to accept connections, so the API still crashes unless you use `condition: service_healthy` **and** make the app resilient (EF `EnableRetryOnFailure`, a retry/Polly policy around migration at startup). Never assume dependencies are up.
:::

### Volumes, Bind Mounts and tmpfs

Container filesystems are ephemeral: delete the container and its writable layer is gone. To persist or share data, mount storage.

| | Named volume | Bind mount | tmpfs |
|---|---|---|---|
| Managed by | Docker (`/var/lib/docker/volumes`) | You (a host path) | Memory only |
| Syntax | `-v sqldata:/var/opt/mssql` | `-v $(pwd)/src:/app/src` or `--mount type=bind,...` | `--tmpfs /tmp` |
| Persists after container removal | **Yes** | Yes (it is your folder) | No |
| Portable / easy to back up | Yes | Host-path dependent | n/a |
| Best for | Databases, uploads, state | Dev hot-reload, config files, sharing source | Scratch data, secrets in RAM, read-only root FS |
| Gotcha | Orphaned volumes pile up (`docker volume prune`) | **Permissions** (non-root user vs host owner), path differences on Windows | Lost on stop |

```bash
docker volume create sqldata
docker run -d -v sqldata:/var/opt/mssql ... mcr.microsoft.com/mssql/server:2022-latest
docker run --rm -v "$PWD/appsettings.Production.json:/app/appsettings.Production.json:ro" shop/orders-api
docker run --read-only --tmpfs /tmp shop/orders-api    # hardened: immutable FS + scratch space
```

### Networks

| Driver | Behaviour | Use |
|---|---|---|
| **bridge** (default) | Private network on one host; containers reach each other by **name on user-defined bridges** (the default `bridge` has no name DNS); `-p` publishes ports to the host | Single-host apps, Compose |
| **host** | Container shares the host network stack (no isolation, no port mapping) | Max throughput, special tools (Linux only) |
| **overlay** | Multi-host network (Swarm/others) | Clustered setups; Kubernetes uses CNI plugins instead |
| **none** | No networking | Isolated batch jobs |
| macvlan | Container gets a real LAN IP | Legacy integrations |

**Service-name DNS.** In a Compose project (or any user-defined bridge), `sql` and `redis` resolve to the right container IPs — so the connection string says `Server=sql`, not an IP or `localhost`. Only the `api` port is published to the host; the database can stay unpublished and unreachable from outside.

### Environment Variables and Secrets

- **Env vars:** `-e KEY=val`, `--env-file .env`, Compose `environment:` / `env_file:`. ASP.NET Core reads them automatically; `Jwt__Issuer` becomes `Jwt:Issuer`. Order of precedence: command-line > environment variables > `appsettings.{Env}.json` > `appsettings.json`.
- **Never** bake secrets into the image with `ENV`/`ARG`/`COPY`; `docker history` and `docker inspect` reveal them.
- **Compose/Swarm secrets** mount files at `/run/secrets/<name>`:

```yaml
services:
  api:
    secrets: [ sql_password ]
secrets:
  sql_password:
    file: ./secrets/sql_password.txt
```

```csharp
// Microsoft.Extensions.Configuration.KeyPerFile: each file becomes a config key
builder.Configuration.AddKeyPerFile("/run/secrets", optional: true);
```

- **Build-time secrets** (private NuGet feed token): `RUN --mount=type=secret,id=nuget dotnet restore` and `docker build --secret id=nuget,src=nuget.config .` — the secret is never stored in a layer.
- **In production** use the platform: Key Vault + managed identity (App Service, Container Apps), Kubernetes Secrets/CSI driver.

## Registries and Publishing

### Container Registries: Docker Hub and ACR

A **registry** stores and distributes images. An image name is `registry/repository:tag` (`acrshop.azurecr.io/shop/orders-api:1.4.2`); without a registry host it means Docker Hub.

| | Docker Hub | Azure Container Registry (ACR) |
|---|---|---|
| Visibility | Public + private repos; rate limits for anonymous pulls | Private, inside your Azure tenant |
| Auth | Docker ID / tokens | Entra ID, **managed identity + `AcrPull` role**, tokens (avoid the admin user) |
| Network | Public | Private endpoints, firewall, geo-replication (Premium) |
| Extras | Huge public image catalogue | `az acr build` (cloud builds), ACR Tasks, vulnerability scanning (Defender), content trust/signing |
| Use | Base images, open source | Your company images next to AKS/App Service |

```bash
az acr create -g rg-shop -n acrshop --sku Standard         # name must be globally unique
az acr login -n acrshop                                    # uses your az login
docker tag shop/orders-api:1.4.2 acrshop.azurecr.io/shop/orders-api:1.4.2
docker push acrshop.azurecr.io/shop/orders-api:1.4.2
az acr repository show-tags -n acrshop --repository shop/orders-api -o table

# Build in the cloud (no local Docker needed) - handy in pipelines
az acr build -r acrshop -t shop/orders-api:1.4.2 -f src/Shop.Api/Dockerfile .

# Let AKS pull without credentials (grants AcrPull to the cluster's kubelet identity)
az aks update -g rg-shop -n aks-shop --attach-acr acrshop
```

**Tagging strategy.** Tags are mutable pointers. Use immutable, traceable tags — the semantic version and/or git SHA (`1.4.2`, `1.4.2-9fceb02`, or the CI build id) — and deploy those. Avoid deploying `latest`: you cannot tell what is running and rollbacks become guesswork. Pin by **digest** (`@sha256:...`) when you need absolute immutability.

### dotnet publish /t:PublishContainer (SDK Container Support)

Since the .NET 8 SDK, you can build an OCI image **without a Dockerfile and without a Docker daemon** (needed only to load the image locally). The SDK picks the correct base image from the target framework, uses the non-root user and detects the port.

```xml
<!-- Shop.Api.csproj -->
<PropertyGroup>
  <ContainerRepository>shop/orders-api</ContainerRepository>
  <ContainerImageTags>1.4.2;latest</ContainerImageTags>
  <ContainerFamily>jammy-chiseled</ContainerFamily>     <!-- chiseled base; pick the family for your TFM -->
</PropertyGroup>
<ItemGroup>
  <ContainerPort Include="8080" Type="tcp" />
</ItemGroup>
```

```bash
# Build into the local Docker daemon
dotnet publish --os linux --arch x64 -c Release /t:PublishContainer

# Build and push straight to ACR (credentials from `az acr login` / docker config)
dotnet publish --os linux --arch x64 -c Release /t:PublishContainer \
   -p ContainerRegistry=acrshop.azurecr.io -p ContainerRepository=shop/orders-api \
   -p ContainerImageTags='"1.4.2"'
```

| | Dockerfile | SDK container support |
|---|---|---|
| Control | **Full** (extra packages, OS tweaks, multi-service images) | MSBuild properties only |
| Needs Docker daemon | Yes | No (to push to a registry or tarball) |
| Caching | Layer cache | Layers: base, dependencies, app (fast rebuilds) |
| Learning curve | Moderate | Very low |
| Best for | Complex images | Simple ASP.NET Core/worker apps in CI |

Property names (`ContainerFamily`, `ContainerBaseImage`, `ContainerUser`, `ContainerImageTags`, `ContainerRegistry`) are stable, but check the current SDK docs for new options.

## Operating Containers

### Debugging Containers

| Need | How |
|---|---|
| Is it running? why did it exit? | `docker ps -a`, `docker logs api`, `docker inspect -f '{{.State.ExitCode}} {{.State.OOMKilled}}' api` |
| Look inside | `docker exec -it api sh` (Debian/Alpine). **Chiseled has no shell**: use `docker debug api` (Docker Desktop), run a debug sidecar sharing the namespace (`kubectl debug` in K8s), or build a Debian variant for troubleshooting |
| Attach a debugger | Visual Studio *Container Tools* debug the Dockerfile target; VS Code: `Attach to .NET Process` via `docker exec`; install `vsdbg` for remote debugging |
| Resource problems | `docker stats`; check `--memory`; .NET respects cgroup memory limits (GC heap sizes derive from them) |
| Diagnose .NET | `dotnet-counters`, `dotnet-trace`, `dotnet-dump` via a tools sidecar or `dotnet-monitor` |
| Network | `docker network inspect backend`, test DNS from a sibling container (`docker compose exec api getent hosts sql`) |

### Image Size and Security Scanning

**Size optimisation checklist:** multi-stage build; runtime image not SDK; chiseled/Alpine base; strong `.dockerignore`; combine `RUN` steps and delete caches in the same layer (`apt-get install ... && rm -rf /var/lib/apt/lists/*`); don't copy `obj`/`bin`; consider trimming (`PublishTrimmed`) or ReadyToRun only after testing (trimming can break reflection-heavy code like EF/JSON); check with `docker history` and tools like `dive`.

**Security checklist:**
- Non-root `USER`; read-only root filesystem (`--read-only` plus `tmpfs /tmp`); drop capabilities (`--cap-drop ALL`); no `--privileged`.
- Minimal, frequently rebuilt base images; pin digests; update on CVE advisories.
- **Scan images**: Trivy (`trivy image shop/orders-api:1.4.2`), Docker Scout (`docker scout cves`), Microsoft Defender for Containers / ACR scanning; fail CI on HIGH/CRITICAL.
- No secrets in layers or env at build; sign images (Notation/cosign) and verify at admission in AKS; generate an SBOM.
- Do not expose the Docker socket to containers.

### Common Problems and Fixes

| Symptom | Cause | Fix |
|---|---|---|
| API cannot reach the database at `localhost` | Inside a container, `localhost` is the **container itself** | Use the Compose **service name** (`Server=sql`); to reach the host machine use `host.docker.internal` |
| `Unable to configure HTTPS endpoint. No server certificate was specified` | No dev certificate in the container | Dev: `dotnet dev-certs https -ep ./https/aspnet.pfx -p <pw>`, mount it, set `ASPNETCORE_Kestrel__Certificates__Default__Path/Password`. **Prod: run plain HTTP in the container and terminate TLS at the ingress/App Service/Front Door**, enabling `UseForwardedHeaders` |
| Connection refused / login failed right after `compose up` | **DB not ready yet** | `depends_on` with `condition: service_healthy`, healthchecks, `EnableRetryOnFailure`, startup retry |
| `permission denied` binding port 80 | Non-root user cannot bind < 1024 | Listen on 8080 (`ASPNETCORE_HTTP_PORTS=8080`), map `-p 80:8080` |
| `permission denied` writing to a mounted volume | Container user (UID 1654) does not own the folder | `chown`/`--user`, set `fsGroup` in K8s, or write to `/tmp` |
| Container exits immediately | PID 1 crashed or finished (bad config, missing env var, unhandled exception on startup) | `docker logs`, `docker inspect` exit code, run with `-it` |
| `exec format error` | Image architecture mismatch (ARM Mac image on amd64) | `--platform linux/amd64` or multi-arch build (`docker buildx`) |
| `CultureNotFoundException`/ICU error on Alpine or chiseled | No ICU libs | `InvariantGlobalization=true` or use `-extra` / install `icu-libs` |
| Code changes not visible | Stale layer cache or image | `docker compose up --build`; check `COPY` order |
| Disk full | Dangling images/volumes | `docker system df`, `docker system prune` |
| API ignores config | Env var naming | Use `__` for nesting (`ConnectionStrings__Default`), not `:` (invalid in shells) |

:::example Real-world example
A team's pipeline builds the Shop API image once, scans it, pushes `acrshop.azurecr.io/shop/orders-api:20261006.3` and the same image is promoted through Dev, Staging and Prod. Only environment variables and Key Vault secrets differ per environment. A rollback is simply deploying the previous tag.
:::

## Quick-fire Q&A

:::q Container vs VM in one sentence?
A VM virtualises hardware and runs a full guest OS; a container virtualises the OS, sharing the host kernel and isolating processes with namespaces and cgroups, so it is lighter and starts faster but offers weaker isolation.
:::

:::q Image vs container?
An image is an immutable, layered template; a container is a running (or stopped) instance of an image with a writable layer on top. Many containers can run from one image.
:::

:::q Why does the order of instructions in a Dockerfile matter?
Each instruction is a cached layer, and a change invalidates every layer after it. I copy `.csproj` files and run `dotnet restore` before copying source code so NuGet restore is cached until dependencies change.
:::

:::q Why use a multi-stage build for .NET?
The SDK image is big and contains compilers I do not need at runtime. Stage one builds and publishes with the SDK; the final stage starts from the small `aspnet` runtime image and copies only the published output, giving a smaller, safer image.
:::

:::q Why does my ASP.NET Core container listen on 8080, not 80?
Since .NET 8 the official images run as a non-root user and default to port 8080, because non-root processes cannot bind ports below 1024. I publish it with `-p 5000:8080` or put the ingress/App Service in front of it.
:::

:::q EXPOSE vs `-p`?
`EXPOSE` only documents which port the app listens on. `-p host:container` actually publishes the port to the host.
:::

:::q How do containers in Compose find each other?
Compose creates a user-defined bridge network with built-in DNS, so a service is reachable by its service name, for example `Server=sql` or `redis:6379`. `localhost` inside a container always means that container.
:::

:::q Volume vs bind mount?
A named volume is managed by Docker and is the right choice for persistent data like database files. A bind mount maps a host folder into the container and is mainly for development, such as live source code or config files.
:::

:::q How do you handle secrets with Docker?
Not in the image: no `ENV`/`ARG`/`COPY` of secrets. Pass them at runtime as env vars or mounted secret files, use BuildKit secret mounts for build-time tokens, and in production use Key Vault with managed identity or Kubernetes secrets.
:::

:::q How do you make a container image secure?
Minimal base (chiseled/Alpine), multi-stage, non-root user, read-only filesystem where possible, pinned and regularly updated base images, vulnerability scanning in CI and the registry, and no secrets in layers.
:::

:::q How do you wait for SQL Server to be ready in Compose?
Give SQL a healthcheck (`sqlcmd -Q "SELECT 1"`) and use `depends_on` with `condition: service_healthy` in the API service. The application also uses retry logic because readiness can still fluctuate.
:::

:::q What does `dotnet publish /t:PublishContainer` do?
It uses the .NET SDK to build a container image from the project without a Dockerfile or daemon, choosing the right base image, a non-root user and ports. I can push directly to a registry such as ACR with `-p ContainerRegistry=...`, which is convenient in CI for simple services.
:::
