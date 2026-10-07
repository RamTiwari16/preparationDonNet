## Behavioural Questions

:::warn Reminder: these are templates
Every story below is an *example*. Swap in your own situations, people and numbers. A real, smaller story told well beats an impressive story you can't defend under follow-up questions.
:::

### Why this company

**Definition.** A short answer that links three things: *what the company does*, *what you want next* and *what you bring*. It needs at least one specific fact you found yourself.

**Why it matters.** It tests whether you researched the company and whether you'll stay. "It's a big brand" or "good work-life balance" tells them nothing.

**How to research (30–45 minutes is enough):**
1. **Job description**: underline the stack, the domain and words like "client-facing", "modernisation" or "migration". Your answer should echo them.
2. **Company website**: services, industries, the practice or business unit you're joining, recent news and press releases, annual or impact report.
3. **Technology partnerships**: for example Microsoft or Azure partner status. Check it on the company's or Microsoft's own pages; don't assume.
4. **LinkedIn**: your interviewers' profiles, people in the same team, recent posts from the practice.
5. **Employee review sites**: the interview process and team culture, taken with a pinch of salt.
6. Pick **one specific fact** to mention and **one question** to ask at the end.

```text
WHY-THIS-COMPANY TEMPLATE

1. THE WORK     "I'm interested in [company] because of the kind of work:
                 [what the role/practice does, in your words]."
2. SPECIFIC     "When I researched, I saw [one fact from YOUR research: a recent
                 project, initiative, practice area or partnership], and that
                 matches [your experience or interest]."
3. GROWTH       "It's the next step I want: [exposure / scale / responsibility]."
4. CONTRIBUTION "And I can contribute from day one with [2 skills from the JD]."
```

:::q Why do you want to join Deloitte? (Or any consulting/services firm.)
*(Template answer. Fill the bracket with a fact you verified yourself; don't quote facts you haven't checked.)*

"Three reasons. First, the consulting model. I've spent three years on one client and one domain, and I want exposure to different clients and industries, and to more client-facing work. A technology consulting practice gives exactly that.

Second, when I researched the team, I saw [specific item from your research, e.g. the practice's focus on cloud modernisation, a recent client case study, or the Microsoft partnership described on their site]. That's the work I've been doing: I migrated a .NET Framework service to .NET 8 on Azure.

Third, the role. The job description mentions ASP.NET Core APIs, Azure and working with client stakeholders. I do the first two every day and I've started doing the third in sprint demos, so I can contribute quickly and grow into the client-facing side."
:::

:::warn Avoid in "why this company"
- Invented or unverified facts ("you're the biggest in…"). One wrong fact undoes the whole answer.
- Answers that fit any company: "good brand", "good culture", "work-life balance".
- Salary, onsite opportunities or "a friend works here" as the main reason.
- Reading the company's website back to them. Connect the fact to *you*.
:::

### Why are you changing jobs

**Definition.** A positive, forward-looking reason: you are moving *toward* something (scale, ownership, domain, technology), not *running away* from something.

**Why it matters.** The interviewer is checking two risks: will you leave here for the same reason, and will you talk about *them* this way later?

| What you might actually feel | What to say instead |
|---|---|
| Same work for three years, bored | "I've learned this domain well; I want exposure to new domains and larger scale." |
| No promotion or growth | "I'm ready for more ownership, design and client-facing work, and that's limited in my current setup." |
| Difficult manager | "I'm looking for a team with a strong engineering culture and mentorship." |
| Legacy technology | "I want to work on modern cloud-native .NET and Azure at scale." |
| Pay is below market | Mention only if asked: "Market alignment is a factor, but the main reason is growth." |
| Laid off | "My role was affected by a restructuring that impacted [N] people. Since then I've [upskilled / certified / freelanced]." |

:::q Why are you looking for a change?
"I've had a great learning curve in my current company. I went from fixing bugs to owning the order APIs and the release pipeline. But I've worked on the same client and domain for three years, and the next things I want, which are designing solutions, working with multiple clients and larger-scale Azure work, aren't really available in my current setup. So this is about the next step, not about leaving something behind. This role is a direct match for that step."
:::

:::warn Never say
- Anything negative about your manager, team, company or client, even if it's true.
- "Only for money" or "I'm bored".
- A lie about a layoff or termination. Background checks and reference calls will find it. Be brief and factual.
- A reason this company also has ("too much travel" when the role involves travel).
:::

### Where you see yourself in 5 years

**Definition.** A realistic growth path that fits the company: a direction (technical lead, solution architect, engineering manager), the skills you'll build, and the value you'll add along the way.

**Why it matters.** They check ambition, self-awareness and whether your plan fits here. Five years is longer than many people stay, so a plan that works *inside* this company is reassuring.

```text
YEAR 1-2   Become a strong, trusted contributor here: own modules, learn the
           domain and client, deepen Azure + system design, earn a cloud cert.
YEAR 3-5   Lead: technical lead for a team or workstream, own designs, mentor
           developers, handle client technical discussions.
```

:::q Where do you see yourself in five years?
"In five years I see myself as a technical lead or solution architect on .NET and Azure projects. I'd own the design of systems, mentor a small team and be the person clients talk to about technical decisions.

To get there, in the first year or two I want to be a strong contributor here: own modules, learn the clients' domains, get deeper into system design and complete an Azure architecture certification. After that I'd like to lead a workstream. I like that this firm has a clear path from developer to lead and architect, so I can grow here rather than having to move again."
:::

:::warn Avoid
"I don't know", "in your position", "running my own startup", "doing an MBA and moving to management elsewhere", or a plan that has nothing to do with the role.
:::

### Biggest achievement

**Definition.** A STAR story where *you* drove a result that mattered to the business, ideally beyond pure coding (ownership, initiative, impact on users or on another team).

**Why it matters.** It shows what you value and what "good work" means to you. Business impact beats technical cleverness.

:::q What is your biggest professional achievement?
*(Example story; replace with your own.)*

"**Situation.** Our finance team reconciled online payments against orders manually every month. They exported reports from the payment gateway and the database into Excel and matched them by hand. It took two people about two days a month, and mismatches were often found weeks late.

**Task.** Nobody owned this problem because it sat between finance and engineering. I offered to own it.

**Action.** I met the finance lead to understand their exact matching rules and exceptions. I built a nightly worker service that pulls settlement data from the gateway's API, matches it against orders in SQL Server, and flags mismatches by category: missing payment, amount mismatch, duplicate charge. I added a simple Angular screen where finance can review and resolve exceptions, with an audit trail. I shipped it in small increments and asked finance for feedback after each one.

**Result.** Manual effort dropped from about two days to roughly two hours a month. Mismatches are now caught the next day instead of weeks later, and in the first quarter we found a duplicate-charge bug in a refund flow early. The finance lead mentioned it in my appraisal. That's why I'm proud of it: it solved a real business problem no one had picked up."
:::

:::tip Pick impact over complexity
"I built a microservice" is weaker than "I removed two days of manual work a month for the finance team". Lead with the business outcome; keep the tech as supporting detail.
:::

### Biggest failure

**Definition.** A real mistake that *you* owned, how you handled it, and what you changed so it doesn't happen again. Use STAR-L, with most of the time on Action and Learning.

**Why it matters.** It tests honesty, ownership and whether you learn. "I've never really failed" is the worst possible answer.

| Good failure story | Bad failure story |
|---|---|
| Your own mistake, honestly owned | Someone else's mistake ("my team failed to…") |
| Moderate impact, quickly contained | A disaster with no fix, or something trivial |
| Clear, specific learning and a changed habit | Vague learning: "I learned to be careful" |
| Happened a while ago; you've shown the change since | Happened last week, still unresolved |

:::q Tell me about your biggest failure.
*(Example story; replace with your own.)*

"Early in my current project I added an index to the `Orders` table through an EF Core migration. It looked harmless and passed in QA, where the table was small. Our pipeline applied migrations automatically during deployment. In production the table had tens of millions of rows. The index build blocked writes, and for about six minutes during business hours checkouts were slow and some timed out.

I raised it in the incident channel straight away, explained it was my migration, and we waited for the index build to finish rather than cancelling it halfway. After that I wrote the postmortem myself.

What I changed: schema changes on large tables now go out as reviewed SQL scripts with `ONLINE = ON` where the database tier supports it, scheduled in a low-traffic window. I added a pipeline check that flags migrations touching large tables, and I test migrations against a copy of production-sized data. In the two years since, we've had no migration-related incidents. The bigger lesson for me was that 'it works in QA' means nothing if QA doesn't look like production."
:::

:::warn Don't disguise a strength as a failure
"I worked so hard I burned out" or "I cared too much about quality" sounds rehearsed. Pick a genuine mistake with a real cost and a real fix.
:::

### Strengths

**Definition.** Two or three strengths that matter for *this role*, each backed by a short piece of evidence.

**Why it matters.** Anyone can say "I'm a team player". Evidence is what makes a strength believable.

| Strength | Evidence line you can adapt |
|---|---|
| Ownership | "I took the reconciliation problem nobody owned and shipped it end to end." |
| Debugging and problem-solving | "I'm usually the one pulled in for hard production issues; I start from data: traces, logs, query plans." |
| Communication with non-technical people | "Our BA asks me to join client calls because I explain technical issues in business terms." |
| Learning quickly | "I picked up Angular in my first project and shipped a production feature within a month." |
| Reliability | "When I commit to a sprint item, I deliver it or raise a risk early. No surprises on demo day." |

:::q What are your strengths?
"I'd pick three. First, ownership. I treat a module as mine from requirement to production. For example, I own our order APIs, including their alerts and incidents. Second, problem-solving from data. When something is slow or failing, I go to traces, logs and execution plans before guessing. That's how I took our order-history endpoint from about 3 seconds to under 400 ms. Third, communication. I can explain a technical problem in business terms, which is why our BA often pulls me into client calls. I think all three fit a client-facing role like this one."
:::

### Weaknesses

**Definition.** A *genuine* weakness that doesn't disqualify you from the role, plus the concrete steps you're taking and evidence that it's improving.

**Why it matters.** It tests self-awareness and honesty. The improvement plan matters more than the weakness itself.

Good options for a developer (pick what is actually true for you):
- **Asking for help too late**: trying to solve everything alone.
- **Saying yes to too much**: over-committing, then working late.
- **Presenting to large groups**: fine one-to-one, nervous in big meetings.
- **A non-core skill gap**: advanced CSS layouts, Kubernetes, or performance testing, if it isn't central to the job.

:::q What is your biggest weakness?
"I tend to try to solve problems on my own for too long before asking for help. In one sprint I spent almost two days on an authentication token issue that a colleague who knew our identity setup solved in about 30 minutes. That delayed a story and taught me that being stuck alone isn't being independent; it's just slow.

What I do now is time-box. If I've made no progress in about two hours, I write down what I've tried and ask someone. Writing it down often solves it, and when it doesn't, the other person can help much faster. My last two sprints had no spillover from being blocked, and my lead mentioned it in my last one-to-one. I still have to remind myself, but it's a habit now."
:::

:::warn Weakness answers that backfire
- Humblebrags: "I'm a perfectionist", "I work too hard". Interviewers have heard them a thousand times.
- A weakness central to the job: "I don't like writing code" or "I struggle with SQL" for a full-stack .NET role.
- A weakness with no improvement plan.
:::

### Handling pressure

**Definition.** How you stay effective when deadlines, incidents or workload spike: **Clarify → Prioritise → Communicate early → Execute in small steps → Protect quality basics → Recover and review.**

**Why it matters.** Delivery roles always have crunch periods. The interviewer wants to hear process and communication, not "I work till 2 a.m.".

:::q How do you handle pressure?
"Pressure usually means too much work or too little time, so I treat it as a prioritisation problem. I first clarify what really has to be done by the deadline. Then I split it into must-haves and nice-to-haves, and I tell my lead early if something won't fit. I don't wait until the last day.

For example *(replace with your story)*, the client moved a demo one week earlier, and we had three stories left. I listed what the demo actually needed, agreed with the product owner to show one feature with mocked data from a stubbed endpoint, and finished the other two properly. I didn't skip code review or tests, because that's where pressure turns into production bugs. We delivered the demo on time, and the mocked feature shipped properly in the next sprint."
:::

:::tip What interviewers listen for
Early communication, prioritisation with the business, and protecting quality. "I just work extra hours" is not a strategy.
:::

### Handling conflict

**Definition.** Resolving a disagreement, usually technical, by focusing on the shared goal and on data rather than on who is right: **Understand their view → Find the common goal → Use evidence (spike, benchmark, prototype) → Decide or escalate → Disagree and commit.**

**Why it matters.** Teams always disagree. The interviewer wants someone who can disagree respectfully, change their mind when the data says so, and support the final decision.

:::q Tell me about a conflict with a colleague and how you resolved it.
*(Example story; replace with your own.)*

"A senior developer and I disagreed on caching the product catalog. He wanted to use `IMemoryCache` in each API instance because it was simpler. I preferred Redis, because we ran three instances behind a load balancer and price updates had to be consistent.

Instead of arguing in the pull request, I asked for a 30-minute call. I first asked about his concerns. They were mainly cost and another piece of infrastructure to run, which were fair points. We agreed the real goal was fast catalog reads *and* correct prices. I built a quick spike: with in-memory caching, after a price update the three instances showed different prices for up to the cache duration. That convinced both of us. We used Redis for catalog and prices and kept in-memory caching for rarely changing configuration, which was his idea and a good one.

The relationship stayed good. If the data had supported his approach, I'd have gone with it. My rule is to argue with data, then commit to whatever the team decides."
:::

:::warn Conflict-story pitfalls
Stories where you "won" and the other person looks foolish, stories with no resolution, or "I escalated to my manager" as the first step.
:::

### Working with a difficult team member

**Definition.** Handling an ongoing *behaviour* problem (missed commitments, dismissive comments, poor collaboration) with a private, specific, respectful conversation before escalating.

**Why it matters.** It shows emotional maturity and whether you make the team stronger or more divided.

```text
1. Assume positive intent       there's usually a reason you can't see
2. Talk privately, early        1:1, not in stand-up or in PR comments
3. Be specific                  behaviour + impact, not personality
                                "Last two sprints, PRs came in on the last day,
                                 so QA couldn't test" (not "you're lazy")
4. Listen and agree next steps  what will each of you do differently?
5. Follow up                    acknowledge improvement
6. Escalate only if it persists to the lead, with facts, not complaints
```

:::q How do you work with a difficult team member?
*(Example story; replace with your own.)*

"One teammate consistently raised very large pull requests on the last day of the sprint. QA couldn't test them, and stories spilled over. Others were getting frustrated, and there were comments about it in stand-up.

I asked him for a quick one-to-one rather than raising it in front of everyone. I said what I'd seen and its impact: in the last two sprints, three stories spilled over because review and testing had no time. Then I asked what was going on. It turned out he wasn't confident about the requirements and didn't want to show unfinished work. We agreed he'd open draft PRs early and we'd do a 15-minute check-in mid-sprint. I also paired with him on one story to clarify the acceptance criteria with the BA.

Within a couple of sprints his PRs were smaller and earlier, and spillover dropped. If it hadn't improved, I'd have taken it to our lead with the facts, but most of the time a private, specific conversation fixes it."
:::

## Client Communication

### Explaining a technical issue to a non-technical client

**Definition.** Translating a technical problem into *business impact, cause, action and timeline*, using an analogy instead of jargon.

**Why it matters.** Clients make decisions about money, dates and risk. They need to understand the impact and the options, not the stack trace.

```text
IMPACT     what the user/business experienced, in their words
CAUSE      one sentence + one analogy, no jargon
ACTION     what we did to fix it now, and what we'll do to prevent it
TIMELINE   when it will be fully resolved; when the next update comes
ASK        any decision or input needed from them
```

| Technical concept | Analogy for a non-technical client |
|---|---|
| Database index | The index at the back of a book: find the page directly instead of reading every page |
| Caching | Keeping the files you use every day on your desk instead of walking to the archive |
| Connection pool exhausted | A restaurant with a fixed number of tables: when all are full, new guests wait at the door |
| Load balancer / scaling out | Opening more checkout counters in a supermarket when queues get long |
| Technical debt | A loan: quick to take, but you pay interest on every future change until you repay it |
| Deadlock | Two cars on a one-lane bridge, each waiting for the other to reverse |
| Eventual consistency | A bank transfer that shows as "processing" before it reaches the other account |
| Expired SSL certificate | An expired passport: everything else is fine, but no one will let you through |
| Rate limiting | A toll booth that lets only a certain number of cars through per minute |

:::q How would you explain a technical issue to a non-technical client?
"I use a simple order: impact, cause, action, timeline. For example, after the site slowed down during a sale, I explained it like this:

'Between 7 and 8 p.m., about one in ten customers saw a slow checkout and some couldn't complete payment. *(Impact.)* Our system talks to the database through a fixed number of connections, like a restaurant with a fixed number of tables. A new feature was holding tables longer than it should, so new customers had to wait at the door. *(Cause.)* We rolled that feature back within 15 minutes, which fixed it, and we've corrected the code and added a test that simulates sale-day traffic. *(Action.)* The corrected feature goes live on Thursday after testing, and I'll confirm once it's stable. *(Timeline.)*'

I avoid jargon, I don't hide the impact, and I check that they've understood by asking if they have questions."
:::

:::warn Pitfalls
- Leading with jargon: "the SNAT ports were exhausted due to HttpClient misuse".
- Minimising the impact, or blaming a third party or a teammate in front of the client.
- Giving a fix date you haven't checked with the team.
:::

### When requirements are unclear

**Definition.** Turning a vague request into something buildable through **clarifying questions → documented assumptions → a prototype or contract → confirmation → small increments**.

**Why it matters.** Unclear requirements are the most common cause of rework. Interviewers want to see that you clarify *before* building, not after the demo fails.

Questions worth asking:
- **Who** is the user, and **why** do they need this? What problem does it solve?
- What does **done** look like? Can you give a real example (input → expected output)?
- **Edge cases**: empty data, very large data, cancellations, partial failures, permissions.
- **Non-functional**: how many users, how fast, which browsers or devices, audit or compliance needs?
- What is **out of scope** for this release?

```text
ASSUMPTION LOG (shared with the client / PO for confirmation)

#  Assumption                                          Status      Confirmed by
1  Export includes only orders from the last 12 months Confirmed   PO, 12 Mar
2  CSV is enough; Excel format not needed in v1        Pending     -
3  Only Admin role can export                          Confirmed   PO, 12 Mar
4  Max ~50k rows per export; larger ones run async     Pending     -
```

:::q What do you do when requirements are unclear?
"I don't start coding on a guess. First I ask clarifying questions, especially for concrete examples: 'For this customer, what exactly should the report show?' Examples remove most of the ambiguity. Then I write down whatever is still unclear as assumptions and send them to the BA or product owner to confirm in writing. Often I build something cheap to react to, like a wireframe, a Swagger contract for the API, or a clickable prototype, because people find it easier to correct something they can see. I also break the feature into a small first slice so we get feedback early.

For example *(replace with your story)*, a client asked for an 'order export'. With three questions and an assumption log we found they needed only last year's orders, only for admins, as CSV. That was a two-day story instead of the two-week reporting module we'd first estimated."
:::

:::tip Write acceptance criteria as examples
"Given an order with status Shipped, when the admin exports, then the row shows the tracking number." Given/When/Then examples remove ambiguity for developers, QA and the client at the same time.
:::

### Client changes requirements near release

**Definition.** Handling a late change through **understand the why → impact analysis → options with trade-offs → client decides → change control** rather than saying a flat "yes" or "no".

**Why it matters.** Saying yes to everything puts quality and the date at risk. Saying no damages the relationship. The right answer makes the trade-off visible and lets the client choose.

| Option | When it fits | Trade-off |
|---|---|---|
| A. Include the change, move the release date | Change is critical to the business | Later release; possibly cost |
| B. Keep the date, swap scope | Something else in the release is less important | A lower-priority feature moves out |
| C. Release as planned, change in a fast follow-up | Current version is still valuable without it | Users get the change a week or two later |
| D. Ship the change behind a feature flag | Change is small and can be toggled | Extra testing for both paths; flag cleanup later |

:::q What would you do if the client changes requirements just before release?
"First, I'd understand why. A late change usually has a real business reason, and sometimes there's a smaller change that meets it. Then I'd do a quick impact analysis with the team: development effort, regression testing, risk to the release, and any dependencies like database changes.

Next, I'd present options rather than a yes or no. For example: we can include it and move the release by a week; keep the date and drop another item; or release as planned and deliver the change in a follow-up release a week later. I'd explain the risk of each, especially rushing untested changes into production. The client or product owner decides, and the decision goes through change control: a documented change request, a re-estimate and sign-off, so everyone has the same understanding later.

*(Example; replace with yours.)* Two days before a release, a client asked to add a discount field to invoices. The change touched the invoice calculation, so the regression risk was high. We released on the planned date without it and shipped the discount change in a hotfix release five days later, fully tested. The client agreed because they could see the trade-off clearly."
:::

:::warn Don't
- Silently accept the change and cut testing to hit the date.
- Say "that's not in the scope document" and stop there.
- Agree verbally without documenting it. Late changes without a record become disputes later.
:::

### Handling an unhappy client

**Definition.** Recovering trust with **Listen → Acknowledge → Own → Plan → Follow up**.

**Why it matters.** Problems happen on every project. Clients judge you less on the problem and more on how you respond to it.

```text
LISTEN       let them finish; don't interrupt or defend; take notes
ACKNOWLEDGE  "I understand this delayed your month-end close. That's serious."
OWN          take responsibility for your part; no blaming teammates or vendors
PLAN         concrete next steps, owners and dates (only what you can deliver)
FOLLOW UP    update as promised; confirm closure; share prevention steps
```

:::q How do you handle an unhappy client?
"First I listen without interrupting or defending, because they usually need to be heard before they can hear a solution. Then I acknowledge the impact in their terms, and I take ownership of our part. Then I give a concrete plan with dates I've checked with my team, and I follow up exactly when I said I would.

*(Example; replace with yours.)* A client's finance head was upset because invoice totals were wrong for some orders with mixed tax rates, and her team had found it, not us. On the call I let her explain everything and said: 'You're right, this should have been caught by us, and I understand it affects your month-end close.' I committed to a fix in two days and a list of every affected invoice by the next morning. I delivered both, and then shared what we'd changed: new test cases for mixed tax rates and a reconciliation check. In the next review she mentioned the fast, transparent response. The relationship came out stronger."
:::

:::warn Don't
- Argue facts in the first five minutes, even if the client is partly wrong.
- Blame a teammate, the testers or a third-party vendor in front of the client.
- Promise a date you haven't validated. A second missed promise is worse than the original issue.
:::
