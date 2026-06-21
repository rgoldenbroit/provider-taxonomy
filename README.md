# AI Provider Taxonomy

[![CI](https://github.com/rgoldenbroit/provider-taxonomy/actions/workflows/ci.yml/badge.svg)](https://github.com/rgoldenbroit/provider-taxonomy/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**A self-maintaining catalog of what Anthropic, OpenAI & Google ship across every AI capability** — each offering discovered from the live web, grounded to its source, cross-checked against an independent second source, and gated before it ships.

🔗 **Live demo:** https://provider-seed-viewer-240942176969.us-east5.run.app

![Overview — the AI provider landscape at a glance](docs/overview.png)

The hard part of a catalog like this isn't *displaying* the data — it's keeping it **true** while the ecosystem changes weekly. This repo is an engine that maintains the catalog itself (discover → ground → triangulate → classify → audit → gate) plus a single-file viewer that renders the result. Architecture first, then how to run it, then the data model that makes it work.

## Why it's interesting

- **It maintains itself.** A discovery pipeline sweeps the live web per capability, an LLM triages each find, and only records that clear quantitative trust gates are admitted — no hand-curation in the loop.
- **Every claim is grounded.** A record is admitted only if an independent judge finds the claim quoted *verbatim* on its cited page, then a **second, independent** source confirms existence and lifecycle status. Disagreement is surfaced, not silently resolved.
- **A deploy gate, not vibes.** The whole catalog is red-teamed before publish; any schema break, eval regression, or critical finding blocks the deploy.
- **Reproducible & auditable — a "lockfile for facts."** Every page fetch and LLM call is recorded in a committed evidence ledger; `taxo verify` replays it (no creds, no network) and asserts the published catalog is byte-identical to what the evidence re-derives — checked in CI. Each record carries a receipt: the verbatim source quote, the source tier, every gate's score, and the model. Confidence is *derived* from source quality, not asserted. See [`OPERATIONS.md`](OPERATIONS.md).
- **Capability-anchored model.** Products churn; capabilities don't. A "comparison" is a *query* over a stable spine, not stored data — so a rename touches one field and the taxonomy holds.
- **Zero-dependency viewer.** One self-contained HTML file (no framework, no build step beyond data injection): an at-a-glance coverage overview, a search/filter/compare explorer, an in-app "How it works", and an "under the hood" panel exposing the live trust metrics. Light/dark, mobile-friendly.

**Explore** — pick a capability to compare providers side by side; click any offering for its cross-provider rivals:

![Explore — compare providers side by side](docs/explore.png)

## Architecture

![How it works](docs/how-it-works.png)

```
 live web ──▶ Discover ──▶ Ground ──▶ Triangulate ──▶ Classify ──▶ Audit + Gate ──▶ publish
              (Tavily      (quote     (2nd indep.     (map to       (red-team;
               sweep)       on page)   source)         capability)   block ship)
                              │             │                            │
                         rejected if   flagged if                 blocked on schema /
                        quote missing  sources disagree           eval / critical finding
```

Each candidate passes **three trust gates** before it's admitted:

- **Schema gate** — conforms to `schema.json` + referential integrity, or it's rejected outright.
- **Grounding gate** — an independent judge's supporting quote must actually appear on the *fetched* source page. The judge is told the current date is past its training cutoff, so it grounds on the page, not on a stale prior — this is what stops it rejecting real-but-unfamiliar 2026 offerings, or hallucinating ones that don't exist.
- **Classification gate** — the capability mapping must be stable across N independent samples.

Above the bar → `confirmed`; partial → `needs_review`; ungrounded → `rejected` (never admitted). A separate **audit critic** then triangulates the finished catalog against independent sources, and a **deploy gate** blocks publish on any schema break, eval regression, or critical finding.

Built on **Vertex AI Claude** (`claude-opus-4-8`). Offline-first: the whole pipeline runs deterministically against fixtures with a stub LLM, behind **77 automated tests** plus gold-set and adversarial evals — no credentials needed to develop or test.

## Running it

### Offline (no GCP credentials) — runs against fixtures with a stub LLM

```sh
python3 -m taxonomy.cli validate    # validate the dataset (schema + referential integrity)
python3 -m taxonomy.cli discover agentic-coding   # sweep providers → candidate records
python3 -m taxonomy.cli triage      # run reviewable records through the trust gates → data/proposed.json
python3 -m taxonomy.cli audit       # red-team the catalog (schema · triangulation · completeness)
python3 -m taxonomy.cli eval        # gold-set + adversarial evals; appends ops/metrics.jsonl
python3 -m taxonomy.cli build       # generate viewer/taxonomy.html  (open in a browser)
python3 tests/run_all.py            # full test suite (no pytest needed)
```

### Going live (Vertex AI Claude)

```sh
pip install -e '.[vertex]'
gcloud auth application-default login
gcloud auth application-default set-quota-project <your-project-id>
cp .env.example .env.local          # set ANTHROPIC_VERTEX_PROJECT_ID, CLOUD_ML_REGION, VERTEX_MODEL
TAXO_OFFLINE=0 python3 -m taxonomy.cli ping                       # expect → 'pong'
TAXO_OFFLINE=0 python3 -m taxonomy.cli autobuild --capabilities agentic-coding   # discover → ground → loop
TAXO_OFFLINE=0 python3 -m taxonomy.cli gate --dataset data/auto.json             # deploy gate (exit 1 = blocked)
```

Auth is keyless (ADC locally, Workload Identity Federation in CI) — there are no API keys or service-account files for cloud auth. On Vertex the engine fetches source URLs itself (no server-side `web_fetch`), so the grounding gate is fully auditable. Optional: a [Tavily](https://tavily.com) key (`TAVILY_API_KEY` in `.env.local`) enables autonomous live-web discovery; without it, discovery is operator-seeded and grounding-fetch still runs in-engine.

## Layout

- `taxonomy/` — engine: `validate` · `discover` · `triage` · `trust` (the three gates) · `audit` (triangulation critic + deploy gate) · `autobuild` (loop-until-dry discovery) · `metrics`/`staleness` · `evals/` · `vertex_client` (Vertex + offline stub) · `retrieval/` (fixtures + httpx fetch + Tavily).
- `data/` — `taxonomy.json` (working store) · `fixtures/` (deterministic offline searches/pages/LLM responses).
- `viewer/` — `template.html` + `build.py` → `taxonomy.html`, a single-file light/dark viewer with four sections: **Overview** (coverage-at-a-glance), **Explore** (search · filter · compare, with cross-provider equivalence and a collapsible `category → feature → sub-feature` breakdown per provider), **How it works** (the pipeline + trust gates), and **Under the hood** (live trust metrics · re-verify queue · intake · lineage). The drawer renders any node's full breakdown tree.
- `scripts/` — `ground.py` (rebuild the verified catalog) · `fill_gaps.py` (incremental gap-fill).
- `ops/` — run logs, eval-metrics time series, fetched-page cache (regenerable).

---

# The data model

The engine above is only as good as the schema it maintains. Two core entity types — `capability` and `product` — plus an optional `category` (per-function IA grouping), defined in `schema.json`, with a hand-curated, fully-conformant seed in `examples.json`.

## The one idea that makes this work

**The capability is the anchor, not the product.**

Products are renamed, merged, and killed constantly. Functions ("agentic coding", "browser agent") are stable. So:

- `capabilities[]` = the stable taxonomy rows. They rarely change.
- `products[]` = concrete offerings, each pointing at one or more capabilities.

A "comparison" is then a **query**, not stored data: pick a capability, group its products by provider. This is what lets the app survive churn — when Google kills a product, you change one `status` field; the taxonomy rows never move.

## Why the comparison is never 1:1 (and how the schema absorbs it)

| Real-world mess | How the schema handles it |
|---|---|
| One provider's product maps to several of another's | Many `products` share one `capability_id`; the join is computed, not hard-coded. |
| A product is broader or narrower than the capability | `relation_within_capability`: `direct` / `partial` / `broader` / `none`. |
| A product spans multiple capabilities | `capability_ids` is an array; `primary_capability_id` picks the home row. |
| Products get renamed / merged / retired | `status` enum + `predecessor_id` / `successor_id` + dated `lifecycle[]`. |
| A provider deliberately offers nothing | An explicit `status: "absent"` record, so the UI shows a *sourced gap*, not a null. |
| The ecosystem changes faster than you can verify | `source.last_verified` + `source.confidence` drive staleness warnings. |
| A capability lives *inside* a product, not as its own product | `kind: "feature"` + `parent_id` pointing at the parent product. |
| A feature has its own internal structure | A deeper `parent_id` chain: a `feature` (sub-feature) parented to another `feature`. Nesting is unbounded. |
| A function's features want grouping for navigation | Optional `categories[]` — per-function, provider-agnostic groupings of feature-axes (the abstract spine). |
| Structure exists but isn't ground-verified yet | `review_status: "scaffold"` — hand-added shape; the reproducible-build replay skips it until the maintenance loop grounds it. |
| Something new is discovered but not yet classified | `review_status: "candidate"` (optionally `primary_capability_id: "unclassified"`) until triage confirms it. |

## Granularity: model family → product → category → feature → sub-feature

The taxonomy holds offerings at any depth using `kind` + `parent_id` for the **concrete** tree, and an optional `categories[]` array for the **abstract spine** (`function → category → feature-axis`).

- `kind` says what the node *is*: `model_family`, `model`, `product`, `feature`, `platform`, `protocol`, or `service_tier`.
- `parent_id` points at the node it belongs to: a `feature` → its `product`, a deeper `feature` (sub-feature) → its parent feature, a `model` → its `model_family`, a sub-product → its parent product. The chain can go as deep as the offering's real structure.
- `categories[]` (optional) groups and orders a function's feature-axes for drill-down — e.g. for **Agentic Coding**: *Agent Management*, *Context & Memory*, *Execution & Safety*, *Quality & Ops*. Each category lists the `feature_axis_ids` (capability ids) it presents. Categories are pure IA — they never move the cross-cutting feature-axes, they just curate one function's view.

This lets **Claude Code subagents** (a feature of Claude Code) drill into **Definition files / Tool scoping / Model per subagent** (sub-features), grouped under the *Agent Management* category — and the viewer renders the whole `category → feature → sub-feature` tree as a collapsible breakdown, compared side by side across providers. Sub-features added as structural scaffold carry `review_status: "scaffold"` until grounded.

**When does a feature earn its own node?** Only when it represents a capability worth comparing across providers. Every product has dozens of small features; tracking them all is unbounded and useless. Remote Control earns a node because async/remote agent control is a real cross-provider axis (Google's Jules, OpenAI's Codex Cloud); a cosmetic toggle does not. **Rule of thumb: if it doesn't map to a capability another provider could also fill, it's a `scope_note`, not a node.** The engine enforces this automatically — an "X SDK / CLI" that merely exposes an already-listed product is folded into that product as an access surface rather than admitted as a new node.

## Discovery / intake lifecycle

The point of the design is that the catalog can *grow itself* as the ecosystem changes:

1. Discovery (live-web sweep, changelog scrape) finds a new product or feature.
2. It's written as a node with `review_status: "candidate"`, a `source.url`, and a best-guess `primary_capability_id` (or the reserved `unclassified` bucket if the capability isn't obvious).
3. Triage confirms the capability, sets `relation_within_capability`, runs the trust gates, and flips `review_status` to `confirmed` — or `rejected` (kept, not deleted, so it isn't rediscovered repeatedly).

## Origin

`schema.json` + `examples.json` were designed as **few-shot examples** to hand to a coding agent: a small, high-quality dataset whose every record demonstrates a specific edge case (rename lineage, scope mismatch, modeled absence, feature-inside-product, model-family hierarchy, discovery intake) so the agent infers the right data model and edge-case handling before writing code. The engine and viewer in this repo are what that seed grew into.
