"""Phase 2 tests: discovery + dedup (offline, deterministic via fixtures)."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.discover import discover  # noqa: E402
from taxonomy.fixtures import load_llm_fixtures  # noqa: E402
from taxonomy.retrieval.fixtures import FixtureRetrieval  # noqa: E402
from taxonomy.schema import load_seed  # noqa: E402
from taxonomy.validate import load_schema, validate_instance  # noqa: E402
from taxonomy.vertex_client import StubLLM  # noqa: E402

_PRODUCT_SCHEMA = {"$ref": "#/$defs/product"}


def _llm() -> StubLLM:
    return StubLLM(responses=load_llm_fixtures())


def _retrieval() -> FixtureRetrieval:
    return FixtureRetrieval()


def _remove(dataset: dict, *ids: str) -> dict:
    d = copy.deepcopy(dataset)
    d["products"] = [p for p in d["products"] if p["id"] not in ids]
    return d


def test_full_seed_yields_no_new_candidates():
    # Every agentic-coding offering in the fixtures already exists in the seed.
    cands = discover("agentic-coding", llm=_llm(), retrieval=_retrieval(), dataset=load_seed())
    assert cands == [], [c.record["id"] for c in cands]


def test_holding_out_a_product_rediscovers_it():
    dataset = _remove(load_seed(), "anthropic-claude-code")
    cands = discover("agentic-coding", llm=_llm(), retrieval=_retrieval(), dataset=dataset)
    names = {c.record["name"] for c in cands}
    assert names == {"Claude Code"}, names


def test_candidate_records_conform_to_product_schema():
    dataset = _remove(load_seed(), "anthropic-claude-code", "google-jules")
    cands = discover("agentic-coding", llm=_llm(), retrieval=_retrieval(), dataset=dataset)
    assert len(cands) == 2
    schema = load_schema()
    for c in cands:
        issues = validate_instance(c.record, _PRODUCT_SCHEMA, root=schema)
        assert issues == [], "\n".join(str(i) for i in issues)
        assert c.record["review_status"] == "candidate"
        assert c.record["source"]["confidence"] == "low"
        assert c.evidence  # grounding evidence captured for the trust gate


def test_candidate_ids_are_kebab_and_unique():
    dataset = _remove(load_seed(), "openai-codex", "openai-codex-cli")
    cands = discover("agentic-coding", llm=_llm(), retrieval=_retrieval(), dataset=dataset)
    ids = [c.record["id"] for c in cands]
    assert ids == ["openai-codex", "openai-codex-cli"]
    assert len(set(ids)) == len(ids)


def test_within_run_dedup_across_providers():
    # Removing several products still yields one candidate per offering (no dupes).
    dataset = _remove(load_seed(), "google-antigravity", "google-antigravity-cli",
                      "google-jules", "google-gemini-cli")
    cands = discover("agentic-coding", llm=_llm(), retrieval=_retrieval(), dataset=dataset)
    ids = [c.record["id"] for c in cands]
    assert sorted(ids) == sorted(set(ids))
    assert {c.record["name"] for c in cands} == {
        "Antigravity 2.0", "Antigravity CLI", "Jules", "Gemini CLI"}
