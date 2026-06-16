"""Loaders for offline fixtures (canned LLM responses keyed by label)."""

from __future__ import annotations

import json

from .schema import REPO_ROOT

FIXTURES_DIR = REPO_ROOT / "data" / "fixtures"


def load_llm_fixtures() -> dict:
    """Map of label → canned structured response for :class:`StubLLM`."""
    path = FIXTURES_DIR / "llm.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)
