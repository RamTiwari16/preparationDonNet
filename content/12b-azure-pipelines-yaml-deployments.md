## Azure Pipelines

### CI vs CD vs Continuous Deployment

| Term | Meaning | Trigger / gate |
|---|---|---|
| **Continuous Integration (CI)** | Every push/PR is built and tested automatically against the merged code; fast feedback, small batches | Push, PR |
| **Continuous Delivery (CD)** | Every green build is *releasable* and deployed to test/staging automatically; production release is a **manual approval** | Approval gate |
| **Continuous Deployment** | Every green build goes to production automatically, no human gate (needs strong tests, flags, monitoring, auto-rollback) | Fully automatic |

### Classic vs YAML, Build vs Release

**Azure Pipelines** is the CI/CD service of Azure DevOps. It runs on Microsoft-hosted or self-hosted agents and can build anything and deploy anywhere (also from GitHub repos).

| | Classic (UI) | YAML |
|---|---|---|
| Defined in | Web designer, stored in the service | `azure-pipelines.yml` **in the repo** |
| Versioned / PR-reviewed | No | **Yes** (pipeline as code) |
| CI and CD | Separate **Build pipeline** and **Release pipeline** | One **multi-stage** pipeline for both |
| Reuse | Task groups | Templates (steps/jobs/stages), parameters |
| Approvals | Release pre/post-deployment approvals | **Environments** with approvals and checks |
| Status | Supported but legacy; Microsoft guidance is to use YAML | Recommended |

**Build pipeline** = compile, test, analyse, package, publish *artifacts* (produces an immutable output). **Release pipeline** = take those artifacts through environments (Dev → Test → Prod) with approvals. In YAML both are *stages* of the same file: `Build` stage, then `Deploy*` stages. The golden rule is **build once, deploy the same artifact everywhere**; only configuration changes between environments.

### YAML Anatomy

```text
pipeline
 |- trigger / pr / schedules / resources      when does it run
 |- parameters (compile-time inputs)           ${{ parameters.x }}
 |- variables (plain, groups, Key Vault)       $(x)
 |- pool                                       which agent
 |- stages
     |- stage (Build, DeployDev, DeployProd)   dependsOn, condition
         |- job / deployment job               runs on one agent
             |- steps: task | script | checkout | publish | download | template
```

| Variable syntax | Evaluated | Example |
|---|---|---|
| Template expression `${{ }}` | **Compile time** (before the run) | `${{ parameters.deployTarget }}` |
| Macro `$( )` | Runtime, just before a task runs | `$(Build.BuildId)` |
| Runtime expression `$[ ]` | Runtime, in conditions/variable definitions | `$[ eq(variables.isMain, true) ]` |

Useful predefined variables: `Build.BuildId`, `Build.SourceBranch`, `Build.SourceVersion`, `Build.ArtifactStagingDirectory`, `Pipeline.Workspace`, `Agent.TempDirectory`, `System.AccessToken`.

**Deployment job** (`deployment:`) differs from a normal `job:` — it targets an **environment**, records deployment history, supports strategies (`runOnce`, `rolling`, `canary`) and lifecycle hooks, and **automatically downloads** the pipeline's artifacts into `$(Pipeline.Workspace)/<artifactName>`. It does *not* check out the repo unless you add `- checkout: self`.

### Complete Multi-Stage Pipeline for ASP.NET Core

Build + test + coverage → package + EF script + Docker image to ACR (with scan) → Dev → Prod (App Service slot swap, or AKS canary).

```yaml
# azure-pipelines.yml
name: $(Date:yyyyMMdd)$(Rev:.r)            # run number, e.g. 20261006.1

# ---------- Triggers ----------
trigger:
  batch: true                              # queue one run for several quick pushes
  branches:
    include: [ main, release/* ]
  paths:
    exclude: [ docs/*, '*.md' ]
# For Azure Repos, PR validation is a *branch policy -> Build validation* pointing at
# this pipeline (the `pr:` keyword is for GitHub/Bitbucket repos).

# ---------- Parameters (chosen at queue time) ----------
parameters:
  - name: deployTarget
    displayName: Production target
    type: string
    default: appService
    values: [ appService, aks ]

# ---------- Variables ----------
variables:
  - group: shop-common            # Library group: non-secret values (resource names, URLs)
  - group: shop-secrets-kv        # Group LINKED to Key Vault: secrets fetched at run time
  - name: buildConfiguration
    value: Release
  - name: dotnetVersion
    value: 9.x
  - name: acrName
    value: acrshop
  - name: imageRepository
    value: shop/orders-api

# ---------- Default agent ----------
pool:
  vmImage: ubuntu-latest          # Microsoft-hosted; fresh VM for every job

stages:
# =====================================================================
- stage: Build
  displayName: Build, test, package
  jobs:
  - job: BuildTest
    displayName: Build and unit test
    steps:
    - checkout: self
      fetchDepth: 0               # full history (GitVersion / Sonar blame)

    - task: UseDotNet@2           # pin the SDK so builds are reproducible
      inputs:
        packageType: sdk
        version: $(dotnetVersion)

    - task: NuGetAuthenticate@1   # auth to private Azure Artifacts feed in nuget.config

    - task: DotNetCoreCLI@2
      displayName: Restore
      inputs:
        command: restore
        projects: Shop.sln

    - task: DotNetCoreCLI@2
      displayName: Build
      inputs:
        command: build
        projects: Shop.sln
        arguments: -c $(buildConfiguration) --no-restore /p:TreatWarningsAsErrors=true

    - task: DotNetCoreCLI@2
      displayName: Unit tests with coverage
      inputs:
        command: test
        projects: tests/**/*.Tests.csproj
        arguments: -c $(buildConfiguration) --no-build --collect:"XPlat Code Coverage"
        publishTestResults: true  # TRX results appear in the Tests tab

    - task: PublishCodeCoverageResults@2
      displayName: Publish coverage (Cobertura)
      inputs:
        summaryFileLocation: $(Agent.TempDirectory)/**/coverage.cobertura.xml

    - task: DotNetCoreCLI@2
      displayName: Publish API
      inputs:
        command: publish
        publishWebProjects: false
        projects: src/Shop.Api/Shop.Api.csproj
        arguments: -c $(buildConfiguration) --no-build -o $(Build.ArtifactStagingDirectory)/api
        zipAfterPublish: false

    # Idempotent SQL script from EF migrations (needs .config/dotnet-tools.json with dotnet-ef)
    - script: |
        dotnet tool restore
        dotnet ef migrations script --idempotent --no-build -c ShopDbContext \
          --configuration $(buildConfiguration) \
          --project src/Shop.Infrastructure --startup-project src/Shop.Api \
          --output $(Build.ArtifactStagingDirectory)/sql/migrate.sql
      displayName: Generate EF migration script

    - task: CopyFiles@2           # ship the Kubernetes manifests with the build
      inputs:
        SourceFolder: k8s
        Contents: '**'
        TargetFolder: $(Build.ArtifactStagingDirectory)/k8s

    - publish: $(Build.ArtifactStagingDirectory)   # pipeline artifact named "drop"
      artifact: drop

  - job: DockerImage
    displayName: Build image, scan, push to ACR
    dependsOn: BuildTest          # only after tests are green
    steps:
    - task: Docker@2
      displayName: Build image
      inputs:
        command: build
        containerRegistry: sc-acr-shop       # Docker Registry service connection
        repository: $(imageRepository)
        Dockerfile: src/Shop.Api/Dockerfile
        buildContext: .
        tags: $(Build.BuildId)
    - script: |                              # fail the build on HIGH/CRITICAL CVEs
        docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
          aquasec/trivy:latest image --exit-code 1 --severity HIGH,CRITICAL \
          --ignore-unfixed $(acrName).azurecr.io/$(imageRepository):$(Build.BuildId)
      displayName: Vulnerability scan (Trivy)
    - task: Docker@2
      displayName: Push image
      inputs:
        command: push
        containerRegistry: sc-acr-shop
        repository: $(imageRepository)
        tags: $(Build.BuildId)

# =====================================================================
- stage: DeployDev
  displayName: Deploy to Dev
  dependsOn: Build
  condition: succeeded()
  jobs:
  - deployment: DeployApi
    environment: shop-dev                    # no approvals: automatic
    strategy:
      runOnce:
        deploy:
          steps:                             # artifact "drop" is auto-downloaded
          - task: SqlAzureDacpacDeployment@1 # migrations first (must be backward-compatible)
            displayName: Apply EF migrations
            inputs:
              azureSubscription: sc-shop-dev # ARM service connection (federated identity)
              AuthenticationType: servicePrincipal
              ServerName: sql-shop-dev.database.windows.net
              DatabaseName: ShopDb
              deployType: SqlTask
              SqlFile: $(Pipeline.Workspace)/drop/sql/migrate.sql
          - task: AzureWebApp@1
            displayName: Deploy API
            inputs:
              azureSubscription: sc-shop-dev
              appType: webAppLinux
              appName: shop-api-dev
              package: $(Pipeline.Workspace)/drop/api
              appSettings: -ASPNETCORE_ENVIRONMENT Development
          - script: curl --fail --retry 6 --retry-delay 10 https://shop-api-dev.azurewebsites.net/health/ready
            displayName: Smoke test

# =====================================================================
# Production option A: App Service, deploy to a staging slot, test, swap
- stage: DeployProd
  displayName: Deploy to Prod (App Service)
  dependsOn: DeployDev
  condition: >-
    and(succeeded(),
        eq(variables['Build.SourceBranch'], 'refs/heads/main'),
        eq('${{ parameters.deployTarget }}', 'appService'))
  jobs:
  - deployment: DeployProdApi
    environment: shop-prod        # approvals and checks are configured ON the environment
    strategy:
      runOnce:
        deploy:
          steps:
          - task: SqlAzureDacpacDeployment@1
            displayName: Apply EF migrations
            inputs:
              azureSubscription: sc-shop-prod
              AuthenticationType: servicePrincipal
              ServerName: sql-shop-prod.database.windows.net
              DatabaseName: ShopDb
              deployType: SqlTask
              SqlFile: $(Pipeline.Workspace)/drop/sql/migrate.sql
          - task: AzureWebApp@1
            displayName: Deploy to staging slot
            inputs:
              azureSubscription: sc-shop-prod
              appType: webAppLinux
              appName: shop-api-prod
              deployToSlotOrASE: true
              resourceGroupName: rg-shop-prod
              slotName: staging
              package: $(Pipeline.Workspace)/drop/api
          - script: curl --fail --retry 6 --retry-delay 10 https://shop-api-prod-staging.azurewebsites.net/health/ready
            displayName: Smoke test staging slot
          - task: AzureAppServiceManage@0
            displayName: Swap staging -> production
            inputs:
              azureSubscription: sc-shop-prod
              Action: Swap Slots
              WebAppName: shop-api-prod
              ResourceGroupName: rg-shop-prod
              SourceSlot: staging
              SwapWithProduction: true
          - script: echo "##vso[task.setvariable variable=swapped]true"
            displayName: Remember that the swap happened
          - script: curl --fail --retry 6 --retry-delay 10 https://shop-api-prod.azurewebsites.net/health/ready
            displayName: Smoke test production
          - task: AzureAppServiceManage@0     # automatic rollback = swap back
            displayName: Roll back (swap back)
            condition: and(failed(), eq(variables['swapped'], 'true'))
            inputs:
              azureSubscription: sc-shop-prod
              Action: Swap Slots
              WebAppName: shop-api-prod
              ResourceGroupName: rg-shop-prod
              SourceSlot: staging
              SwapWithProduction: true

# =====================================================================
# Production option B: AKS with a canary rollout (10% then 50% then 100%)
- stage: DeployAks
  displayName: Deploy to Prod (AKS canary)
  dependsOn: DeployDev
  condition: >-
    and(succeeded(),
        eq(variables['Build.SourceBranch'], 'refs/heads/main'),
        eq('${{ parameters.deployTarget }}', 'aks'))
  jobs:
  - deployment: DeployAksCanary
    environment: shop-aks.shop    # <environment>.<Kubernetes resource (namespace "shop")>
    strategy:
      canary:
        increments: [ 10, 50 ]
        deploy:
          steps:
          - task: KubernetesManifest@1
            displayName: Deploy canary $(strategy.increment)%
            inputs:
              action: deploy
              strategy: canary
              percentage: $(strategy.increment)
              manifests: $(Pipeline.Workspace)/drop/k8s/*.yaml
              containers: $(acrName).azurecr.io/$(imageRepository):$(Build.BuildId)
        postRouteTraffic:             # observe the canary before widening
          pool: server
          steps:
          - task: Delay@1
            inputs:
              delayForMinutes: '5'
        on:
          failure:
            steps:
            - task: KubernetesManifest@1   # delete canary, keep stable
              inputs:
                action: reject
                strategy: canary
                manifests: $(Pipeline.Workspace)/drop/k8s/*.yaml
          success:
            steps:
            - task: KubernetesManifest@1   # make the canary version the stable one
              inputs:
                action: promote
                strategy: canary
                manifests: $(Pipeline.Workspace)/drop/k8s/*.yaml
                containers: $(acrName).azurecr.io/$(imageRepository):$(Build.BuildId)
```

Notes on correctness: task input names change between task major versions and the `canary` strategy with Kubernetes assumes service-mesh or replica-based traffic splitting as described in the docs — verify against the current task reference. Pipeline tasks such as `AzureWebApp@1` and `SqlAzureDacpacDeployment@1` run with the identity of the `azureSubscription` service connection.

### Environments, Approvals and Checks

An **environment** (`shop-prod`) is a deployment target abstraction with history, traceability (commit, work items) and **gates**. It is configured in the UI under *Pipelines → Environments*, not in YAML — which is exactly why the YAML file cannot bypass the gate. A pipeline stops at the stage that targets the environment until every check passes.

| Check | What it does |
|---|---|
| **Approvals** | Named people/groups must approve (with timeout, optional "prevent self-approval") |
| **Branch control** | Only allow deployments from `main` / `release/*` |
| **Business hours** | Deploy only within a window |
| **Invoke Azure Function / REST API** | Call your own validation (change-management ticket, feature toggle) |
| **Query Azure Monitor alerts** | Block while there are active alerts (health gate) |
| **Required template** | Pipeline must extend a security-approved template |
| **Exclusive lock** | Only one run deploys to this environment at a time |

**Resources on an environment:** Kubernetes namespaces (and VMs) can be added so deployment jobs target them with the right credentials and show pods/workloads in the UI.

### Deployment Strategies in YAML

| Strategy | Hooks and behaviour | Typical use |
|---|---|---|
| `runOnce` | `preDeploy` → `deploy` → `routeTraffic` → `postRouteTraffic`, then `on: success/failure` | Simple deployments, slot swaps |
| `rolling` | Updates a set of VMs a batch at a time (`maxParallel`); **VM resources only** | IIS/VM farms |
| `canary` | Deploys to a small increment (`increments: [10, 50]`), observes, then promotes or rejects | Kubernetes, VMs |

```yaml
strategy:
  rolling:
    maxParallel: 25%              # at most a quarter of the VMs updated at once
    deploy:
      steps:
      - script: ./deploy.sh
    on:
      failure:
        steps:
        - script: ./rollback.sh
```

:::q What is the difference between a `job` and a `deployment` job?
A `job` just runs steps on an agent. A `deployment` job targets an environment, so it records deployment history, can be gated by approvals and checks, supports `runOnce`/`rolling`/`canary` strategies with lifecycle hooks, and automatically downloads the pipeline artifacts.
:::

:::q How do you prevent someone from deploying to production by editing the YAML?
Approvals and checks live on the *environment*, not in the YAML, and branch policies force PR review of the YAML itself. I can add *branch control* and *required template* checks so the prod stage can only run from `main` through an approved template, and restrict who can edit the environment and service connection.
:::
