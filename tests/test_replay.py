"""Replay/re-verify tests — canonical hashing + source-tier re-grading."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.replay import catalog_hash, reverify_record  # noqa: E402
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


def test_reverify_downgrades_low_quality_source():
    rec = _rec("https://random-blog.example/r")
    assert reverify_record(rec, _judge_llm(), _Stub(), ledger=None) == "needs_review"
    assert rec["source"]["confidence"] == "low"


def test_reverify_keeps_official_source_confirmed_high():
    rec = _rec("https://platform.openai.com/docs/r")
    assert reverify_record(rec, _judge_llm(), _Stub(), ledger=None) == "confirmed"
    assert rec["source"]["confidence"] == "high"


def test_reverify_unsupported_source_flags_needs_review():
    rec = _rec("https://platform.openai.com/docs/r")
    llm = StubLLM({"judge:r": {"supported": False, "confidence": "low", "found_quote": "",
                               "lifecycle_status": "unknown", "rationale": "page is silent"}})
    assert reverify_record(rec, llm, _Stub(), ledger=None) == "needs_review"   # drifted/silent source
