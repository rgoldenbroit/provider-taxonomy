"""Adversarial grounding: fabricated offerings must be rejected, never admitted.

Two failure modes: a source URL that cannot be fetched (no evidence at all), and a
fetchable page that does not substantiate the claim (judge says unsupported). The
grounding gate must reject both — ``false_admit_rate`` should be 0.
"""

from __future__ import annotations

from ..retrieval.base import RetrievalProvider
from ..triage import triage_one
from ..vertex_client import LLMClient

PHANTOMS = [
    {
        "id": "openai-phantomcoder", "name": "PhantomCoder", "kind": "product",
        "provider": "OpenAI", "capability_ids": ["agentic-coding"],
        "primary_capability_id": "agentic-coding", "relation_within_capability": "direct",
        "status": "active", "review_status": "candidate", "surfaces": ["cloud"],
        "scope_note": "A coding agent that does not exist; its URL cannot be fetched.",
        "lifecycle": [],
        "source": {"url": "https://example.com/phantom", "last_verified": "2026-06-15", "confidence": "low"},
    },
    {
        "id": "openai-fakeforge", "name": "FakeForge", "kind": "product",
        "provider": "OpenAI", "capability_ids": ["agentic-coding"],
        "primary_capability_id": "agentic-coding", "relation_within_capability": "direct",
        "status": "active", "review_status": "candidate", "surfaces": ["cloud"],
        "scope_note": "A fabricated agent whose cited page is real but about Codex, not FakeForge.",
        "lifecycle": [],
        "source": {"url": "https://openai.com/index/codex", "last_verified": "2026-06-15", "confidence": "low"},
    },
]


def run_adversarial(seed: dict, *, llm: LLMClient, retrieval: RetrievalProvider) -> dict:
    results = []
    false_admits = 0
    for phantom in PHANTOMS:
        outcome = triage_one(phantom, dataset=seed, llm=llm, retrieval=retrieval)
        results.append({"id": phantom["id"], "decision": outcome.decision,
                        "grounding": round(outcome.report.grounding.score, 2)})
        if outcome.decision == "confirmed":
            false_admits += 1
    return {
        "cases": len(PHANTOMS),
        "false_admits": false_admits,
        "false_admit_rate": round(false_admits / len(PHANTOMS), 3),
        "results": results,
    }
