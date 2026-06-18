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
from taxonomy.retrieval import get_retrieval  # noqa: E402
from taxonomy.schema import DEFAULT_DATA_PATH  # noqa: E402
from taxonomy.sources import derive_confidence, source_tier  # noqa: E402
from taxonomy.triage import _clean_enum, _judge_grounding  # noqa: E402
from taxonomy.validate import validate  # noqa: E402
from taxonomy.vertex_client import build_ledger, get_llm  # noqa: E402

_AS_OF = "2026-06-18"


def main() -> int:
    cfg = settings()
    if cfg.offline or cfg.ledger_mode not in ("record", "replay"):
        print("reverify needs: TAXO_OFFLINE=0 and TAXO_LEDGER=record (or replay)", file=sys.stderr)
        return 1
    catalog = json.loads(DEFAULT_DATA_PATH.read_text(encoding="utf-8"))
    llm, retrieval, ledger = get_llm(cfg), get_retrieval(cfg), build_ledger(cfg)
    print(f"re-verify ({cfg.ledger_mode}) — {len(catalog['products'])} records\n")
    counts: Counter[str] = Counter()
    for rec in catalog["products"]:
        if rec.get("status") == "absent":
            counts["absent"] += 1
            continue
        page, judge = _judge_grounding(rec, retrieval, llm)   # fetch + judge, both via the ledger
        supported = bool(judge and judge.get("supported"))
        tier = source_tier((rec.get("source") or {}).get("url"), rec.get("provider"))
        if not supported:
            review, conf = "needs_review", "low"
        else:
            review = rec.get("review_status", "confirmed")
            if review == "confirmed" and tier == "low":
                review = "needs_review"            # a lone low-quality source can't stay 'confirmed'
            conf = derive_confidence(tier)
            if review == "needs_review":           # a record under review isn't 'high' confidence
                conf = "low" if tier == "low" else "medium"
            observed = _clean_enum(judge.get("lifecycle_status"))
            if observed and observed != "unknown":
                rec["status"] = observed           # refresh lifecycle from the source
        rec["review_status"] = review
        src = rec.setdefault("source", {})
        src["confidence"], src["last_verified"] = conf, _AS_OF
        ledger.put("provenance", rec["id"], {
            "record_id": rec["id"], "name": rec["name"], "provider": rec["provider"],
            "primary_capability_id": rec["primary_capability_id"],
            "source_url": src.get("url"), "source_tier": tier,
            "page_content_hash": getattr(page, "content_hash", None),
            "supported": supported,
            "found_quote": (judge or {}).get("found_quote"),
            "lifecycle_status": (judge or {}).get("lifecycle_status"),
            "review_status": review, "confidence": conf,
            "model": getattr(llm, "model", "?"), "verified_at": _AS_OF,
        })
        counts[review] += 1
        flag = "" if supported else "  ← source no longer substantiates"
        print(f"  {review:12} [{tier:9}] {rec['id']:48}{flag}")
        DEFAULT_DATA_PATH.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")

    issues = validate(catalog)
    print(f"\n{dict(counts)} · ledger {ledger.stats()} · "
          f"{'✓ valid' if not issues else f'✗ {len(issues)} schema issue(s)'}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
