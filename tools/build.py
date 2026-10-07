#!/usr/bin/env python3
"""
Build index.html for the .NET Full Stack Interview Prep site.

    python tools/build.py

Inputs
  content/NN*.md        markdown source, one or more files per section number NN
  screenshots/NN-*.*    diagrams / screenshots; the NN prefix attaches them to section NN
                        (00-* appear on the home page)
  tools/template.html   page shell      tools/home.html   home-page narrative

Output
  index.html            the whole site (sections are lazy-rendered <template>s)

Requires: pip install markdown-it-py pygments
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.util import ClassNotFound

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
SHOTS = ROOT / "screenshots"
TOOLS = ROOT / "tools"

# --------------------------------------------------------------------------- #
# Section metadata (numbers follow the original topic list)
# --------------------------------------------------------------------------- #
PRIORITY = {
    "vh": "Very High",
    "h": "High",
    "m": "Medium",
    "s": "Supporting",
}

SECTIONS = [
    # id, title, short, priority, group
    ("01", "C# — Core & Advanced", "C# & OOP", "vh", "Core .NET"),
    ("02", ".NET / ASP.NET Core", "ASP.NET Core & Web API", "vh", "Core .NET"),
    ("03", "Dependency Injection", "Dependency Injection", "vh", "Core .NET"),
    ("04", "Authentication & Authorization", "Auth, JWT & Security", "vh", "Core .NET"),
    ("05", "Entity Framework Core", "EF Core", "vh", "Core .NET"),
    ("06", "SQL Server", "SQL Server", "vh", "Data"),
    ("25", "SQL Coding Questions", "SQL Coding Questions", "vh", "Data"),
    ("07", "Coding / DSA", "DSA", "vh", "Coding Rounds"),
    ("24", "Coding Questions to Practice", "Coding Questions", "vh", "Coding Rounds"),
    ("08", "Frontend — JavaScript", "JavaScript", "h", "Frontend"),
    ("09", "React", "React", "h", "Frontend"),
    ("10", "Angular", "Angular", "h", "Frontend"),
    ("11", "Azure Cloud", "Azure", "h", "Cloud & DevOps"),
    ("12", "Azure DevOps / CI-CD", "CI/CD", "h", "Cloud & DevOps"),
    ("13", "Docker", "Docker", "h", "Cloud & DevOps"),
    ("14", "Kubernetes", "Kubernetes", "m", "Cloud & DevOps"),
    ("15", "Microservices", "Microservices", "h", "Architecture & Design"),
    ("16", "Caching", "Caching & Redis", "m", "Architecture & Design"),
    ("17", "System Design — HLD", "System Design (HLD)", "h", "Architecture & Design"),
    ("18", "LLD — Low Level Design", "LLD", "m", "Architecture & Design"),
    ("19", "Real-World System Design Problems", "Design Problems", "h", "Architecture & Design"),
    ("20", "Performance Optimization", "Performance", "m", "Quality & Operations"),
    ("21", "Observability & Monitoring", "Observability", "m", "Quality & Operations"),
    ("22", "AI / GenAI for .NET", "AI / GenAI", "m", "AI & Interview Skills"),
    ("23", "Managerial / HR / Client Round", "HR & Client Round", "s", "AI & Interview Skills"),
]

LANG_LABEL = {
    "csharp": "C#", "cs": "C#", "sql": "T-SQL", "tsql": "T-SQL", "javascript": "JavaScript",
    "js": "JavaScript", "typescript": "TypeScript", "ts": "TypeScript", "html": "HTML",
    "json": "JSON", "yaml": "YAML", "yml": "YAML", "dockerfile": "Dockerfile", "bash": "Bash",
    "sh": "Bash", "powershell": "PowerShell", "ps": "PowerShell", "xml": "XML", "text": "Diagram / Text",
    "txt": "Diagram / Text", "": "Text", "css": "CSS", "razor": "Razor", "kql": "KQL",
    "proto": "Protobuf", "http": "HTTP", "ini": "INI", "jsx": "JSX", "tsx": "TSX", "diff": "Diff",
    "mermaid": "Diagram", "python": "Python", "java": "Java", "markdown": "Markdown", "md": "Markdown",
    "bicep": "Bicep", "toml": "TOML", "regex": "Regex", "console": "Console", "shell": "Shell",
}
LANG_ALIAS = {
    "csharp": "csharp", "cs": "csharp", "sql": "tsql", "tsql": "tsql", "js": "javascript",
    "ts": "typescript", "yml": "yaml", "sh": "bash", "shell": "bash", "ps": "powershell",
    "razor": "html", "kql": "text", "mermaid": "text", "proto": "protobuf", "txt": "text",
    "": "text", "bicep": "text", "regex": "text", "md": "markdown",
}

WARNINGS: list[str] = []


def warn(msg: str) -> None:
    WARNINGS.append(msg)


# --------------------------------------------------------------------------- #
# Markdown rendering
# --------------------------------------------------------------------------- #
FORMATTER = HtmlFormatter(nowrap=True)


def highlight_code(code: str, lang: str) -> str:
    lang = (lang or "").strip().lower()
    alias = LANG_ALIAS.get(lang, lang)
    try:
        lexer = get_lexer_by_name(alias, stripall=False)
    except ClassNotFound:
        lexer = TextLexer()
    out = highlight(code.rstrip("\n"), lexer, FORMATTER)
    return out.rstrip("\n")


def slugify(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = text.lower()
    text = re.sub(r"[`*_]", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:64] or "topic"


def make_md() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False})
    md.enable("table").enable("strikethrough")

    def fence(self, tokens, idx, options, env):
        tok = tokens[idx]
        lang = (tok.info or "").strip().split()[0] if tok.info else ""
        label = LANG_LABEL.get(lang.lower(), lang or "Text")
        env["code_blocks"] = env.get("code_blocks", 0) + 1
        body = highlight_code(tok.content, lang)
        cls = "codeblock" + (" diagram" if lang.lower() in ("text", "txt", "mermaid") else "")
        return (
            f'<div class="{cls}" data-lang="{html.escape(lang.lower())}">'
            f'<div class="codebar"><span class="lang">{html.escape(label)}</span>'
            f'<button class="copy" type="button" aria-label="Copy code">Copy</button></div>'
            f"<pre><code>{body}</code></pre></div>\n"
        )

    def code_block(self, tokens, idx, options, env):  # indented code
        return fence_like(tokens[idx].content, env)

    def fence_like(content, env):
        env["code_blocks"] = env.get("code_blocks", 0) + 1
        return (
            '<div class="codeblock" data-lang="text"><div class="codebar"><span class="lang">Text</span>'
            '<button class="copy" type="button" aria-label="Copy code">Copy</button></div>'
            f"<pre><code>{html.escape(content.rstrip())}</code></pre></div>\n"
        )

    def heading_open(self, tokens, idx, options, env):
        tok = tokens[idx]
        level = int(tok.tag[1])
        if env.get("collect_headings"):
            text = tokens[idx + 1].content if idx + 1 < len(tokens) else ""
            plain = re.sub(r"[`*_]", "", text)
            base = f'{env["sec"]}-{slugify(plain)}'
            hid, n = base, 2
            used = env["used_ids"]
            while hid in used:
                hid = f"{base}-{n}"
                n += 1
            used.add(hid)
            tok.attrSet("id", hid)
            env["headings"].append({"level": level, "id": hid, "title": plain})
        return self.renderToken(tokens, idx, options, env)

    def heading_close(self, tokens, idx, options, env):
        tok = tokens[idx]
        anchor = ""
        if env.get("collect_headings") and env["headings"]:
            anchor = f' <a class="anchor" href="#/s{env["sec"]}/{env["headings"][-1]["id"]}" aria-label="Link to this heading">#</a>'
        out = anchor + self.renderToken(tokens, idx, options, env)
        simple = env.get("simple")
        if env.get("collect_headings") and simple and env["headings"]:
            key = norm_heading(env["headings"][-1]["title"])
            entry = simple.get(key)
            if entry and not entry["used"]:
                entry["used"] = True
                env["simple_count"] = env.get("simple_count", 0) + 1
                out += (
                    '<div class="callout simple"><div class="chead"><span class="tag">Easy</span>'
                    '<span class="ttl">Explained simply</span></div>'
                    f'<div class="cbody">{entry["html"]}</div></div>\n'
                )
        return out

    def table_open(self, tokens, idx, options, env):
        return '<div class="table-wrap"><table>\n'

    def table_close(self, tokens, idx, options, env):
        return "</table></div>\n"

    def link_open(self, tokens, idx, options, env):
        tok = tokens[idx]
        href = tok.attrGet("href") or ""
        if href.startswith("http"):
            tok.attrSet("target", "_blank")
            tok.attrSet("rel", "noopener noreferrer")
        return self.renderToken(tokens, idx, options, env)

    md.add_render_rule("fence", fence)
    md.add_render_rule("code_block", code_block)
    md.add_render_rule("heading_open", heading_open)
    md.add_render_rule("heading_close", heading_close)
    md.add_render_rule("table_open", table_open)
    md.add_render_rule("table_close", table_close)
    md.add_render_rule("link_open", link_open)
    return md


MD = make_md()

# --------------------------------------------------------------------------- #
# Container parsing (:::kind Title ... :::) — fence aware, no nesting
# --------------------------------------------------------------------------- #
FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")
OPEN_RE = re.compile(r"^:::\s*([A-Za-z]+)\s*(.*?)\s*$")
CLOSE_RE = re.compile(r"^:::\s*$")

KINDS = {
    "example": ("Example", "example"),
    "q": ("Interview Q", "q"),
    "scenario": ("Scenario", "scenario"),
    "tip": ("Tip", "tip"),
    "warn": ("Watch out", "warn"),
    "note": ("Note", "tip"),
    "pitfall": ("Watch out", "warn"),
    "gotcha": ("Watch out", "warn"),
    "question": ("Interview Q", "q"),
    "interview": ("Interview Q", "q"),
}


def split_blocks(text: str, fname: str):
    """Yield ('md', text) and ('box', kind, title, text) blocks."""
    lines = text.replace("\r\n", "\n").split("\n")
    blocks = []
    cur: list[str] = []
    box = None  # (kind, title, lines)
    fence = None  # (char, length)

    def flush_md():
        nonlocal cur
        if "".join(cur).strip():
            blocks.append(("md", "\n".join(cur)))
        cur = []

    for ln_no, line in enumerate(lines, 1):
        target = box[2] if box else cur
        m = FENCE_RE.match(line)
        if m:
            marker = m.group(2)
            rest = m.group(3)
            if fence is None:
                fence = (marker[0], len(marker))
                target.append(line)
                continue
            if marker[0] == fence[0] and len(marker) >= fence[1] and rest.strip() == "":
                fence = None
                target.append(line)
                continue
        if fence is not None:
            target.append(line)
            continue
        if box is not None:
            if CLOSE_RE.match(line):
                blocks.append(("box", box[0], box[1], "\n".join(box[2])))
                box = None
                continue
            o = OPEN_RE.match(line)
            if o and o.group(1).lower() in KINDS:
                warn(f"{fname}:{ln_no}: container '{box[0]}' not closed before next ':::{o.group(1)}'")
                blocks.append(("box", box[0], box[1], "\n".join(box[2])))
                box = (o.group(1).lower(), o.group(2), [])
                continue
            box[2].append(line)
            continue
        o = OPEN_RE.match(line)
        if o and o.group(1).lower() in KINDS:
            flush_md()
            box = (o.group(1).lower(), o.group(2), [])
            continue
        if CLOSE_RE.match(line):
            warn(f"{fname}:{ln_no}: stray ':::' ignored")
            continue
        cur.append(line)
    if fence is not None:
        warn(f"{fname}: unclosed code fence at end of file")
    if box is not None:
        warn(f"{fname}: container '{box[0]}' not closed at end of file")
        blocks.append(("box", box[0], box[1], "\n".join(box[2])))
    flush_md()
    return blocks


def render_inline(text: str) -> str:
    return MD.renderInline(text)


def norm_heading(text: str) -> str:
    text = re.sub(r"[`*_]", "", text).lower()
    return re.sub(r"\s+", " ", text).strip().rstrip(".:?")


SIMPLE_DIR = CONTENT / "simple"


def load_simple(sec_id: str) -> dict:
    """Parse content/simple/NN*.md into {normalised heading: {title, html, used}}."""
    entries: dict = {}
    if not SIMPLE_DIR.exists():
        return entries
    for f in sorted(SIMPLE_DIR.glob(f"{sec_id}*.md")):
        title, buf, fence = None, [], None

        def flush():
            if title is not None:
                key = norm_heading(title)
                if key in entries:
                    warn(f"simple/{f.name}: duplicate entry '{title}' ignored")
                else:
                    sub = {"sec": sec_id, "used_ids": set(), "headings": [], "collect_headings": False}
                    entries[key] = {"title": title, "html": MD.render("\n".join(buf), sub), "used": False}

        for line in f.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n"):
            m = FENCE_RE.match(line)
            if m:
                marker = m.group(2)
                if fence is None:
                    fence = (marker[0], len(marker))
                elif marker[0] == fence[0] and len(marker) >= fence[1] and m.group(3).strip() == "":
                    fence = None
                buf.append(line)
                continue
            if fence is None and line.startswith("### "):
                flush()
                title, buf = line[4:].strip(), []
                continue
            buf.append(line)
        flush()
    return entries


def render_section(sec_id: str, files: list[Path]):
    simple = load_simple(sec_id)
    env = {"sec": sec_id, "used_ids": set(), "headings": [], "collect_headings": True, "code_blocks": 0,
           "simple": simple, "simple_count": 0}
    out: list[str] = []
    stats = {"qa": 0, "examples": 0, "scenarios": 0, "words": 0}
    for f in files:
        raw = f.read_text(encoding="utf-8")
        stats["words"] += len(re.findall(r"\w+", raw))
        for blk in split_blocks(raw, f.name):
            if blk[0] == "md":
                out.append(MD.render(blk[1], env))
            else:
                _, kind, title, body = blk
                label, css = KINDS[kind]
                env["collect_headings"] = False
                inner = MD.render(body, env)
                env["collect_headings"] = True
                title_html = render_inline(title) if title else ""
                if css == "q":
                    stats["qa"] += 1
                    out.append(
                        f'<details class="callout q"><summary><span class="tag">Q</span>'
                        f'<span class="ttl">{title_html or "Question"}</span></summary>'
                        f'<div class="cbody">{inner}</div></details>\n'
                    )
                else:
                    if css == "example":
                        stats["examples"] += 1
                    if css == "scenario":
                        stats["scenarios"] += 1
                    out.append(
                        f'<div class="callout {css}"><div class="chead"><span class="tag">{label}</span>'
                        f'<span class="ttl">{title_html}</span></div><div class="cbody">{inner}</div></div>\n'
                    )
    for e in env["simple"].values():
        if not e["used"]:
            warn(f"simple/{sec_id}: no heading matches easy entry '{e['title']}'")
    return "".join(out), env, stats


# --------------------------------------------------------------------------- #
# Screenshots / diagrams
# --------------------------------------------------------------------------- #
IMG_RE = re.compile(r"^(\d{2})[-_].+\.(svg|png|jpe?g|webp|gif)$", re.I)


def pretty_name(p: Path) -> str:
    stem = re.sub(r"^\d{2}[-_]", "", p.stem)
    words = re.sub(r"[-_]+", " ", stem).strip()
    return words[:1].upper() + words[1:]


def svg_title(p: Path) -> str | None:
    try:
        head = p.read_text(encoding="utf-8", errors="ignore")[:4000]
    except OSError:
        return None
    m = re.search(r"<title[^>]*>(.*?)</title>", head, re.S | re.I)
    return html.unescape(m.group(1).strip()) if m else None


def collect_images():
    by_sec: dict[str, list[dict]] = {}
    if not SHOTS.exists():
        return by_sec
    for p in sorted(SHOTS.iterdir(), key=lambda x: x.name.lower()):
        m = IMG_RE.match(p.name)
        if not m:
            continue
        cap = (svg_title(p) if p.suffix.lower() == ".svg" else None) or pretty_name(p)
        kind = "diagram" if p.suffix.lower() == ".svg" else "screenshot"
        by_sec.setdefault(m.group(1), []).append(
            {"src": f"screenshots/{p.name}", "caption": cap, "kind": kind, "name": p.name}
        )
    return by_sec


def gallery_html(images: list[dict]) -> str:
    if not images:
        return ""
    cards = []
    for i, im in enumerate(images):
        cards.append(
            f'<figure class="shot" data-i="{i}"><button type="button" class="shot-btn" aria-label="Open {html.escape(im["caption"])}">'
            f'<img loading="lazy" src="{html.escape(im["src"])}" alt="{html.escape(im["caption"])}"></button>'
            f'<figcaption><span class="k {im["kind"]}">{im["kind"]}</span> {html.escape(im["caption"])}</figcaption></figure>'
        )
    n = len(images)
    return (
        f'<details class="gallery" open><summary>Reference diagrams &amp; screenshots <span class="count">{n}</span>'
        f'<span class="hint">click to enlarge · folder: <code>screenshots/</code></span></summary>'
        f'<div class="shots">{"".join(cards)}</div></details>\n'
    )


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
def main() -> int:
    files_by_sec: dict[str, list[Path]] = {}
    for p in sorted(CONTENT.glob("*.md")):
        if p.name.startswith("_"):
            continue
        m = re.match(r"^(\d{2})", p.name)
        if not m:
            warn(f"content file without NN prefix ignored: {p.name}")
            continue
        files_by_sec.setdefault(m.group(1), []).append(p)

    images = collect_images()
    meta_sections = []
    templates = []
    totals = {"topics": 0, "qa": 0, "code": 0, "diagrams": 0, "words": 0, "examples": 0, "scenarios": 0, "shots": 0}

    for sec_id, title, short, prio, group in SECTIONS:
        files = files_by_sec.get(sec_id, [])
        body, env, stats = ("", {"headings": [], "code_blocks": 0, "simple_count": 0}, {"qa": 0, "examples": 0, "scenarios": 0, "words": 0})
        if files:
            body, env, stats = render_section(sec_id, files)
        else:
            warn(f"section {sec_id} ({title}) has no content files")
            body = '<p class="empty">Content for this section has not been generated yet.</p>'

        heads = env["headings"]
        has_h3 = any(h["level"] == 3 for h in heads)
        track_level = 3 if has_h3 else 2
        tracked = [h for h in heads if h["level"] == track_level and not h["title"].lower().startswith("quick-fire")]
        imgs = images.get(sec_id, [])
        diagrams = sum(1 for i in imgs if i["kind"] == "diagram")
        shots = len(imgs) - diagrams
        read_min = max(1, round(stats["words"] / 200))

        meta_sections.append(
            {
                "id": sec_id, "title": title, "short": short, "prio": prio, "group": group,
                "topics": len(tracked), "trackIds": [h["id"] for h in tracked],
                "qa": stats["qa"], "code": env["code_blocks"], "images": len(imgs),
                "minutes": read_min, "easy": env.get("simple_count", 0),
                "toc": [{"l": h["level"], "id": h["id"], "t": h["title"]} for h in heads if h["level"] <= 3],
            }
        )
        totals["topics"] += len(tracked)
        totals["easy"] = totals.get("easy", 0) + env.get("simple_count", 0)
        totals["qa"] += stats["qa"]
        totals["code"] += env["code_blocks"]
        totals["diagrams"] += diagrams
        totals["shots"] += shots
        totals["words"] += stats["words"]
        totals["examples"] += stats["examples"]
        totals["scenarios"] += stats["scenarios"]

        head = (
            f'<header class="sec-head"><div class="sec-num">{sec_id}</div><div class="sec-title">'
            f'<h1>{html.escape(title)}</h1><p class="sec-meta"><span class="chip {prio}">{PRIORITY[prio]} priority</span>'
            f'<span>{len(tracked)} topics</span><span>{env.get("simple_count", 0)} easy explanations</span><span>{stats["qa"]} interview Q&amp;As</span>'
            f'<span>{env["code_blocks"]} code samples</span><span>{len(imgs)} visuals</span><span>~{read_min} min read</span></p></div>'
            f'<div class="sec-tools"><button type="button" class="btn simple-toggle" data-act="simple-view" aria-pressed="false">Simple view</button>'
            f'<button type="button" class="btn" data-act="expand-qa">Expand all Q&amp;A</button>'
            f'<button type="button" class="btn" data-act="collapse-qa">Collapse all</button></div></header>\n'
        )
        templates.append(
            f'<template id="tpl-s{sec_id}"><article class="section" data-sec="{sec_id}">{head}'
            f'{gallery_html(imgs)}<div class="prose">{body}</div></article></template>'
        )

    # home-page gallery (00-*)
    home_images = images.get("00", [])
    totals["diagrams"] += sum(1 for i in home_images if i["kind"] == "diagram")
    totals["shots"] += sum(1 for i in home_images if i["kind"] == "screenshot")

    meta = {
        "sections": meta_sections,
        "groups": list(dict.fromkeys(s[4] for s in SECTIONS)),
        "priority": PRIORITY,
        "totals": totals,
        "homeImages": home_images,
    }
    meta_json = json.dumps(meta, ensure_ascii=False).replace("</", "<\\/")

    template = (TOOLS / "template.html").read_text(encoding="utf-8")
    home = (TOOLS / "home.html").read_text(encoding="utf-8")
    page = (
        template.replace("{{HOME}}", home)
        .replace("{{META}}", meta_json)
        .replace("{{TEMPLATES}}", "\n".join(templates))
    )
    out = ROOT / "index.html"
    out.write_text(page, encoding="utf-8")

    size_mb = out.stat().st_size / 1024 / 1024
    print(f"Wrote {out}  ({size_mb:.1f} MB)")
    print(
        f"  sections: {len(SECTIONS)} | topics: {totals['topics']} | Q&As: {totals['qa']} | "
        f"code blocks: {totals['code']} | diagrams: {totals['diagrams']} | screenshots: {totals['shots']} | "
        f"easy boxes: {totals.get('easy', 0)} | words: {totals['words']:,}"
    )
    if WARNINGS:
        print(f"\n{len(WARNINGS)} warning(s):")
        for w in WARNINGS:
            print("  -", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
