"""Changelog diff tests."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.changelog import diff_catalogs, is_empty, to_markdown  # noqa: E402


def _p(pid, **kw):
    return {"id": pid, "name": pid.upper(), "provider": "X", "status": "active",
            "source": {"confidence": "high"}, **kw}


def test_diff_detects_add_remove_and_field_change():
    old = {"products": [_p("a"), _p("b")]}
    new = {"products": [_p("a", status="sunset"), _p("c", provider="Y", source={"confidence": "low"})]}
    d = diff_catalogs(old, new)
    assert [x["id"] for x in d["added"]] == ["c"]
    assert [x["id"] for x in d["removed"]] == ["b"]
    assert d["changed"][0]["id"] == "a"
    assert d["changed"][0]["fields"]["status"] == ["active", "sunset"]
    assert not is_empty(d)


def test_diff_is_empty_for_identical_catalogs():
    cat = {"products": [_p("a")]}
    assert is_empty(diff_catalogs(cat, copy.deepcopy(cat)))


def test_markdown_includes_date_and_names():
    md = to_markdown({"added": [{"name": "C", "provider": "Y"}], "removed": [], "changed": []}, "2026-06-18")
    assert "2026-06-18" in md and "C" in md and "Y" in md
