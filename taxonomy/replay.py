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


def reverify_record(rec: dict, llm, retrieval, ledger, as_of: str = AS_OF,
                    skip_grounding: bool = False) -> str:
    """Re-ground one record, re-grade it by source tier, and (if a ledger is active)
    write its provenance receipt. Returns the resulting review_status.

    ``skip_grounding`` (sub-features) → no fetch/judge/LLM at all: a sub-feature was admitted by
    deterministic string-presence on its parent feature's already-grounded official page, so it
    needs no independent judge call. It passes through unchanged (keeps verify byte-identical) and
    is the bulk of the cost saving (sub-features are ~75% of records)."""
    if skip_grounding:
        return rec.get("review_status", "confirmed")
    page, judge = _judge_grounding(rec, retrieval, llm)   # fetch + judge (both via the ledger when active)
    fetch_ok = (page is not None and getattr(page, "status", 0) == 200
                and bool((getattr(page, "text", "") or "").strip()))
    supported = bool(judge and judge.get("supported"))
    reconfirmed = fetch_ok and supported
    tier = source_tier((rec.get("source") or {}).get("url"), rec.get("provider"))
    src = rec.setdefault("source", {})
    review = rec.get("review_status", "confirmed")   # CONSERVATIVE: keep the prior verdict by default

    if reconfirmed:
        src["last_verified"] = as_of                  # only refresh the date when we actually re-confirmed
        if review == "confirmed":
            src["confidence"] = derive_confidence(tier)
    # else: blocked/silent this run → keep verdict + confidence + (now-stale) date; the receipt flags it.
    # NOTE: a routine re-verify does NOT reclassify lifecycle `status`. The grounding judge verifies
    # EXISTENCE, not lifecycle, and its lifecycle read is noisy (and model-dependent) — letting it flip
    # status silently drifts the catalog (e.g. a current product judged "deprecated"). The observed
    # lifecycle_status is still recorded in the receipt below for the audit/triangulation to flag, where
    # a real change gets a second-source check and deliberate review instead of a silent overwrite.

    if ledger is not None and getattr(ledger, "active", False):
        ledger.put("provenance", rec["id"], {
            "record_id": rec["id"], "name": rec["name"], "provider": rec["provider"],
            "primary_capability_id": rec["primary_capability_id"],
            "source_url": src.get("url"), "source_tier": tier,
            "page_content_hash": getattr(page, "content_hash", None),
            "fetch_ok": fetch_ok, "supported": supported, "reconfirmed": reconfirmed,
            "found_quote": (judge or {}).get("found_quote"),
            "lifecycle_status": (judge or {}).get("lifecycle_status"),
            "review_status": review, "confidence": src.get("confidence"),
            "model": getattr(llm, "model", "?"), "verified_at": src.get("last_verified"),
        })
    return review


def reverify_catalog(catalog: dict, llm, retrieval, ledger, as_of: str = AS_OF) -> Counter:
    catalog.setdefault("_meta", {})["as_of"] = as_of   # the verification date travels with the catalog
    feature_ids = {p["id"] for p in catalog["products"] if p.get("kind") == "feature"}
    counts: Counter[str] = Counter()
    for rec in catalog["products"]:
        if rec.get("status") == "absent":
            counts["absent"] += 1
            continue
        # Structural scaffold (e.g. a hand-added sub-feature) is not yet ground-verified
        # and carries no ledger evidence. The reproducible-build check reproduces the
        # *grounded* catalog; scaffold passes through unchanged until the loop grounds it.
        if rec.get("review_status") == "scaffold":
            counts["scaffold"] += 1
            continue
        # A sub-feature's parent is itself a feature → skip the judge (deterministic presence).
        sub = rec.get("parent_id") in feature_ids
        counts[reverify_record(rec, llm, retrieval, ledger, as_of, skip_grounding=sub)] += 1
    return counts
