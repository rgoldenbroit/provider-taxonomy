"""Generate feature-level cross-provider comparisons.

For each TOP-LEVEL feature (a feature whose parent is a product), find the nearest equivalent
among the OTHER providers' features within the same top-level capability cluster (across axes — so
e.g. a code-review feature can match a competitor's review feature even if it sits on a different
axis), and synthesize a plain-language "what it does + how providers compare" note. Constrained to
real catalog features (no hallucination); "no direct equivalent" is allowed. Also flags sub-features
that aren't actually facets of the parent (mis-attached sweep noise) and drops them.

Result is stored on each feature as `comparison` and carried in the catalog (generated insight, not
a grounded fact — so it travels through `taxo verify` unchanged; not ledger-replayed). Run live:
    TAXO_OFFLINE=0 .venv/bin/python scripts/gen_comparison.py [--capability=<id>]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from taxonomy.config import settings  # noqa: E402
from taxonomy.schema import DEFAULT_DATA_PATH  # noqa: E402
from taxonomy.validate import validate  # noqa: E402
from taxonomy.vertex_client import get_llm  # noqa: E402

SYSTEM = (
    "You compare one provider's feature against competitors' offerings, for a technical reader "
    "choosing between AI providers. Be specific and plain-spoken — no marketing language. You may "
    "ONLY reference features that appear in the provided candidate lists; never invent a feature. "
    "If a provider has no comparable offering, say so explicitly."
)

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["summary", "equivalents"],
    "properties": {
        "summary": {"type": "string",
                    "description": "At most 2 sentences, ~45 words. First what THIS feature does in simple terms, then how the other providers' nearest equivalents compare (or that they have none). Specific to this feature. Do NOT discuss sub-feature attribution here."},
        "equivalents": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["provider", "match", "note"],
            "properties": {
                "provider": {"type": "string"},
                "match": {"type": ["string", "null"], "description": "EXACT name of the nearest candidate feature, or null if none."},
                "note": {"type": "string", "description": "<=15 words: how it differs, or 'no direct equivalent'."},
            }}},
        "offtopic_subfeatures": {"type": "array", "items": {"type": "string"},
                                 "description": "Listed sub-features that are NOT actually a facet of this feature (mis-attached). [] if all fit."},
    },
}

_norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())


def main() -> int:
    flags = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    only_cap = flags.get("capability")
    cfg = settings()
    if cfg.offline:
        print("gen_comparison needs live LLM: set TAXO_OFFLINE=0.", file=sys.stderr)
        return 1
    cat = json.loads(DEFAULT_DATA_PATH.read_text(encoding="utf-8"))
    prods = cat["products"]
    by_id = {p["id"]: p for p in prods}
    children = {}
    for p in prods:
        children.setdefault(p.get("parent_id"), []).append(p)

    def root_function(p):  # walk to the top-level product; its primary capability is the cluster
        seen = 0
        while p.get("parent_id") in by_id and seen < 20:
            p = by_id[p["parent_id"]]; seen += 1
        return p.get("primary_capability_id")

    NONFEATURE = {"product", "platform", "model_family", "model", "service_tier", "protocol"}
    all_top = [p for p in prods if p.get("kind") == "feature"
               and (by_id.get(p.get("parent_id")) or {}).get("kind") in NONFEATURE]

    # candidate pool per (function, provider) — built from ALL top-level features (the full universe),
    # independent of which features we generate for, so --name/--limit never starves the candidates.
    pool = {}
    for f in all_top:
        pool.setdefault((root_function(f), f["provider"]), []).append(f)

    targets = all_top
    if only_cap:
        targets = [f for f in targets if root_function(f) == only_cap]
    only_name = flags.get("name")
    if only_name:
        targets = [f for f in targets if only_name.lower() in f["name"].lower()]
    limit = int(flags.get("limit", 0))
    dry = "dry" in {a[2:] for a in sys.argv[1:] if a.startswith("--")}
    if limit:
        targets = targets[:limit]

    llm = get_llm(cfg)
    providers = sorted({p["provider"] for p in prods})
    done = dropped = 0
    print(f"generating comparisons for {len(targets)} top-level features\n")
    for f in targets:
        fn = root_function(f)
        others = [pr for pr in providers if pr != f["provider"]]
        cand_lines = []
        for pr in others:
            cs = pool.get((fn, pr), [])[:60]
            if not cs:
                cand_lines.append(f"{pr}: (no features found in this area)")
                continue
            cand_lines.append(f"{pr}:\n" + "\n".join(
                f"  - {c['name']}: {(c.get('scope_note') or '')[:140]}" for c in cs))
        subs = [c["name"] for c in children.get(f["id"], []) if c.get("kind") == "feature"]
        prompt = (
            f'FEATURE: "{f["name"]}" by {f["provider"]}\n'
            f'What it does: {(f.get("scope_note") or f["name"])[:300]}\n'
            f'Its listed sub-features: {", ".join(subs) or "(none)"}\n\n'
            f'CANDIDATE features from other providers in the same area '
            f'(pick the NEAREST equivalent for each provider, or none):\n'
            + "\n".join(cand_lines)
            + f'\n\nCompare specifically against "{f["name"]}". For EACH other provider, scan ALL its '
            f'candidates above and pick the single NEAREST equivalent by function (match its exact name); '
            f'only set match=null if genuinely none is comparable. Keep summary to <=2 sentences (~45 words) '
            f'and do not mention sub-feature attribution there. Return one equivalents entry per other '
            f'provider ({", ".join(others)}).')
        try:
            out = llm.structured(system=SYSTEM, prompt=prompt, schema=SCHEMA, label=f"compare:{f['id']}")
        except Exception as exc:  # one feature failing must not abort the sweep; skip it
            print(f"  SKIP {f['id']}: {type(exc).__name__}")
            continue
        f["comparison"] = {"summary": out.get("summary", ""),
                           "equivalents": [e for e in (out.get("equivalents") or []) if e.get("provider")]}
        if dry:
            print(f"\n=== {f['name']} ({f['provider']}) ===\n  {out.get('summary','')}")
            for e in f["comparison"]["equivalents"]:
                print(f"   {e['provider']}: {e.get('match') or '—'} — {e.get('note','')}")
            if out.get("offtopic_subfeatures"):
                print(f"   off-topic subs flagged: {out['offtopic_subfeatures']}")
        # drop mis-attached sub-features
        off = {_norm(s) for s in (out.get("offtopic_subfeatures") or [])}
        if off:
            kill = {c["id"] for c in children.get(f["id"], []) if _norm(c["name"]) in off}
            if kill:
                cat["products"] = [p for p in cat["products"] if p["id"] not in kill]
                dropped += len(kill)
        done += 1
        if done % 20 == 0:
            print(f"  {done}/{len(targets)}")

    if dry:
        print(f"\n[dry] {done} comparisons generated, not written")
        return 0
    issues = validate(cat)
    print(f"\ngenerated {done} comparisons; dropped {dropped} off-topic sub-features")
    print(f"catalog: {len(cat['products'])} products · {'valid' if not issues else f'{len(issues)} ISSUES'}")
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
