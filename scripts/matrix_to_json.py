#!/usr/bin/env python3
"""Generate ``data/agentic-matrix.json`` from the matrix YAML embedded in
``ai-provider-capability-taxonomy.md``, gated by the section-2 schema + definition-of-done
validator.

This keeps the ``.md`` file the single source of truth while letting the viewer build
(pure stdlib) read JSON — so PyYAML never enters the build/deploy path. Run this whenever
the matrix changes; CI also runs ``scripts/validate_matrix.py`` as the standing gate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import yaml
except ImportError:  # dev-only dependency; the viewer build itself never imports yaml.
    sys.exit("ERROR: PyYAML not installed. Run: python -m pip install pyyaml")

from validate_matrix import MD_PATH, extract_matrix_yaml, validate  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "agentic-matrix.json"


def main() -> int:
    raw = extract_matrix_yaml(MD_PATH.read_text(encoding="utf-8"))
    doc = yaml.safe_load(raw)
    errors, stats = validate(doc)
    if errors:
        # Refuse to emit a JSON that wouldn't pass the gate — surface, don't paper over.
        print(
            f"refusing to emit: matrix has {len(errors)} validation error(s). "
            "Run `python scripts/validate_matrix.py` for details.",
            file=sys.stderr,
        )
        return 1
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(OUT.parents[1])}  "
        f"({stats['groups']} groups, {stats['capabilities']} capabilities, "
        f"{stats['filled']} grounded / {stats['unverified']} unverified)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
