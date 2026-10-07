## Docker Fundamentals

### Containers vs Virtual Machines

**Definition.** A **container** is an isolated process (or group of processes) that shares the host's OS kernel but has its own filesystem, network and process view. Linux provides this with *namespaces* (isolation: pid, net, mount, user) and *cgroups* (resource limits: CPU, memory). An **image** is the read-only, layered template; a container is a running instance of an image plus a thin writable layer.

**Why it matters.** "Works on my machine" disappears: the exact runtime, libraries and config that passed CI are what run in production. Containers start in about a second, pack densely, and are the unit that Kubernetes, Container Apps and App Service for Containers schedule.

| | Virtual machine | Container |
|---|---|---|
| Isolation | Hardware-level; own guest OS + kernel | Process-level; shares host kernel |
| Size | GBs | Tens to hundreds of MB |
| Startup | Seconds to minutes | Milliseconds to seconds |
| Density | Few per host | Many per host |
| Security boundary | Stronger | Weaker (kernel shared); needs hardening |
| Typical use | Different OS, strong isolation, legacy | Microservices, CI, cloud-native apps |

Windows containers exist but Linux containers are the norm for ASP.NET Core.

### Images, Layers and Build Cache

An image is a stack of **read-only layers**, each produced by one Dockerfile instruction (`RUN`, `COPY`, `ADD` create filesystem layers). Layers are content-addressed and shared: ten images based on `aspnet:9.0` store the base only once, and pulls only fetch layers you do not have. A running container adds a **copy-on-write** writable layer that disappears with the container.

**Build cache rule.** Docker reuses a cached layer if the instruction and its inputs are unchanged. The first changed layer **invalidates all layers after it**. So order instructions from *least* to *most* frequently changing: base image → `.csproj` files → `restore` → source code → `publish`. That is why a .NET Dockerfile copies the project files and restores *before* copying the source.

```text
Layer order (good)                         Layer order (bad)
FROM sdk                                   FROM sdk
COPY *.csproj    <- changes rarely         COPY . .       <- changes every commit
RUN dotnet restore  <- cached              RUN dotnet restore  <- re-runs every build
COPY . .         <- changes often          RUN dotnet publish
RUN dotnet publish
```

### Dockerfile Instructions Explained

| Instruction | Purpose | Notes |
|---|---|---|
| `FROM image AS name` | Base image; starts a **stage** | Multi-stage builds use several `FROM`s |
| `WORKDIR /app` | Sets (and creates) the working directory | Prefer over `RUN cd` |
| `COPY src dest` | Copy files from build context (or `--from=stage`) | Prefer over `ADD` (which also untars and fetches URLs) |
| `RUN cmd` | Execute at **build time**; creates a layer | Chain with `&&` and clean caches in the same `RUN` |
| `ENV KEY=value` | Environment variable, persists in the **image and container** | Do not put secrets here |
| `ARG NAME=default` | **Build-time** variable only (`--build-arg`) | Not available at runtime; still visible in image history |
| `EXPOSE 8080` | **Documentation** of the listening port | Does *not* publish it; `-p` does |
| `ENTRYPOINT [...]` | The executable that always runs | Use exec (JSON) form |
| `CMD [...]` | Default arguments (or default command) | Overridden by args to `docker run` |
| `USER` | Non-root user for following instructions and runtime | Security best practice |
| `HEALTHCHECK` | Command Docker runs to mark the container healthy/unhealthy | Ignored by Kubernetes (use probes) |
| `LABEL`, `VOLUME`, `SHELL`, `STOPSIGNAL` | Metadata, declared mount points, etc. | |

#### ENTRYPOINT vs CMD

| | ENTRYPOINT | CMD |
|---|---|---|
| Role | The fixed program | Default arguments to it (or the default command if no ENTRYPOINT) |
| `docker run img foo` | `foo` is **appended** as an argument | `foo` **replaces** CMD |
| Override | `--entrypoint` | Extra args to `docker run` |

```dockerfile
ENTRYPOINT ["dotnet", "Shop.Api.dll"]     # exec form: dotnet is PID 1 and receives SIGTERM
CMD ["--urls", "http://+:8080"]           # default args; replaceable at docker run
# Shell form (ENTRYPOINT dotnet Shop.Api.dll) wraps in /bin/sh -c, so signals are not
# forwarded and graceful shutdown breaks. Always use the exec (JSON array) form.
```

:::q What is the difference between CMD and ENTRYPOINT?
ENTRYPOINT defines the executable that always runs; CMD supplies default arguments or a default command that `docker run` arguments replace. With ENTRYPOINT `["dotnet","Shop.Api.dll"]`, `docker run image --foo` appends `--foo`. Both should use exec form so the process is PID 1 and receives SIGTERM for graceful shutdown.
:::

:::q What is the difference between ARG and ENV?
ARG exists only while building and is set with `--build-arg`; ENV is baked into the image and visible to the running container. Neither is a safe place for secrets — they leak through `docker history`/`inspect`.
:::

### Production Multi-Stage Dockerfile for ASP.NET Core

**Definition.** A *multi-stage build* uses several `FROM` stages in one Dockerfile and copies only the final artifacts into a small runtime image. The SDK (hundreds of MB, compilers, NuGet cache) never reaches production.

```dockerfile
# syntax=docker/dockerfile:1
# ---------- Stage 1: restore + build (SDK image) ----------
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src

# Copy ONLY project files first so `dotnet restore` stays cached until a csproj changes.
COPY ["Directory.Build.props", "Directory.Packages.props", "./"]
COPY ["src/Shop.Api/Shop.Api.csproj",                       "src/Shop.Api/"]
COPY ["src/Shop.Application/Shop.Application.csproj",       "src/Shop.Application/"]
COPY ["src/Shop.Domain/Shop.Domain.csproj",                 "src/Shop.Domain/"]
COPY ["src/Shop.Infrastructure/Shop.Infrastructure.csproj", "src/Shop.Infrastructure/"]
RUN dotnet restore "src/Shop.Api/Shop.Api.csproj"

# Now the sources (changes on every commit - everything below is rebuilt).
COPY src/ src/
WORKDIR /src/src/Shop.Api
RUN dotnet build "Shop.Api.csproj" -c Release --no-restore -o /app/build

# ---------- Stage 2: publish ----------
FROM build AS publish
RUN dotnet publish "Shop.Api.csproj" -c Release --no-restore -o /app/publish \
    /p:UseAppHost=false          # no native launcher executable needed

# ---------- Stage 3: runtime (small ASP.NET Core image, no SDK) ----------
FROM mcr.microsoft.com/dotnet/aspnet:9.0 AS final
WORKDIR /app

# .NET 8+ images listen on 8080 (non-privileged) by default; stated here for clarity.
ENV ASPNETCORE_HTTP_PORTS=8080
EXPOSE 8080

COPY --from=publish /app/publish .

# .NET 8+ images define a non-root user "app" and the variable APP_UID (1654).
USER $APP_UID

ENTRYPOINT ["dotnet", "Shop.Api.dll"]
```

Build and run:

```bash
docker build -t shop/orders-api:1.4.2 -f src/Shop.Api/Dockerfile .   # context = repo root
docker run -d --name orders-api -p 5000:8080 \
   -e ASPNETCORE_ENVIRONMENT=Production \
   -e ConnectionStrings__Default="Server=host.docker.internal;Database=ShopDb;..." \
   shop/orders-api:1.4.2
curl http://localhost:5000/health/live
```

Version note: use the `9.0` tag shown, `8.0` for .NET 8, or `10.0` for .NET 10 (verify current tags on `mcr.microsoft.com`). Pin to a more specific tag (`9.0.4`) or digest for reproducible builds.

#### .dockerignore

A `.dockerignore` at the build-context root keeps junk out of the context (faster builds, no secrets, better cache hits). Without it, a local `bin/` or `obj/` copied into the image breaks restores.

```text
**/bin/
**/obj/
**/.vs/
**/.vscode/
**/node_modules/
**/TestResults/
.git/
.gitignore
**/*.user
**/.env
**/appsettings.Development.json
Dockerfile*
docker-compose*
**/*.md
```

#### Why non-root and why port 8080

Running as root inside a container means a container escape yields root on the host. From .NET 8 onward the official images ship a non-root `app` user and default to **port 8080** (via `ASPNETCORE_HTTP_PORTS=8080`), because non-root processes cannot bind privileged ports below 1024. Older tutorials map port 80 — that fails with "permission denied" for non-root users. Map `-p 5000:8080` on the host.

### Image Variants: Debian, Alpine and Chiseled

| Variant | Example tag | Approx. size* | Shell / package manager | Notes |
|---|---|---|---|---|
| Default (Debian/Ubuntu) | `aspnet:9.0` | ~220 MB | Yes | Most compatible, easiest to debug |
| **Alpine** | `aspnet:9.0-alpine` | ~110 MB | `sh`, `apk` | musl libc: native-library surprises, ICU/globalization needs setup |
| **Chiseled (Ubuntu)** | `aspnet:9.0-noble-chiseled` (`8.0-jammy-chiseled`) | ~110 MB | **None** | Distroless-style: no shell, no package manager, non-root by default, tiny attack surface |
| Chiseled-extra | `...-chiseled-extra` | slightly larger | None | Adds ICU and tzdata for culture/time-zone support |

*Sizes are indicative; verify.

Chiseled images give the best security story, but you cannot `docker exec ... sh` into them and a `HEALTHCHECK` using `curl` will not work. For globalization on Alpine/chiseled either use `InvariantGlobalization=true` or the `-extra` image; otherwise cultures other than invariant throw `CultureNotFoundException`.

### Docker Commands Cheat Sheet

| Command | What it does |
|---|---|
| `docker build -t name:tag -f path/Dockerfile .` | Build an image from the context `.` |
| `docker run -d --name api -p 5000:8080 -e KEY=val -v data:/app/data image:tag` | Run detached, publish `host:container` port, set env, mount a volume |
| `docker run --rm -it image sh` | Throwaway interactive container |
| `docker ps` / `docker ps -a` | Running / all containers |
| `docker logs -f --tail 100 api` | Follow the log output |
| `docker exec -it api sh` | Open a shell in a running container (not possible in chiseled) |
| `docker stop api` / `docker start api` / `docker restart api` | Lifecycle (`stop` sends SIGTERM, then SIGKILL after 10 s) |
| `docker rm -f api` | Remove a container (`-f` forces) |
| `docker images` / `docker rmi image` | List / delete images |
| `docker tag image:tag acrshop.azurecr.io/shop/orders-api:1.4.2` | Add a registry-qualified name |
| `docker login acrshop.azurecr.io` / `az acr login -n acrshop` | Authenticate to a registry |
| `docker push acrshop.azurecr.io/shop/orders-api:1.4.2` | Upload the image |
| `docker pull image:tag` | Download an image |
| `docker inspect api` | Full JSON: IP, mounts, env, health, exit code |
| `docker stats` | Live CPU/memory per container |
| `docker cp api:/app/log.txt .` | Copy files in/out |
| `docker history image` | Layers and their sizes (spot fat layers) |
| `docker system df` / `docker system prune -a --volumes` | Disk usage / delete unused data (**dangerous**: removes unused volumes and images) |
| `docker volume ls`, `docker network ls` | List volumes / networks |
