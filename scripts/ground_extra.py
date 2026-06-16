"""Ground a few specific records with corrected sources and append to the catalog.

Targeted top-up (no full re-run) for records that were rejected only because their
first source didn't name them. Appends confirmed/needs_review records to
data/taxonomy.json.

    .venv/bin/python scripts/ground_extra.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.config import settings
from taxonomy.discover import _kebab
from taxonomy.retrieval.http_fetch import HttpFetch
from taxonomy.schema import DEFAULT_DATA_PATH, load_dataset
from taxonomy.triage import triage_one
from taxonomy.vertex_client import VertexLLM

_AS_OF = "2026-06-16"
EXTRA = [
    # Official page describes these but doesn't use the exact name → authoritative source that does.
    ("agentic-coding", "Google", "Antigravity 2.0", "platform", "https://en.wikipedia.org/wiki/Google_Antigravity"),
    ("remote-agent-control", "Anthropic", "Claude Code Remote Control", "feature", "https://www.unite.ai/openclaw-vs-claude-code-remote-control-agents/"),
    ("remote-agent-control", "OpenAI", "Codex Cloud", "feature", "https://www.firecrawl.dev/blog/best-ai-coding-agents"),
]


def _record(cap: str, provider: str, name: str, kind: str, url: str) -> dict:
    return {
        "id": _kebab(provider, name), "name": name, "kind": kind, "provider": provider,
        "capability_ids": [cap], "primary_capability_id": cap,
        "relation_within_capability": "direct", "surfaces": [], "status": "active",
        "review_status": "candidate", "scope_note": "", "lifecycle": [],
        "source": {"url": url, "last_verified": _AS_OF, "confidence": "low"},
    }


def main() -> int:
    cfg = settings()
    llm = VertexLLM(project_id=cfg.project_id, region=cfg.region, model=cfg.model)
    retrieval = HttpFetch()
    catalog = load_dataset()
    existing = {p["id"] for p in catalog["products"]}

    for cap, provider, name, kind, url in EXTRA:
        rec = _record(cap, provider, name, kind, url)
        if rec["id"] in existing:
            print(f"  SKIP (already present) {rec['id']}")
            continue
        outcome = triage_one(rec, dataset=catalog, llm=llm, retrieval=retrieval,
                             evidence=name, pinned_capability=cap)
        outcome.record["kind"] = kind
        outcome.record["capability_ids"] = [cap]
        outcome.record["primary_capability_id"] = cap
        print(f"  {outcome.decision.upper():12} {outcome.record['id']:34} "
              f"[g {outcome.report.grounding.score:.2f}]")
        if outcome.decision in ("confirmed", "needs_review"):
            catalog["products"].append(outcome.record)
            DEFAULT_DATA_PATH.write_text(json.dumps(catalog, indent=2), encoding="utf-8")

    print(f"total products: {len(catalog['products'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
