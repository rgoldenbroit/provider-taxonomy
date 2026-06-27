# Plan — Scope-B: weekly self-healing gap discovery (A1 · B1+B2 · C1 · D2)

Build a matrix-gap-driven autonomous discoverer that feeds the **catalog** (never the matrix build),
reusing Tavily(include_domains) + `ground_gap`'s verify-safe admit + sticky + the overlay. Search stays
un-ledgered (proven safe — see research.md). Each phase ends green: `validate` + `verify` + tests.

## Core design decision (C1 done right)
A *well-grounded* discovered record would otherwise project straight to `active`, skipping human review.
To keep "machine proposes, human disposes": autonomous discoveries are admitted with
`review_status: "candidate"` (not `confirmed`), and the matrix renders a cell grounded on a
non-`confirmed` feature as **`needs_review`** until a human promotes it via `review-decisions.yaml`
(confirm) — or rejects it. Existing pipeline records are all `confirmed`, so nothing changes for them.

## Phase 1 — Reusable verify-safe admit + official domains
- Extract `ground_gap`'s admit core into `admit_grounded(provider, root, name, kind, cap, url, *, as_of,
  review_status="candidate", audit=None)` (fetch → `triage_one` → `reverify_record` at `as_of` →
  re-pin id/parent → append). `ground_gap.py` keeps working via this shared function.
- `PROVIDER_DOMAINS = {provider: [official doc hosts]}` (Anthropic: code/docs.claude.com, claude.com;
  OpenAI: developers/platform.openai.com, openai.github.io; Google: antigravity.google, ai.google.dev,
  adk.dev, google.github.io). Reuse `sources.py` host knowledge if it already encodes this.
- *Done when:* `ground_gap` still grounds hooks + `verify` PASS (no behavior change), unit test for the
  refactor.

## Phase 2 — The scout driver (`scripts/scout_gaps.py`)
- Read `data/agentic-matrix.json` → the `unverified` cells, each carrying (cap_id, provider, lineup root,
  `hints` from `matrix/capabilities.yaml`).
- Per gap: `tavily.search(query=hints-join, include_domains=PROVIDER_DOMAINS[provider], max_results=…)` →
  top first-party hits.
- Per top hit: a slim LLM extraction (ledgered) — "name the feature on this page that realizes
  `<capability what>`; quote it verbatim or return none" → candidate (name + supporting quote).
- `admit_grounded(..., url=hit.url, review_status="candidate", audit={query, result_url, snippet})`.
  The grounding gate still requires the verbatim quote on the page, so nothing ungrounded enters.
- **B2:** the `audit` dict is written into the provenance receipt (`discovered_via`) — safe for `verify`
  (it hashes catalog records, not receipts).
- Offline/keys guard: needs `TAXO_OFFLINE=0` + `TAVILY_API_KEY` (set). Caps per run (e.g. 1–2 URLs/gap).
- *Done when:* a dry run on the current 20 gaps admits ≥1 real feature as `candidate`; `verify` PASS.

## Phase 3 — Matrix renders candidate discoveries as `needs_review` + UI review queue
- In `build_matrix.py` cell loop: when a chosen/sticky feature has `review_status != "confirmed"`, emit a
  `needs_review` cell (carrying its real fields) unless the overlay has a `confirm` verdict for it. A
  `confirm` verdict promotes it to grounded (existing path); a human can also bump the catalog record to
  `confirmed`. Sticky doesn't protect a `needs_review` cell (so it re-decides until confirmed) — correct.
- **UI review mechanism (static viewer, no backend):**
  - A **"Review queue"** affordance in the matrix toolbar: a chip + count badge that filters to only
    `needs_review` cells, so the pending queue is one click to scan.
  - In the cell drawer for a `needs_review` cell: **Confirm** / **Reject** buttons that **copy a
    ready-to-paste `review-decisions.yaml` entry** to the clipboard (cap, provider, verdict, feature,
    `reason: ""` placeholder, date). The static page can't persist, so the workflow is: review in the UI →
    click → paste the snippet into `matrix/review-decisions.yaml` → commit → next build applies it.
  - The cell already shows the candidate, its first-party `docs ↗` link, and the "why" — enough to decide.
- *Done when:* a scouted `candidate` shows `needs_review`; the review-queue chip filters to it; Confirm/Reject
  copy a valid YAML decision; pasting a `confirm` + rebuild flips it to grounded; `validate` PASS.

## Phase 4 — Tests + reproducibility
- Tests (offline `StubLLM` + a stub Tavily poster): scout picks the official-domain hit; extraction→admit
  produces a `candidate`; `admit_grounded` writes a reproducible record (reverify-normalized); the
  `review_status!=confirmed → needs_review` rule; overlay `confirm` promotion.
- Full suite + `verify` PASS. Confirm the only catalog delta is the newly-admitted candidate(s).

## Phase 5 — Weekly self-heal in `maintain.yml` (D2)
- Add a step (gated on the `TAVILY_API_KEY` secret + Vertex WIF): `scout_gaps` → re-project (sticky) →
  render `.md` → `validate` → `verify` → write changelog.
- **Safety rollout:** land it as a **PR-opening** step (or a `scout/<date>` branch), NOT a direct push to
  `main` — so a human reviews the proposed `needs_review` cells before they're published, and adjudicates
  via `review-decisions.yaml`. (maintain.yml already commits; we scope the scout output to a branch/PR.)
- Document the loop in OPERATIONS.md: weekly → scout proposes `needs_review` → human confirms/rejects in
  the overlay → next run is stable (sticky).
- *Done when:* a manual `workflow_dispatch` produces a reviewable PR with new `needs_review` cells +
  committed evidence, CI (tests + verify + matrix-validate) green on it.

## Risks / mitigations
- **Wrong page grounded** → grounding gate (verbatim quote) + `include_domains` + lands as `needs_review`
  for human confirm. Nothing auto-activates.
- **Reproducibility** → every admit goes through `admit_grounded`'s reverify-at-`as_of` (the trap from last
  round, now centralized). Tests assert `verify` byte-identical.
- **Cost** → ~20 searches + slim extractions + groundings/run, judge tier; replay makes CI free.
- **Recall ceiling** → A1 only chases *known* gaps; a completeness-critic sweep (A2) is a later add.
- **Auto-commit safety** → PR/branch, not direct-to-main (Phase 5), so a human is always the gate to publish.

## Sequencing
P1 (refactor, no behavior change) → P2 (scout, dry-run) → P3 (needs_review rendering) → P4 (tests/verify)
→ P5 (weekly, PR-gated). Stop after each for review; deploy only after a human adjudicates the first batch.
