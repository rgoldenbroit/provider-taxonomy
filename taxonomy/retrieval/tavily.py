"""Tavily-backed web search (search only; grounding-fetch stays in-engine via httpx).

Tavily is an LLM/agent-oriented search API. We use it for the discovery sweep —
turning a (provider × capability) query into candidate URLs — and keep the
grounding fetch on our own httpx fetcher so the page text the judge sees is
logged and auditable.

The HTTP call is injectable (``poster``) so it can be unit-tested without httpx.
"""

from __future__ import annotations

from typing import Callable

from .base import RetrievalError, SearchResult

TAVILY_URL = "https://api.tavily.com/search"


class TavilySearch:
    def __init__(self, api_key: str | None, *, timeout: float = 20.0,
                 search_depth: str = "basic", poster: Callable[[dict], dict] | None = None):
        if not api_key:
            raise RetrievalError("TAVILY_API_KEY is not set — cannot search.")
        self.api_key = api_key
        self.timeout = timeout
        self.search_depth = search_depth
        self._poster = poster  # test seam: (payload) -> parsed json dict

    def _post(self, payload: dict) -> dict:
        if self._poster is not None:
            return self._poster(payload)
        import httpx  # lazy: offline/test paths never import httpx

        try:
            resp = httpx.post(TAVILY_URL, json=payload, timeout=self.timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:  # network/timeout/HTTP-status error
            raise RetrievalError(f"Tavily request failed: {exc}") from exc
        return resp.json()

    def search(self, query: str, *, max_results: int = 8,
               include_domains: list[str] | None = None) -> list[SearchResult]:
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": self.search_depth,
        }
        if include_domains:
            payload["include_domains"] = include_domains   # scope to a provider's official docs
        data = self._post(payload)
        return [
            SearchResult(url=r["url"], title=r.get("title", ""), snippet=(r.get("content") or "")[:300])
            for r in data.get("results", []) if r.get("url")
        ][:max_results]
