## Pipeline Building Blocks

### Templates and Reusable Steps

**Definition.** YAML templates let you define steps, jobs or stages once and reuse them with parameters. They remove copy-paste across 30 microservice pipelines and are the way a platform team enforces standards.

```yaml
# templates/dotnet-build-test.yml  (step template)
parameters:
  - name: solution
    type: string
  - name: configuration
    type: string
    default: Release
  - name: coverageThreshold
    type: number
    default: 80

steps:
- task: DotNetCoreCLI@2
  displayName: Restore + build ${{ parameters.solution }}
  inputs:
    command: build
    projects: ${{ parameters.solution }}
    arguments: -c ${{ parameters.configuration }}
- task: DotNetCoreCLI@2
  displayName: Test
  inputs:
    command: test
    projects: '**/*.Tests.csproj'
    arguments: -c ${{ parameters.configuration }} --no-build --collect:"XPlat Code Coverage"
```

```yaml
# azure-pipelines.yml  (consumer)
steps:
- template: templates/dotnet-build-test.yml
  parameters:
    solution: Shop.sln

# Cross-repo shared templates
resources:
  repositories:
  - repository: platform
    type: git
    name: Platform/pipeline-templates
    ref: refs/tags/v3
# - template: dotnet/build.yml@platform
```

| Template kind | Reuses | Notes |
|---|---|---|
| **Step** template | A list of steps | Most common |
| **Job** / **Stage** template | Whole job or stage (e.g., "deploy to App Service" for any environment) | Parameterise names, service connection, environment |
| **Extends** template | Whole pipeline skeleton the team *must* extend | Combined with the "Required template" environment check to enforce security steps |
| Variable template | Shared variables | `variables: - template: vars/prod.yml` |

Template expressions (`${{ if eq(parameters.x, 'y') }}:`) evaluate at **compile time**, so they can add or remove steps; `condition:` evaluates at run time.

### Service Connections and Workload Identity Federation

**Definition.** A **service connection** is how a pipeline authenticates to an external system: Azure (ARM), Docker registry/ACR, Kubernetes, GitHub, SonarQube, npm/NuGet feeds. It is a stored, permission-controlled credential reference.

| Azure connection type | How it authenticates | Secret to rotate? |
|---|---|---|
| **Workload identity federation (OIDC)** — recommended | Pipeline presents a short-lived Azure DevOps-issued OIDC token; Entra trusts it through a **federated credential** on an app registration or managed identity | **No** |
| Service principal with secret/cert | Client secret/cert stored in the connection | Yes (expires; can leak) |
| Managed identity (self-hosted agent on Azure) | Agent VM's identity | No |

Practices: one connection per environment (`sc-shop-dev`, `sc-shop-prod`) with **least-privilege RBAC** (for example `Contributor` only on `rg-shop-prod`, or `Website Contributor`); restrict the connection to specific pipelines; require approval for prod connection use; never grant subscription-wide Owner. Create it with *Automatic* app registration for WIF or manually link an existing identity and federated credential (issuer `https://vstoken.dev.azure.com/<org-id>`; verify the exact subject format in the docs).

### Agent Pools

An **agent** is the machine that runs jobs; a **pool** is a group of agents.

| | Microsoft-hosted | Self-hosted |
|---|---|---|
| Setup | None; `vmImage: ubuntu-latest` / `windows-latest` | You install the agent on a VM/container |
| Clean state | **Fresh VM per job** | Persistent unless you automate cleanup |
| Hardware | Fixed, shared size; time limits per job | Any size, GPUs, big caches |
| Network | Public internet; cannot reach private VNet resources | **Inside your VNet / on-prem**, can hit private endpoints |
| Cost | Free grant of parallel jobs (public repos get more), then buy parallelism | You pay for the VMs (use scale-set agents) |
| Maintenance | Microsoft patches images | You patch and secure |

Use **self-hosted** (preferably *VM scale set agents* or Managed DevOps Pools) when deployments must reach private endpoints, builds need licensed tools or heavy caches, or security requires isolation. A **parallel job** limit controls how many jobs run concurrently.

### Artifacts: Pipeline Artifacts vs Azure Artifacts

| | Pipeline artifacts | Azure Artifacts (feeds) |
|---|---|---|
| Purpose | Pass build output between jobs/stages; keep the deployable "drop" for a run | **Package management**: host NuGet, npm, Maven, Python, universal packages |
| Lifetime | Tied to the run's retention policy | Versioned, long-lived packages |
| Used by | `publish:` / `download:` / deployment jobs | `dotnet restore`, `npm install`, `nuget push` |
| Features | Fast upload/download, dedupe | Upstream sources (nuget.org cache), views (`@prerelease`, `@release`), retention, permissions |

```bash
# Publish an internal shared library as a NuGet package
dotnet pack src/Shop.Common -c Release -o ./nupkg
dotnet nuget push ./nupkg/*.nupkg --source "ShopFeed" --api-key az
```

### Secrets Handling in Pipelines

- **Never** commit secrets or write them into YAML. Do not `echo` them; secret variables are masked as `***` in logs but masking is best-effort.
- **Secret variables** (lock icon in the UI or variable group) are **not exposed to scripts automatically**; map them explicitly: `env: { SQL_PASSWORD: $(SqlAdminPassword) }`.
- **Variable group linked to Key Vault** (`shop-secrets-kv`): the pipeline fetches current values at run time using a service connection that has `Key Vault Secrets User`/*Get, List* rights; only the secrets you select are exposed.
- **`AzureKeyVault@2` task** pulls secrets into variables inside a job.
- Prefer **no secrets at all**: workload identity federation for Azure, managed identity at runtime, Entra auth to SQL.
- Fork PRs and untrusted code must not get access to secrets; restrict who can run pipelines against `main` and protect service connections and environments.

```yaml
- task: AzureKeyVault@2
  inputs:
    azureSubscription: sc-shop-prod
    KeyVaultName: kv-shop-prod
    SecretsFilter: 'ThirdPartyApiKey,SmtpPassword'
    RunAsPreJob: false
- script: ./smoke.sh
  env:
    API_KEY: $(ThirdPartyApiKey)       # explicit mapping for secrets
```

### Database Migrations in Pipelines

Three common ways to ship EF Core migrations:

| Approach | How | Pros | Cons |
|---|---|---|---|
| **Idempotent SQL script** | `dotnet ef migrations script --idempotent -o migrate.sql`; run with `SqlAzureDacpacDeployment@1` or `sqlcmd` | Reviewable, DBAs can approve, no .NET SDK on target | Must manage the identity running it |
| **Migration bundle** | `dotnet ef migrations bundle --self-contained -r linux-x64 -o efbundle` then `./efbundle --connection "$CONN"` | One executable artifact, runs anywhere (also in a K8s Job) | Larger artifact; connection string needed |
| **`Database.Migrate()` at startup** | App migrates itself | Simple for demos | **Avoid in production**: races between instances, app needs DDL rights, failed migration blocks startup |

```yaml
- script: |
    dotnet ef migrations bundle --self-contained -r linux-x64 \
      --project src/Shop.Infrastructure --startup-project src/Shop.Api \
      -o $(Build.ArtifactStagingDirectory)/efbundle --force
  displayName: Build migration bundle
```

Rules: run migrations as a **separate deployment step** before the new code; use a **dedicated higher-privileged identity** for DDL (the runtime app identity only gets read/write); make migrations **backward compatible** (expand/contract) so the previous app version still works; take a backup or rely on point-in-time restore before risky changes; prefer **roll-forward** over down-migrations in production.

### Quality Gates

A gate is an automated check that must pass before the pipeline continues or a PR can merge.

| Gate | Tool | Fails when |
|---|---|---|
| Unit tests | `dotnet test` | Any failing test |
| Coverage threshold | coverlet (`/p:Threshold=80`) / Cobertura policy | Coverage on **new code** below target |
| Static analysis / code smells | **SonarQube / SonarCloud**, Roslyn analyzers | Quality Gate not "Passed" (bugs, vulnerabilities, duplication, hotspots) |
| **SAST** | GitHub **CodeQL**, GitHub Advanced Security for Azure DevOps, Semgrep | Injection, insecure crypto, etc. |
| Dependency vulnerabilities (SCA) | `dotnet list package --vulnerable --include-transitive`, Dependabot, OWASP Dependency-Check | High/critical CVEs |
| Container scan | Trivy, Defender for Containers | HIGH/CRITICAL image CVEs |
| Secret scanning | Push protection, gitleaks | Credentials in commits |
| DAST / smoke | OWASP ZAP, Playwright against staging | Alerts or failed journeys |

```yaml
- task: SonarQubePrepare@6        # (SonarCloudPrepare@3 for SonarCloud)
  inputs:
    SonarQube: sc-sonarqube
    scannerMode: dotnet
    projectKey: shop-api
- task: DotNetCoreCLI@2
  inputs: { command: build, projects: Shop.sln }
- task: SonarQubeAnalyze@6
- task: SonarQubePublish@6
  inputs: { pollingTimeoutSec: '300' }    # waits for the Quality Gate result
```

Task versions change; check the Marketplace extension's current docs. A PR *build validation* policy plus a **Quality Gate** check means "no merge unless clean as you code".

## Release Strategies and Rollback

### Blue-Green vs Canary vs Rolling vs Recreate

| Strategy | How it works | Downtime | Rollback speed | Extra cost | Risk exposure | Needs |
|---|---|---|---|---|---|---|
| **Recreate** | Stop old, start new | **Yes** | Slow (redeploy) | None | All users | Nothing |
| **Rolling** | Replace instances in batches | None (if backward compatible) | Medium (roll again) | Little | Gradual | Health probes, compatible versions |
| **Blue-Green** | Run full new stack (green) beside old (blue); flip traffic at once | None | **Instant** (flip back) | **Double** capacity during release | All at flip time (but pre-tested) | Router/slot swap, DB compatibility |
| **Canary** | Send 5-10% of traffic to new version, watch metrics, widen | None | Fast (route to 0%) | Small | **Small slice first** | Traffic splitting + good metrics |

**Slot swap = blue-green on App Service.** The staging slot is "green"; swap flips the virtual IP routing, and swapping back is the instant rollback. For AKS: blue-green with two Deployments and a Service selector flip (or Ingress/mesh weights); rolling update is the Kubernetes default; canary via Argo Rollouts/Flagger/Istio or the Azure Pipelines canary strategy. Front Door/Application Gateway weighted routing can canary across App Services.

### Rollback Strategies

| Layer | Rollback mechanism |
|---|---|
| App Service | Swap slots back; or redeploy the previous artifact (pipeline run "Redeploy") |
| AKS | `kubectl rollout undo deployment/orders-api`; or re-deploy previous image tag; Helm `helm rollback` |
| Feature | Turn the **feature flag** off (fastest, no deploy) |
| Container image | Deploy previous immutable tag (never `latest`) |
| Database | **Roll forward** with a fix migration; restore from point-in-time backup only as last resort. Keep schema changes backward compatible |
| Automated | Health-check/alert gate after deploy; failed → swap back or `rollout undo` |

:::tip Interview line
"Rollback is a design decision made before release: immutable artifacts, backward-compatible DB changes, feature flags and a one-command way back. I measure it through change failure rate and time to restore."
:::

## Pipeline Flow, GitHub Actions and DORA

### The Typical Pipeline Flow

```text
Developer -> git push (feature branch) -> Pull Request
    |                                          |
    |        build validation (CI) <-----------+
    v
 Build -> Unit tests + coverage -> Code quality (Sonar, SAST, SCA)
    -> Docker build -> Image scan -> Push to ACR  -> Artifact (drop)
    -> Deploy Dev (auto) -> Smoke/integration tests
    -> Deploy Staging (auto) -> Load/E2E tests
    -> [Approval + checks] -> Deploy Prod (slot / canary) -> Health gate
    -> Monitor (App Insights alerts)  -> Auto-rollback on failure
```

### GitHub Actions Equivalent

```yaml
# .github/workflows/ci-cd.yml
name: ci-cd
on:
  push:    { branches: [ main ] }
  pull_request: { branches: [ main ] }

permissions:
  id-token: write            # allow OIDC token for azure/login
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-dotnet@v4
        with: { dotnet-version: 9.0.x }
      - run: dotnet restore
      - run: dotnet build -c Release --no-restore
      - run: dotnet test -c Release --no-build --collect:"XPlat Code Coverage"
      - run: dotnet publish src/Shop.Api -c Release --no-build -o ./publish
      - uses: actions/upload-artifact@v4
        with: { name: api, path: ./publish }

  deploy-prod:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production                 # required reviewers = approval gate
    steps:
      - uses: actions/download-artifact@v4
        with: { name: api, path: ./publish }
      - uses: azure/login@v2                # federated credential, no secret
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - uses: azure/webapps-deploy@v3
        with:
          app-name: shop-api-prod
          slot-name: staging
          package: ./publish
```

| Azure Pipelines | GitHub Actions |
|---|---|
| Pipeline / stage / job / step | Workflow / (n/a) / job / step |
| Task (`DotNetCoreCLI@2`) | Action (`actions/setup-dotnet@v4`) |
| Environment + approvals/checks | Environment + required reviewers + protection rules |
| Variable group, Key Vault link | Secrets and variables (+ OIDC to Key Vault) |
| Service connection | OIDC federated credential / secrets |
| Template | Reusable workflow / composite action |
| Agent pool | Runner (hosted / self-hosted) |

### DORA Metrics

Four research-backed measures of delivery performance (from the DevOps Research and Assessment programme; recent reports also add rework rate):

| Metric | Measures | Elite-level target (rough) |
|---|---|---|
| **Deployment frequency** | How often you ship to production | On demand, multiple per day |
| **Lead time for changes** | Commit to running in production | Under a day |
| **Change failure rate** | % of deployments causing a failure/rollback/hotfix | Around 5% or lower |
| **Time to restore service (MTTR)** | How fast you recover from a failure | Under an hour |

Speed (the first two) and stability (the last two) improve *together* with small batches, trunk-based development, test automation, feature flags and good observability.

## Quick-fire Q&A

:::q CI vs continuous delivery vs continuous deployment?
CI builds and tests every change automatically. Continuous delivery keeps every green build releasable and deploys to lower environments automatically, with a manual approval for production. Continuous deployment removes that approval and releases every green build automatically.
:::

:::q Why prefer YAML pipelines over classic?
YAML lives in the repo so it is versioned, reviewed in PRs, branchable and reusable through templates, and one file covers build and multi-stage deployment. Classic UI pipelines drift, cannot be code-reviewed and are the legacy path.
:::

:::q How do you authenticate a pipeline to Azure without secrets?
A service connection using workload identity federation: the pipeline gets a short-lived OIDC token and Entra exchanges it through a federated credential on an app registration or managed identity. There is no client secret to store, leak or rotate.
:::

:::q What is the difference between `git merge` and `git rebase`, and when do you not rebase?
Merge preserves history with a merge commit; rebase replays my commits to produce linear history and rewrites SHAs. I rebase only my own unpushed or private branches and never shared branches.
:::

:::q How do you resolve a merge conflict?
Run the merge, open each conflicted file, decide the correct combination between the `<<<<<<<` and `>>>>>>>` markers, remove the markers, build and test, `git add`, then `git commit` (or `rebase --continue`). `--abort` backs out.
:::

:::q Reset vs revert?
Reset moves the branch pointer and rewrites history, so use it on local commits only. Revert adds a new commit that undoes an old one and is safe on shared branches like `main`.
:::

:::q GitFlow vs trunk-based development?
GitFlow uses long-lived develop and release branches suited to scheduled, versioned releases. Trunk-based uses very short-lived branches into main with feature flags and strong CI, which suits continuous delivery. Trunk-based gives fewer merge conflicts and faster feedback.
:::

:::q What branch policies would you set on `main`?
Require a PR, minimum 1-2 reviewers with no self-approval, build validation that runs build and tests, comment resolution, linked work item, squash-only merge, and no direct pushes. Path-based required reviewers for sensitive areas.
:::

:::q How do you do zero-downtime deployment to App Service?
Deploy to a staging slot, warm up and smoke test it, then swap. Swap re-routes traffic to the warm instances; if metrics degrade, swap back. Database changes must be backward compatible because both versions share the database.
:::

:::q Blue-green vs canary?
Blue-green switches all traffic between two full environments at once, with instant rollback but double capacity. Canary shifts a small percentage first and increases it as metrics stay healthy, limiting blast radius but needing traffic splitting and good observability.
:::

:::q How do you apply EF Core migrations safely in CD?
Generate an idempotent SQL script or a migration bundle in the build, store it as an artifact, and run it in the deploy stage before the new code using a dedicated DDL identity. Migrations are backward compatible and I roll forward rather than writing down-migrations for production.
:::

:::q Pipeline artifacts vs Azure Artifacts?
Pipeline artifacts carry build output between stages of a run, for example the deployable drop. Azure Artifacts is a package feed for NuGet/npm/Maven packages that are shared across projects and versioned long-term.
:::

:::q Microsoft-hosted vs self-hosted agents?
Microsoft-hosted agents are maintained, clean per job and zero setup but live on the public internet. Self-hosted agents run in my network so they can reach private endpoints, can be larger and cached, but I must patch and secure them.
:::

:::q How do you keep secrets safe in Azure Pipelines?
No secrets in YAML or the repo; use a Key Vault-linked variable group or the Key Vault task, map secrets explicitly into `env:` when a script needs them, rely on federated identity and managed identity where possible, and restrict service connections and environments.
:::

:::q What are DORA metrics?
Deployment frequency, lead time for changes, change failure rate and time to restore service. Together they measure the speed and stability of delivery, and I use them to show whether pipeline improvements actually help.
:::
