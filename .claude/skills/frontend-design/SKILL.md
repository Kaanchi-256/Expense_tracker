---
name: spendly-ui-designer
description: Generates and redesigns Flask/Jinja2 UI pages and components for Spendly, the personal expense tracker (campusx-official/spendly). Trigger this skill whenever the user asks to design, build, create, redesign, improve, or style any page or component for Spendly — phrases like "design the ___ page", "create UI for ___", "build a component for ___", "redesign ___", "make ___ look better", or any frontend/UI work in this repo, even if they don't say "Spendly" by name once the repo context is clear (app.py, templates/, CLAUDE.md present). Always use this skill instead of generating generic React/Tailwind UI for this project — Spendly is Flask + Jinja2 + vanilla CSS/JS only, and this skill knows the real design tokens and file conventions.
---

# Spendly Frontend UI Designer

Spendly is a Flask + SQLite personal expense tracker rendered with Jinja2 templates,
vanilla CSS, and vanilla JS — **no React, no Tailwind, no npm packages, no build step.**
This skill generates new pages/components or redesigns existing ones so they fit the
app's real, already-established look rather than a generic AI-SaaS default.

## Step 0: Figure out your access mode

Check whether you have live file access to the actual Spendly checkout (bash/view
tools, `app.py` and `templates/base.html` present on disk).

- **Repo mode** (you can read/write real files): do the full workflow below and
  write the files directly into the project.
- **Standalone mode** (no file access — pasted context only): ask the user to paste
  `templates/base.html`, `static/css/style.css`, and the CSS file for the closest
  existing page, or to share a screenshot. Do not invent a design system from
  scratch — Spendly already has a distinctive one (see below) and guessing wrong
  is worse than asking. Then produce the same deliverables as code blocks instead
  of writing files.

## Step 1: Read before you design (repo mode)

Never generate UI from memory or from a generic "fintech" template. Before writing
anything:

1. Read `CLAUDE.md` for the current architecture/tech constraints (they can change).
2. Read `templates/base.html` — the shared layout every page extends, including the
   navbar, flash-message block, and footer markup you must not duplicate.
3. Read `static/css/style.css` — the global stylesheet and CSS custom properties
   (`:root` variables). This is the actual design system: use the existing
   `--ink`, `--paper`, `--accent`, `--radius-*`, `--font-*` variables etc. instead
   of inventing new hex codes or a new type scale. If the task needs a token that
   doesn't exist yet (e.g. a new semantic color), add it to `:root` in the page's
   own CSS file or propose adding it to `style.css`, and say so explicitly in the
   UI Structure brief — don't add it silently.
4. Read the CSS + template of one or two pages closest in spirit to what you're
   building (e.g. a data/stats page → look at `profile.html` + `profile.css`'s
   `stat-card`/`cat-row`/`cat-bar` patterns; a form-heavy page → look at
   `add_expense.html`/`login.html`/`register.html`). Match their class-naming
   style (short, page-prefixed, e.g. `stat-card`, `cat-bar-track`) and structural
   patterns (card wrapper → header → body). **Watch for placeholder/"coming soon"
   pages** (e.g. `analytics.html` is currently a stub with decorative blobs,
   corner accents, and animated dots — a one-off treatment, not the app's general
   design language). Don't copy a placeholder page's decorative styling as if it
   were the standard pattern; prefer a real, data-driven page as your reference.
5. Note the icon conventions already in use: small accent glyphs are plain Unicode
   characters in a `<span>` (e.g. `◈`, `◎`, `◷`, `₹` — see `landing.html` and
   `base.html`), while more detailed icons are hand-written inline `<svg>` with
   `stroke="currentColor"` (see `analytics.html`). Follow whichever fits the
   component: a simple bullet/badge icon → Unicode glyph; a toolbar/action/empty-state
   icon → inline SVG in the same minimal-stroke style. Never add an icon library
   import, icon font package, or npm dependency — everything must be hand-inlined.

If the page you're designing has no close analog anywhere in the app and the brief
is genuinely ambiguous (layout, information density, tone), ask the user for a
reference screenshot or a short description rather than guessing — per Spendly's
own consistency rule, matching the existing app always beats a generic default,
including beating the generic "fintech SaaS" look if the two conflict. (Spendly's
actual aesthetic is a warm editorial "paper/ink" palette with a serif display font
for headings — not the generic blue-and-white fintech look — so lead with what's
actually in `style.css`, not a fintech stereotype.)

## Step 2: Design rules

Apply these on top of whatever `style.css` already establishes:

- Card-based layout: white/`--paper-card` panels, `1px solid var(--border)`,
  existing `--radius-sm/md/lg` tokens, subtle shadows. Shadow weight varies by
  context in the real CSS (e.g. hero/marketing cards use a heavier
  `0 8px 40px rgba(0,0,0,0.06)`, ordinary content cards use a lighter
  `0 2px 8px rgba(0,0,0,0.04)`) — copy the weight from the nearest analogous
  card you read in Step 1, don't reuse one fixed value everywhere.
- Spacing on a consistent rhythm matching nearby components (the app mixes `rem`
  units on roughly an 8px-ish rhythm — 0.5rem/0.75rem/1rem/1.25rem/1.5rem/2rem).
- Clear visual hierarchy: serif `--font-display` for page/section headings, sans
  `--font-body` for everything else, muted `--ink-muted`/`--ink-faint` for
  secondary text — this is already the pattern, keep using it.
- Icons used meaningfully (label a real action or category), never decoratively
  for their own sake.
- Responsive: check `style.css`'s existing `@media (max-width: 900px/600px)`
  breakpoints and extend them, don't invent new breakpoints per page.

Avoid:
- Generic/dated UI that ignores the above (bootstrap-y defaults, drop shadows
  everywhere, mismatched radii)
- Unstructured code dumps — always structure output per Step 3
- Inline `<style>` tags or inline `style="..."` attributes (CLAUDE.md forbids this
  — page styles always go in their own CSS file)
- Hardcoded URLs in templates — always `url_for()`
- Any new pip/npm dependency, React, Tailwind, or JS framework

## Step 3: Output format

Always produce, in this order:

1. **UI Structure (brief)** — a few lines: layout + key sections, and any notable
   UX decision (e.g. "empty state shown when no expenses exist yet"). Note here if
   you added any new CSS variable or deviated from an existing pattern, and why.
2. **Code**:
   - Jinja2 template at `templates/<page>.html`, extending `base.html` with
     `{% block content %}`, following the existing block/whitespace style.
   - CSS at `static/css/<page>.css` (new file, matching CLAUDE.md's "one CSS file
     per page" rule), linked from the template's `{% block head %}` via
     `url_for('static', filename='css/<page>.css')`.
   - JS only if genuinely needed, appended to `static/js/main.js` or a new
     page-specific vanilla `<script>` block — never a new framework/package.

In **repo mode**, write these files for real (respecting `CLAUDE.md`'s "new pages →
new `.html` file extending `base.html`", "page-specific styles → new `.css` file")
and tell the user the paths you wrote. In **standalone mode**, present them as
labeled code blocks the user can paste in themselves, and note which existing files
(base.html, style.css) they should double check against once they have repo access.

**Reusable components** (the "build a component for ___" trigger): the app has no
established partials convention yet — there's no `templates/components/` folder in
today's tree. Putting one there is a reasonable, low-risk choice (Jinja `{% include
%}` partials are standard), but call it out explicitly in the brief as a new
convention being introduced, don't present it as if it already existed.

**Redesigns of an existing page** ("redesign ___", "make ___ better"): prefer a
targeted diff over a full rewrite — change only what serves the ask, keep the rest
of the markup/CSS untouched, and show/apply it as an edit rather than replacing the
whole file. A full rewrite risks silently dropping something that already worked.

## Notes

- This is a solo-maintainer hobby project (CLAUDE.md's own "Do not implement a stub
  route unless explicitly targeted" spirit) — don't scope-creep into implementing
  backend routes or DB logic unless asked; this skill is UI-only. If a route is a
  stub, design the page against mock/sample data and say so.
- If in repo mode and `CLAUDE.md` has changed since this skill was written (new
  constraints, new tech allowed), the live `CLAUDE.md` always wins — re-read it,
  don't trust this file's summary of it.