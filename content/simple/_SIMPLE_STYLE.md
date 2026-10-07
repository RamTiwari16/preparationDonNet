# "In simple words" boxes — authoring guide (READ FULLY BEFORE WRITING)

The site already has detailed, technical content for every topic. Your job is to add a short,
**easy-language** box for every topic so that:

1. the learner (a .NET developer whose first language is not English) understands the idea quickly, and
2. they have a simple, correct answer they can say aloud in an interview.

You do NOT edit the existing content files. You write a separate file per section in
`D:\Ram\dotNet\InterviewPrep\content\simple\` named `NN-simple.md` (NN = section number, e.g. `05-simple.md`).
The build script places each box directly under the matching topic heading.

## How matching works (important)

- Read the section's content files `D:\Ram\dotNet\InterviewPrep\content\NN*.md` (all letters a, b, c…).
- For **every `### ` heading** in those files (skip headings inside code blocks), write one entry.
- Start each entry with the heading line **copied exactly**, character for character, including backticks,
  punctuation and capital letters. Example: if the file has `### IEnumerable vs IQueryable`, write exactly that.
- Keep the entries in the same order as the headings appear.
- If one section has two identical `###` headings, write the entry once — it attaches to the first.
- No `#`, `##` or `####` headings in your file. No `:::` containers. No HTML.

## Entry format (exactly these four bold labels, in this order)

```markdown
### Exact heading text

**In simple words:** 2–4 short sentences. Say what it is and why it exists.

**Real-life example:** One everyday comparison (1–2 sentences) that matches how it really works.

**Interview question:** The question an interviewer would most likely ask about this topic?

**Simple answer:** 2–3 short sentences the candidate can say aloud. Correct, confident, no jargon without explanation.
```

Optional, only when it really helps: after the four parts, one tiny code block (max 8 lines, language-tagged:
`csharp`, `sql`, `javascript`, `typescript`, `yaml`, `bash`, `json`, `text`) showing the simplest possible example.

## Language rules

- Short sentences (aim for 15 words or fewer). One idea per sentence.
- Common words. Write "use" not "utilise", "start" not "instantiate", "check" not "validate" (unless you explain it).
- When a technical word is unavoidable, explain it in brackets the first time: "a *thread* (a worker that runs code)".
- No idioms or slang ("under the hood", "silver bullet", "out of the box" — avoid).
- Speak directly to the learner: "you", "your code".
- Everyday examples should be universal: restaurant, kitchen, bank, ATM, library, post office, train/bus ticket,
  school, shop, delivery app, mobile phone, parking lot, hospital, etc.
- **Simple must still be correct.** Never trade accuracy for simplicity. If a common simplification is wrong
  (e.g. "structs always live on the stack"), do not use it.
- No filler such as "Great question!" or "In today's world".
- Length per entry: roughly 80–150 words (plus optional tiny code).

## Worked example (the tone to copy)

```markdown
### Service lifetimes: Singleton, Scoped, Transient

**In simple words:** When ASP.NET Core creates an object for you, the lifetime decides how long that object is reused. Singleton means one object for the whole app. Scoped means one object per web request. Transient means a new object every time someone asks for it.

**Real-life example:** In an office, the building's main door is a singleton — everyone uses the same one. A visitor badge is scoped — you get one when you arrive and return it when you leave. A paper cup at the water cooler is transient — you take a new one each time.

**Interview question:** What is the difference between Singleton, Scoped and Transient?

**Simple answer:** Singleton creates one object and shares it for the app's whole life. Scoped creates one object per HTTP request, so all classes in that request share it — that is why DbContext is scoped. Transient creates a new object every time it is injected, which suits small, stateless services.
```

```markdown
### Boxing and Unboxing

**In simple words:** Boxing means putting a value type (like an `int`) inside an `object`. .NET copies the value to the heap (the memory area for objects). Unboxing takes the value back out. Both cost time and memory, so avoid them in code that runs very often.

**Real-life example:** You put a single coin into a gift box to mail it. Packing and unpacking takes effort, even though you only wanted to send a coin.

**Interview question:** What is boxing and why should we avoid it?

**Simple answer:** Boxing converts a value type to `object` by copying it to the heap, and unboxing copies it back. It creates extra objects for the garbage collector, so in loops it slows the app. Using generics like `List<int>` instead of `ArrayList` avoids it.

```csharp
int n = 42;
object box = n;      // boxing: copy to heap
int back = (int)box; // unboxing: copy back
```
```

## Before you finish

1. Every `###` heading from your sections has exactly one entry, copied exactly.
2. Every entry has all four labels.
3. Language is simple; facts are correct.
4. Keep each file under ~45 KB; if a section needs more, split into `NNa-simple.md`, `NNb-simple.md` in heading order.
5. Reply with: files written, number of entries per section, and any heading you could not match.
