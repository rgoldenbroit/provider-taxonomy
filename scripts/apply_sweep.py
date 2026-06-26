#!/usr/bin/env python3
"""Apply a staged discovery sweep ADDITIVELY into data/taxonomy.json: prune noise, dedup against
existing features (by id and provider+normalized-name), append the rest, validate, and write (after a
backup). Unlike swap_capability.py this does NOT remove existing descendants — it only adds new ones.

  python scripts/apply_sweep.py data/_sweep_antigravity.json
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from taxonomy.schema import DEFAULT_DATA_PATH   # noqa: E402
from taxonomy.validate import validate          # noqa: E402

_norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
# thin / out-of-scope candidates to drop (reviewed) — stored normalized so matching is exact
PRUNE = {_norm(x) for x in ("CLI", "Tab completions", "Workspace scoping", "Prompt context inputs",
                            "Generative Image Tool", "Managing Credits")}


def main() -> int:
    sweep_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "_sweep_antigravity.json"
    sweep = json.loads(sweep_path.read_text(encoding="utf-8"))
    catalog = json.loads(DEFAULT_DATA_PATH.read_text(encoding="utf-8"))

    ids = {p["id"] for p in catalog["products"]}
    names = {(p["provider"], _norm(p["name"])) for p in catalog["products"]}
    added, pruned, dup = [], [], []
    for r in sweep["records"]:
        nm = _norm(r["name"])
        if nm in PRUNE:
            pruned.append(r["name"]); continue
        key = (r["provider"], nm)
        if r["id"] in ids or key in names:
            dup.append(r["name"]); continue
        catalog["products"].append(r)
        ids.add(r["id"]); names.add(key)
        added.append((r["name"], r.get("primary_capability_id")))

    issues = validate(catalog)
    if issues:
        print(f"ABORT: applying would break validation ({len(issues)} issues):", file=sys.stderr)
        for i in issues[:10]:
            print(f"  - {i.kind}:{i.rule} {i.record_id} {i.message}", file=sys.stderr)
        return 1

    backup = Path("/tmp") / "taxonomy.before_sweep.json"
    shutil.copy(DEFAULT_DATA_PATH, backup)
    DEFAULT_DATA_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"applied: +{len(added)} features  (pruned {len(pruned)}, skipped {len(dup)} dups).  backup: {backup}")
    print("  added:")
    for nm, ax in added:
        print(f"    {nm}  [{ax}]")
    if dup:
        print(f"  skipped as duplicates of existing features: {', '.join(dup)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
