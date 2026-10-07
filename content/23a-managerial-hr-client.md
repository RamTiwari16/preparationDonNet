## How the Non-Technical Rounds Work

### What each round evaluates

**Definition.** The managerial, HR and client rounds test whether you can *own work, communicate clearly and be trusted in front of a client*. The technical rounds check that you can build it. These rounds check whether people want to work with you.

**Why it matters.** At 2–5 years of experience, most rejections after a good technical round come from four things: a vague project explanation, "we did" answers with no personal ownership, negative talk about the current employer, and badly handled salary or notice-period questions.

| Round | Usually taken by | What they are really checking |
|---|---|---|
| Managerial / techno-managerial | Engineering manager, delivery lead, architect | Depth in *your* project, ownership, decisions, production handling, deadlines |
| Client round | Client's tech lead or product owner (common in services and consulting firms) | Clarity, domain understanding, whether they trust you to work directly with their team |
| HR | HR partner or recruiter | Motivation, culture fit, stability, notice period, salary expectations |

:::tip The three signals in every answer
1. **Ownership**: say "I" and name what you personally did.
2. **Impact**: end with a result (a number, a user outcome, or a lesson).
3. **Structure**: 60–120 seconds, a clear beginning and end, no rambling.

Interviewers forget details. They remember whether you sounded like an owner.
:::

:::warn Every sample in this section is a template
The stories, numbers and project details below are *illustrative examples*. Replace them with your own real experience before the interview. Interviewers probe with follow-ups ("What was the exact query?", "Who approved that?"), and an invented story collapses after two questions. Use real numbers. If you don't know an exact figure, say "roughly" and explain how it was measured.
:::

### The STAR method

**Definition.** STAR is a structure for behavioural answers: **S**ituation (context), **T**ask (your responsibility or goal), **A**ction (what *you* did, step by step, and why), **R**esult (the measurable outcome). Many people add **L** for Learning, which makes it STAR-L.

**Why it matters.** Any question that starts with "Tell me about a time…", "Give an example of…" or "How did you handle…" is behavioural. It is scored on specificity. STAR stops you spending three minutes on background and then forgetting the result.

| Part | Question it answers | Share of the answer | Common mistake |
|---|---|---|---|
| Situation | Where, when, what was going on? | ~15% | Five minutes of backstory |
| Task | What was *your* responsibility? | ~10% | Describing the team's goal, not yours |
| Action | What did *you* do, and why? | ~55–60% | "We" everywhere; no reasoning |
| Result | What changed? Numbers, feedback | ~15–20% | No result, or a result with no number |
| Learning | What would you do differently? | one line | Skipping it on failure questions |

:::example Worked example: "Tell me about a time you improved a process"
**Weak answer:** "We had some deployment issues, so we set up CI/CD and things got better."

**STAR answer (example numbers; replace with your own):**
- **Situation:** "In my current project, releases of our ASP.NET Core order API were manual. A developer published from Visual Studio, copied files to the server and ran SQL scripts by hand. Releases took about half a day, and roughly one in four needed a hotfix because a script or config value was missed."
- **Task:** "I volunteered to automate releases within about one sprint, without blocking feature work."
- **Action:** "First I sat with the senior developer who usually released and wrote down every manual step. Then I built an Azure DevOps YAML pipeline: build, run unit tests, publish one artifact, and deploy that same artifact to dev, QA and prod with approval gates. I moved secrets to Azure Key Vault, generated an idempotent EF Core migration script in the pipeline instead of running scripts by hand, and deployed to an App Service staging slot so we could swap back in about a minute. I demoed it to the team and wrote a one-page runbook."
- **Result:** "Release time dropped from about four hours to around 25 minutes. We had no release-caused hotfixes in the next three months, and because releases became cheap we moved from bi-weekly to weekly releases."
- **Learning:** "I'd involve QA earlier. They later asked for automated smoke tests after deployment, which I should have built from day one."
:::

#### Build a story bank

Prepare 6–8 real STAR stories and map each one to several questions. Write each as five bullet lines (S, T, A, R, L) and rehearse them out loud.

| Story (from your own work) | Questions it can answer |
|---|---|
| A performance fix with before/after numbers | Performance issue, achievement, technical depth |
| A production incident you handled | Production issues, pressure, ownership |
| A design or technology decision | Technical decision, trade-offs, "why X?" |
| A migration or large feature you owned | Biggest challenge, achievement, project explanation |
| A mistake you made | Biggest failure, weakness, learning |
| A disagreement with a teammate or lead | Conflict, difficult team member, influence |
| A requirement change or unhappy stakeholder | Unclear requirements, changes near release, unhappy client |
| Helping or mentoring someone | Leadership, teamwork, 5-year plan |

:::tip One story, many questions
A single good incident story can answer "a production issue", "working under pressure", "a challenge" and "a mistake that was caught". Change the emphasis, not the facts.
:::

## Introduction and Project Questions

### Tell me about yourself

**Definition.** A 60–90 second professional summary. It opens almost every round and it sets the agenda for the follow-ups.

**Why it matters.** Whatever you mention here, the interviewer will ask about. So mention only things you can defend in depth: your strongest stack, your best project and one or two achievements.

**Formula: Present → Past → Future.**
- **Present** (20–30 s): current role, domain, years of experience, core stack, what you own.
- **Past** (20–30 s): how you got here, earlier work, and 1–2 achievements with numbers.
- **Future** (10–15 s): what you want next and why this role fits.

```text
FILL-IN TEMPLATE (60-90 seconds)

PRESENT  I'm a [role] with [N] years of experience, currently at [company / type]
         in the [domain] domain. I work on [backend stack] and [frontend stack],
         on [cloud], and I mainly own [module / responsibility].
PAST     I started at [company / project], working on [earlier tech / domain].
         Since then I have [achievement 1 with a number] and
         [achievement 2: CI/CD, cloud migration, mentoring, production support].
FUTURE   I'm now looking for [type of work / scale / responsibility], which is why
         this role interests me: [one specific link to the job description].
```

:::q Tell me about yourself.
*(Sample for a 3.5-year .NET full-stack developer; adapt every detail.)*

"I'm a full-stack .NET developer with about three and a half years of experience. I currently work at an IT services company on an e-commerce platform for a retail client. On the backend I build REST APIs in ASP.NET Core 8 with EF Core and SQL Server. On the frontend I work mainly in Angular, with some React on an internal tool. Everything runs on Azure: App Service, Azure SQL, Service Bus and Key Vault. Right now I own the order APIs end to end: design, development, code reviews and production support.

I started on a .NET Framework MVC application for an insurance client, where I learned SQL Server properly: stored procedures, indexing and reading execution plans. In my current project I helped migrate our legacy APIs to .NET 8. One thing I'm proud of is bringing our order-history API from around 3 seconds to under 400 milliseconds at p95. I also built our Azure DevOps release pipeline, which cut release time from half a day to about 25 minutes.

Now I'm looking for larger-scale, client-facing work where I can grow from building features to designing solutions. This role's focus on Azure-based .NET modernisation is exactly what I've been doing and want to do more of."
:::

:::tip Tune the emphasis per round
For a technical manager, stress stack and architecture. For HR, stress motivation and growth. For a client round, stress domain knowledge and communication. Keep the skeleton; change the emphasis.
:::

:::warn Avoid in "tell me about yourself"
- Reading your resume line by line, or starting from school and college marks.
- Personal details first (hometown, family). One line at the end is fine if the interviewer is informal.
- Listing 20 technologies. Name 4–6 that you can defend.
- Going past two minutes. Practise with a timer.
:::

### Explain your current project

**Definition.** A structured 2–3 minute walkthrough of the system you work on and your place in it. It is the most important question in the managerial round because most follow-ups come from it.

**Why it matters.** It shows whether you understand the *business* and the *whole system*, or only the tickets assigned to you.

**Structure (memorise this order):**
1. **Business context**: who the client and users are, what problem the system solves, rough scale.
2. **Architecture**: main components and how one request flows.
3. **Your role**: what you own, team size, how you work.
4. **Tech stack**: backend, frontend, data, cloud, DevOps, monitoring.
5. **Challenges**: one or two hard problems you worked on.
6. **Impact**: measurable outcomes.

Sample architecture sketch for an e-commerce order platform:

```text
        Angular SPA (customers)            Angular admin portal (staff)
                 |                                    |
                 +-----------------+------------------+
                                   |  HTTPS + JWT bearer token
                     Azure Front Door -> Azure API Management
                                   |
         +-------------------------+-------------------------+
         |                         |                         |
   Catalog API              Order API (.NET 8)        Payment API (.NET 8)
   + Azure Cache for Redis  EF Core -> Azure SQL      -> external payment gateway
         |                         |                         |
         +------------ Azure Service Bus (topics) -----------+
                                   |
            Worker services: confirmation email, inventory sync, invoices
                                   |
           Application Insights + Log Analytics (logs, traces, alerts)
```

:::q Explain your current project.
*(Sample: e-commerce order platform. Replace with your real project; numbers are examples.)*

"**Business context.** I work on the online ordering platform for a mid-size retail chain. Customers browse the catalog, place orders and pay online. Store staff use an admin portal for fulfilment and refunds. On a normal day it handles around 15–20 thousand orders, with peaks of about five times that during sale events.

**Architecture.** It's three ASP.NET Core 8 APIs (Catalog, Order and Payment) behind Azure API Management, with two Angular front ends. Each API follows Clean Architecture: controllers, an application layer with use-case handlers, a domain layer, and infrastructure with EF Core and Azure SQL. Calls that need an immediate answer go over REST. Anything that doesn't need to happen inside the checkout request, such as emails, inventory sync and invoices, is published to Azure Service Bus and handled by worker services. The catalog is cached in Redis.

**My role.** I'm one of six developers. I own the Order API and the order screens in the admin portal. I take stories from refinement to production: API contract, EF Core model and migrations, Angular screens, unit and integration tests. I review most pull requests that touch orders, and I'm on the production-support rotation.

**Stack.** .NET 8, ASP.NET Core Web API, EF Core, Azure SQL, Angular with RxJS, Redis, Service Bus, Azure DevOps pipelines and Application Insights.

**Challenges.** The biggest one was migrating the legacy .NET Framework order service to .NET 8 without downtime. Later I fixed a slow order-history endpoint that was hurting us during sale peaks.

**Impact.** After the migration we run on fewer App Service instances, order-history p95 went from about 3 seconds to under 400 ms, and checkout failures during the last sale stayed under 0.5%."
:::

```text
PROJECT EXPLANATION TEMPLATE (2-3 minutes)

1. BUSINESS   Client / domain: ____   Users: ____   Problem it solves: ____
              Scale: ___ users, ___ requests or orders per day, ___ data size
2. ARCH       Style: monolith / modular monolith / microservices
              Flow: UI -> gateway -> API(s) -> DB / cache / queue / 3rd party
3. ROLE       Team size: ___   I own: ____   I also: reviews / support / mentoring
4. STACK      Backend ___  Frontend ___  Data ___  Cloud ___  DevOps ___  Logs ___
5. CHALLENGE  Problem: ____  ->  What I did: ____
6. IMPACT     Metric before -> after: ____   Business outcome: ____
```

:::tip Be ready to draw it and trace one request
Many interviewers say "Can you draw it?". Practise drawing your architecture in under two minutes. Then trace one request end to end: "When a customer clicks *Place order*, the Angular app calls `POST /api/orders` through API Management, the Order API validates the token, writes the order in a transaction, publishes `OrderPlaced`, and returns 201 with the order id."
:::

:::warn Project-explanation mistakes
- Starting with the tech stack instead of the business problem.
- Saying only "we": the interviewer can't tell what *you* did.
- Claiming microservices, Kubernetes or Kafka you can't explain. A well-explained monolith scores higher than buzzwords that collapse under follow-ups.
- Sharing confidential client names or figures. Say "a large UK retailer" if your NDA requires it.
:::

### What is your role

**Definition.** The interviewer wants three things: *scope* (what you own), *level* (do you work independently, do others depend on you) and *collaboration* (who you work with).

**Why it matters.** It decides the level you're hired at. "I work on tickets" sounds junior. "I own the order module and review others' code" sounds like a mid-level or senior engineer.

| Area | What to mention |
|---|---|
| Development | Modules you own end to end, backend and frontend |
| Design | API contracts, DB schema, small design decisions you drove |
| Quality | Unit and integration tests, code reviews, static analysis |
| Delivery | Estimation, sprint ceremonies, demos to the client |
| Operations | Production support rotation, monitoring, incident handling |
| People | Onboarding and mentoring juniors, knowledge sharing |

:::q What is your role in the project?
"My title is Software Engineer and I'm one of six developers. Practically, my role has four parts.

First, I own the Order module end to end. I pick up stories in refinement, break them into tasks, estimate, design the API contract with the frontend developer, and build both the ASP.NET Core endpoints and the Angular screens, with unit and integration tests.

Second, I review most pull requests that touch orders and payments, so I'm the go-to person for that area.

Third, I'm on a weekly production-support rotation: I watch Application Insights alerts and handle incidents for our services.

Fourth, I onboard new joiners. Last quarter I mentored two juniors through their first features.

I work daily with the BA and QA, and I join client calls for sprint demos and requirement clarifications."
:::

:::tip Show growth inside the same project
"When I joined I was fixing bugs in the admin portal. Within a year I owned the Order API, and now I review that area." Growth over time is a strong signal.
:::

:::warn Don't inflate your title
If you're a developer, don't say "I architected the whole system". Say "I contributed to the design of X and owned Y." Managers check with "Who made the final call on that?".
:::

### What architecture your project uses

**Definition.** Answer at three levels: *code* architecture (how one service is layered), *deployment* architecture (monolith or services, where it is hosted) and *integration* (synchronous vs asynchronous communication).

**Why it matters.** Interviewers want to see that you know *why* the architecture is the way it is, not just its name.

```text
CODE LEVEL: Clean Architecture (dependencies point inward)

  API             controllers, auth, filters, ProblemDetails  -> uses Application
  Application     use cases, DTOs, validation, interfaces     -> uses Domain
  Domain          entities, value objects, business rules     -> depends on nothing
  Infrastructure  EF Core, Redis, Service Bus, email clients  -> implements interfaces
```

:::q What architecture does your project use, and why?
"I'd describe it at three levels.

**Code level:** each API uses Clean Architecture. Business rules sit in the domain layer with no dependency on EF Core or ASP.NET Core, so they're easy to unit test. Infrastructure implements interfaces defined in the application layer.

**Deployment level:** it's a small set of services (Catalog, Order, Payment), each with its own database schema, deployed to Azure App Service. It's not 30 microservices. We split only where scaling and release cadence were genuinely different. Catalog is read-heavy and cached, and Payment has stricter compliance and release controls.

**Integration level:** REST for anything the user waits for, and Service Bus events for side effects like emails and inventory sync, so a slow email provider can't break checkout.

The trade-off is extra operational work: distributed tracing, idempotent consumers and dead-letter monitoring. If I could change one thing, I'd add the outbox pattern everywhere. Today one service publishes events after the database commit, so there is a small window where an event can be lost."
:::

:::tip Always add "why" and "what I'd change"
Naming the architecture is a junior answer. Explaining why it was chosen and one thing you'd improve is a senior answer. The trade-offs are covered in depth in the Microservices and HLD sections.
:::

### Biggest challenge

**Definition.** A STAR story about a problem that was technically hard, uncertain, or high-stakes, and that *you* helped resolve.

**Why it matters.** It shows how you think when there is no ready answer: how you break down a problem, reduce risk and involve others.

Pick a challenge that has: (1) real technical depth, (2) a constraint (no downtime, deadline, legacy code), and (3) a clear personal contribution and result.

:::q What was the biggest challenge in your project?
*(Example story; replace with your own.)*

"**Situation.** Our order service was a .NET Framework 4.8 Web API on Windows VMs. Releases were slow, it was hard to scale, and we couldn't use modern libraries. The business would not accept a big-bang rewrite or any downtime.

**Task.** I was one of two developers asked to plan and run the migration to .NET 8 while feature work continued.

**Action.** We used the strangler fig pattern. I set up a YARP reverse proxy in front of the legacy API, so all traffic still went to the old service on day one. Then we moved endpoints one at a time, starting with read-only ones. For each endpoint I wrote contract tests that called both the old and the new implementation and compared the JSON. Routing per endpoint was behind configuration, so we could switch back in minutes. Both versions shared the same database at first, so there was no data migration. The hardest part was subtle behaviour differences: date formats, null handling and casing differences between Newtonsoft.Json and System.Text.Json. The contract tests caught most of them before production.

**Result.** Over about four months we moved roughly 40 endpoints with zero downtime and decommissioned the legacy VMs. p95 latency improved by about 30%, and the service moved onto our automated pipeline.

**Learning.** Write the contract tests first. They turned a risky rewrite into a series of small, reversible steps."
:::

:::warn Weak "challenge" answers
"Learning Angular in two weeks" or "the requirements kept changing" with no technical depth or result. Also avoid stories where the challenge was caused by you and never fixed. Save those for the failure question, with a learning.
:::

### Performance issue you solved

**Definition.** A story about making something measurably faster or cheaper, told as **Measure → Find the bottleneck → Fix → Verify → Prevent**.

**Why it matters.** It is the most common "prove your depth" question for full-stack .NET roles. Interviewers listen for *measurement*. "I added caching and it got faster" with no numbers is a red flag.

| Step | What to say | Tools to mention (only if you used them) |
|---|---|---|
| Measure | Baseline p95/p99, throughput, error rate | Application Insights, load test, browser DevTools |
| Find | Which layer: UI, network, API, DB, external call | Dependency traces, Query Store, execution plan, EF Core logging |
| Fix | The smallest change that removes the bottleneck | Index, projection, paging, caching, async, batching |
| Verify | Same test, new numbers, in production too | Dashboards, before/after load test |
| Prevent | Stop it coming back | Alerts, perf test in pipeline, review checklist |

:::q Tell me about a performance issue you solved.
*(Example numbers; use your own measurements.)*

"**Situation.** Customers complained that 'My Orders' was slow, especially during sales. Application Insights showed the order-history endpoint at about 2.8 seconds p95, and Azure SQL CPU spiked whenever traffic grew.

**Task.** I owned the Order API, so I took the investigation.

**Action.** I opened end-to-end traces for slow requests and saw about 20 SQL calls per request. It was an N+1 problem: we loaded orders and then lazy-loaded the lines for each one. The query also loaded full tracked entities with every column, and there was no index on `CustomerId` plus `CreatedAt`, so SQL Server scanned the table. I changed the query to project straight into a summary DTO with `AsNoTracking`, used keyset paging of 20 rows, and added a composite index after checking the execution plan and Query Store. I tested with a load test that replayed production-like traffic.

**Result.** p95 dropped from about 2.8 s to around 350 ms. Queries per request went from about 20 to 1, and database CPU at peak dropped by roughly 40%. I added an alert on that endpoint's p95 and an EF Core query-count check in our integration tests."
:::

```csharp
// Before: full tracked entities, lazy-loaded lines (N+1), no paging
var orders = await db.Orders.Where(o => o.CustomerId == customerId).ToListAsync(ct);

// After: one query, projection to DTO, no tracking, keyset paging
var page = await db.Orders
    .AsNoTracking()
    .Where(o => o.CustomerId == customerId && o.CreatedAt < cursor)
    .OrderByDescending(o => o.CreatedAt)
    .Select(o => new OrderSummaryDto(o.Id, o.CreatedAt, o.Status, o.Total,
                                     o.Lines.Count))
    .Take(20)
    .ToListAsync(ct);
```

```sql
-- Supports "orders for one customer, newest first" without a scan or a sort
CREATE NONCLUSTERED INDEX IX_Orders_CustomerId_CreatedAt
ON dbo.Orders (CustomerId, CreatedAt DESC)
INCLUDE (Status, Total);
```

:::warn Performance-story red flags
- No baseline number, or "it became much faster".
- A fix that hides the problem: a bigger App Service plan or caching everything without finding the root cause.
- Claiming tools you've never opened. Expect "How did you read the execution plan?" as a follow-up.
:::

### A technical decision you made

**Definition.** A story about choosing between real alternatives, told as **Context → Options → Criteria → Decision → Trade-offs accepted → Outcome**.

**Why it matters.** It separates people who implement from people who can be trusted to design. The key word is *trade-off*. Every decision has a cost, and naming it shows maturity.

| Option for post-checkout work | Pros | Cons |
|---|---|---|
| Call email/inventory/invoice inline in the request | Simple, immediately consistent | Slow checkout; one failing provider breaks orders |
| Fire-and-forget `Task.Run` in the API | Fast response | Work is lost on restart; no retries; hard to monitor |
| Azure Service Bus topic + worker services | Decoupled, retries, dead-letter queue, scales separately | Eventual consistency, more infrastructure, consumers must be idempotent |

:::q Tell me about a technical decision you made and its trade-offs.
*(Example; replace with your own.)*

"After checkout, our Order API synchronously sent the confirmation email, updated inventory and generated the invoice. When the email provider was slow, checkout took 6–8 seconds, and if it failed the whole order failed.

I proposed publishing an `OrderPlaced` event to an Azure Service Bus topic and moving the three side effects into worker services. I compared three options: keep it inline, fire-and-forget with `Task.Run`, or a message broker. My criteria were reliability, checkout latency and operational effort. `Task.Run` was ruled out because work is lost if the app restarts. Between Service Bus and Storage Queues, I chose Service Bus because we needed topics for several subscribers, dead-lettering and duplicate detection.

The trade-offs I called out to the team were: emails now arrive a few seconds later, consumers must be idempotent because messages can be delivered more than once, we need to watch the dead-letter queue, and there is a gap between the database commit and publishing. We closed that gap with the outbox pattern.

The result: checkout p95 went from about 6 s to under 1 s, and an email provider outage no longer affected orders. I documented it as a short architecture decision record so new joiners know why it's built that way."
:::

:::tip Write it like an ADR
An Architecture Decision Record is one page: context, options, decision, consequences. Saying "I wrote an ADR" signals that you think about future maintainers.
:::

### Why you chose a particular technology

**Definition.** A justification grounded in *requirements and constraints*, not in personal preference: "We needed X; options were A, B and C; A fit best because…; the cost is…".

**Why it matters.** "Because it's popular" or "because I know it" are weak answers. The interviewer wants to know whether you can evaluate tools.

| Technology | One-line justification you can expand |
|---|---|
| ASP.NET Core | Cross-platform, high performance, built-in DI, config and logging; long-term support releases |
| EF Core | Productivity, LINQ, migrations, change tracking; drop to raw SQL or Dapper for hot paths |
| Dapper | Thin and fast for read-heavy reporting queries; you write and own the SQL |
| SQL Server / Azure SQL | Relational integrity and transactions for orders and payments; team expertise |
| Angular | Opinionated, full framework (routing, forms, DI, HttpClient) suits large enterprise teams |
| React | Flexible library, large ecosystem; you choose routing and state libraries |
| Redis | Shared cache across scaled-out instances, unlike in-memory cache per instance |
| Azure Service Bus | Enterprise messaging: topics, sessions, dead-lettering, duplicate detection |

:::q Why did you use EF Core instead of Dapper or ADO.NET?
"Most of our work is CRUD on a rich domain model (orders, lines, payments), so EF Core gives us the most productivity: LINQ, change tracking, migrations and fewer hand-written mapping bugs. Performance is fine when you use it properly: `AsNoTracking` for reads, projection to DTOs, compiled queries for hot paths, and watching the generated SQL. We still use Dapper for two heavy reporting queries where we wanted full control of the SQL. So it isn't EF Core *or* Dapper. It's EF Core by default and Dapper where measurements show we need it."
:::

:::q Why Angular and not React? (The choice was made before you joined.)
"Honestly, Angular was chosen before I joined, but I can see why it fits. It's a large enterprise app with many forms and a rotating team. Angular gives one standard way to do routing, forms, HTTP and dependency injection, so new developers are productive faster and code looks the same across modules. React would have meant choosing and maintaining our own set of libraries. If we were building a small, highly interactive widget I'd consider React. For this app, Angular's conventions were the right trade-off."
:::

:::tip If you didn't choose it, say so
Don't pretend you made a decision you didn't. "It was chosen before I joined; here's why I think it fits, and here's where I'd reconsider" is honest and still shows judgement.
:::

### How you handle production issues

**Definition.** A disciplined incident process: **Triage → Mitigate → Root cause → Fix → Postmortem**, with communication running through all of it.

**Why it matters.** Every manager has been woken up by an outage. They want someone who restores service first, communicates calmly, finds the real cause and stops it from happening again, without blaming people.

```text
DETECT      alert or user report -> acknowledge, open an incident channel
TRIAGE      who is affected, how many, is money or data at risk? -> set severity
            what changed recently? (deployment, config, traffic, dependency)
MITIGATE    restore service FIRST: roll back / swap slot / feature flag off /
            scale out / fail over. Debug after users are unblocked.
COMMUNICATE status update to stakeholders on a fixed cadence (e.g. every 30 min)
ROOT CAUSE  logs, traces, metrics, release diff -> reproduce -> 5 Whys
FIX         proper fix through PR, tests and pipeline (hotfix branch if urgent)
POSTMORTEM  blameless: timeline, impact, root cause, what went well,
            action items with owners and due dates
```

| Severity | Example | Response |
|---|---|---|
| Sev 1 | Checkout down, data loss, security breach | Immediate, all hands, frequent updates |
| Sev 2 | Major feature degraded, workaround exists | Same day, on-call owner |
| Sev 3 | Minor bug, single user, cosmetic | Normal backlog priority |

:::q How do you handle production issues? Give an example.
*(Example incident; replace with your own.)*

"My rule is: restore service first, then find the root cause, then make sure it can't happen again.

**Detect and triage.** During a promotional campaign, about an hour after a release, Application Insights alerted that checkout failures had jumped from under 0.5% to about 9%. I acknowledged the alert, opened an incident channel and checked impact: real customers couldn't pay, so it was Sev 1. The obvious question was 'what changed?' and the answer was the release an hour earlier.

**Mitigate.** I didn't start debugging in production. With the lead's approval I swapped the App Service staging slot back to the previous version. The failure rate returned to normal in about ten minutes. I posted updates to the business every 15 minutes until then.

**Root cause.** Dependency telemetry showed socket errors when calling the payment gateway. The release diff showed a new payment-status call that created `new HttpClient()` on every request. Under campaign traffic it exhausted the outbound connections available to the app. I reproduced it with a load test in the QA environment.

**Fix.** We switched to a typed client from `IHttpClientFactory` with the standard resilience handler, load-tested it and redeployed the next morning.

**Postmortem.** We ran a blameless postmortem. Action items: a load test for payment flows in the pipeline, an alert on dependency failure rate, a code-review checklist item for `HttpClient` usage, and no releases during campaigns without sign-off."
:::

```csharp
// Root cause (simplified): a new HttpClient per call; connections are not reused
public async Task<PaymentStatus?> GetStatusAsync(string paymentId)
{
    using var client = new HttpClient();                 // anti-pattern under load
    return await client.GetFromJsonAsync<PaymentStatus>(
        $"{_baseUrl}/payments/{paymentId}");
}

// Fix: typed client from IHttpClientFactory + standard resilience pipeline
// (AddStandardResilienceHandler comes from Microsoft.Extensions.Http.Resilience)
builder.Services
    .AddHttpClient<IPaymentGatewayClient, PaymentGatewayClient>(c =>
        c.BaseAddress = new Uri(builder.Configuration["PaymentGateway:BaseUrl"]!))
    .AddStandardResilienceHandler();
```

:::warn Production-issue anti-patterns
- Debugging live while users are failing, instead of rolling back first.
- Editing code or config directly on the production server with no review or record.
- Going silent. Stakeholders forgive outages more easily than silence.
- Blaming a person in the postmortem. Ask "what allowed this to reach production?", not "who did it?".
:::
