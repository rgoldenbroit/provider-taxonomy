"""Phase 5 test: the viewer builds, validates, and embeds parseable data."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _build_module():
    spec = importlib.util.spec_from_file_location("viewer_build", ROOT / "viewer" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_viewer_builds_and_embeds_valid_data():
    from taxonomy.schema import load_dataset  # noqa: PLC0415

    out, issues = _build_module().build()
    assert issues == []
    html = Path(out).read_text(encoding="utf-8")
    m = re.search(r"const APP = (\{.*?\});\nconst D", html, re.S)
    assert m, "embedded APP blob not found"
    app = json.loads(m.group(1).replace("<\\/", "</"))
    assert app["validation"]["valid"] is True
    # Embedded count matches whatever the working store holds (seed or grounded catalog).
    assert len(app["data"]["products"]) == len(load_dataset()["products"]) >= 1
    for hook in ("viewOverview", "viewExplore", "openDrawer", "cross-provider equivalents", "In flux"):
        assert hook in html
