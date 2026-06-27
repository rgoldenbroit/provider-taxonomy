# Plan — Adversarial-absence gate ("disprover") for the matrix

**Goal:** make a gap *earned*. Today the grounding gate proves presence (verbatim quote) but nothing
proves absence, so an empty cell is a free, unverified claim. The keyword gap-floor (already shipped in
`build_matrix.py`) is a brittle stopgap — it caught Anthropic/Google checkpoint-rewind but missed
OpenAI's semantic match ("Version Saving"), because keywords can't read meaning. The disprover replaces
the floor's role with a semantic, adversarial pass.

## Principle
Before any cell is allowed to render as a gap, an LLM is told the cell is *about to be marked absent* and
ordered to **prove that wrong** from the provider's real lineup features. It's the recall counterpart to
the existing `confirm_provider` precision gate — and it composes WITH it: a disprover hit is not trusted
on its own; it must still pass the same strict confirm before it grounds. So the disprover can only
*recover* real features, never weaken the gate.

## Where it slots in (`select_provider`)
Current flow: `map → reconsider(skipped) → [confirm → repick]×N → return confirmed`.
Add one final stage on cells still unconfirmed (the would-be-gaps):

```
disprove(still-empty cells) → candidate index (or 0)
   → feed any hit through the SAME confirm_provider gate
       → pass  → grounded cell  (status from the feature)
       → fail  → needs_review   (a real candidate exists, confirm didn't admit it)
   → disprover returns 0 AND keyword floor also empty → EARNED gap (unverified)
   → disprover returns 0 but keyword floor finds something → needs_review (cross-check; never silent absence)
```

This makes the keyword floor a backstop, not the primary mechanism: the disprover is authoritative for
the gap decision; the floor only adds a `needs_review` when it catches something the disprover dismissed.

## New function (mirrors `reconsider`, adversarial framing)
- `disprove(llm, pkey, pname, feats, gaps)` — batched, one call per provider, ledgered
  `label=f"matrixdisprove:{pkey}"`, schema = the existing `REPICK_SCHEMA` (capability_id, feature_index).
- System prompt (the only genuinely new prose): *"Each capability below is about to be recorded as NOT
  SUPPORTED by {provider}. That is a strong, falsifiable claim. Your job is to refute it: from the
  numbered features, pick the one that genuinely realizes the capability. Prefer finding a match —
  default to a plausible candidate rather than 0. Return feature_index=0 ONLY if, after a careful read,
  no listed feature realizes it."* (Deliberately biased toward finding — the confirm gate downstream
  removes false positives, so a generous disprover + strict confirm = high recall AND high precision.)

## Evidence scope — DECISION NEEDED (recommend A now, B later)
- **A — catalog lineup only (recommended first):** disprover reads the provider's full lineup features
  (the same widened set the mapper sees). Fixes *projection/recall misses* (checkpoint-rewind, Version
  Saving). Fully deterministic + replayable, no new creds beyond the existing Vertex run.
- **B — lineup + live docs (follow-on):** disprover may also fetch official doc roots / Tavily to find
  features not yet in the catalog (true *discovery* misses). Needs the search-ledger work flagged in
  plan-matrix-pipeline.md (Tavily searches aren't ledgered → breaks byte-identical replay). Out of scope
  for this pass.

## Cost / determinism
- +1 batched disprover call per provider per build (~3 total), plus a final confirm batch — all ledgered,
  so CI/replay stays free. Negligible $ on the Sonnet judge tier.
- No change to determinism: same ledger discipline as map/confirm/repick/reconsider.

## Validation (how we know it works, before trusting it)
1. Offline: unit-check `disprove` against a stub LLM fixture (returns a known index) → cell grounds.
2. The checkpoint-rewind row is the gold case: after the Vertex run, Anthropic + Google should ground
   (not just needs_review); OpenAI either grounds on Version Saving or stays an *earned* 0-gap with a
   logged reason.
3. Diff the full re-projected matrix vs today's; every cell that flips gap→grounded must cite a real
   first-party URL. Spot-check 5.

## Downstream (same as the floor work, still required)
- `validate_matrix.py:28` STATUSES needs `needs_review` (+ evidence_url required for it).
- `viewer/template.html` needs a `needs_review` render.
- Regenerate `data/agentic-matrix.json` via a Vertex run (`TAXO_OFFLINE=0`).

## Risks
- **Disprover over-recalls** → mitigated by the downstream confirm gate (unchanged precision).
- **Disprover + confirm disagree forever** (hit→confirm-rejects→needs_review) → that's the correct,
  honest terminal state: a candidate exists but isn't confidently a match; a human decides.
- **Catalog-only scope can't catch discovery misses** → acknowledged; that's scope B.
