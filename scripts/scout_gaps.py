#!/usr/bin/env python3
"""Scout the matrix's open gaps → ground from official docs → admit as CANDIDATES for review (scope-B, A1).

For each `unverified` matrix cell, Tavily-search the provider's official docs (scoped via
``include_domains``) using the row's hints, extract the feature the top result names, and admit it to the
CATALOG with ``review_status='candidate'`` — so the matrix shows it as ``needs_review`` until a human
confirms it via ``matrix/review-decisions.yaml``. Search is a discovery aid (NOT ledgered — `taxo verify`
replays grounding, not search); every admit goes through ``admit_grounded`` (reverify → replay-reproducible).
Audit trail → ``data/scout-log.jsonl`` (B2). The matrix stays a pure projection; this only feeds the catalog.

    TAXO_OFFLINE=0 TAVILY_API_KEY=… .venv/bin/python scripts/scout_gaps.py [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from taxonomy.config import settings                       # noqa: E402
from taxonomy.replay import AS_OF                           # noqa: E402
from taxonomy.retrieval import get_retrieval                # noqa: E402
from taxonomy.retrieval.base import RetrievalError          # noqa: E402
from taxonomy.schema import DEFAULT_DATA_PATH, load_dataset  # noqa: E402
from taxonomy.vertex_client import build_ledger, get_llm    # noqa: E402

from scripts.build_matrix import PROVIDERS                  # noqa: E402  (lineup roots)
from scripts.ground_gap import admit_grounded, _slug        # noqa: E402  (verify-safe admit)

CAPS_YAML = ROOT / "matrix" / "capabilities.yaml"
REVIEW_YAML = ROOT / "matrix" / "review-decisions.yaml"
MATRIX = ROOT / "data" / "agentic-matrix.json"
SCOUT_LOG = ROOT / "data" / "scout-log.jsonl"

# Search is scoped to the LINEUP's own doc hosts (coding agent + agent SDK) — NOT all of a provider's
# official domains. Using the broad set surfaces cross-product noise (e.g. cloud.google.com enterprise
# caching for an Antigravity row). These are the docs the lineup actually lives in.
LINEUP_DOMAINS = {
    "Anthropic": ["code.claude.com", "docs.claude.com"],
    "OpenAI": ["developers.openai.com", "openai.github.io"],
    "Google": ["antigravity.google", "adk.dev", "google.github.io"],
}

EXTRACT_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["feature_name", "realizes"],
    "properties": {
        "feature_name": {"type": "string", "description": "the provider's SHORT product name for the feature, or '' if none"},
        "realizes": {"type": "boolean", "description": "does the result actually describe a feature realizing the capability?"}}}
EXTRACT_SYSTEM = (
    "You map a vendor-neutral capability to a provider's real feature. Given the capability and ONE "
    "official-doc search result (title + snippet), return the SHORT name the provider uses for the feature "
    "that realizes the capability (e.g. 'Hooks', 'Plan Mode', 'Checkpointing') and whether the result "
    "actually describes such a feature. If it does not, set realizes=false and feature_name=''. Do not "
    "invent — the page is fetched and an independent judge must find a verbatim quote, so a wrong guess is "
    "rejected downstream; prefer realizes=false when unsure."
)


def _hints_by_cap():
    caps = yaml.safe_load(CAPS_YAML.read_text(encoding="utf-8"))
    return {c["id"]: (c.get("hints") or [], c["name"], c["what"])
            for g in caps["capability_groups"] for c in g["capabilities"]}


def _gaps(matrix):
    for g in matrix["capability_groups"]:
        for c in g["capabilities"]:
            for pk, cell in c["providers"].items():
                if cell.get("status") == "unverified":
                    yield c["id"], pk


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=8, help="max gaps to scout this run")
    ap.add_argument("--dry-run", action="store_true", help="search + extract, but do not ground/admit/write")
    args = ap.parse_args()

    cfg = settings()
    if cfg.offline or not cfg.tavily_api_key:
        print("scout needs live search: set TAXO_OFFLINE=0 and TAVILY_API_KEY.", file=sys.stderr)
        return 1
    llm, ledger = get_llm(cfg), build_ledger(cfg)
    retrieval = get_retrieval(cfg)                 # Tavily search + ledgered grounding-fetch
    catalog = load_dataset()
    as_of = (catalog.get("_meta") or {}).get("as_of") or AS_OF
    byid = {p["id"]: p for p in catalog["products"]}
    existing = set(byid)
    prov = {pk: (pname, roots, product) for pk, pname, product, roots in PROVIDERS}
    hb = _hints_by_cap()

    # Skip cells a human already adjudicated (confirm/reject) — don't re-propose settled decisions.
    adjudicated = set()
    if REVIEW_YAML.exists():
        rdoc = yaml.safe_load(REVIEW_YAML.read_text(encoding="utf-8")) or {}
        adjudicated = {(d["cap"], d["provider"]) for d in rdoc.get("decisions", [])}

    gaps = [(cid, pk) for cid, pk in _gaps(json.loads(MATRIX.read_text(encoding="utf-8")))
            if (cid, pk) not in adjudicated][: args.limit]
    print(f"scouting {len(gaps)} gap(s){' (dry-run)' if args.dry_run else ''}\n")
    admitted, log_rows = 0, []
    for cap_id, pk in gaps:
        hints, cap_name, cap_what = hb.get(cap_id, ([], cap_id, ""))
        pname, roots, product = prov[pk]
        root = roots[0]
        root_cap = byid[root]["primary_capability_id"]
        domains = LINEUP_DOMAINS.get(pname, [])
        query = f"{product} {cap_name} " + " ".join(hints[:4])
        try:
            results = retrieval.search(query, include_domains=domains, max_results=5)
        except (RetrievalError, NotImplementedError) as exc:   # search backend down/keyless — skip this gap
            print(f"  {cap_id:26} {pk:9} search failed: {exc}")
            continue
        results = [r for r in results if any(d in urlparse(r.url).netloc for d in domains)]  # enforce scope
        if not results:
            print(f"  {cap_id:26} {pk:9} no first-party result")
            continue
        top = results[0]
        ext = llm.structured(system=EXTRACT_SYSTEM,
                             prompt=f"CAPABILITY: {cap_name} — {cap_what}\n\nRESULT:\n  title: {top.title}\n  snippet: {top.snippet}\n  url: {top.url}",
                             schema=EXTRACT_SCHEMA, label=f"scoutextract:{cap_id}:{pk}")
        name = (ext.get("feature_name") or "").strip()
        if not ext.get("realizes") or not name:
            print(f"  {cap_id:26} {pk:9} no feature on top result ({top.url})")
            continue
        rid = f"{root}-{_slug(name)}"
        if rid in existing:
            print(f"  {cap_id:26} {pk:9} '{name}' already present ({rid})")
            continue
        if args.dry_run:
            print(f"  {cap_id:26} {pk:9} WOULD ground '{name}' ← {top.url}")
            continue
        decision, rec, score = admit_grounded(pname, root, name, "feature", root_cap, top.url,
                                              catalog=catalog, llm=llm, retrieval=retrieval, ledger=ledger,
                                              as_of=as_of, review_status="candidate",
                                              scope_note=(top.snippet or "").strip())
        log_rows.append({"as_of": as_of, "cap": cap_id, "provider": pk, "feature": name,
                         "url": top.url, "query": query, "snippet": top.snippet[:200],
                         "decision": decision, "grounding": round(score, 2)})
        if rec is not None:
            catalog["products"].append(rec)
            existing.add(rid)
            DEFAULT_DATA_PATH.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
            admitted += 1
            print(f"  {cap_id:26} {pk:9} ADMIT candidate '{name}' [grounding {score:.2f}] ← {top.url}")
        else:
            print(f"  {cap_id:26} {pk:9} grounding rejected '{name}' [{score:.2f}] — left a gap")

    if log_rows:   # B2 audit trail — durable + decoupled from verify (which rewrites provenance receipts)
        with SCOUT_LOG.open("a", encoding="utf-8") as f:
            for r in log_rows:
                f.write(json.dumps(r) + "\n")
    print(f"\nadmitted {admitted} candidate(s); review via the matrix → matrix/review-decisions.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
