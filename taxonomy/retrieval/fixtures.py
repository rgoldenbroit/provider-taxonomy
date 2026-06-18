"""Deterministic retrieval from recorded fixtures (offline dev + evals).

Fixtures live under ``data/fixtures/``:
  searches.json : {query: [{url, title, snippet}, ...]}
  pages.json    : {url: {status, text}}
"""

from __future__ import annotations

import json
from pathlib import Path

from ..schema import REPO_ROOT
from .base import FetchedPage, RetrievalMissing, RetrievalProvider, SearchResult, content_hash

FIXTURES_DIR = REPO_ROOT / "data" / "fixtures"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


class FixtureRetrieval(RetrievalProvider):
    def __init__(self, root: Path = FIXTURES_DIR):
        self.root = root
        self._searches = _load(root / "searches.json")
        self._pages = _load(root / "pages.json")

    def search(self, query: str, *, max_results: int = 8,
               include_domains: list[str] | None = None) -> list[SearchResult]:   # fixtures ignore domain scoping
        results = self._searches.get(query)
        if results is None:
            raise RetrievalMissing(f"no fixture search recorded for query {query!r}")
        return [SearchResult(**r) for r in results][:max_results]

    def fetch(self, url: str) -> FetchedPage:
        page = self._pages.get(url)
        if page is None:
            raise RetrievalMissing(f"no fixture page recorded for url {url!r}")
        text = page.get("text", "")
        return FetchedPage(url=url, status=page.get("status", 200), text=text,
                           content_hash=content_hash(text))
