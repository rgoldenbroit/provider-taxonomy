# Plan — Provider-first, real-named, insight-driven Agentic Coding (automated)

*(Supersedes the grid-fill plan, preserved in git. Anchored on `research.md`: portfolio bar =
cross-provider completeness + polish + insight; automated pipeline; accuracy + completeness override
automation convenience.)*

**Decisions locked:** automated provider-first pipeline · names extracted from the grounded page ·
Gemini CLI dropped (lifecycle-verified) · per-axis `comparison_note` insight field · axis set may grow
to match what providers actually ship (bounded to Agentic Coding).

**Invariants:** admit-only-what-grounds (no fabricated cells/names); every node parented to a product
(no orphans); end state = `taxo gate` PASS + `taxo verify` byte-identical. Live runs use
`.venv/bin/python` + `TAXO_OFFLINE=0`; discovery via Tavily + HttpFetch (Claude web tools org-blocked).

---

## Phase 1 — Schema + validator
- `schema.json`: add optional `comparison_note` (string) to **capability** (the per-axis insight) and
  optional `comparison_note_sources` (array of urls). No new required fields. Allow the axis set to grow
  (already additive).
- `validate.py`: nothing new required (optional fields pass the walker); add a test that
  `comparison_note` validates and that a capability without it still validates.
- Tests: schema accepts / round-trips `comparison_note`.

## Phase 2 — Build the automated provider-first pipeline (the core)
Modules `taxonomy/provider_scan.py` + `taxonomy/doc_source.py` + driver `scripts/repopulate_agentic.py`.
Per provider (Anthropic→Claude Code; OpenAI→Codex; Google→Antigravity + Jules):
1. **Retrieve the provider's structured doc surface** (NOT web search): tiered
   `llms-full.txt`/`llms.txt` (per-page `.md`) → `sitemap.xml` → headless-Chrome render for JS docs.
   Wrap fetched clean pages as a retrieval provider so the grounding judge runs against real markdown;
   Tavily is a last-resort discovery fallback only.
2. **Extract** features per page (new LLM step, structured): for each, the **real name as the page
   calls it**, a one-line claim, a verbatim quote, lifecycle status, and a suggested axis. Names come
   from the page, never templated.
3. **Classify → axis**; **parent → the provider's product** (no orphans by construction). New axes are
   created when a real feature fits none (axis set grows); slotted into a category.
4. **Ground** each via `triage_one` (judge confirms the named feature is on its cited page) → accuracy;
   confidence from source tier. Admit only `confirmed`/`needs_review`.
5. **Completeness critic, loop-until-dry:** after each pass, an LLM critic lists documented
   agentic-coding capabilities for provider X *not yet captured* and emits new queries; loop until 2
   dry rounds. **Cap: max 4 rounds/provider** (cost guard; log what was dropped if capped).
6. **Lifecycle:** capture `status`; a deprecated/sunset offering (e.g. Gemini CLI) gets a `deprecated`
   badge + dated `lifecycle` event, not a feature slot.
- **Pilot checkpoint:** run the pipeline on **one axis across all 3 providers (subagents)** first;
  inspect real names + grounding scores + parenting before the full sweep. Adjust prompts, then run all.

## Phase 3 — Replace templated content + structural cleanup
- **Swap in** the pipeline output for the agentic-coding feature/sub-feature subtree, **removing the 22
  templated nodes** they supersede (keep top-level products + capabilities).
- **Structural fixes:** re-parent any residual orphans (evals ×3, Anthropic guardrails, OpenAI MCP) to
  products; **Google MCP** `service_tier`→`feature`, parented; **fold the empty "Antigravity CLI"**
  into Antigravity (or drop); ensure Google = Antigravity + Jules only.
- **Parity check (deterministic):** for each axis, assert all 3 providers are either represented or a
  **grounded absence** (`status:absent` + note) — never a silent blank. Log the parity matrix.

## Phase 4 — Comparative-insight synthesis
- For each axis, synthesize `comparison_note` (one grounded sentence contrasting the 3 approaches) from
  the verified per-provider features; attach `comparison_note_sources` (the per-provider citations).
  Editorial-but-grounded: must reference only captured facts.

## Phase 5 — Evidence + reproducibility
- `TAXO_OFFLINE=0 TAXO_LEDGER=record TAXO_AS_OF=<run date> .venv/bin/python scripts/reverify.py` →
  re-ground all records, write provenance receipts.
- `taxo verify` (replay) → **must be byte-identical**.

## Phase 6 — Viewer
- Render the per-axis `comparison_note` as a callout in the comparison views (Explore compare,
  Overview-inline breakdown, and/or the drawer's axis section). Confirm real names show; rebuild
  `taxonomy.html`. Headless-Chrome check: zero JS errors, insight callouts visible.

## Phase 7 — Gate + ship
- `taxo validate` → `tests/run_all.py` → `taxo eval` → `taxo audit`/`gate` (0 critical) → `taxo build`.
- `gcloud run deploy …` (us-east5); confirm live == local hash.
- `git add -A && commit && push`; update memory.

---

## Quality bars (how "accuracy + completeness" are enforced, not just claimed)
- **Accuracy:** every feature name + claim grounded on its cited official page; confidence derived from
  source tier; reproducible via `verify`. Names judge-confirmed against the page.
- **Completeness:** the loop-until-dry critic per provider (not first-query-and-stop); the deterministic
  parity check flags any axis missing a provider; capped rounds are logged, never silent.
- **Honesty:** ungrounded → dropped; genuine gaps → grounded `absent` with a note; deprecated → badged.

## Risks
- **Live cost/time** (Phase 2 is the bulk — many pages × extract/ground/critic calls). Mitigate: pilot
  on one axis first; round cap; report running counts.
- **Extraction over-/under-splitting** (a page lists many sub-bullets). Mitigate: judge-grounding +
  node-worthiness audit (a feature earns a node only if it's a real cross-provider axis; else it's a
  sub-feature or scope_note).
- **Rebuild is destructive.** Mitigate: work on a copy, diff old→new before swap, keep git as the undo;
  `verify` proves the new state reproduces.
- **Insight drift into opinion.** Mitigate: synthesize only from captured facts + require citations.

## Sequencing
Phases 1→2 build the machine (with a pilot checkpoint inside 2). 3→5 produce + harden the data. 6→7
present + ship. I'll pause after the **Phase 2 pilot** to show you real-name/grounding quality before
the full sweep — and again before deploy if you want.
