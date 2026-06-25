#!/usr/bin/env python3
"""Build the agentic-coding capability matrix as a GROUNDED PROJECTION of the catalog.

Rows come from matrix/capabilities.yaml (curated "what"). Cells (the per-provider "how") are
grounded automatically, escalating until something sticks:

  Stage A — project from the grounded catalog (data/taxonomy.json): a ledgered LLM mapper picks the
            best-matching grounded feature(s) for each capability; the cell inherits that feature's
            evidence_url / status / last_verified (no fabrication — evidence stays the catalog's).
  Stage B — official-doc grounding for cells Stage A can't fill (relevant_doc_pages + triage judge).   [P3]
  Stage C — live Tavily discovery restricted to the provider's official domains.                        [P3]
  else    — honest `unverified` (not a claim of absence).

Output: data/agentic-matrix.json (validated by scripts/validate_matrix.py).

  TAXO_OFFLINE=0 TAXO_LEDGER=record .venv/bin/python scripts/build_matrix.py            # full grounded build
  TAXO_OFFLINE=0 TAXO_LEDGER=record .venv/bin/python scripts/build_matrix.py --stage-a  # Stage A only (staging)

This module is P2 (Stage A). Stages B/C are wired in P3.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

import re  # noqa: E402

from taxonomy.config import settings  # noqa: E402
from taxonomy.doc_source import CachedPages, relevant_doc_pages  # noqa: E402
from taxonomy.provider_scan import CAPABILITY_CONFIG  # noqa: E402
from taxonomy.retrieval import get_retrieval  # noqa: E402
from taxonomy.sources import OFFICIAL_DOMAINS, derive_confidence, source_tier  # noqa: E402
from taxonomy.triage import _judge_grounding  # noqa: E402
from taxonomy.trust import grounding_gate  # noqa: E402
from taxonomy.vertex_client import get_llm  # noqa: E402

AS_OF = "2026-06-25"
PNAME = {"anthropic": "Anthropic", "google": "Google", "openai": "OpenAI"}
LIFECYCLE_MAP = {"active": "active", "preview": "preview", "beta": "preview",
                 "deprecated": "sunset", "sunset": "sunset", "unknown": "active"}
_slug = lambda s: re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:48]

# Stage C is restricted to TRUE first-party documentation hosts — NOT the engine's broad
# OFFICIAL_DOMAINS, which admits community forums (discuss./community.), blogs, and other products.
# A forum/blog/feature-request page mentioning a capability passes the quote gate but isn't evidence
# the provider *ships* it, so we never accept those here.
MATRIX_DOC_HOSTS = {
    "anthropic": ("docs.claude.com", "code.claude.com", "docs.anthropic.com"),
    "openai": ("developers.openai.com", "platform.openai.com"),
    "google": ("antigravity.google", "ai.google.dev"),
}
_BAD_SUBDOMAINS = {"discuss", "community", "blog", "forum", "support", "status"}


_BINARY_EXT = (".pdf", ".zip", ".gz", ".tar", ".png", ".jpg", ".jpeg", ".gif", ".svg",
               ".mp4", ".mov", ".woff", ".woff2", ".ico", ".webp", ".bin")
MAX_PAGE_CHARS = 1_000_000  # never ground against (or cache) a page bigger than this — guards against PDF/asset blobs


def _texty(url):
    u = (url or "").lower().split("?")[0].split("#")[0]
    return not u.endswith(_BINARY_EXT)


def _is_doc_host(url, pkey):
    from urllib.parse import urlparse
    u = urlparse(url or "")
    host = u.netloc.lower()
    if host.split(".")[0] in _BAD_SUBDOMAINS:
        return False
    if not any(host == h or host.endswith("." + h) for h in MATRIX_DOC_HOSTS.get(pkey, ())):
        return False
    return len([p for p in (u.path or "/").split("/") if p]) >= 1  # reject bare homepages

CAPS_YAML = ROOT / "matrix" / "capabilities.yaml"
CATALOG = ROOT / "data" / "taxonomy.json"
STAGE_A_OUT = ROOT / "data" / "_matrix_stageA.json"
FINAL_OUT = ROOT / "data" / "agentic-matrix.json"

PROVIDERS = [("anthropic", "Anthropic", "Claude Code", "anthropic-claude-code"),
             ("google", "Google", "Antigravity", "google-antigravity-2-0"),
             ("openai", "OpenAI", "Codex", "openai-codex")]

# catalog lifecycle status -> matrix enum
STATUS_MAP = {"active": "active", "preview": "preview", "beta": "preview",
              "deprecated": "sunset", "sunset": "sunset", "merged": "sunset",
              "renamed": "active", "absent": "none"}

MAP_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["mappings"],
    "properties": {"mappings": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["capability_id", "matched", "feature_index", "implementation", "confidence"],
        "properties": {
            "capability_id": {"type": "string"},
            "matched": {"type": "boolean"},
            "feature_index": {"type": "integer", "description": "1-based index of the best feature, or 0 if matched=false"},
            "implementation": {"type": "string", "description": "Concise real feature name(s) for the cell; '' if no match"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        }}}}}

SYSTEM = (
    "You map vendor-neutral capabilities to a provider's REAL, grounded features. For each capability, "
    "pick the single feature that DIRECTLY realizes it and write a concise `implementation` label using "
    "the provider's actual feature name(s).\n"
    "Be strict: a WRONG match is worse than NO match. If no listed feature directly realizes the "
    "capability, set matched=false and feature_index=0 — do NOT force a tangential, partial, or merely "
    "category-adjacent feature. A later grounding stage handles gaps, so leaving it unmatched is safe. "
    "Bad forced matches to avoid, for example: 'persistent memory' -> a 'Skills' feature; "
    "'prompt-injection protection' -> 'DNS rebinding protection'; 'plan mode' -> an 'artifact review' "
    "feature; 'prompt/context caching' -> 'container/environment caching'.\n"
    "Only use features from the list — never invent one. Return exactly one entry per capability_id given."
)

CONFIRM_SYSTEM = (
    "You are a strict adversarial reviewer of capability->feature matches. For each pair, decide whether "
    "the feature DIRECTLY realizes the capability for this provider. Tangential, partial, or merely "
    "category-adjacent features do NOT count -> realizes=false. A false rejection is acceptable (another "
    "grounding stage retries); a false acceptance is not. Judge only from the names/descriptions given."
)
CONFIRM_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["confirmations"],
    "properties": {"confirmations": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["capability_id", "realizes"],
        "properties": {"capability_id": {"type": "string"}, "realizes": {"type": "boolean"},
                       "reason": {"type": "string"}}}}}}


def descendants(products_by_parent, root):
    out, stack = [], list(products_by_parent.get(root, []))
    while stack:
        p = stack.pop(); out.append(p); stack += products_by_parent.get(p["id"], [])
    return out


def provider_features(catalog, root_id):
    by_parent = {}
    for p in catalog["products"]:
        by_parent.setdefault(p.get("parent_id"), []).append(p)
    feats = [p for p in descendants(by_parent, root_id)
             if p["kind"] in ("feature", "product", "platform") and p.get("review_status") != "scaffold"]
    # de-dup by id, stable order by name
    seen, uniq = set(), []
    for f in sorted(feats, key=lambda x: x["name"].lower()):
        if f["id"] not in seen:
            seen.add(f["id"]); uniq.append(f)
    return uniq


def cap_rows(caps_doc):
    rows = []
    for g in caps_doc["capability_groups"]:
        for c in g["capabilities"]:
            rows.append(c)
    return rows


def map_provider(llm, pkey, pname, product, feats, rows):
    feat_lines = "\n".join(
        f"  [{i+1}] {f['name']} — {(f.get('scope_note') or '')[:120]}" for i, f in enumerate(feats))
    cap_lines = "\n".join(f"  - {c['id']}: {c['name']} — {c['what']}" for c in rows)
    prompt = (f"PROVIDER: {pname} ({product})\n\n"
              f"FEATURES (numbered):\n{feat_lines}\n\n"
              f"CAPABILITIES to map (return one entry per id):\n{cap_lines}")
    out = llm.structured(system=SYSTEM, prompt=prompt, schema=MAP_SCHEMA, label=f"matrixmap:{pkey}")
    return {m["capability_id"]: m for m in out.get("mappings", [])}


def confirm_provider(llm, pkey, pname, pairs):
    """Adversarial second pass: reject weak/forced matches so they fall through to Stage B/C."""
    if not pairs:
        return {}
    lines = "\n".join(
        f"  - {cid}: capability \"{cname}\" ({cwhat})  vs  feature \"{fname}\" ({(fscope or '')[:120]})"
        for cid, cname, cwhat, fname, fscope in pairs)
    out = llm.structured(system=CONFIRM_SYSTEM,
                         prompt=f"PROVIDER: {pname}\nReview whether each feature directly realizes its capability:\n{lines}",
                         schema=CONFIRM_SCHEMA, label=f"matrixconfirm:{pkey}")
    return {c["capability_id"]: bool(c["realizes"]) for c in out.get("confirmations", [])}


def build_cell(pkey, pname, product, mapping, feats):
    if not mapping or not mapping.get("matched") or not (1 <= mapping.get("feature_index", 0) <= len(feats)):
        return {"offering": product, "implementation": "unverified", "status": "unverified",
                "evidence_url": "", "last_verified": "",
                "notes": "No first-party documentation found for this capability — left unverified rather than guessed."}
    f = feats[mapping["feature_index"] - 1]
    src = f.get("source") or {}
    return {"offering": product,
            "implementation": (mapping.get("implementation") or f["name"])[:120],
            "status": STATUS_MAP.get(f.get("status", "active"), "active"),
            "evidence_url": src.get("url", ""),
            "last_verified": src.get("last_verified", ""),
            "notes": f"Catalog-grounded via \"{f['name']}\"."}


def _ground_url(llm, retrieval, pkey, cap_id, cap_name, cap_what, url):
    """Judge whether the page at `url` supports '<provider> offers <capability>'. Returns judge dict or None."""
    rec = {"id": f"matrix-{pkey}-{_slug(cap_id)}", "provider": PNAME[pkey], "name": cap_name,
           "scope_note": cap_what, "source": {"url": url}}
    page, judge = _judge_grounding(rec, retrieval, llm)
    return judge if (judge and grounding_gate(rec, page, judge).passed) else None


def _cell_from_judge(pkey, product, url, judge):
    return {"offering": product,
            "status": LIFECYCLE_MAP.get(judge.get("lifecycle_status", "active"), "active"),
            "evidence_url": url, "last_verified": AS_OF,
            "confidence": derive_confidence(source_tier(url, PNAME[pkey])),
            "quote": (judge.get("found_quote") or "")[:160]}


def stage_b(llm, pkey, product, hints, cap_id, cap_name, cap_what):
    """Ground against the provider's official agentic-coding doc surface, filtered by the capability's hints."""
    doc_cfg = CAPABILITY_CONFIG["agentic-coding"][PNAME[pkey]]["doc"]
    try:
        pages = relevant_doc_pages(doc_cfg, hints, limit=8)
    except Exception:  # doc surface fetch failed — let Stage C try
        return None
    # never ground against binary (PDF/asset) or oversized pages — they bloat the ledger and aren't doc text
    pages = [p for p in (pages or []) if _texty(p.url) and len(p.text or "") <= MAX_PAGE_CHARS]
    if not pages:
        return None
    cached = CachedPages(pages)
    for pg in pages[:4]:
        try:
            judge = _ground_url(llm, cached, pkey, cap_id, cap_name, cap_what, pg.url)
        except Exception:  # one bad page must not abort the cell
            continue
        if judge:
            return _cell_from_judge(pkey, product, pg.url, judge)
    return None


def stage_c(llm, retrieval, pkey, product, cap_id, cap_name, cap_what):
    """Live Tavily discovery, restricted to the provider's official domains; accept official-tier pages only."""
    try:
        results = retrieval.search(f"{PNAME[pkey]} {product} {cap_name}", max_results=8,
                                   include_domains=list(MATRIX_DOC_HOSTS.get(pkey, ())))
    except (NotImplementedError, Exception):
        return None
    for r in results[:6]:
        if not _is_doc_host(r.url, pkey) or not _texty(r.url):   # first-party doc hosts only; no binary blobs
            continue
        try:
            judge = _ground_url(llm, retrieval, pkey, cap_id, cap_name, cap_what, r.url)
        except Exception:
            continue
        if judge:
            return _cell_from_judge(pkey, product, r.url, judge)
    return None


def main() -> int:
    cfg = settings()
    if cfg.offline:
        print("build_matrix needs live grounding for Stage A: set TAXO_OFFLINE=0.", file=sys.stderr)
        return 1
    caps_doc = yaml.safe_load(CAPS_YAML.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = cap_rows(caps_doc)
    llm = get_llm(cfg)
    retrieval = get_retrieval(cfg)

    mappings = {}
    for pkey, pname, product, root_id in PROVIDERS:
        feats = provider_features(catalog, root_id)
        print(f"  {pname}: {len(feats)} grounded features → mapping {len(rows)} capabilities …", file=sys.stderr)
        mp = map_provider(llm, pkey, pname, product, feats, rows)
        # Adversarial confirmation: drop weak/forced matches so they escalate to Stage B/C.
        pairs = []
        for c in rows:
            m = mp.get(c["id"])
            if m and m.get("matched") and 1 <= m.get("feature_index", 0) <= len(feats):
                f = feats[m["feature_index"] - 1]
                pairs.append((c["id"], c["name"], c["what"], f["name"], f.get("scope_note")))
        confirmed = confirm_provider(llm, pkey, pname, pairs)
        rejected = 0
        for cid, ok in confirmed.items():
            if not ok and cid in mp:
                mp[cid]["matched"] = False
                rejected += 1
        print(f"    confirmed {sum(confirmed.values())}/{len(pairs)} matches ({rejected} rejected → Stage B/C)", file=sys.stderr)
        mappings[pkey] = (mp, feats)

    by_stage = {"A": 0, "B": 0, "C": 0, "unverified": 0}
    doc = {"product_category": caps_doc["product_category"], "capability_groups": []}
    for g in caps_doc["capability_groups"]:
        ng = {"name": g["name"], "layer": g["layer"], "capabilities": []}
        for c in g["capabilities"]:
            cell_providers = {}
            for pkey, pname, product, _ in PROVIDERS:
                mp, feats = mappings[pkey]
                cell = build_cell(pkey, pname, product, mp.get(c["id"]), feats)
                if cell["status"] != "unverified":
                    by_stage["A"] += 1
                else:
                    # escalate: official docs (B) → live Tavily (C) → honest unverified
                    bc, stg = None, None
                    try:
                        bc = stage_b(llm, pkey, product, c.get("hints", []), c["id"], c["name"], c["what"])
                        if bc:
                            stg = "B"
                        else:
                            bc = stage_c(llm, retrieval, pkey, product, c["id"], c["name"], c["what"])
                            stg = "C" if bc else None
                    except Exception as exc:  # one cell's grounding must not abort the build
                        print(f"    grounding error {c['id']}/{pkey}: {type(exc).__name__}", file=sys.stderr)
                    if bc:
                        cell = {"offering": product, "implementation": c["name"], "status": bc["status"],
                                "evidence_url": bc["evidence_url"], "last_verified": bc["last_verified"],
                                "notes": (f"Grounded against official docs: “{bc['quote']}”"
                                          if bc.get("quote") else "Grounded against official docs.")}
                        by_stage[stg] += 1
                    else:
                        by_stage["unverified"] += 1
                cell_providers[pkey] = cell
            ng["capabilities"].append({"id": c["id"], "name": c["name"], "what": c["what"],
                                       "tier": c["tier"], "providers": cell_providers})
        doc["capability_groups"].append(ng)

    FINAL_OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(by_stage.values())
    print(f"\nwrote {FINAL_OUT.relative_to(ROOT)}: {total} cells — "
          f"A(catalog)={by_stage['A']}  B(docs)={by_stage['B']}  C(tavily)={by_stage['C']}  unverified={by_stage['unverified']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
