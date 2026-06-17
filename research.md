# Research — UX review of the AI Provider Taxonomy viewer

*(Supersedes the original build-phase research, which is preserved in git history at the initial commit. This doc is the active research focus: diagnosing the current UX and steering an improvement plan.)*

## What I reviewed

Every surface of the deployed viewer (`viewer/template.html`, live at the Cloud Run URL), against the stated goals:
Pivot · Providers · Lineage & history · Staleness · Intake · How it works · the detail drawer. Cross-checked against the original goals in the build research and against the three portfolio goals you named: **look great · offer practical help · demonstrate ability.**

## The goals, restated

- **Primary audience (assumed): a portfolio visitor** — recruiter, hiring manager, or peer engineer who lands for 30–90 seconds. They want to (a) instantly grasp what this is and why it's impressive, (b) interact with something satisfying, (c) sense the engineering depth.
- **Secondary audience: someone with a real question** — "what's OpenAI's answer to Claude Code?", "who ships a browser agent?", "what got sunset recently?"
- The original build goals were **engine-first**: discovery, triage, trust gates, evals. The viewer was specced as a faithful window onto *all* of that engine state.

## Core diagnosis

**The viewer is an operator's console wearing a product's clothes.** It was built to expose the maintenance engine, so its information architecture mirrors the engine's internals — not a visitor's intent. Concretely, of six top-level tabs, only one (**Pivot**) serves the primary audience well:

| Tab | Who it's actually for | Verdict |
|---|---|---|
| **Pivot** (capability × provider) | Everyone — this is the core idea, made visible | **Keep & elevate.** The strongest asset. |
| **Providers** | Browsers | Redundant — same data as Pivot, transposed; adds little. |
| **Lineage & history** | Maintainers | Half-empty: the "rename/sunset/merge" section has **no chains** in current data; only the "in flux" table populates. Reads as scaffolding. |
| **Staleness** | **Operators only** | A re-verify queue ("overdue −89d"). A visitor does not care which rows are due for re-checking. |
| **Intake** | **Operators only** | A triage queue showing 1 candidate. Pure back-office. |
| **How it works** | Everyone (new) | Good — but it's the *last* tab, so the engineering story is the easiest thing to miss. |

So the IA conflates the person *maintaining* the taxonomy with the person *consuming* it. The maintainer's tools dominate the navigation; the consumer's "wow" and "useful task" are underserved.

## Specific problems (ranked by impact on the goals)

1. **Operator-centric IA.** 5 of 6 tabs are back-office or redundant. No clear "main thing," no hierarchy, no obvious starting point. A visitor doesn't know where to look.
2. **No wow, no delight.** It's a competent dark data-table. No hero moment, no signature visual (e.g. an at-a-glance coverage map), no interactive satisfaction — no **search**, no **filter**, no **compare**, no hover richness, no motion. The pivot, the best asset, is presented flatly.
3. **The most useful task is buried.** "Compare provider X vs Y on capability Z" / "find the equivalent of product P" is the real practical value. The drawer's **cross-provider equivalents** is the killer feature — but it's hidden behind a click and undiscoverable, and there's no way to *focus* the pivot (no search/filter/compare).
4. **Engine internals leak into the consumer UI.** Confidence dots, the header's `confirmed:27 needs_review:1`, the schema/provenance/staleness metric bar, and raw triage notes in the drawer ("grounding 1.00, classification 1.00"). These *prove rigor* — an asset for the "demonstrate ability" goal — but presented raw they read as clutter. They belong in a narrated trust story, not bleeding onto every screen.
5. **Thin / half-empty views** (Lineage's main section, Intake's 1 row, Staleness all-fresh) make a finished system feel like scaffolding.
6. **Aesthetic is generic and unmemorable.** GitHub-dark is professional but says nothing; provider brand colors are defined in CSS yet barely used as structure; typography is purely functional; no light mode; mobile (where many LinkedIn clicks land) is an unverified 4-column grid likely to be cramped.

## What's genuinely good (keep)

- The **capability-anchored pivot** — the core concept, correctly the default.
- The **cross-provider equivalents** in the drawer — needs promotion, not replacement.
- The **lifecycle timeline** (renders future *scheduled* events) — a nice detail.
- The new **How it works** view — the right idea; just positioned and styled as an afterthought.
- The underlying rigor (gates/evals) — the differentiator; needs *narration*, not exposure.

## The strategic fork (this is what I need your call on)

"Improve the UX" forks three ways, and the right plan depends entirely on which you want:

1. **Portfolio-first** — collapse the operator views, lead with a polished overview + one killer interactive view (compare/search), turn the engineering into a *narrated* feature, add delight. Optimizes *look great* + *demonstrate ability*; practical help is a demo.
2. **Product-first** — make it the best "AI-provider capability tracker": strong search/filter/compare, a "what changed recently" feed, broaden coverage, keep operator views but make them shine. Optimizes *practical help*; portfolio value follows from it being genuinely good.
3. **Layered (my lean)** — a polished consumer **front door** (hero overview + a signature interactive compare/search) with the engine/trust/operator views demoted to a clearly-labelled **"under the hood"** area. Serves all three goals: front door = *look great*, compare/search = *practical help*, narrated engine = *demonstrate ability* — and it reframes the existing operator work as **evidence of rigor** instead of deleting it.

## My recommended direction (for your approval)

**Direction 3 (layered), with a deliberate visual upgrade.** Roughly:
- A **front door**: a real hero, an at-a-glance coverage visual, and immediate orientation.
- One **signature interactive view**: focused compare/search over the pivot, with cross-provider equivalence promoted to a first-class, discoverable action.
- **Demote** Staleness/Intake/Lineage into a single "under the hood / how it's maintained" area that *shows off* the trust machinery as a feature.
- A **design pass**: brand-color structure, typography/spacing, motion, mobile-first responsiveness, and possibly a light mode.

## Open questions blocking the plan

1. **Audience priority** — portfolio visitor, real practitioner, or both equally?
2. **What you dislike most** — so I weight the fixes to your gut, not just my diagnosis.
3. **Appetite** — a focused re-architecture of the front door (keeping the engine views as "under the hood"), a lighter polish pass, or a full redesign?

→ Once you answer, I'll write a concrete `plan.md` (phased, with mockups for the new views) and stop for your approval before changing anything.
