# Plan — Catalog credibility + coverage cleanup (phased)

Sequence chosen so credibility lands first, the catalog is clean before it grows, and each phase ends
verify-green + deployed. Every data phase: edit → `reverify(record)` → `taxo verify` byte-identical →
prune ledger → build → test → render-check → deploy → commit.

## Phase 1 — Re-ground to first-party sources (credibility)
- Add a small driver `scripts/reground.py`: for each mis-sourced top-level node, search/confirm a
  first-party page (using `is_official` + the known doc roots), set `source.url`, and re-ground
  (HttpFetch + judge) so confidence is earned from an official page.
- Nodes: Antigravity→`antigravity.google`, Gemini app→`gemini.google`/`support.google.com/gemini`,
  NotebookLM→`notebooklm.google`, Gemini Computer Use→`ai.google.dev/.../computer-use`,
  Gemini 3.5 Pro→`ai.google.dev`/`blog.google` (verify), Claude Cowork→search `anthropic.com`/`claude.com`.
- **Any node with no official page → drop it** (or set `absent`/unverified) — never confirmed-on-a-blog.
- Sweep the whole catalog for other non-official sources (Wikipedia/blog hosts) and re-ground or flag.
- Out: an `is_official` gate in the maintenance loop so this can't regress.

## Phase 2 — Dedup + cleanup pass (clean before growing)
- **Deterministic dedup** (`scripts/dedupe_features.py`): for each (provider, normalized-name) group,
  keep the instance on the best-fit axis (most sub-features / highest grounding score; tie → keyword
  match), drop the rest; re-point any orphaned sub-features.
- **LLM cleanup pass** (`scripts/clean_features.py`, Sonnet, ledgered): per top-level feature, return
  `{keep: bool, name: <=6-word clean name, reason}`. Drops non-node-worthy API minutiae (refusal/
  stop_details/fallback/rate-limiting), normalizes sentence-names. Apply: rename keeps, remove drops
  (+ their sub-features). Cheap (~150 features).
- **Sub-feature descriptions**: where a sub-feature has no scope_note, the cleanup pass also returns a
  one-line plain description so the pop-out stops falling back to the parent's generic text.
- Re-gen `comparison` for features whose name changed (names feed the candidate matching).

## Phase 3 — Overview level-mixing fix (viewer-only, fast)
- `viewer/template.html`: the Overview "coverage at a glance" matrix lists only **product capabilities**
  (those NOT in any `categories.feature_axis_ids`); developer-platform **axes** drop out of the matrix
  and remain reachable only inside product pop-outs / Explore. Removes the 100+-feature pill-clouds and
  the double-appearance.
- Re-tier `remote-agent-control` → `developer_platform` (data one-liner; it's an axis).
- Optionally: a compact "developer-platform axes" strip below the matrix that opens the axis pop-outs,
  so the axes are still discoverable without being giant rows.

## Phase 4 — Fill the hollow capabilities (coverage)
Reuse the per-capability registry + pipeline (`CAPABILITY_CONFIG`, `repopulate_agentic.py --capability`,
`swap_capability.py`, `gen_comparison.py`). Order by tractability:
1. **agent-building-sdk** — cleanest (3 llms-full/clean docs). The original cheap-path proof.
2. **browser-computer-use-agent** — Claude/OpenAI/Gemini computer-use dev docs.
3. **image-video-generation** — OpenAI + Google (Anthropic absent, shown honestly).
4. **knowledge-work-research** — Deep Research + NotebookLM (mixed; partial acceptable).
5. **consumer-chat-assistant** — Anthropic `support.anthropic.com` clean; OpenAI/Google need the
   Tavily-content retriever (separate sub-task) or stay partial-with-a-note.
- **flagship-model**: deferred unless you want a model-attribute comparison (different shape) — flag.
- Define axes + categories per new capability (or reuse cross-cutting axes); generate comparisons.

## Phase 5 — Status spotchecks
- Script: sample `deprecated`/`preview` records, re-judge lifecycle against the cited page; list any not
  supported by the source; correct them (deliberate, not auto). Sora confirmed correct already.

## Cost / time (Sonnet cheap-path, sequential)
- P1 re-ground: minutes, ~$0–1. P2 cleanup: ~150 calls, ~15 min, ~$2. P3: viewer-only, no run.
- P4 per capability: ~$2–5 / ~20–45 min each (the measured rate). P5: minutes.

## Risks
- Dropping blog-sourced nodes removes content — but they're unverifiable; honesty > count.
- Cleanup could over-drop — LLM pass returns a reason + is reviewable; spot-check before committing.
- consumer-chat retrieval is genuinely hard — scoped as partial / Tavily-later, not a blocker.
- Each data phase re-grounds → re-baseline + prune (the established loop); verify stays the gate.

## Decisions (approved)
- **flagship-model: DEFER** — leave as model cards; model-attribute comparison is its own later task.
- **consumer-chat + knowledge-work: ENTERPRISE-EDITION lens** — don't chase the blocked consumer help
  centers; represent these via the enterprise editions (Claude Enterprise, ChatGPT Enterprise, Gemini
  Enterprise / Gemini for Workspace), whose admin/enterprise docs are official + reachable. Verify each
  surface in Phase 4; any provider whose enterprise docs are still blocked → partial + honest note.
- **Execution: RUN ALL FIVE THROUGH** — P1→P5 end-to-end, deploy, then report (no mid-pause).

## Execution order
P1 (credibility) → P2 (clean) → P3 (viewer fix) → P4 (grow: agent-SDK, browser-use, image-video,
then knowledge-work + consumer-chat via enterprise editions) → P5 (spotcheck). Deploy + report at end.
