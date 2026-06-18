"""Reliable per-(provider × axis) coverage resolution.

Resolves a coverage cell to **present** (grounded) or **unknown** — never to a
false absence. Misses are rare by construction:

- **official-source-first**: each cell is searched against the provider's own docs
  (``include_domains``) before the open web, so the authoritative page is found;
- **multi-query**: several phrasings per cell, candidates pooled and official-first;
- **grounded admission**: every candidate is run through the trust pipeline; a cell
  becomes ``present`` only when a page substantiates it, else stays ``unknown``.

This is the discovery half of the "no manual second pass" loop (see ``research.md``).
"""

from __future__ import annotations

from .discover import _kebab
from .retrieval.base import RetrievalError
from .sources import OFFICIAL_DOMAINS, source_tier  # canonical source-tier definitions
from .triage import triage_one

_AS_OF = "2026-06-17"


def _is_official(url: str, provider: str) -> bool:
    return source_tier(url, provider) == "official"


def _candidate(provider: str, axis_id: str, name: str, url: str, summary: str) -> dict:
    return {
        "id": _kebab(provider, f"{name} {axis_id}"),
        "name": name, "kind": "feature", "provider": provider,
        "capability_ids": [axis_id], "primary_capability_id": axis_id,
        "relation_within_capability": "direct", "surfaces": [], "status": "active",
        "review_status": "candidate", "scope_note": (summary or "")[:280], "lifecycle": [],
        "source": {"url": url, "last_verified": _AS_OF, "confidence": "low"},
    }


def _queries(provider: str, axis_name: str, keywords: str):
    """Official-docs-scoped queries first, then an open-web fallback."""
    dom = OFFICIAL_DOMAINS.get(provider)
    return [
        (f"{provider} {axis_name} {keywords}", dom),
        (f"{provider} {axis_name} {keywords} documentation", dom),
        (f"{provider} {axis_name} {keywords} 2026", None),
    ]


def gather_candidates(provider: str, axis_name: str, keywords: str, retrieval, *, per: int = 3):
    seen: set[str] = set()
    cands = []
    for query, domains in _queries(provider, axis_name, keywords):
        try:
            results = retrieval.search(query, max_results=per, include_domains=domains)
        except (RetrievalError, NotImplementedError):
            results = []
        for r in results:
            if r.url and r.url not in seen:
                seen.add(r.url)
                cands.append(r)
    cands.sort(key=lambda r: 0 if _is_official(r.url, provider) else 1)   # official first
    return cands


def find_offering(provider: str, axis_id: str, axis_name: str, keywords: str, *,
                  dataset: dict, llm, retrieval, name: str | None = None,
                  max_candidates: int = 3):
    """Resolve one (provider × axis) cell. Returns a grounded `present` record, or None (unknown)."""
    fname = name or f"{provider} {axis_name}"
    for c in gather_candidates(provider, axis_name, keywords, retrieval)[:max_candidates]:
        rec = _candidate(provider, axis_id, fname, c.url, c.snippet)
        try:
            outcome = triage_one(rec, dataset=dataset, llm=llm, retrieval=retrieval,
                                 evidence=fname, pinned_capability=axis_id)
        except (RetrievalError, NotImplementedError):
            continue
        if outcome.decision in ("confirmed", "needs_review"):
            r = outcome.record
            r["primary_capability_id"], r["capability_ids"] = axis_id, [axis_id]  # keep it on its axis
            r.pop("parent_id", None)   # axis-level offering; not forced under a coding product
            return r, c.url
    return None, None
