# Research — Deepening the taxonomy (category + sub-feature levels) with collapsible UI

## Goal

Make the taxonomy **go levels deeper** and render it with a **collapsible UI**, using
`docs/agentic-coding-taxonomy.md` as a *shape* reference only. The reference's content is
explicitly **not** treated as fact — only its information architecture
(`function → product → category → feature → sub-feature` + per-provider alignment) informs the design.

Decisions locked via Q&A:
- **Model:** Hybrid — abstract spine (`function → category → feature-axis`) + concrete per-provider fill (`product → feature → sub-feature` via `parent_id`).
- **Scope:** Pilot on the **Agentic Coding** function; design to generalize.
- **Data/trust:** **Structure-only scaffold**, marked unverified; the maintenance loop grounds it later. No fabricated facts.
- **UI:** Upgrade the **drawer + Explore** in place (no new top-level tab).

## Current architecture (verified against code)

**Data model** (`schema.json`): two arrays.
- `capabilities` — stable, provider-agnostic axes. `tier ∈ {model, end_user_product, developer_platform, uncategorized}`. The "feature axes" (`subagents-orchestration`, `mcp-connectors`, `agent-memory`, `code-execution-sandbox`, `guardrails-safety`, `agent-evals-observability`, `managed-agent-runtime`, `remote-agent-control`) are **already** modeled here as `developer_platform` capabilities. They are **cross-cutting** (not owned by one function).
- `products` — concrete per-provider nodes. `kind ∈ {model_family, model, product, feature, platform, protocol, service_tier}`; `parent_id` gives hierarchy; a concrete `feature` maps a product to a feature-axis via `primary_capability_id`.

**Current depth = 1** (feature → product). No `category` grouping; no sub-features. Example today:
`agentic-coding` (capability) → `Claude Code` (product) → `Claude Code subagents` (feature, `primary_capability_id=subagents-orchestration`).

**Schema reality:** `parent_id` is a free reference; arbitrary-depth nesting is **already schema-legal**. `validate.py` only checks ref-resolution + uniqueness (no depth/cycle limit). So "deeper" is mostly a **data + UI** change.

**Viewer** (`viewer/template.html` → `build.py` inlines the dataset → `viewer/taxonomy.html`). Zero-dependency single file. Four tabs: Overview (coverage matrix), Explore (search/filter/side-by-side compare), How it works, Under the hood. The drawer's `featuresSection()` renders a **flat** feature list grouped by axis. Nothing collapses.

**Trust machinery (the app's identity — must not regress):**
- Every product carries `source {url, last_verified, confidence}` + a provenance receipt.
- `taxo verify` = **reproducible-build gate** (`cli.cmd_verify` → `replay.reverify_catalog`): deep-copies `data/taxonomy.json`, re-grounds **every `products` entry** from the committed `evidence/` ledger, and asserts a **byte-identical** catalog hash. It **skips `status=="absent"`**; any product missing ledger evidence raises `LedgerMiss` → FAIL. **Currently PASSES** (48 grounded records = 48 pages/48 provenance; 43 confirmed + 6 needs_review non-absent + 1 absent).
- CI (`.github/workflows/ci.yml`) runs offline tests + `taxo verify`.

## Gap vs the reference

The reference adds two structural levels the app lacks:
1. **Category** — an IA grouping of feature-axes *within a function* (e.g. "Surfaces", "Agent Management"). Provider-agnostic.
2. **Sub-feature** — a concrete level **below** a feature (e.g. `Subagents → Definition files / Tool scoping / Model per agent`), per provider.

Plus the UX ask: **collapsible** rendering of the deeper tree, with per-provider comparison preserved.

> Note: the reference's "Surfaces" category (CLI/IDE/web/mobile) largely duplicates the existing `surfaces` enum field, and the app *deliberately folds* access surfaces into their parent product (`autobuild._fold_surface`). So "Surfaces" is represented as a category over existing data, not as new per-surface nodes — consistent with the existing folding rule.

## Proposed model changes (additive, backward-compatible)

### 1. `categories` — new optional top-level array (abstract spine)
```json
{ "id": "agentic-coding/agent-management",
  "function_id": "agentic-coding",         // → a capability id (the "function")
  "name": "Agent Management",
  "description": "Defining, specializing, and orchestrating agents.",
  "order": 2,
  "feature_axis_ids": ["subagents-orchestration", "managed-agent-runtime"] }  // → capability ids
```
- Purely structural / provider-agnostic — analogous to `capabilities` (which are also hand-authored and ungrounded). Groups + orders existing feature-axes *for one function's view*; keeps feature-axes cross-cutting.
- A concrete feature's category is **derived** (`primary_capability_id` → which category lists that axis). No per-product `category` field needed → data stays DRY.

Pilot category set for `agentic-coding` (built over **existing real** feature-axes, no fabricated facts):
| Category | Feature-axes grouped |
|---|---|
| Surfaces | (derived from the `surfaces` field) |
| Agent Management | subagents-orchestration, managed-agent-runtime |
| Context & Memory | agent-memory, mcp-connectors |
| Execution & Safety | code-execution-sandbox, guardrails-safety |
| Quality & Ops | agent-evals-observability, remote-agent-control |

### 2. `sub-feature` nodes — concrete, via existing `parent_id`
Sub-features are `products` with `kind="feature"`, `parent_id` = a concrete feature node (one level deeper than today). Depth is derived from the parent chain — **no new `kind`** needed. Each maps to the same `primary_capability_id` as its parent feature.

### 3. `scaffold` — new `review_status` value (the trust-honest hinge)
Sub-feature scaffold nodes are **structure, not yet ground-verified**. They get `review_status:"scaffold"`, a real official-doc `source.url`, `confidence:"low"`, `last_verified=as_of`, and a `scope_note` saying so.
- `replay.reverify_catalog` **skips `review_status=="scaffold"`** exactly as it already skips `status=="absent"` → no ledger evidence required → **`taxo verify` stays byte-identical and green**.
- This is a deliberate, honest refinement: the reproducible-build check reproduces the *grounded* catalog; explicitly-unverified scaffold passes through unchanged. The maintenance loop later grounds a scaffold node → it flips to `needs_review`/`confirmed` with real evidence (intended lifecycle).

## Reproducibility constraint — why this design is safe (the key analysis)

- `categories` (new top-level array): `reverify_catalog` only iterates `products`, so categories pass through replay **untouched** → hash identical. Safe. ✔
- Sub-feature **scaffold** products: skipped by the new `review_status=="scaffold"` guard → no evidence needed, passed through unchanged → hash identical. ✔
- Why not reuse `needs_review`? The 6 existing `needs_review` records **have** evidence and are currently replayed; skipping them would silently drop them from the reproducibility guarantee. A dedicated `scaffold` state keeps "confirmed-but-evidence-missing" a real FAIL. ✔
- Why not `status:"absent"`? Wrong semantics (deliberate non-offering) + forces `relation="none"`. ✔

## Dependency impact map

| File | Change | Why |
|---|---|---|
| `schema.json` | add `categories` `$def` + optional top-level `categories`; add `"scaffold"` to `review_status` enum | new structures must validate |
| `taxonomy/validate.py` | integrity checks for categories (id unique, `function_id` resolves to a capability, `feature_axis_ids` resolve); optional `parent_id` cycle guard now nesting is deeper | catch real data bugs the schema can't |
| `taxonomy/replay.py` | `reverify_catalog` skips `review_status=="scaffold"` | keep `taxo verify` green + honest |
| `data/taxonomy.json` | add `categories` (agentic-coding) + scaffold sub-feature nodes (pilot) | the catalog the viewer renders |
| `examples.json` (seed/gold) | add the same `categories` only (NOT scaffold nodes) | keep seed structurally consistent + valid; keep gold set pristine for evals |
| `viewer/template.html` | collapsible `category → feature → sub-feature` tree in the **drawer**; category-grouped drill-down in **Explore**; `scaffold`/unverified badge styling | the UX ask |
| `viewer/build.py` | none required (passes `data` wholesale; categories ride along) — confirm | — |
| `README.md` | document the deeper taxonomy + collapsible UI | docs accuracy |
| `tests/` | add: schema accepts `categories`; validator rejects bad category refs; replay skips scaffold (verify stays byte-identical); viewer embeds categories | regression cover |

**Verified non-issues:**
- `metrics.dataset_metrics`: `provenance_completeness = with_source/n` counts a `source.url` (not a receipt) → scaffold nodes with a doc URL **don't** drag it; `schema_conformance` stays 1.0 if valid. ✔
- Audit gate (`audit.gate`) blocks only on **critical** findings; `_node_worthiness_findings` emits warning/info and is LLM/online-only (skipped in CI); `_coverage_findings` emits info. Sub-features won't block the gate. ✔
- Evals (`gold.py`/`adversarial.py`, `test_evals.py`) use `load_seed()` (examples.json) — untouched by scaffold nodes. ✔
- `test_viewer.py` builds from `load_dataset()` and asserts `validation.valid` + product-count match — satisfied by valid additions. ✔
- `test_validate.py::test_seed_is_valid` validates examples.json — `categories` optional ⇒ still valid. ✔

## Risks & mitigations
- **R1 — verify gate breaks.** Mitigated by the `scaffold`-skip design above + a new test asserting verify stays byte-identical with scaffold nodes present.
- **R2 — `CHANGELOG.md` is loop-generated** (`taxo changelog`); manual edits can be clobbered. → Don't hand-edit CHANGELOG; let the next loop diff pick up the additions (they'll show as "added"). Document the rev in README instead.
- **R3 — scope creep to all 17 capabilities.** → Pilot only `agentic-coding`; categories are optional per-function so other functions render exactly as today.
- **R4 — UI complexity in a single file.** → Use native `<details>/<summary>` for collapse (no JS state), styled to match the design tokens.

## Out of scope (this revision)
- Live grounding of the scaffold sub-features (the maintenance loop owns that).
- Categories for functions other than Agentic Coding.
- Schema-level enforcement of category↔feature-axis completeness (advisory only for now).

## Open questions
None blocking — the four design forks are resolved. One confirmation I'll seek at plan-approval: the **exact pilot sub-feature list** (I'll propose ~3 per feature for 2–3 marquee features, sourced to official docs) before writing data.
