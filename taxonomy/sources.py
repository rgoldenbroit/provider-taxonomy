"""Source-quality tiers — official > reputable > low.

Drives two things: the **derived confidence** of a record (no longer hand-set) and an
**admission rule** (a lone low-quality source can't reach 'confirmed'). This is what
keeps content-farm / AI-spam pages from silently substantiating a claim.
"""

from __future__ import annotations

from urllib.parse import urlparse

# A provider's own documentation / blog / announcement domains — authoritative.
OFFICIAL_DOMAINS = {
    "Anthropic": ["docs.anthropic.com", "anthropic.com", "code.claude.com", "claude.com"],
    "OpenAI": ["platform.openai.com", "developers.openai.com", "openai.com",
               "help.openai.com", "cookbook.openai.com"],
    "Google": ["ai.google.dev", "discuss.ai.google.dev", "cloud.google.com",
               "developers.googleblog.com", "blog.google", "deepmind.google",
               "firebase.google.com", "jules.google", "antigravity.google",
               "gemini.google", "developer.chrome.com"],
}
# any provider's official domain (used when no provider context is supplied)
_OFFICIAL_ANY = tuple({d for ds in OFFICIAL_DOMAINS.values() for d in ds})

# Reputable independent press / references / developer hubs — corroborating, not authoritative.
_REPUTABLE = (
    "wikipedia.org", "github.com", "github.io", "techcrunch.com", "theverge.com",
    "arstechnica.com", "wired.com", "venturebeat.com", "infoworld.com", "zdnet.com",
    "simonwillison.net", "infoq.com", "thenewstack.io", "huggingface.co",
    "stackoverflow.com", "reuters.com", "nytimes.com", "bloomberg.com",
    "theinformation.com", "semianalysis.com", "developer.mozilla.org",
)
# Known low-quality / content-farm / AI-spam hosts seen in runs (extend as needed).
_JUNK = ("agentpedia.codes", "pas7.com.ua")

_CONFIDENCE = {"official": "high", "reputable": "medium", "low": "low"}


def host(url: str | None) -> str:
    return urlparse(url or "").netloc.lower()


def source_tier(url: str | None, provider: str | None = None) -> str:
    """official | reputable | low. With a provider, 'official' means *that* provider's
    own domains; without one, any provider's official domain counts."""
    h = host(url)
    if not h or any(j in h for j in _JUNK):
        return "low"
    official = OFFICIAL_DOMAINS.get(provider, []) if provider else _OFFICIAL_ANY
    if any(d in h for d in official):
        return "official"
    if any(d in h for d in _REPUTABLE):
        return "reputable"
    return "low"


def derive_confidence(tier: str) -> str:
    """Confidence follows source quality — computed, not asserted."""
    return _CONFIDENCE.get(tier, "low")
