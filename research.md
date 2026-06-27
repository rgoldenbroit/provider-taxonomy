# Research — Scope-B: autonomous discovery for matrix gaps (and the "search-ledger" question)

**Question.** The matrix can't fill a cell when the *catalog* lacks the feature (a discovery miss, e.g.
OpenAI Codex hooks). Scope-A's disprover only reads the catalog. Scope-B = autonomously find the
first-party page and ground it. The open worry was: search isn't ledgered → does that break `taxo verify`
(byte-identical replay)?

## Key finding: the search-ledger is NOT a blocker

`taxo verify` replays **grounding** (page + llm + provenance), **not search**. A record's reproducibility
depends only on its committed `source.url` re-grounding from the ledger — *not* on how that URL was
discovered. Proof points, all verified in-repo:

- Ledger has exactly three spaces: `page`, `llm`, `provenance`. There is **no** `search`/`tavily` space,
  and `tavily.search()` is a live, un-ledgered call.
- `taxonomy/autobuild.py` **already** does autonomous Tavily discovery → ground → admit (loop-until-dry
  with a `completeness_critic`). The committed catalog contains its output, and **HEAD passes `verify`.**
- `discover.py` is explicit: *"Discovery never admits anything — triage + the gates do."* Search finds
  candidate URLs; triage/grounding (ledgered) is the reproducible part.

So the plan-matrix-pipeline.md note ("Tavily searches aren't ledgered → breaks replay") was only true of
the **removed Stage C**, which ran search *inside the matrix build*. The fix isn't to ledger search — it's
to not search in the matrix build at all.

## Architecture principle: feed the CATALOG, not the matrix

Scope-B should add records to the catalog via the existing discover→ground→reverify path; the matrix then
projects them on the next rebuild (sticky => only genuinely-new cells move). This keeps the matrix a pure
projection (the lesson behind removing Stage B/C), and keeps `verify` green because grounding is ledgered.

## What's already built (reuse, don't reinvent)

- `tavily.search(query, include_domains=…)` — official-domain-scoped web search. **TAVILY_API_KEY is set.**
- `discover()` / `autobuild()` — Tavily discovery + `_try_admit` + `completeness_critic` loop-until-dry.
- `scripts/ground_gap.py` — admits a found URL under the lineup root **and** runs `reverify_record` at the
  catalog's `as_of` so the new record is `verify`-reproducible by construction. (This is the verify-safe
  admit the existing autobuild path does *not* do inline — it stages to `auto.json` for manual promote.)
- The sticky projection — new catalog records surface without churning settled cells.
- The matrix overlay (`review-decisions.yaml`) — human confirm/reject of what discovery proposes.

The only genuinely new code is a **driver**: turn each matrix gap into a scoped search, feed the top
first-party hit into `ground_gap`'s verify-safe admit, re-project.

## Options

### A. Driver — what selects what to discover
- **A1 (recommended): matrix-gap-driven.** Iterate the 20 `unverified` cells; for each, Tavily-search the
  provider's official domain(s) using the row's `hints`; ground the top first-party hit. Targeted, cheap
  (~20 searches/run), precise. Directly closes the misses a human would notice.
- **A2: completeness-critic-driven (the autobuild way).** Ask an LLM "what's Provider X missing for
  capability Y" per row. Broader recall (finds things not yet imagined as gaps) but noisier and costlier.
- **A3: both** — A1 each run; A2 occasionally as a wider sweep. Best coverage, most cost.

### B. Search reproducibility / auditability
- **B1 (recommended): don't ledger search.** Matches autobuild; `verify` already green. Zero new infra.
  Trade-off: you can replay "does this URL still ground" but not "how we found it."
- **B2: snapshot the discovering query into the provenance receipt.** Cheap audit trail (which query +
  snippet surfaced the page) without making search replayable. Nice-to-have on top of B1.
- **B3: full `search` ledger space.** Records query→results so discovery is replayable too. Real infra
  (new space, replay wiring); only buys "re-derive the same URL set from scratch," which committed source
  URLs already pin. Not worth it now.

### C. Human-in-the-loop placement
- **C1 (recommended): auto-admit → matrix `needs_review` → overlay.** Discovery grounds + admits to the
  catalog; the matrix surfaces the new cell as `needs_review` (the disprover/confirm path already does
  this); a human confirms/rejects in `review-decisions.yaml`. Preserves the whole conversation's thesis:
  the machine *proposes*, the human *disposes*. Note: catalog admit still passes the grounding gate, so
  nothing ungrounded enters.
- **C2: stage to `auto.json` + audit gate + manual promote (the existing autobuild flow).** Heavier human
  step at the catalog layer; more friction, more safety.

### D. Cadence
- **D1 (recommended start): on-demand** — a command you run when you spot/expect gaps.
- **D2: weekly self-heal in `maintain.yml`** — compute gaps → discover → reverify → re-project → commit.
  The "misses self-heal" end state. Move here once A1+C1 are trusted.

## Risks & mitigations
- **Wrong page grounded (precision).** The grounding gate still requires a verbatim quote; `include_domains`
  restricts to official docs; new cells land as `needs_review`, not `active` — human adjudicates (C1).
- **Reproducibility regressions.** Every admit MUST go through `ground_gap`'s reverify-at-`as_of` (proven
  this round). A non-ledgered admit silently breaks `verify`.
- **Cost.** ~20 searches + groundings per run on the judge tier; bounded and cheap. Replay makes re-runs free.
- **Recall ceiling.** A1 only chases known gaps; truly-unknown misses need A2/completeness-critic — defer.

## Recommendation
**A1 + B1 (+B2 audit snippet) + C1 + D1.** A matrix-gap-driven discovery driver that reuses
Tavily(include_domains) + `ground_gap`'s verify-safe admit, lands new cells as `needs_review` for overlay
adjudication, run on-demand first; graduate to `maintain.yml` (D2) once trusted. No search ledger needed.

## Decisions for you
1. Driver: **A1** (gap-driven) now, or also **A2** (completeness critic) for wider recall?
2. Auditability: add the **B2** discovering-query snapshot to provenance, or skip (B1 only)?
3. Human gate: **C1** (auto-admit → needs_review → overlay) or **C2** (auto.json + gate + manual promote)?
4. Cadence: **D1** on-demand to start (recommended), or go straight to **D2** weekly self-heal?
