"""Audit critic + gate tests (deterministic parts; no LLM/network)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.audit import (  # noqa: E402
    Finding,
    _coverage_findings,
    _mechanical_findings,
    _triangulate,
    audit_catalog,
    gate,
    source_authority,
)
from taxonomy.retrieval.base import FetchedPage, RetrievalProvider, SearchResult, content_hash  # noqa: E402
from taxonomy.vertex_client import StubLLM  # noqa: E402


class _OneSourceRetrieval(RetrievalProvider):
    """A single independent secondary result + a canned page (for triangulation tests)."""

    def __init__(self, url="https://secondary.example/x", text="unrelated page text"):
        self._url, self._text = url, text

    def search(self, query, *, max_results=8, include_domains=None):
        return [SearchResult(url=self._url, title="x", snippet="")]

    def fetch(self, url):
        return FetchedPage(url=url, status=200, text=self._text, content_hash=content_hash(self._text))
from taxonomy.schema import load_seed  # noqa: E402


def test_source_authority():
    assert source_authority("https://www.anthropic.com/claude") == "official"
    assert source_authority("https://help.openai.com/en/articles/x") == "official"
    assert source_authority("https://deepmind.google/models/veo/") == "official"
    assert source_authority("https://en.wikipedia.org/wiki/X") == "secondary"
    assert source_authority("https://someblog.com/x") == "secondary"


def test_mechanical_critical_on_schema_break():
    d = load_seed()
    assert not [f for f in _mechanical_findings(d) if f.severity == "critical"]  # valid seed
    d["products"][0]["status"] = "frozen"  # bad enum
    assert any(f.severity == "critical" and f.kind == "schema" for f in _mechanical_findings(d))


def test_mechanical_flags_non_official_source():
    seed = load_seed()
    d = {"_meta": {"as_of": "2026-06-16"}, "capabilities": seed["capabilities"], "products": [{
        "id": "x", "name": "X", "kind": "product", "provider": "OpenAI",
        "capability_ids": ["agentic-coding"], "primary_capability_id": "agentic-coding",
        "relation_within_capability": "direct", "status": "active",
        "source": {"url": "https://randomblog.com/x", "last_verified": "2026-06-16", "confidence": "low"},
    }]}
    assert any(f.kind == "source" and f.record_id == "x" for f in _mechanical_findings(d))


def test_gate_blocks_on_critical():
    passed, reasons = gate(load_seed(), [Finding("critical", "existence", "x", "gone")], {"passed": True})
    assert not passed and any("critical" in r for r in reasons)


def test_gate_blocks_on_eval_fail():
    passed, reasons = gate(load_seed(), [], {"passed": False})
    assert not passed and any("eval" in r for r in reasons)


def test_gate_passes_when_clean():
    passed, reasons = gate(load_seed(), [Finding("warning", "source", "x", "weak")], {"passed": True})
    assert passed and reasons == []


def test_audit_mechanical_only_runs_without_llm():
    findings = audit_catalog(load_seed(), None, None)
    assert all(f.kind in ("schema", "source", "staleness", "coverage_gap") for f in findings)


def _prod(pid, provider, cap, status="active"):
    return {"id": pid, "name": pid, "kind": "product", "provider": provider,
            "capability_ids": [cap], "primary_capability_id": cap,
            "relation_within_capability": "direct" if status != "absent" else "none",
            "status": status,
            "source": {"url": f"https://x/{pid}", "last_verified": "2026-06-17", "confidence": "high"}}


def test_triangulate_skips_absent_records():
    absent = _prod("none", "Anthropic", "image-video-generation", status="absent")
    assert _triangulate(absent, None, None) is None   # absent check is first; never touches llm/retrieval


def test_triangulate_silence_is_unconfirmed_warning_not_critical_existence():
    rec = _prod("x", "OpenAI", "agentic-coding")
    rec["name"] = "Codex managed agents"
    rec["source"]["url"] = "https://platform.openai.com/docs/x"   # official primary, different host from 2nd
    llm = StubLLM({f"audit:{rec['id']}": {
        "supported": False, "confidence": "low", "found_quote": "",
        "lifecycle_status": "unknown", "rationale": "page doesn't mention it"}})
    f = _triangulate(rec, llm, _OneSourceRetrieval())
    assert f is not None and f.severity == "warning" and f.kind == "unconfirmed"   # silence ≠ doesn't exist


def test_coverage_gap_flags_asymmetric_unknown_not_grounded_absence():
    seed = load_seed()
    # all three providers exist in the catalog (via flagship-model); only Anthropic on agentic-coding
    cat = {"_meta": {"as_of": "2026-06-17"}, "capabilities": seed["capabilities"], "products": [
        _prod("a", "Anthropic", "agentic-coding"),
        _prod("o", "OpenAI", "flagship-model"),
        _prod("g", "Google", "flagship-model")]}
    gaps = [f for f in _coverage_findings(cat) if f.kind == "coverage_gap" and "agentic-coding" in f.message]
    assert any("OpenAI" in f.message for f in gaps)   # peers present, OpenAI unknown → flagged
    assert any("Google" in f.message for f in gaps)
    # a grounded ABSENCE resolves the cell — no longer a gap
    cat["products"].append(_prod("x", "OpenAI", "agentic-coding", status="absent"))
    gaps2 = [f for f in _coverage_findings(cat) if f.kind == "coverage_gap" and "agentic-coding" in f.message]
    assert not any("OpenAI" in f.message for f in gaps2)   # grounded-absent ≠ unknown
    assert any("Google" in f.message for f in gaps2)       # still unknown
