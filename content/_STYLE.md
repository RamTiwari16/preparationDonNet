# Content authoring guide (READ FULLY BEFORE WRITING)

You are writing study material for a **.NET Full Stack interview prep site** (2–5 years experience level). Your markdown files are compiled by a custom build script into one HTML page. Follow this format exactly or the build will mis-render.

Outline of every topic to cover lives in `D:\Ram\dotNet\InterviewPrep\content\_topics.md` (read the numbered sections assigned to you; cover **every bullet**, grouping tightly-related bullets under one heading is fine).

## Depth: what "detailed" means here
For each topic, be ready to give the full chain:
**Definition → Why it matters → How it works → Code → Real-world example → Common interview question → Scenario/problem.**
- Never write definitions only. Every topic gets at least: a crisp definition, *why/when*, a runnable-looking code or SQL or diagram sample, and one real-world example or pitfall.
- Topics flagged "very important" / Very High priority (C#/OOP, ASP.NET Core, Web API, SQL, EF Core, LINQ, DI, JWT, DSA) get the deepest treatment: multiple code samples, comparison tables, gotchas, 2–4 interview Q&As each.
- Lower-priority topics (Kubernetes, Kafka, GenAI, LLD, HR) can be tighter but still need definition + example + Q&A.
- Prefer a *concrete running example domain* (e-commerce: Orders, Products, Customers, Payments) so examples feel real, and keep it consistent within a file.
- Be accurate and current: target modern .NET (8/9/10, C# 12–14) unless the topic is historic. If you are not sure about a precise recent-version detail, either verify (WebSearch/WebFetch are available) or phrase it carefully ("verify in the release notes"). Do not invent APIs. Code must compile in principle.
- End each section's files with a `## Quick-fire Q&A` block of 8–15 short `:::q` containers (1–4 sentence answers) — the questions most likely asked in interviews for that section.
- Write like a senior engineer coaching a candidate: direct, no filler, no marketing tone. Short sentences. Interview-ready answers phrased the way a candidate would say them aloud ("Say this:" style lines are welcome inside `:::q`).

## Files
- Write files into `D:\Ram\dotNet\InterviewPrep\content\` named `NN<letter>-short-slug.md`, where `NN` is the two-digit section number from `_topics.md` and the optional letter orders multiple files of the same section (e.g. `02a-dotnet-versions.md`, `02b-aspnet-core.md`). The build concatenates all files with the same `NN` prefix in filename order.
- **Keep each file under ~30 KB**; split a big section into several files (a, b, c …) in topic order. Write each file with a single Write call (do not append piecemeal into one huge call).
- Do NOT write a `# H1` title — the build adds the section header. Do not write front-matter.
- Only touch your own files. Never edit other agents' files, `_topics.md`, or this guide.
- Do not create HTML. Do not create the screenshots/diagrams (another agent does that). Do not reference image files.

## Markdown subset (everything else is unsupported)
- Headings: `##` = topic group (matches the groups in `_topics.md`), `###` = a topic, `####` = a sub-point. Each `##`/`###` automatically appears in the sidebar and table of contents, so keep titles short and meaningful. Don't skip levels.
- Paragraphs, **bold**, *italic*, `inline code`, bullet lists (`-`), numbered lists (`1.`), links, blockquotes (`>`), horizontal rules (avoid).
- Tables with pipes (use them for comparisons — "X vs Y" topics should have a table):
  ```
  | Feature | A | B |
  |---|---|---|
  ```
- Fenced code blocks with a language tag: `csharp`, `sql`, `javascript`, `typescript`, `html`, `json`, `yaml`, `dockerfile`, `bash`, `powershell`, `xml`, `text` (use `text` for ASCII diagrams/flows). **Always tag the language.** Keep lines ≤ ~90 chars so they don't scroll horizontally. Use realistic names, add short comments where it teaches something. Mark output with `// Output: ...` comments.
- ASCII flow/diagram example (use `text`):
  ```text
  Client → API → Redis → SQL Server
  ```
- Do not use raw HTML. Do not use emoji in headings. Do not use footnotes, task lists, or nested containers.

## Containers (custom blocks)
Syntax — opening line `:::kind Title text`, content, closing line `:::` (own line, column 0). Content is normal markdown (code fences allowed). **No nesting, no indentation.**

| Kind | Use for |
|---|---|
| `:::example Title` | Real-world example / worked example in a business setting |
| `:::q Question as an interviewer would ask it?` | Interview question + model answer (title = the question; body = the answer you'd say; may include a code block) |
| `:::scenario Title` | Scenario/problem-style question ("Your API is slow under load…") with the reasoning and fix |
| `:::tip Title` | Interview tip / memory trick / what interviewers look for |
| `:::warn Title` | Common mistake / gotcha / anti-pattern |

Example of the expected shape for ONE topic:

````markdown
### Value type vs Reference type

**Definition.** A *value type* stores its data directly (stack or inline in its container); a *reference type* stores a reference to an object on the managed heap.

**Why it matters.** Assignment semantics, equality, nullability, GC pressure and performance all follow from this one distinction.

| | Value type | Reference type |
|---|---|---|
| Examples | `int`, `bool`, `struct`, `enum` | `class`, `string`, `array`, `delegate` |
| Assignment | copies the data | copies the reference |
| Default | zero-initialised | `null` |

```csharp
struct PointS { public int X; }
class PointC { public int X; }

var a = new PointS { X = 1 }; var b = a; b.X = 99;   // a.X is still 1
var c = new PointC { X = 1 }; var d = c; d.X = 99;   // c.X is now 99
```

:::example Real-world example
An `OrderLine` DTO that is copied around thousands of times per request is a good `readonly struct` candidate — no heap allocation; but an `Order` aggregate that is mutated and shared must be a class.
:::

:::warn Gotcha
Mutable structs inside a `List<T>` — `list[0].X = 5` does not compile because the indexer returns a copy.
:::

:::q Is a struct always allocated on the stack?
No. That is an implementation detail. A struct that is a field of a class lives on the heap with that object; boxed structs live on the heap; locals may even be enregistered. The correct statement: value types have *copy semantics*, not "always stack".
:::
````

## Quality bar checklist (self-review before finishing)
1. Every bullet in your assigned `_topics.md` sections is covered somewhere.
2. Every `###` topic has definition + why + code/diagram/table + at least one example, pitfall, or Q&A.
3. Every section ends with `## Quick-fire Q&A` (8–15 `:::q`).
4. All fenced blocks are language-tagged and closed; all `:::` containers are closed; no nesting.
5. Code is correct, idiomatic, modern, and consistent with the chosen domain.
6. Skim your files once more for factual errors, especially version-specific claims.

When finished, reply with: the list of files written (with approximate word counts) and any topics you deliberately merged or could not cover. Keep that reply under 15 lines.
