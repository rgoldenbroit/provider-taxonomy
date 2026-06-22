# Plan — Fill in Agentic Coding content (grounded, live)

*(Supersedes the deeper-taxonomy plan, preserved in git. Anchored on `research.md`: complete the 5
categories across Claude Code/Codex/Antigravity, hybrid population, live grounding now.)*

**Decisions (recs accepted):** proposed sub-feature curation table · `needs_review` = keep-and-flag ·
CI/GitHub surface = defer. **Pinned `as_of` = 2026-06-21** (written by the final record pass).

**Invariant:** admit-only-what-grounds. An ungrounded/blocked cell is left empty or `scaffold` — never fabricated. End state must be: `taxo verify` byte-identical + `taxo gate` PASS.

---

## Phase A — Live smoke-test + fill missing feature cells
1. Smoke-test the live stack with one cheap call: `TAXO_OFFLINE=0 .venv/bin/python -m taxonomy.cli ping` (or `search`). Abort if Vertex/Tavily aren't reachable.
2. Run `TAXO_OFFLINE=0 .venv/bin/python scripts/ground_features.py` — idempotent; targets the empty cells (Google managed-agents, Google MCP, Google remote-control, etc.). Admit only grounded.
3. Reconcile classification gaps the script can't (pin `kind`+axis, judge sets relation only):
   - Google MCP: fold the existing non-`feature` MCP record into a `feature` under the right product, or let ground_features create the Antigravity/Jules MCP cell.
   - Google remote-control: ensure **Jules** fills the `remote-agent-control` cell (it *is* the async agent).

## Phase B — Reconfirm the 2 `needs_review`
- Codex managed agents, Codex guardrails: re-grounded by the Phase-D record pass; if they reconfirm → `confirmed`, else keep-and-flag (no downgrade of real records — conservative reverify).

## Phase C — Curate + ground sub-features (the bulk)
1. Write **`scripts/ground_subfeatures.py`** (modeled on `ground_features.py`, one level deeper): a curated `SUBFEATURES` list of `(parent_feature_id, provider, [(name, search_kw, official_url)])`; for each, build a `kind:"feature"` candidate with `parent_id`=the feature, `pinned_capability`=parent's axis, and ground via `triage_one`. **Flip the 13 existing `scaffold` ids in place** (same id) to the grounded decision; append new ones. Admit only `confirmed`/`needs_review`; drop rejected.
2. Curated targets (~2 per axis×provider where docs support it — from `research.md`): subagents (Definition files/Tool scoping/Model per subagent), managed-runtime, mcp, memory, sandbox, guardrails, evals, remote-control. Official-domain URLs only.
3. Run live; report per-cell decision + grounding score + admit/drop counts.

## Phase D — Evidence capture + reproducibility
1. `TAXO_OFFLINE=0 TAXO_LEDGER=record .venv/bin/python scripts/reverify.py` with **`as_of=2026-06-21`** → re-grounds every non-`scaffold` record, writes `evidence/` pages+LLM+provenance receipts, sets `_meta.as_of`. (Scaffold-skip means Phase C must have flipped sub-features out of `scaffold` first — sequencing enforced.)
2. `python3 -m taxonomy.cli verify` (replay, no creds) → **must be byte-identical**.

## Phase E — Gate + ship
1. `taxo validate` → `python3 tests/run_all.py` → `taxo eval` → `taxo audit`/`taxo gate` (must PASS; 0 critical).
2. `taxo build`; headless-Chrome render check (zero JS errors; new content shows in the Overview inline tree + Explore + drawer).
3. `gcloud run deploy provider-seed-viewer --source viewer --region us-east5 --allow-unauthenticated --quiet`; confirm live == local hash.
4. `git add -A && commit && push`; update project memory.

---

## Execution notes
- All live runs: `.venv/bin/python` + `TAXO_OFFLINE=0` (system python3 lacks the `anthropic` SDK).
- Cost: concentrated in Phase C (~2 calls/sub-feature). I'll report running counts; if a provider's docs don't substantiate a sub-feature, it's dropped (empty cell), not invented.
- If the live stack is unreachable (auth/quota), I stop and report — I won't fake grounding or commit ungrounded records as confirmed.
- I'll proceed through all phases without stopping (per "go ahead"), reporting at the end + deploying.
