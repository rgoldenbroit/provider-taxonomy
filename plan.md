# Plan — Information architecture: map → focus → drill (progressive disclosure)

**Problem:** everything is shown at once. The Overview is both a map *and* a full deep-dive (8
always-on insight paragraphs + 3 fully-expanded provider columns with every feature & sub-feature).
The product pop-out dumps all 43 descendants as a comma-run "Includes:". Height grows as
`capabilities × features` → unnavigable as capabilities grow.

**Principle:** one screen = one job. Show **counts and headings**; expand on demand. Never dump a
flat list. Three surfaces, each with a single role:

## 1. Overview = a compact MAP (not a deep-dive)
- Keep the capability × provider presence matrix (the pills) — the scannable landscape, O(capabilities) tall.
- **Remove the inline "Drill into breakdown"** dump (the covbreak block with all insights + expanded
  columns). The map's job is "who plays where," not the full tree.
- Capability row name → opens the **capability pop-out** (below). Product pill → product pop-out.
- Each matrix row keeps just a one-line teaser of its key distinction (muted), not all 8 at once.

## 2. Pop-out = the FOCUS surface, progressively disclosed
Same centered modal, but the breakdown is collapsed to categories-with-counts; you expand only what
you want.

**Product** (e.g. Claude Code) — replaces the comma-run:
```
Claude Code            Anthropic · active · Agentic coding
Autonomous or assisted software development across terminal, IDE, and cloud surfaces.

43 features in 8 categories
  ▸ Agent Management          12
  ▸ Context & Memory           9
  ▸ MCP & connectors           7
  ▸ Code execution & sandbox   6        ← click a category → its features (sub-features nested)
  …
How it compares — Agentic coding
  Google → Antigravity CLI · Jules · Antigravity 2.0
  OpenAI → Codex
```

**Capability/category** (e.g. Managed agent runtime) — the comparison hub:
```
Managed agent runtime
Provider-hosted execution of agents…
How they differ — <the one comparison_note for THIS capability>
  Anthropic   12 ▸     (expand → categories → features)
  Google       8 ▸
  OpenAI       9 ▸
```

**Feature** (leaf-ish, e.g. Code Review) — unchanged: what it is → small "Includes:" (few
sub-features, fine) → how it compares.

## 3. Explore = the POWER view (search/filter), categories collapsed by default
- Keep the pivot, but render category groups collapsed (name + count); expand on click. Today they're
  `open` by default → the wall. One flag flip + the matrix becomes scannable.

## Implementation (viewer-only, `viewer/template.html`)
- `featureTreeHtml` / `treeRow`: collapse `<details>` by default (drop `open`), show counts on every
  level (already have kids.length) — so every tree is expand-on-demand.
- New `categorySummary(p)` helper: list a node's categories with feature counts (collapsed), used in
  the product/capability pop-out instead of the flat "Includes:".
- `openDrawer`: product/parent nodes → category summary; true features → keep the small Includes line.
- `openCapability`: per-provider show count + collapsed categories (reuse the tree, collapsed).
- Overview `viewOverview`: drop the `covbreak` inline breakdown; keep the matrix; add a muted
  one-line distinction teaser per row; make the capability name the pop-out entry.
- No data/engine change. Rebuild + redeploy; render-verify before deploy.

## Open question
- **Overview key-distinction teasers**: keep a one-line teaser per capability row (adds analytical
  signal but a little text), or a totally bare matrix (cleanest, insights only in the pop-out)?
