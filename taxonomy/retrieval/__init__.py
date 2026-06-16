"""Retrieval: search for offerings, fetch source pages.

Discovery may search via different providers, but the **grounding gate always
fetches source URLs in-engine** (Vertex has no ``web_fetch``), so fetched page
text is logged and auditable. ``get_retrieval()`` returns the fixtures provider
offline (deterministic dev/eval) and the live http fetcher otherwise.
"""

from __future__ import annotations

from ..config import Settings, settings
from .base import FetchedPage, RetrievalProvider, SearchResult, content_hash

__all__ = [
    "FetchedPage",
    "RetrievalProvider",
    "SearchResult",
    "content_hash",
    "get_retrieval",
]


def get_retrieval(cfg: Settings | None = None) -> RetrievalProvider:
    cfg = cfg or settings()
    if cfg.offline:
        from .fixtures import FixtureRetrieval

        return FixtureRetrieval()

    from .http_fetch import HttpFetch  # grounding-fetch is always in-engine httpx

    fetcher = HttpFetch()
    if cfg.tavily_api_key:  # live web search → real discovery instead of an operator shortlist
        from .base import CompositeRetrieval
        from .tavily import TavilySearch

        return CompositeRetrieval(TavilySearch(cfg.tavily_api_key), fetcher)
    return fetcher  # no search key: fetch-only (search raises NotImplementedError)
