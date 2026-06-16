"""Node-worthiness / admissibility tests (deterministic; canned StubLLM, no network).

Covers the new pieces of the self-maintaining pipeline:
- `admissibility` returns the model's verdict and excludes the record itself as a parent.
- `_fold_surface` / `_find_parent` (pure helpers).
- `_try_admit` routing: a `surface` verdict folds into its parent; a `node` verdict admits.
- audit `_node_worthiness_findings`: surface → warning, ambiguous → info, node → none.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.audit import _node_worthiness_findings  # noqa: E402
from taxonomy.autobuild import (  # noqa: E402
    _candidate_record,
    _find_parent,
    _fold_surface,
    _shares_distinctive_token,
    _try_admit,
)
from taxonomy.retrieval.base import FetchedPage, RetrievalProvider, content_hash  # noqa: E402
from taxonomy.schema import load_seed  # noqa: E402
from taxonomy.triage import admissibility  # noqa: E402
from taxonomy.vertex_client import StubLLM  # noqa: E402


class _StubRetrieval(RetrievalProvider):
    """Returns one canned page for any fetch; search is unused by these tests."""

    def __init__(self, text: str):
        self._text = text

    def search(self, query: str, *, max_results: int = 8):
        return []

    def fetch(self, url: str) -> FetchedPage:
        return FetchedPage(url=url, status=200, text=self._text, content_hash=content_hash(self._text))


def _parent_product() -> dict:
    return {
        "id": "google-antigravity", "name": "Antigravity", "kind": "product", "provider": "Google",
        "capability_ids": ["agentic-coding"], "primary_capability_id": "agentic-coding",
        "relation_within_capability": "direct", "surfaces": ["ide"], "status": "active",
        "review_status": "confirmed", "scope_note": "Google's agentic IDE.", "lifecycle": [],
        "source": {"url": "https://antigravity.google/", "last_verified": "2026-06-16", "confidence": "high"},
    }


def _catalog_with_parent() -> dict:
    seed = load_seed()
    return {"_meta": {"as_of": "2026-06-16"}, "capabilities": seed["capabilities"],
            "products": [_parent_product()]}


# --- admissibility ---------------------------------------------------------- #

def test_admissibility_returns_verdict_and_excludes_self():
    cat = _catalog_with_parent()
    record = cat["products"][0]  # the record is already in the catalog
    llm = StubLLM({f"admit:{record['id']}": {"verdict": "node", "rationale": "distinct axis"}})
    out = admissibility(record, cat, llm)
    assert out["verdict"] == "node"
    # the record must not be offered as a parent of itself
    assert record["id"] not in llm.calls[-1]["prompt"].split("EXISTING CATALOG NODES")[1]


# --- pure helpers ----------------------------------------------------------- #

def test_fold_surface_merges_valid_surfaces_and_notes():
    parent = _parent_product()
    _fold_surface(parent, ["cli", "terminal", "ide"], "Antigravity CLI")  # "cli" is not a valid surface
    assert "terminal" in parent["surfaces"]
    assert parent["surfaces"].count("ide") == 1            # no duplicate
    assert "cli" not in parent["surfaces"]                 # invalid surface dropped
    assert "Accessible via Antigravity CLI." in parent["scope_note"]


def test_fold_surface_is_idempotent():
    parent = _parent_product()
    _fold_surface(parent, ["terminal"], "Antigravity CLI")
    note_once = parent["scope_note"]
    _fold_surface(parent, ["terminal"], "Antigravity CLI")
    assert parent["scope_note"] == note_once               # mention not appended twice
    assert parent["surfaces"].count("terminal") == 1


def test_find_parent_exact_and_prefix_and_miss():
    cat = _catalog_with_parent()
    rec = {"provider": "Google"}
    assert _find_parent(cat, "google-antigravity", rec) is cat["products"][0]      # exact id
    assert _find_parent(cat, "google-antigravity-cli", rec) is cat["products"][0]  # prefix (slug drift)
    assert _find_parent(cat, "openai-codex", {"provider": "OpenAI"}) is None       # no match
    assert _find_parent(cat, "", rec) is None                                      # empty id


def test_shares_distinctive_token_guards_wrong_parent():
    anti = _parent_product()  # Google Antigravity
    code = {"provider": "Anthropic", "name": "Claude Code"}
    # real access surfaces name their parent
    assert _shares_distinctive_token({"provider": "Google", "name": "Antigravity CLI"}, anti)
    assert _shares_distinctive_token({"provider": "Google", "name": "Antigravity SDK"}, anti)
    assert _shares_distinctive_token({"provider": "Anthropic", "name": "Claude Agent SDK"}, code)
    # wrong-parent picks share no product token → must not fold
    assert not _shares_distinctive_token({"provider": "Google", "name": "Gemini CLI"}, anti)
    assert not _shares_distinctive_token({"provider": "Google", "name": "AI Studio"}, anti)


# --- routing in _try_admit -------------------------------------------------- #

def test_try_admit_folds_surface_into_parent():
    cat = _catalog_with_parent()
    cand = _candidate_record("agentic-coding", "Google", "Antigravity CLI",
                             "https://antigravity.google/cli", "CLI access to Antigravity.")
    llm = StubLLM({f"admit:{cand['id']}": {
        "verdict": "surface", "parent_id": "google-antigravity",
        "access_surfaces": ["terminal"], "rationale": "CLI is an access surface of Antigravity"}})
    found, counts = set(), {}
    _try_admit(cat, "agentic-coding", cand, "", llm, _StubRetrieval(""), found, counts, log=lambda *_: None)

    assert len(cat["products"]) == 1                       # NOT admitted as its own node
    assert "terminal" in cat["products"][0]["surfaces"]    # folded into the parent
    assert counts.get("folded_surface") == 1
    assert found                                           # key recorded so it won't be re-chased


def test_try_admit_does_not_fold_wrong_parent():
    cat = _catalog_with_parent()  # only Antigravity present
    cand = _candidate_record("agentic-coding", "Google", "Gemini CLI",
                             "https://google.dev/gemini-cli", "Command-line agent for Gemini.")
    page = "Gemini CLI is Google's open-source command-line agent."
    llm = StubLLM({
        # LLM wrongly calls it a surface of Antigravity
        f"admit:{cand['id']}": {"verdict": "surface", "parent_id": "google-antigravity",
                                "access_surfaces": ["terminal"], "rationale": "guessed wrong parent"},
        f"triage:{cand['id']}": {
            "capability_ids": ["agentic-coding"], "primary_capability_id": "agentic-coding",
            "relation_within_capability": "direct", "kind": "product", "surfaces": ["terminal"],
            "confidence": "high", "rationale": "distinct CLI agent"},
        f"judge:{cand['id']}": {
            "supported": True, "confidence": "high", "found_quote": "Gemini CLI",
            "lifecycle_status": "active", "rationale": "page describes it"},
    })
    found, counts = set(), {}
    _try_admit(cat, "agentic-coding", cand, "Gemini CLI", llm, _StubRetrieval(page),
               found, counts, log=lambda *_: None)

    assert "terminal" not in cat["products"][0]["surfaces"]          # NOT folded into Antigravity
    assert counts.get("folded_surface") is None
    assert any(p["name"] == "Gemini CLI" for p in cat["products"])   # admitted as its own node instead


def test_try_admit_admits_node():
    cat = _catalog_with_parent()
    cand = _candidate_record("agentic-coding", "Google", "Managed Agents",
                             "https://ai.google.dev/managed-agents", "Server-managed agent runtimes.")
    page = "Google Managed Agents provides server-managed agent runtimes for the Gemini API."
    llm = StubLLM({
        f"admit:{cand['id']}": {"verdict": "node", "rationale": "managed runtime is a distinct axis"},
        f"triage:{cand['id']}": {
            "capability_ids": ["agentic-coding"], "primary_capability_id": "agentic-coding",
            "relation_within_capability": "direct", "kind": "product", "surfaces": ["cloud"],
            "confidence": "high", "rationale": "managed agent runtime"},
        f"judge:{cand['id']}": {
            "supported": True, "confidence": "high", "found_quote": "Managed Agents",
            "lifecycle_status": "active", "rationale": "page describes it"},
    })
    found, counts = set(), {}
    _try_admit(cat, "agentic-coding", cand, "Managed Agents", llm, _StubRetrieval(page),
               found, counts, log=lambda *_: None)

    assert any(p["name"] == "Managed Agents" for p in cat["products"])  # admitted as its own node
    assert counts.get("folded_surface") is None


# --- audit node-worthiness finding ------------------------------------------ #

def test_node_worthiness_findings_severity_by_verdict():
    cat = _catalog_with_parent()
    surface = _candidate_record("agentic-coding", "Google", "Antigravity SDK",
                                "https://antigravity.google/sdk", "SDK exposing Antigravity.")
    ambiguous = _candidate_record("agentic-coding", "OpenAI", "Mystery Tool",
                                  "https://openai.com/mystery", "Unclear thing.")
    cat["products"] += [surface, ambiguous]
    llm = StubLLM({
        f"admit:{cat['products'][0]['id']}": {"verdict": "node", "rationale": "the IDE itself"},
        f"admit:{surface['id']}": {"verdict": "surface", "parent_id": "google-antigravity",
                                   "rationale": "SDK merely exposes Antigravity"},
        f"admit:{ambiguous['id']}": {"verdict": "ambiguous", "rationale": "cannot tell"},
    })
    findings = _node_worthiness_findings(cat, llm)
    by_id = {f.record_id: f for f in findings}
    assert "google-antigravity" not in by_id                       # node → no finding
    assert by_id[surface["id"]].severity == "warning"              # surface → warning
    assert by_id[ambiguous["id"]].severity == "info"               # ambiguous → info
    assert all(f.kind == "node_worthiness" for f in findings)
