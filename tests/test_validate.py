"""Validator tests. Runnable under pytest OR standalone: ``python3 tests/test_validate.py``."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from taxonomy.schema import load_seed  # noqa: E402
from taxonomy.validate import Issue, validate  # noqa: E402


def _seed() -> dict:
    return load_seed()


def _absence_index(data: dict) -> int:
    return next(i for i, p in enumerate(data["products"]) if p["status"] == "absent")


def _has(issues: list[Issue], *, kind: str | None = None, rule: str | None = None,
         path_contains: str | None = None, msg_contains: str | None = None) -> bool:
    for it in issues:
        if kind is not None and it.kind != kind:
            continue
        if rule is not None and it.rule != rule:
            continue
        if path_contains is not None and path_contains not in it.path:
            continue
        if msg_contains is not None and msg_contains not in it.message:
            continue
        return True
    return False


def test_seed_is_valid():
    issues = validate(_seed())
    assert issues == [], "seed should validate cleanly:\n" + "\n".join(str(i) for i in issues)


def test_bad_enum_status():
    d = _seed()
    d["products"][0]["status"] = "frozen"
    assert _has(validate(d), kind="schema", rule="enum", path_contains=".status")


def test_missing_required_source():
    d = _seed()
    del d["products"][0]["source"]
    assert _has(validate(d), kind="schema", rule="required", msg_contains="source")


def test_additional_property_rejected():
    d = _seed()
    d["products"][0]["color"] = "blue"
    assert _has(validate(d), kind="schema", rule="additionalProperties", msg_contains="color")


def test_bad_date_format():
    d = _seed()
    d["products"][0]["source"]["last_verified"] = "2026/06/15"
    assert _has(validate(d), kind="schema", rule="format", path_contains="last_verified")


def test_dangling_capability_reference():
    d = _seed()
    d["products"][0]["capability_ids"] = ["does-not-exist"]
    d["products"][0]["primary_capability_id"] = "does-not-exist"
    assert _has(validate(d), kind="integrity", rule="ref_resolution", msg_contains="unknown capability")


def test_primary_not_in_capability_ids():
    d = _seed()
    # products[0] is the Claude model family: capability_ids == ["flagship-model"].
    d["products"][0]["primary_capability_id"] = "agentic-coding"  # real, but not in the list
    assert _has(validate(d), kind="integrity", rule="invariant", path_contains="primary_capability_id")


def test_absent_requires_relation_none():
    d = _seed()
    d["products"][_absence_index(d)]["relation_within_capability"] = "direct"
    assert _has(validate(d), kind="integrity", rule="invariant", msg_contains="absent")


def test_duplicate_product_id():
    d = _seed()
    d["products"].append(copy.deepcopy(d["products"][0]))
    assert _has(validate(d), kind="integrity", rule="uniqueness")


def test_dangling_parent_id():
    d = _seed()
    # products[1] is a model with parent_id -> the model family; break the link.
    d["products"][1]["parent_id"] = "ghost-parent"
    assert _has(validate(d), kind="integrity", rule="ref_resolution", path_contains="parent_id")


def test_empty_capability_ids():
    d = _seed()
    d["products"][0]["capability_ids"] = []
    assert _has(validate(d), kind="integrity", rule="invariant", path_contains="capability_ids")


def _a_capability(d: dict) -> str:
    return d["capabilities"][0]["id"]


def test_valid_categories_accepted():
    d = _seed()
    fn = _a_capability(d)
    d["categories"] = [{
        "id": "cat/one", "function_id": fn, "name": "One",
        "description": "A grouping.", "order": 1, "feature_axis_ids": [fn],
    }]
    assert validate(d) == []


def test_scaffold_review_status_accepted():
    d = _seed()
    d["products"][1]["review_status"] = "scaffold"
    assert validate(d) == []


def test_category_unknown_function_id():
    d = _seed()
    d["categories"] = [{"id": "cat/x", "function_id": "ghost-fn",
                        "name": "X", "description": "d"}]
    assert _has(validate(d), kind="integrity", rule="ref_resolution",
                path_contains="function_id")


def test_category_unknown_feature_axis():
    d = _seed()
    fn = _a_capability(d)
    d["categories"] = [{"id": "cat/x", "function_id": fn, "name": "X",
                        "description": "d", "feature_axis_ids": ["ghost-axis"]}]
    assert _has(validate(d), kind="integrity", rule="ref_resolution",
                path_contains="feature_axis_ids")


def test_duplicate_category_id():
    d = _seed()
    fn = _a_capability(d)
    cat = {"id": "cat/dup", "function_id": fn, "name": "X", "description": "d"}
    d["categories"] = [cat, copy.deepcopy(cat)]
    assert _has(validate(d), kind="integrity", rule="uniqueness", path_contains="categories")


def test_category_bad_additional_property():
    d = _seed()
    fn = _a_capability(d)
    d["categories"] = [{"id": "cat/x", "function_id": fn, "name": "X",
                        "description": "d", "bogus": 1}]
    assert _has(validate(d), kind="schema", rule="additionalProperties", msg_contains="bogus")


def test_comparison_note_accepted():
    d = _seed()
    cap = d["capabilities"][0]
    cap["comparison_note"] = "Anthropic uses files; OpenAI uses config; Google uses a managed runtime."
    cap["comparison_note_sources"] = ["https://docs.anthropic.com/x", "https://developers.openai.com/y"]
    assert validate(d) == []
    # and a capability without it still validates
    del cap["comparison_note"], cap["comparison_note_sources"]
    assert validate(d) == []


def test_parent_id_cycle_detected():
    d = _seed()
    a, b = d["products"][0]["id"], d["products"][1]["id"]
    d["products"][0]["parent_id"] = b
    d["products"][1]["parent_id"] = a  # a -> b -> a
    assert _has(validate(d), kind="integrity", rule="invariant", msg_contains="cycle")


def _run_standalone() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {t.__name__}: {exc}")
        except Exception as exc:  # surface unexpected errors as failures
            failed += 1
            print(f"  ERROR {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
