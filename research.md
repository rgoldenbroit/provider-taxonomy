# Research — Revised approach: provider-first, real-named, insight-driven Agentic Coding

## Why we're revising (the bar changed)

This is a **portfolio piece** the user will feature on LinkedIn to attract hiring interest from AI
providers. The bar is therefore: **cross-provider completeness + polish + insight** — a Google or
OpenAI reviewer must see *their* products represented fully, accurately, and by their real names,
side by side with Anthropic's. (See memory `portfolio-intent`.)

User feedback (2026-06-22): the taxonomy looks "a little disjointed," "fails at being all-inclusive,"
and the names are wrong — *"it's not called 'Anthropic guardrails' or 'Antigravity guardrails.'"* Correct.

## Diagnosis — root cause, with evidence

The current content was built **top-down (grid-first)**: define a fixed set of axes, then have
`ground_features.py` mint one node per `(provider × axis)` with a **templated name** `"{Product} {axis}"`
and try to ground it. That method produces exactly the three problems observed:

1. **Generic/manufactured names.** **22 of 25** feature-level comparison cells are templated
   ("Anthropic guardrails," "Antigravity guardrails," "Codex sandbox," "OpenAI evals & observability"…).
   Only 3 read as real (Codex Cloud, Jules async control, Claude Code Remote Control). The tier that
   *does* sound real — sub-features like "Permission modes," "Approval modes" — is the one I
   hand-curated. **The auto-minted layer is the weak link.**
2. **Coverage biased toward the best-documented provider.** "Admit only what grounds" + Anthropic's
   richer public docs ⇒ sub-feature depth Anthropic **11** / OpenAI **7** / **Google 0**. The method
   itself favors whoever documents best — the opposite of what a 3-way portfolio piece needs.
3. **Structural disjointedness.** 6 orphaned features (the entire **evals** row floats; Anthropic
   guardrails and OpenAI MCP aren't under their products), **Google MCP mis-typed** as `service_tier`,
   and Google fragmented across **Antigravity 2.0 / Jules / an empty "Antigravity CLI"** node.
4. **No comparative insight.** Presence/absence cells only — no "so what," which is what actually
   impresses a hiring reviewer.

## The reframe — provider-first / evidence-first

Flip the population method:

> **For each provider, read their actual agentic-coding docs; capture the real, named features and how
> the provider groups them; THEN map those real features onto the shared comparison axes.**

- **Axes / categories become the comparison lens (row labels), not the source of nodes.** Each leaf
  carries the provider's *real* feature name + citation (the model already supports this:
  capability = axis, product = the provider's product, `feature`(parent=product, primary=axis) = the
  real named offering).
- **Add a comparative-insight layer.** A presence/absence matrix is commodity; the differentiator is
  one short, **grounded** sentence per axis on *how the three approaches differ* — e.g. *"Subagents:
  Anthropic = version-controlled Markdown files (`.claude/agents/`); OpenAI = `AGENTS.md` config;
  Google = managed Agent Manager — file-native vs config-native vs managed-runtime."* Derived from the
  verified per-provider facts (cited, not opinion), rendered as a callout on each axis. This is what
  reads as "understands the space" rather than "scraped some docs."
- **Scope: go deep and impeccable on Agentic Coding only** — the 5 existing categories, all three
  providers brought to **parity** depth and real names. No broadening to other functions this pass.
- **Keep the trust backbone** (grounding judge, source tiers, reverify→verify reproducibility, the
  collapsible viewer). We change *what we populate and how we name it*, not the trust machinery. The
  engine's job shifts from *inventing node names off a grid* to *verifying operator-/doc-sourced real
  features*.

## What stays vs. changes

**Stays:** schema's `capability(axis) → product → feature(parent) → sub-feature` model (already the
right shape); grounding/`triage_one`; `reverify --record` → `taxo verify` byte-identical; the
collapsible Overview/Explore/drawer tree.

**Changes (data):** rename the 22 templated cells to real product/feature names; re-parent the 6
orphans to their products; fix Google MCP `kind`; resolve Google's node fragmentation; bring
OpenAI + Google to parity depth with Anthropic.

**Changes (process):** replace grid-mint discovery with an **automated provider-first pipeline**.
Automation is required — but accuracy and completeness rank above it (a naive autopopulate is what
produced the current mess). The pipeline (per provider, per category):
1. **Retrieve the provider's own structured doc surface** — NOT web search. Probed + confirmed:
   - **OpenAI Codex:** `developers.openai.com/codex/llms.txt` (per-page `.md` index) / `llms-full.txt`
     (1 MB, 23k lines, 93 "subagent" hits) — the entire docs as clean markdown.
   - **Anthropic Claude Code:** `code.claude.com/llms.txt` — index where every page is a clean `.md` URL.
   - **Google Antigravity:** no llms.txt, but `antigravity.google/sitemap.xml` lists the real doc URLs
     (e.g. `/docs/agent-features`); pages are JS-rendered, so fetch via **headless Chrome** (`--dump-dom`).
   Tiered retriever: `llms-full/llms.txt` → `sitemap.xml` → headless render. Tavily demoted to a
   last-resort discovery fallback. (Search-as-retrieval was the root cause of blogs, junk, and Google=0.)
2. **Extract** the features each official page documents *under their real names*, with the exact
   phrasing — the canonical name comes **from the page**, never a template.
3. **Map** each extracted feature to a comparison axis (no artificial pinning).
4. **Ground** each: the judge confirms the named feature appears on its cited official page → accuracy;
   confidence derived from source tier.
5. **Completeness critic + loop-until-dry:** after each pass, ask "for provider X, what documented
   agentic-coding features are NOT yet captured?" and re-query until two rounds surface nothing new.
6. **Lifecycle check:** capture `status` (active/preview/deprecated/sunset) so churn (e.g. a deprecated
   Gemini CLI) is flagged with a dated lifecycle event, not silently featured.
7. **Reverify --record → verify** for evidence + byte-identical reproducibility (existing backbone).
8. **Insight synthesis:** once all three providers' real features for an axis are grounded, synthesize
   the one-line "how they differ," grounded in the captured facts + citations.

Constraint: on this GCP project Claude's own `web_search`/`web_fetch` are org-blocked, so discovery uses
Tavily + `HttpFetch` (already wired). Human reviews pipeline *output*; does not hand-curate each cell.

**Adds (small schema + UI):** a comparative-insight field (per axis or per category) + render it as
the "so what" line in the viewer.

## Real-name targets (hypotheses — the pass verifies/corrects)

| Axis | Anthropic (real) | OpenAI (real) | Google (real) |
|---|---|---|---|
| guardrails-safety | Permission modes & sandboxing | Codex approval modes & sandbox | Antigravity ? (verify) |
| subagents | Subagents (`.claude/agents`) | AGENTS.md / ? | Antigravity Agent Manager |
| managed-runtime | ? | Codex Cloud tasks | Jules (managed/async) |
| memory | CLAUDE.md memory | AGENTS.md | Jules ? |

These are starting hypotheses only; provider-first reading sets the actual names and catches what we're
missing for each competitor.

## Structural cleanup (part of this pass)
- **Re-parent orphans** to their products: evals ×3, Anthropic guardrails, OpenAI MCP → under
  Claude Code / Codex / the right Google node.
- **Google MCP:** `service_tier` → `feature`, parent to its product.
- **Google fragmentation:** canonical Google representation = **Antigravity** (agent-first IDE) +
  **Jules** (async). **Gemini CLI is out** as a primary node (reportedly being deprecated) — the
  pipeline lifecycle-checks it and, if sunset/merged, shows a `deprecated` badge + dated event rather
  than featuring it. Fold/populate the empty "Antigravity CLI" node.

## Risks & tensions
- **Automation vs. accuracy/completeness (the core requirement).** It must be automated AND maximally
  accurate + complete. Accuracy ← grounding judge + source tiers + reproducible verify. Completeness ←
  the completeness-critic loop-until-dry. If forced to choose, accuracy/completeness win over automation
  convenience.
- **Thin/newer Google docs** ⇒ some axes may be genuine gaps. Represent as a **grounded absence with a
  note**, not silent emptiness — and never a fabricated cell.
- **Comparative insight is editorial** ⇒ it must stay grounded/cited or it weakens the trust story.
- **Scope creep.** Hold to Agentic Coding; resist adding functions/categories mid-pass.
- **Naming accuracy is itself a claim** ⇒ the real name must be substantiated on the cited page (the
  judge confirms the page actually calls it that), or we've traded generic-but-safe for specific-but-wrong.

## Resolved (from feedback 2026-06-22)
- **Automation:** automated provider-first pipeline; accuracy + completeness are hard requirements above
  automation convenience.
- **Google:** Antigravity + Jules; **Gemini CLI dropped** (lifecycle-verified, not featured).
- **Naming source of truth:** extract the canonical name **from the grounded page**, judge-confirmed.

## Open questions (resolve at plan)
1. **Insight layer placement:** per-axis vs per-category; a schema field vs render-only (recommend a
   per-axis `comparison_note` field, rendered as a callout).
2. **Reference axes:** add the missing Agent-Management concepts (Agent teams, Custom personas, Skills)
   and make Surfaces real this pass, or hold to the current 5 categories?

## Out of scope
Functions other than Agentic Coding; the reference's extension categories (Session/Context/Workflow);
re-architecting the trust/reproducibility backbone.
