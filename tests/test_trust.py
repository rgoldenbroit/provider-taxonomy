"""Phase 3 tests: trust gates (pure) + triage decisions (offline)."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.fixtures import load_llm_fixtures  # noqa: E402
from taxonomy.retrieval.base import FetchedPage  # noqa: E402
from taxonomy.retrieval.fixtures import FixtureRetrieval  # noqa: E402
from taxonomy.schema import load_seed  # noqa: E402
from taxonomy.triage import triage_dataset, triage_one  # noqa: E402
from taxonomy.trust import (  # noqa: E402
    GateResult,
    TrustReport,
    classification_score,
    grounding_gate,
    matchkey,
)
from taxonomy.vertex_client import StubLLM  # noqa: E402


def _page(text: str) -> FetchedPage:
    return FetchedPage(url="https://x", status=200, text=text, content_hash="h")


# -- pure gate units --------------------------------------------------------- #

def test_grounding_requires_supported_and_quote_in_page():
    page = _page("Codex Cloud runs asynchronous coding tasks remotely.")
    ok = grounding_gate({}, page, {"supported": True, "found_quote": "Codex Cloud runs asynchronous coding tasks remotely."})
    assert ok.passed and ok.score == 1.0


def test_grounding_fails_when_quote_not_in_page():
    page = _page("This page is about something else entirely.")
    res = grounding_gate({}, page, {"supported": True, "found_quote": "fabricated supporting sentence"})
    assert not res.passed and res.score == 0.5  # judge claimed support but quote isn't there


def test_grounding_fails_when_unsupported_or_unfetched():
    assert not grounding_gate({}, _page("x"), {"supported": False, "found_quote": ""}).passed
    assert not grounding_gate({}, None, None).passed


def test_classification_agreement():
    agree = [{"primary_capability_id": "a", "relation_within_capability": "direct"}] * 3
    assert classification_score(agree)[0] == 1.0
    mixed = [
        {"primary_capability_id": "a", "relation_within_capability": "direct"},
        {"primary_capability_id": "b", "relation_within_capability": "partial"},
        {"primary_capability_id": "a", "relation_within_capability": "direct"},
    ]
    assert abs(classification_score(mixed)[0] - 2 / 3) < 1e-9


def test_report_decision_matrix():
    ok = GateResult("x", True, 1.0, "")
    bad = GateResult("x", False, 0.0, "")
    assert TrustReport(ok, ok, ok).decision() == "confirmed"
    assert TrustReport(ok, bad, ok).decision() == "rejected"          # grounding gate is decisive
    assert TrustReport(bad, ok, ok).decision() == "rejected"          # schema-invalid is never admitted
    assert TrustReport(ok, ok, bad).decision() == "needs_review"


def test_matchkey_normalizes_punctuation_and_case():
    assert matchkey("Codex Cloud — runs REMOTELY!") == "codex cloud runs remotely"


# -- triage integration (offline, fixtures) ---------------------------------- #

def test_seeded_candidate_triages_to_confirmed():
    dataset = load_seed()
    llm = StubLLM(responses=load_llm_fixtures())
    proposed, outcomes = triage_dataset(dataset, llm=llm, retrieval=FixtureRetrieval())
    by_id = {o.record["id"]: o for o in outcomes}
    assert "openai-codex-cloud-remote" in by_id
    outcome = by_id["openai-codex-cloud-remote"]
    assert outcome.decision == "confirmed"
    assert outcome.record["review_status"] == "confirmed"
    assert outcome.record["primary_capability_id"] == "remote-agent-control"
    # append-only: a triaged lifecycle event was added
    assert outcome.record["lifecycle"][-1]["event"] == "triaged"


def test_adversarial_unverifiable_source_is_rejected():
    # A fabricated candidate whose source URL has no fixture page → grounding fails → rejected.
    dataset = load_seed()
    phantom = {
        "id": "openai-phantomcoder", "name": "PhantomCoder", "kind": "product",
        "provider": "OpenAI", "capability_ids": ["agentic-coding"],
        "primary_capability_id": "agentic-coding", "relation_within_capability": "direct",
        "status": "active", "review_status": "candidate", "surfaces": ["cloud"],
        "scope_note": "A coding agent that does not actually exist.", "lifecycle": [],
        "source": {"url": "https://example.com/phantom", "last_verified": "2026-06-15", "confidence": "low"},
    }
    d = copy.deepcopy(dataset)
    d["products"].append(phantom)
    llm = StubLLM(responses=load_llm_fixtures())  # no judge/triage fixture for phantom
    outcome = triage_one(phantom, dataset=d, llm=llm, retrieval=FixtureRetrieval())
    assert outcome.decision == "rejected"
    assert outcome.record["review_status"] == "rejected"
