"""Live source fetch via httpx, with a stdlib HTML→text strip and an on-disk cache.

The grounding gate (Phase 3) calls ``fetch`` to get the raw text of a record's
``source.url`` so an independent judge can confirm the page substantiates the
claim. Pages are cached under ``ops/cache/`` keyed by URL hash so re-verification
is free and deterministic. ``search`` is not implemented here — live search is the
Vertex ``web_search`` tool, wired in Phase 2.
"""

from __future__ import annotations

import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

from ..schema import REPO_ROOT
from .base import FetchedPage, RetrievalError, RetrievalProvider, SearchResult, content_hash

OPS_CACHE = REPO_ROOT / "ops" / "cache"
_SKIP_TAGS = {"script", "style", "noscript", "template", "svg"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._chunks.append(text)

    def text(self) -> str:
        return "\n".join(self._chunks)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text()


class HttpFetch(RetrievalProvider):
    def __init__(self, cache_dir: Path = OPS_CACHE, timeout: float = 20.0,
                 user_agent: str = "provider-taxonomy/0.1 (+grounding-gate)", ledger=None):
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.user_agent = user_agent
        self._ledger = ledger   # optional evidence ledger: page snapshots become committed evidence

    def search(self, query: str, *, max_results: int = 8,
               include_domains: list[str] | None = None) -> list[SearchResult]:
        raise NotImplementedError("HttpFetch is fetch-only; use Tavily for search")

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()}.json"

    def _live_fetch(self, url: str) -> dict:
        import httpx  # lazy: offline path never imports httpx

        try:
            resp = httpx.get(url, timeout=self.timeout, follow_redirects=True,
                             headers={"User-Agent": self.user_agent})
        except httpx.HTTPError as exc:  # network/timeout/DNS — surface as a retrieval failure
            raise RetrievalError(f"fetch failed for {url}: {exc}") from exc
        return {"url": url, "status": resp.status_code, "text": html_to_text(resp.text)}

    def fetch(self, url: str) -> FetchedPage:
        if self._ledger is not None and self._ledger.active:   # snapshot into the committed evidence ledger
            from ..ledger import page_key
            data = self._ledger.cached("page", page_key(url), lambda: self._live_fetch(url), meta={"url": url})
            return FetchedPage(url=url, status=data["status"], text=data["text"],
                               content_hash=content_hash(data["text"]))

        cached = self._cache_path(url)   # legacy on-disk cache (regenerable, gitignored)
        if cached.exists():
            data = json.loads(cached.read_text(encoding="utf-8"))
            return FetchedPage(url=url, status=data["status"], text=data["text"],
                               content_hash=content_hash(data["text"]))
        data = self._live_fetch(url)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps({"status": data["status"], "text": data["text"]}), encoding="utf-8")
        return FetchedPage(url=url, status=data["status"], text=data["text"], content_hash=content_hash(data["text"]))
