# Plan — reliable, self-checking coverage

*(Supersedes the feature-grounding plan. Built on the three principles in `research.md`: never infer absence from silence · robust-by-construction discovery · the completeness loop is built in.)*

**Keep:** the 7 feature-axes (Phase A, done) and the 14 grounded-present features (verified true). **Fix:** how the *absence* of a record is represented and how gaps get resolved — automatically.

---

## Phase 1 — The `unknown` state (stops the misrepresentation; ships safely alone)

**Principle:** an empty cell means *not yet verified*, never *not offered*. Absence must be a grounded record.

- **Data convention (no schema change):** three states derived from records —
  - **present** = a feature record (status ≠ absent),
  - **absent** = a grounded absence record (`status:"absent"`, with a source),
  - **unknown** = neither.
- **Viewer:** the coverage matrix, Explore, and drawer render `unknown` as a distinct, neutral **"? not verified"** marker (tooltip: "no confirmed offering or absence yet — not a claim that it's missing"), clearly different from grounded **"none"**. Add it to the legend. (The original 9 capabilities have no empty cells, so `?` only appears on the new feature axes — exactly where verification is still in progress.)
- **Result:** Antigravity/managed-agents immediately reads "not yet verified," not "Google doesn't do this." Honest the moment it ships, even before better discovery.

*Checkpoint: rebuild + screenshot; this is independently shippable.*

## Phase 2 — Reliable discovery (axis-first · official-source-first · multi-query)

**Principle:** make misses rare by construction, and attach features to the correct parent.

- **`include_domains` on Tavily search** (the API supports it) → scope queries to a provider's official docs. Official domains reused from `audit.py` (`docs.anthropic.com`, `developers/platform.openai.com`, `ai.google.dev`/`cloud.google.com`, …).
- **`discover_axis(provider, axis)`** (new): for each (provider × axis), run several queries — **official-docs-scoped first**, then general phrasings — gather candidates, and ground presence against the most authoritative source. The classifier attaches the **correct parent** (Google managed agents → Gemini API, not Antigravity), adding the parent product if it isn't catalogued yet.
- Replaces single-shot `ground_features`. Re-run for the 7 axes; the Google-managed-agents / OpenAI-&-Google-MCP misses resolve because we now read the official docs.

*Checkpoint: the grounded coverage matrix — show what's now present vs still unknown.*

## Phase 3 — The completeness loop (no human "second pass")

**Principle:** gaps re-verify themselves until exhausted.

- After the sweep, a **completeness critic auto-targets** every **unknown** cell and every **asymmetric** cell (≥1 peer present, this provider unknown) with deeper, official-docs-scoped queries — **looped until a full round adds nothing new** (loop-until-dry, `max_rounds` cap).
- **Resolution after exhaustion:** positive evidence of non-offering → write a **grounded absence** record; otherwise leave **unknown** (low confidence, re-verify scheduled by the existing staleness mechanism). Absence is never the default.
- Reuses `rank.completeness_critic` + `autobuild`'s loop; the retry is intrinsic to the pipeline, never prompted.

*Checkpoint: coverage after the loop — present / grounded-absent / still-unknown counts.*

## Phase 4 — Honesty gate (the checking becomes machine-run)

- **`_absence_integrity`** (new audit check): flag any cell the viewer would show as a clean absence that lacks a grounded absence record → blocks the misrepresentation at the gate.
- **`_asymmetry`** (new): peers present, this provider unknown → an automatic verification target (warning), fed back into the loop rather than onto a human.
- Wire both into `audit_catalog` + `gate`. Unknowns ship (honestly marked); **false absences cannot**.

## Phase 5 — Feature UX + ship

- Product drawer gains a **"Features"** section (child features by axis); opening a feature shows its **cross-provider comparison** on its axis, with present / unknown / absent shown honestly per provider.
- Product cards hint "N features ›".
- Run the full reliable pipeline for the 7 axes → audit → gate → rebuild → re-screenshot → redeploy → commit → push to `main`.

---

## Why this answers "without manual intervention and checking"
- **No misrepresentation:** unknown ≠ absent, enforced in data, UI, and gate.
- **Coverage is automatic:** official-source-first multi-query + a loop that re-targets its own gaps until dry — the "second pass" is the pipeline, not you.
- **Accuracy is self-checked:** the gate blocks false absences and surfaces asymmetric gaps mechanically; you review a gated result, you don't hunt for misses.

## Guards / scope
- No schema change (unknown is "no record"; absence uses the existing `absent` status).
- Engine changes are additive; existing records and the 9 product-capabilities are untouched.
- First cluster stays agentic-coding for the feature axes; platform/API fan-out is a later pass.
- Cost: Phases 2–3 are the heavier live runs (multi-query + loop); I'll run them in the background and checkpoint each.

→ **Approve and I start Phase 1** (the unknown-state fix — small, high-value, independently shippable). I'll checkpoint after each phase.
