# .NET Full Stack Interview Prep

Open **`index.html`** in any browser (no server, no internet needed).

```
InterviewPrep/
├─ index.html          ← the site (generated; open this)
├─ assets/             ← style.css, app.js
├─ screenshots/        ← diagrams + your own screenshots (NN-name.svg/png/jpg)
├─ content/            ← markdown source, one or more files per section (NN*.md)
├─ tools/              ← build.py, template.html, home.html
└─ build.bat           ← rebuilds index.html
```

## Using the site
- **Search** (`/` key): searches every heading and paragraph across all sections.
- **Mastered** checkbox next to each topic: progress is saved in your browser and shown per section on the home page.
- **Interview Q&A** blocks are collapsed — try to answer aloud, then expand. *Expand all / Collapse all* are in each section header.
- **Copy** button on every code block; light/dark toggle top-right; works on phones.
- Click a diagram in the *Reference diagrams & screenshots* panel to enlarge it (← → to browse, Esc to close).

## Editing / extending
- Edit or add `content/NN-name.md` (NN = section number). Format: `##` topic group, `###` topic, fenced code with a language,
  and `:::example`, `:::q Question?`, `:::scenario`, `:::tip`, `:::warn` containers closed with `:::`. See `content/_STYLE.md`.
- Drop screenshots into `screenshots/` named `NN-your-title.png` (see `screenshots/README.md`).
- Rebuild with `build.bat` (needs Python 3 and `pip install markdown-it-py pygments`).
