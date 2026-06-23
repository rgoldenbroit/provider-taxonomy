"""Retrieve a provider's OWN structured documentation surface — not web search.

Search-as-retrieval was the root cause of blog/forum/junk leakage and the Google=0 gap.
Providers publish their docs in machine-readable form; we use that directly:

- **llms.txt index** (Anthropic Claude Code): a markdown index where each page is a clean `.md` URL.
- **llms-full.txt** (OpenAI Codex): the entire docs as one markdown file → sectioned by heading.
- **sitemap.xml + headless render** (Google Antigravity): JS-rendered docs; enumerate `/docs/*` from
  the sitemap and render with headless Chrome (`--dump-dom`).

Returns clean `DocPage(url, text, title)` objects. `CachedPages` wraps them as a RetrievalProvider so
the existing grounding judge runs against the real markdown we fetched.
"""

from __future__ import annotations

import gzip
import os
import re
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass

from .retrieval.base import FetchedPage, RetrievalProvider, content_hash

_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"

DOC_SOURCES = {
    "Anthropic": {"kind": "llms_index", "url": "https://code.claude.com/llms.txt"},
    # Codex llms.txt lists ~95 per-page .md URLs that fetch clean markdown directly — use those
    # (fetchable + reproducible by reverify), not llms-full.txt section fragments.
    "OpenAI": {"kind": "llms_index", "url": "https://developers.openai.com/codex/llms.txt"},
    # Antigravity is a client-rendered SPA — rendering yields only the nav shell. Its content is served
    # as clean gzipped markdown assets the SPA fetches; we enumerate those via a Chrome net-log pass
    # (no puppeteer dep) and fetch them directly → complete + official + no rendering fragility.
    "Google": {"kind": "asset_md", "home": "https://antigravity.google/docs",
               "asset_re": r"https://antigravity\.google/assets/docs/[^\"\\]+\.md"},
}
_FETCH_CACHE: dict[str, str] = {}   # url → text, so the full sweep doesn't refetch the corpus per axis
_ENUM_CACHE: dict[str, list] = {}   # home_url → enumerated asset urls (one Chrome pass per process)


@dataclass
class DocPage:
    url: str
    text: str
    title: str = ""


def _get(url: str, timeout: int = 25) -> str:
    """HTTP GET, gzip-aware, memoized (doc assets are often served gzipped, e.g. antigravity)."""
    if url in _FETCH_CACHE:
        return _FETCH_CACHE[url]
    text = ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept-Encoding": "gzip, identity"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec - fetching public docs
            raw = r.read()
            if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
                raw = gzip.decompress(raw)
            text = raw.decode("utf-8", "replace")
    except Exception:  # network/HTTP/decode/gzip failure → treat as "no doc" (caller handles emptiness)
        text = ""
    _FETCH_CACHE[url] = text
    return text


def enumerate_asset_docs(home_url: str, asset_re: str, budget_ms: int = 18000) -> list[str]:
    """Robustly enumerate an SPA's content-asset URLs via a Chrome net-log pass (no puppeteer).
    Loads the docs home with a virtual-time budget, then greps the captured network log for the
    asset URLs the SPA fetched. Returns [] if Chrome is unavailable (caller falls back)."""
    if home_url in _ENUM_CACHE:   # one Chrome pass per process, reused across every axis
        return _ENUM_CACHE[home_url]
    netlog = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            netlog = tf.name
        subprocess.run([_CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
                        f"--log-net-log={netlog}", f"--virtual-time-budget={budget_ms}", home_url],
                       capture_output=True, timeout=budget_ms / 1000 + 30)
        data = open(netlog, encoding="utf-8", errors="replace").read()
        urls = sorted(set(re.findall(asset_re, data)))
        _ENUM_CACHE[home_url] = urls
        return urls
    except (subprocess.SubprocessError, OSError):
        return []
    finally:
        if netlog and os.path.exists(netlog):
            try:
                os.unlink(netlog)
            except OSError:  # temp cleanup is best-effort
                pass


def _md_title(text: str) -> str:
    """Page title from YAML frontmatter `title:` or the first markdown `# ` heading."""
    m = re.search(r"^title:\s*(.+)$", text, re.M)
    if m:
        return m.group(1).strip().strip("\"'")
    h = re.search(r"^#\s+(.+)$", text, re.M)
    return h.group(1).strip() if h else ""


def _density(text: str, keywords) -> int:
    t = (text or "").lower()
    return sum(t.count(k) for k in keywords)


def parse_llms_index(text: str):
    """Markdown index lines `[title](url)` or `- [title](url): desc` → (title, url, desc).
    Handles both Anthropic (dash + description) and OpenAI Codex (bare link) formats."""
    out = []
    for m in re.finditer(r"^\s*-?\s*\[([^\]]+)\]\((https?://[^)]+)\)\s*:?\s*(.*)$", text, re.M):
        out.append((m.group(1).strip(), m.group(2).strip(), m.group(3).strip()))
    return out


def _matches(text: str, keywords) -> bool:
    t = (text or "").lower()
    return any(k in t for k in keywords)


def relevant_doc_pages(provider: str, keywords, limit: int = 8) -> list[DocPage]:
    """Clean doc pages for a provider, filtered to the axis keywords, via its best official surface."""
    cfg = DOC_SOURCES[provider]
    kws = [k.lower() for k in keywords]
    scored: list[tuple[int, DocPage]] = []   # (relevance density, page) → rank, then take top `limit`
    if cfg["kind"] == "llms_index":
        cands = [(t, u, d) for (t, u, d) in parse_llms_index(_get(cfg["url"]))
                 if u.endswith(".md") and _matches(f"{t} {d} {u}", kws)][:16]   # per-page .md only
        for title, url, _ in cands:
            txt = _get(url)
            if txt.strip():
                scored.append((_density(txt, kws), DocPage(url, txt, title)))
    elif cfg["kind"] == "asset_md":
        for url in enumerate_asset_docs(cfg["home"], cfg["asset_re"]):
            txt = _get(url)   # gzip-aware
            if txt.strip() and _matches(txt, kws):
                scored.append((_density(txt, kws), DocPage(url, txt, _md_title(txt) or url.rsplit("/", 1)[-1])))
    scored.sort(key=lambda s: s[0], reverse=True)   # densest (most on-axis) pages first
    return [p for _, p in scored[:limit]]


class CachedPages(RetrievalProvider):
    """Serve already-fetched clean doc text to the grounding judge (keyed by url)."""

    def __init__(self, pages: list[DocPage]):
        self._by_url = {p.url: p.text for p in pages}

    def search(self, query, *, max_results=8, include_domains=None):
        return []

    def fetch(self, url):
        text = self._by_url.get(url, "")
        return FetchedPage(url=url, status=200 if text else 404, text=text,
                           content_hash=content_hash(text))
