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


@dataclass(frozen=True)
class Settings:
    project_id: str | None
    region: str
    model: str
    offline: bool
    tavily_api_key: str | None = None  # enables live web search (discovery)

    @property
    def mode(self) -> str:
        return "OFFLINE (stub LLM; no Vertex calls)" if self.offline else "LIVE (Vertex AI Claude)"


def settings() -> Settings:
    _load_dotenv()
    offline = os.environ.get("TAXO_OFFLINE", "1").strip().lower() in ("1", "true", "yes")
    return Settings(
        project_id=os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID"),
        region=os.environ.get("CLOUD_ML_REGION", "us-east5"),
        model=os.environ.get("VERTEX_MODEL", "claude-opus-4-8"),
        offline=offline,
        tavily_api_key=os.environ.get("TAVILY_API_KEY") or None,
    )
