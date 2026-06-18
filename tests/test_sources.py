"""Source-tier classification + the source-quality admission rule."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.retrieval.base import FetchedPage, RetrievalProvider, content_hash  # noqa: E402
from taxonomy.schema import load_seed  # noqa: E402
from taxonomy.sources import derive_confidence, source_tier  # noqa: E402
from taxonomy.triage import triage_one  # noqa: E402
from taxonomy.vertex_client import StubLLM  # noqa: E402


def test_source_tier():
    assert source_tier("https://docs.anthropic.com/x", "Anthropic") == "official"
    assert source_tier("https://ai.google.dev/x", "Google") == "official"
    assert source_tier("https://en.wikipedia.org/wiki/x") == "reputable"
    assert source_tier("https://github.com/a/b") == "reputable"
    assert source_tier("https://agentpedia.codes/x", "Google") == "low"        # junk blocklist
    assert source_tier("https://some-random-blog.example/x") == "low"
    # provider-specific: another provider's official domain is NOT official for this provider
    assert source_tier("https://openai.com/x", "OpenAI") == "official"
    assert source_tier("https://openai.com/x", "Google") == "low"


def test_derive_confidence():
    assert derive_confidence("official") == "high"
    assert derive_confidence("reputable") == "medium"
    assert derive_confidence("low") == "low"


class _Stub(RetrievalProvider):
    _PAGE = "T is OpenAI's agentic coding tool, generally available."

    def search(self, q, *, max_results=8, include_domains=None):
        return []

    def fetch(self, url):
        return FetchedPage(url=url, status=200, text=self._PAGE, content_hash=content_hash(self._PAGE))


def _record(url):
    return {"id": "t", "name": "T", "kind": "product", "provider": "OpenAI",
            "capability_ids": ["agentic-coding"], "primary_capability_id": "agentic-coding",
            "relation_within_capability": "direct", "surfaces": [], "status": "active",
            "review_status": "candidate", "scope_note": "", "lifecycle": [],
            "source": {"url": url, "last_verified": "2026-06-17", "confidence": "low"}}


def _llm():
    return StubLLM({
        "triage:t": {"capability_ids": ["agentic-coding"], "primary_capability_id": "agentic-coding",
                     "relation_within_capability": "direct", "kind": "product", "surfaces": [],
                     "confidence": "high", "rationale": "x"},
        "judge:t": {"supported": True, "confidence": "high", "found_quote": "agentic coding tool",
                    "lifecycle_status": "active", "rationale": "y"}})


def test_official_source_confirms_high():
    o = triage_one(_record("https://platform.openai.com/docs/x"), dataset=load_seed(),
                   llm=_llm(), retrieval=_Stub())
    assert o.decision == "confirmed" and o.record["source"]["confidence"] == "high"


def test_low_quality_source_is_downgraded_even_when_grounding_passes():
    # grounding passes (the page substantiates it) but a lone low-quality source can't confirm
    o = triage_one(_record("https://random-blog.example/x"), dataset=load_seed(),
                   llm=_llm(), retrieval=_Stub())
    assert o.decision == "needs_review" and o.record["source"]["confidence"] == "low"
