### Git Cheat Sheet

**In simple words:** Git is a version control system. It saves snapshots of your code called *commits*. Every clone has the full history, so you can work offline. A *branch* is just a movable label pointing to a commit. Your changes move from the working folder, to the staging area (`git add`), to your local repository (`git commit`), and then to the server (`git push`).

**Real-life example:** Git is like a photo album of your project. Each commit is a dated photo, and you can always look back or go back to an older photo.

**Interview question:** What is the difference between `git fetch` and `git pull`?

**Simple answer:** `git fetch` downloads new changes from the server but does not change my current branch. `git pull` is fetch plus a merge, or a rebase if I use `--rebase`, into my current branch. I often fetch first and look at the changes, or use `git pull --rebase` on my own branches.

```bash
git switch -c feature/order-discount
git add -p
git commit -m "feat: add discount"
git push -u origin feature/order-discount
```

### Merge vs Rebase

**In simple words:** Both bring changes from one branch into another. *Merge* adds a new merge commit and keeps the real history of branches. *Rebase* replays your commits on top of the other branch, so history becomes a straight line, but your commits get new IDs. Because rebase rewrites history, never use it on branches other people share.

**Real-life example:** Merge is like joining two roads with a junction you can still see on the map. Rebase is like redrawing your road so it looks like it always started from the end of the main road.

**Interview question:** What is the difference between merge and rebase, and when should you not rebase?

**Simple answer:** Merge keeps history as it happened and adds a merge commit. Rebase rewrites my commits to make a linear history. I rebase only my own private feature branch, for example to clean it up before a PR. I never rebase shared branches, and after a rebase I push with `--force-with-lease`.

```bash
git fetch origin
git rebase origin/main
git push --force-with-lease
```

### Squash, Cherry-pick, Stash

**In simple words:** *Squash* joins many commits into one, so `main` gets one clean commit per PR. *Cherry-pick* copies one specific commit onto another branch, for example a hotfix to a release branch. *Stash* puts your unfinished changes aside so you can switch branches, and brings them back later.

**Real-life example:** Squash is like stapling many draft pages into one final report. Cherry-pick is like copying one good recipe from a friend's book. Stash is like putting your half-done work in a drawer while you answer an urgent call.

**Interview question:** When would you use cherry-pick?

**Simple answer:** I use cherry-pick to copy a specific fix from one branch to another, most often to backport a hotfix from `main` to a release branch. It creates a new commit with a new ID. I usually add `-x` so the message shows where it came from.

```bash
git switch release/1.4
git cherry-pick -x 9fceb02
git stash push -u -m "wip"   # later: git stash pop
```

### Reset vs Revert, and the Reflog

**In simple words:** `git reset` moves your branch back to an older commit, which rewrites history. `git revert` adds a new commit that undoes an old one, so history is kept. Use reset only on local commits and revert on shared branches. The *reflog* is Git's local diary of where `HEAD` has been, so you can recover "lost" commits.

**Real-life example:** Reset is like tearing pages out of your notebook. Revert is like writing a new line: "Ignore the mistake on page 5." The reflog is your recycle bin.

**Interview question:** I ran `git reset --hard` and lost commits. Can I get them back?

**Simple answer:** Yes, if they were committed. `git reflog` shows where `HEAD` was before. I find the commit ID and run `git reset --hard <sha>` or create a branch from it. But uncommitted changes that were not saved in Git cannot be recovered.

```bash
git revert 9fceb02        # safe undo on shared branches
git reflog                # find the lost commit
git branch rescue HEAD@{3}
```

### Resolving Merge Conflicts Step by Step

**In simple words:** A *merge conflict* happens when two branches change the same lines and Git cannot decide which to keep. Git marks the conflict in the file with `<<<<<<<`, `=======` and `>>>>>>>`. You choose the correct result, remove the markers, build and test, then mark the file as resolved.

**Real-life example:** Two people edit the same sentence in a shared document. Someone must read both versions and write the final sentence.

**Interview question:** How do you resolve a merge conflict?

**Simple answer:** I run the merge, check `git status` for conflicted files, and open each one. I decide the right code, which is often a mix of both sides, and delete the markers. Then I build and run tests, `git add` the file, and finish with `git commit` or `git rebase --continue`. `--abort` cancels everything.

```text
<<<<<<< HEAD
    var total = subtotal - discount;
=======
    var total = subtotal - discount + tax;
>>>>>>> origin/main
```

### GitFlow vs GitHub Flow vs Trunk-Based

**In simple words:** These are *branching strategies*: team rules for how branches are used. *GitFlow* has long-lived `main` and `develop` branches plus release and hotfix branches. *GitHub Flow* has only `main` and short feature branches merged by PR. *Trunk-based* means everyone merges very small changes into `main` often, and *feature flags* hide unfinished work.

**Real-life example:** GitFlow is like a publisher preparing a printed book edition by edition. Trunk-based is like a news website that publishes small updates all day.

**Interview question:** Which branching strategy would you pick for a SaaS app deployed many times a day?

**Simple answer:** I would pick trunk-based or GitHub Flow: short-lived branches, PRs with build checks, and deploys from `main` through environments. Feature flags hide incomplete work. GitFlow suits products with scheduled, versioned releases, but its long-lived branches cause more merge pain.

### Pull Requests and Branch Policies

**In simple words:** A *pull request* (PR) asks to merge your branch into another, like `main`. Team members review the code and automatic checks run. *Branch policies* are rules that protect `main`, such as "at least two reviewers", "the build must pass" and "no direct pushes".

**Real-life example:** It is like a bank where large payments need a second signature. No single person can move the money alone.

**Interview question:** What branch policies would you set on `main`?

**Simple answer:** I require a PR for every change, at least one or two reviewers with no self-approval, and build validation that runs the build and tests. I also require all comments resolved, a linked work item, squash merge only, and no direct pushes. Sensitive folders get automatic required reviewers.

### Azure Repos and Azure DevOps Services

**In simple words:** *Azure DevOps* is a set of tools: Boards for work items, Repos for Git, Pipelines for CI/CD, Test Plans, and Artifacts for package feeds. *Azure Repos* hosts private Git repositories with PRs and branch policies. It links closely with Boards and Pipelines. You can also keep code on GitHub and still use Azure Pipelines.

**Real-life example:** Azure DevOps is like a full office building with a planning room (Boards), a library (Repos), a factory (Pipelines) and a warehouse (Artifacts).

**Interview question:** When would you choose Azure Repos versus GitHub?

**Simple answer:** I choose Azure Repos when the company already uses Azure DevOps and plans work in Boards. GitHub fits teams that want GitHub Actions, the open-source community and its security tools. Both support PRs and branch protection, so the choice is mostly about the existing tools and process.

### CI vs CD vs Continuous Deployment

**In simple words:** *Continuous Integration* (CI) builds and tests every change automatically. *Continuous Delivery* (CD) means every good build is ready to release and goes to test environments automatically; production needs a manual approval. *Continuous Deployment* goes one step further: every good build goes to production automatically, with no human approval.

**Real-life example:** CI is checking every ingredient as it arrives. Continuous delivery is having every dish ready to serve, waiting for the head chef's OK. Continuous deployment is serving each dish as soon as it is ready.

**Interview question:** What is the difference between continuous delivery and continuous deployment?

**Simple answer:** Both build, test and deploy automatically to lower environments. In continuous delivery, a person approves the production release. In continuous deployment, there is no manual step; every green build goes live. This needs strong tests, feature flags, monitoring and automatic rollback.

### Classic vs YAML, Build vs Release

**In simple words:** Azure Pipelines can be built in two ways. *Classic* pipelines are created in the web UI, with separate Build and Release pipelines. *YAML* pipelines are a file in your repo, so they are versioned and reviewed like code. A build creates the *artifact* (the package to deploy); a release deploys it through environments.

**Real-life example:** Classic is like recipe notes on a whiteboard that anyone can erase. YAML is a printed recipe book with a version history.

**Interview question:** Why prefer YAML pipelines over classic pipelines?

**Simple answer:** YAML lives in the repo, so changes are versioned and reviewed in PRs. One multi-stage file covers both build and deployment, and templates allow reuse. The golden rule is "build once, deploy the same artifact everywhere", changing only the configuration per environment.

### YAML Anatomy

**In simple words:** A YAML pipeline has a clear structure. `trigger` says when it runs. `variables` and `parameters` hold values. `pool` chooses the machine (agent). `stages` contain `jobs`, and jobs contain `steps` (tasks or scripts). `${{ }}` is read before the run starts, while `$( )` is read while the run is happening.

**Real-life example:** It is like a school timetable: the year has terms (stages), terms have classes (jobs), and each class has lessons (steps).

**Interview question:** What is the difference between a normal `job` and a `deployment` job?

**Simple answer:** A normal job just runs steps on an agent. A deployment job targets an environment, so it records deployment history, can wait for approvals, supports strategies like `runOnce` or `canary`, and downloads the build artifacts automatically.

```yaml
trigger: [ main ]
pool: { vmImage: ubuntu-latest }
stages:
- stage: Build
  jobs:
  - job: BuildTest
    steps:
    - script: dotnet build -c Release
```

### Complete Multi-Stage Pipeline for ASP.NET Core

**In simple words:** One YAML file can do everything. The Build stage restores, builds, tests, publishes the API and creates the EF migration script. It can also build a Docker image, scan it and push it. Then Deploy stages send the same artifact to Dev automatically, and to Prod after approval — for example, to a staging slot followed by a swap.

**Real-life example:** It is like a car factory line. Parts are built and tested once, then the same car is driven to the test track and finally to the showroom.

**Interview question:** Walk me through a CI/CD pipeline for an ASP.NET Core API.

**Simple answer:** The Build stage restores, builds, runs tests with coverage, publishes the API and an idempotent migration script, and saves them as one artifact. Dev deploys automatically and runs a smoke test. Prod waits for approval, applies migrations, deploys to a staging slot, tests it, swaps, and swaps back automatically if the health check fails.

```yaml
- stage: DeployProd
  jobs:
  - deployment: DeployProdApi
    environment: shop-prod   # approvals live here
    strategy:
      runOnce:
        deploy:
          steps: [ ... ]
```

### Environments, Approvals and Checks

**In simple words:** An *environment* in Azure Pipelines (like `shop-prod`) is a named deployment target with history. You add *approvals and checks* to it in the web UI, not in YAML. Any stage that deploys to it waits until all checks pass, for example a manager's approval, business hours or no active alerts.

**Real-life example:** It is like a hospital operating room. No matter who books it, the surgery cannot start until the checklist is signed.

**Interview question:** How do you stop someone from deploying to production by editing the YAML?

**Simple answer:** Approvals and checks live on the environment, not in the YAML, so editing the file cannot skip them. YAML changes also go through PR review. I add branch control so only `main` can deploy, and a required template check, and I limit who can edit the environment and the service connection.

### Deployment Strategies in YAML

**In simple words:** Deployment jobs support three strategies. `runOnce` deploys everything in one go and is the most common. `rolling` updates a few VMs at a time. `canary` deploys to a small percentage first, watches it, then goes wider or rolls back. Each strategy has *hooks*, like `deploy` and `on: failure`, where you put steps.

**Real-life example:** `rolling` is like repainting a building one floor at a time while people still work there. `canary` is like testing a new dish on a few tables before adding it to the menu.

**Interview question:** What deployment strategies does Azure Pipelines support?

**Simple answer:** `runOnce` runs all steps once and suits simple deploys and slot swaps. `rolling` updates VMs in batches using `maxParallel`. `canary` deploys to small increments like 10% and then 50%, so I can check metrics and then promote or reject. The `on: failure` hook is where I put rollback steps.

```yaml
strategy:
  rolling:
    maxParallel: 25%
    deploy:
      steps:
      - script: ./deploy.sh
```

### Templates and Reusable Steps

**In simple words:** *Templates* let you write steps, jobs or stages once and reuse them in many pipelines with parameters. This removes copy-paste across many services. A platform team can also make an *extends* template that every pipeline must use, so security steps are always included.

**Real-life example:** It is like a standard form at a bank. Every branch uses the same form, and only fills in the customer's details.

**Interview question:** How do you share pipeline logic across many microservices?

**Simple answer:** I put common steps in a YAML template with parameters and reference it from each pipeline. Shared templates can live in a separate repo, pinned to a version tag. For security, I use an extends template together with the "required template" environment check.

```yaml
steps:
- template: templates/dotnet-build-test.yml
  parameters:
    solution: Shop.sln
```

### Service Connections and Workload Identity Federation

**In simple words:** A *service connection* is how a pipeline logs in to another system, like Azure, a container registry or SonarQube. The recommended Azure type is *workload identity federation*: the pipeline gets a short-lived token, and Entra ID trusts it. There is no secret stored anywhere, so there is nothing to leak or renew.

**Real-life example:** Instead of giving the delivery driver a permanent house key, you give them a one-time code that works only for today's delivery.

**Interview question:** How do you let a pipeline deploy to Azure without storing secrets?

**Simple answer:** I use a service connection with workload identity federation (OIDC). The pipeline gets a short-lived token that Entra ID trusts through a federated credential. I create one connection per environment with least-privilege roles, for example only on the production resource group.

### Agent Pools

**In simple words:** An *agent* is the machine that runs your pipeline jobs, and a *pool* is a group of agents. Microsoft-hosted agents are ready to use and give you a fresh, clean machine every job. Self-hosted agents run on your own machines, often inside your network, so they can reach private resources.

**Real-life example:** Microsoft-hosted agents are like taxis: always clean, but they cannot enter a gated private area. A self-hosted agent is your own company car with a pass for the private car park.

**Interview question:** When would you use a self-hosted agent?

**Simple answer:** I use self-hosted agents when deployments must reach private endpoints in a VNet, when builds need special tools, large caches or GPUs, or for security isolation. The cost is that I must patch and secure them. Scale-set agents or Managed DevOps Pools reduce that work.

### Artifacts: Pipeline Artifacts vs Azure Artifacts

**In simple words:** *Pipeline artifacts* are the files a build produces, like the published API, passed between stages of one run. *Azure Artifacts* is a package feed service that hosts NuGet, npm, Maven or Python packages for many projects to share, with versions that live a long time.

**Real-life example:** A pipeline artifact is like a parcel moving between rooms in one delivery. Azure Artifacts is like a company warehouse where everyone picks up standard parts.

**Interview question:** What is the difference between pipeline artifacts and Azure Artifacts?

**Simple answer:** Pipeline artifacts carry the build output from one stage to the next in the same run, like the deployable "drop". Azure Artifacts hosts versioned packages, like an internal NuGet library, that many projects can install. It can also cache public packages from nuget.org.

```bash
dotnet pack src/Shop.Common -c Release -o ./nupkg
dotnet nuget push ./nupkg/*.nupkg --source "ShopFeed" --api-key az
```

### Secrets Handling in Pipelines

**In simple words:** Never put secrets in YAML or in the repo. Use secret variables or a variable group linked to Key Vault. Secret variables are hidden in logs, and scripts do not get them unless you map them in `env:`. The best option is no secrets at all: workload identity federation and managed identity.

**Real-life example:** It is like a bank teller who never writes a customer's PIN on the counter. They read it from a secure machine only when it is needed.

**Interview question:** How do you keep secrets safe in Azure Pipelines?

**Simple answer:** No secrets in YAML or code. I use a Key Vault-linked variable group or the `AzureKeyVault` task, and I map secrets into `env:` only for the script that needs them. Where possible, I avoid secrets using federated and managed identity. I also restrict service connections, and fork PRs never get secrets.

```yaml
- script: ./smoke.sh
  env:
    API_KEY: $(ThirdPartyApiKey)   # explicit mapping
```

### Database Migrations in Pipelines

**In simple words:** EF Core migrations change the database schema. In a pipeline, you create an *idempotent* SQL script (safe to run many times) or a *migration bundle* (one executable file) during the build. Then you run it in the deploy stage before the new code goes live. Avoid running `Database.Migrate()` when the app starts in production.

**Real-life example:** It is like a builder who first strengthens the floor, then moves the heavy new furniture in — and the old furniture must still fit.

**Interview question:** How do you apply EF Core migrations safely in CD?

**Simple answer:** I generate an idempotent script or bundle in the build and store it as an artifact. The deploy stage runs it before the new code, using a separate identity with schema-change rights. Migrations must be backward compatible (expand, then contract), and I fix problems by rolling forward with a new migration.

```bash
dotnet ef migrations script --idempotent \
  --project src/Shop.Infrastructure --startup-project src/Shop.Api \
  -o migrate.sql
```

### Quality Gates

**In simple words:** A *quality gate* is an automatic check that must pass before code can merge or move to the next stage. Examples: all tests pass, code coverage is above a target, SonarQube finds no serious issues, there are no known vulnerable packages, and the container scan is clean.

**Real-life example:** It is like a factory checkpoint. A product that fails inspection cannot go to the packing line.

**Interview question:** What quality gates would you add to a .NET pipeline?

**Simple answer:** I add unit tests, a coverage target on new code, static analysis with SonarQube, a security scan like CodeQL, a check for vulnerable NuGet packages, a container image scan, and secret scanning. With PR build validation, code cannot merge unless all gates pass.

### Blue-Green vs Canary vs Rolling vs Recreate

**In simple words:** These are ways to release a new version. *Recreate* stops the old version and starts the new one, so there is downtime. *Rolling* replaces servers in batches. *Blue-green* runs a full new copy next to the old one and switches all traffic at once. *Canary* sends a small share of users to the new version first, then more if it looks healthy.

**Real-life example:** Blue-green is like having a second, fully ready kitchen and switching over in one moment. Canary is like letting a few customers taste a new dish before serving it to everyone.

**Interview question:** What is the difference between blue-green and canary deployment?

**Simple answer:** Blue-green switches all traffic between two full environments at once, so rollback is instant, but you need double capacity. Canary moves a small percentage of traffic first and increases it while metrics stay healthy, so fewer users are hit by a bad release. On App Service, a slot swap is blue-green.

### Rollback Strategies

**In simple words:** *Rollback* means going back to the last good version when a release fails. On App Service, you swap the slots back. On AKS, you run `kubectl rollout undo` or deploy the previous image tag. For a feature, you turn its feature flag off. For the database, you usually *roll forward* with a fixing migration.

**Real-life example:** It is like keeping the old key when you change a lock. If the new key does not work, you can still open the door.

**Interview question:** How do you plan for rollback?

**Simple answer:** I plan rollback before the release. I use immutable, versioned artifacts and image tags, never `latest`. Database changes are backward compatible, and feature flags let me turn things off fast. I add an automatic health check after deploy that swaps back or undoes the rollout on failure.

```bash
kubectl rollout undo deployment/orders-api
```

### The Typical Pipeline Flow

**In simple words:** A typical flow starts when a developer pushes a branch and opens a PR. CI builds, tests and runs quality checks. The build creates one artifact (and maybe a Docker image). It deploys automatically to Dev and Staging with tests, then waits for approval to deploy to Prod. After that, monitoring and health checks can trigger an automatic rollback.

**Real-life example:** It is like an airport: check-in (PR), security scan (CI and quality gates), boarding gate (approval), flight (production) and the control tower watching the whole time (monitoring).

**Interview question:** Describe the end-to-end flow from a code change to production.

**Simple answer:** Push a branch, open a PR, and build validation runs. After merge, the pipeline builds, tests, runs quality and security scans, and publishes an artifact. It deploys to Dev, then Staging with tests, then Prod after approval using a slot or canary, with a health gate and automatic rollback.

### GitHub Actions Equivalent

**In simple words:** GitHub Actions is GitHub's CI/CD service, and it is very similar to Azure Pipelines. A *workflow* file holds *jobs*, and jobs hold *steps*. Steps use *actions*, which are like Azure Pipelines tasks. *Environments* with required reviewers give approvals, and `azure/login` with OIDC deploys to Azure without a secret.

**Real-life example:** It is like the same recipe written in two different cookbooks. The words differ, but the cooking steps are the same.

**Interview question:** How do Azure Pipelines concepts map to GitHub Actions?

**Simple answer:** A pipeline becomes a workflow, a task becomes an action, and an agent pool becomes a runner. Environments with approvals become environments with required reviewers. Templates become reusable workflows or composite actions. Service connections become OIDC federated credentials.

```yaml
on: { push: { branches: [ main ] } }
permissions:
  id-token: write
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
```

### DORA Metrics

**In simple words:** DORA metrics are four measures of how well a team delivers software. *Deployment frequency*: how often you release. *Lead time for changes*: time from commit to production. *Change failure rate*: what percentage of releases cause problems. *Time to restore service*: how fast you recover from a failure.

**Real-life example:** It is like measuring a delivery app: how often deliveries go out, how long each takes, how many go wrong, and how fast a wrong order is fixed.

**Interview question:** What are DORA metrics and why do they matter?

**Simple answer:** They are deployment frequency, lead time for changes, change failure rate and time to restore service. The first two measure speed and the last two measure stability. Good teams improve both together through small changes, automated tests, feature flags and good monitoring.
