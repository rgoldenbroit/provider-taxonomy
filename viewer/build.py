"""Generate the single-file viewer by inlining a validated dataset into the template.

``examples.json``/``data/taxonomy.json`` stay canonical; ``viewer/taxonomy.html`` is
a generated artifact. The dataset is validated at build time (the Python validator
is the single source of validation truth) and the result embedded so the page can
render the banner without re-implementing the validator in JS.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.metrics import dataset_metrics  # noqa: E402
from taxonomy.schema import REPO_ROOT, load_dataset  # noqa: E402
from taxonomy.staleness import INTERVALS, days_overdue, today_for  # noqa: E402
from taxonomy.validate import validate  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent / "template.html"
OUTPUT = Path(__file__).resolve().parent / "taxonomy.html"
_MARKER = "/*__APP_DATA__*/{}"


def build(data_path: str | None = None) -> tuple[Path, list]:
    data = load_dataset(data_path)
    issues = validate(data)
    today = today_for(data)
    app = {
        "data": data,
        "today": today,
        "intervals": INTERVALS,
        "metrics": dataset_metrics(data),
        "staleness": {p["id"]: days_overdue(p, today) for p in data.get("products", [])},
        "validation": {
            "valid": not issues,
            "issues": [
                {"kind": i.kind, "rule": i.rule, "path": i.path,
                 "message": i.message, "record_id": i.record_id}
                for i in issues
            ],
        },
    }
    blob = json.dumps(app, ensure_ascii=False).replace("</", "<\\/")  # keep </script> inert
    template = TEMPLATE.read_text(encoding="utf-8")
    if _MARKER not in template:
        raise SystemExit(f"template marker {_MARKER!r} not found in {TEMPLATE}")
    OUTPUT.write_text(template.replace(_MARKER, blob), encoding="utf-8")
    return OUTPUT, issues


if __name__ == "__main__":
    out, issues = build(sys.argv[1] if len(sys.argv) > 1 else None)
    status = "valid" if not issues else f"{len(issues)} validation issue(s)"
    print(f"wrote {out}  ({status})")
    if issues:
        for i in issues:
            print(f"  - {i['kind'] if isinstance(i, dict) else i}", file=sys.stderr)
