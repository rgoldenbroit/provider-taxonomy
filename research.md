# Research — AI Provider Taxonomy system

## 0. Scope revision (what changed and why)

The first cut framed this as a **single-file static viewer** of the seed data. Your direction expands it into a **self-maintaining taxonomy system**:

- a **discovery function outside the seed** (the seed is a grounding *example*, not the universe),
- **almost entirely automated**, using an **LLM/agent to triage** finds into the taxonomy,
- a UI to **drill into a provider** and to **click a feature and see the cross-provider equivalents**,
- **reliability and trust as the first-class concern, grounded in quantitative metrics**,
- **content integrity guarded by evals**, both during development and in ongoing maintenance.

Consequence: the single static file is no longer the whole app — it becomes the **viewer**. A separate **engine** does discovery, triage, validation, and evals. `plan.md` is now stale and will be rewritten after this is approved.

## 1. Vision (restated)

A system that keeps an always-current, **trustworthy** map of AI-provider products/features organized by a stable capability taxonomy. It:
1. **Discovers** new/changed offerings across providers automatically (web search + fetch).
2. **Triages** each find with an LLM/agent: classify into capability, set scope-relation and hierarchy, dedup, link lineage, score confidence.
3. **Gates** everything on trust: nothing enters as `confirmed` unless it passes schema, grounding, and classification checks; otherwise it waits as `candidate`/`needs_review`.
4. **Presents** it: capability pivot, provider drill-down, feature-equivalence-across-providers, lineage, staleness, and the triage/review queue.
5. **Proves itself** with quantitative evals on every run, using the seed as the gold set.

`examples.json` = canonical **seed + gold set**; all new records conform to `schema.json`.

## 2. Data model (the part that constrains everything — condensed)

Capability is the stable anchor; products are 0..n per capability per provider; a comparison is a *query*, not stored data. Load-bearing fields the system must produce and the UI must render:
- `kind` (`model_family|model|product|feature|platform|protocol|service_tier`) + `parent_id` → hierarchy (family→model, product→feature/sub-product).
- `relation_within_capability` (`direct|partial|broader|none`) → scope fit vs. the capability.
- `capability_ids[]` (len>1 = spans capabilities) + `primary_capability_id` → home row.
- `status` (`active|preview|beta|deprecated|sunset|merged|renamed|absent`) + `predecessor_id`/`successor_id` → lineage; `absent` = sourced gap (`name:"(none)"`).
- `review_status` (`confirmed|candidate|needs_review|rejected`) → the discovery pipeline state.
- `source{url,last_verified,confidence}` + `lifecycle[]` (dated, sourced events) → provenance, freshness, history.

## 3. Edge-case acceptance bar (unchanged, still binding)

The 16 cases the README/seed demonstrate remain the acceptance bar — now for **two** things: the viewer must render them, and the **triage engine must reproduce them** when fed the raw facts. (Clean trio; one-to-many; broader/partial scope mismatch; sunset+successor with future-dated event; merged; pending consolidation; absence; confidence gradient; feature-of-product; sub-product; rename lineage; brand ambiguity; cross-provider deployment; model-family hierarchy; discovery candidate.) Detailed list retained from the prior draft and used as eval fixtures (§8).

## 4. Architecture (revised)

Four components:

1. **Canonical data store — JSON, git-tracked, append-only.**
   `examples.json` (seed/gold) + a working `taxonomy.json` the engine grows. Changes are expressed as new `lifecycle` events and `review_status`/field transitions, never silent overwrites.
   *Decision (you invited my judgment): JSON, not a DB.* Trust = auditability; a diffable text store makes every discovery/triage decision a reviewable diff (ideally a PR), which a database hides behind opaque mutations. The dataset is small and high-value; the schema is explicitly designed to be append-only. This is the strongest substrate for "trust is paramount."

2. **Operational store — SQLite or JSONL (telemetry, not source of truth).**
   Discovery run logs, fetched-source cache, and the **eval-metrics time series**. Kept *out* of the canonical file so the trust anchor stays clean and diffable. Metrics-over-time wants a queryable store; provenance wants a diffable one — so they're separated.

3. **Engine — Python CLI/agent.** Subcommands:
   - `discover` — per `provider × capability` web sweep → raw candidates with source URLs.
   - `triage` — LLM/agent classifies, dedups, links lineage, scores confidence, sets `review_status`.
   - `validate` — schema-subset + referential-integrity checks (fail loudly).
   - `eval` — computes the trust metrics (§7) and the gold-set regression (§8); writes a report.
   Uses `WebSearch`/`WebFetch` for grounding and an LLM for extraction/triage.

4. **Viewer — single self-contained HTML file (keeps your earlier preference).**
   Reads the produced JSON. Surfaces: capability pivot · provider drill-down · **feature-equivalence** (pick a feature/capability → the row of provider equivalents with relation tags) · lineage/history · staleness · triage/review queue showing each record's confidence, sources, and gate results. Zero-dep, opens on `file://`.

   *(Optional later: a thin local server so "Discover now" can be triggered from the UI. Not v1.)*

## 5. Discovery pipeline (front half — now in scope)

The capability taxonomy *is* the search plan. For each `(provider, capability)`:
1. Query the web for the provider's current offering(s) in that capability.
2. Extract candidate products/features + the **source URL** that substantiates each.
3. **Dedup** against existing `product.id`s, including **rename detection** (don't re-add Vertex AI as new when it became Gemini Enterprise Agent Platform).
4. Emit `review_status:"candidate"` nodes with `source`, a best-guess `primary_capability_id` (or the reserved `unclassified` bucket), and confidence `low` until triage.

Almost fully automated. Human involvement is *optional* and bounded to approving promotions that the trust gates didn't auto-clear.

## 6. Triage (LLM/agent — now in scope)

Per candidate, the agent decides: capability(ies) + `primary_capability_id`; `relation_within_capability`; `kind` + `parent_id` (hierarchy/feature/sub-product); `surfaces`; lineage links; and a confidence grounded in evidence + self-agreement. It then sets `review_status`:
- `confirmed` — passes all three gates above the auto-confirm bar,
- `needs_review` — grounded but low classification agreement,
- `rejected` — fails the grounding gate (no source substantiates it) → kept (not deleted) so it isn't rediscovered.

## 7. Trust & reliability framework (the heart of the ask)

Every record passes three **gates**; each emits a number, so trust is quantitative, not vibes:

| Gate | Question | Metric | Fail behavior |
|---|---|---|---|
| **Schema** | Conforms to `schema.json` + referential integrity? | conformance (must be 100%) | reject |
| **Grounding** | Does a *fetched* source actually substantiate the claim? | grounding rate (% of records whose `source.url`, when fetched, an independent LLM-judge confirms supports it) | hold as `candidate`/`rejected`, never auto-confirm |
| **Classification** | Is the capability/relation assignment stable? | self-consistency across N LLM samples; agreement vs. gold where it overlaps | `needs_review` if low |

**Anti-hallucination (the core trust guarantee):** a discovered product is admitted *only if* its `source.url` fetches and a **separate** LLM-judge confirms the page substantiates the product's existence and key attributes. No verifiable source → not admitted. The discoverer never gets to self-certify.

**Dataset-level metrics** (computed every run, stored as a time series):
- grounding rate, provenance completeness (every product ≥1 source; every claim-bearing lifecycle event has a `source_url`),
- schema/integrity conformance (target 100%),
- classification accuracy vs. gold (precision/recall per capability),
- dedup precision/recall (incl. rename cases),
- staleness coverage (% within the confidence-based re-verify window: high=90d/med=45d/low=21d),
- confidence calibration (do `low`-confidence records actually get corrected more often?),
- estimated hallucination rate (admitted records later found ungrounded).

## 8. Evals — development *and* ongoing maintenance

The seed is a labeled **gold set**, which makes real evals possible:
- **Hold-out reconstruction:** remove N seed records, run `discover`+`triage`, measure recovery + correct classification (capability, relation, hierarchy, lineage). This is the dev-time integrity test and the regression guard.
- **Adversarial / hallucination:** inject a plausible-but-fake product with a bogus/irrelevant URL; the grounding gate must reject it. Tracks false-admit rate.
- **Dedup/rename:** feed a rename event; pipeline must link, not duplicate.
- **Regression gate:** every run emits a metrics report; if grounding rate, conformance, or classification accuracy drop below thresholds, candidate→confirmed promotion is blocked and the run is flagged. This is how ongoing maintenance stays honest.
- Stale records are re-verified on a schedule; metrics tracked over time in the operational store so drift is visible.

## 9. Constraints / non-negotiables

- `examples.json` + `schema.json` are canonical; every emitted record conforms and is referential-integrity-clean.
- Append-only history (lifecycle events); never silent overwrite.
- **Never admit ungrounded content** — no record without a fetched, verified source.
- The engine needs network + an LLM; the **viewer does not** (reads produced JSON, opens offline).
- Don't log whole responses/configs/secrets — specific fields only (global rule).

## 10. Decisions I made on your behalf (correct me if wrong)

1. **Storage:** JSON canonical (diffable, auditable) + SQLite/JSONL for telemetry/metrics. Not a DB for canonical data — auditability beats query convenience when trust is the point.
2. **Form factor:** Python **engine** (discover/triage/validate/eval) + static **single-file viewer**. Keeps your single-file preference for *browsing*; the automated work lives in the engine.
3. **Auto-confirm bar:** records auto-confirm only above a high grounding+agreement threshold; everything else lands as `needs_review` for a human. Safer default given "trust is paramount."

## 11. Open questions (genuinely block or steer the build)

- **Q1 — LLM access (blocker for the engine).** How should the engine call a model here? Options: (a) Anthropic API key in env; (b) Vertex AI Claude (the `scaffold-gcp-app` pattern); (c) build the engine model-agnostic behind a small client interface and stub the LLM in dev so the whole pipeline runs end-to-end without creds, with the real client dropped in later. I lean **(c)** — it lets me build and *eval* the harness deterministically now, and it's the most testable. Do you have creds you want used, or should I go stub-first?
- **Q2 — Prove-the-loop scope.** Run the first end-to-end discover→triage→eval on **one capability** (I'd pick `agentic-coding`, the richest edge-case cluster) before fanning out to all providers × all capabilities? I lean **yes** — get the trust loop + gold-set eval green on one slice, then scale.
- **Q3 — Viewer now or after the engine?** Build the engine + trust/eval first (the substance of your ask) and the viewer second, or interleave? I lean **engine-first**, with a minimal viewer stub early so you can see results, then enrich it.

## 12. Out of scope for v1

Multi-user/auth/hosting; real-time streaming discovery (v1 = on-demand/scheduled batch runs); UI-triggered discovery (needs the optional local server); write-back to the seed from the viewer (the engine owns writes, as reviewable diffs).
