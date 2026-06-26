#!/usr/bin/env python3
"""Build the agentic-coding capability matrix as a PROJECTION of the grounded catalog.

The matrix is a different SCHEMA over the same data — NOT a separate grounding pipeline. Rows come
from matrix/capabilities.yaml (the neutral "what"). For each (capability x provider) an LLM SELECTS
the single best-matching, most-canonical feature **from the provider's real grounded catalog features**
(it can only choose a real node — it cannot invent or ground anything), and an adversarial pass rejects
weak/adjacent picks. The cell then carries that feature's REAL fields: its name (the "how"), lifecycle
status, first-party source URL, and grounded `scope_note` as the description. No generated prose.

Every grounded cell is therefore a real catalog node that already passed the catalog's full verification
(verbatim-quote grounding + 3-sample classification + triangulation + audit). Capabilities the catalog
doesn't cover are left `unverified` ("not yet covered"); close them by deepening the CATALOG via
`taxo discover` (see plan-matrix-verification.md), after which they populate here automatically.

  TAXO_OFFLINE=0 TAXO_LEDGER=record python scripts/build_matrix.py [--report]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import yaml
except ImportError:
    sys.exit("ERROR: PyYAML not installed. Run: python -m pip install pyyaml")

from taxonomy.config import settings        # noqa: E402
from taxonomy.vertex_client import get_llm    # noqa: E402

CAPS_YAML = ROOT / "matrix" / "capabilities.yaml"
CATALOG = ROOT / "data" / "taxonomy.json"
OUT = ROOT / "data" / "agentic-matrix.json"

PROVIDERS = [("anthropic", "Anthropic", "Claude Code", "anthropic-claude-code"),
             ("google", "Google", "Antigravity", "google-antigravity-2-0"),
             ("openai", "OpenAI", "Codex", "openai-codex")]
STATUS_MAP = {"active": "active", "preview": "preview", "beta": "preview", "deprecated": "sunset",
              "sunset": "sunset", "merged": "sunset", "renamed": "active", "absent": "none"}

MAP_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["mappings"],
    "properties": {"mappings": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["capability_id", "matched", "feature_index"],
        "properties": {
            "capability_id": {"type": "string"},
            "matched": {"type": "boolean"},
            "feature_index": {"type": "integer", "description": "1-based index of the best feature, 0 if matched=false"}}}}}}
MAP_SYSTEM = (
    "You map vendor-neutral capabilities to a provider's REAL, grounded features. For each capability, "
    "pick the single feature that BEST and most canonically realizes it — prefer the primary/representative "
    "feature over a narrow sub-feature (e.g. choose 'Subagents', not 'CSV Batch Subagent Processing'). "
    "If NO listed feature directly realizes the capability, set matched=false, feature_index=0 — a WRONG "
    "match is worse than NO match; a later step handles gaps. Only use features from the numbered list; "
    "never invent one. Return exactly one entry per capability_id."
)

CONFIRM_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["confirmations"],
    "properties": {"confirmations": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["capability_id", "realizes"],
        "properties": {"capability_id": {"type": "string"}, "realizes": {"type": "boolean"},
                       "reason": {"type": "string"}}}}}}
CONFIRM_SYSTEM = (
    "You are a strict reviewer of capability->feature matches. For each pair, decide whether the feature "
    "DIRECTLY and specifically realizes THIS capability — not an adjacent/sibling one. Classic traps to "
    "reject: context CACHING vs context COMPACTION; observability/'loop span' vs goal-directed ITERATION; "
    "inter-agent messaging vs a chat SURFACE like Slack; sandboxing vs access SURFACES. Tangential, partial, "
    "or category-adjacent -> realizes=false. A false rejection is fine (it becomes an honest gap); a false "
    "acceptance is not."
)


def descendants(by_parent, root):
    out, stack = [], list(by_parent.get(root, []))
    while stack:
        p = stack.pop(); out.append(p); stack += by_parent.get(p["id"], [])
    return out


def provider_features(catalog, root_id):
    by_parent = {}
    for p in catalog["products"]:
        by_parent.setdefault(p.get("parent_id"), []).append(p)
    feats = [p for p in descendants(by_parent, root_id)
             if p["kind"] in ("feature", "product", "platform") and p.get("review_status") != "scaffold"]
    seen, uniq = set(), []
    for f in sorted(feats, key=lambda x: x["name"].lower()):
        if f["id"] not in seen:
            seen.add(f["id"]); uniq.append(f)
    return uniq


def map_provider(llm, pkey, pname, product, feats, rows):
    feat_lines = "\n".join(f"  [{i+1}] {f['name']} — {(f.get('scope_note') or '')[:110]}" for i, f in enumerate(feats))
    cap_lines = "\n".join(f"  - {c['id']}: {c['name']} — {c['what']}" for c in rows)
    out = llm.structured(system=MAP_SYSTEM,
                         prompt=f"PROVIDER: {pname} ({product})\n\nFEATURES (numbered):\n{feat_lines}\n\nCAPABILITIES (one entry each):\n{cap_lines}",
                         schema=MAP_SCHEMA, label=f"matrixmap:{pkey}")
    return {m["capability_id"]: m for m in out.get("mappings", [])}


def confirm_provider(llm, pkey, pname, pairs):
    if not pairs:
        return {}
    lines = "\n".join(f"  - {cid}: \"{cname}\" ({cwhat})  vs feature \"{fname}\" ({(fscope or '')[:110]})"
                      for cid, cname, cwhat, fname, fscope in pairs)
    out = llm.structured(system=CONFIRM_SYSTEM,
                         prompt=f"PROVIDER: {pname}\nConfirm each feature directly realizes its capability:\n{lines}",
                         schema=CONFIRM_SCHEMA, label=f"matrixconfirm:{pkey}")
    return {c["capability_id"]: bool(c["realizes"]) for c in out.get("confirmations", [])}


def cell_for(product, feat):
    if not feat:
        return {"offering": product, "implementation": "unverified", "status": "unverified",
                "evidence_url": "", "last_verified": "",
                "description": "Not yet covered in the grounded catalog.", "notes": ""}
    src = feat.get("source") or {}
    return {"offering": product, "implementation": feat["name"],
            "status": STATUS_MAP.get(feat.get("status", "active"), "active"),
            "evidence_url": src.get("url", ""), "last_verified": src.get("last_verified", ""),
            "description": (feat.get("scope_note") or "").strip(), "notes": ""}


def main() -> int:
    cfg = settings()
    if cfg.offline:
        print("build_matrix selects via the LLM: set TAXO_OFFLINE=0.", file=sys.stderr)
        return 1
    caps = yaml.safe_load(CAPS_YAML.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = [c for g in caps["capability_groups"] for c in g["capabilities"]]
    llm = get_llm(cfg)

    chosen = {}   # pkey -> {cap_id: feat or None}
    for pkey, pname, product, root in PROVIDERS:
        feats = provider_features(catalog, root)
        mp = map_provider(llm, pkey, pname, product, feats, rows)
        pairs = []
        for c in rows:
            m = mp.get(c["id"])
            if m and m.get("matched") and 1 <= m.get("feature_index", 0) <= len(feats):
                f = feats[m["feature_index"] - 1]
                pairs.append((c["id"], c["name"], c["what"], f["name"], f.get("scope_note")))
        ok = confirm_provider(llm, pkey, pname, pairs)
        rej = sum(1 for cid in ok if not ok[cid])
        chosen[pkey] = {}
        for c in rows:
            m = mp.get(c["id"])
            f = None
            if (m and m.get("matched") and 1 <= m.get("feature_index", 0) <= len(feats)
                    and ok.get(c["id"], True)):
                f = feats[m["feature_index"] - 1]
            chosen[pkey][c["id"]] = f
        print(f"  {pname}: selected {sum(1 for v in chosen[pkey].values() if v)}/{len(rows)} "
              f"({rej} rejected by confirm)", file=sys.stderr)

    doc = {"product_category": caps["product_category"], "capability_groups": []}
    total = covered = 0
    mapping = []
    for g in caps["capability_groups"]:
        ng = {"name": g["name"], "layer": g["layer"], "capabilities": []}
        for c in g["capabilities"]:
            provs = {}
            for pkey, _, product, _ in PROVIDERS:
                f = chosen[pkey][c["id"]]
                total += 1
                if f:
                    covered += 1
                provs[pkey] = cell_for(product, f)
                mapping.append((c["id"], pkey, f["name"] if f else "—"))
            ng["capabilities"].append({"id": c["id"], "name": c["name"], "what": c["what"],
                                       "tier": c["tier"], "providers": provs})
        doc["capability_groups"].append(ng)

    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nprojected {total} cells: {covered} grounded, {total - covered} gaps (not yet in catalog)")
    if "--report" in sys.argv:
        print("\ncell -> catalog feature:")
        for cid, pk, fname in mapping:
            print(f"  {pk:9s} {cid:30s} <- {fname}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
