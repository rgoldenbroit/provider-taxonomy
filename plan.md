# Plan — Deeper taxonomy (category + sub-feature) + collapsible UI

*(Supersedes the reproducibility plan, preserved in git. Anchored on `research.md`: Hybrid model, pilot on Agentic Coding, structure-only scaffold, drawer+Explore UI.)*

**Guardrail for every phase:** `taxo verify` must stay GREEN (byte-identical replay) and the offline test
suite must stay GREEN. Run `python3 -m taxonomy.cli verify` + `python3 tests/run_all.py` after each phase.

---

## Phase 1 — Schema + validator foundation (no data yet)
**Files:** `schema.json`, `taxonomy/validate.py`, `tests/test_validate.py`
1. `schema.json`: add a `categories` `$def` (`id`, `function_id`, `name`, `description`, `order`, `feature_axis_ids[]`, all `additionalProperties:false`) and an optional top-level `categories` array. Add `"scaffold"` to the product `review_status` enum.
2. `validate.py` `_check_integrity`: add category checks — unique `id`; `function_id` resolves to a capability id; every `feature_axis_ids` entry resolves to a capability id. Add a `parent_id` **cycle/self-reference guard** (now that nesting goes deeper) → integrity issue on a cycle.
3. Tests: `categories` accepted when valid; bad `function_id`/`feature_axis_ids` → `ref_resolution`; duplicate category id → `uniqueness`; `parent_id` cycle → integrity. `test_seed_is_valid` still passes (categories optional).

**Exit:** `tests/run_all.py` green; `taxo validate` clean on current data (unchanged).

## Phase 2 — Replay/verify scaffold-skip (keep the gate honest)
**Files:** `taxonomy/replay.py`, `tests/test_replay.py`
1. `reverify_catalog`: skip records with `review_status=="scaffold"` (mirror the existing `status=="absent"` skip; count them as `"scaffold"`). They pass through unchanged → hash unaffected.
2. Test: inject a `scaffold` node into a copy of the current catalog, run `reverify_catalog` with the replay ledger, assert the catalog hash is unchanged vs. the same catalog with the node passed through (i.e. scaffold is not grounded, no `LedgerMiss`).

**Exit:** `taxo verify` still PASS on current data; new test green.

## Phase 3 — Data: categories + pilot scaffold sub-features
**Files:** `examples.json` (categories only), `data/taxonomy.json` (categories + scaffold nodes)
1. Add `categories` for `agentic-coding` to **both** files (identical block):

   | id | name | order | feature_axis_ids |
   |---|---|---|---|
   | `agentic-coding/surfaces` | Surfaces | 1 | _(empty — derived from `surfaces` field)_ |
   | `agentic-coding/agent-management` | Agent Management | 2 | `subagents-orchestration`, `managed-agent-runtime` |
   | `agentic-coding/context-memory` | Context & Memory | 3 | `agent-memory`, `mcp-connectors` |
   | `agentic-coding/execution-safety` | Execution & Safety | 4 | `code-execution-sandbox`, `guardrails-safety` |
   | `agentic-coding/quality-ops` | Quality & Ops | 5 | `agent-evals-observability`, `remote-agent-control` |

2. Add **scaffold sub-feature nodes** to `data/taxonomy.json` only (each: `kind:"feature"`, `parent_id`→ existing feature, `primary_capability_id`= parent's axis, `relation_within_capability:"partial"`, `review_status:"scaffold"`, `status:"active"`, `source{official-doc url, last_verified=as_of, confidence:"low"}`, `scope_note:"Structural placeholder — pending grounding by the maintenance loop."`).

   **Proposed pilot list (≈13 nodes) — confirm before writing:**
   - **Subagents** (under `*-subagents-orchestration` for all 3 providers): `Definition files`, `Tool scoping`, `Model per subagent` → 3 × 3 = 9 nodes. Demonstrates sub-feature-level cross-provider compare (mirrors the reference's Sub agents example).
   - **MCP & connectors** (under Anthropic + OpenAI MCP features): `Local (stdio) servers`, `Remote (HTTP/SSE) servers` → 2 × 2 = 4 nodes.

   Source URLs point at the providers' official docs (anthropic.com/openai.com/google) as grounding *targets*; names are kept generic/structural, not asserted specifics.

**Exit:** `taxo validate` clean; `taxo verify` PASS; metrics unchanged materially (provenance still counts source urls).

## Phase 4 — Collapsible UI (drawer + Explore)
**Files:** `viewer/template.html`, then regenerate `viewer/taxonomy.html`
1. Add JS helpers: `categoriesFor(functionId)`, `categoryOf(featureAxisId)`, `childrenOf(id)` (recursive), and a `treeNode(p, depth)` renderer using native `<details>/<summary>` (no JS state) — collapsed by default below the feature level.
2. **Drawer** (`featuresSection`): replace the flat list with a collapsible **category → feature → sub-feature** tree for the product. Each node shows status/relation/confidence; **scaffold** nodes get a distinct "structural · unverified" badge and a muted style. Keep `axisCompareSection` (cross-provider) intact.
3. **Explore**: when a single capability that has categories is selected (e.g. agentic-coding), group the per-provider compare cells by category (collapsible category headers). Otherwise unchanged.
4. **Styles:** `<details>` summary chevron, indentation per depth, `.b-scaffold` badge using existing tokens; light/dark parity.
5. Rebuild: `python3 -m taxonomy.cli build`.

**Exit:** `test_viewer.py` green (valid + count match); manual check the tree expands/collapses in `viewer/taxonomy.html`; categories present in the embedded blob.

## Phase 5 — Docs + final gate
**Files:** `README.md`, full verification
1. README: document the deeper taxonomy (category + sub-feature) and the collapsible UI; note scaffold/unverified semantics + how the loop grounds them. (Do **not** hand-edit `CHANGELOG.md` — it's loop-generated.)
2. Final run: `taxo validate` → `python3 tests/run_all.py` → `taxo eval` (offline) → `taxo verify` → `taxo build`. All must pass / PASS.
3. Summarize what changed; surface anything noticed outside scope (don't fix).

**Deploy:** redeploy is the user's call (per memory: `gcloud run deploy provider-seed-viewer --source viewer --region us-east5 …`). Not done automatically.

---

## Confirm before Phase 3
- The **pilot sub-feature list** above (Subagents ×3 providers + MCP ×2 providers). Add/trim any?

## Sequencing note
Phases 1→2 are pure infra (safe, test-backed). Phase 3 adds data. Phase 4 is UI. Each phase is independently reviewable and leaves the repo green. I'll implement **one phase at a time** and pause after each for your review.
