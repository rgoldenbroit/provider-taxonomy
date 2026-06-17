# Plan — UX re-architecture of the viewer

*(Supersedes the original build plan, preserved in git history at the initial commit.)*

**Direction (from your answers):** portfolio-first but genuinely useful · re-architect the front door (keep engine views, demote them) · lighter "designed-product" aesthetic · fix the three gripes — *doesn't look impressive*, *hard to find/do anything*, *too much operator clutter*.

**Hard constraints (unchanged):** single self-contained HTML file, zero dependencies, offline-capable, same data contract (`build.py` injects `APP` JSON into `template.html`). No framework. All 77 tests stay green; nothing in the engine changes. This is a `viewer/template.html` rewrite plus a re-skin.

---

## 1. New information architecture

Six operator-shaped tabs → **four intent-shaped sections**:

| New section | Replaces | Job |
|---|---|---|
| **Overview** (home/front door) | — (new) | The wow + 5-second orientation. Hero, at-a-glance coverage matrix, headline stats, CTAs. |
| **Explore** | Pivot + Providers | The useful tool. Search + filters + capability comparison, with cross-provider equivalence promoted to first-class. |
| **How it works** | How it works | The engineering story, narrated and styled as a feature (pipeline + trust gates + live metrics as *proof*). |
| **Under the hood** | Staleness + Intake + Lineage + metrics | "How the catalog keeps itself honest." Operator/trust views consolidated here, reframed as evidence of rigor — out of the main flow, but a click away to show depth. |

Global chrome loses the operator clutter: the `confirmed:27 needs_review:1` counts and the raw `schema/provenance/staleness` metric bar leave the always-on header and move into *How it works* / *Under the hood*.

---

## 2. The two new screens (mockups for your reaction)

**Overview — hero + signature coverage matrix**
```
┌────────────────────────────────────────────────────────────────────────┐
│  ◆ AI Provider Taxonomy              Overview  Explore  How it works  ··· │
├────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   The AI provider landscape, kept honest.                                │
│   A self-maintaining map of what Anthropic, OpenAI & Google ship —       │
│   discovered from the live web, grounded to source, gated before ship.   │
│                                                                          │
│   [ Explore the catalog → ]   [ How it works ]                           │
│                                                                          │
│   28 offerings · 9 capabilities · 3 providers · 100% source-grounded     │
├────────────────────────────────────────────────────────────────────────┤
│   COVERAGE AT A GLANCE                       ● active ◐ preview ○ none    │
│                        Anthropic      OpenAI       Google                 │
│     Flagship model        ●              ●            ●                   │
│     Chat assistant        ●              ●            ●                   │
│     Agentic coding        ●              ●            ● ● ●               │
│     Browser agent         ●              ●            ●                   │
│     Image / video         ○              ◐ sunset     ●                   │
│         hover a cell → product name · click → detail + rivals            │
└────────────────────────────────────────────────────────────────────────┘
```

**Explore — search / filter / compare**
```
┌────────────────────────────────────────────────────────────────────────┐
│  ⌕ search "codex"…           Provider ▾   Capability ▾   Status ▾        │
├────────────────────────────────────────────────────────────────────────┤
│  Agentic coding                                        [ side-by-side ]  │
│                                                                          │
│   Anthropic              OpenAI                Google                     │
│   ┌────────────────┐     ┌────────────────┐    ┌────────────────┐        │
│   │ Claude Code  ● │     │ Codex        ● │    │ Antigravity  ● │        │
│   │ terminal · ide │     │ terminal·cloud │    │ ide · desktop  │        │
│   │ rivals: Codex, │     │ rivals: Claude │    │ +2 more here   │        │
│   │ Antigravity →  │     │ Code, Anti.. → │    │ Jules, …       │        │
│   └────────────────┘     └────────────────┘    └────────────────┘        │
│                                                                          │
│   click a card → drawer: full cross-provider line-up + lifecycle + source│
└────────────────────────────────────────────────────────────────────────┘
```

The drawer stays (it's good) but: cross-provider equivalents move to the *top* of it, and raw triage notes ("grounding 1.00…") get tucked under a collapsed "provenance" disclosure rather than shown inline.

---

## 3. Visual direction — "lighter, designed-product"

- **Theme:** light by default (warm off-white `#fbfbf9` bg, ink `#1a1c20` text), with a **dark toggle** that reuses today's palette so nothing is lost.
- **Accent:** one primary (indigo `#5b5bd6`) for actions/active state; **provider colors as structure** — Anthropic clay `#cc785c`, OpenAI teal `#0a8a6e`, Google blue `#4f86ff` — used on column heads, card left-borders, and the coverage legend.
- **Type:** a proper scale (hero 32–40px, section 20px, body 14–15px), system font stack, generous line-height and whitespace.
- **Surfaces:** soft cards (1px border + subtle shadow), 12px radius, clear hover lift.
- **Motion:** hover transitions, smooth section changes, the existing drawer slide.
- **Status as color, not jargon:** active/preview/sunset/absent read as a small consistent dot+label system, legend shown once.
- **Mobile-first:** the coverage matrix and Explore grid collapse to stacked, provider-labelled cards under ~720px (the current 4-col grid does not survive a phone).

---

## 4. Phased implementation (one phase at a time; I stop between phases if you want)

- **Phase 1 — Design system + shell.** New CSS foundation (palette, type, spacing, light/dark), responsive scaffolding, and the 4-section nav shell. Re-point existing views into it so the build never breaks. *Checkpoint: rebuild, 77 tests green, screenshot.*
- **Phase 2 — Overview front door.** Hero + signature coverage matrix + stats + CTAs.
- **Phase 3 — Explore.** Search + filters (provider/capability/status) + capability comparison + promoted equivalence; fold Providers in.
- **Phase 4 — Under the hood + de-clutter.** Consolidate Staleness/Intake/Lineage/metrics into one reframed section; strip operator counts/metric-bar from global chrome; restyle *How it works*.
- **Phase 5 — Polish + ship.** Motion, mobile QA, empty-state handling, re-capture `docs/` screenshots, update README hero, rebuild + redeploy.

**Effort:** Phases 1–3 are the bulk (the visible win); 4–5 are consolidation and polish. All in vanilla JS/CSS in the one file.

**Risks / watch-items:** (a) keeping the single-file/offline contract while adding search/filter state — fine in vanilla JS; (b) the light theme must still carry the absent/"(none)" and flux states — I'll port every status into the new system; (c) no data field is lost — operator detail relocates, never disappears.

---

## 5. What I am NOT doing (unless you say so)

- Not touching the engine, schema, trust gates, or evals.
- Not adding a framework or build step.
- Not broadening data coverage (separate effort).
- Not pushing to GitHub or redeploying until you approve.

→ **Approve this and I'll start with Phase 1.** Tell me if you want to react to the mockups, change the IA, or adjust the visual direction first.
