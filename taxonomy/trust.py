"""Trust gates and dataset-level trust metrics.

Every record passes three gates before it can be admitted as ``confirmed``:

1. **schema** — conforms to ``schema.json`` (product subset) + referential integrity.
2. **grounding** — a *fetched* source page substantiates the claim, verified two
   ways: an independent judge says ``supported`` AND the judge's quote is actually
   present in the page (guards against a judge hallucinating support).
3. **classification** — the triage decision is stable across N samples.

The functions here are pure given their inputs (fetched page, judge result,
samples) — the LLM/retrieval calls live in ``triage.py`` — so the gates are
directly unit-testable.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .retrieval.base import FetchedPage
from .validate import validate_instance

_PRODUCT_REF = {"$ref": "#/$defs/product"}
_CONFIRM_AGREEMENT = 2 / 3  # ≥2 of 3 samples must agree on (primary, relation)


def matchkey(text: str) -> str:
    """Normalize for quote matching: lowercase, collapse non-alphanumerics to spaces."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def quote_supported(quote: str, text: str) -> bool:
    """Is the quote present in the page? Exact (normalized) substring, or — for
    messy/JS-rendered pages — a high token-overlap fallback. Keeps the
    anti-hallucination guard (the quote's content must be on the page) while
    tolerating whitespace/punctuation/truncation differences."""
    q, t = matchkey(quote), matchkey(text)
    if not q:
        return False
    if q in t:
        return True
    q_tokens = q.split()
    if len(q_tokens) < 4:
        return False  # too short to trust an overlap match
    page_tokens = set(t.split())
    present = sum(1 for w in q_tokens if w in page_tokens)
    return present / len(q_tokens) >= 0.85


@dataclass
class GateResult:
    name: str
    passed: bool
    score: float
    detail: str


@dataclass
class TrustReport:
    schema: GateResult
    grounding: GateResult
    classification: GateResult

    def decision(self) -> str:
        if not self.grounding.passed:
            return "rejected"        # no verifiable source — not a real find
        if not self.schema.passed:
            return "rejected"        # malformed/invalid record — never admit (keeps the catalog valid)
        if not self.classification.passed:
            return "needs_review"    # grounded + valid, but unstable classification
        return "confirmed"

    def as_dict(self) -> dict:
        return {g.name: {"passed": g.passed, "score": round(g.score, 3), "detail": g.detail}
                for g in (self.schema, self.grounding, self.classification)}


def record_integrity(record: dict, cap_ids: set[str], prod_ids: set[str]) -> list[str]:
    """Per-record referential checks (the subset that applies to a single record)."""
    issues: list[str] = []
    caps = record.get("capability_ids", [])
    if isinstance(caps, list):
        if not caps:
            issues.append("capability_ids is empty")
        for cid in caps:
            if cid not in cap_ids:
                issues.append(f"unknown capability {cid!r}")
    primary = record.get("primary_capability_id")
    if isinstance(primary, str):
        if primary not in cap_ids:
            issues.append(f"unknown primary_capability_id {primary!r}")
        elif isinstance(caps, list) and primary not in caps:
            issues.append("primary_capability_id not in capability_ids")
    for field in ("parent_id", "predecessor_id", "successor_id"):
        ref = record.get(field)
        if isinstance(ref, str) and ref not in prod_ids:
            issues.append(f"{field} references unknown product {ref!r}")
    if record.get("status") == "absent" and record.get("relation_within_capability") != "none":
        issues.append("status 'absent' requires relation_within_capability 'none'")
    return issues


def schema_gate(record: dict, dataset: dict) -> GateResult:
    from .schema import load_schema  # local import to keep trust.py import-light

    root = load_schema()
    shape_issues = validate_instance(record, _PRODUCT_REF, root=root)
    cap_ids = {c["id"] for c in dataset.get("capabilities", [])}
    prod_ids = {p["id"] for p in dataset.get("products", [])} | {record.get("id")}
    ref_issues = record_integrity(record, cap_ids, prod_ids)
    detail = "; ".join([str(i) for i in shape_issues] + ref_issues) or "ok"
    passed = not shape_issues and not ref_issues
    return GateResult("schema", passed, 1.0 if passed else 0.0, detail)


def grounding_gate(record: dict, page: FetchedPage | None, judge: dict | None,
                   evidence: str | None = None) -> GateResult:
    """Independent judge must say supported AND a quote must verify in the page.

    The quote anchor is the judge's quote OR the extraction-time ``evidence`` quote
    (both come from the page) — robust against pages where the judge paraphrases.
    Judge independence is preserved: ``supported`` is still required.
    """
    if page is None or judge is None:
        return GateResult("grounding", False, 0.0, "source could not be fetched/judged")
    supported = bool(judge.get("supported"))
    judge_quote = judge.get("found_quote", "") or ""
    verified = quote_supported(judge_quote, page.text) or (
        bool(evidence) and quote_supported(evidence, page.text))
    passed = supported and verified
    if passed:
        score, detail = 1.0, "judge supported; quote verified in page"
    elif supported:
        score, detail = 0.5, "judge supported but quote not verifiable in page"
    else:
        score, detail = 0.0, "judge did not find support in page"
    return GateResult("grounding", passed, score, detail)


def classification_score(samples: list[dict]) -> tuple[float, str]:
    """Agreement on (primary_capability_id, relation_within_capability) across samples."""
    if not samples:
        return 0.0, "no samples"
    keys = [(s.get("primary_capability_id"), s.get("relation_within_capability")) for s in samples]
    winner, count = Counter(keys).most_common(1)[0]
    agreement = count / len(samples)
    return agreement, f"{count}/{len(samples)} agree on primary={winner[0]} relation={winner[1]}"


def classification_gate(samples: list[dict]) -> GateResult:
    agreement, detail = classification_score(samples)
    return GateResult("classification", agreement >= _CONFIRM_AGREEMENT, agreement, detail)
