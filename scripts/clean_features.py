"""LLM cleanup pass: fix verbose/sentence names, drop mis-scoped API minutiae, describe sub-features.

One Sonnet call per top-level feature handles the feature AND all its sub-features at once (so it's
~150 calls, not ~600). The model: normalizes names to <=6 words in the provider's own terminology,
flags nodes that aren't node-worthy product features (API-call mechanics, config keys, refusal/
fallback plumbing, sentence-fragments) for removal, and writes a one-line plain description for any
sub-feature missing one. Generated insight stored in the catalog (carried through `taxo verify`
unchanged); run with TAXO_LEDGER=off. Renaming changes grounding keys, so a reverify(record) must
follow. Flags: --dry (print, don't write), --limit=N, --name=<substr>.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from taxonomy.config import settings  # noqa: E402
from taxonomy.schema import DEFAULT_DATA_PATH  # noqa: E402
from taxonomy.validate import validate  # noqa: E402
from taxonomy.vertex_client import get_llm  # noqa: E402

SYSTEM = (
    "You are a taxonomy editor cleaning a cross-provider catalog of AI product features for a technical "
    "reader. For a feature and its sub-features you: (1) give each a SHORT name (<=6 words) in the "
    "provider's own terminology — never a sentence; (2) decide keep vs drop. DROP things that are not "
    "node-worthy product capabilities a competitor could also have: API-call mechanics, response-field "
    "/ config-key / flag descriptions, refusal/fallback/rate-limit plumbing, SDK boilerplate, and "
    "sentence-fragment 'names'. KEEP distinct named capabilities. (3) Write a one-line plain description "
    "(<=20 words) of what each item is. Never invent capabilities; base everything on the given text."
)
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["feature", "subfeatures"],
    "properties": {
        "feature": {"type": "object", "additionalProperties": False, "required": ["keep", "name", "description"],
                    "properties": {"keep": {"type": "boolean"}, "name": {"type": "string"}, "description": {"type": "string"}}},
        "subfeatures": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["orig", "keep", "name", "description"],
            "properties": {"orig": {"type": "string"}, "keep": {"type": "boolean"}, "name": {"type": "string"}, "description": {"type": "string"}}}},
    },
}
NONFEATURE = {"product", "platform", "model_family", "model", "service_tier", "protocol"}
_norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())


def main() -> int:
    flags = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    dry = "dry" in {a[2:] for a in sys.argv[1:] if a.startswith("--")}
    cfg = settings()
    if cfg.offline:
        print("clean_features needs live LLM: TAXO_OFFLINE=0", file=sys.stderr); return 1
    d = json.loads(DEFAULT_DATA_PATH.read_text(encoding="utf-8"))
    P = d["products"]; byid = {p["id"]: p for p in P}
    children = defaultdict(list)
    for p in P:
        children[p.get("parent_id")].append(p)
    def feat_kids(pid):
        return [c for c in children[pid] if c.get("kind") == "feature"]
    # process every feature that is either top-level (parent is a product) OR has feature-children,
    # so cleanup reaches all nesting levels (e.g. the 3-level Anthropic enterprise tree).
    tops = [p for p in P if p.get("kind") == "feature"
            and ((byid.get(p.get("parent_id")) or {}).get("kind") in NONFEATURE or feat_kids(p["id"]))]
    if flags.get("name"):
        tops = [f for f in tops if flags["name"].lower() in f["name"].lower()]
    if flags.get("limit"):
        tops = tops[:int(flags["limit"])]

    llm = get_llm(cfg)
    drop_ids = set(); renamed = 0; described = 0; dropped_feats = 0
    print(f"cleaning {len(tops)} top-level features\n")
    for i, f in enumerate(tops):
        subs = [c for c in children[f["id"]] if c.get("kind") == "feature"]
        prompt = (f'FEATURE: "{f["name"]}"\nDescription: {(f.get("scope_note") or "")[:300]}\n'
                  f'SUB-FEATURES:\n' + ("\n".join(f'  - {s["name"]}' for s in subs) or "  (none)"))
        try:
            out = llm.structured(system=SYSTEM, prompt=prompt, schema=SCHEMA, label=f"clean:{f['id']}")
        except Exception as exc:
            print(f"  SKIP {f['id']}: {type(exc).__name__}"); continue
        ff = out.get("feature", {})
        if dry:
            print(f"  {'KEEP' if ff.get('keep') else 'DROP'} {f['name'][:48]!r} -> {ff.get('name')!r}")
            for s in out.get("subfeatures", []):
                if not s.get("keep"): print(f"       drop sub: {s.get('orig','')[:50]}")
            continue
        if not ff.get("keep", True):
            drop_ids.add(f["id"]); drop_ids.update(s["id"] for s in subs); dropped_feats += 1; continue
        if ff.get("name") and ff["name"] != f["name"]:
            f["name"] = ff["name"][:80]; renamed += 1
        if ff.get("description") and not f.get("scope_note"):
            f["scope_note"] = ff["description"]; described += 1
        by_orig = {_norm(s["orig"]): s for s in out.get("subfeatures", [])}
        for s in subs:
            o = by_orig.get(_norm(s["name"]))
            if not o:
                continue
            if not o.get("keep", True):
                drop_ids.add(s["id"]); drop_ids.update(x["id"] for x in feat_kids(s["id"])); continue
            # only (re)name/describe a child here if it's a LEAF; a child that is itself a parent gets
            # cleaned by its own call (avoids double-rename across nesting levels).
            if feat_kids(s["id"]):
                continue
            if o.get("name") and o["name"] != s["name"]:
                s["name"] = o["name"][:80]; renamed += 1
            if o.get("description") and not s.get("scope_note"):
                s["scope_note"] = o["description"]; described += 1
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(tops)}")

    if dry:
        print("\n[dry] not written"); return 0
    d["products"] = [p for p in P if p["id"] not in drop_ids]
    issues = validate(d)
    print(f"\ndropped {dropped_feats} non-node-worthy features ({len(drop_ids)} nodes incl subs); "
          f"renamed {renamed}; described {described}")
    print(f"catalog: {len(d['products'])} products · {'valid' if not issues else f'{len(issues)} ISSUES'}")
    for x in issues[:8]:
        print("  ", x)
    if issues:
        print("NOT writing", file=sys.stderr); return 1
    DEFAULT_DATA_PATH.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {DEFAULT_DATA_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
