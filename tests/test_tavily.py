"""Tavily search provider tests (offline — HTTP call is injected, no httpx/key needed)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.config import Settings  # noqa: E402
from taxonomy.retrieval import get_retrieval  # noqa: E402
from taxonomy.retrieval.base import CompositeRetrieval, RetrievalError  # noqa: E402
from taxonomy.retrieval.tavily import TavilySearch  # noqa: E402

_FAKE = {"results": [
    {"url": "https://a.com/x", "title": "A", "content": "about a"},
    {"url": "https://b.com/y", "title": "B", "content": "about b"},
    {"title": "no url — skipped"},
]}


def test_tavily_parses_results():
    t = TavilySearch("tvly-test", poster=lambda payload: _FAKE)
    results = t.search("anything", max_results=5)
    assert [r.url for r in results] == ["https://a.com/x", "https://b.com/y"]
    assert results[0].title == "A" and results[0].snippet == "about a"


def test_tavily_sends_query_and_key():
    captured = {}

    def poster(payload):
        captured.update(payload)
        return {"results": []}

    TavilySearch("tvly-secret", poster=poster).search("my query", max_results=3)
    assert captured["query"] == "my query"
    assert captured["api_key"] == "tvly-secret"
    assert captured["max_results"] == 3


def test_tavily_requires_key():
    try:
        TavilySearch("")
    except RetrievalError:
        return
    raise AssertionError("expected RetrievalError when key missing")


def test_get_retrieval_wires_tavily_when_key_present():
    cfg = Settings(project_id="p", region="global", model="m", offline=False, tavily_api_key="tvly-x")
    assert isinstance(get_retrieval(cfg), CompositeRetrieval)


def test_get_retrieval_no_key_is_fetch_only():
    cfg = Settings(project_id="p", region="global", model="m", offline=False, tavily_api_key=None)
    assert not isinstance(get_retrieval(cfg), CompositeRetrieval)
