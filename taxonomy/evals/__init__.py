"""Eval harness: gold-set reconstruction + adversarial grounding, plus thresholds.

Evals run deterministically against fixtures with the offline stub, so they work
with no GCP credentials and gate the pipeline the same way every run.
"""

from __future__ import annotations

from ..fixtures import load_llm_fixtures
from ..metrics import dataset_metrics
from ..retrieval.fixtures import FixtureRetrieval
from ..vertex_client import StubLLM
from .adversarial import run_adversarial
from .gold import run_gold

# Regression thresholds; a run "passes" only if every gate holds.
THRESHOLDS = {
    "schema_conformance": 1.0,
    "discovery_recall": 0.9,
    "classification_primary_accuracy": 0.9,
    "false_admit_rate": 0.0,
}


def run_all(seed: dict, dataset: dict) -> dict:
    llm = StubLLM(responses=load_llm_fixtures())
    retrieval = FixtureRetrieval()
    gold = run_gold(seed, llm=llm, retrieval=retrieval)
    adversarial = run_adversarial(seed, llm=llm, retrieval=retrieval)
    metrics = dataset_metrics(dataset)

    flat = {
        "schema_conformance": metrics["schema_conformance"],
        "discovery_recall": gold["discovery_recall"],
        "classification_primary_accuracy": gold["classification_primary_accuracy"] or 0.0,
        "false_admit_rate": adversarial["false_admit_rate"],
    }
    gates = {k: (flat[k] >= thr if k != "false_admit_rate" else flat[k] <= thr)
             for k, thr in THRESHOLDS.items()}
    return {
        "gold": gold,
        "adversarial": adversarial,
        "dataset_metrics": metrics,
        "gates": gates,
        "passed": all(gates.values()),
    }
