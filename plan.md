# Plan — Feature-level comparison (stop showing axis blurbs on every feature)

**Problem (from Code Review pop-out):** comparison data exists ONLY at the axis level — one
`comparison_note` per capability. So every feature on "Managed agent runtime" shows the same
sandbox/runtime blurb, irrelevant to code review; the cross-provider list dumps the whole axis
(Sessions, Memory Bank…); the true equivalent (OpenAI Codex PR review) may live under a *different*
axis so same-axis matching misses it. Plus: "Includes" shows a mis-attached sub-feature, and the
docs link points at the `.md` source.

**Root cause:** features have no per-feature cross-provider equivalence or comparison; the viewer
borrows the axis note and the full axis feature list, which is wrong at the feature grain.

## Phase 1 — honest fixes now (viewer-only, small)
- **Docs link**: strip a trailing `.md` / `.md.txt` so it opens the real page, not the markdown.
- **Sub-features**: drop the comparison section entirely; show "what it is" + "Part of <parent>".
  (Comparison is a top-level concept; the repeated blurb on every sub-feature is the worst offender.)
- **Top-level feature, until Phase 2 lands**: stop dumping the full axis feature list + axis blurb.
  Show "what it is" + "Includes" + a single link **"Compare <capability> across providers →"** that
  opens the capability pop-out (where the axis note + per-provider lists are actually coherent). No
  misleading per-feature comparison.

## Phase 2 — real feature-level comparison (engine; the portfolio value)
New pipeline step `comparison.py` (or extend provider_scan), run per top-level feature F:
- **Candidates = the OTHER providers' features within the same top-level capability cluster**
  (e.g. all of agentic-coding, across its axes — not just F's axis), name + scope_note.
- One LLM call (Sonnet), labeled `compare:<F.id>`, constrained to ONLY reference provided
  candidates (no hallucination; "no direct equivalent" allowed): returns
  `{ summary: "plain 1–2 sentences: what F does + how each provider's nearest equivalent compares",
     equivalents: [{ provider, feature_id|null, note }] }`.
- Store on the feature as `comparison`. **Ledger the `compare:` calls** (record/replay) so
  `taxo verify` reproduces them — generated insight stays first-class/reproducible, not loose.
- While re-running, add a **sub-feature relevance guard**: a sub-feature is kept only if it's
  actually about its parent (string-presence already required; add a cheap "is this a facet of
  <parent>?" check) — fixes the "Plugin marketplaces under Code Review" noise.
- **Viewer**: feature pop-out shows F.comparison.summary + ONLY the matched equivalents per provider
  (not the whole axis). Capability pop-out keeps the axis-level note.
- **Schema**: add optional `comparison` object to the product `$def` + validation.
- **Cost/time**: ~170 top-level features × 1 Sonnet call ≈ ~$2–4, sequential ~20–30 min; then
  reverify(record) → verify → prune → deploy (the usual loop).

## Risk / honesty
- Recall risk: a feature may have no real equivalent, or the LLM matches loosely. Mitigation: hard
  constraint to provided candidates + explicit "no direct equivalent", concise output, and it's
  reproducible/inspectable via the ledger.
- This is the comparative-insight payoff of the whole piece, so it's worth doing at the feature grain.

## Decision needed
- **(A) Phase 1 only** — fast, honest (no wrong per-feature comparison; comparison lives at the
  capability level). No engine re-run.
- **(B) Phase 1 + Phase 2** — true per-feature "how each provider compares for *this* thing."
  Recommended for the portfolio bar; costs a cheap engine re-run.
