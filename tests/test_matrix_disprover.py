"""Adversarial-absence gate (disprover) tests — offline StubLLM, no creds.

A cell the mapper + reconsider both miss is about to become a gap. The disprover must try to refute that
absence from the lineup; any hit it finds must still pass the SAME confirm gate before it grounds. These
pin the three terminal states: recovered, vetoed-by-confirm, and earned-absent.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build_matrix import select_provider, _incumbent_feature  # noqa: E402
from taxonomy.vertex_client import StubLLM  # noqa: E402

FEATS = [
    {"id": "rewind-feat", "name": "Session resumption for rewind",
     "scope_note": "Roll the session back to a prior checkpoint.", "status": "active",
     "source": {"url": "https://code.claude.com/docs/x", "last_verified": "2026-06-26"}},
    {"id": "noise-feat", "name": "Telemetry export",
     "scope_note": "Emit OpenTelemetry spans.", "status": "active",
     "source": {"url": "https://code.claude.com/docs/y", "last_verified": "2026-06-26"}},
]
ROWS = [{"id": "checkpoint-rewind", "name": "Checkpoint / rewind",
         "what": "Roll the agent back to a prior state."}]

# map + reconsider both find nothing -> the cell reaches the disprover as a would-be gap.
_GAP = {
    "matrixmap:anthropic": {"mappings": [{"capability_id": "checkpoint-rewind", "matched": False, "feature_index": 0}]},
    "matrixreconsider:anthropic": {"repicks": [{"capability_id": "checkpoint-rewind", "feature_index": 0}]},
}


def _run(extra):
    llm = StubLLM({**_GAP, **extra})
    sel, diag = select_provider(llm, "anthropic", "Anthropic", "Claude Code", FEATS, ROWS)
    return sel, diag, llm


def test_disprover_recovers_false_gap():
    # disprover refutes the gap (picks feat 1); confirm admits it -> the cell grounds on the real feature.
    sel, _, llm = _run({
        "matrixdisprove:anthropic": {"repicks": [{"capability_id": "checkpoint-rewind", "feature_index": 1}]},
        "matrixconfirm:anthropic": {"confirmations": [{"capability_id": "checkpoint-rewind", "realizes": True, "reason": "direct match"}]},
    })
    assert sel["checkpoint-rewind"] is not None, "disprover hit + confirm pass should ground the cell"
    assert sel["checkpoint-rewind"]["name"] == "Session resumption for rewind"
    assert any(c["label"] == "matrixdisprove:anthropic" for c in llm.calls), "disprover must run on the gap"


def test_confirm_vetoes_disprover_hit():
    # disprover picks a feature but confirm rejects it -> NOT grounded (precision preserved), reason logged.
    sel, diag, _ = _run({
        "matrixdisprove:anthropic": {"repicks": [{"capability_id": "checkpoint-rewind", "feature_index": 2}]},
        "matrixconfirm:anthropic": {"confirmations": [{"capability_id": "checkpoint-rewind", "realizes": False, "reason": "telemetry, not rewind"}]},
    })
    assert sel["checkpoint-rewind"] is None, "confirm veto must keep the disprover hit out of the catalog"
    assert "confirm rejected" in diag["checkpoint-rewind"]


def test_true_absence_stays_gap():
    # disprover finds nothing (index 0) -> the gap is earned, and confirm is never called for this cell.
    sel, _, llm = _run({
        "matrixdisprove:anthropic": {"repicks": [{"capability_id": "checkpoint-rewind", "feature_index": 0}]},
    })
    assert sel["checkpoint-rewind"] is None
    assert not any(c["label"] == "matrixconfirm:anthropic" for c in llm.calls), "no confirm when disprover abstains"


# --- sticky projection: a still-valid incumbent is kept; a vanished one re-decides ------------------
_LINEUP = [
    {"name": "Custom Agents", "source": {"url": "https://x/agents", "last_verified": "2026-06-27"}, "status": "active"},
    {"name": "Guardrails", "source": {"url": "https://x/guard", "last_verified": "2026-06-27"}, "status": "active"},
]


def test_sticky_incumbent_still_present_is_kept():
    # the cell's last-published feature still exists -> sticky returns it (so an unrelated add can't churn it).
    f = _incumbent_feature(_LINEUP, "Custom Agents", "https://x/agents")
    assert f is not None and f["name"] == "Custom Agents"


def test_sticky_url_breaks_ties_but_name_is_enough():
    # name match alone is sufficient (a url refresh shouldn't drop the incumbent).
    assert _incumbent_feature(_LINEUP, "Guardrails", "https://x/STALE")["name"] == "Guardrails"


def test_sticky_vanished_incumbent_returns_none():
    # renamed/removed feature -> no match -> None, which lets the cell re-decide (a real change flows through).
    assert _incumbent_feature(_LINEUP, "Personas (was Custom Agents)", "") is None
