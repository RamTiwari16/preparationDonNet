## Git Essentials

### Git Cheat Sheet

**Definition.** Git is a distributed version control system: every clone holds the full history. A commit is an immutable snapshot identified by a SHA; a branch is just a movable pointer to a commit; `HEAD` is a pointer to where you are now.

**Three areas.** Working directory → (`git add`) → staging area/index → (`git commit`) → local repository → (`git push`) → remote.

| Task | Command |
|---|---|
| Clone / init | `git clone <url>` / `git init` |
| Status, short log | `git status -sb` / `git log --oneline --graph --decorate --all` |
| New branch and switch | `git switch -c feature/order-discount` |
| Stage (interactively by hunk) | `git add -p` |
| Commit / fix the last commit | `git commit -m "feat: add discount"` / `git commit --amend` |
| See changes | `git diff` (unstaged), `git diff --staged`, `git diff main...HEAD` |
| Get remote changes | `git fetch` (safe), `git pull --rebase` (fetch + rebase) |
| Publish a branch | `git push -u origin feature/order-discount` |
| Safe force push after rebase | `git push --force-with-lease` |
| Discard file changes | `git restore <file>`; unstage: `git restore --staged <file>` |
| Tag a release | `git tag -a v1.4.0 -m "Release 1.4.0"` then `git push --tags` |
| Who changed this line / find the bad commit | `git blame <file>` / `git bisect start` |
| Delete merged branches | `git branch -d feature/x`, remote: `git push origin --delete feature/x` |

Use **Conventional Commits** (`feat:`, `fix:`, `chore:`) so changelogs and semantic versions can be generated.

### Merge vs Rebase

Both integrate changes from one branch into another.

| | `git merge` | `git rebase` |
|---|---|---|
| Result | New **merge commit**; history keeps real branching | Replays your commits on top of the target; **linear** history |
| Rewrites history? | No | **Yes** (new SHAs) |
| Conflicts | Resolve once | May resolve per replayed commit |
| Safe on shared branches | **Yes** | **No** |
| Best for | Integrating into `main`, preserving context | Cleaning up *your own* feature branch before a PR |

```bash
# Update my feature branch with latest main (my branch is private)
git fetch origin
git rebase origin/main                 # or: git merge origin/main
git push --force-with-lease            # needed after a rebase

# Clean up the last 4 commits before opening the PR
git rebase -i HEAD~4                   # pick / squash / fixup / reword / drop
```

:::warn Golden rule of rebase
Never rebase commits that others have already pulled (shared or protected branches). Rewriting public history makes everyone's local branch diverge. `--force-with-lease` refuses to overwrite remote commits you have not seen, unlike `--force`.
:::

### Squash, Cherry-pick, Stash

**Squash** combines many commits into one — either with interactive rebase or at PR completion ("squash merge"). It produces one clean commit per PR on `main`. The trade-off is that you lose granular history and `git bisect` becomes coarser.

```bash
git merge --squash feature/order-discount     # stages the combined changes
git commit -m "feat: order discount (#1234)"  # one commit on main
```

**Cherry-pick** copies the effect of specific commits onto the current branch (a new commit with a new SHA). Typical use: **backport a hotfix** from `main` to `release/1.4`.

```bash
git switch release/1.4
git cherry-pick -x 9fceb02            # -x appends "(cherry picked from ...)" to the message
git cherry-pick A^..B                 # a range, inclusive
```

**Stash** shelves uncommitted work so you can switch context.

```bash
git stash push -u -m "wip: discount rules"   # -u includes untracked files
git stash list
git stash pop                                 # apply and drop;  `apply` keeps it
git stash drop stash@{1}
```

### Reset vs Revert, and the Reflog

| | `git reset` | `git revert` |
|---|---|---|
| What | **Moves** the branch pointer back | Creates a **new commit** that undoes an old one |
| History | Rewritten | Preserved |
| Use on pushed/shared commits | **No** | **Yes** |
| Use for | Local cleanup | Undoing a bad change that is already on `main` |

| Reset mode | Branch pointer | Staging area | Working files |
|---|---|---|---|
| `--soft` | moved | kept (staged) | kept |
| `--mixed` (default) | moved | reset | kept |
| `--hard` | moved | reset | **overwritten (data loss)** |

```bash
git reset --soft HEAD~1          # undo commit, keep changes staged (redo the message)
git reset --hard origin/main     # throw away all local work: be sure
git revert 9fceb02               # safe undo on shared history
git revert -m 1 <merge-sha>      # undo a merge commit; -m 1 = keep the mainline parent
```

**Reflog** is the local journal of everywhere `HEAD` has been, for about 90 days by default. It is how you recover from a bad `reset --hard`, a deleted branch or a botched rebase.

```bash
git reflog                                   # find the lost state: HEAD@{3}: commit: add tax
git branch rescue HEAD@{3}                   # or: git reset --hard HEAD@{3}
```

:::q I accidentally ran `git reset --hard` and lost commits. Can you recover them?
Yes if they were committed. `git reflog` lists previous `HEAD` positions; I find the SHA from before the reset and run `git reset --hard <sha>` or `git branch rescue <sha>`. Uncommitted working-directory changes cannot be recovered by Git.
:::

### Resolving Merge Conflicts Step by Step

A conflict occurs when two branches change the same lines (or one deletes a file the other edits) and Git cannot decide.

1. **Start the integration:** `git merge origin/main` (or `git rebase origin/main`). Git stops with `CONFLICT (content): Merge conflict in OrderService.cs`.
2. **List the files:** `git status` shows *both modified* under "Unmerged paths".
3. **Open each file** and find the markers:

```text
<<<<<<< HEAD
    var total = subtotal - discount;          // your change (current branch)
=======
    var total = subtotal - discount + tax;    // incoming change
>>>>>>> origin/main
```

4. **Decide the correct result** — often a combination, not a pick-one. Remove the three marker lines. Talk to the author if intent is unclear.
5. **Build and run the tests.** A textually clean merge can still be semantically broken.
6. **Mark resolved:** `git add OrderService.cs`.
7. **Finish:** `git commit` for a merge (`git rebase --continue` for a rebase). To bail out: `git merge --abort` / `git rebase --abort`.
8. Push. Use a merge tool if you prefer: `git mergetool`, or the VS / VS Code three-way editor.

Shortcuts: `git checkout --ours <file>` / `--theirs <file>` takes one side (note: during a *rebase* "ours" and "theirs" are swapped). Enable `git config rerere.enabled true` to reuse earlier resolutions.

**Prevention.** Short-lived branches, frequent `git pull --rebase`, small PRs, avoid mass reformatting, and agree on `.editorconfig`.

:::scenario Conflict in a generated file (`package-lock.json`, EF `ModelSnapshot`)
Do not hand-merge. For the lock file, take one side, run `npm install` and commit. For the EF Core `ShopDbContextModelSnapshot.cs` conflict: resolve by deleting your migration, merging `main`, then **re-creating your migration** with `dotnet ef migrations add` so the snapshot is regenerated. Hand-edited snapshots cause subtle model drift.
:::

## Branching Strategies

### GitFlow vs GitHub Flow vs Trunk-Based

| | GitFlow | GitHub Flow | Trunk-based development |
|---|---|---|---|
| Long-lived branches | `main`, `develop` (+ `release/*`, `hotfix/*`) | `main` only | `main` (trunk) only |
| Feature branches | Long (days-weeks) | Short, PR to `main` | **Very short (hours-1-2 days)** or none |
| Release process | Cut `release/x`, stabilise, merge to `main` and `develop`, tag | Every merge to `main` is deployable | Release from trunk (tag) or short-lived `release/*` |
| Feature hiding | Branches | Merged only when ready | **Feature flags** |
| Suited to | Versioned/installed products, scheduled releases | SaaS/web apps, continuous delivery | High-performing teams, strong CI + tests |
| CI maturity needed | Medium | Medium-high | **High** |
| Drawbacks | Merge pain, slow, two sources of truth | Needs good tests/rollback | Needs discipline, flags, fast pipeline |

```text
GitFlow
main     o------------------o-----------o  (tags v1.0, v1.1)
          \                / \         /
release    \         o----o   \   o---o
            \       /          \ /
develop  o---o--o--o---o--o--o--o---o
              \  /    \  /
feature        o-o     o-o
hotfix                         o--o --> main + develop

Trunk-based
main     o--o--o--o--o--o--o--o--o   (small commits, flags hide unfinished work)
          \/ \/  (branches live < 1 day)
```

**Release branches.** Even in trunk-based flow you may cut `release/2.3` to stabilise a version that customers run, fix bugs there by **fixing on `main` first then cherry-picking** (so fixes never get lost), and tag from it.

**Feature flags** decouple *deploy* from *release*: unfinished code ships dark and is turned on per user, ring or percentage. They also give an instant kill switch (rollback without redeploying).

```csharp
// dotnet add package Microsoft.FeatureManagement.AspNetCore
// (backed by appsettings or Azure App Configuration with refresh)
builder.Services.AddFeatureManagement();

// appsettings.json
// "FeatureManagement": { "NewCheckout": { "EnabledFor": [
//     { "Name": "Percentage", "Parameters": { "Value": 20 } } ] } }

app.MapPost("/checkout", async (IFeatureManager fm, ICheckout oldFlow, ICheckoutV2 newFlow) =>
    await fm.IsEnabledAsync("NewCheckout") ? await newFlow.RunAsync() : await oldFlow.RunAsync());
```

:::warn Feature flag debt
Flags are temporary. Track an owner and removal date, delete the flag and the dead branch of code once rolled out, and test both states while it exists.
:::

:::q Which branching strategy would you pick for a SaaS web app deployed multiple times a day?
Trunk-based or GitHub Flow: short-lived branches, PRs with build validation, deploy from `main` through staged environments, and feature flags to hide incomplete work. GitFlow's long-lived `develop` and release branches slow integration and increase merge pain, so I reserve it for products with scheduled, versioned releases.
:::

## Pull Requests and Azure Repos

### Pull Requests and Branch Policies

**Definition.** A PR proposes merging a source branch into a target, hosting the diff, discussion, automated checks and approvals. It is the gate that protects `main`.

**Branch policies (Azure Repos) / branch protection and rulesets (GitHub):**

| Policy | Effect |
|---|---|
| **Minimum number of reviewers** (+ "prevent requestors approving their own changes") | At least N approvals; reset votes when new commits are pushed |
| **Required reviewers / path-based** | Auto-add owners for `/src/Payments/*` (CODEOWNERS-like) |
| **Build validation** | PR is blocked until the CI pipeline (build + unit tests + analysis) succeeds on the merged result |
| **Check for linked work items** | Traceability from Boards |
| **Check for comment resolution** | All threads must be resolved |
| **Limit merge types** | Allow only squash (or rebase+FF) for a clean history |
| **Status checks** | External checks (security scan, SonarQube quality gate) |
| **No direct push** | Even admins use PRs |

**Merge types in Azure Repos:** *Merge (no fast-forward)*, *Squash merge*, *Rebase and fast-forward*, *Semi-linear merge*.

**Code review checklist.**
- **Correctness:** meets the requirement and acceptance criteria? Edge cases (null, empty, concurrency, time zones)?
- **Tests:** new/changed behaviour covered; tests deterministic and meaningful, not just coverage padding.
- **Design:** single responsibility, naming, no leaky abstractions; respects layer boundaries.
- **Security:** input validated, authorisation checks present, no secrets, SQL injection and XSS safe.
- **Performance:** no N+1 queries, no sync-over-async, `AsNoTracking` for reads, pagination.
- **Operability:** logging with context (no PII), cancellation tokens, meaningful errors, health checks, config not hard-coded.
- **Data:** EF migration reviewed, backward-compatible, has a rollback story.
- **Small PR:** ideally under ~400 changed lines; one concern per PR.

:::tip Reviewer etiquette
Review the code, not the person. Distinguish blocking ("must fix") from nit ("optional"). Approve with comments when only nits remain. A PR waiting over a day is a delivery problem — interviewers like hearing that you review within hours.
:::

### Azure Repos and Azure DevOps Services

**Azure DevOps** is a suite: **Boards** (work items, Kanban/Scrum), **Repos** (Git), **Pipelines** (CI/CD), **Test Plans**, **Artifacts** (NuGet/npm/Maven/Python/universal package feeds). Structure: *Organization → Project → services*. **Azure Repos** provides unlimited private Git repos, PRs, branch policies, and tight integration with Boards (`Fixes #1234` in a PR links and closes the work item) and Pipelines (build validation). You can also keep code in GitHub and still use Azure Pipelines (and use `AB#1234` to link work items).

| | Azure Repos | GitHub |
|---|---|---|
| Home | Azure DevOps (enterprise, Microsoft-centric) | Open source + enterprise |
| Policies | Branch policies | Branch protection / rulesets, CODEOWNERS |
| CI/CD | Azure Pipelines (YAML) | GitHub Actions |
| Security | Advanced Security (GHAzDO) | Advanced Security / Dependabot / secret scanning |
| Choose | Existing ADO org, Boards-driven process, on-prem Server option | Community, Actions ecosystem, Copilot |

```bash
# Clone from Azure Repos over HTTPS (Git Credential Manager signs you in with Entra ID)
git clone https://dev.azure.com/contoso/Shop/_git/shop-api
# Set the remote of an existing repo
git remote add origin https://dev.azure.com/contoso/Shop/_git/shop-api
```

:::q Merge vs squash vs rebase when completing a PR?
Merge keeps full history with a merge commit; squash collapses the PR into a single commit giving a linear, readable `main` (my usual choice); rebase-and-fast-forward replays each commit linearly and keeps granularity. Whichever the team picks should be enforced by branch policy.
:::

:::q What is the difference between `git fetch` and `git pull`?
`fetch` downloads remote changes into remote-tracking branches without touching my working branch. `pull` is fetch plus a merge (or a rebase with `--rebase`) into the current branch. I prefer `fetch` then inspect, or `pull --rebase` on private branches.
:::
