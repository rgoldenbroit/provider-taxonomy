# Plan — bring the matrix up to the catalog's verification bar

**Status: PLAN — awaiting approval.** Goal: make every grounded matrix cell pass the *same class* of
checks the Overview/catalog uses, by **reusing the catalog's machinery** rather than running a thinner
parallel path. Trust = precision; accept more honest `unverified`.

## Why (the gap, confirmed in code)
The catalog and matrix share the grounding primitive (`grounding_gate`: a judge must find the claim
**quoted verbatim** on the page). The catalog wraps it in gates the matrix skips, and the matrix adds an
unguarded generative step:

| Check | Catalog (`triage_one` + `audit`) | Matrix today |
|---|---|---|
| Verbatim-quote grounding | ✅ | ✅ (shared) |
| Majority-vote classification (3 samples, ≥2/3) | ✅ `classification_gate` | ❌ (Stage A: 1-shot; B/C: none) |
| Second-source triangulation | ✅ `audit._triangulate` | ❌ |
| Gold-set + adversarial eval gate | ✅ `cmd_eval` | ❌ |
| Red-team audit before ship | ✅ `cmd_audit` | ❌ |
| Generated prose (hallucination surface) | none — stores verbatim quote + fields | ❌ unguarded `describe` |
| Inference direction | bottom-up (extract what's on the page) | top-down "is X here?" (confirmation-bias prone) |

This is why `prompt-caching/google` grounded to a page with no caching, and `context-compaction/google`
got mislabeled "Context Caching": a single top-down judgment + an unverified description, with none of
the catalog's corroborating gates.

## Design — reuse first, add only what the catalog can't lend
**Reuse as-is:** `grounding_gate` / `quote_supported` (already), `audit._triangulate` (second source),
the engine's LLM client + evidence ledger + `get_retrieval` + `source_tier`.

**Add (matrix-specific, because the catalog classifies into *its* taxonomy and stores no prose):**
1. **Distinctness confirmation (3-sample majority).** After a page passes `grounding_gate`, run the
   judgment **3×** with an adversarial, distinctness-aware prompt: *"Does this page document SPECIFICALLY
   `<capability>` — NOT the adjacent capabilities `<sibling rows>` (e.g. context **caching** vs context
   **compaction**) — as a shipped feature?"* Require ≥2/3 yes. (Mirrors `classification_gate`'s rigor,
   specialized to the matrix taxonomy + the adjacency trap.)
2. **Second-source triangulation.** Build a record and call `audit._triangulate`; if a cell can't be
   corroborated by an independent second source, mark it `single_source` → drop to `unverified`.
3. **Description faithfulness gate.** `describe` must also return a **verbatim anchor quote**; reject
   (via `quote_supported`) if the quote isn't on the page, or if the label/description names a feature
   the page doesn't support. Applies to **all** generated cells (Stage A included — the compaction
   mislabel was a describe error). Keeps the plain-language description you wanted, but tied to evidence.
4. **Conflation guard.** When one page would ground multiple capabilities for a provider, each must pass
   the distinctness confirmation independently (the Antigravity agent page proves compaction + cloud, but
   not caching → the caching cell drops).

Net effect: Stage A (catalog projection) is already the bottom-up, pre-triaged path — keep it; harden
Stage B/C (the top-down gap-filler, where the errors live) and the describe step.

## Phases
1. **Read-only audit (quantify first).** Run the new checks over all 100 currently-grounded cells without
   changing data → report: PASS / false-positive / mislabeled / single-source, with the offending URL per
   cell. Gives the real error rate and the fix list. *(No data change; ~200–300 ledgered LLM calls.)*
2. **Wire the gates into `build_matrix.py`** and re-run. Cells failing any gate → honest `unverified`.
   Produce a **diff** (dropped / relabeled / re-grounded). Expect grounded to fall (100 → ~80–88) — that
   drop *is* the fix.
3. **Review the diff together**, then render → rebuild → you redeploy.

## Tradeoffs / risks
- **Fewer green cells, all trustworthy** — explicit and intended.
- **Cost:** ~5–6 LLM calls + 1 Tavily search per cell on a full live build (×100). Ledgered, so CI/replay
  stays free; the live re-run is the spend.
- **Recall misses persist** (e.g. Antigravity plan-mode — no plan-mode doc found on the pages checked, so
  `unverified` may be *correct*). The completeness critic can *flag* gaps but won't manufacture grounding.
- Stage C triangulation needs `TAVILY_API_KEY` (already configured).

## Decision needed
Start with **Phase 1 (read-only audit)** so you see the real error rate before any change? Or go straight
to building + diffing (Phase 2)?
