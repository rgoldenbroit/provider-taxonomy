# Research — Catalog credibility + coverage cleanup

Devil's-advocate review surfaced five workstreams (user-approved). This documents the diagnosis and
the investigation that grounds the plan.

## 1. Source credibility (highest ROI)
The hero claims "discovered from the live web, grounded to its source… kept honest" and the engine's
whole pitch is official-docs grounding — but several nodes are sourced from Wikipedia/blogs:

| Node | Provider | Current source | First-party replacement (verified 200) |
|---|---|---|---|
| Antigravity | Google | en.wikipedia.org | `antigravity.google/` |
| Gemini app | Google | en.wikipedia.org | `gemini.google/about/` or `support.google.com/gemini/` |
| NotebookLM | Google | en.wikipedia.org | `notebooklm.google/` |
| Gemini 3.5 Pro | Google | codersera.com (blog) | `blog.google/products/gemini/` or `ai.google.dev` — **verify it exists** |
| Gemini Computer Use | Google | digitalapplied.com (blog) | `ai.google.dev/gemini-api/docs/computer-use` (200) |
| Claude Cowork | Anthropic | elephas.app (blog) | **verify on anthropic.com/claude.com — DROP if no official page** |

`is_official` already exists; the gap is that these nodes were admitted via search with non-official
sources and never re-grounded. **Decision:** re-ground each to a first-party page; any node with NO
official page (likely Claude Cowork, possibly Gemini 3.5 Pro) is dropped or marked unverified honestly
— not shown as confirmed on a blog.

## 2. Coverage is uneven (8 product capabilities, only 2 deep)
Deep: **agentic-coding** (43/37/34) and **enterprise-agent-platform**. Hollow (bare product cards,
0 features, no comparison_note): consumer-chat, browser-computer-use, image-video, agent-building-sdk,
knowledge-work, flagship-model. Tractability by doc surface:

- **Easy (clean machine-readable docs):** `agent-building-sdk` (OpenAI Agents SDK `developers.openai.com`/`openai.github.io`; Claude Agent SDK `docs.claude.com`; Google ADK `adk.dev/llms-full.txt`); `browser-computer-use` (Claude Computer Use `docs.claude.com`; OpenAI computer-use in Responses docs; Gemini Computer Use `ai.google.dev/gemini-api/docs/computer-use`); `image-video-generation` (OpenAI image/Sora `platform/help`; Google Imagen/Veo `ai.google.dev`/`deepmind.google`; Anthropic honestly **absent**).
- **Hard (help-center / SPA wall):** `consumer-chat-assistant` (Anthropic `support.anthropic.com` clean; OpenAI `help.openai.com` Cloudflare-blocked; Gemini app SPA) — needs Tavily-content path or stays partial; `knowledge-work-research` (Deep Research across ChatGPT/Gemini/Claude + NotebookLM — mixed).
- **Different shape:** `flagship-model` (Claude Fable 5 / Gemini 3.5 Pro / GPT-5.5 Pro) — models, not feature-decomposable; better compared on attributes (context, modalities, pricing, thinking). Treat separately or defer.

## 3. Dedup + mis-scoped noise
- **31 duplicate-name groups** within a provider (same feature under multiple axes): two "Code Review", two "Sandbox runtime", two "Permission system" (Anthropic); three "asynchronous execution model" (Google). Root cause: extraction under several axis keyword-sets without cross-axis dedup.
- **Mis-scoped API/SDK minutiae as features:** the refusal/fallback cluster — `stop_details policy category: On Claude Fable 5…`, `fallback credit`, `Track refusal patterns`, `Reset context after refusal`, `Session rate limiting`.
- **Sentence-as-name features:** the 10 longest names are 136–159 chars.
- **Sub-features have no scope_note** → pop-out "what it is" falls back to the parent capability's generic description.

## 4. Overview level-mixing
The matrix renders all 16 capabilities as rows, mixing **product capabilities** (few pills) with
**developer-platform axes** (`guardrails-safety`=165 features, `mcp-connectors`=122) as unreadable
pill-clouds; the axes also nest inside product trees, so features appear twice. Clean fix: matrix shows
only capabilities NOT in any `categories.feature_axis_ids`; axes live only inside product pop-outs.
(`remote-agent-control` is mis-tiered `end_user_product` but is an axis — the feature_axis_ids signal
catches it regardless; also worth re-tiering it `developer_platform`.)

## 5. Spotchecks
- **Sora `sunset` is correct** — grounded to `help.openai.com/.../sora-discontinuation` (review was too hasty; the grounding worked).
- Remaining: spot-check the 10 `deprecated` + 92 `preview` flags against their cited pages; correct outliers.

## Reproducibility note (affects every phase)
Re-grounding, renaming, or dropping nodes changes the grounding-judge `llm_key` and the product set →
each data phase needs `reverify(record)` → `taxo verify` byte-identical → ledger prune. `comparison`
is regenerated only for changed/new nodes.

## Open questions
1. **flagship-model**: model-attribute comparison, or defer? (Recommend defer — different data shape.)
2. **consumer-chat / knowledge-work**: build Tavily-content retriever for blocked help centers, or fill only cleanly-documented providers + mark the rest honestly? (Recommend clean providers now, Tavily later.)
3. **Cleanup mechanism**: deterministic dedup + heuristic drop, or LLM cleanup pass? (Recommend both.)
