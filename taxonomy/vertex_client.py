"""LLM access: one interface, two backends.

The engine (discover / triage / trust) calls :class:`LLMClient` and never touches
the SDK directly. Two implementations:

- :class:`VertexLLM` — Claude on Vertex AI (``AnthropicVertex``). Adaptive thinking,
  ``effort: high``, structured outputs (``output_config.format``), streaming, and a
  **client-side** refusal fallback (Vertex has no server-side ``fallbacks``).
- :class:`StubLLM` — offline, deterministic. Returns registered canned responses or,
  failing that, a minimal schema-valid instance. Lets the whole pipeline (and the
  gold-set eval) run with no GCP credentials.

``get_llm()`` picks the backend from :func:`taxonomy.config.settings`.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from .config import Settings, settings


class LLMError(RuntimeError):
    pass


class LLMRefusal(LLMError):
    """The model declined (``stop_reason == "refusal"``) and no fallback succeeded."""


# --------------------------------------------------------------------------- #
# Deterministic minimal instance from a JSON-schema (supported subset)        #
# --------------------------------------------------------------------------- #

def _resolve_ref(schema: dict, root: dict) -> dict:
    seen = 0
    while isinstance(schema, dict) and "$ref" in schema:
        ref = schema["$ref"]
        node: Any = root
        for part in ref[2:].split("/"):
            node = node[part]
        schema = node
        seen += 1
        if seen > 32:
            break
    return schema


def instance_from_schema(schema: dict, root: dict | None = None) -> Any:
    """A minimal, deterministic, schema-valid value. Used only by the stub LLM."""
    root = root or schema
    schema = _resolve_ref(schema, root)
    if "enum" in schema:
        return schema["enum"][0]
    t = schema.get("type")
    if t == "object":
        props: dict = schema.get("properties", {})
        required = schema.get("required", list(props.keys()))
        out: dict[str, Any] = {}
        for key in required:
            out[key] = instance_from_schema(props[key], root) if key in props else None
        return out
    if t == "array":
        items = schema.get("items")
        return [instance_from_schema(items, root)] if items is not None else []
    if t == "string":
        return "2026-01-01" if schema.get("format") == "date" else "stub"
    if t == "integer":
        return 0
    if t == "number":
        return 0.0
    if t == "boolean":
        return False
    return None


# --------------------------------------------------------------------------- #
# Interface                                                                    #
# --------------------------------------------------------------------------- #

class LLMClient(ABC):
    @abstractmethod
    def structured(self, *, system: str, prompt: str, schema: dict, label: str | None = None) -> Any:
        """Return a JSON value constrained to ``schema``."""

    @abstractmethod
    def ping(self) -> str:
        """Cheap health check; returns a short string."""


# --------------------------------------------------------------------------- #
# Offline stub                                                                 #
# --------------------------------------------------------------------------- #

class StubLLM(LLMClient):
    def __init__(self, responses: dict[str, Any] | None = None):
        self.responses: dict[str, Any] = dict(responses or {})
        self.calls: list[dict] = []  # recorded prompts, for tests/inspection

    def structured(self, *, system: str, prompt: str, schema: dict, label: str | None = None) -> Any:
        self.calls.append({"label": label, "system": system, "prompt": prompt})
        if label is not None and label in self.responses:
            return self.responses[label]
        return instance_from_schema(schema)

    def ping(self) -> str:
        return "offline-stub"


# --------------------------------------------------------------------------- #
# Vertex AI Claude                                                             #
# --------------------------------------------------------------------------- #

def _first_text(message: Any) -> str:
    for block in getattr(message, "content", []):
        if getattr(block, "type", None) == "text":
            return block.text
    return ""


def _is_transient(exc: Exception) -> bool:
    """Worth retrying: timeouts, dropped connections, 429/5xx. NOT 400s (e.g. context
    overflow) or auth errors, which should fail fast."""
    import anthropic  # lazy: offline path never imports the SDK
    import httpx
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError,
                        anthropic.APITimeoutError, anthropic.APIConnectionError)):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return getattr(exc, "status_code", None) in (408, 409, 425, 429, 500, 502, 503, 504)
    return False


class VertexLLM(LLMClient):
    def __init__(self, *, project_id: str | None, region: str, model: str,
                 fallback_model: str | None = None, max_tokens: int = 8000,
                 max_retries: int = 3, backoff: float = 2.0, ledger=None):
        if not project_id:
            raise LLMError("ANTHROPIC_VERTEX_PROJECT_ID is not set; cannot reach Vertex.")
        try:
            from anthropic import AnthropicVertex  # lazy: offline path never imports the SDK
        except ImportError as exc:
            raise LLMError(
                "anthropic[vertex] is not installed; run `pip install -e '.[vertex]'` "
                "to enable live Vertex calls (or keep TAXO_OFFLINE=1)."
            ) from exc

        self._client = AnthropicVertex(project_id=project_id, region=region)
        self.model = model
        self.fallback_model = fallback_model
        self.max_tokens = max_tokens
        self._max_retries = max_retries
        self._backoff = backoff
        self._ledger = ledger   # optional evidence ledger for record/replay (default: none → live each call)

    # Structured output via a forced tool call, not output_config.format: the
    # structured_outputs feature is commonly blocked by the Vertex partner-model
    # org policy, whereas tool use is allowed. Forced tool_choice is incompatible
    # with thinking, so thinking is omitted here.
    _TOOL_NAME = "emit_result"

    def _invoke(self, *, system: str, prompt: str, schema: dict | None, model: str) -> Any:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        if schema is not None:
            kwargs["tools"] = [{
                "name": self._TOOL_NAME,
                "description": "Return the result as a single structured JSON object.",
                "input_schema": schema,
            }]
            kwargs["tool_choice"] = {"type": "tool", "name": self._TOOL_NAME}

        message = None
        for attempt in range(self._max_retries + 1):
            try:
                with self._client.messages.stream(**kwargs) as stream:
                    message = stream.get_final_message()
                break
            except Exception as exc:  # retry transient infra failures; re-raise everything else
                if attempt < self._max_retries and _is_transient(exc):
                    import time
                    time.sleep(self._backoff * (2 ** attempt))
                    continue
                raise

        if getattr(message, "stop_reason", None) == "refusal":
            # Vertex has no server-side fallback — retry once on the fallback model.
            if self.fallback_model and model != self.fallback_model:
                return self._invoke(system=system, prompt=prompt, schema=schema, model=self.fallback_model)
            raise LLMRefusal(f"model {model} refused the request")
        return message

    def _structured_live(self, *, system: str, prompt: str, schema: dict) -> Any:
        message = self._invoke(system=system, prompt=prompt, schema=schema, model=self.model)
        for block in getattr(message, "content", []):
            if getattr(block, "type", None) == "tool_use" and block.name == self._TOOL_NAME:
                return block.input
        text = _first_text(message)  # fallback: some models answer in text
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError("model did not return a structured tool call") from exc

    def structured(self, *, system: str, prompt: str, schema: dict, label: str | None = None) -> Any:
        if self._ledger is not None and self._ledger.active:
            from .ledger import llm_key  # lazy: only the ledgered path needs it
            key = llm_key(model=self.model, system=system, prompt=prompt, schema=schema)
            return self._ledger.cached("llm", key,
                                       lambda: self._structured_live(system=system, prompt=prompt, schema=schema),
                                       meta={"label": label, "model": self.model})
        return self._structured_live(system=system, prompt=prompt, schema=schema)

    def ping(self) -> str:
        with self._client.messages.stream(
            model=self.model,
            max_tokens=16,
            messages=[{"role": "user", "content": "Reply with the single word: pong"}],
        ) as stream:
            message = stream.get_final_message()
        return _first_text(message).strip() or "(empty)"


def build_ledger(cfg: Settings | None = None):
    """Construct the evidence ledger from config (None when mode is 'off')."""
    cfg = cfg or settings()
    if getattr(cfg, "ledger_mode", "off") == "off":
        return None
    from .config import _LEDGER_DIR
    from .ledger import Ledger
    return Ledger(_LEDGER_DIR, mode=cfg.ledger_mode)


def get_llm(cfg: Settings | None = None, *, responses: dict[str, Any] | None = None) -> LLMClient:
    cfg = cfg or settings()
    if cfg.offline:
        return StubLLM(responses=responses)
    return VertexLLM(project_id=cfg.project_id, region=cfg.region, model=cfg.model,
                     ledger=build_ledger(cfg))
