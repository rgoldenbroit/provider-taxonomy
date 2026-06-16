"""Phase 4 tests: gold-set reconstruction, adversarial grounding, dataset metrics."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.evals import run_all  # noqa: E402
from taxonomy.fixtures import load_llm_fixtures  # noqa: E402
from taxonomy.metrics import dataset_metrics  # noqa: E402
from taxonomy.retrieval.fixtures import FixtureRetrieval  # noqa: E402
from taxonomy.schema import load_dataset, load_seed  # noqa: E402
from taxonomy.staleness import is_stale  # noqa: E402
from taxonomy.evals.adversarial import run_adversarial  # noqa: E402
from taxonomy.evals.gold import run_gold  # noqa: E402
from taxonomy.vertex_client import StubLLM  # noqa: E402


def _llm() -> StubLLM:
    return StubLLM(responses=load_llm_fixtures())


def test_gold_reconstruction_recovers_holdout():
    gold = run_gold(load_seed(), llm=_llm(), retrieval=FixtureRetrieval())
    assert gold["discovery_recall"] == 1.0
    assert gold["discovery_precision"] == 1.0
    assert gold["classification_primary_accuracy"] == 1.0
    assert gold["classification_relation_accuracy"] == 1.0
    assert gold["mistakes"] == []


def test_adversarial_admits_nothing():
    adv = run_adversarial(load_seed(), llm=_llm(), retrieval=FixtureRetrieval())
    assert adv["false_admit_rate"] == 0.0
    assert {r["decision"] for r in adv["results"]} == {"rejected"}


def test_dataset_metrics_on_seed():
    m = dataset_metrics(load_seed())
    assert m["schema_conformance"] == 1.0
    assert m["provenance_completeness"] == 1.0  # every seed product cites a source
    assert m["products"] == 35


def test_staleness_flags_overdue_low_confidence():
    # low-confidence interval is 21 days; verified 30 days before as_of → stale.
    product = {"source": {"last_verified": "2026-05-16", "confidence": "low"}}
    assert is_stale(product, "2026-06-15")
    fresh = {"source": {"last_verified": "2026-06-10", "confidence": "low"}}
    assert not is_stale(fresh, "2026-06-15")


def test_run_all_passes_all_gates():
    report = run_all(load_seed(), load_dataset())
    assert report["passed"] is True
    assert all(report["gates"].values())
