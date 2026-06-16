"""Selection steps the trust gates don't cover: ranking and completeness.

Grounding verifies a record *exists*; it cannot verify that a model is the
*most capable* one, or that a provider×capability set is *complete*. Those are
the two error classes that produced a wrong flagship (Gemini 3.1 Pro vs 3.5 Pro)
and a missing product (Antigravity). These steps close that gap:

- ``rank_flagship`` — given a provider's model lineup, pick the single most
  capable / latest one for the ``flagship-model`` capability.
- ``completeness_critic`` — given the offerings found for a provider×capability,
  surface notable ones that are missing, so omissions are flagged not silent.

Both reason over supplied evidence via the LLM (web access is blocked on this
Vertex project, so they use the model's knowledge + the candidates given, not a
live search).
"""

from __future__ import annotations

from .vertex_client import LLMClient

RANK_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["flagship_name", "rationale"],
    "properties": {
        "flagship_name": {"type": "string"},
        "rationale": {"type": "string"},
    },
}

COMPLETENESS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["missing"],
    "properties": {
        "missing": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "why"],
                "properties": {"name": {"type": "string"}, "why": {"type": "string"}},
            },
        }
    },
}

_RANK_SYSTEM = (
    "You select a provider's flagship model: its single MOST CAPABLE, general-purpose, "
    "generally-available model as of the given date. Prefer the latest, highest-capability "
    "GA model over fast/cheap tiers or preview-only models. Return the exact name from the list."
)

_COMPLETENESS_SYSTEM = (
    "You audit coverage. Given a provider, a capability, and the offerings already found, "
    "list notable offerings for that provider+capability that are MISSING from the found list. "
    "Only real, current offerings; do not repeat found items; return an empty list if complete."
)


def rank_flagship(provider: str, candidates: list[dict], llm: LLMClient,
                  as_of: str = "June 2026") -> dict:
    listing = "\n".join(f"- {c['name']}: {c.get('note', '')}" for c in candidates)
    prompt = (f"Provider: {provider}\nDate: {as_of}\nCandidate models:\n{listing}\n\n"
              "Which single model is the flagship (most capable general-purpose GA model)?")
    return llm.structured(system=_RANK_SYSTEM, prompt=prompt, schema=RANK_SCHEMA,
                          label=f"rank:{provider}")


def completeness_critic(provider: str, capability_name: str, found_names: list[str],
                        llm: LLMClient, as_of: str = "June 2026") -> dict:
    prompt = (f"Provider: {provider}\nCapability: {capability_name}\nDate: {as_of}\n"
              f"Already found: {', '.join(found_names) or 'none'}\n\n"
              "What notable offerings for this provider+capability are missing?")
    return llm.structured(system=_COMPLETENESS_SYSTEM, prompt=prompt, schema=COMPLETENESS_SCHEMA,
                          label=f"complete:{provider}:{capability_name}")
