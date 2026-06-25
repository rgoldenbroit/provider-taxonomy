# Plan — Matrix as a grounded projection (scalable, no manual cell-fixes)

**Status: IMPLEMENTED (P1–P5).** The matrix is now a generated, grounded projection.
Pipeline: `matrix/capabilities.yaml` (rows) → `scripts/build_matrix.py` (Stage A catalog projection
+ adversarial confirmation → Stage B official-doc grounding → Stage C domain-restricted Tavily) →
canonical `data/agentic-matrix.json` → `scripts/render_matrix_md.py` (renders the `.md`) →
`scripts/validate_matrix.py` (gate). CI render-diffs the `.md`; `maintain.yml` re-grounds every run.
Result: **100/111 cells grounded, 11 honest `unverified`** — all grounded cells on first-party doc
hosts; the pipeline recovered 10 cells the hand-build had missed (e.g. Anthropic eval-tool, Codex
memories/plan-mode). Obsolete `scripts/matrix_to_json.py` (reverse direction) removed.

**Known follow-ups:** (1) `openai checkpoint-rewind` stays `unverified` — its `features.undo` flag is
buried in the config reference and the doc-surface keyword filter doesn't surface it (honest gap, not
chased). (2) Byte-identical replay-verify (a `taxo verify` analogue for the matrix) is not yet wired —
Stage C's Tavily *search* results aren't ledgered, so full replay needs a search-ledger space first.
Current gates (schema validate + render-drift) prevent corruption/drift; full replay is the gold standard.

## Problem
The matrix is hand-curated and its `unverified` cells came from a brittle keyword-miner over the
catalog — producing false gaps (e.g. Codex/Antigravity output-customization, Codex plan-mode). Every
new capability or provider change needs a manual web-verify + hand-edit. Not scalable.

## Principle
The matrix is a **grounded projection of the catalog**, produced by the *same* engine that builds
`data/taxonomy.json` (LLM-judge against official docs → evidence ledger → replay-verify). Reuse, don't
reinvent. The only hand-maintained thing is the neutral capability list (the "what" — editorial).

## Locked decisions
1. **Source of truth = `matrix/capabilities.yaml` (rows) + the grounded catalog/docs (cells).**
   `data/agentic-matrix.json` and the section-3 YAML in the `.md` become *generated outputs*.
2. **Grounding escalation = catalog → official docs → live Tavily.** Stage A maps from the grounded
   catalog; Stage B grounds against the provider's official doc roots; Stage C runs live Tavily
   discovery for first-party pages before giving up. Only then → honest `unverified` (or documented `none`).
3. **Cadence = every `maintain.yml` run** (re-ground on the catalog's schedule; the ledger makes
   repeat/CI runs free via replay).

## Two layers
- **`matrix/capabilities.yaml`** — `group, layer, id, name, what, tier` per row (+ optional per-cap
  search hints/keywords for Stages B/C). ~37 rows. The only file a human edits to add a capability.
- **`scripts/build_matrix.py`** — for each (capability × provider):
  - **Stage A — catalog projection.** Pull the provider's grounded agentic-coding features from
    `data/taxonomy.json`; a ledgered `llm.structured` mapper (judge tier, stable label) picks the best
    feature(s) → `{matched_id, implementation_label, confidence}` or null. Cell inherits the matched
    feature's `source.url` / `status` / `last_verified` / `confidence`.
  - **Stage B — official-doc grounding.** If A is null: `relevant_doc_pages(CAPABILITY_CONFIG[cap][prov]
    ["doc"], hints)` → `triage_one` / `_judge_grounding`. Grounded (quote verified on page) → fill cell.
  - **Stage C — live Tavily discovery.** If B misses: `get_retrieval` (Tavily + HttpFetch) restricted to
    the provider's `OFFICIAL_DOMAINS`, find a first-party page, ground it.
  - Else → `unverified` (not a claim of absence) — or `none` only if a doc explicitly says so.
  - Every LLM/page call goes through the **evidence ledger** (`TAXO_LEDGER=record|replay`).
  - Emit `data/agentic-matrix.json`; `validate_matrix.py` gates it.

## Phases (each ends validate-green)
1. **`matrix/capabilities.yaml`** — extract the 37 rows from today's matrix (mechanical) + add search
   hints per capability. No grounding yet.
2. **Stage A** — `build_matrix.py` catalog projection (ledgered mapper) → emit JSON. **Validate the
   mapper by diffing against the current hand-built matrix** (it's a strong gold reference); spot-check.
3. **Stages B + C** — official-doc grounding then Tavily fallback for cells A didn't fill.
4. **Reproducibility** — ledger spaces for the mapper + grounding; a replay/verify step that asserts the
   committed `agentic-matrix.json` is byte-identical to what the ledger re-derives. Wire into `ci.yml`
   (replay, free) and `maintain.yml` (record, every run).
5. **Rendering** — regenerate the `.md` section-3 YAML from the JSON (the `.md` becomes a rendering);
   retire the `/tmp` generator and the hand-authored-YAML-as-source. Viewer already reads the JSON.

## Risks / mitigations
- **Mapper mis-maps a catalog feature to the wrong row** → validate P2 against the hand-built gold matrix;
  the grounding gate still requires a verbatim quote on the cited page, so a bad map can't fabricate evidence.
- **Reproducibility** → mapper calls must be deterministic + ledgered (route by stable label, as the engine does).
- **Cost/latency** → ~111 mapper calls + gap-grounding per full rebuild (judge tier, cheap); replay makes
  CI/repeat runs free. Tavily (Stage C) needs `TAVILY_API_KEY` — already used by the engine.
- **The capability list stays human-authored** — intended; that's the editorial "what," and it's small.

## Interim
The uncommitted **output-customization correction** (Codex `personality`/`model_verbosity`; Antigravity
Rules) is validated and live-accurate. Recommend committing it now as an independent fix — the pipeline
will re-derive it anyway, but no reason to hold a correct change behind a ~1-day build.
