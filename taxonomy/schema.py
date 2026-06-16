"""Paths and JSON loading for the canonical seed, schema, and working store.

``examples.json`` is the canonical seed *and* the labeled gold set — it is never
mutated by the engine. ``data/taxonomy.json`` is the working store the engine
grows (seeded as a copy of ``examples.json``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

SCHEMA_PATH = REPO_ROOT / "schema.json"
SEED_PATH = REPO_ROOT / "examples.json"
DEFAULT_DATA_PATH = REPO_ROOT / "data" / "taxonomy.json"


def load_json(path: str | Path) -> Any:
    """Load and parse a JSON file. Raises on missing file or bad JSON (fail loudly)."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_schema() -> dict:
    return load_json(SCHEMA_PATH)


def load_seed() -> dict:
    return load_json(SEED_PATH)


def load_dataset(path: str | Path | None = None) -> dict:
    return load_json(path or DEFAULT_DATA_PATH)
