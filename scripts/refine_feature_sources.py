"""Phase 5 cleanup — upgrade weakly-sourced feature records to OFFICIAL sources.

Many feature records were grounded against secondary blogs (single-shot search).
For each feature record whose source isn't official, re-search the provider's own
docs and, if an official page grounds the same feature, swap the source (and refresh
the lifecycle status from it). Records that can't be re-grounded officially are left
as-is (an honest non-official 'source' warning) — never fabricated.

    TAXO_OFFLINE=0 .venv/bin/python scripts/refine_feature_sources.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from taxonomy.config import settings  # noqa: E402
from taxonomy.coverage import OFFICIAL_DOMAINS, _is_official  # noqa: E402
from taxonomy.retrieval.base import RetrievalError  # noqa: E402
from taxonomy.schema import DEFAULT_DATA_PATH  # noqa: E402
from taxonomy.triage import triage_one  # noqa: E402
from taxonomy.validate import validate  # noqa: E402
from taxonomy.vertex_client import get_llm  # noqa: E402
from taxonomy.retrieval import get_retrieval  # noqa: E402
from urllib.parse import urlparse  # noqa: E402

FEATURE_AXES = {"managed-agent-runtime", "mcp-connectors", "agent-memory", "code-execution-sandbox",
                "agent-evals-observability", "guardrails-safety", "subagents-orchestration"}


def _official_candidates(provider, query, retrieval):
    dom = OFFICIAL_DOMAINS.get(provider)
    seen, cands = set(), []
    for q in (f"{provider} {query}", f"{provider} {query} documentation"):
        try:
            results = retrieval.search(q, max_results=4, include_domains=dom)
        except (RetrievalError, NotImplementedError):
            results = []
        for r in results:
            if r.url and r.url not in seen and _is_official(r.url, provider):
                seen.add(r.url)
                cands.append(r)
    return cands


def main() -> int:
    cfg = settings()
    if cfg.offline:
        print("refine needs live grounding + search: set TAXO_OFFLINE=0.", file=sys.stderr)
        return 1
    catalog = json.loads(DEFAULT_DATA_PATH.read_text(encoding="utf-8"))
    llm, retrieval = get_llm(cfg), get_retrieval(cfg)
    prod_by_id = {p["id"]: p for p in catalog["products"]}

    targets = [p for p in catalog["products"]
               if (p.get("kind") == "feature" or p["primary_capability_id"] in FEATURE_AXES)
               and _is_official(p.get("source", {}).get("url", ""), p["provider"]) is False]
    print(f"{len(targets)} feature record(s) with a non-official source\n")
    upgraded = 0
    for rec in targets:
        parent = prod_by_id.get(rec.get("parent_id"))
        query = f"{parent['name']} {rec['name']}" if parent else rec["name"]
        found = None
        try:
            candidates = _official_candidates(rec["provider"], query, retrieval)[:3]
        except (RetrievalError, NotImplementedError):
            candidates = []
        for c in candidates:
            probe = json.loads(json.dumps(rec))
            probe["source"] = {**rec["source"], "url": c.url}
            try:
                outcome = triage_one(probe, dataset=catalog, llm=llm, retrieval=retrieval,
                                     evidence=rec["name"], pinned_capability=rec["primary_capability_id"])
            except Exception as exc:  # transient LLM/network failure after retries → skip this candidate
                print(f"  (skip candidate {urlparse(c.url).netloc}: {type(exc).__name__})")
                continue
            if outcome.decision in ("confirmed", "needs_review"):
                found = (c.url, outcome.record.get("status", rec["status"]))
                break
        if found:
            rec["source"]["url"], rec["status"] = found[0], found[1]
            rec["source"]["confidence"] = "medium"
            upgraded += 1
            print(f"  UPGRADED  {rec['id']:48} → {urlparse(found[0]).netloc}")
        else:
            print(f"  kept      {rec['id']:48} (no official source grounded; honest 'source' warning)")
        DEFAULT_DATA_PATH.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")  # incremental save

    issues = validate(catalog)
    print(f"\nupgraded {upgraded}/{len(targets)} · {'✓ valid' if not issues else f'✗ {len(issues)} issue(s)'}")
    if issues:
        for i in issues[:8]:
            print("   ", i)
        return 1
    DEFAULT_DATA_PATH.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {DEFAULT_DATA_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
