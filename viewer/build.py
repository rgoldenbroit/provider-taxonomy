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


def _load_provenance() -> dict:
    """Per-record receipts from the evidence ledger (the 'why we believe this' trail)."""
    prov_dir = REPO_ROOT / "evidence" / "provenance"
    receipts: dict[str, dict] = {}
    if not prov_dir.exists():
        return receipts
    for f in prov_dir.rglob("*.json"):
        try:
            rec = json.loads(f.read_text(encoding="utf-8")).get("value") or {}
        except (json.JSONDecodeError, OSError):
            continue  # a malformed/unreadable receipt must not break the build
        if rec.get("record_id"):
            receipts[rec["record_id"]] = {
                k: rec.get(k) for k in
                ("source_tier", "supported", "found_quote", "source_url", "model",
                 "verified_at", "review_status", "confidence", "lifecycle_status")
            }
    return receipts


def _load_json(rel: str) -> dict:
    p = REPO_ROOT / rel
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def build(data_path: str | None = None) -> tuple[Path, list]:
    data = load_dataset(data_path)
    issues = validate(data)
    today = today_for(data)
    app = {
        "data": data,
        "today": today,
        "intervals": INTERVALS,
        "metrics": dataset_metrics(data),
        "provenance": _load_provenance(),
        "changelog": _load_json("data/changelog.json"),
        "matrix": _load_json("data/agentic-matrix.json"),
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
