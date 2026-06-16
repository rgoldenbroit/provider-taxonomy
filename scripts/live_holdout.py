"""Live hold-out discovery + triage on agentic-coding (real Vertex + real fetches).

Search URLs are seeded (live web_search isn't wired yet), but everything else is
live: httpx fetches the real provider pages, Sonnet 4.6 extracts offerings, the
grounding judge verifies against the live-fetched page, and classification runs
3 real samples. Hold out Claude Code + Jules so the pipeline must rediscover them.

    .venv/bin/python scripts/live_holdout.py
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.config import settings
from taxonomy.discover import discover
from taxonomy.retrieval.base import RetrievalMissing, RetrievalProvider, SearchResult
from taxonomy.retrieval.http_fetch import HttpFetch
from taxonomy.schema import load_seed
from taxonomy.triage import triage_one
from taxonomy.vertex_client import VertexLLM

HOLDOUT = ["anthropic-claude-code", "google-jules"]
SEARCH = {
    "Anthropic agentic-coding products 2026-06": [
        {"url": "https://www.anthropic.com/claude-code", "title": "Claude Code", "snippet": ""}],
    "Google agentic-coding products 2026-06": [
        {"url": "https://jules.google", "title": "Jules", "snippet": ""}],
}


class SeededSearchLiveFetch(RetrievalProvider):
    """Seeded search results, but live page fetches."""

    def __init__(self) -> None:
        self.http = HttpFetch()

    def search(self, query: str, *, max_results: int = 8) -> list[SearchResult]:
        results = SEARCH.get(query)
        if results is None:
            raise RetrievalMissing(query)
        return [SearchResult(**r) for r in results][:max_results]

    def fetch(self, url: str):
        return self.http.fetch(url)


def main() -> int:
    cfg = settings()
    llm = VertexLLM(project_id=cfg.project_id, region=cfg.region, model=cfg.model)
    retrieval = SeededSearchLiveFetch()

    reduced = copy.deepcopy(load_seed())
    reduced["products"] = [p for p in reduced["products"] if p["id"] not in HOLDOUT]

    print(f"LIVE — model {cfg.model} @ {cfg.region}; held out: {', '.join(HOLDOUT)}\n")

    candidates = discover("agentic-coding", llm=llm, retrieval=retrieval,
                          dataset=reduced, providers=("Anthropic", "Google"))
    print(f"DISCOVERED {len(candidates)} candidate(s):")
    for c in candidates:
        print(f"  + {c.record['id']}  ({c.record['provider']}: {c.record['name']})")
        print(f"      source : {c.record['source']['url']}")
        print(f"      evidence: {c.evidence[:140]!r}")

    print("\nTRIAGE (live classification ×3 + live grounding judge):")
    for c in candidates:
        outcome = triage_one(c.record, dataset=reduced, llm=llm, retrieval=retrieval,
                             evidence=c.evidence)
        r = outcome.report
        print(f"  {outcome.decision.upper():9} {outcome.record['id']}  "
              f"→ primary={outcome.record['primary_capability_id']} "
              f"relation={outcome.record['relation_within_capability']} "
              f"kind={outcome.record['kind']}")
        print(f"      schema {r.schema.score:.0f} ({r.schema.detail})")
        print(f"      grounding {r.grounding.score:.2f} ({r.grounding.detail})")
        print(f"      classification {r.classification.score:.2f} ({r.classification.detail})")
        print(f"      VERIFY → open {outcome.record['source']['url']}")
        print(f"               and find: {c.evidence[:160]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
