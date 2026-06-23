"""Swap a capability's staged sweep records into the catalog (capability-general).

Unlike swap_agentic (which removed by axis — wrong when a capability reuses cross-cutting axes),
this removes only the existing feature DESCENDANTS of the capability's product nodes, then adds the
freshly-grounded sweep records. Keeps the product nodes, models, platforms, capabilities, categories.
Validates before writing.

Usage: python3 scripts/swap_capability.py --capability=enterprise-agent-platform
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from taxonomy.provider_scan import CAPABILITY_CONFIG  # noqa: E402
from taxonomy.schema import DEFAULT_DATA_PATH  # noqa: E402
from taxonomy.validate import validate  # noqa: E402


def _descendants(products: list[dict], roots: set[str]) -> set[str]:
    """All records whose parent chain bottoms out at one of `roots` (the capability's products)."""
    by_parent: dict[str, list[str]] = {}
    for p in products:
        by_parent.setdefault(p.get("parent_id"), []).append(p["id"])
    out, stack = set(), list(roots)
    while stack:
        for child in by_parent.get(stack.pop(), []):
            if child not in out:
                out.add(child)
                stack.append(child)
    return out


def main() -> int:
    flags = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    capability = flags.get("capability")
    if capability not in CAPABILITY_CONFIG:
        print(f"unknown capability {capability!r}; known: {list(CAPABILITY_CONFIG)}", file=sys.stderr)
        return 1
    staged_path = ROOT / "data" / f"_sweep_{capability}.json"
    blob = json.loads(staged_path.read_text(encoding="utf-8"))
    staged, as_of = blob["records"], blob.get("as_of")

    cat = json.loads(DEFAULT_DATA_PATH.read_text(encoding="utf-8"))
    product_ids = {meta["product_id"] for meta in CAPABILITY_CONFIG[capability].values()}
    old = _descendants(cat["products"], product_ids)   # existing feature layer for this capability
    kept = [p for p in cat["products"] if p["id"] not in old]
    kept_ids = {p["id"] for p in kept}
    added = [r for r in staged if r["id"] not in kept_ids]
    cat["products"] = kept + added
    if as_of:
        cat.setdefault("_meta", {})["as_of"] = as_of

    issues = validate(cat)
    print(f"capability {capability}: removed {len(old)} old descendant(s); added {len(added)} grounded records")
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
