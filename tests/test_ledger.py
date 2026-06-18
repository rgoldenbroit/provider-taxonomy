"""Evidence ledger tests — content-addressing + record→replay determinism."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.ledger import REPLAY, RECORD, Ledger, LedgerMiss, digest, llm_key, page_key  # noqa: E402


def test_digest_is_stable_and_unambiguous():
    assert digest("a", "b") == digest("a", "b")
    assert digest("a", "b") != digest("b", "a")        # order matters
    assert digest("ab", "c") != digest("a", "bc")      # NUL separation prevents concatenation collisions


def test_keys_are_deterministic_and_input_sensitive():
    assert llm_key(model="m", system="s", prompt="p", schema={"x": 1}) == \
           llm_key(model="m", system="s", prompt="p", schema={"x": 1})
    assert llm_key(model="m", system="s", prompt="p", schema={"x": 1}) != \
           llm_key(model="m2", system="s", prompt="p", schema={"x": 1})
    assert page_key("https://a") != page_key("https://b")


def test_put_get_roundtrip():
    d = tempfile.mkdtemp()
    try:
        led = Ledger(d, RECORD)
        led.put("llm", "k1", {"r": 1})
        assert led.get("llm", "k1")["value"] == {"r": 1}
        assert led.get("llm", "missing") is None
    finally:
        shutil.rmtree(d)


def test_record_then_replay_is_deterministic():
    d = tempfile.mkdtemp()
    try:
        calls = []
        rec = Ledger(d, RECORD)
        v1 = rec.cached("llm", "k", lambda: (calls.append(1), {"v": 42})[1])
        v2 = rec.cached("llm", "k", lambda: (calls.append(1), {"v": 99})[1])  # hit → not recomputed
        assert v1 == v2 == {"v": 42}
        assert len(calls) == 1

        def boom():
            raise AssertionError("replay must never compute")
        rep = Ledger(d, REPLAY)                       # fresh ledger over the same evidence
        assert rep.cached("llm", "k", boom) == {"v": 42}
    finally:
        shutil.rmtree(d)


def test_replay_miss_raises():
    d = tempfile.mkdtemp()
    try:
        rep = Ledger(d, REPLAY)
        try:
            rep.cached("llm", "absent", lambda: {"v": 1})
            raise AssertionError("expected LedgerMiss")
        except LedgerMiss:
            pass
    finally:
        shutil.rmtree(d)


def test_off_mode_is_inactive():
    assert Ledger("/tmp/unused", "off").active is False
    assert Ledger("/tmp/unused", RECORD).active is True
    assert Ledger("/tmp/unused", REPLAY).active is True


def test_triage_writes_a_provenance_receipt():
    from taxonomy.retrieval.base import FetchedPage, RetrievalProvider, content_hash
    from taxonomy.schema import load_seed
    from taxonomy.triage import triage_one
    from taxonomy.vertex_client import StubLLM

    page_text = "Test X is OpenAI's agentic coding tool, generally available."

    class _Stub(RetrievalProvider):
        def search(self, q, *, max_results=8, include_domains=None):
            return []

        def fetch(self, url):
            return FetchedPage(url=url, status=200, text=page_text, content_hash=content_hash(page_text))

    rec = {"id": "test-x", "name": "Test X", "kind": "product", "provider": "OpenAI",
           "capability_ids": ["agentic-coding"], "primary_capability_id": "agentic-coding",
           "relation_within_capability": "direct", "surfaces": [], "status": "active",
           "review_status": "candidate", "scope_note": "", "lifecycle": [],
           "source": {"url": "https://openai.com/x", "last_verified": "2026-06-17", "confidence": "low"}}
    llm = StubLLM({
        "triage:test-x": {"capability_ids": ["agentic-coding"], "primary_capability_id": "agentic-coding",
                          "relation_within_capability": "direct", "kind": "product", "surfaces": [],
                          "confidence": "high", "rationale": "a coding tool"},
        "judge:test-x": {"supported": True, "confidence": "high", "found_quote": "agentic coding tool",
                         "lifecycle_status": "active", "rationale": "page describes it"}})

    d = tempfile.mkdtemp()
    try:
        led = Ledger(d, RECORD)
        triage_one(rec, dataset=load_seed(), llm=llm, retrieval=_Stub(), ledger=led)
        receipt = led.get("provenance", "test-x")
        assert receipt is not None
        r = receipt["value"]
        assert r["judge"]["found_quote"] == "agentic coding tool"
        assert r["decision"] in ("confirmed", "needs_review")
        assert "grounding" in r["gates"] and "schema" in r["gates"]
        assert r["page_content_hash"]
    finally:
        shutil.rmtree(d)
