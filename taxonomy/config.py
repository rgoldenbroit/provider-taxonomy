"""Runtime configuration, resolved from the environment / ``.env.local``.

Auth is keyless: ADC locally, Workload Identity Federation in CI. This module
only reads non-secret identifiers (project id, region, model). No credential is
ever read or stored here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .schema import REPO_ROOT

_ENV_FILE = REPO_ROOT / ".env.local"


def _load_dotenv() -> None:
    """Minimal ``.env.local`` reader (KEY=VALUE), without overriding real env vars."""
    if not _ENV_FILE.exists():
        return
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_LEDGER_DIR = REPO_ROOT / "evidence"


# Steps that are judgment-heavy run on the primary (Opus) model; everything mechanical
# (extraction, grounding-judge, classification, admissibility) runs on the cheaper judge model.
# Routing is BY STEP and deterministic — record and replay must derive the same model so the
# content-addressed ledger key (which includes the model) matches. Do not route dynamically.
_JUDGMENT_STEPS = frozenset({"consolidate", "insight"})


@dataclass(frozen=True)
class Settings:
    project_id: str | None
    region: str
    model: str
    offline: bool
    judge_model: str = "claude-sonnet-4-6"  # mechanical steps (extract/judge/classify) — cheaper tier
    tavily_api_key: str | None = None  # enables live web search (discovery)
    ledger_mode: str = "off"           # off | record | replay — evidence ledger for reproducibility

    @property
    def mode(self) -> str:
        return "OFFLINE (stub LLM; no Vertex calls)" if self.offline else "LIVE (Vertex AI Claude)"


def route_model(label: str | None, cfg: "Settings") -> str:
    """Deterministic per-step model choice. `consolidate:`/`insight:` → primary (Opus);
    all other steps (extract/judge/triage/admit) → the cheaper judge model (Sonnet)."""
    step = (label or "").split(":", 1)[0]
    return cfg.model if step in _JUDGMENT_STEPS else cfg.judge_model


def settings() -> Settings:
    _load_dotenv()
    offline = os.environ.get("TAXO_OFFLINE", "1").strip().lower() in ("1", "true", "yes")
    ledger_mode = os.environ.get("TAXO_LEDGER", "off").strip().lower()
    if ledger_mode not in ("off", "record", "replay"):
        ledger_mode = "off"
    return Settings(
        project_id=os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID"),
        region=os.environ.get("CLOUD_ML_REGION", "us-east5"),
        model=os.environ.get("VERTEX_MODEL", "claude-opus-4-8"),
        judge_model=os.environ.get("VERTEX_JUDGE_MODEL", "claude-sonnet-4-6"),
        offline=offline,
        tavily_api_key=os.environ.get("TAVILY_API_KEY") or None,
        ledger_mode=ledger_mode,
    )
