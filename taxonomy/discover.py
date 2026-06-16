"""Discovery: sweep each provider × capability for current offerings.

The capability taxonomy *is* the search plan. For each (provider, capability) we
search, fetch the candidate pages, and ask the model to extract offerings —
**grounded**: every offering must carry a ``source_url`` from the supplied pages
and a verbatim ``evidence_quote``. Extracted offerings are deduped against the
existing dataset (including rename lineage) and emitted as ``review_status:
"candidate"`` records for triage. Discovery never admits anything — triage + the
trust gates (Phase 3) decide.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .index import build_index
from .retrieval.base import RetrievalMissing, RetrievalProvider
from .vertex_client import LLMClient

PROVIDERS = ("Anthropic", "OpenAI", "Google")
_SURFACE_ENUM = ["web", "desktop", "mobile", "terminal", "ide", "extension", "cloud", "api"]
_KIND_ENUM = ["model_family", "model", "product", "feature", "platform", "protocol", "service_tier"]

EXTRACT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["offerings"],
    "properties": {
        "offerings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "provider", "kind", "source_url", "evidence_quote", "summary"],
                "properties": {
                    "name": {"type": "string"},
                    "provider": {"type": "string"},
                    "kind": {"type": "string", "enum": _KIND_ENUM},
                    "surfaces": {"type": "array", "items": {"type": "string", "enum": _SURFACE_ENUM}},
                    "source_url": {"type": "string"},
                    "evidence_quote": {"type": "string"},
                    "summary": {"type": "string"},
                },
            },
        }
    },
}

_EXTRACT_SYSTEM = (
    "You map AI-provider offerings to a capability taxonomy. Extract only offerings "
    "made by the named provider for the named capability, and only ones substantiated "
    "by the supplied pages. For each, return the exact source_url it came from and a "
    "verbatim evidence_quote copied from that page. Never invent an offering or a URL.\n\n"
    "GRANULARITY: extract the named PRODUCT or MODEL — not its individual features. A "
    "capability inside a product (an integration, a surface, a setting) is NOT its own "
    "offering unless it maps to a capability another provider could also fill (e.g. "
    "remote/async agent control, managed agent runtimes). When unsure, return the parent "
    "product, not the feature. An SDK, CLI, API, plugin, or IDE extension that merely gives "
    "developers ACCESS to an already-named product is an access surface of that product — do "
    "NOT emit it as a separate offering. Most pages describe one product; returning more than "
    "~2 offerings for one product page usually means you are over-splitting features."
)

_AS_OF = "2026-06"
_AS_OF_DATE = "2026-06-15"


@dataclass
class Candidate:
    record: dict          # schema-clean product, review_status == "candidate"
    evidence: str         # verbatim quote supporting the offering's existence
    source_query: str


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def dedup_key(provider: str, name: str) -> str:
    """Normalized key with the provider name and version numbers stripped, so
    'Google Antigravity' and 'Antigravity 2.0' collapse, while distinct products
    ('Codex' vs 'Codex CLI', 'Gemini 3.5 Pro' vs 'Flash') stay separate."""
    s = name.lower()
    for word in provider.lower().split():
        if len(word) > 2:
            s = s.replace(word, " ")
    s = re.sub(r"\b\d+(?:\.\d+)*\b", " ", s)  # drop version-like numbers (2.0, 3.5, ...)
    return re.sub(r"[^a-z0-9]+", "", s)


def is_duplicate(key: str, known: set[str]) -> bool:
    return bool(key) and key in known


def _kebab(provider: str, name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", f"{provider} {name}".lower()).strip("-")
    return slug or "candidate"


def _unique_id(base: str, taken: set[str]) -> str:
    if base not in taken:
        return base
    i = 2
    while f"{base}-{i}" in taken:
        i += 1
    return f"{base}-{i}"


def query_for(provider: str, capability_id: str, as_of: str = _AS_OF) -> str:
    return f"{provider} {capability_id} products {as_of}"


def _existing_keys(dataset: dict) -> tuple[set[str], set[str], set[str]]:
    """Return (normalized names, product ids, source urls) for dedup."""
    names: set[str] = set()
    ids: set[str] = set()
    urls: set[str] = set()
    for p in dataset.get("products", []):
        if p.get("name") and p["name"] != "(none)":
            names.add(dedup_key(p.get("provider", ""), p["name"]))
        if p.get("id"):
            ids.add(p["id"])
        src = (p.get("source") or {}).get("url")
        if src:
            urls.add(src)
    return names, ids, urls


def _extract_prompt(provider: str, capability: dict, pages: list) -> str:
    blocks = [f"PROVIDER: {provider}",
              f"CAPABILITY: {capability['name']} — {capability['description']}",
              "PAGES:"]
    for page in pages:
        blocks.append(f"\n[source_url: {page.url}]\n{page.text}")
    blocks.append("\nReturn the offerings as structured JSON.")
    return "\n".join(blocks)


def discover(capability_id: str, *, llm: LLMClient, retrieval: RetrievalProvider,
             dataset: dict, providers: tuple[str, ...] = PROVIDERS,
             as_of: str = _AS_OF) -> list[Candidate]:
    idx = build_index(dataset)
    capability = idx.capabilities_by_id[capability_id]
    known_names, known_ids, known_urls = _existing_keys(dataset)

    candidates: list[Candidate] = []
    seen_names: set[str] = set()
    used_ids = set(known_ids)

    for provider in providers:
        query = query_for(provider, capability_id, as_of)
        try:
            results = retrieval.search(query)
        except RetrievalMissing:
            continue
        pages = []
        for result in results:
            try:
                pages.append(retrieval.fetch(result.url))
            except RetrievalMissing:
                continue

        extraction = llm.structured(
            system=_EXTRACT_SYSTEM,
            prompt=_extract_prompt(provider, capability, pages),
            schema=EXTRACT_SCHEMA,
            label=f"discover:{provider}:{capability_id}",
        )

        for off in extraction.get("offerings", []):
            key = dedup_key(off.get("provider", ""), off.get("name", ""))
            url = off.get("source_url", "")
            if not key:
                continue
            if is_duplicate(key, known_names) or url in known_urls or is_duplicate(key, seen_names):
                continue  # dedup vs dataset (incl. rename lineage) and within this run
            seen_names.add(key)
            pid = _unique_id(_kebab(off["provider"], off["name"]), used_ids)
            used_ids.add(pid)
            record = {
                "id": pid,
                "name": off["name"],
                "kind": off.get("kind", "product"),
                "provider": off["provider"],
                "capability_ids": [capability_id],
                "primary_capability_id": capability_id,
                "relation_within_capability": "direct",  # provisional; triage refines
                "surfaces": off.get("surfaces", []),
                "status": "active",                       # provisional; triage refines
                "review_status": "candidate",
                "scope_note": off.get("summary", ""),
                "lifecycle": [],
                "source": {"url": url, "last_verified": _AS_OF_DATE, "confidence": "low"},
            }
            candidates.append(Candidate(record=record, evidence=off.get("evidence_quote", ""),
                                        source_query=query))
    return candidates


def candidates_to_doc(capability_id: str, candidates: list[Candidate]) -> dict:
    return {
        "capability_id": capability_id,
        "candidates": [
            {"record": c.record, "evidence": c.evidence, "source_query": c.source_query}
            for c in candidates
        ],
    }
