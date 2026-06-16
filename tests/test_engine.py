"""Phase 1 tests: offline LLM stub + retrieval. No GCP creds, no network."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.config import Settings  # noqa: E402
from taxonomy.retrieval import get_retrieval  # noqa: E402
from taxonomy.retrieval.base import RetrievalMissing  # noqa: E402
from taxonomy.retrieval.fixtures import FixtureRetrieval  # noqa: E402
from taxonomy.retrieval.http_fetch import html_to_text  # noqa: E402
from taxonomy.validate import validate_instance  # noqa: E402
from taxonomy.vertex_client import StubLLM, get_llm, instance_from_schema  # noqa: E402

_OFFLINE = Settings(project_id=None, region="us-east5", model="claude-opus-4-8", offline=True)

_DEMO_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "kind", "tags"],
    "properties": {
        "name": {"type": "string"},
        "kind": {"type": "string", "enum": ["product", "feature"]},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
}


def test_instance_from_schema_is_valid():
    inst = instance_from_schema(_DEMO_SCHEMA)
    assert validate_instance(inst, _DEMO_SCHEMA) == []
    assert inst["kind"] == "product"  # first enum value, deterministic


def test_stub_structured_returns_valid_instance():
    llm = StubLLM()
    out = llm.structured(system="s", prompt="p", schema=_DEMO_SCHEMA)
    assert validate_instance(out, _DEMO_SCHEMA) == []
    assert llm.calls and llm.calls[0]["prompt"] == "p"  # prompts are recorded


def test_stub_returns_canned_response_by_label():
    canned = {"name": "Claude Code", "kind": "product", "tags": ["agentic-coding"]}
    llm = StubLLM(responses={"cc": canned})
    assert llm.structured(system="s", prompt="p", schema=_DEMO_SCHEMA, label="cc") == canned


def test_get_llm_offline_is_stub():
    assert isinstance(get_llm(_OFFLINE), StubLLM)


def test_fixture_retrieval_search_and_fetch():
    r = get_retrieval(_OFFLINE)
    assert isinstance(r, FixtureRetrieval)
    query = "Anthropic agentic-coding products 2026-06"
    results = r.search(query)
    assert results and results[0].url == "https://www.anthropic.com/claude-code"
    page = r.fetch(results[0].url)
    assert "agentic coding" in page.text and len(page.content_hash) == 64


def test_fixture_retrieval_missing_raises():
    r = FixtureRetrieval()
    try:
        r.search("no such query")
    except RetrievalMissing:
        return
    raise AssertionError("expected RetrievalMissing for an unrecorded query")


def test_html_to_text_strips_tags_and_scripts():
    html = "<html><head><style>.a{}</style></head><body><h1>Hi</h1>" \
           "<script>evil()</script><p>Body text</p></body></html>"
    text = html_to_text(html)
    assert "Hi" in text and "Body text" in text
    assert "evil" not in text and ".a{" not in text
