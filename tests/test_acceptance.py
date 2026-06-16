"""Phase 6 acceptance: the 16 edge cases the dataset must demonstrate (research.md §3).

Each test pins one pattern to concrete records + the invariant the engine/viewer
relies on, so a future dataset edit that breaks a pattern fails loudly.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.index import build_index  # noqa: E402
from taxonomy.schema import load_seed  # noqa: E402
from taxonomy.staleness import today_for  # noqa: E402

SEED = load_seed()
IDX = build_index(SEED)
P = IDX.products_by_id
TODAY = today_for(SEED)


def test_01_clean_trio_consumer_chat():
    chat = IDX.products_by_capability["consumer-chat-assistant"]
    assert {p["provider"] for p in chat} == {"Anthropic", "OpenAI", "Google"}
    assert all(p["relation_within_capability"] == "direct" for p in chat)


def test_02_one_to_many_agentic_coding():
    by_provider = {}
    for p in IDX.products_by_capability["agentic-coding"]:
        by_provider.setdefault(p["provider"], []).append(p)
    assert len(by_provider["Anthropic"]) < len(by_provider["Google"])  # asymmetric


def test_03_scope_broader():
    p = P["openai-codex"]
    assert p["relation_within_capability"] == "broader" and len(p["capability_ids"]) > 1


def test_04_scope_partial_multicapability():
    p = P["google-jules"]
    assert p["relation_within_capability"] == "partial"
    assert {"agentic-coding", "remote-agent-control"} <= set(p["capability_ids"])
    # appears in two pivots:
    assert p in IDX.products_by_capability["agentic-coding"]
    assert p in IDX.products_by_capability["remote-agent-control"]


def test_05_sunset_with_successor_and_future_event():
    p = P["google-gemini-cli"]
    assert p["status"] == "sunset" and p["successor_id"] == "google-antigravity-cli"
    assert any(e["date"] > TODAY for e in p["lifecycle"])  # future-dated sunset


def test_06_merged_with_successor():
    p = P["google-project-mariner"]
    assert p["status"] == "merged" and p["successor_id"] == "google-gemini-agent"


def test_07_pending_consolidation_without_status_change():
    p = P["openai-chatgpt"]
    assert p["status"] == "active"
    assert any(e["event"] == "consolidation_announced" for e in p["lifecycle"])


def test_08_absence_record():
    p = P["anthropic-image-video"]
    assert p["name"] == "(none)" and p["status"] == "absent"
    assert p["relation_within_capability"] == "none" and p["surfaces"] == []


def test_09_confidence_gradient():
    confs = {p["source"]["confidence"] for p in SEED["products"]}
    assert {"high", "medium", "low"} <= confs


def test_10_feature_inside_product():
    p = P["anthropic-claude-code-remote-control"]
    assert p["kind"] == "feature" and p["parent_id"] == "anthropic-claude-code"
    assert p["primary_capability_id"] == "remote-agent-control"  # mapped to its own capability


def test_11_sub_product():
    p = P["openai-codex-cli"]
    assert p["kind"] == "product" and p["parent_id"] == "openai-codex"


def test_12_rename_lineage_resolves():
    old, new = P["google-vertex-ai"], P["google-gemini-enterprise-agent-platform"]
    assert old["status"] == "renamed" and old["successor_id"] == new["id"]
    assert new["predecessor_id"] == old["id"]


def test_13_brand_ambiguity():
    workplace, platform = P["google-gemini-enterprise"], P["google-gemini-enterprise-agent-platform"]
    assert workplace["primary_capability_id"] != platform["primary_capability_id"]


def test_14_cross_provider_deployment():
    p = P["anthropic-claude-on-cloud-platforms"]
    assert p["kind"] == "feature" and p["relation_within_capability"] == "partial"
    assert p["primary_capability_id"] == "enterprise-agent-platform" and "parent_id" not in p


def test_15_model_family_hierarchy():
    family = P["anthropic-claude-model-family"]
    assert family["kind"] == "model_family"
    children = IDX.children_by_parent[family["id"]]
    assert children and all(c["kind"] == "model" for c in children)


def test_16_discovery_candidate_present():
    assert P["openai-codex-cloud-remote"]["review_status"] == "candidate"
