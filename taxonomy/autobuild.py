"""Autonomous catalog build: Tavily discovery, looped until completeness is dry.

For each capability: a broad discovery sweep, then completeness-critic-driven
targeted searches for whatever's still missing, round after round, until the
critic reports no gaps (or max_rounds). Single-source grounding here (fast); the
audit pass triangulates afterward. Replaces the hand-curated candidate list.
"""

from __future__ import annotations

import copy
import re
from typing import Callable

from .discover import PROVIDERS, _kebab, dedup_key, discover, is_duplicate
from .rank import completeness_critic
from .retrieval.base import RetrievalError
from .triage import _VALID_SURFACES, admissibility, triage_one

_AS_OF = "2026-06-16"
_GAPS_PER_PROVIDER = 2  # bound the loop's fan-out per round


def _candidate_record(cap: str, provider: str, name: str, url: str, summary: str = "") -> dict:
    return {
        "id": _kebab(provider, name), "name": name, "kind": "product", "provider": provider,
        "capability_ids": [cap], "primary_capability_id": cap,
        "relation_within_capability": "direct", "surfaces": [], "status": "active",
        "review_status": "candidate", "scope_note": summary, "lifecycle": [],
        "source": {"url": url, "last_verified": _AS_OF, "confidence": "low"},
    }


# Access-surface and stop words carry no product identity, so they don't count as
# a shared token between a candidate and its claimed parent.
_GENERIC_TOKENS = {"sdk", "cli", "api", "app", "ide", "extension", "plugin",
                   "integration", "for", "the", "in", "and", "to", "of"}


def _distinctive_tokens(provider: str, name: str) -> set[str]:
    provider_words = {w for w in provider.lower().split() if len(w) > 2}
    words = re.findall(r"[a-z0-9]+", name.lower())
    return {w for w in words if len(w) > 1 and w not in _GENERIC_TOKENS and w not in provider_words}


def _shares_distinctive_token(record: dict, parent: dict) -> bool:
    """A real access surface names its parent ('Antigravity CLI' → Antigravity). If the
    candidate and the claimed parent share no product-identity token, the LLM picked the
    wrong parent (e.g. 'Gemini CLI' → Antigravity) and we must NOT fold."""
    a = _distinctive_tokens(record.get("provider", ""), record.get("name", ""))
    b = _distinctive_tokens(parent.get("provider", ""), parent.get("name", ""))
    return bool(a & b)


def _find_parent(catalog: dict, parent_id: str | None, record: dict) -> dict | None:
    """Locate the parent product a surface attaches to: exact id, else same-provider id overlap."""
    if not parent_id:
        return None
    products = catalog.get("products", [])
    for p in products:
        if p["id"] == parent_id:
            return p
    for p in products:  # tolerate slug drift from the LLM
        if p.get("provider") == record.get("provider") and (
                p["id"].startswith(parent_id) or parent_id.startswith(p["id"])):
            return p
    return None


def _fold_surface(parent: dict, access_surfaces, name: str) -> None:
    """Fold an access-surface candidate into its parent: merge surfaces, note the access path."""
    surfaces = parent.setdefault("surfaces", [])
    for s in access_surfaces or []:
        if s in _VALID_SURFACES and s not in surfaces:
            surfaces.append(s)
    note = parent.get("scope_note", "") or ""
    mention = f"Accessible via {name}."
    if name and mention not in note:
        parent["scope_note"] = f"{note} {mention}".strip()


def _try_admit(catalog, cap, record, evidence, llm, retrieval, found, counts, log) -> None:
    key = dedup_key(record["provider"], record["name"])
    if not key or is_duplicate(key, found):
        return
    # node-worthiness: a pure access surface (an X SDK/CLI for an already-listed X)
    # folds into its parent instead of earning its own node.
    verdict = admissibility(record, dataset=catalog, llm=llm)
    if verdict.get("verdict") == "surface":
        parent = _find_parent(catalog, verdict.get("parent_id"), record)
        if parent is not None and _shares_distinctive_token(record, parent):
            _fold_surface(parent, verdict.get("access_surfaces", []), record["name"])
            counts["folded_surface"] = counts.get("folded_surface", 0) + 1
            log(f"    FOLD(surface) {record['id']:34} → {parent['id']}")
            found.add(key)
            return
        # no real parent (absent, or LLM named the wrong one) → admit as its own node; audit re-flags it.
    outcome = triage_one(record, dataset=catalog, llm=llm, retrieval=retrieval,
                         evidence=evidence, pinned_capability=cap)
    # granularity: a base model belongs only in flagship-model, not a product capability
    if outcome.record.get("kind") in ("model", "model_family") and cap != "flagship-model":
        counts["skipped_model"] = counts.get("skipped_model", 0) + 1
        log(f"    SKIP(model)   {outcome.record['id']}")
        return
    counts[outcome.decision] = counts.get(outcome.decision, 0) + 1
    log(f"    {outcome.decision.upper():12} {outcome.record['id']:34} [g {outcome.report.grounding.score:.2f}]")
    if outcome.decision in ("confirmed", "needs_review"):
        catalog["products"].append(outcome.record)
        found.add(key)


def _search_candidate(cap: str, provider: str, name: str, retrieval):
    try:
        results = retrieval.search(f"{provider} {name} 2026", max_results=4)
    except (RetrievalError, NotImplementedError):
        return None
    if not results:
        return None
    return _candidate_record(cap, provider, name, results[0].url, results[0].snippet)


def _autobuild_capability(catalog, cap, llm, retrieval, providers, max_rounds, log) -> None:
    found: set[str] = set()
    cap_name = next((c["name"] for c in catalog["capabilities"] if c["id"] == cap), cap)

    log(f"  [{cap}] round 1 — broad discovery")
    counts: dict[str, int] = {}
    try:
        candidates = discover(cap, llm=llm, retrieval=retrieval, dataset=catalog, providers=providers)
    except (RetrievalError, NotImplementedError) as exc:
        log(f"    discovery unavailable: {exc}")
        candidates = []
    for c in candidates:
        _try_admit(catalog, cap, c.record, c.evidence, llm, retrieval, found, counts, log)

    for rnd in range(2, max_rounds + 1):
        gaps: list[tuple[str, str]] = []
        for provider in providers:
            have = [p["name"] for p in catalog["products"]
                    if p["provider"] == provider and cap in p["capability_ids"]]
            missing = completeness_critic(provider, cap_name, have, llm).get("missing", [])
            for g in missing[:_GAPS_PER_PROVIDER]:
                if not is_duplicate(dedup_key(provider, g["name"]), found):
                    gaps.append((provider, g["name"]))
        if not gaps:
            log(f"  [{cap}] complete — completeness critic dry")
            return
        log(f"  [{cap}] round {rnd} — {len(gaps)} gap(s) to chase")
        for provider, name in gaps:
            cand = _search_candidate(cap, provider, name, retrieval)
            if cand:
                _try_admit(catalog, cap, cand, "", llm, retrieval, found, counts, log)
    log(f"  [{cap}] stopped at max_rounds={max_rounds}")


def autobuild(llm, retrieval, seed: dict, *, capabilities: list[str] | None = None,
              providers: tuple[str, ...] = PROVIDERS, max_rounds: int = 2,
              log: Callable[[str], None] = print) -> dict:
    caps = capabilities or [c["id"] for c in seed["capabilities"] if c["id"] != "unclassified"]
    catalog = {
        "_meta": {"description": "Autonomously built grounded catalog (Tavily discovery + loop-until-dry).",
                  "as_of": _AS_OF, "conforms_to": "schema.json"},
        "capabilities": copy.deepcopy(seed["capabilities"]), "products": [],
    }
    for cap in caps:
        _autobuild_capability(catalog, cap, llm, retrieval, providers, max_rounds, log)
    return catalog
