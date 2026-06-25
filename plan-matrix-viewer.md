# Scope — Wire the agentic-coding capability matrix into the viewer

**Status: SCOPE ONLY — awaiting approval. Nothing here is implemented.**
(Kept separate from `plan.md`/`research.md`, which document the shipped P1–P5 catalog work.)

## Goal
Surface the vendor-neutral agentic-coding matrix (from `ai-provider-capability-taxonomy.md`)
as a view in the deployed viewer, so the 16-capability × 3-provider comparison is live on the
site — without disturbing the existing grounded catalog or its reproducibility gate.

## What exists today (verified)
- `viewer/build.py` loads `data/taxonomy.json`, validates it, and inlines the result into
  `viewer/template.html` at the `/*__APP_DATA__*/` marker → single-file `viewer/taxonomy.html`.
- `template.html` renders from one inlined object `APP`; views are a registry:
  `const VIEWS = [['Overview',viewOverview],['Explore',viewExplore],['How it works',viewAbout]]`,
  each a function returning an HTML string; `selectView(label)` swaps the body; nav is generated
  from `VIEWS`.
- Deploy (OPERATIONS.md): `taxo build` → `gcloud run deploy provider-seed-viewer --source viewer
  --region us-east5`. The Cloud Run image serves the pre-built static `taxonomy.html`; the build
  runs **before** deploy (locally or in `maintain.yml`), so the runtime image needs no new deps.
- The matrix is a **different shape** from the catalog (neutral `capability_groups → capabilities
  → providers{anthropic,google,openai}` with a 5-value status), and has no confidence/grounding
  fields. It should be its own view, not forced into the catalog's `capabilities`/`products` model.

## Recommended approach — additive "Capability Matrix" view (low coupling)

### Decision 1 — Source of truth & build dependency
Keep the YAML in `ai-provider-capability-taxonomy.md` (your earlier choice). Add a tiny committed
generator `scripts/matrix_to_json.py` that reuses `validate_matrix.py`'s extractor, validates, and
writes `data/agentic-matrix.json`. `build.py` reads that JSON (stdlib only).
- **Why JSON-at-commit, not extract-at-build:** keeps `build.py` / `maintain.yml` / the reproducible
  build pure-stdlib (no PyYAML in the build/deploy path). The MD stays canonical; regenerate the
  JSON whenever the matrix changes (and gate it in CI with `validate_matrix.py`).

### Decision 2 — Rendering
- New nav tab **"Capability Matrix"**; register `['Capability Matrix', viewMatrix]` in `VIEWS`.
- `viewMatrix()` renders the 8 groups, each with its `layer` tag, as sections; within each, a
  capability × {Anthropic, Google, OpenAI} grid. Each cell shows: status pill, `implementation`,
  an evidence link (↗ to `evidence_url`), and `notes` on hover/expand.
- Reuse existing status-pill colors; add `unverified` styling. Show the 1 honest `unverified`
  cell (Antigravity context-compaction) explicitly rather than hiding it.
- A short header explainer distinguishing this **curated neutral comparison (grounded to official
  docs)** from the auto-discovered catalog, so the two methodologies don't read as contradictory.

### Decision 3 — Polish (portfolio bar)
- Responsive: the 3-column grid collapses to stacked per-capability cards on narrow screens
  (mobile was a prior must-fix).
- `.md` evidence URLs → link to the human doc page (decide: keep `.md` or strip).

## Phases (each ends build-green + render-checked)
1. **Data pipeline** — `scripts/matrix_to_json.py` (+ reuse the validator's extractor); emit
   `data/agentic-matrix.json`; wire `app["matrix"]` into `build.py`. Add the matrix validate step
   to `ci.yml`. *No UI yet.*
2. **View (desktop)** — `viewMatrix()` + `VIEWS` registration + status/evidence/notes styling.
3. **Polish** — responsive/mobile layout + the framing/attribution explainer.
4. **Ship** — `taxo build`, render-check `taxonomy.html` locally, `gcloud run deploy`, commit.

## Risks / watch-items
- **Two data models in one app** — mitigated by a separate view + clear framing.
- **Reproducibility gate** — `taxo verify` covers the catalog only; the matrix is separate. Keep it
  that way; gate the matrix with `validate_matrix.py` in CI so it can't rot.
- **Dependency creep** — avoided by the JSON-at-commit approach (build/deploy stay stdlib).
- **Doc-link rot** — evidence URLs were verified 2026-06-24/25; staleness is out of scope here.

## Rough effort
Viewer-only + one small build step. ~Half a day. No model/API calls, no new infra.

## Open questions for you
1. **Nav placement** — top-level "Capability Matrix" tab, or nested under Overview?
2. **Evidence links** — link the `.md` doc pages as-is, or strip `.md` to the rendered doc page?
3. **Scope of the matrix view** — agentic-coding only (what we have), or build it to accept more
   `product_category` matrices later (slightly more upfront structure)?
