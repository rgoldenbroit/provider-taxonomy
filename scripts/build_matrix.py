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
import re
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
REVIEW_YAML = ROOT / "matrix" / "review-decisions.yaml"   # human adjudication layer (optional)
CATALOG = ROOT / "data" / "taxonomy.json"
OUT = ROOT / "data" / "agentic-matrix.json"

# Each column is the provider's agentic-coding LINEUP — the coding agent PLUS its agent-building SDK —
# not a single product node. Claude Code is built on the Agent SDK, where capabilities like session
# rewind/checkpointing are modelled; a single-product column structurally can't see them, which is how
# the checkpoint/rewind row went false-empty. The first root is the column's headline product; features
# drawn from a sibling root are tagged with their provenance in the cell `notes`.
PROVIDERS = [("anthropic", "Anthropic", "Claude Code",
              ["anthropic-claude-code", "anthropic-claude-agent-sdk"]),
             ("google", "Google", "Antigravity",
              ["google-antigravity-2-0", "google-agent-development-kit-adk"]),
             ("openai", "OpenAI", "Codex",
              ["openai-codex", "openai-openai-agents-sdk"])]
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
        "type": "object", "additionalProperties": False, "required": ["capability_id", "realizes", "reason"],
        "properties": {"capability_id": {"type": "string"}, "realizes": {"type": "boolean"},
                       "reason": {"type": "string"}}}}}}
CONFIRM_SYSTEM = (
    "You are a strict reviewer of capability->feature matches. For each pair, decide whether the feature "
    "DIRECTLY and specifically realizes THIS capability — not an adjacent/sibling one. Classic traps to "
    "reject: context CACHING vs context COMPACTION; observability/'loop span' vs goal-directed ITERATION; "
    "inter-agent messaging vs a chat SURFACE like Slack; sandboxing vs access SURFACES. Tangential, partial, "
    "or category-adjacent -> realizes=false. A false rejection is fine (it becomes an honest gap); a false "
    "acceptance is not. Give a brief `reason` for every verdict."
)


def descendants(by_parent, root):
    out, stack = [], list(by_parent.get(root, []))
    while stack:
        p = stack.pop(); out.append(p); stack += by_parent.get(p["id"], [])
    return out


def provider_features(catalog, roots):
    """Union the grounded features across the column's lineup roots (coding agent + agent SDK), deduped.
    Each feature is tagged with `_root` (the lineup root it came from) so cells can cite provenance."""
    by_parent = {}
    for p in catalog["products"]:
        by_parent.setdefault(p.get("parent_id"), []).append(p)
    seen, uniq = set(), []
    for root_id in roots:
        feats = [p for p in descendants(by_parent, root_id)
                 if p["kind"] in ("feature", "product", "platform") and p.get("review_status") != "scaffold"]
        for f in sorted(feats, key=lambda x: x["name"].lower()):
            if f["id"] not in seen:
                seen.add(f["id"]); f["_root"] = root_id; uniq.append(f)
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
    return {c["capability_id"]: {"ok": bool(c["realizes"]), "reason": (c.get("reason") or "").strip()}
            for c in out.get("confirmations", [])}


# Inflectional suffixes: "rewind" must match "rewinding", "checkpoint" must match "checkpointing".
# Without this, the keyword candidate-finder misses real features (the recall bug behind the Google/
# Anthropic false-empty checkpoint cells) — it can't be the gate, but it must not silently undercount.
_SUFFIX = r"(?:s|es|ed|ing|ings|ment|ments|able|er|ers)?"


def _hit(hint, text):
    return re.search(r"(?<![a-z0-9])" + re.escape(hint.lower()) + _SUFFIX + r"(?![a-z0-9])", text) is not None


def top_candidates(feats, hints, n=3):
    """Hint-matching catalog features (for the gap breakdown) — does an appropriate feature even exist?"""
    scored = []
    for f in feats:
        nm, sc = f["name"].lower(), (f.get("scope_note") or "").lower()
        nh = sum(1 for h in hints if _hit(h, nm))
        sh = sum(1 for h in hints if _hit(h, sc))
        if nh or sh:
            scored.append(((nh, sh), f))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [f for _, f in scored[:n]]


REPICK_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["repicks"],
    "properties": {"repicks": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["capability_id", "feature_index"],
        "properties": {"capability_id": {"type": "string"}, "feature_index": {"type": "integer"}}}}}}
REPICK_SYSTEM = (
    "You re-select features after a strict reviewer REJECTED your earlier picks. For each capability, "
    "choose a DIFFERENT numbered feature that DIRECTLY and specifically realizes it — not the rejected "
    "feature, not an already-tried index, not an adjacent concept. If no remaining feature truly fits, "
    "return feature_index=0 — a wrong pick is worse than none."
)


def repick(llm, pkey, pname, feats, items, tried):
    feat_lines = "\n".join(f"  [{i+1}] {f['name']} — {(f.get('scope_note') or '')[:110]}" for i, f in enumerate(feats))
    item_lines = "\n".join(
        f"  - {cid}: {name} — {what}\n      rejected \"{rn}\": {rr}; already tried: {sorted(tried.get(cid, set()))}"
        for cid, name, what, rn, rr in items)
    out = llm.structured(system=REPICK_SYSTEM,
                         prompt=f"PROVIDER: {pname}\n\nFEATURES (numbered):\n{feat_lines}\n\nRE-PICK a different index (or 0 if none fits):\n{item_lines}",
                         schema=REPICK_SCHEMA, label=f"matrixrepick:{pkey}")
    return {r["capability_id"]: r["feature_index"] for r in out.get("repicks", [])}


RECONSIDER_SYSTEM = (
    "You are re-examining capabilities a first pass left UNMATCHED. For each, look carefully at the "
    "numbered features and pick the one that DIRECTLY and specifically realizes it (not an adjacent "
    "concept), or feature_index=0 if no feature truly fits — a wrong pick is worse than none."
)


def reconsider(llm, pkey, pname, feats, skipped):
    """Give the mapper a second look at cells it left empty (so a clean fit it overlooked isn't lost)."""
    feat_lines = "\n".join(f"  [{i+1}] {f['name']} — {(f.get('scope_note') or '')[:110]}" for i, f in enumerate(feats))
    item_lines = "\n".join(f"  - {cid}: {name} — {what}" for cid, name, what in skipped)
    out = llm.structured(system=RECONSIDER_SYSTEM,
                         prompt=f"PROVIDER: {pname}\n\nFEATURES (numbered):\n{feat_lines}\n\nUNMATCHED capabilities — pick a feature index or 0:\n{item_lines}",
                         schema=REPICK_SCHEMA, label=f"matrixreconsider:{pkey}")
    return {r["capability_id"]: r["feature_index"] for r in out.get("repicks", [])}


DISPROVE_SYSTEM = (
    "Each capability below is about to be recorded as NOT SUPPORTED by this provider — a strong, "
    "falsifiable claim. Your job is to REFUTE it. From the numbered features, pick the one that genuinely "
    "realizes the capability. Prefer finding a real match — default to a plausible candidate rather than "
    "0. Return feature_index=0 ONLY if, after a careful read, NO listed feature truly realizes it. A "
    "downstream reviewer removes wrong picks, so erring toward a candidate is safe; a silent false "
    "'absent' is not."
)


def disprove(llm, pkey, pname, feats, gaps):
    """Adversarial-absence gate: the recall counterpart to confirm_provider. For cells about to be marked
    a gap, try to find a real lineup feature that refutes the absence. Generous by design — every hit
    still passes the SAME strict confirm gate before it grounds, so recall rises without losing precision."""
    feat_lines = "\n".join(f"  [{i+1}] {f['name']} — {(f.get('scope_note') or '')[:110]}" for i, f in enumerate(feats))
    item_lines = "\n".join(f"  - {cid}: {name} — {what}" for cid, name, what in gaps)
    out = llm.structured(system=DISPROVE_SYSTEM,
                         prompt=f"PROVIDER: {pname}\n\nFEATURES (numbered):\n{feat_lines}\n\nThese capabilities are about to be marked NOT SUPPORTED — refute each (pick an index) or 0 if truly absent:\n{item_lines}",
                         schema=REPICK_SCHEMA, label=f"matrixdisprove:{pkey}")
    return {r["capability_id"]: r["feature_index"] for r in out.get("repicks", [])}


def select_provider(llm, pkey, pname, product, feats, rows, max_rounds=3):
    """Map -> confirm -> (on rejection) re-pick a different feature -> re-confirm. A cell is grounded only
    once a pick PASSES confirm; the re-pick recovers genuine misses without weakening the gate."""
    mp = map_provider(llm, pkey, pname, product, feats, rows)
    rowby = {c["id"]: c for c in rows}
    cur, tried, confirmed, diag = {}, {}, {}, {}
    for c in rows:
        m = mp.get(c["id"])
        if m and m.get("matched") and 1 <= m.get("feature_index", 0) <= len(feats):
            cur[c["id"]] = m["feature_index"]
            tried.setdefault(c["id"], set()).add(m["feature_index"])
        else:
            diag[c["id"]] = "mapper: no feature selected"
    # second look at cells the mapper skipped — any pick still has to pass the same strict confirm below
    skipped = [(c["id"], c["name"], c["what"]) for c in rows if c["id"] not in cur]
    if skipped:
        for cid, idx in reconsider(llm, pkey, pname, feats, skipped).items():
            if 1 <= idx <= len(feats) and idx not in tried.get(cid, set()):
                cur[cid] = idx
                tried.setdefault(cid, set()).add(idx)
                diag.pop(cid, None)
    for _ in range(max_rounds):
        pending = {cid: idx for cid, idx in cur.items() if cid not in confirmed}
        if not pending:
            break
        pairs = [(cid, rowby[cid]["name"], rowby[cid]["what"], feats[idx-1]["name"], feats[idx-1].get("scope_note"))
                 for cid, idx in pending.items()]
        ok = confirm_provider(llm, pkey, pname, pairs)
        rejected = []
        for cid, idx in pending.items():
            v = ok.get(cid)
            if v and v["ok"]:
                confirmed[cid] = feats[idx-1]
                diag.pop(cid, None)
            else:
                rejected.append((cid, rowby[cid]["name"], rowby[cid]["what"], feats[idx-1]["name"], (v or {}).get("reason", "")))
                diag[cid] = f"confirm rejected \"{feats[idx-1]['name']}\": {(v or {}).get('reason') or '(no reason)'}"
                cur.pop(cid, None)
        if not rejected:
            break
        rep = repick(llm, pkey, pname, feats, rejected, tried)
        progressed = False
        for cid, idx in rep.items():
            if 1 <= idx <= len(feats) and idx not in tried.get(cid, set()):
                cur[cid] = idx
                tried.setdefault(cid, set()).add(idx)
                progressed = True
        if not progressed:
            break
    # adversarial-absence gate: every still-empty cell is about to become a gap — make the model refute
    # it from the lineup before we allow that claim. Any hit goes through the SAME confirm gate.
    gaps = [(c["id"], rowby[c["id"]]["name"], rowby[c["id"]]["what"]) for c in rows if c["id"] not in confirmed]
    if gaps:
        dp_pending = {}
        for cid, idx in disprove(llm, pkey, pname, feats, gaps).items():
            if 1 <= idx <= len(feats) and idx not in tried.get(cid, set()):
                dp_pending[cid] = idx
                tried.setdefault(cid, set()).add(idx)
        if dp_pending:
            pairs = [(cid, rowby[cid]["name"], rowby[cid]["what"], feats[idx-1]["name"], feats[idx-1].get("scope_note"))
                     for cid, idx in dp_pending.items()]
            ok = confirm_provider(llm, pkey, pname, pairs)
            for cid, idx in dp_pending.items():
                v = ok.get(cid)
                if v and v["ok"]:                          # refuted the gap AND passed confirm -> grounded
                    confirmed[cid] = feats[idx-1]
                    diag.pop(cid, None)
                else:                                      # candidate exists but confirm won't admit it
                    diag[cid] = (f"disprover picked \"{feats[idx-1]['name']}\" but confirm rejected: "
                                 f"{(v or {}).get('reason') or '(no reason)'}")
    return {c["id"]: confirmed.get(c["id"]) for c in rows}, diag


def _provenance(feat, primary_root, root_label):
    """Note the sibling product a feature was drawn from, when it's not the column's headline root."""
    r = feat.get("_root")
    if r and primary_root and r != primary_root and root_label:
        return f"via {root_label.get(r, r)}"
    return ""


def cell_for(product, feat, primary_root=None, root_label=None):
    if not feat:
        return {"offering": product, "implementation": "unverified", "status": "unverified",
                "evidence_url": "", "last_verified": "",
                "description": "Not yet covered in the grounded catalog.", "notes": ""}
    src = feat.get("source") or {}
    return {"offering": product, "implementation": feat["name"],
            "status": STATUS_MAP.get(feat.get("status", "active"), "active"),
            "evidence_url": src.get("url", ""), "last_verified": src.get("last_verified", ""),
            "description": (feat.get("scope_note") or "").strip(),
            "notes": _provenance(feat, primary_root, root_label)}


def review_cell(product, feat, primary_root=None, root_label=None):
    """The confirm pass didn't admit a pick, but the lineup DOES hold a hint-matching feature for this
    capability. Surface it as `needs_review` (a candidate exists, unconfirmed) — never as a bare absence.
    This is the floor that makes a false gap structurally impossible when the catalog has the data."""
    src = feat.get("source") or {}
    prov = _provenance(feat, primary_root, root_label)
    note = "Lineup holds a matching feature the confirm pass hasn't admitted; needs human review."
    return {"offering": product, "implementation": feat["name"], "status": "needs_review",
            "evidence_url": src.get("url", ""), "last_verified": src.get("last_verified", ""),
            "description": (feat.get("scope_note") or "").strip(),
            "notes": f"{prov}; {note}" if prov else note}


def main() -> int:
    cfg = settings()
    if cfg.offline:
        print("build_matrix selects via the LLM: set TAXO_OFFLINE=0.", file=sys.stderr)
        return 1
    caps = yaml.safe_load(CAPS_YAML.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = [c for g in caps["capability_groups"] for c in g["capabilities"]]
    root_label = {p["id"]: p["name"] for p in catalog["products"] if not p.get("parent_id")}
    reviews = {}   # (cap_id, provider) -> human verdict; applied AFTER the automated pass
    if REVIEW_YAML.exists():
        rdoc = yaml.safe_load(REVIEW_YAML.read_text(encoding="utf-8")) or {}
        for d in rdoc.get("decisions", []):
            reviews[(d["cap"], d["provider"])] = d
    llm = get_llm(cfg)

    chosen, featmap, diag = {}, {}, {}   # diag[(pkey, cap_id)] = why a cell ended up a gap
    for pkey, pname, product, roots in PROVIDERS:
        feats = provider_features(catalog, roots)
        featmap[pkey] = feats
        sel, dg = select_provider(llm, pkey, pname, product, feats, rows)   # map -> confirm -> re-pick
        chosen[pkey] = sel
        for cid, reason in dg.items():
            diag[(pkey, cid)] = reason
        print(f"  {pname}: selected {sum(1 for x in sel.values() if x)}/{len(rows)}", file=sys.stderr)

    doc = {"product_category": caps["product_category"], "capability_groups": []}
    total = covered = review = 0
    mapping = []
    for g in caps["capability_groups"]:
        ng = {"name": g["name"], "layer": g["layer"], "capabilities": []}
        for c in g["capabilities"]:
            provs = {}
            for pkey, _, product, roots in PROVIDERS:
                primary = roots[0]
                cid = c["id"]
                dec = reviews.get((cid, pkey))
                f = chosen[pkey][cid]
                total += 1
                if dec and dec.get("verdict") == "reject":   # human override -> honest gap (even over a pick)
                    cell = cell_for(product, None, primary, root_label)
                    cell["notes"] = f"Reviewed → gap: {dec.get('reason', '').strip()}"
                    provs[pkey] = cell
                    mapping.append((cid, pkey, "— (reviewed)"))
                elif f:                                # confirmed pick — grounded
                    covered += 1
                    provs[pkey] = cell_for(product, f, primary, root_label)
                    mapping.append((cid, pkey, f["name"]))
                else:
                    cand = top_candidates(featmap[pkey], c.get("hints", []), 1)
                    # human confirm promotes a needs_review candidate -> grounded, but only if it's still
                    # the same surfaced feature (else the candidate changed and it returns to review).
                    if cand and dec and dec.get("verdict") == "confirm" \
                            and (not dec.get("feature") or dec["feature"] == cand[0]["name"]):
                        covered += 1
                        cell = cell_for(product, cand[0], primary, root_label)
                        prov_note = cell.get("notes", "")
                        cell["notes"] = (prov_note + "; " if prov_note else "") + f"human-confirmed {dec.get('date', '')}".strip()
                        provs[pkey] = cell
                        mapping.append((cid, pkey, f"{cand[0]['name']} (confirmed)"))
                    elif cand:                         # gap-floor — lineup HAS a candidate -> needs_review
                        review += 1
                        provs[pkey] = review_cell(product, cand[0], primary, root_label)
                        mapping.append((cid, pkey, f"needs_review: {cand[0]['name']}"))
                    else:                              # no candidate anywhere -> earned gap
                        provs[pkey] = cell_for(product, None, primary, root_label)
                        mapping.append((cid, pkey, "—"))
            ng["capabilities"].append({"id": c["id"], "name": c["name"], "what": c["what"],
                                       "tier": c["tier"], "providers": provs})
        doc["capability_groups"].append(ng)

    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nprojected {total} cells: {covered} grounded, {review} needs-review (candidate in lineup, "
          f"unconfirmed), {total - covered - review} true gaps (no candidate found)")

    if "--report" in sys.argv:
        print("\ncell -> catalog feature:")
        for cid, pk, fname in mapping:
            print(f"  {pk:9s} {cid:30s} <- {fname}")
    if "--gaps" in sys.argv:
        print("\n=== GAP BREAKDOWN — why each gap, + top hint-matching catalog candidates for review ===")
        for pkey, pname, _, _ in PROVIDERS:
            for c in rows:
                if chosen[pkey][c["id"]]:
                    continue
                cands = top_candidates(featmap[pkey], c["hints"], 3)
                tag = "no candidate -> TRUE GAP" if not cands else "candidate(s) exist -> review"
                print(f"\n  {pname} / {c['id']}  [{tag}]")
                print(f"      why: {diag.get((pkey, c['id']), '?')}")
                for f in cands:
                    print(f"      cand: {f['name']}  ::  {(f.get('scope_note') or '')[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
