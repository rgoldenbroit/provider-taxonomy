"""Triage: classify a candidate into the taxonomy, run the trust gates, decide.

Orchestrates the LLM/retrieval calls (which the pure scorers in ``trust.py`` do
not), assembles the updated record, and sets ``review_status`` from the gates'
verdict. Writes are append-only: a ``triaged`` lifecycle event is added; existing
fields are replaced by the triage decision, never silently dropped.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from .discover import _KIND_ENUM, _SURFACE_ENUM
from .retrieval.base import RetrievalError, RetrievalProvider
from .trust import (
    GateResult,
    TrustReport,
    classification_gate,
    grounding_gate,
    schema_gate,
)
from .vertex_client import LLMClient

_AS_OF_DATE = "2026-06-15"
_N_SAMPLES = 3
_MAX_PAGE_CHARS = 20000   # cap page text in the judge prompt; a pathological page must not blow the context window
_REVIEWABLE = ("candidate", "needs_review")
_VALID_SURFACES = {"web", "desktop", "mobile", "terminal", "ide", "extension", "cloud", "api"}

CLASSIFY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["capability_ids", "primary_capability_id", "relation_within_capability",
                 "kind", "surfaces", "confidence", "rationale"],
    "properties": {
        "capability_ids": {"type": "array", "items": {"type": "string"}},
        "primary_capability_id": {"type": "string"},
        "relation_within_capability": {"type": "string", "enum": ["direct", "partial", "broader", "none"]},
        "kind": {"type": "string", "enum": _KIND_ENUM},
        "parent_id": {"type": "string"},
        "surfaces": {"type": "array", "items": {"type": "string", "enum": _SURFACE_ENUM}},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "rationale": {"type": "string"},
    },
}

JUDGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["supported", "confidence", "found_quote", "lifecycle_status", "rationale"],
    "properties": {
        "supported": {"type": "boolean"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "found_quote": {"type": "string"},
        "lifecycle_status": {
            "type": "string",
            "enum": ["active", "preview", "beta", "deprecated", "sunset", "merged", "renamed", "unknown"],
        },
        "rationale": {"type": "string"},
    },
}

ADMIT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict", "rationale"],
    "properties": {
        "verdict": {"type": "string", "enum": ["node", "surface", "ambiguous"]},
        "parent_id": {"type": "string"},
        "access_surfaces": {"type": "array", "items": {"type": "string",
            "enum": ["web", "desktop", "mobile", "terminal", "ide", "extension", "cloud", "api"]}},
        "rationale": {"type": "string"},
    },
}

_CLASSIFY_SYSTEM = (
    "You classify an AI-provider offering into a fixed capability taxonomy. Choose "
    "only from the provided capability ids. primary_capability_id must be one of "
    "capability_ids.\n\n"
    "capability_ids lists ONLY the capabilities this offering is itself presented "
    "as — usually exactly ONE (the primary). Add a second only when the offering is "
    "genuinely a distinct, comparable product in that capability too (e.g. an agent "
    "that is both a coding agent and a remote-control surface). Do NOT attribute "
    "downstream uses to a thing: a base MODEL belongs to flagship-model only — not "
    "to chat, coding, or browsing, which are separate products built on it.\n\n"
    "relation: 'broader' if the offering does more than the capability, 'partial' if "
    "it covers only a slice, else 'direct'. Set parent_id only if it is a feature or "
    "sub-product of an existing product."
)

_JUDGE_SYSTEM = (
    "You verify grounding STRICTLY from the fetched page — it is the source of truth. Decide "
    "only whether THE PAGE asserts or describes that the provider has the named offering "
    "(announced, in preview, or available). "
    "Do NOT use your own knowledge of whether the offering exists, and do NOT judge plausibility: "
    "the current date is LATER than your training cutoff, so real offerings, models, companies, "
    "and events from 2025–2026 may be unfamiliar to you — that does not make them fake. A third-"
    "party article that describes the offering DOES substantiate its existence. "
    "Set supported true if the page describes the offering, and quote it verbatim in found_quote. "
    "Set supported false ONLY if the page does not mention the offering at all. "
    "Never quote text that is not on the page.\n"
    "Also report lifecycle_status — what the PAGE says about the offering's stage: 'active' "
    "(current/generally available), 'preview'/'beta' (early access or 'coming soon'), 'deprecated' "
    "(being retired but still works), 'sunset' (discontinued/shut down/end-of-life), 'merged' or "
    "'renamed' (folded into or renamed to another product), or 'unknown' if the page doesn't say. "
    "If the page says the offering is discontinued, shutting down, or has a retirement date, that is "
    "'sunset' (or 'deprecated' if it still works for now) — do not call it 'active'."
)


_ADMIT_SYSTEM = (
    "You decide whether an offering earns its OWN node in a capability taxonomy. It earns a node "
    "('node') only if it adds a cross-provider comparison axis — a capability another provider could "
    "also fill — distinct from offerings already in the catalog. If it merely EXPOSES or PACKAGES an "
    "existing parent product (an SDK / CLI / API / plugin / IDE-extension giving access to a product "
    "already listed), it is a 'surface' of that parent: set verdict 'surface', parent_id to that "
    "product's id, and access_surfaces to how it is accessed. If genuinely unclear, 'ambiguous'. "
    "Managed agent runtimes, remote/async control, and computer-use are distinct axes (nodes); an "
    "'X SDK' or 'X CLI' for an already-listed X is usually a surface of X."
)


@dataclass
class TriageOutcome:
    record: dict          # updated record (review_status set, lifecycle appended)
    report: TrustReport
    decision: str


def _capabilities_block(dataset: dict) -> str:
    lines = [f"- {c['id']}: {c['name']} — {c['description']}" for c in dataset.get("capabilities", [])]
    return "\n".join(lines)


def classify(record: dict, dataset: dict, llm: LLMClient,
             pinned_capability: str | None = None) -> dict:
    pin = ""
    if pinned_capability:
        pin = (f"\nThis offering was discovered under the capability '{pinned_capability}'. "
               f"primary_capability_id MUST be '{pinned_capability}'. Determine its relation to "
               f"THAT capability, its kind, surfaces, and any ADDITIONAL capabilities it genuinely "
               f"also fills (always include '{pinned_capability}' in capability_ids).\n")
    prompt = (
        f"OFFERING: {record.get('name')} (provider {record.get('provider')})\n"
        f"SUMMARY: {record.get('scope_note', '')}\n\n"
        f"CAPABILITIES:\n{_capabilities_block(dataset)}\n"
        f"{pin}\n"
        f"EXISTING PRODUCT IDS (for parent_id, if this is a feature/sub-product):\n"
        f"{', '.join(p['id'] for p in dataset.get('products', []))}\n\n"
        "Return the classification as structured JSON."
    )
    out = llm.structured(system=_CLASSIFY_SYSTEM, prompt=prompt,
                         schema=CLASSIFY_SCHEMA, label=f"triage:{record['id']}")
    if pinned_capability:
        out["primary_capability_id"] = pinned_capability
        caps = [c for c in (out.get("capability_ids") or []) if c]
        if pinned_capability not in caps:
            caps = [pinned_capability, *caps]
        out["capability_ids"] = caps
    # flagship-model is a model-only capability — never attribute it to a product/feature.
    if out.get("kind") not in ("model", "model_family"):
        caps = [c for c in out.get("capability_ids", []) if c != "flagship-model"]
        out["capability_ids"] = caps or [out["primary_capability_id"]]
        if out.get("primary_capability_id") == "flagship-model":
            out["primary_capability_id"] = out["capability_ids"][0]
    return out


def admissibility(record: dict, dataset: dict, llm: LLMClient) -> dict:
    """Decide whether a candidate earns its own node, or is a surface of a parent."""
    existing = "\n".join(f"- {p['id']}: {p['name']} ({p['provider']})"
                         for p in dataset.get("products", []) if p.get("id") != record.get("id"))
    prompt = (f"OFFERING: {record.get('name')} ({record.get('provider')})\n"
              f"SUMMARY: {record.get('scope_note', '')}\n\n"
              f"EXISTING CATALOG NODES (potential parents):\n{existing or '(none yet)'}\n\n"
              "Return the admissibility decision as JSON.")
    return llm.structured(system=_ADMIT_SYSTEM, prompt=prompt, schema=ADMIT_SCHEMA,
                          label=f"admit:{record['id']}")


def _judge_grounding(record: dict, retrieval: RetrievalProvider, llm: LLMClient):
    url = (record.get("source") or {}).get("url", "")
    try:
        page = retrieval.fetch(url)
    except RetrievalError:  # missing fixture or network failure ⇒ grounding cannot pass
        return None, None
    prompt = (
        f"CLAIM: {record.get('provider')} offers {record.get('name')} "
        f"({record.get('scope_note', '')}).\n\n"
        f"PAGE (fetched from {url}):\n{page.text[:_MAX_PAGE_CHARS]}\n\n"
        "Does the page substantiate the claim? Return structured JSON."
    )
    judge = llm.structured(system=_JUDGE_SYSTEM, prompt=prompt,
                           schema=JUDGE_SCHEMA, label=f"judge:{record['id']}")
    return page, judge


def _clean_enum(value):
    """Strip whitespace and stray wrapping quotes the LLM sometimes emits (e.g. '"model"')."""
    return value.strip().strip('"').strip("'").strip() if isinstance(value, str) else value


def _apply_classification(record: dict, decision: dict) -> dict:
    updated = copy.deepcopy(record)
    updated["capability_ids"] = decision.get("capability_ids", record.get("capability_ids", []))
    updated["primary_capability_id"] = decision.get("primary_capability_id",
                                                     record.get("primary_capability_id"))
    updated["relation_within_capability"] = _clean_enum(decision.get("relation_within_capability",
                                                        record.get("relation_within_capability")))
    updated["kind"] = _clean_enum(decision.get("kind", record.get("kind")))
    # the LLM occasionally emits a surface outside the enum (e.g. "cli") — drop those
    surfaces = decision.get("surfaces", record.get("surfaces", []))
    updated["surfaces"] = [s for s in surfaces if s in _VALID_SURFACES]
    parent = decision.get("parent_id")
    if parent:
        updated["parent_id"] = parent
    return updated


def _confidence_for(decision_status: str, classify_confidence: str) -> str:
    if decision_status == "confirmed":
        return classify_confidence or "medium"
    return "low"


def triage_one(record: dict, *, dataset: dict, llm: LLMClient,
               retrieval: RetrievalProvider, n_samples: int = _N_SAMPLES,
               evidence: str | None = None, pinned_capability: str | None = None) -> TriageOutcome:
    samples = [classify(record, dataset, llm, pinned_capability) for _ in range(n_samples)]
    decision = samples[0]
    updated = _apply_classification(record, decision)

    page, judge = _judge_grounding(record, retrieval, llm)
    if judge and judge.get("supported"):
        observed = _clean_enum(judge.get("lifecycle_status"))
        if observed and observed != "unknown":
            updated["status"] = observed  # lifecycle grounded from the source, not defaulted
    report = TrustReport(
        schema=schema_gate(updated, dataset),
        grounding=grounding_gate(updated, page, judge, evidence=evidence),
        classification=classification_gate(samples),
    )
    status = report.decision()

    updated["review_status"] = status
    source = updated.setdefault("source", {})
    source["last_verified"] = _AS_OF_DATE
    source["confidence"] = _confidence_for(status, decision.get("confidence", "low"))
    note = f"Auto-triage → {status} (grounding {report.grounding.score:.2f}, " \
           f"classification {report.classification.score:.2f}). {decision.get('rationale', '')}"
    updated.setdefault("lifecycle", []).append(
        {"date": _AS_OF_DATE, "event": "triaged", "note": note[:280]})

    return TriageOutcome(record=updated, report=report, decision=status)


def triage_dataset(dataset: dict, *, llm: LLMClient,
                   retrieval: RetrievalProvider) -> tuple[dict, list[TriageOutcome]]:
    """Triage every reviewable record; return a proposed dataset + per-record outcomes."""
    proposed = copy.deepcopy(dataset)
    outcomes: list[TriageOutcome] = []
    for i, product in enumerate(proposed["products"]):
        if product.get("review_status") in _REVIEWABLE:
            outcome = triage_one(product, dataset=dataset, llm=llm, retrieval=retrieval)
            proposed["products"][i] = outcome.record
            outcomes.append(outcome)
    return proposed, outcomes
