"""Retrieval interface and value types."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str
    snippet: str = ""


@dataclass(frozen=True)
class FetchedPage:
    url: str
    status: int
    text: str
    content_hash: str


class RetrievalError(Exception):
    """A retrieval operation failed (network error, or a missing offline fixture)."""


class RetrievalMissing(RetrievalError, LookupError):
    """A fixture / cache entry the offline provider was asked for does not exist."""


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RetrievalProvider(ABC):
    @abstractmethod
    def search(self, query: str, *, max_results: int = 8) -> list[SearchResult]:
        ...

    @abstractmethod
    def fetch(self, url: str) -> FetchedPage:
        ...


class CompositeRetrieval(RetrievalProvider):
    """Search from one provider, fetch from another (e.g. Tavily search + httpx fetch)."""

    def __init__(self, searcher, fetcher):
        self._searcher = searcher
        self._fetcher = fetcher

    def search(self, query: str, *, max_results: int = 8) -> list[SearchResult]:
        return self._searcher.search(query, max_results=max_results)

    def fetch(self, url: str) -> FetchedPage:
        return self._fetcher.fetch(url)
