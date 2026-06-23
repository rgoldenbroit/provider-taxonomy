# Scope — "Scale & Monitor" milestone (cheap, fast, multi-capability)

*(Supersedes the agentic-coding rebuild plan, preserved in git. Goal: make a per-capability build-out
cost single-digit dollars and minutes, keep ongoing monitoring ~free, then prove it by onboarding the
consumer-chat capability. No pass should take hours or hundreds of dollars.)*

## Why each lever, and the one sharp edge

The session's ~$40–80 / ~hour was **one-time build-out**, not steady state (the content-addressed ledger
already makes unchanged docs cache-hits → monitoring is near-free). The build-out cost has four removable
multipliers. **Sharp edge:** the evidence ledger keys every LLM call by `model` (`llm_key(model=…)`) and
`ReplayLLM` recomputes that key — so any per-call model change must be **deterministic by step** (same
routing in record and replay) or `taxo verify` breaks. This constrains the design below.

## Phases

### Phase 1 — Model tiering (biggest cost lever) · effort M · risk M
- Add `route_model(label) -> (model, effort)` — deterministic by step: `extract:` / `judge:` (grounding)
  → **Haiku 4.5** ($1/$5); `consolidate:` / `insight:` / classification → **Sonnet 4.6**/**Opus** (judgment).
- Thread an optional `model`/`effort` through `LLMClient.structured` → `VertexLLM._invoke`.
- **Reproducibility fix:** `llm_key` must use the *routed* model; `ReplayLLM` calls the same `route_model`
  so record + replay derive identical keys. Shared routing function, used by both.
- Config: routing table in `config.py` (overridable); default keeps current behavior if unset.
- **Expected:** ~3–5× cheaper on the mechanical bulk (extract + grounding judges).

### Phase 2 — Prompt caching on the doc corpus · effort M · risk L
- Send each fetched doc page as a `cache_control: ephemeral` content block (Vertex AnthropicVertex
  supports it). Many calls cite the same page (a feature + its sub-features, multiple axes) → the page
  text is billed ~once, reads at ~0.1×.
- Transparent to the ledger (key = inputs, unchanged) and to replay (live-cost only).
- Touches prompt construction in `triage._judge_grounding` + `provider_scan.extract_features`.
- **Expected:** ~90% cut on repeated doc-text input.

### Phase 3 — Concurrency for sweeps + reverify · effort S–M · risk L
- Run grounding/extraction with a bounded thread pool (e.g. 8) instead of serially. Wall-clock ≈ /N.
- (Vertex Batch API = 50% off but GCS/BigQuery-based and heavier — **stretch**, not in this milestone;
  concurrency gets the time win without it.)
- **Expected:** hours → minutes.

### Phase 4 — Deterministic sub-feature receipts (skip the judge) · effort M · risk **H** (touches trust core)
- Sub-features are admitted by string-presence on the parent's cited page — deterministic, no model needed.
- In `reverify_record`/grounding: for a sub-feature (relation `partial`, parent is a feature), **skip the
  LLM judge**; write a deterministic receipt ("documented under <parent> on <page>, term present") + tier.
- `replay` reproduces it without an `llm/` entry. Cuts ~75% of judge calls (442 of 593 are sub-features).
- Highest risk — careful tests so `taxo verify` stays byte-identical.

### Phase 5 — Re-baseline the existing catalog · effort S · risk M
- Phases 1 & 4 change llm keys / receipts → one-time `reverify --record` of the current agentic catalog
  under the new routing (now mostly Haiku → **cheap**), then `taxo verify` green. Commit the new evidence.

### Phase 6 — Onboard consumer-chat (the cheap-path proof) · effort M · risk M
- **Generalize the config** (today `provider_scan.PROVIDERS` + `doc_source.DOC_SOURCES` are coding-specific):
  a per-capability registry → `{capability: {provider: {product_node, doc_source}}}`.
- Consumer chat: products = ChatGPT / Claude apps / Gemini app; doc sources = help.openai.com /
  support.anthropic.com|claude.ai / support.google.com (help centers — likely SPA → sitemap or the
  net-log asset-capture trick, already built).
- Define chat axes + keywords (memory/personalization, web & search, voice, image gen in chat,
  connectors/apps, projects/custom-GPTs, …).
- Run the same pipeline: sweep → consolidate → ground → swap → insight → reverify → verify → deploy.
- **Measure actual $ + wall-clock** — this is the proof the levers worked.

### Monitoring (no new phase — mostly inherent)
- Ongoing: re-fetch pages (parallel, cheap HTTP) → unchanged pages are ledger cache-hits (~$0); only
  changed docs incur new (Haiku) judge calls. Confirm `maintain.yml`'s reverify is incremental.

## Expected end-state economics
- **Per-capability build-out:** ~$2–5 and minutes (was $15–25, ~hour) — Haiku judges + cached doc text +
  concurrency + no-judge sub-features.
- **Weekly monitoring:** cents–low-$, minutes — only changed docs cost anything.
- **5–6 more capabilities:** ~$15–40 total. Nowhere near $1000.

## Risks & mitigations
- **Reproducibility regressions** (Phases 1 & 4 change ledger keys/receipts) → re-baseline in Phase 5,
  pin with tests asserting byte-identical replay; do Phases 1–5 before onboarding anything new.
- **Quality dip from cheaper models** → keep consolidation/insight on Opus/Sonnet; spot-check a Haiku-judged
  axis against an Opus-judged one before committing the routing.
- **Vertex caching specifics** (TTL, min-cacheable prefix) may differ from first-party → verify on a smoke
  call; fall back to no-cache if unsupported (cost-only, never correctness).
- **Sub-feature receipt change** is in the trust core → land it behind tests, smallest diff.

## Sequencing
1–4 build the cheap path (independent; 1 & 2 are the big wins). 5 re-baselines + proves verify still
green. 6 onboards consumer-chat and measures. Stretch: Vertex Batch. I'll implement one phase at a time
and pause after Phase 5 (cheap path proven on the existing catalog) before onboarding consumer-chat.

## Open questions
1. **Judge model floor** — Haiku 4.5 for grounding judges, or Sonnet 4.6 (safer, still ~1.7× cheaper than Opus)? (I'll spot-check both.)
2. **Concurrency vs. Batch** — concurrency now (simple, time-only) and defer Vertex Batch (50% cost, complex)? Recommended.
3. **Onboarding order after chat** — which capabilities next (browser-agent, knowledge-work, image/video)?
