"""Re-derive the catalog from evidence: re-verify each record, re-grade by source tier,
write a provenance receipt. Shared by ``scripts/reverify.py`` (record mode) and
``taxo verify`` (replay mode → the reproducible-build check).
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter

from .sources import derive_confidence, source_tier
from .triage import _clean_enum, _judge_grounding

AS_OF = "2026-06-18"   # the verification date baked into the catalog; replay must match it


def catalog_hash(catalog: dict) -> str:
    """Canonical content hash of a catalog (same serialization the store is written with)."""
    return hashlib.sha256((json.dumps(catalog, indent=2) + "\n").encode("utf-8")).hexdigest()


def reverify_record(rec: dict, llm, retrieval, ledger, as_of: str = AS_OF) -> str:
    """Re-ground one record, re-grade it by source tier, and (if a ledger is active)
    write its provenance receipt. Returns the resulting review_status."""
    page, judge = _judge_grounding(rec, retrieval, llm)   # fetch + judge (both via the ledger when active)
    supported = bool(judge and judge.get("supported"))
    tier = source_tier((rec.get("source") or {}).get("url"), rec.get("provider"))
    if not supported:
        review, conf = "needs_review", "low"
    else:
        review = rec.get("review_status", "confirmed")
        if review == "confirmed" and tier == "low":
            review = "needs_review"            # a lone low-quality source can't stay 'confirmed'
        conf = derive_confidence(tier)
        if review == "needs_review":
            conf = "low" if tier == "low" else "medium"   # not 'high' while under review
        observed = _clean_enum(judge.get("lifecycle_status"))
        if observed and observed != "unknown":
            rec["status"] = observed
    rec["review_status"] = review
    src = rec.setdefault("source", {})
    src["confidence"], src["last_verified"] = conf, as_of
    if ledger is not None and getattr(ledger, "active", False):
        ledger.put("provenance", rec["id"], {
            "record_id": rec["id"], "name": rec["name"], "provider": rec["provider"],
            "primary_capability_id": rec["primary_capability_id"],
            "source_url": src.get("url"), "source_tier": tier,
            "page_content_hash": getattr(page, "content_hash", None),
            "supported": supported, "found_quote": (judge or {}).get("found_quote"),
            "lifecycle_status": (judge or {}).get("lifecycle_status"),
            "review_status": review, "confidence": conf,
            "model": getattr(llm, "model", "?"), "verified_at": as_of,
        })
    return review


def reverify_catalog(catalog: dict, llm, retrieval, ledger, as_of: str = AS_OF) -> Counter:
    catalog.setdefault("_meta", {})["as_of"] = as_of   # the verification date travels with the catalog
    counts: Counter[str] = Counter()
    for rec in catalog["products"]:
        if rec.get("status") == "absent":
            counts["absent"] += 1
            continue
        counts[reverify_record(rec, llm, retrieval, ledger, as_of)] += 1
    return counts
