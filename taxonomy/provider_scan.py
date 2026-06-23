"""Provider-first, evidence-first feature discovery for one capability axis.

Replaces grid-mint discovery (one templated node per provider×axis) with: read the
provider's OFFICIAL docs, extract the features the page actually documents *under their
real names*, then ground each. Two LLM steps live here — `extract_features` (pull real
named features off a fetched page) and `completeness_queries` (a critic that names what's
still missing and proposes follow-up queries, enabling loop-until-dry coverage).

Grounding/classification stays in `triage.py`; this module only finds + names. Names come
from the page, never a template.
"""

from __future__ import annotations

from .retrieval.base import RetrievalError
from .sources import _JUNK

# provider → its agentic-coding product node + OFFICIAL first-party domains ONLY.
# Note: forums (community./discuss.) and third-party blogs are excluded (see is_official).
# Google is scoped to the coding-agent products (antigravity.google / jules.google) — NOT
# ai.google.dev, which is the Gemini/ADK platform (a different product that caused drift).
PROVIDERS = {
    "Anthropic": {
        "product_id": "anthropic-claude-code", "product": "Claude Code",
        "domains": ["anthropic.com", "claude.com"],   # covers docs./code./support.*.claude(.anthropic).com
    },
    "OpenAI": {
        "product_id": "openai-codex", "product": "Codex",
        "domains": ["openai.com"],                     # developers./platform./help./cookbook.openai.com
    },
    "Google": {
        "product_id": "google-antigravity-2-0", "product": "Antigravity",
        "domains": ["antigravity.google", "jules.google"],
    },
}

_FORUM_PREFIXES = ("community.", "discuss.", "forum.", "support-community.")
_MAX_PAGE_CHARS = 20000


def is_official(host: str, provider: str) -> bool:
    """First-party docs only: provider's own domain, but NOT its user forums or junk hosts."""
    host = (host or "").lower()
    if not host or any(host.startswith(p) for p in _FORUM_PREFIXES):
        return False
    if any(j in host for j in _JUNK):
        return False
    return any(host == d or host.endswith("." + d) for d in PROVIDERS[provider]["domains"])

# ---- step 1: extract real-named features off a fetched official page ----
EXTRACT_SYSTEM = (
    "You extract documented product features from an OFFICIAL documentation page. "
    "Report ONLY what the page actually states — never infer, generalize, or add features not present. "
    "Use the provider's OWN terminology, verbatim, for each feature name (e.g. the page's heading), not a "
    "generic label. If the page does not cover the asked-about axis, return an empty list.\n\n"
    "Report only NODE-WORTHY features: a distinct, named capability a competing product could ALSO have "
    "(something you'd compare across providers). EXCLUDE — these are at most sub-features, never top-level: "
    "individual slash-commands (e.g. /agents), config keys or CLI flags (e.g. max_depth, --explore), API "
    "symbols/class names (e.g. ParallelAgent, output_key), UI labels, and marketing phrases. "
    "Stay STRICTLY on the named PRODUCT given — do NOT report features of the provider's OTHER products or "
    "frameworks. Return at most ~6 genuine top-level features; put finer detail under subfeatures."
)
EXTRACT_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["features"],
    "properties": {"features": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["name", "claim", "quote", "level"],
        "properties": {
            "name": {"type": "string", "description": "verbatim, as the page names it"},
            "claim": {"type": "string", "description": "one-line factual claim about the feature"},
            "quote": {"type": "string", "description": "a verbatim supporting sentence from the page"},
            "level": {"type": "string", "enum": ["feature", "subfeature"]},
            "parent_hint": {"type": "string", "description": "if subfeature, the feature it belongs under"},
            "status": {"type": "string",
                       "enum": ["active", "preview", "beta", "deprecated", "sunset", "unknown"]},
        },
    }}},
}


def extract_features(llm, page_text, url, provider, product, axis_name, axis_desc):
    prompt = (
        f"PROVIDER: {provider}\nPRODUCT: {product}\n"
        f"AXIS OF INTEREST: {axis_name} — {axis_desc}\n\n"
        f"PAGE (fetched from {url}):\n{(page_text or '')[:_MAX_PAGE_CHARS]}\n\n"
        "List the distinct features this page documents that are relevant to the axis. For each: the "
        "verbatim name the page uses, a one-line claim, a verbatim supporting quote, level "
        "(feature or subfeature), parent_hint (the feature a subfeature belongs under), and lifecycle "
        "status if the page states one. Return JSON."
    )
    out = llm.structured(system=EXTRACT_SYSTEM, prompt=prompt, schema=EXTRACT_SCHEMA,
                         label=f"extract:{provider}:{axis_name}")
    feats = out.get("features", []) if isinstance(out, dict) else []
    for f in feats:
        f["_url"] = url
    return feats


# ---- step 2: completeness critic — what's still missing + how to find it ----
COMPLETENESS_SYSTEM = (
    "You are a completeness critic for a cross-provider feature catalog. Given the NODE-WORTHY features "
    "already captured for one provider's product on one axis, identify documented top-level capabilities "
    "that are likely STILL MISSING, and propose official-docs search queries to find them. Only flag "
    "genuine, comparable, top-level features of THIS specific product — not slash-commands, config keys, "
    "or features of the provider's OTHER products/frameworks. Scope queries to the product's official docs. "
    "If coverage looks complete, return empty lists — do not invent gaps."
)
COMPLETENESS_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["missing", "queries"],
    "properties": {
        "missing": {"type": "array", "items": {"type": "string"}},
        "queries": {"type": "array", "items": {"type": "string"}},
    },
}


def completeness_queries(llm, provider, product, axis_name, axis_desc, captured_names):
    prompt = (
        f"PROVIDER: {provider}\nPRODUCT: {product}\nAXIS: {axis_name} — {axis_desc}\n"
        f"FEATURES CAPTURED SO FAR: {', '.join(captured_names) or '(none)'}\n\n"
        "What documented features on this axis are likely still MISSING for this product? Return `missing` "
        "(short labels) and up to 3 official-docs search `queries` to locate them."
    )
    out = llm.structured(system=COMPLETENESS_SYSTEM, prompt=prompt, schema=COMPLETENESS_SCHEMA,
                         label=f"critic:{provider}:{axis_name}")
    if not isinstance(out, dict):
        return [], []
    return out.get("missing", []), out.get("queries", [])


# ---- step 3: consolidate raw extracted items into a clean comparison set ----
CONSOLIDATE_SYSTEM = (
    "You consolidate raw extracted documentation items into a clean cross-provider comparison set. "
    "The input mixes genuine top-level features with their facets, doc sections, and near-duplicates. "
    "Merge them into a SMALL set of distinct, top-level, COMPARABLE features (max 6) — the things you'd "
    "line up against other providers — using the provider's real terminology. Demote finer items to "
    "subfeatures under the right feature. Never invent anything not in the input. Each feature keeps a "
    "representative source_url drawn from its constituent items."
)
CONSOLIDATE_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["features"],
    "properties": {"features": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["name", "claim", "source_url"],
        "properties": {
            "name": {"type": "string"}, "claim": {"type": "string"}, "source_url": {"type": "string"},
            "status": {"type": "string",
                       "enum": ["active", "preview", "beta", "deprecated", "sunset", "unknown"]},
            "subfeatures": {"type": "array", "items": {"type": "string"}},
        }}}},
}


def consolidate_features(llm, provider, product, axis_name, items):
    """Collapse raw extracted items → ≤6 distinct comparable features (real names) + subfeatures."""
    if not items:
        return []
    listing = "\n".join(
        f"- {it['name']} [{it.get('level', 'feature')}] ({it.get('_url', '')}): {(it.get('claim') or '')[:120]}"
        for it in items)
    prompt = (
        f"PROVIDER: {provider}\nPRODUCT: {product}\nAXIS: {axis_name}\n\n"
        f"EXTRACTED ITEMS:\n{listing}\n\n"
        "Consolidate into at most 6 distinct, comparable top-level features with the provider's real "
        "names; fold the rest in as subfeatures. Keep a representative source_url per feature. Return JSON."
    )
    out = llm.structured(system=CONSOLIDATE_SYSTEM, prompt=prompt, schema=CONSOLIDATE_SCHEMA,
                         label=f"consolidate:{provider}:{axis_name}")
    return out.get("features", []) if isinstance(out, dict) else []


def search_official(retrieval, provider, query, max_results=8):
    """Official-docs-only search. Scoped to the provider's first-party domains AND hard-filtered by
    is_official (forums/junk/off-product dropped). NO unscoped fallback — if official docs surface
    nothing, that is a real, honest gap, not a cue to scrape blogs."""
    from urllib.parse import urlparse
    try:
        res = retrieval.search(query, max_results=max_results,
                               include_domains=PROVIDERS[provider]["domains"])
    except (RetrievalError, NotImplementedError, TypeError):
        res = []
    return [r for r in res if is_official(urlparse(r.url).netloc, provider)]
