"""Tests for the ranking + completeness steps (offline stub)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.rank import RANK_SCHEMA, completeness_critic, rank_flagship  # noqa: E402
from taxonomy.validate import validate_instance  # noqa: E402
from taxonomy.vertex_client import StubLLM  # noqa: E402


def test_rank_flagship_returns_choice():
    llm = StubLLM(responses={"rank:Google": {"flagship_name": "Gemini 3.5 Pro", "rationale": "most capable GA"}})
    out = rank_flagship("Google", [{"name": "Gemini 3.5 Pro"}, {"name": "Gemini 3.5 Flash"}], llm)
    assert out["flagship_name"] == "Gemini 3.5 Pro"


def test_completeness_critic_returns_missing():
    llm = StubLLM(responses={"complete:Google:Agentic coding": {
        "missing": [{"name": "Antigravity", "why": "agent-first coding platform"}]}})
    out = completeness_critic("Google", "Agentic coding", ["Jules"], llm)
    assert out["missing"][0]["name"] == "Antigravity"


def test_rank_flagship_stub_default_is_schema_valid():
    out = rank_flagship("X", [{"name": "A"}], StubLLM())
    assert validate_instance(out, RANK_SCHEMA) == []
