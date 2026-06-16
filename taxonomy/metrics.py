"""Dataset-level trust metrics — the quantitative health of the canonical store."""

from __future__ import annotations

from collections import Counter

from .staleness import is_stale, today_for
from .validate import validate


def dataset_metrics(dataset: dict) -> dict:
    products = dataset.get("products", [])
    n = len(products) or 1
    issues = validate(dataset)
    today = today_for(dataset)

    with_source = sum(1 for p in products if (p.get("source") or {}).get("url"))
    stale = sum(1 for p in products if is_stale(p, today))
    review_status = Counter(p.get("review_status", "confirmed") for p in products)
    confidence = Counter((p.get("source") or {}).get("confidence") for p in products)

    return {
        "products": len(products),
        "capabilities": len(dataset.get("capabilities", [])),
        "schema_conformance": 1.0 if not issues else 0.0,
        "schema_issues": len(issues),
        "provenance_completeness": round(with_source / n, 3),
        "staleness_coverage": round(1 - stale / n, 3),  # fraction within re-verify window
        "stale_count": stale,
        "review_status": dict(review_status),
        "confidence": {k: v for k, v in confidence.items() if k},
    }
