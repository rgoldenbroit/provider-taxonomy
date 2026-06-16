# Plan — AI Provider Taxonomy system

Decisions confirmed: **Vertex AI Claude**, **prove the loop on one capability (`agentic-coding`) first**, **engine before viewer**. Storage = JSON canonical (git-diffable) + SQLite operational store. Auto-confirm only above a high trust bar.

## Vertex AI Claude — grounded facts (from the Vertex docs, not memory)

- **Install:** `pip install -U google-cloud-aiplatform "anthropic[vertex]"`.
- **Client:** `from anthropic import AnthropicVertex` → `AnthropicVertex(project_id=..., region="global")`. Auth via GCP ADC (`gcloud auth application-default login`); `project_id`/`region` from env (`ANTHROPIC_VERTEX_PROJECT_ID`, `CLOUD_ML_REGION`) or args. `region="global"` (no pricing premium, best availability).
- **Model:** `claude-opus-4-8` (bare ID on Vertex — newer models have no `@date` suffix; Sonnet 4.5 etc. still do). 1M context. Adaptive thinking only (`thinking={"type":"adaptive"}` + `output_config={"effort":"high"}`); no `budget_tokens`/sampling params; no last-assistant prefill.
- **Supported on Vertex:** Messages API, **structured outputs** (`output_config.format` / `messages.parse()`), prompt caching, extended/adaptive thinking, tool use, **`web_search` server tool**, citations.
- **NOT supported on Vertex (drives design):** **`web_fetch`** server tool, **Files API**, **Message Batches**, **Managed Agents**, server-side `fallbacks`. → The engine fetches source URLs itself (httpx), makes synchronous (streaming) Messages calls (no batch discount), and uses **client-side** refusal fallback.

## Architecture / layout

```
schema.json, examples.json        # canonical seed + gold set (UNCHANGED, never mutated)
data/
  taxonomy.json                   # canonical working store (seeded from examples.json), append-only
  fixtures/                       # saved searches + fetched pages → deterministic dev/eval
ops/taxonomy.db                   # SQLite: discovery run logs, eval-metrics time series, source-fetch cache
taxonomy/                         # the engine (Python package)
  schema.py        # load schema.json
  validate.py      # schema-subset walk + referential integrity (no jsonschema dep)
  index.py         # capability/product/children/lineage maps
  vertex_client.py # AnthropicVertex wrapper: model, adaptive thinking, structured output, retry, client-side refusal fallback, OFFLINE STUB
  retrieval/
    base.py        # RetrievalProvider interface (search + fetch)
    fixtures.py    # replay saved searches/pages (deterministic, no creds)
    vertex_search.py # discovery via Claude-on-Vertex web_search
    http_fetch.py  # httpx GET → cleaned text (stdlib html.parser), logged+cached to ops
  discover.py      # per provider×capability sweep → candidate records
  triage.py        # LLM classify/dedup/lineage/confidence → review_status
  trust.py         # 3 gates (schema·grounding·classification) + dataset metrics
  evals/
    gold.py        # hold-out reconstruction vs seed
    adversarial.py # fake-product injection (grounding-gate must reject)
  cli.py           # taxo validate|ping|discover|triage|eval
viewer/
  taxonomy.template.html, build.py → taxonomy.html   # static single-file viewer (reads data/taxonomy.json)
pyproject.toml (deps: anthropic[vertex], google-cloud-aiplatform, httpx, pytest)
```

**Dependency discipline:** custom validator (no `jsonschema`); stdlib `html.parser` for page→text (no bs4). Engine needs network+Vertex for *live* runs; **all of it runs offline** via the stub LLM + fixtures (so dev/CI/evals are deterministic without creds).

## Phases (engine first, agentic-coding first; stop after each for a check)

### Phase 0 — Data layer + validator (no LLM)
- `pyproject.toml`; seed `data/taxonomy.json` from `examples.json`.
- `validate.py`: schema-subset (`required`/`enum`/`additionalProperties:false`/`$ref`→`$defs`/`array`/`format:date`) **+** referential integrity (id resolution for `capability_ids`/`primary_capability_id`/`parent_id`/`predecessor_id`/`successor_id`; `primary ∈ capability_ids`; `status:"absent"`⇒`relation:"none"`; unique ids; valid lifecycle dates). Fail loudly with `<id>·<path>·<rule>`.
- `index.py`; `taxo validate`.
- **Done:** `taxo validate` green on seed; pytest covers each integrity rule (corrupt fixtures → specific errors).

### Phase 1 — Vertex client + retrieval interface + offline stub
- `vertex_client.py`: `AnthropicVertex(project_id, region="global")`, `claude-opus-4-8`, adaptive thinking + `effort:high`, structured-output call (`messages.parse`/`output_config.format`), streaming, retry, **client-side refusal fallback** (Vertex has no server-side `fallbacks`). An **offline stub** (env `TAXO_OFFLINE=1`) records prompts and returns canned structured outputs from fixtures — the whole pipeline runs without creds.
- `retrieval/`: `base.py` interface; `fixtures.py`; `http_fetch.py` (httpx → text, cached to `ops/`).
- `taxo ping`: 1-token Vertex call if creds present, else stub.
- **Done:** `taxo ping` works both modes; fixtures load; structured-output round-trips through the stub.

### Phase 2 — Discovery (agentic-coding only)
- `discover.py`: for provider ∈ {Anthropic, OpenAI, Google} × `agentic-coding`: retrieve current offerings (live: Vertex `web_search`; dev: fixtures) → extract candidate products/features + **source URLs** (structured output) → **dedup** vs existing `product.id` incl. **rename detection** → emit `review_status:"candidate"` nodes (confidence `low`) to a candidates list.
- **Done:** on agentic-coding fixtures, discovery emits sourced candidates and correctly skips already-present Claude Code / Codex / Antigravity etc.

### Phase 3 — Triage (LLM) + trust gates
- `triage.py`: per candidate → capability(ies)+`primary`, `relation_within_capability`, `kind`+`parent_id`, `surfaces`, lineage links, confidence — emitted as **schema-conforming** structured output.
- `trust.py`: **Gate 1 schema** (`validate`, must pass) · **Gate 2 grounding** (httpx-fetch the `source.url` → *independent* Opus judge confirms it substantiates the claim → grounding score; no verified source ⇒ never auto-confirm) · **Gate 3 classification** (N-sample self-consistency). Set `review_status` by thresholds: `confirmed` only above the high bar, else `needs_review`; `rejected` (kept, not deleted) on grounding failure.
- Write results into `data/taxonomy.json` as **append-only** lifecycle events + field transitions (never silent overwrite); log to `ops/`.
- **Done:** seeded candidate `openai-codex-cloud-remote` triages to a valid record with grounding+classification scores; an injected fake product is rejected by Gate 2.

### Phase 4 — Evals + metrics (the trust proof)
- `evals/gold.py`: hold out N agentic-coding seed records → run discover+triage on fixtures → score reconstruction (capability/relation/hierarchy/lineage) → precision/recall per capability.
- `evals/adversarial.py`: inject plausible-but-fake product w/ bogus URL → assert grounding gate rejects → false-admit rate.
- `trust.py`: aggregate dataset metrics (grounding rate, provenance completeness, schema conformance=100%, classification accuracy, dedup precision/recall, staleness coverage) → write a report to `ops/` (time series); thresholds **gate auto-confirm** (regression → block promotion).
- `taxo eval` prints the metrics table.
- **Done:** gold-set eval reports numbers; adversarial false-admit = 0 on fixtures; metrics report persisted.

### Phase 5 — Static viewer (single file)
- `viewer/build.py` inlines `data/taxonomy.json` + `schema.json` into the template → `taxonomy.html` (zero-dep, opens offline; in-browser validation banner).
- Views: **capability pivot** (providers as columns, hierarchy nesting, relation tags, absence-as-sourced-gap, multi-capability cross-listing) · **provider drill-down** · **feature-equivalence** (pick a capability/feature → the cross-provider row) · **lineage/history** (predecessor/successor chains, lifecycle timelines, in-flux detection) · **staleness** (90/45/21, `as_of`-based today) · **intake/triage queue** showing each record's `review_status`, confidence, sources, and gate results.
- **Done:** renders the agentic-coding slice + every applicable edge case; trust metadata visible.

### Phase 6 — Fan out + acceptance
- Extend discover/triage to all capabilities; full run; re-run evals.
- Walk the 16-case checklist (research.md §3) as acceptance; append "Running the system" to `README.md` (incl. `gcloud auth application-default login` + `ANTHROPIC_VERTEX_PROJECT_ID`).
- **Done:** all capabilities covered, evals green, viewer complete.

## Verification strategy
- **pytest** for pure logic (validator, index, dedup, lineage, gate scoring) — deterministic.
- **Offline stub + fixtures** make every LLM/network step deterministic → the gold-set eval runs as an integration test with no creds.
- **Adversarial test** enforces the core guarantee: the engine never admits ungrounded content.
- Live Vertex is exercised by `taxo ping` and (when creds present) a real one-capability run; I report eval numbers per phase, you do the visual viewer pass.

## Decisions I made (correct me)
1. **Retrieval split:** discovery may use Vertex `web_search` (supported, **no creds beyond Vertex**); the **grounding gate fetches source URLs in-engine via httpx** (web_fetch unsupported on Vertex, and engine-fetched raw text is what we want for an auditable trust gate). Pluggable provider; `fixtures` is the dev/eval default.
2. **Offline-first build:** I build and *eval* the whole pipeline against fixtures with a stub LLM, so I need **no GCP creds to make progress**. You supply `project_id` (+ `gcloud` ADC) when you want a live run — not a blocker for any phase except the live `ping`/run.
3. **Model = `claude-opus-4-8`** for triage and the grounding/classification judges (quality drives trust); Sonnet/Haiku on Vertex are a later cost lever, not v1.
4. **No Batches** (unsupported on Vertex) → synchronous streaming calls; fine at v1 scale.

## Open question (only one, and non-blocking)
- **Live search provider:** default the *live* discovery sweep to the Vertex `web_search` server tool (zero extra creds)? The alternative is an external search API (Brave/Bing/SerpAPI) if you'd rather the engine own search end-to-end. Either way the **grounding gate is engine-side httpx**, so trust isn't affected. I'll proceed with Vertex `web_search` unless you say otherwise — and since the build is offline-first, this doesn't block starting.

## Out of scope for v1
Multi-user/auth/hosting; UI-triggered discovery (needs a server); real-time streaming discovery (v1 = on-demand/scheduled batch runs); viewer write-back (engine owns writes as reviewable diffs); cost-tier model routing.
