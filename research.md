# Research — reliable coverage without manual intervention

*(Supersedes the feature-depth research; the feature work continues, but on top of this reliability fix.)*

## The problem (you surfaced it; it's the central one)

Two failures, one root cause:
1. **A grounding miss is rendered identically to a real absence.** Antigravity shows empty for managed agents → reads as "Google doesn't do managed agents." But it clearly does (`ai.google.dev/gemini-api/docs/custom-agents`). The system **infers absence from silence**.
2. **It needed a human to notice the MCP gap and ask for a "second pass."** A self-maintaining catalog that must be *prompted* to be complete isn't self-maintaining.

Root cause: the engine has only two states — *found* / *not-found* — and treats not-found as absent. Discovery is single-shot (one query → one source), so misses are common, and nothing automatically retries the gaps.

## Three concrete root causes

1. **No "unknown" state.** present vs absent only; "not yet verified" collapses into absent → misrepresentation.
2. **Single-shot, product-narrow discovery.** One query, one source. My Google miss is the tell: I searched *"Antigravity managed agents"* — but managed agents is a **Gemini API** feature, not an Antigravity-the-IDE feature, and I never searched Google's official docs. Wrong parent + wrong source = false absence.
3. **No built-in completeness loop.** The "second pass" was manual; gaps don't auto-trigger deeper verification.

## The design — three principles

### 1. Never infer absence from silence (three-state model)
- **present** — a grounded feature record.
- **absent** — a grounded *absence* record: positively verified the provider doesn't offer it.
- **unknown** — not yet verified. A **distinct** visual state ("not yet verified — not a confirmed absence"), never shown as a clean blank/"none". Stays in the work queue.

Absence must be **earned with evidence**, exactly like presence. An empty cell defaults to *unknown*, never *absent*.

### 2. Robust-by-construction discovery (axis-first · official-source-first · multi-query)
- **Axis-first, not product-first.** For each (provider × axis), find the offering *wherever it lives* and attach it to the correct parent (Google managed agents → Gemini API, not Antigravity). The cross-provider comparison is still by axis.
- **Official docs first.** Scoped queries against the provider's own domains (`docs.anthropic.com`, `platform/developers.openai.com`, `ai.google.dev`/`cloud.google.com`) plus general web, in several phrasings. Ground against the authoritative source — this is what finds `custom-agents`.

### 3. The completeness loop is built in (no human "second pass")
- After the first sweep, a completeness critic **auto-targets** every **unknown** cell and every **asymmetric** cell (peers present, this provider not) with deeper, official-docs-scoped queries — **looped until a full round finds nothing new** (loop-until-dry).
- A cell only settles to **absent** after the loop exhausts *and* there's positive evidence of non-offering; otherwise it stays **unknown** (low confidence, re-verify scheduled). The retry is intrinsic, not prompted.

## The gate enforces honesty automatically (the "checking" becomes machine-run)
- Audit **blocks** any cell shown as a clean absence without a grounded absence record → kills the misrepresentation at the gate.
- Audit flags **asymmetric coverage** (peers have it, this provider is unknown) → an automatic verification target fed back into the loop, not a human task.
- Ships with unknowns **honestly marked**; never ships a false absence.

## Builds on what already exists (evolution, not rebuild)
`rank.completeness_critic`, `autobuild`'s gap-chasing loop, `audit.py`'s triangulation + official-source authority, the absent-record convention, and the staleness re-verify schedule. This wires them into one reliable loop with an explicit *unknown* state.

## What changes vs the prior plan
- **Add the `unknown` state** (data + UI) — the misrepresentation fix, and the highest-priority change.
- **Replace single-shot `ground_features`** with axis-first, official-source-first, multi-query discovery + the completeness loop.
- **Gate** flags false-absences and asymmetric gaps.
- **Keep the 14 grounded-present features** (verified true); the loop fills the rest or marks them honestly *unknown*.

→ This revises `plan.md`. On approval I'll rewrite the plan around these three principles and stop again before building.
