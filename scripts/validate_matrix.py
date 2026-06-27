#!/usr/bin/env python3
"""Validate the agentic-coding capability matrix embedded in
`ai-provider-capability-taxonomy.md` against the section-2 schema and the
section-5 definition of done, then print the summary `/goal` evaluates against.

The matrix lives in the fenced ```yaml block whose first line carries the marker
`# matrix-data:` (this keeps the validator off the section-2 schema *template*,
which contains <placeholder> tokens that are not real data).

Exit code 0 == zero errors.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # PyYAML is the only dependency; fail loudly rather than guess.
    sys.exit("ERROR: PyYAML not installed. Run: python -m pip install pyyaml")

MD_PATH = Path(__file__).resolve().parent.parent / "ai-provider-capability-taxonomy.md"

PROVIDERS = ("anthropic", "google", "openai")
LAYERS = {"user", "platform", "governance"}
TIERS = {"core", "advanced"}
# `needs_review` = the lineup holds a candidate the confirm gate hasn't admitted; shown, but not claimed
# as grounded. It still must cite a real source (enforced below) — it is never a bare, sourceless claim.
STATUSES = {"active", "preview", "sunset", "none", "unverified", "needs_review"}
CELL_KEYS = ("offering", "implementation", "status", "evidence_url", "last_verified")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Row names must be vendor-neutral: the vendor's feature name belongs in the cell.
# MCP is deliberately NOT here — it is now a cross-vendor open standard.
VENDOR_TOKENS = (
    "claude code", "claude.md", "claude", "anthropic", "codex", "openai", "gpt",
    "antigravity", "gemini", "google", "agents.md", "copilot", "cursor",
)


def extract_matrix_yaml(md_text: str) -> str:
    """Return the body of the fenced yaml block containing the `# matrix-data:` marker."""
    blocks = re.findall(r"```yaml\n(.*?)```", md_text, re.DOTALL)
    marked = [b for b in blocks if "# matrix-data:" in b]
    if not marked:
        raise ValueError("no ```yaml block containing the '# matrix-data:' marker was found")
    if len(marked) > 1:
        raise ValueError("more than one '# matrix-data:' block found; expected exactly one")
    return marked[0]


def validate(doc: dict) -> tuple[list[str], dict]:
    errors: list[str] = []
    stats = {
        "groups": 0, "capabilities": 0, "cells": 0,
        "by_status": {s: 0 for s in STATUSES}, "filled": 0, "unverified": 0,
        "needs_review": 0, "bad_status": 0,
    }

    if not isinstance(doc.get("product_category"), str) or not doc["product_category"].strip():
        errors.append("top-level: 'product_category' missing or not a non-empty string")

    groups = doc.get("capability_groups")
    if not isinstance(groups, list) or not groups:
        errors.append("top-level: 'capability_groups' missing or empty")
        return errors, stats

    seen_ids: set[str] = set()
    for gi, group in enumerate(groups):
        gname = group.get("name", f"<group #{gi}>") if isinstance(group, dict) else f"<group #{gi}>"
        if not isinstance(group, dict):
            errors.append(f"group #{gi}: not a mapping")
            continue
        stats["groups"] += 1
        if not isinstance(group.get("name"), str) or not group["name"].strip():
            errors.append(f"group #{gi}: missing 'name'")
        if group.get("layer") not in LAYERS:
            errors.append(f"group '{gname}': layer {group.get('layer')!r} not in {sorted(LAYERS)}")
        caps = group.get("capabilities")
        if not isinstance(caps, list) or not caps:
            errors.append(f"group '{gname}': 'capabilities' missing or empty")
            continue

        for ci, cap in enumerate(caps):
            loc = f"group '{gname}' cap #{ci}"
            if not isinstance(cap, dict):
                errors.append(f"{loc}: not a mapping")
                continue
            stats["capabilities"] += 1
            cid = cap.get("id")
            loc = f"cap '{cid}'" if isinstance(cid, str) else loc
            if not isinstance(cid, str) or not KEBAB_RE.match(cid or ""):
                errors.append(f"{loc}: 'id' missing or not kebab-case")
            elif cid in seen_ids:
                errors.append(f"{loc}: duplicate id")
            else:
                seen_ids.add(cid)

            name = cap.get("name")
            if not isinstance(name, str) or not name.strip():
                errors.append(f"{loc}: 'name' missing")
            else:
                low = name.lower()
                hit = next((t for t in VENDOR_TOKENS if t in low), None)
                if hit:
                    errors.append(f"{loc}: row name is vendor-specific (contains {hit!r}): {name!r}")
            if not isinstance(cap.get("what"), str) or not cap["what"].strip():
                errors.append(f"{loc}: 'what' missing")
            if cap.get("tier") not in TIERS:
                errors.append(f"{loc}: tier {cap.get('tier')!r} not in {sorted(TIERS)}")

            providers = cap.get("providers")
            if not isinstance(providers, dict):
                errors.append(f"{loc}: 'providers' missing")
                continue
            missing = [p for p in PROVIDERS if p not in providers]
            if missing:
                errors.append(f"{loc}: missing providers {missing}")
            extra = [p for p in providers if p not in PROVIDERS]
            if extra:
                errors.append(f"{loc}: unexpected providers {extra}")

            for prov in PROVIDERS:
                cell = providers.get(prov)
                if cell is None:
                    continue
                stats["cells"] += 1
                cloc = f"{loc} / {prov}"
                if not isinstance(cell, dict):
                    errors.append(f"{cloc}: cell is not a mapping")
                    continue
                for k in CELL_KEYS:
                    if k not in cell:
                        errors.append(f"{cloc}: missing key '{k}'")
                status = cell.get("status")
                if status not in STATUSES:
                    errors.append(f"{cloc}: status {status!r} not in {sorted(STATUSES)}")
                    stats["bad_status"] += 1
                    continue
                stats["by_status"][status] += 1
                if status == "unverified":
                    stats["unverified"] += 1
                else:
                    # `needs_review` is bucketed apart from grounded, but — like grounded — must cite a
                    # real source + date. That requirement is what keeps it honest rather than a free gap.
                    stats["needs_review" if status == "needs_review" else "filled"] += 1
                    ev = (cell.get("evidence_url") or "").strip()
                    lv = (cell.get("last_verified") or "").strip()
                    if not ev:
                        errors.append(f"{cloc}: status '{status}' requires a non-empty evidence_url")
                    elif not ev.startswith("http"):
                        errors.append(f"{cloc}: evidence_url is not a URL: {ev!r}")
                    if not lv:
                        errors.append(f"{cloc}: status '{status}' requires a last_verified date")
                    elif not DATE_RE.match(lv):
                        errors.append(f"{cloc}: last_verified {lv!r} is not YYYY-MM-DD")

    return errors, stats


def main() -> int:
    md_text = MD_PATH.read_text(encoding="utf-8")
    try:
        raw = extract_matrix_yaml(md_text)
        doc = yaml.safe_load(raw)
    except (ValueError, yaml.YAMLError) as exc:
        print("=" * 60)
        print("AGENTIC-CODING MATRIX — VALIDATION SUMMARY")
        print("=" * 60)
        print(f"  YAML parse: FAILED — {exc}")
        print("\nVALIDATION SUMMARY: 1 error (YAML did not parse)")
        return 1

    errors, stats = validate(doc)

    print("=" * 60)
    print("AGENTIC-CODING MATRIX — VALIDATION SUMMARY")
    print("=" * 60)
    print(f"  source            : {MD_PATH.name}")
    print(f"  YAML parse        : OK")
    print(f"  product_category  : {doc.get('product_category')}")
    print(f"  capability groups : {stats['groups']}")
    print(f"  capabilities      : {stats['capabilities']}")
    print(f"  provider cells    : {stats['cells']}  (expected {stats['capabilities'] * 3})")
    print(f"  grounded (confirmed)           : {stats['filled']}")
    print(f"  needs_review (candidate exists): {stats['needs_review']}")
    print(f"  unverified (earned gap)        : {stats['unverified']}")
    print("  status breakdown  : " + ", ".join(
        f"{s}={stats['by_status'][s]}" for s in ("active", "preview", "sunset", "none", "needs_review", "unverified")
    ))
    if stats["cells"] != stats["capabilities"] * 3:
        # already reported per-capability as missing providers; surfaced here too.
        pass

    print("-" * 60)
    if errors:
        print(f"  ERRORS ({len(errors)}):")
        for e in errors:
            print(f"    - {e}")
    print("=" * 60)
    print(f"VALIDATION SUMMARY: {len(errors)} error{'s' if len(errors) != 1 else ''}")
    if not errors:
        print("RESULT: PASS — matrix is complete and conforms to the schema + definition of done.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
