#!/usr/bin/env python3
"""Targeted Antigravity discovery sweep over UNMINED doc pages that map to current matrix gaps.

Reuses the catalog engine end-to-end (extract real features off the official .md page -> consolidate ->
triage: 3-sample classification + verbatim-quote grounding + schema gate), so every candidate is
grounded and gated exactly like the rest of the catalog. It STAGES results to data/_sweep_antigravity.json
for review — it does NOT touch data/taxonomy.json. Live + ledgered.

  TAXO_OFFLINE=0 TAXO_LEDGER=record python scripts/sweep_antigravity.py
"""
from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from taxonomy.config import settings                                  # noqa: E402
from taxonomy.doc_source import CachedPages, DocPage, _get            # noqa: E402
from taxonomy.provider_scan import consolidate_features, extract_features  # noqa: E402
from taxonomy.schema import DEFAULT_DATA_PATH                         # noqa: E402
from taxonomy.triage import triage_one                               # noqa: E402
from taxonomy.vertex_client import get_llm                           # noqa: E402

PRODUCT_ID, PROVIDER, PRODUCT = "google-antigravity-2-0", "Google", "Antigravity"
AS_OF = "2026-06-26"
BASE = "https://antigravity.google/assets/docs/"
# unmined pages chosen because they map onto current matrix gaps
PAGES = [
    "antigravity-2-0/models.md",            # model-selection
    "antigravity-2-0/mcp.md",               # mcp-authentication / mcp-*
    "antigravity-2-0/skills.md",            # packaged-extensions
    "antigravity-2-0/implementation-plan.md",  # plan-mode
    "plans/plans.md",                       # plan-mode
    "cli/cli-conversations.md",             # resume-session
    "cli/cli-credits.md",                   # cost-usage-tracking
    "cli/cli-reference.md",                 # checkpoint-rewind (/rewind), misc
    "cli/cli-best-practices.md",            # checkpoint-rewind, goal-directed
    "editor/ide-hooks.md",                  # lifecycle-hooks
    "editor/ide-workflows.md",              # workflows
    "enterprise/enterprise.md",             # cost / governance / audit
]
AXIS_NAME = "Agentic coding capabilities"
AXIS_DESC = "any notable, user-facing feature of the Antigravity agentic coding tool described on this page"
FEATURE_CAP = 5
_slug = lambda s: re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:48]


def sweep_page(path, llm, catalog):
    url = BASE + path
    try:
        text = _get(url)
    except Exception as e:  # one bad page must not abort the sweep
        return path, [], f"fetch failed: {type(e).__name__}"
    if not text or len(text) < 200:
        return path, [], f"thin/empty ({len(text or '')} chars)"
    cached = CachedPages([DocPage(url, text, path)])
    feats = [f for f in extract_features(llm, text, url, PROVIDER, PRODUCT, AXIS_NAME, AXIS_DESC) if f.get("name")]
    if not feats:
        return path, [], "nothing extracted"
    kept = []
    for cf in consolidate_features(llm, PROVIDER, PRODUCT, AXIS_NAME, feats)[:FEATURE_CAP]:
        status = cf.get("status") if cf.get("status") in ("active", "preview", "beta", "deprecated", "sunset") else "active"
        cand = {"id": f"{PRODUCT_ID}-disc-{_slug(cf['name'])}"[:96], "name": cf["name"], "kind": "feature",
                "parent_id": PRODUCT_ID, "provider": PROVIDER, "capability_ids": ["agentic-coding"],
                "primary_capability_id": "agentic-coding", "relation_within_capability": "direct",
                "surfaces": [], "status": status, "review_status": "candidate",
                "scope_note": (cf.get("claim") or "")[:280], "lifecycle": [],
                "source": {"url": url, "last_verified": AS_OF, "confidence": "low"}}
        try:
            out = triage_one(cand, dataset=catalog, llm=llm, retrieval=cached, evidence=cf.get("claim") or cf["name"])
        except Exception:
            continue
        if out.decision in ("confirmed", "needs_review"):
            r = out.record
            r["review_status"] = out.decision
            kept.append(r)
    return path, kept, f"{len(kept)} grounded"


def main() -> int:
    cfg = settings()
    if cfg.offline:
        sys.exit("sweep needs live grounding: set TAXO_OFFLINE=0.")
    llm = get_llm(cfg)
    catalog = json.loads(DEFAULT_DATA_PATH.read_text(encoding="utf-8"))
    print(f"sweeping {len(PAGES)} unmined Antigravity pages …\n", file=sys.stderr)

    records, summary = [], {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for path, kept, note in ex.map(lambda p: sweep_page(p, llm, catalog), PAGES):
            print(f"  {path}: {note}", file=sys.stderr)
            records.extend(kept)
            summary[path] = [(r["name"], r["primary_capability_id"], r["review_status"]) for r in kept]

    out_path = ROOT / "data" / "_sweep_antigravity.json"
    out_path.write_text(json.dumps({"as_of": AS_OF, "provider": PROVIDER, "records": records},
                                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nstaged {len(records)} grounded Antigravity features -> {out_path.relative_to(ROOT)} (NOT applied)")
    print("\n=== staged candidates by page (name [classified axis] decision) ===")
    for path, items in summary.items():
        if items:
            print(f"\n  {path}")
            for nm, ax, dec in items:
                print(f"     {nm}  [{ax}] {dec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
