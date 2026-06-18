"""Self-audit critic + deploy gate.

The critic red-teams a finished catalog — the job a human spot-check was doing —
and emits findings by severity:

- **mechanical** (no LLM, deterministic): schema validity, source authority
  (official vs secondary), staleness.
- **triangulation** (LLM + a *second, independent* source): for each record, search
  the web for an independent source and check it agrees on existence + lifecycle
  status. Disagreement (e.g. one source says active, another says discontinued) is a
  flag, not a silent pick — this is what catches a stale 'active'.
- **completeness**: per provider×capability, what notable offering is missing.

The **gate** blocks shipping unless: schema is clean, eval thresholds hold, and
there are zero *critical* findings. A critic with no gate is a report nobody
enforces; a gate with no critic has nothing to check.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlparse

from .rank import completeness_critic
from .retrieval.base import RetrievalError
from .staleness import days_overdue, is_stale, today_for
from .triage import JUDGE_SCHEMA, _JUDGE_SYSTEM, admissibility
from .validate import validate

# Provider-owned domains (incl. their docs/blogs) — everything else is "secondary".
_OFFICIAL_MARKERS = (
    "anthropic.com", "openai.com", "help.openai.com", "platform.openai.com", "openai.github.io",
    "deepmind.google", "ai.google.dev", "cloud.google.com", "developers.googleblog.com",
    "blog.google", "google.github.io", "jules.google", "antigravity.google", "notebooklm.google",
    "gemini.google",
)
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


@dataclass(frozen=True)
class Finding:
    severity: str   # critical | warning | info
    kind: str       # schema | existence | status | source | staleness | completeness | single_source | unconfirmed | node_worthiness | coverage_gap
    record_id: str | None
    message: str


def source_authority(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    return "official" if any(m in host for m in _OFFICIAL_MARKERS) else "secondary"


def _mechanical_findings(catalog: dict) -> list[Finding]:
    findings: list[Finding] = []
    for issue in validate(catalog):
        findings.append(Finding("critical", "schema", issue.record_id, str(issue)))
    today = today_for(catalog)
    for p in catalog.get("products", []):
        url = (p.get("source") or {}).get("url", "")
        if p.get("status") != "absent" and source_authority(url) != "official":
            findings.append(Finding("warning", "source", p["id"],
                                    f"non-official source: {urlparse(url).netloc}"))
        if is_stale(p, today):
            findings.append(Finding("warning", "staleness", p["id"],
                                    f"stale: {days_overdue(p, today)}d past re-verify window"))
    return findings


def _triangulate(record: dict, llm, retrieval) -> Finding | None:
    """Confirm an offering against an INDEPENDENT second source.

    Failure to confirm is 'unconfirmed' (a WARNING), never 'doesn't exist': a single
    page's silence is weak evidence, and the primary source already grounded the record
    at triage. Inferring non-existence from one source's silence is the same error as
    inferring absence from an empty cell. Only an OFFICIAL source asserting a real
    lifecycle CHANGE (sunset/merged/…) is escalated to critical."""
    if record.get("status") == "absent":
        return None  # a modeled absence has no existence to triangulate
    name, provider = record.get("name"), record.get("provider")
    primary_host = urlparse((record.get("source") or {}).get("url", "")).netloc
    try:
        results = retrieval.search(f"{provider} {name} 2026", max_results=6)
    except (RetrievalError, NotImplementedError):
        return None  # no live search → can't triangulate (mechanical checks still ran)
    others = [r for r in results if urlparse(r.url).netloc and urlparse(r.url).netloc != primary_host]
    # prefer an official independent source (avoids junk like instagram/axios as the 2nd source)
    second = next((r for r in others if source_authority(r.url) == "official"), others[0] if others else None)
    if second is None:
        return Finding("warning", "single_source", record["id"], "no independent second source found")
    try:
        page = retrieval.fetch(second.url)
    except RetrievalError:
        return Finding("warning", "single_source", record["id"], f"second source unfetchable: {second.url}")
    second_official = source_authority(second.url) == "official"

    prompt = (f"CLAIM: {provider} has an offering '{name}', currently '{record.get('status')}'.\n\n"
              f"INDEPENDENT PAGE (from {second.url}):\n{page.text[:8000]}\n\n"
              "Does this page substantiate the offering, and what lifecycle status does it indicate? JSON.")
    judge = llm.structured(system=_JUDGE_SYSTEM, prompt=prompt, schema=JUDGE_SCHEMA,
                           label=f"audit:{record['id']}")
    if not judge.get("supported"):
        # 2nd source is silent → unconfirmed, NOT disproven (the primary already grounded it)
        return Finding("warning", "unconfirmed", record["id"],
                       f"not confirmed by independent source {urlparse(second.url).netloc} "
                       f"(primary grounded it; one page's silence isn't disproof)")
    observed = judge.get("lifecycle_status")
    if observed and observed not in ("unknown", record.get("status")):
        lifecycle_change = {"sunset", "deprecated", "merged", "renamed"}
        # escalate only when an OFFICIAL source asserts a real lifecycle change
        severity = ("critical" if second_official and {observed, record.get("status")} & lifecycle_change
                    else "warning")
        return Finding(severity, "status", record["id"],
                       f"status mismatch: record says '{record.get('status')}', "
                       f"{urlparse(second.url).netloc} indicates '{observed}'")
    return None


def _node_worthiness_findings(catalog: dict, llm) -> list[Finding]:
    """Flag records that look like an access surface of another node, or are ambiguous."""
    findings: list[Finding] = []
    for p in catalog.get("products", []):
        if p.get("status") == "absent":
            continue
        verdict = admissibility(p, catalog, llm)
        v = verdict.get("verdict")
        rationale = (verdict.get("rationale") or "")[:80]
        if v == "surface":
            parent = verdict.get("parent_id") or "?"
            findings.append(Finding("warning", "node_worthiness", p["id"],
                                    f"likely a surface of '{parent}', not its own node: {rationale}"))
        elif v == "ambiguous":
            findings.append(Finding("info", "node_worthiness", p["id"],
                                    f"node-worthiness ambiguous: {rationale}"))
    return findings


def _coverage_findings(catalog: dict) -> list[Finding]:
    """Machine-flag every asymmetric cell: a provider with no record on an axis where
    a peer is present, and no grounded *absence* either → it's UNKNOWN, a verification
    target. This is the "checking" done by the engine, not by a human reading the grid."""
    findings: list[Finding] = []
    providers = sorted({p["provider"] for p in catalog.get("products", [])})
    present: dict[str, set[str]] = {}
    absent: dict[str, set[str]] = {}
    for p in catalog.get("products", []):
        if p.get("status") == "absent":
            absent.setdefault(p["primary_capability_id"], set()).add(p["provider"])
        else:
            for cap in p.get("capability_ids", []):
                present.setdefault(cap, set()).add(p["provider"])
    for c in catalog.get("capabilities", []):
        cap = c["id"]
        pres = present.get(cap, set())
        if cap == "unclassified" or not pres:
            continue   # a wholly-empty axis isn't an asymmetry; nobody claims coverage
        for prov in providers:
            if prov in pres or prov in absent.get(cap, set()):
                continue   # present, or a grounded absence — both are resolved
            findings.append(Finding("info", "coverage_gap", None,
                f"[{cap}] not yet verified for {prov} (present: {', '.join(sorted(pres))}) — verification target"))
    return findings


def _completeness_findings(catalog: dict, llm) -> list[Finding]:
    findings: list[Finding] = []
    cap_name = {c["id"]: c["name"] for c in catalog.get("capabilities", [])}
    by: dict[tuple, list[str]] = {}
    for p in catalog.get("products", []):
        by.setdefault((p["primary_capability_id"], p["provider"]), []).append(p["name"])
    for (cap, provider), found in sorted(by.items()):
        for gap in completeness_critic(provider, cap_name.get(cap, cap), found, llm).get("missing", [])[:3]:
            findings.append(Finding("info", "completeness", None,
                                    f"[{cap} / {provider}] missing: {gap['name']} — {gap['why'][:80]}"))
    return findings


def audit_catalog(catalog: dict, llm=None, retrieval=None, *,
                  triangulate: bool = True, completeness: bool = True,
                  node_worthiness: bool = True) -> list[Finding]:
    findings = _mechanical_findings(catalog)
    findings += _coverage_findings(catalog)   # deterministic; the engine flags asymmetric/unknown cells
    if llm is not None and triangulate and retrieval is not None:
        for p in catalog.get("products", []):
            f = _triangulate(p, llm, retrieval)
            if f:
                findings.append(f)
    if llm is not None and node_worthiness:
        findings += _node_worthiness_findings(catalog, llm)
    if llm is not None and completeness:
        findings += _completeness_findings(catalog, llm)
    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.kind, f.record_id or ""))
    return findings


def gate(catalog: dict, findings: list[Finding], eval_report: dict | None = None) -> tuple[bool, list[str]]:
    """Ship only if schema clean, evals pass, and no critical findings."""
    reasons: list[str] = []
    if validate(catalog):
        reasons.append("schema invalid")
    if eval_report is not None and not eval_report.get("passed"):
        reasons.append("eval thresholds failed")
    critical = [f for f in findings if f.severity == "critical"]
    if critical:
        reasons.append(f"{len(critical)} critical audit finding(s)")
    return (not reasons, reasons)


def findings_to_dicts(findings: list[Finding]) -> list[dict]:
    return [asdict(f) for f in findings]
