### Containers vs Virtual Machines

**In simple words:** A virtual machine (VM) is a full computer made in software, with its own operating system. A container is an isolated process that shares the host's *kernel* (the core of the operating system). Linux keeps containers apart with *namespaces* (separate views of processes, network and files) and limits them with *cgroups* (CPU and memory limits). So containers are smaller and start much faster than VMs.

**Real-life example:** A VM is like a separate house with its own walls, water and power. A container is like a flat in one building. Each flat is private, but all flats share the same foundation and pipes.

**Interview question:** What is the difference between a container and a virtual machine?

**Simple answer:** A VM virtualises hardware and runs a full guest operating system, so it is large and slow to start. A container shares the host kernel and isolates only the process, so it is small and starts in about a second. The trade-off is that a VM gives stronger isolation, because all containers share one kernel.

### Images, Layers and Build Cache

**In simple words:** An image is a read-only template for a container. It is built as a stack of *layers*; instructions like `RUN`, `COPY` and `ADD` each add one. Docker caches layers and reuses them when nothing changed. But when one layer changes, every layer after it is rebuilt. So put the steps that change rarely first.

**Real-life example:** Think of a layered cake. If you change the top layer, you only redo the top. If you change the bottom layer, you must rebuild every layer above it.

**Interview question:** Why does the order of instructions in a Dockerfile matter?

**Simple answer:** Each instruction makes a cached layer, and a change invalidates all layers after it. In .NET I copy the `.csproj` files and run `dotnet restore` before copying the source code. Then the NuGet restore stays cached until dependencies change, so builds are much faster.

```text
COPY *.csproj ./            # changes rarely
RUN dotnet restore          # stays cached
COPY . .                    # changes on every commit
RUN dotnet publish -c Release -o /app
```

### Dockerfile Instructions Explained

**In simple words:** A Dockerfile is the recipe for an image. `FROM` picks the base image, `WORKDIR` sets the folder, `COPY` adds files and `RUN` runs a command at build time. `ENV` sets a variable that the running container also sees; `ARG` exists only during the build. `EXPOSE` only documents a port. `ENTRYPOINT` is the program that always runs, and `CMD` gives its default arguments.

**Real-life example:** A cake recipe card: start with a base mix (`FROM`), add ingredients (`COPY`), do the baking steps (`RUN`), and finally the serving note (`ENTRYPOINT`).

**Interview question:** What is the difference between CMD and ENTRYPOINT?

**Simple answer:** ENTRYPOINT is the fixed program, for example `dotnet Shop.Api.dll`. CMD gives default arguments, and arguments you pass to `docker run` replace CMD. I use the exec (JSON array) form, so my app is PID 1 (the main process) and gets the stop signal for a clean shutdown.

```text
ENTRYPOINT ["dotnet", "Shop.Api.dll"]
CMD ["--urls", "http://+:8080"]
```

### Production Multi-Stage Dockerfile for ASP.NET Core

**In simple words:** A multi-stage build has several `FROM` stages in one Dockerfile. The first stage uses the big SDK image to restore, build and publish. The last stage starts from the small `aspnet` runtime image and copies only the published files. Since .NET 8 the image runs as a non-root user on port 8080, because non-root users cannot use ports below 1024.

**Real-life example:** A furniture factory uses big machines to build a table. Only the finished table is delivered to your home, not the machines.

**Interview question:** Why use a multi-stage build for .NET?

**Simple answer:** The SDK image is large and has compilers that I do not need at runtime. I build and publish in an SDK stage, then copy only the output into the `aspnet` runtime image. The final image is smaller, faster to pull and safer. I also add a `.dockerignore` so `bin`, `obj` and secrets stay out.

```text
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src
COPY . .
RUN dotnet publish -c Release -o /app/publish
FROM mcr.microsoft.com/dotnet/aspnet:9.0
COPY --from=build /app/publish /app
USER $APP_UID
ENTRYPOINT ["dotnet", "/app/Shop.Api.dll"]
```

### Image Variants: Debian, Alpine and Chiseled

**In simple words:** Microsoft ships .NET images on different Linux bases. The default Debian image is the biggest but the easiest to debug. Alpine is smaller, but it uses a different C library (musl), which can break some native libraries and cultures. Chiseled Ubuntu images are small, have no shell and no package manager, and run as non-root, so they are the most secure.

**Real-life example:** A big suitcase holds everything (Debian). A backpack is lighter (Alpine). A small sealed box carries only what you need, and nobody can open it on the way (chiseled).

**Interview question:** Which base image would you choose for an ASP.NET Core app in production?

**Simple answer:** I prefer a chiseled image, because it is small, non-root and has very little to attack. The downside is no shell, so I cannot `docker exec` into it, and a `curl` healthcheck will not work. For cultures and time zones I use the `-extra` variant or set `InvariantGlobalization=true`.

### Docker Commands Cheat Sheet

**In simple words:** A few commands cover most daily work. `docker build` makes an image and `docker run` starts a container from it. `docker ps` lists containers and `docker logs` shows their output. `docker exec` runs a command inside a running container. `docker tag` and `docker push` send an image to a registry.

**Real-life example:** Like a TV remote: it has many buttons, but you use the same five every day.

**Interview question:** Which Docker commands do you use to build, run and debug a container?

**Simple answer:** I build with `docker build -t name:tag .` and run with `docker run -d -p 5000:8080 name:tag`. To debug, I use `docker ps -a`, `docker logs -f`, `docker exec -it api sh` and `docker inspect` for the exit code. Then I `docker tag` and `docker push` the image to a registry like ACR.

```bash
docker build -t shop/api:1.0 .
docker run -d --name api -p 5000:8080 shop/api:1.0
docker logs -f api
docker exec -it api sh
```

### Docker Compose: API + SQL Server + Redis

**In simple words:** Docker Compose describes several containers in one `compose.yaml` file and starts them all with one command. It creates a private network, so each service reaches the others by its service name, like `sql` or `redis`. Plain `depends_on` only controls the start order, not readiness. So add a healthcheck with `condition: service_healthy`, and retry logic in the app.

**Real-life example:** A restaurant manager opens the kitchen, the bar and the cash desk every morning using one instruction sheet.

**Interview question:** How do you make the API wait until SQL Server is ready in Compose?

**Simple answer:** I give the SQL service a healthcheck that runs `SELECT 1`. In the API service I use `depends_on` with `condition: service_healthy`. The app also retries, for example with EF Core `EnableRetryOnFailure`, because the database can still be slow at first.

```bash
docker compose up -d --build   # build and start all services
docker compose logs -f api     # follow the API logs
docker compose down            # stop and remove; volumes are kept
docker compose down -v         # also delete volumes (data is lost)
```

### Volumes, Bind Mounts and tmpfs

**In simple words:** Files written inside a container are lost when you delete the container. To keep data, you mount storage. A *named volume* is managed by Docker and is best for database files. A *bind mount* maps a folder from your machine, which is handy in development. *tmpfs* keeps data only in memory and loses it when the container stops.

**Real-life example:** A named volume is a bank locker that the bank manages. A bind mount is lending someone your own cupboard. tmpfs is a whiteboard that is wiped every evening.

**Interview question:** What is the difference between a volume and a bind mount?

**Simple answer:** A named volume is created and managed by Docker and survives when the container is removed, so I use it for databases. A bind mount maps a host folder into the container, mainly for live code or config files in development. Bind mounts often have permission problems with non-root users.

```bash
docker run -d -v sqldata:/var/opt/mssql mcr.microsoft.com/mssql/server:2022-latest
```

### Networks

**In simple words:** Docker networks decide how containers talk to each other. The default driver is *bridge*, a private network on one host. On a user-defined bridge (Compose creates one for you), containers find each other by name through built-in DNS. Other drivers are `host` (share the host network), `overlay` (many hosts) and `none` (no network).

**Real-life example:** An office phone system. Inside the office you call a colleague by name. People outside can only reach the numbers you publish.

**Interview question:** How do containers in Docker Compose find each other?

**Simple answer:** Compose puts them on a user-defined bridge network with built-in DNS. So a service is reachable by its name, like `Server=sql` or `redis:6379`. Inside a container, `localhost` means that container itself. Only ports I publish with `-p` are reachable from the host, so the database can stay private.

### Environment Variables and Secrets

**In simple words:** Containers get settings through environment variables. ASP.NET Core reads them automatically, and a double underscore means a nested key, so `Jwt__Issuer` becomes `Jwt:Issuer`. Never put secrets into the image with `ENV`, `ARG` or `COPY`, because `docker history` and `docker inspect` can show them. Pass secrets at run time instead.

**Real-life example:** You do not paint the safe code on the safe door. You tell it to the staff member when the shift starts.

**Interview question:** How do you handle secrets with Docker?

**Simple answer:** I never bake secrets into the image. I pass them at run time as environment variables or as secret files under `/run/secrets`. For build-time tokens, like a private NuGet feed, I use BuildKit secret mounts. In production I use Key Vault with managed identity, or Kubernetes secrets.

```bash
docker run -e ConnectionStrings__Default="Server=sql;..." shop/api:1.0
```

### Container Registries: Docker Hub and ACR

**In simple words:** A registry is a server that stores images. An image name looks like `registry/repository:tag`; with no registry host, Docker Hub is used. Docker Hub has public and private images and many base images. Azure Container Registry (ACR) is private inside your Azure account. AKS can pull from ACR with a managed identity and the `AcrPull` role, without passwords.

**Real-life example:** Like an app store: you upload (push) a version, and servers download (pull) it when they need it.

**Interview question:** How do you tag images, and why avoid `latest`?

**Simple answer:** I use unique, traceable tags, such as the version plus the git commit, like `1.4.2-9fceb02`. `latest` keeps moving, so you cannot tell what is running and rollback becomes guesswork. For full certainty I pin the image by its digest (`@sha256:...`).

```bash
az acr login -n acrshop
docker tag shop/api:1.4.2 acrshop.azurecr.io/shop/api:1.4.2
docker push acrshop.azurecr.io/shop/api:1.4.2
```

### dotnet publish /t:PublishContainer (SDK Container Support)

**In simple words:** Since .NET 8, the .NET SDK can build a container image without a Dockerfile. If you push straight to a registry, it does not even need Docker running. The SDK picks the right base image, uses a non-root user and sets the port. You control it with MSBuild properties like `ContainerRepository` and `ContainerImageTags`.

**Real-life example:** A meal kit gives you a standard dinner very fast. Cooking from your own recipe (a Dockerfile) takes more work but gives full control.

**Interview question:** What does `dotnet publish /t:PublishContainer` do?

**Simple answer:** It builds a container image directly from the project, without a Dockerfile. It chooses the base image, a non-root user and the port for me, and it can push straight to ACR. I use it for simple APIs and workers in CI. For extra OS packages or complex images I still write a Dockerfile.

```bash
dotnet publish --os linux --arch x64 -c Release /t:PublishContainer
```

### Debugging Containers

**In simple words:** When a container fails, first check whether it runs and why it stopped. `docker ps -a` shows stopped containers too, `docker logs` shows the output, and `docker inspect` shows the exit code and whether memory ran out. `docker exec -it api sh` opens a shell inside. Chiseled images have no shell, so use `docker debug` or a debug sidecar (a helper container) instead.

**Real-life example:** A mechanic first reads the warning lights (logs), then the service record (inspect), and only then opens the bonnet (exec).

**Interview question:** A container keeps exiting. How do you find the cause?

**Simple answer:** I run `docker ps -a` and `docker logs` to see the error. Then `docker inspect` shows the exit code and the `OOMKilled` flag (killed for using too much memory). Common causes are a missing environment variable, bad config or an exception at startup. For deeper .NET problems I use `dotnet-counters`, `dotnet-trace` or `dotnet-dump`.

```bash
docker logs api
docker inspect -f '{{.State.ExitCode}} {{.State.OOMKilled}}' api
```

### Image Size and Security Scanning

**In simple words:** Small images download faster and contain fewer things to attack. Use a multi-stage build, a runtime or chiseled base image and a good `.dockerignore`. For security, run as non-root, update base images often and never put secrets in layers. Scan images for *CVEs* (publicly known security bugs) with tools like Trivy or Docker Scout, and fail the CI build on serious ones.

**Real-life example:** Packing for a flight: take only what you need, lock your bag, and let airport security scan it before boarding.

**Interview question:** How do you make a container image small and secure?

**Simple answer:** I use a multi-stage build with a minimal base like chiseled, and a non-root user. I pin base images and rebuild them often, and I scan images in CI and in the registry. There are no secrets in layers, and where possible the container runs with a read-only filesystem.

```bash
trivy image shop/orders-api:1.4.2
docker history shop/orders-api:1.4.2
```

### Common Problems and Fixes

**In simple words:** Most container problems repeat. Inside a container, `localhost` means the container itself, so use the service name, like `sql`. Since .NET 8, images run as non-root on port 8080, so binding port 80 fails. If the API fails just after start, the database is often not ready yet. An `exec format error` means the image's CPU type (ARM or x64) does not match the machine.

**Real-life example:** Like a help desk sheet that lists common phone problems and their quick fixes.

**Interview question:** Your API container cannot connect to the database at `localhost`. Why?

**Simple answer:** Inside a container, `localhost` points to that same container, not to the database or my PC. In Compose I use the service name, like `Server=sql`. To reach a database running on the host machine, I use `host.docker.internal`.
