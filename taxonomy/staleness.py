"""Confidence-weighted staleness.

A record is stale when ``today - source.last_verified`` exceeds the re-verify
interval for its confidence — low-confidence records are re-checked sooner.
``today`` defaults to the dataset's ``_meta.as_of`` for deterministic behavior.
"""

from __future__ import annotations

from datetime import date

INTERVALS = {"high": 90, "medium": 45, "low": 21}  # days
_FALLBACK_TODAY = "2026-06-15"


def today_for(dataset: dict) -> str:
    return (dataset.get("_meta") or {}).get("as_of") or _FALLBACK_TODAY


def days_overdue(product: dict, today: str) -> int | None:
    source = product.get("source") or {}
    last_verified = source.get("last_verified")
    if not last_verified:
        return None
    interval = INTERVALS.get(source.get("confidence", "low"), INTERVALS["low"])
    age = (date.fromisoformat(today) - date.fromisoformat(last_verified)).days
    return age - interval


def is_stale(product: dict, today: str) -> bool:
    overdue = days_overdue(product, today)
    return overdue is not None and overdue > 0
