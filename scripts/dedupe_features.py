"""Deduplicate top-level features that were extracted under multiple axes.

A feature like "Sandbox runtime" got pulled under both code-execution-sandbox and managed-agent-runtime.
For each (provider, normalized-name) group of top-level features (parent is a product/platform), keep
the richest instance (most sub-features, then highest source confidence, then shortest id), re-point the
losers' sub-features onto the keeper (deduping sub-features by name), and drop the losers. Idempotent.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from taxonomy.schema import DEFAULT_DATA_PATH  # noqa: E402
from taxonomy.validate import validate  # noqa: E402

_norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
_CONF = {"high": 3, "medium": 2, "low": 1}
NONFEATURE = {"product", "platform", "model_family", "model", "service_tier", "protocol"}


def main() -> int:
    d = json.loads(DEFAULT_DATA_PATH.read_text(encoding="utf-8"))
    P = d["products"]; byid = {p["id"]: p for p in P}
    children = defaultdict(list)
    for p in P:
        children[p.get("parent_id")].append(p)

    def is_top_feature(p):
        return p.get("kind") == "feature" and (byid.get(p.get("parent_id")) or {}).get("kind") in NONFEATURE

    def richness(p):
        subs = sum(1 for c in children[p["id"]] if c.get("kind") == "feature")
        return (subs, _CONF.get((p.get("source") or {}).get("confidence"), 0), -len(p["id"]))

    groups = defaultdict(list)
    for p in P:
        if is_top_feature(p):
            groups[(p["provider"], _norm(p["name"]))].append(p)

    drop_ids, merged_subs, kept_axes = set(), 0, []
    for (prov, name), insts in groups.items():
        if len(insts) < 2:
            continue
        insts.sort(key=richness, reverse=True)
        keep, losers = insts[0], insts[1:]
        keep_sub_names = {_norm(c["name"]) for c in children[keep["id"]] if c.get("kind") == "feature"}
        for L in losers:
            for sub in list(children[L["id"]]):
                if sub.get("kind") == "feature" and _norm(sub["name"]) not in keep_sub_names:
                    sub["parent_id"] = keep["id"]; keep_sub_names.add(_norm(sub["name"])); merged_subs += 1
                else:
                    drop_ids.add(sub["id"])   # duplicate sub-feature
            drop_ids.add(L["id"])
        kept_axes.append(f"{prov} '{keep['name'][:32]}' kept on {keep['primary_capability_id']} (dropped {len(losers)})")

    d["products"] = [p for p in P if p["id"] not in drop_ids]
    issues = validate(d)
    print(f"deduped {len([1 for g in groups.values() if len(g)>1])} groups; "
          f"dropped {len(drop_ids)} nodes; re-pointed {merged_subs} sub-features")
    for line in kept_axes[:20]:
        print("  ", line)
    print(f"catalog: {len(d['products'])} products · {'valid' if not issues else f'{len(issues)} ISSUES'}")
    for i in issues[:8]:
        print("  ", i)
    if issues:
        print("NOT writing — fix integrity first", file=sys.stderr); return 1
    DEFAULT_DATA_PATH.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {DEFAULT_DATA_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
