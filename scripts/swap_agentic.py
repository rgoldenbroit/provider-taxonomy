"""Swap the staged sweep records into the catalog, replacing the old agentic-coding feature layer.

Removes every old `feature`/`service_tier` node on the 8 agentic axes (templated cells, earlier
sub-features, orphans, the mis-typed Google MCP record) and adds the grounded sweep records. Keeps
top-level products, models, platforms, capabilities, and categories. Validates before writing.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from taxonomy.schema import DEFAULT_DATA_PATH  # noqa: E402
from taxonomy.validate import validate  # noqa: E402

AXES = {"subagents-orchestration", "managed-agent-runtime", "agent-memory", "mcp-connectors",
        "code-execution-sandbox", "guardrails-safety", "agent-evals-observability", "remote-agent-control"}

def main() -> int:
    cat = json.loads(DEFAULT_DATA_PATH.read_text(encoding="utf-8"))
    staged = json.loads((ROOT / "data" / "_sweep_records.json").read_text(encoding="utf-8"))["records"]

    before = len(cat["products"])
    # keep everything that is NOT an old agentic-axis feature/service_tier cell
    kept = [p for p in cat["products"]
            if not (p.get("kind") in ("feature", "service_tier")
                    and p.get("primary_capability_id") in AXES)]
    removed = before - len(kept)

    # add the staged grounded records (dedup by id)
    kept_ids = {p["id"] for p in kept}
    added = [r for r in staged if r["id"] not in kept_ids]
    cat["products"] = kept + added
    cat.setdefault("_meta", {})["as_of"] = "2026-06-22"

    issues = validate(cat)
    print(f"removed {removed} old agentic feature/service_tier nodes; added {len(added)} grounded records")
    print(f"catalog: {len(cat['products'])} products  ·  {'valid' if not issues else f'{len(issues)} ISSUES'}")
    for i in issues[:10]:
        print("  ", i)
    if issues:
        print("NOT writing — fix integrity first", file=sys.stderr)
        return 1
    DEFAULT_DATA_PATH.write_text(json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {DEFAULT_DATA_PATH}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
