"""Phase 3b — recorded re-verification (the evidence backfill).

Re-grounds every catalog record with the evidence ledger ON, applies source-tier
grading (low-quality lone sources → needs_review; confidence derived from tier), and
writes a provenance receipt per fact. Captures the full evidence bundle so the catalog
becomes REPLAY-REPRODUCIBLE. It does NOT re-discover — membership is stable; this only
re-verifies + re-grades + receipts the records already present.

    TAXO_OFFLINE=0 TAXO_LEDGER=record .venv/bin/python scripts/reverify.py
    # then replay (no live calls): TAXO_OFFLINE=0 TAXO_LEDGER=replay ... reverify.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from taxonomy.config import settings  # noqa: E402
from taxonomy.replay import AS_OF, reverify_record  # noqa: E402  (one shared grading path)
from taxonomy.retrieval import get_retrieval  # noqa: E402
from taxonomy.schema import DEFAULT_DATA_PATH  # noqa: E402
from taxonomy.sources import source_tier  # noqa: E402
from taxonomy.validate import validate  # noqa: E402
from taxonomy.vertex_client import build_ledger, get_llm  # noqa: E402


def main() -> int:
    import os
    cfg = settings()
    if cfg.offline or cfg.ledger_mode not in ("record", "replay"):
        print("reverify needs: TAXO_OFFLINE=0 and TAXO_LEDGER=record (or replay)", file=sys.stderr)
        return 1
    as_of = os.environ.get("TAXO_AS_OF", AS_OF)   # the scheduled loop stamps the run date
    catalog = json.loads(DEFAULT_DATA_PATH.read_text(encoding="utf-8"))
    catalog.setdefault("_meta", {})["as_of"] = as_of
    llm, retrieval, ledger = get_llm(cfg), get_retrieval(cfg), build_ledger(cfg)
    print(f"re-verify ({cfg.ledger_mode}, as_of {as_of}) — {len(catalog['products'])} records\n")
    feature_ids = {p["id"] for p in catalog["products"] if p.get("kind") == "feature"}
    counts: Counter[str] = Counter()
    for rec in catalog["products"]:
        if rec.get("status") == "absent":
            counts["absent"] += 1
            continue
        if rec.get("review_status") == "scaffold":
            counts["scaffold"] += 1
            continue
        sub = rec.get("parent_id") in feature_ids   # sub-feature → deterministic presence, no judge
        review = reverify_record(rec, llm, retrieval, ledger, as_of, skip_grounding=sub)
        counts[review] += 1
        tier = source_tier((rec.get("source") or {}).get("url"), rec.get("provider"))
        print(f"  {review:12} [{tier:9}] {rec['id']:48}")
        DEFAULT_DATA_PATH.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")

    issues = validate(catalog)
    print(f"\n{dict(counts)} · ledger {ledger.stats()} · "
          f"{'✓ valid' if not issues else f'✗ {len(issues)} schema issue(s)'}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
