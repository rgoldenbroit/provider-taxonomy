"""Gold-set reconstruction: hold out seed records, see if the pipeline recovers them.

The seed is the labeled gold set. We remove a few agentic-coding records, run
discover + triage on the remainder, and score whether the held-out records are
rediscovered (recall/precision) and classified the way the gold says
(primary capability + scope relation).
"""

from __future__ import annotations

import copy

from ..discover import _norm, discover
from ..retrieval.base import RetrievalProvider
from ..triage import triage_one
from ..vertex_client import LLMClient

DEFAULT_HOLDOUT = ["anthropic-claude-code", "google-jules"]


def run_gold(seed: dict, *, llm: LLMClient, retrieval: RetrievalProvider,
             capability: str = "agentic-coding", holdout: list[str] | None = None) -> dict:
    holdout = holdout or DEFAULT_HOLDOUT
    gold_by_norm = {_norm(p["name"]): p for p in seed["products"] if p["id"] in holdout}

    reduced = copy.deepcopy(seed)
    reduced["products"] = [p for p in reduced["products"] if p["id"] not in holdout]

    candidates = discover(capability, llm=llm, retrieval=retrieval, dataset=reduced)
    recovered = {_norm(c.record["name"]) for c in candidates}
    want = set(gold_by_norm)

    true_positives = len(recovered & want)
    recall = true_positives / len(want) if want else 1.0
    precision = true_positives / len(recovered) if recovered else 0.0

    primary_ok = relation_ok = scored = 0
    mistakes: list[dict] = []
    for c in candidates:
        gold = gold_by_norm.get(_norm(c.record["name"]))
        if not gold:
            continue
        outcome = triage_one(c.record, dataset=reduced, llm=llm, retrieval=retrieval)
        scored += 1
        got_primary = outcome.record["primary_capability_id"]
        got_relation = outcome.record["relation_within_capability"]
        if got_primary == gold["primary_capability_id"]:
            primary_ok += 1
        else:
            mistakes.append({"id": gold["id"], "field": "primary",
                             "got": got_primary, "want": gold["primary_capability_id"]})
        if got_relation == gold["relation_within_capability"]:
            relation_ok += 1
        else:
            mistakes.append({"id": gold["id"], "field": "relation",
                             "got": got_relation, "want": gold["relation_within_capability"]})

    return {
        "holdout": holdout,
        "recovered": sorted(recovered),
        "discovery_recall": round(recall, 3),
        "discovery_precision": round(precision, 3),
        "classification_primary_accuracy": round(primary_ok / scored, 3) if scored else None,
        "classification_relation_accuracy": round(relation_ok / scored, 3) if scored else None,
        "scored": scored,
        "mistakes": mistakes,
    }
