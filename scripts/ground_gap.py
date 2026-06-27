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

_AS_OF = "2026-06-27"

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


def _record(provider: str, root: str, name: str, kind: str, cap: str, url: str) -> dict:
    rid = f"{root}-{_slug(name)}"
    return {
        "id": rid, "parent_id": root, "name": name, "kind": kind, "provider": provider,
        "capability_ids": [cap], "primary_capability_id": cap,
        "relation_within_capability": "direct", "surfaces": [], "status": "active",
        "review_status": "candidate", "scope_note": _SCOPE.get(rid, ""), "lifecycle": [],
        "source": {"url": url, "last_verified": _AS_OF, "confidence": "low"},
    }


def main() -> int:
    cfg = settings()
    if cfg.offline:
        print("ground_gap grounds against live docs: set TAXO_OFFLINE=0.", file=sys.stderr)
        return 1
    # Ledgered LLM + fetcher so the grounding (page snapshot + judge call) is recorded to the evidence
    # ledger — otherwise `taxo verify` can't replay this record and the reproducibility gate fails.
    llm = get_llm(cfg)
    ledger = build_ledger(cfg)
    retrieval = HttpFetch(ledger=ledger)
    catalog = load_dataset()
    as_of = (catalog.get("_meta") or {}).get("as_of") or AS_OF   # reproduce at the catalog's own date
    existing = {p["id"] for p in catalog["products"]}

    admitted = 0
    for provider, root, name, kind, cap, url in GAPS:
        rec = _record(provider, root, name, kind, cap, url)
        if rec["id"] in existing:
            print(f"  SKIP (already present) {rec['id']}")
            continue
        # ground: fetch the page, judge must find the supporting quote verbatim on it
        outcome = triage_one(rec, dataset=catalog, llm=llm, retrieval=retrieval,
                             evidence=name, pinned_capability=cap)
        # triage_one can rewrite fields — re-pin the ones that decide projection/placement
        outcome.record["id"] = rec["id"]
        outcome.record["parent_id"] = root
        outcome.record["kind"] = kind
        outcome.record["capability_ids"] = [cap]
        outcome.record["primary_capability_id"] = cap
        if not outcome.record.get("scope_note"):
            outcome.record["scope_note"] = rec["scope_note"]
        print(f"  {outcome.decision.upper():12} {outcome.record['id']:24} "
              f"[grounding {outcome.report.grounding.score:.2f}]")
        if outcome.decision in ("confirmed", "needs_review"):
            # normalize to verify's fixed point: re-ground + grade + write a provenance receipt at the
            # catalog's own as_of, so `taxo verify` reproduces it byte-identically (the CI repro gate).
            reverify_record(outcome.record, llm, retrieval, ledger, as_of)
            outcome.record["id"] = rec["id"]
            outcome.record["parent_id"] = root
            outcome.record["primary_capability_id"] = cap
            catalog["products"].append(outcome.record)
            DEFAULT_DATA_PATH.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
            admitted += 1
        else:
            print(f"    NOT admitted — grounding rejected; leaving the cell an honest gap.")

    print(f"admitted {admitted}/{len(GAPS)}; total products: {len(catalog['products'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
