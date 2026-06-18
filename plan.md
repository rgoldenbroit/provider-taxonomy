# Plan — trustworthiness + reproducibility (then #1/#2/#3)

*(Supersedes the reliability plan, preserved in git. Anchored on the "lockfile for facts" thesis in `research.md`: trust and reproducibility are one problem — a durable, content-addressed evidence trail.)*

**Decisions (confirmed):** commit the evidence bundle into the repo (self-contained reproducibility); backfill provenance for the existing records (no partial receipts). Achievable target = **replay-determinism** (`taxo build --replay` reproduces from the ledger, like `npm ci` from a lockfile) — not bit-reproducibility on re-derivation.

---

## Phase 1 — Evidence ledger + dual cache (reproducibility backbone)
`taxonomy/ledger.py`: a content-addressed store with modes **record** (live calls run, results stored), **replay** (no live calls; a miss is an error), **off** (legacy). Two spaces: `page` (fetched snapshots) and `llm` (`hash(model+system+prompt+schema) → response`). Wire into `VertexLLM.structured` and `HttpFetch.fetch` (opt-in via config, default off → existing behavior unchanged). Committed under `evidence/`.
*Checkpoint: tests green; a record→replay round-trip reproduces a result deterministically, offline.*

## Phase 2 — Provenance receipts (the trust trail)
During triage, write a per-record receipt to `evidence/provenance/<id>.json` (OUTSIDE the catalog — no schema change): query · candidate sources · chosen source + page-snapshot hash · judge `supported` + verbatim quote · classification agreement · gate scores · model id · run id · verified_at.

## Phase 3 — Tiered admission + derived confidence (accuracy; = rec #3)
Source tiers: official > reputable-secondary > unknown/low (allow/block heuristics kill junk domains). Admission: **confirmed requires official OR ≥2 independent reputable corroborations**; a lone low-tier source → needs_review/unknown. **Confidence computed** from tier + corroboration + recency. Then a **recorded canonical rebuild**: re-run the catalog through the instrumented pipeline in record mode → a fully-evidenced, higher-quality catalog + committed ledger (demotes the 14 unconfirmed, fixes weak names/sources).

## Phase 4 — `verify` command + reproducible-build CI (= rec #2)
Catalog carries a build manifest (input commit · ledger hash · model id · engine version · eval metrics · **output content-hash**). `taxo verify` replays the ledger and asserts the catalog hash matches. CI (GitHub Actions): run the 80 tests + `taxo verify` on push → green "tests + reproducible build" badge. Add LICENSE + runbook.

## Phase 5 — Receipts in the UI (visible trust)
Each record's drawer gains a "Why we believe this" panel: the verbatim quote from the actual page, source + tier, gates cleared, corroboration count, verified date — read from the provenance ledger.

## Phase 6 — Self-maintaining loop (= rec #1)
Scheduled GitHub Action runs the pipeline on a rotating capability in record mode, appends to the ledger, commits the diff, and emits a **"what changed" changelog** (falls out of the ledger). Site shows a real "last built / last changed" signal. This is now reproducible + auditable by construction.

---

## Guards
- Ledger is **opt-in** (config `LEDGER_MODE`, default off) → existing offline tests/behavior unchanged.
- Provenance lives outside the catalog → **no schema change**.
- Replay-determinism is the explicit, stated target (not re-derivation determinism).
- Each phase ships behind tests; live recorded rebuild (Phase 3) is the only heavy run and is checkpointed.

→ Starting Phase 1 now; checkpoint after each phase.
