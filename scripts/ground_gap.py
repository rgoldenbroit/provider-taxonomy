#!/usr/bin/env python3
"""Ground a matrix gap from its official doc page into the CATALOG (scope-B grounding core).

A matrix cell is empty when the capability isn't in the catalog for that provider. The scope-A
disprover can't fix that — it only reads the catalog. This grounds a specific (capability x provider)
from a first-party URL the SAME way the catalog does (fetch -> judge verifies a verbatim quote ->
admit), parenting the record under the provider's lineup root so the matrix projection picks it up on
the next rebuild. No new matrix-side grounding path: the matrix stays a pure projection of the catalog.

This is the grounding engine scope-B needs. Here it's driven by a hand-supplied URL list (the cells a
human caught); the autonomous URL-discovery layer (Tavily over official domains) feeds the same engine.

    TAXO_OFFLINE=0 .venv/bin/python scripts/ground_gap.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.config import settings                       # noqa: E402
from taxonomy.retrieval.http_fetch import HttpFetch        # noqa: E402
from taxonomy.schema import DEFAULT_DATA_PATH, load_dataset  # noqa: E402
from taxonomy.replay import AS_OF, reverify_record         # noqa: E402
from taxonomy.triage import triage_one                     # noqa: E402
from taxonomy.vertex_client import build_ledger, get_llm   # noqa: E402

# (provider, lineup_root, feature name, kind, catalog capability_id, first-party doc URL)
GAPS = [
    ("OpenAI", "openai-codex", "Hooks", "feature", "guardrails-safety",
     "https://developers.openai.com/codex/hooks"),
]

_SCOPE = {
    "openai-codex-hooks": "An extensibility framework that injects user scripts into Codex's agentic "
    "loop on lifecycle events — SessionStart, SubagentStart, PreToolUse, PermissionRequest, PostToolUse, "
    "PreCompact/PostCompact, UserPromptSubmit, SubagentStop, Stop — configured via hooks.json or "
    "config.toml. Enabled by default.",
}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def admit_grounded(provider, root, name, kind, cap, url, *, catalog, llm, retrieval, ledger,
                   as_of, scope_note="", review_status="candidate"):
    """Ground one (capability × provider) from a first-party URL and admit it under the lineup root,
    normalized to verify's fixed point (reverify at `as_of` → replay-reproducible). Forces
    ``review_status`` (default 'candidate') so autonomous discoveries land for human review rather than
    auto-activate. Returns (decision, record|None, grounding_score); the caller handles dedup + writing.
    Shared by ``ground_gap`` (hand-supplied URLs) and ``scout_gaps`` (Tavily-discovered URLs)."""
    rid = f"{root}-{_slug(name)}"
    rec = {
        "id": rid, "parent_id": root, "name": name, "kind": kind, "provider": provider,
        "capability_ids": [cap], "primary_capability_id": cap,
        "relation_within_capability": "direct", "surfaces": [], "status": "active",
        "review_status": review_status, "scope_note": scope_note or _SCOPE.get(rid, ""), "lifecycle": [],
        "source": {"url": url, "last_verified": as_of, "confidence": "low"},
    }
    # ground: fetch the page, judge must find the supporting quote verbatim on it
    outcome = triage_one(rec, dataset=catalog, llm=llm, retrieval=retrieval,
                         evidence=name, pinned_capability=cap)
    r = outcome.record                                  # triage can rewrite fields — re-pin placement + verdict
    r["id"], r["parent_id"], r["kind"] = rid, root, kind
    r["capability_ids"], r["primary_capability_id"] = [cap], cap
    r["review_status"] = review_status                  # keep it a candidate going INTO reverify (C1)
    if not r.get("scope_note"):
        r["scope_note"] = rec["scope_note"]
    if outcome.decision not in ("confirmed", "needs_review"):
        return outcome.decision, None, outcome.report.grounding.score
    # normalize to verify's fixed point: re-ground + grade + provenance receipt at the catalog's as_of,
    # so `taxo verify` reproduces it byte-identically (the CI repro gate — a non-ledgered admit breaks it).
    reverify_record(r, llm, retrieval, ledger, as_of)
    r["id"], r["parent_id"], r["primary_capability_id"], r["review_status"] = rid, root, cap, review_status
    return outcome.decision, r, outcome.report.grounding.score


def main() -> int:
    cfg = settings()
    if cfg.offline:
        print("ground_gap grounds against live docs: set TAXO_OFFLINE=0.", file=sys.stderr)
        return 1
    llm, ledger = get_llm(cfg), build_ledger(cfg)
    retrieval = HttpFetch(ledger=ledger)
    catalog = load_dataset()
    as_of = (catalog.get("_meta") or {}).get("as_of") or AS_OF   # reproduce at the catalog's own date
    existing = {p["id"] for p in catalog["products"]}

    admitted = 0
    for provider, root, name, kind, cap, url in GAPS:
        rid = f"{root}-{_slug(name)}"
        if rid in existing:
            print(f"  SKIP (already present) {rid}")
            continue
        decision, rec, score = admit_grounded(provider, root, name, kind, cap, url, catalog=catalog,
                                              llm=llm, retrieval=retrieval, ledger=ledger, as_of=as_of)
        print(f"  {decision.upper():12} {rid:28} [grounding {score:.2f}]")
        if rec is not None:
            catalog["products"].append(rec)
            DEFAULT_DATA_PATH.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
            existing.add(rid)
            admitted += 1
        else:
            print("    NOT admitted — grounding rejected; leaving the cell an honest gap.")

    print(f"admitted {admitted}/{len(GAPS)}; total products: {len(catalog['products'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
