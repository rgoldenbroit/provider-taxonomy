# Research — Filling in the Agentic Coding content (grounded)

## Goal & locked decisions

Now that the structure (5 categories + scaffold sub-features) is right, **populate the Agentic Coding
function with real, grounded content** through the existing trust pipeline. Decisions (Q&A):
- **Scope:** complete the **5 current categories** (Surfaces · Agent Management · Context & Memory · Execution & Safety · Quality & Ops) across **Claude Code · Codex · Antigravity** (+ Jules where it's the relevant offering).
- **Method:** **Hybrid** — engine discovery (Tavily, official-docs-scoped) for feature/coverage breadth + operator-curated **sub-feature** depth from official docs; the pipeline grounds everything.
- **Grounding:** **run live now** (Vertex global · `claude-opus-4-8` · Tavily). Admit-only-what-grounds.

## How "filling in" works here (not hand-typed facts)

A record becomes content only by clearing the pipeline that produced the existing 48 grounded records:
1. **Candidate** node authored with an official `source.url` (operator-curated for sub-features; Tavily-discovered for feature cells).
2. **`triage_one(record, dataset, llm, retrieval, evidence=, pinned_capability=)`** fetches the cited page, an LLM **grounding judge must find the claim quoted on it**, classifies, and returns an `Outcome{decision: confirmed|needs_review|rejected, record, report.grounding.score}`. Confidence is **derived from source tier** (`sources.py`), not asserted.
3. Admit only `confirmed`/`needs_review`; **rejected/ungrounded cells stay empty or `scaffold`** — an honest "not verified", never fabricated.
4. **Evidence capture:** `scripts/reverify.py` in `TAXO_LEDGER=record` re-grounds every (non-scaffold) record, writing page+LLM+**provenance receipt** into `evidence/` → the catalog becomes **replay-reproducible**.
5. `taxo verify` (replay) asserts byte-identical; `audit`/`eval`/`gate`; `build`; deploy.

## Current coverage map (the gap to close)

Per category → feature-axis → provider (`feature` nodes), from `data/taxonomy.json`:

| Axis (category) | Anthropic | OpenAI | Google | Sub-features today |
|---|---|---|---|---|
| subagents-orchestration (Agent Mgmt) | ✅ confirmed | ✅ confirmed | ✅ confirmed | 3 scaffold × 3 providers (Definition files · Tool scoping · Model per subagent) |
| managed-agent-runtime (Agent Mgmt) | ✅ confirmed | ⚠️ needs_review | ❌ **missing** | none |
| agent-memory (Context & Mem) | ✅ | ✅ | ✅ (Jules) | none |
| mcp-connectors (Context & Mem) | ✅ + 2 scaffold | ✅ + 2 scaffold | ❌ **missing-as-feature** (a Google MCP record exists but isn't a `feature` under a product) | 2 scaffold × 2 providers |
| code-execution-sandbox (Exec & Safety) | ✅ | ✅ | ✅ | none |
| guardrails-safety (Exec & Safety) | ✅ | ⚠️ needs_review | ✅ | none |
| agent-evals-observability (Quality & Ops) | ✅ | ✅ | ✅ | none |
| remote-agent-control (Quality & Ops) | ✅ | ✅ | ❌ **missing** (Jules *is* Google's async/remote agent — a classification gap, not a real absence) | none |

**Three workstreams fall out:**
- **A — Fill missing feature cells:** Google managed-agents, Google MCP (reconcile the existing record into a `feature`), Google remote-control (map Jules). `scripts/ground_features.py` already iterates this exact CLUSTER (incl. `google-antigravity-2-0`, `google-jules`) × 7 AXES and **skips existing** → running it live attempts precisely the empty cells.
- **B — Reconfirm the 2 `needs_review`:** Codex managed agents, Codex guardrails (re-ground → confirm or keep flagged).
- **C — Curate + ground sub-features** for every axis that has none, per provider (operator-curated from official docs, then judged). Also ground the 13 existing scaffold sub-features (flip `scaffold` → `confirmed`/`needs_review` with evidence).

## Tooling

| Step | Tool | Notes |
|---|---|---|
| Fill feature cells (A) | `scripts/ground_features.py` (exists) | live; idempotent; admit-only-what-grounds. Run as-is. |
| Reconfirm needs_review (B) | `scripts/reverify.py` (record) | re-grounds + re-grades the 2 records. |
| Ground sub-features (C) | **new `scripts/ground_subfeatures.py`** | modeled on `ground_features.py`, one level deeper: `parent_id`=a feature node, `pinned_capability`=parent's axis, curated `(feature, provider) → [sub-feature name, search kw, official url]` list. Converts existing scaffold ids in place + appends new ones. |
| Evidence + reproducibility | `scripts/reverify.py` `TAXO_LEDGER=record` → `taxo verify` (replay) | captures receipts; proves byte-identical. |
| Ship | `taxo audit`/`eval`/`gate` → `taxo build` → `gcloud run deploy` | the established gate + deploy. |

## Sub-feature curation (workstream C) — proposed shape

~2 sub-features per `(axis × provider)` where official docs support them (admit only what grounds). Illustrative targets (final list confirmed at plan):
- **subagents** → Definition files · Tool scoping · Model per subagent (the existing 13 scaffold).
- **managed-agent-runtime** → Hosted execution · Parallel/queued tasks.
- **mcp-connectors** → Local (stdio) servers · Remote (HTTP/SSE) servers (+ Google once the feature cell exists).
- **agent-memory** → Project memory file · Cross-session/persistent memory.
- **code-execution-sandbox** → Network policy · Filesystem isolation.
- **guardrails-safety** → Permission/approval modes · Allow/deny rules.
- **agent-evals-observability** → Tracing/logs · Eval harness.
- **remote-agent-control** → Async task hand-off · Status/notifications.

Each curated entry carries an **official-domain** URL (`docs.anthropic.com` · `developers.openai.com`/`platform.openai.com` · `antigravity.google`/`ai.google.dev` — all official-tier per `sources.py`). The judge verifies the quote actually appears; ungrounded ones are dropped, not faked.

## Surfaces category (special-cased)

`agentic-coding/surfaces` has **empty `feature_axis_ids`** — surfaces aren't feature nodes; the engine deliberately folds CLI/IDE/web/mobile into the product's **`surfaces`** field (`autobuild._fold_surface`). So "completing Surfaces" = verifying each product's `surfaces[]` is accurate/complete (and modelling CI/GitHub as a surface where real). Rendered as a read-only "Surfaces" row in the breakdown, not as groundable sub-features.

## Live stack & reproducibility (verified)

- `taxo config`: project `second-impact-444322-p8` · region **global** · model `claude-opus-4-8` · **Tavily configured**. `.env.local` pins `TAXO_OFFLINE=1`; override per-command (`TAXO_OFFLINE=0 .venv/bin/python …`). ADC logged in locally.
- **Vertex gotchas (must honor):** global endpoint only for Opus 4.8; `structured_outputs`/`web_search`/`web_fetch` org-blocked → forced tool calls + HttpFetch for page retrieval; judge grounds **strictly on the fetched page** (its cutoff predates 2026).
- **Reproducibility flow:** ground (live, mutates catalog) → `reverify.py --record` (writes `evidence/`) → `taxo verify` replay = byte-identical. The `as_of` date written by reverify must equal `_meta.as_of`; I'll pin a single date (2026-06-21) for this pass.

## Risks & mitigations
- **R1 — live fetch 403 / thin docs.** Admit-only-what-grounds means a blocked/silent page → cell left empty (honest), never fabricated. Local IP (not a datacenter) avoids the CI 403 issue.
- **R2 — cost / volume.** Workstream C is the bulk (~2 calls per sub-feature). Bounded by the curated list; I'll report counts and let you calibrate at plan.
- **R3 — scaffold-skip interaction.** `reverify(record)` skips `review_status=="scaffold"`, so scaffold sub-features get **no** evidence until grounded. Workstream C must flip them out of `scaffold` (via `triage_one`) **before** the record pass, else they stay unverified. Sequencing matters.
- **R4 — `as_of` drift breaks verify.** Pin one date across ground + reverify + `_meta`.
- **R5 — classification over-reach** (e.g. mapping Jules to remote-control). Pin `kind`+axis (operator-known); let the judge set only relation/surfaces — per the engine's existing discipline.

## Out of scope
- Categories beyond the 5 current ones; sibling-surface products (Gemini CLI, Codex CLI/cloud) as standalone nodes; functions other than Agentic Coding.

## Open questions (confirm at plan)
1. The **sub-feature curation list + per-(axis×provider) count** (the table above is the proposed start).
2. **Failure policy on `needs_review`:** keep-and-flag (current behavior) vs hold from the tree until confirmed.
3. Whether to model **CI/GitHub** as a surface now or defer.
