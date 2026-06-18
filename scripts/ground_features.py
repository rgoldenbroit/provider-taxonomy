"""Phase B — ground per-product features on the 7 feature-axes (agentic-coding cluster).

For each (cluster product × axis): live-search for the feature, build a candidate
`kind:"feature"` record (parent_id = product, primary_capability_id = axis), and
ground it via the trust pipeline. ADMIT ONLY WHAT GROUNDS — an ungrounded cell is
left empty (an honest "this product doesn't expose that"), never fabricated.

Incremental + idempotent: appends to data/taxonomy.json without re-grounding the
existing records. Requires live grounding + Tavily search (TAXO_OFFLINE=0).

    .venv/bin/python scripts/ground_features.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from taxonomy.config import settings  # noqa: E402
from taxonomy.discover import _kebab  # noqa: E402
from taxonomy.retrieval import get_retrieval  # noqa: E402
from taxonomy.retrieval.base import RetrievalError  # noqa: E402
from taxonomy.schema import DEFAULT_DATA_PATH  # noqa: E402
from taxonomy.triage import triage_one  # noqa: E402
from taxonomy.validate import validate  # noqa: E402
from taxonomy.vertex_client import get_llm  # noqa: E402

_AS_OF = "2026-06-17"

# (parent product id, provider, product name used in the search query)
CLUSTER = [
    ("anthropic-claude-code", "Anthropic", "Claude Code"),
    ("openai-codex", "OpenAI", "Codex"),
    ("google-antigravity-2-0", "Google", "Antigravity"),
    ("google-jules", "Google", "Jules"),
]

# (axis id, short label for the feature name, search keywords)
AXES = [
    ("managed-agent-runtime", "managed agents", "managed agents hosted agent runtime"),
    ("mcp-connectors", "MCP & connectors", "MCP Model Context Protocol connectors support"),
    ("agent-memory", "memory", "agent memory persistent context across sessions"),
    ("code-execution-sandbox", "sandbox", "code execution sandbox isolated environment"),
    ("agent-evals-observability", "evals & observability", "evals observability tracing monitoring"),
    ("guardrails-safety", "guardrails", "guardrails safety permissions approval controls"),
    ("subagents-orchestration", "subagents", "subagents multi-agent orchestration spawn"),
]


def _feature_candidate(pid, provider, pname, axis_id, short, url, summary) -> dict:
    return {
        "id": _kebab(provider, f"{pname} {axis_id}"),
        "name": f"{pname} {short}", "kind": "feature", "provider": provider,
        "capability_ids": [axis_id], "primary_capability_id": axis_id,
        "relation_within_capability": "direct", "surfaces": [], "status": "active",
        "review_status": "candidate", "parent_id": pid,
        "scope_note": (summary or "")[:280], "lifecycle": [],
        "source": {"url": url, "last_verified": _AS_OF, "confidence": "low"},
    }


def main() -> int:
    cfg = settings()
    if cfg.offline:
        print("ground_features needs live grounding + search: set TAXO_OFFLINE=0.", file=sys.stderr)
        return 1
    catalog = json.loads(DEFAULT_DATA_PATH.read_text(encoding="utf-8"))
    have = {p["id"] for p in catalog["products"]}
    llm, retrieval = get_llm(cfg), get_retrieval(cfg)
    cap_ids = {c["id"] for c in catalog["capabilities"]}
    missing = [a for a, _, _ in AXES if a not in cap_ids]
    if missing:
        print(f"axes missing from the catalog spine (run add_feature_axes.py first): {missing}", file=sys.stderr)
        return 1

    coverage: dict[str, set[str]] = defaultdict(set)   # axis -> providers grounded
    counts: dict[str, int] = defaultdict(int)
    for pid, provider, pname in CLUSTER:
        print(f"\n[{pname}]")
        for axis_id, short, kw in AXES:
            fid = _kebab(provider, f"{pname} {axis_id}")
            if fid in have:
                print(f"  SKIP(exists) {fid}")
                continue
            try:
                results = retrieval.search(f"{provider} {pname} {kw} 2026", max_results=4)
            except (RetrievalError, NotImplementedError):
                results = []
            if not results:
                print(f"  no source    {short:22} (no search result)")
                counts["no_source"] += 1
                continue
            cand = _feature_candidate(pid, provider, pname, axis_id, short, results[0].url, results[0].snippet)
            try:
                outcome = triage_one(cand, dataset=catalog, llm=llm, retrieval=retrieval,
                                     evidence=cand["name"], pinned_capability=axis_id)
            except (RetrievalError, NotImplementedError) as exc:  # fetch/grounding failed → leave the cell empty
                print(f"  ERROR        {short:22} ({exc})")
                counts["error"] += 1
                continue
            rec = outcome.record                        # enforce the feature shape (operator knows it)
            rec["kind"], rec["parent_id"] = "feature", pid
            rec["primary_capability_id"], rec["capability_ids"] = axis_id, [axis_id]
            g = outcome.report.grounding.score
            print(f"  {outcome.decision.upper():12} {short:22} [g {g:.2f}] {rec['status']}")
            counts[outcome.decision] += 1
            if outcome.decision in ("confirmed", "needs_review"):
                catalog["products"].append(rec)
                have.add(fid)
                coverage[axis_id].add(provider)
        DEFAULT_DATA_PATH.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")

    print("\n=== axis coverage (discipline check: ≥2 providers to keep an axis) ===")
    for axis_id, _, _ in AXES:
        provs = sorted(coverage.get(axis_id, set()))
        flag = "" if len(provs) >= 2 else "  ← THIN (<2 providers)"
        print(f"  {axis_id:28} {len(provs)} provider(s): {', '.join(provs) or '—'}{flag}")

    issues = validate(catalog)
    print(f"\n{dict(counts)}  ·  {'✓ valid' if not issues else f'✗ {len(issues)} schema issue(s)'}  ·  {len(catalog['products'])} products total")
    if issues:
        for i in issues[:8]:
            print("   ", i)
        return 1
    print(f"wrote {DEFAULT_DATA_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
