#!/usr/bin/env python3
"""Render section 3 of ai-provider-capability-taxonomy.md from data/agentic-matrix.json.

The .md section is a human-readable RENDERING — the canonical matrix is data/agentic-matrix.json,
built by scripts/build_matrix.py (rows from matrix/capabilities.yaml, cells grounded automatically).
Run this after build_matrix to keep the spec file in sync; CI render-diffs it as a drift gate.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("ERROR: PyYAML not installed. Run: python -m pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent
MD = ROOT / "ai-provider-capability-taxonomy.md"
JSON_PATH = ROOT / "data" / "agentic-matrix.json"


def main() -> int:
    doc = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    total = grounded = unv = 0
    for g in doc["capability_groups"]:
        for c in g["capabilities"]:
            for pk in ("anthropic", "google", "openai"):
                total += 1
                if c["providers"][pk]["status"] == "unverified":
                    unv += 1
                else:
                    grounded += 1
    ncap = sum(len(g["capabilities"]) for g in doc["capability_groups"])
    ngrp = len(doc["capability_groups"])

    ybody = yaml.safe_dump(doc, sort_keys=False, default_flow_style=False, width=4096, allow_unicode=True)
    yblock = ("```yaml\n# matrix-data: agentic-coding   (the validator selects the YAML block containing this marker)\n"
              + ybody + "```")

    intro = (
        "## 3. Agentic-coding matrix — generated, grounded projection of the catalog\n\n"
        "This section is GENERATED, not hand-edited. Rows come from `matrix/capabilities.yaml`; the\n"
        "per-provider cells are grounded automatically by `scripts/build_matrix.py` — it projects the\n"
        "official-docs-grounded catalog (`data/taxonomy.json`), then escalates to each vendor's official\n"
        "doc pages and a domain-restricted live search, leaving a cell `unverified` only when no\n"
        "first-party doc supports it. The canonical data is `data/agentic-matrix.json`; this block renders it.\n\n"
        f"{ngrp} capability groups, {ncap} neutral capabilities. "
        f"**{grounded}/{total} cells grounded, {unv} honestly `unverified`** (no first-party doc — left\n"
        "blank, not guessed). Every grounded cell links the official page it was verified against.\n\n"
        "> Regenerate: `scripts/build_matrix.py` (re-ground, needs Vertex) → `scripts/render_matrix_md.py`\n"
        "> (re-render this block) → `scripts/validate_matrix.py` (gate). The viewer reads the JSON directly.\n\n"
    )

    text = MD.read_text(encoding="utf-8")
    new_sec3 = intro + yblock + "\n"
    text2 = re.sub(r"## 3\. .*?(?=\n---\n\n## 4\. )", lambda m: new_sec3, text, count=1, flags=re.DOTALL)
    if text2 == text:
        sys.exit("ERROR: section-3 replacement did not match — the .md structure changed.")
    MD.write_text(text2, encoding="utf-8")
    print(f"rendered .md section 3: {ngrp} groups, {ncap} caps, {grounded}/{total} grounded, {unv} unverified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
