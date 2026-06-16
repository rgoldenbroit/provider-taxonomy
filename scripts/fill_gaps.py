"""Fill two specific coverage gaps WITHOUT re-grounding the existing catalog.

  - OpenAI × enterprise-agent-platform → ground AgentKit (a real product) and append.
  - Anthropic × image-video-generation → append a modeled-absence record.

Incremental + idempotent: loads data/taxonomy.json, skips ids already present, validates,
writes back. The source of truth (scripts/ground.py) carries the same two additions, so a
full re-ground reproduces this result — this script just avoids disturbing the 26 verified
records (and re-tripping known-flaky sources) when all we want is the two gaps.

    .venv/bin/python scripts/fill_gaps.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from ground import ABSENT, _absent_record, _finalize, _record  # noqa: E402

from taxonomy.config import settings  # noqa: E402
from taxonomy.retrieval.http_fetch import HttpFetch  # noqa: E402
from taxonomy.schema import DEFAULT_DATA_PATH  # noqa: E402
from taxonomy.triage import triage_one  # noqa: E402
from taxonomy.validate import validate  # noqa: E402
from taxonomy.vertex_client import VertexLLM  # noqa: E402

# Real products to ground into a gap. (capability, provider, name, kind, source_url)
NEW_CANDIDATES = [
    ("enterprise-agent-platform", "OpenAI", "AgentKit", "platform",
     "https://openai.com/index/introducing-agentkit"),
]


def main() -> int:
    cfg = settings()
    if cfg.offline:
        print("fill_gaps needs live grounding: set TAXO_OFFLINE=0.", file=sys.stderr)
        return 1
    catalog = json.loads(DEFAULT_DATA_PATH.read_text(encoding="utf-8"))
    have = {p["id"] for p in catalog["products"]}
    llm = VertexLLM(project_id=cfg.project_id, region=cfg.region, model=cfg.model)
    retrieval = HttpFetch()

    print("GROUND new real products (capability pinned):")
    for cap, provider, name, kind, url in NEW_CANDIDATES:
        rec = _record(cap, provider, name, kind, url)
        if rec["id"] in have:
            print(f"  SKIP (exists) {rec['id']}")
            continue
        outcome = triage_one(rec, dataset=catalog, llm=llm, retrieval=retrieval,
                             evidence=name, pinned_capability=cap)
        _finalize(outcome.record, kind, cap)
        print(f"  {outcome.decision.upper():12} {outcome.record['id']:30} "
              f"[g {outcome.report.grounding.score:.2f}] status={outcome.record['status']}")
        if outcome.decision in ("confirmed", "needs_review"):
            catalog["products"].append(outcome.record)
            have.add(outcome.record["id"])
        else:
            print("    (not appended — grounding did not confirm; check the source URL)")

    print("MODELED ABSENCES:")
    for cap, provider, url, note in ABSENT:
        rec = _absent_record(cap, provider, url, note)
        if rec["id"] in have:
            print(f"  SKIP (exists) {rec['id']}")
            continue
        catalog["products"].append(rec)
        have.add(rec["id"])
        print(f"  ABSENT       {rec['id']:30} caps={rec['capability_ids']}")

    issues = validate(catalog)
    if issues:
        print(f"\n✗ {len(issues)} schema issue(s) — NOT writing:")
        for i in issues[:10]:
            print("   ", i)
        return 1
    DEFAULT_DATA_PATH.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"\n✓ valid — wrote {len(catalog['products'])} products to {DEFAULT_DATA_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
