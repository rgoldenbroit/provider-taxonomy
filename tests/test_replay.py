"""Replay/re-verify tests — canonical hashing + source-tier re-grading."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.replay import catalog_hash, reverify_catalog, reverify_record  # noqa: E402
from taxonomy.retrieval.base import FetchedPage, RetrievalProvider, content_hash  # noqa: E402
from taxonomy.vertex_client import StubLLM  # noqa: E402


def test_catalog_hash_is_deterministic_and_sensitive():
    a = {"products": [{"id": "x", "name": "X"}]}
    assert catalog_hash(a) == catalog_hash({"products": [{"id": "x", "name": "X"}]})
    assert catalog_hash(a) != catalog_hash({"products": [{"id": "y", "name": "X"}]})


class _Stub(RetrievalProvider):
    _PAGE = "R is OpenAI's agentic coding tool, generally available."

    def search(self, q, *, max_results=8, include_domains=None):
        return []

    def fetch(self, url):
        return FetchedPage(url=url, status=200, text=self._PAGE, content_hash=content_hash(self._PAGE))


def _rec(url):
    return {"id": "r", "name": "R", "kind": "product", "provider": "OpenAI",
            "primary_capability_id": "agentic-coding", "review_status": "confirmed", "status": "active",
            "source": {"url": url, "last_verified": "2026-06-01", "confidence": "high"}}


def _judge_llm():
    return StubLLM({"judge:r": {"supported": True, "confidence": "high", "found_quote": "agentic coding tool",
                                "lifecycle_status": "active", "rationale": "page describes it"}})


def test_reverify_official_reconfirm_refreshes_date_and_confidence():
    rec = _rec("https://platform.openai.com/docs/r")   # prior: confirmed, last_verified 2026-06-01
    assert reverify_record(rec, _judge_llm(), _Stub(), ledger=None) == "confirmed"
    assert rec["source"]["confidence"] == "high"
    assert rec["source"]["last_verified"] == "2026-06-18"   # refreshed on re-confirmation (AS_OF)


def test_reverify_keeps_confirmed_on_low_source_with_low_confidence():
    rec = _rec("https://random-blog.example/r")         # low tier but already confirmed
    assert reverify_record(rec, _judge_llm(), _Stub(), ledger=None) == "confirmed"   # conservative: no downgrade
    assert rec["source"]["confidence"] == "low"         # confidence reflects the tier


def test_reverify_silent_200_page_keeps_prior_not_downgraded():
    rec = _rec("https://platform.openai.com/docs/r")
    llm = StubLLM({"judge:r": {"supported": False, "confidence": "low", "found_quote": "",
                               "lifecycle_status": "unknown", "rationale": "page is silent"}})
    assert reverify_record(rec, llm, _Stub(), ledger=None) == "confirmed"   # a single silent re-check ≠ drift
    assert rec["source"]["last_verified"] == "2026-06-01"  # date NOT refreshed (not re-confirmed)


class _Blocked(RetrievalProvider):
    """Simulates a 403/empty fetch (e.g. a datacenter IP getting blocked)."""

    def search(self, q, *, max_results=8, include_domains=None):
        return []

    def fetch(self, url):
        return FetchedPage(url=url, status=403, text="", content_hash=content_hash(""))


class _Exploding(RetrievalProvider):
    """Any fetch is a hard error — proves a record was NOT ground-verified."""

    def search(self, q, *, max_results=8, include_domains=None):
        return []

    def fetch(self, url):
        raise AssertionError(f"scaffold record must not be grounded (fetched {url})")


def test_reverify_catalog_skips_scaffold_without_grounding():
    # A scaffold node carries no ledger evidence; replay must skip it AND leave the
    # catalog byte-identical, so `taxo verify` stays green when scaffold is present.
    catalog = {"_meta": {"as_of": "2026-06-18"}, "products": [{
        "id": "sf", "name": "Sub-feature", "kind": "feature", "provider": "Anthropic",
        "parent_id": "p", "capability_ids": ["agentic-coding"],
        "primary_capability_id": "agentic-coding", "relation_within_capability": "partial",
        "review_status": "scaffold", "status": "active",
        "source": {"url": "https://docs.anthropic.com/x", "last_verified": "2026-06-18", "confidence": "low"},
    }]}
    before = catalog_hash(catalog)
    counts = reverify_catalog(catalog, _judge_llm(), _Exploding(), ledger=None, as_of="2026-06-18")
    assert counts["scaffold"] == 1
    assert catalog_hash(catalog) == before   # unchanged → reproducible-build hash holds


def test_reverify_keeps_prior_verdict_when_source_unreachable():
    rec = _rec("https://platform.openai.com/docs/r")   # prior: confirmed / high
    llm = StubLLM({"judge:r": {"supported": False, "confidence": "low", "found_quote": "",
                               "lifecycle_status": "unknown", "rationale": "empty page"}})
    assert reverify_record(rec, llm, _Blocked(), ledger=None) == "confirmed"   # unreachable ≠ gone
    assert rec["source"]["confidence"] == "high"        # grade untouched
    assert rec["source"]["last_verified"] == "2026-06-01"  # date NOT refreshed (we didn't verify it)
