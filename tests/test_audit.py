"""Audit critic + gate tests (deterministic parts; no LLM/network)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.audit import Finding, _mechanical_findings, audit_catalog, gate, source_authority  # noqa: E402
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
    assert all(f.kind in ("schema", "source", "staleness") for f in findings)
