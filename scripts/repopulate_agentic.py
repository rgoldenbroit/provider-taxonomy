"""Provider-first repopulation of the Agentic Coding axes (automated, grounded, real-named).

Pipeline per (provider × axis):
  retrieve the provider's structured doc surface (taxonomy/doc_source) → extract real-named features
  off the clean markdown → consolidate facets into a small comparable set → ground each top-level
  feature against its cited official page → keep sub-features that are present on that page.

Names come from the docs; admit only what grounds; every node parented to a product.

  TAXO_OFFLINE=0 .venv/bin/python scripts/repopulate_agentic.py              # full sweep (all axes) → staging
  TAXO_OFFLINE=0 .venv/bin/python scripts/repopulate_agentic.py <axis_id>    # one axis → staging

Writes records to data/_sweep_records.json (a later, reviewed step swaps them into the catalog).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from taxonomy.config import settings  # noqa: E402
from taxonomy.doc_source import CachedPages, relevant_doc_pages  # noqa: E402
from taxonomy.provider_scan import CAPABILITY_CONFIG, consolidate_features, extract_features  # noqa: E402
from taxonomy.retrieval.base import RetrievalError  # noqa: E402
from taxonomy.schema import DEFAULT_DATA_PATH  # noqa: E402
from taxonomy.triage import triage_one  # noqa: E402
from taxonomy.vertex_client import get_llm  # noqa: E402

AS_OF = "2026-06-22"
FEATURE_CAP = 6

AXIS_KEYWORDS = {  # agentic-coding axes
    "subagents-orchestration": ["subagent", "sub-agent", "multi-agent", "multi agent", "orchestrat",
                                "parallel agent", "agent team", "agent manager", "delegat", "spawn"],
    "managed-agent-runtime": ["managed agent", "hosted", "runtime", "cloud agent", "background agent",
                              "async task", "remote execution", "agent runtime", "schedule"],
    "agent-memory": ["memory", "remember", "persistent", "agents.md", "claude.md", "knowledge",
                     "context file", "recall", "rules"],
    "mcp-connectors": ["mcp", "model context protocol", "connector", "mcp server", "integration",
                       "external tool"],
    "code-execution-sandbox": ["sandbox", "isolation", "network access", "filesystem", "container",
                               "execution environment", "permission"],
    "guardrails-safety": ["guardrail", "safety", "permission", "approval", "allowlist", "denylist",
                          "security", "review", "trust"],
    "agent-evals-observability": ["eval", "observability", "trace", "logging", "monitor", "metric",
                                  "telemetry", "debug"],
    "remote-agent-control": ["remote", "async", "cloud", "on the web", "delegate", "background task",
                             "pull request", "headless"],
}

# enterprise-agent-platform reuses cross-cutting axes, keyworded for enterprise/cloud docs.
ENTERPRISE_AXES = {
    "managed-agent-runtime": ["agent engine", "managed runtime", "deploy", "hosting", "serverless",
                              "scale", "endpoint", "runtime", "reasoning engine", "fully managed"],
    "guardrails-safety": ["governance", "iam", "permission", "vpc service controls", "security",
                          "compliance", "policy", "access control", "guardrail", "safety", "data residency"],
    "agent-evals-observability": ["observability", "monitoring", "trace", "cloud trace", "logging",
                                  "metrics", "evaluation", "eval", "telemetry", "tracing", "dashboard"],
    "mcp-connectors": ["connector", "integration", "mcp", "tool", "data store", "grounding",
                       "data source", "extension", "function calling"],
    "agent-memory": ["memory", "memory bank", "session", "state", "context", "rag", "example store"],
}

CAPABILITY_AXES = {
    "agentic-coding": AXIS_KEYWORDS,
    "enterprise-agent-platform": ENTERPRISE_AXES,
}

_norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
_host = lambda u: urlparse(u or "").netloc
_slug = lambda s: re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:48]


def _is_noise(name: str) -> bool:
    n = (name or "").strip()
    if not n or n.startswith("/") or n.startswith("--") or "=" in n:
        return True
    if " " not in n and ("_" in n or re.match(r"^[a-z]+(?:[A-Z][a-z0-9]+)+$", n)):
        return True
    return False


def _present(name: str, text: str) -> bool:
    """A sub-feature is admitted only if its significant words actually appear on the cited page."""
    words = [w for w in re.findall(r"[a-z0-9]+", (name or "").lower()) if len(w) > 2]
    if not words:
        return False
    t = text.lower()
    return sum(w in t for w in words) / len(words) >= 0.6


def _feat_record(provider, product_id, axis, name, claim, url, status, review):
    return {
        "id": f"{product_id}-{axis}-{_slug(name)}"[:96], "name": name, "kind": "feature",
        "parent_id": product_id, "provider": provider, "capability_ids": [axis],
        "primary_capability_id": axis, "relation_within_capability": "direct", "surfaces": [],
        "status": status if status in ("active", "preview", "beta", "deprecated", "sunset") else "active",
        "review_status": review, "scope_note": (claim or "")[:280], "lifecycle": [],
        "source": {"url": url, "last_verified": AS_OF, "confidence": "low"},
    }


def _sub_record(provider, parent_id, axis, name, url):
    return {
        "id": f"{parent_id}-{_slug(name)}"[:96], "name": name, "kind": "feature",
        "parent_id": parent_id, "provider": provider, "capability_ids": [axis],
        "primary_capability_id": axis, "relation_within_capability": "partial", "surfaces": [],
        "status": "active", "review_status": "confirmed", "scope_note": "", "lifecycle": [],
        "source": {"url": url, "last_verified": AS_OF, "confidence": "low"},
    }


def scan_provider(provider, meta, cfg_axis, kws, catalog, llm):
    axis_id, axis_name, axis_desc = cfg_axis
    pages = relevant_doc_pages(meta["doc"], kws)
    if not pages:
        return [], [f"  no doc pages ({axis_id})"]
    cached = CachedPages(pages)
    page_text = {p.url: p.text for p in pages}
    log = [f"  {len(pages)} page(s): {', '.join(sorted({_host(p.url) for p in pages}))}"]

    extracted = [f for p in pages
                 for f in extract_features(llm, p.text, p.url, provider, meta["product"], axis_name, axis_desc)
                 if not _is_noise(f.get("name"))]
    if not extracted:
        return [], log + ["  nothing extracted"]
    consolidated = consolidate_features(llm, provider, meta["product"], axis_name, extracted)[:FEATURE_CAP]

    records, ids = [], set()
    for cf in consolidated:
        url = cf.get("source_url") if cf.get("source_url") in page_text else pages[0].url
        cand = _feat_record(provider, meta["product_id"], axis_id, cf["name"], cf.get("claim"),
                            url, cf.get("status"), "candidate")
        try:
            out = triage_one(cand, dataset=catalog, llm=llm, retrieval=cached,
                             evidence=cf.get("claim") or cf["name"], pinned_capability=axis_id)
        except (RetrievalError, NotImplementedError):
            continue
        if out.decision not in ("confirmed", "needs_review"):
            log.append(f"  drop         {cf['name']} (ungrounded)")
            continue
        rec = out.record
        rec["kind"], rec["parent_id"] = "feature", meta["product_id"]
        rec["primary_capability_id"], rec["capability_ids"] = axis_id, [axis_id]
        rec["id"], rec["review_status"] = cand["id"], out.decision
        if rec["id"] in ids:
            continue
        ids.add(rec["id"])
        records.append(rec)
        log.append(f"  {out.decision.upper():12} [g {out.report.grounding.score:.2f}] {cf['name']}")
        ptext = page_text.get(url, "")
        for sub in (cf.get("subfeatures") or [])[:8]:
            if _present(sub, ptext):
                sr = _sub_record(provider, rec["id"], axis_id, sub, url)
                if sr["id"] not in ids:
                    ids.add(sr["id"])
                    records.append(sr)
    return records, log


def main() -> int:
    flags = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    global AS_OF
    AS_OF = flags.get("as_of", AS_OF)
    capability = flags.get("capability", "agentic-coding")
    config = CAPABILITY_CONFIG.get(capability)
    kw_map = CAPABILITY_AXES.get(capability)
    if not config or not kw_map:
        print(f"unknown capability {capability!r}; known: {list(CAPABILITY_CONFIG)}", file=sys.stderr)
        return 1
    cfg = settings()
    if cfg.offline:
        print("repopulate needs live grounding: set TAXO_OFFLINE=0.", file=sys.stderr)
        return 1
    catalog = json.loads(DEFAULT_DATA_PATH.read_text(encoding="utf-8"))
    cap_by_id = {c["id"]: c for c in catalog["capabilities"]}
    axes = [args[0]] if args else list(kw_map)
    llm = get_llm(cfg)

    all_records, summary = [], {}
    for axis_id in axes:
        cap = cap_by_id.get(axis_id)
        if not cap:
            print(f"  skip unknown axis {axis_id}")
            continue
        cfg_axis = (axis_id, cap["name"], cap.get("description", ""))
        kws = kw_map.get(axis_id, [cap["name"].lower()])
        print(f"\n=== AXIS: {cap['name']} ({axis_id}) ===")
        summary[axis_id] = {}
        for provider, meta in config.items():
            print(f"[{provider}]")
            recs, log = scan_provider(provider, meta, cfg_axis, kws, catalog, llm)
            for line in log:
                print(line)
            feats = [r for r in recs if r["parent_id"] == meta["product_id"]]
            all_records.extend(recs)
            summary[axis_id][provider] = [r["name"] for r in feats]

    out = ROOT / "data" / f"_sweep_{capability}.json"
    out.write_text(json.dumps({"as_of": AS_OF, "capability": capability, "records": all_records},
                              indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\n=== SWEEP SUMMARY — features per axis × provider ===")
    for axis_id, provs in summary.items():
        counts = " · ".join(f"{p}:{len(provs.get(p, []))}" for p in config)
        print(f"  {axis_id:28} {counts}")
    feats = sum(1 for r in all_records if r["relation_within_capability"] == "direct")
    print(f"\n{len(all_records)} records ({feats} features + {len(all_records)-feats} sub-features) → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
