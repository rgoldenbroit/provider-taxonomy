"""Ground a real, verified catalog — ranking + completeness + pinned capabilities.

Pipeline:
  1. flagship-model: rank each provider's lineup → ground the winner; if its source
     won't verify, fall back to the next-ranked model (so a fetch problem doesn't
     drop the provider's flagship).
  2. other capabilities: ground+triage an exhaustive researched candidate set.
     The capability is PINNED (operator discovery knows it) — the classifier
     refines relation/kind/surfaces and may add secondary capabilities, but can't
     move the primary or attribute flagship-model to a product.
  3. completeness critic per provider×capability: surface what's still missing.

Web access is blocked on this Vertex project, so the candidate list is
operator-researched; the engine does grounding, classification, ranking, audit.

    .venv/bin/python scripts/ground.py
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.config import settings
from taxonomy.discover import _kebab, _norm
from taxonomy.rank import completeness_critic, rank_flagship
from taxonomy.retrieval.http_fetch import HttpFetch
from taxonomy.schema import DEFAULT_DATA_PATH, load_seed
from taxonomy.triage import triage_one
from taxonomy.vertex_client import VertexLLM

_AS_OF = "2026-06-16"
_WIKI_CLAUDE = "https://en.wikipedia.org/wiki/Claude_(language_model)"
_WIKI_CHATGPT = "https://en.wikipedia.org/wiki/ChatGPT"
_WIKI_GEMINI = "https://en.wikipedia.org/wiki/Gemini_(chatbot)"
_WIKI_ANTIGRAVITY = "https://en.wikipedia.org/wiki/Google_Antigravity"

# Official provider sources; the judge reads the lifecycle status off these pages.
_AN_MODELS = "https://docs.anthropic.com/en/docs/about-claude/models/overview"
_OA_GPT55 = "https://openai.com/index/introducing-gpt-5-5/"

FLAGSHIP_LINEUP = {
    "Anthropic": [
        {"name": "Claude Fable 5", "note": "most capable model Anthropic has made generally available (June 9 2026 frontier)", "source_url": _AN_MODELS},
        {"name": "Claude Opus 4.8", "note": "workhorse flagship; top-tier reasoning and agentic coding", "source_url": _AN_MODELS},
    ],
    "OpenAI": [
        {"name": "GPT-5.5 Pro", "note": "highest-capability tier of the GPT-5.5 generation", "source_url": _OA_GPT55},
        {"name": "GPT-5.5", "note": "current default flagship, launched April 2026", "source_url": _OA_GPT55},
    ],
    "Google": [
        {"name": "Gemini 3.5 Pro", "note": "flagship (most capable); unveiled I/O May 2026, nearing June GA; 2M context, Deep Think", "source_url": "https://codersera.com/blog/gemini-3-5-pro-launch-guide-2026/"},
        {"name": "Gemini 3.5 Flash", "note": "fast, low-cost tier of the 3.5 family; GA since May 2026", "source_url": "https://deepmind.google/models/gemini/"},
    ],
}

_CLAUDE_CODE = "https://www.anthropic.com/claude-code"
_WIKI_CODEX = "https://en.wikipedia.org/wiki/GPT-5.3-Codex"
_BROWSER = "https://www.digitalapplied.com/blog/computer-use-agents-2026-claude-openai-gemini-matrix"
_SDK = "https://composio.dev/content/claude-agents-sdk-vs-openai-agents-sdk-vs-google-adk"
_WIKI_GEAP = "https://en.wikipedia.org/wiki/Gemini_Enterprise_Agent_Platform"

# Exhaustive candidates, official sources. (capability, provider, name, kind, url, extra_capability_ids)
CANDIDATES = [
    ("consumer-chat-assistant", "Anthropic", "Claude (web/desktop/mobile)", "product", "https://www.anthropic.com/claude", ()),
    ("consumer-chat-assistant", "OpenAI", "ChatGPT", "product", "https://openai.com/chatgpt/overview/", ()),
    ("consumer-chat-assistant", "Google", "Gemini app", "product", "https://en.wikipedia.org/wiki/Gemini_(chatbot)", ()),

    ("agentic-coding", "Anthropic", "Claude Code", "product", "https://www.anthropic.com/claude-code", ()),
    ("agentic-coding", "OpenAI", "Codex", "product", "https://openai.com/codex/", ()),
    ("agentic-coding", "Google", "Antigravity 2.0", "platform", "https://en.wikipedia.org/wiki/Google_Antigravity", ()),
    ("agentic-coding", "Google", "Antigravity CLI", "product", "https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/", ()),
    ("agentic-coding", "Google", "Jules", "product", "https://jules.google", ("remote-agent-control",)),

    ("remote-agent-control", "Anthropic", "Claude Code Remote Control", "feature", "https://www.unite.ai/openclaw-vs-claude-code-remote-control-agents/", ()),
    ("remote-agent-control", "OpenAI", "Codex Cloud", "feature", "https://www.firecrawl.dev/blog/best-ai-coding-agents", ()),

    ("browser-computer-use-agent", "Anthropic", "Claude Computer Use", "product", "https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/computer-use-tool", ()),
    ("browser-computer-use-agent", "OpenAI", "Operator", "product", "https://openai.com/index/introducing-operator/", ()),
    ("browser-computer-use-agent", "Google", "Gemini Computer Use", "product", "https://www.digitalapplied.com/blog/computer-use-agents-2026-claude-openai-gemini-matrix", ()),

    ("knowledge-work-research", "Anthropic", "Claude Cowork", "product", "https://elephas.app/resources/notebooklm-vs-claude-cowork", ()),
    ("knowledge-work-research", "OpenAI", "ChatGPT Deep Research", "feature", "https://openai.com/index/introducing-deep-research/", ()),
    ("knowledge-work-research", "Google", "NotebookLM", "product", "https://en.wikipedia.org/wiki/NotebookLM", ()),

    ("agent-building-sdk", "Anthropic", "Claude Agent SDK", "product", "https://docs.anthropic.com/en/api/agent-sdk/overview", ()),
    ("agent-building-sdk", "OpenAI", "OpenAI Agents SDK", "product", "https://openai.github.io/openai-agents-python/", ()),
    ("agent-building-sdk", "Google", "Agent Development Kit (ADK)", "product", "https://google.github.io/adk-docs/", ()),

    ("enterprise-agent-platform", "Google", "Gemini Enterprise Agent Platform", "platform", "https://cloud.google.com/products/agent-builder", ()),
    ("enterprise-agent-platform", "Anthropic", "Claude on third-party platforms", "feature", "https://docs.anthropic.com/en/api/claude-on-vertex-ai", ()),
    ("enterprise-agent-platform", "OpenAI", "AgentKit", "platform", "https://openai.com/index/introducing-agentkit", ()),

    ("image-video-generation", "OpenAI", "Sora", "product", "https://help.openai.com/en/articles/20001152-what-to-know-about-the-sora-discontinuation", ()),
    ("image-video-generation", "Google", "Veo", "product", "https://deepmind.google/models/veo/", ()),
]

# Modeled absences — a provider deliberately offers NOTHING on this axis. Operator-asserted:
# the existence judge confirms presence, not absence, so these bypass triage; the source is a
# lineup page that shows the gap. (capability, provider, source_url, note)
ABSENT = [
    ("image-video-generation", "Anthropic",
     "https://docs.anthropic.com/en/docs/about-claude/models/overview",
     "Anthropic ships no first-party image or video generation model; the Claude family is text- and code-only."),
]


def _record(capability: str, provider: str, name: str, kind: str, url: str,
            status: str = "active") -> dict:
    return {
        "id": _kebab(provider, name), "name": name, "kind": kind, "provider": provider,
        "capability_ids": [capability], "primary_capability_id": capability,
        "relation_within_capability": "direct", "surfaces": [], "status": status,
        "review_status": "candidate", "scope_note": "", "lifecycle": [],
        "source": {"url": url, "last_verified": _AS_OF, "confidence": "low"},
    }


def _absent_record(capability: str, provider: str, url: str, note: str) -> dict:
    """A modeled absence: the provider deliberately offers nothing on this axis.
    name '(none)', status 'absent', relation 'none' (per schema.json). Operator-verified
    rather than existence-grounded — the judge confirms presence, and there is none."""
    return {
        "id": _kebab(provider, f"no {capability}"), "name": "(none)", "kind": "product",
        "provider": provider, "capability_ids": [capability], "primary_capability_id": capability,
        "relation_within_capability": "none", "surfaces": [], "status": "absent",
        "review_status": "confirmed", "scope_note": note,
        "lifecycle": [{"date": _AS_OF, "event": "triaged", "note": "Modeled absence — operator-verified."}],
        "source": {"url": url, "last_verified": _AS_OF, "confidence": "medium"},
    }


def _finalize(record: dict, kind: str, capability: str, extras: tuple = ()) -> None:
    """Operator discovery knows the kind + capability — keep them authoritative;
    the LLM's relation/surfaces stay. Avoids over-attribution and wrong-kind noise.
    ``extras`` are curated secondary capabilities (e.g. Jules also fills remote-control)."""
    record["kind"] = kind
    record["capability_ids"] = [capability, *extras]
    record["primary_capability_id"] = capability


def _accept(catalog: dict, outcome, counts: dict) -> bool:
    counts[outcome.decision] = counts.get(outcome.decision, 0) + 1
    g = outcome.report.grounding
    print(f"  {outcome.decision.upper():12} {outcome.record['id']:32} "
          f"[g {g.score:.2f}] caps={outcome.record['capability_ids']}")
    if outcome.decision in ("confirmed", "needs_review"):
        catalog["products"].append(outcome.record)
        DEFAULT_DATA_PATH.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
        return True
    return False


def main() -> int:
    cfg = settings()
    llm = VertexLLM(project_id=cfg.project_id, region=cfg.region, model=cfg.model)
    retrieval = HttpFetch()
    seed = load_seed()
    catalog = {
        "_meta": {"description": "Live grounded catalog — seed capabilities + pipeline-verified products.",
                  "as_of": _AS_OF, "conforms_to": "schema.json"},
        "capabilities": copy.deepcopy(seed["capabilities"]), "products": [],
    }
    print(f"GROUNDING — model {cfg.model} @ {cfg.region}\n")
    counts: dict[str, int] = {}

    print("RANK + GROUND flagship-model (fall back if a source won't verify):")
    for provider, lineup in FLAGSHIP_LINEUP.items():
        choice = rank_flagship(provider, lineup, llm, as_of="June 2026")
        chosen = next((c for c in lineup if _norm(c["name"]) == _norm(choice["flagship_name"])), lineup[0])
        ordered = [chosen] + [c for c in lineup if c is not chosen]
        print(f"  {provider:9} ranked → {chosen['name']} ({choice['rationale'][:70]})")
        for cand in ordered:
            rec = _record("flagship-model", provider, cand["name"], "model",
                          cand["source_url"], cand.get("status", "active"))
            outcome = triage_one(rec, dataset=catalog, llm=llm, retrieval=retrieval,
                                 evidence=cand["name"], pinned_capability="flagship-model")
            _finalize(outcome.record, "model", "flagship-model")
            if _accept(catalog, outcome, counts):
                break
            print(f"               (fall back from {cand['name']} — source not verified)")

    print("\nGROUND + TRIAGE products (capability pinned):")
    for cap, provider, name, kind, url, extras in CANDIDATES:
        rec = _record(cap, provider, name, kind, url)
        outcome = triage_one(rec, dataset=catalog, llm=llm, retrieval=retrieval,
                             evidence=name, pinned_capability=cap)
        _finalize(outcome.record, kind, cap, extras)
        _accept(catalog, outcome, counts)

    print("\nMODELED ABSENCES (provider deliberately offers nothing on this axis):")
    for cap, provider, url, note in ABSENT:
        rec = _absent_record(cap, provider, url, note)
        catalog["products"].append(rec)
        DEFAULT_DATA_PATH.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
        counts["absent"] = counts.get("absent", 0) + 1
        print(f"  ABSENT       {rec['id']:32} caps={rec['capability_ids']}")

    print("\nCOMPLETENESS audit (gaps still missing):")
    by_cap_prov: dict[tuple, list[str]] = {}
    for p in catalog["products"]:
        by_cap_prov.setdefault((p["primary_capability_id"], p["provider"]), []).append(p["name"])
    cap_name = {c["id"]: c["name"] for c in catalog["capabilities"]}
    for (cap, provider), found in sorted(by_cap_prov.items()):
        for gap in completeness_critic(provider, cap_name[cap], found, llm).get("missing", [])[:3]:
            print(f"  [{cap} / {provider}] missing: {gap['name']} — {gap['why'][:70]}")

    print(f"\n{counts}  → wrote {len(catalog['products'])} record(s) to {DEFAULT_DATA_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
