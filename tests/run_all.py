"""Run every test_*.py here without requiring pytest (pytest-compatible too).

    python3 tests/run_all.py
"""

from __future__ import annotations

import importlib.util
import sys
import traceback
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent))


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def main() -> int:
    total = failed = 0
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        module = _load(path)
        fns = [v for k, v in sorted(vars(module).items())
               if k.startswith("test_") and callable(v)]
        print(f"{path.name}:")
        for fn in fns:
            total += 1
            try:
                fn()
                print(f"  PASS {fn.__name__}")
            except AssertionError as exc:
                failed += 1
                print(f"  FAIL {fn.__name__}: {exc}")
            except Exception as exc:  # unexpected error counts as a failure
                failed += 1
                print(f"  ERROR {fn.__name__}: {type(exc).__name__}: {exc}")
                traceback.print_exc()
    print(f"\n{total - failed}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
