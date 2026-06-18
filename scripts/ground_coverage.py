"""Phase 2 — reliable coverage: fill UNKNOWN (provider × axis) cells, official-source-first.

For each feature-axis × provider that isn't already grounded-present, run the
official-docs-first multi-query discovery (taxonomy/coverage.find_offering) and
admit only what grounds. Cells that still don't ground stay UNKNOWN (no record) —
never a false absence. Idempotent: skips cells already present.

    TAXO_OFFLINE=0 .venv/bin/python scripts/ground_coverage.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from taxonomy.config import settings  # noqa: E402
from taxonomy.coverage import OFFICIAL_DOMAINS, _is_official, find_offering  # noqa: E402
from taxonomy.retrieval import get_retrieval  # noqa: E402
from taxonomy.schema import DEFAULT_DATA_PATH  # noqa: E402
from taxonomy.validate import validate  # noqa: E402
from taxonomy.vertex_client import get_llm  # noqa: E402

PROVIDERS = ("Anthropic", "OpenAI", "Google")

# (axis id, human name for the query, search keywords, short label for the record)
AXES = [
    ("managed-agent-runtime", "managed agents", "hosted agent runtime managed", "managed agents"),
    ("mcp-connectors", "MCP", "Model Context Protocol connectors hosted server support", "MCP & connectors"),
    ("agent-memory", "memory", "agent memory persistent context across sessions", "memory"),
    ("code-execution-sandbox", "code execution", "code execution sandbox isolated environment", "sandbox"),
    ("agent-evals-observability", "evals observability", "agent evals observability tracing monitoring", "evals & observability"),
    ("guardrails-safety", "guardrails", "agent guardrails safety moderation controls", "guardrails"),
    ("subagents-orchestration", "subagents", "subagents multi-agent orchestration spawn", "subagents"),
]


def _present(catalog, provider, axis_id) -> bool:
    return any(p for p in catalog["products"]
               if p["provider"] == provider and axis_id in p.get("capability_ids", [])
               and p.get("status") != "absent")


def main() -> int:
    cfg = settings()
    if cfg.offline:
        print("ground_coverage needs live grounding + search: set TAXO_OFFLINE=0.", file=sys.stderr)
        return 1
    catalog = json.loads(DEFAULT_DATA_PATH.read_text(encoding="utf-8"))
    cap_ids = {c["id"] for c in catalog["capabilities"]}
    llm, retrieval = get_llm(cfg), get_retrieval(cfg)
    found = filled = 0

    for axis_id, axis_name, keywords, short in AXES:
        if axis_id not in cap_ids:
            print(f"skip {axis_id}: not in spine (run add_feature_axes.py)", file=sys.stderr)
            continue
        print(f"\n[{axis_id}]")
        for provider in PROVIDERS:
            if _present(catalog, provider, axis_id):
                print(f"  present      {provider:10} (already grounded)")
                continue
            rec, url = find_offering(provider, axis_id, axis_name, keywords,
                                     dataset=catalog, llm=llm, retrieval=retrieval,
                                     name=f"{provider} {short}")
            found += 1
            if rec is None:
                print(f"  UNKNOWN      {provider:10} (no source grounded — left unverified, not absent)")
                continue
            off = "official" if _is_official(url, provider) else "secondary"
            print(f"  PRESENT      {provider:10} → {rec['name']}  [{off}]  {rec['status']}")
            catalog["products"].append(rec)
            filled += 1
        DEFAULT_DATA_PATH.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")

    print("\n=== coverage after fill (per axis) ===")
    for axis_id, _, _, _ in AXES:
        provs = [pr for pr in PROVIDERS if _present(catalog, pr, axis_id)]
        unk = [pr for pr in PROVIDERS if pr not in provs]
        print(f"  {axis_id:28} present: {', '.join(provs) or '—':32} unknown: {', '.join(unk) or '—'}")

    issues = validate(catalog)
    print(f"\nfilled {filled}/{found} unknown cells · {len(catalog['products'])} products · "
          f"{'✓ valid' if not issues else f'✗ {len(issues)} issue(s)'}")
    if issues:
        for i in issues[:8]:
            print("   ", i)
        return 1
    print(f"wrote {DEFAULT_DATA_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
