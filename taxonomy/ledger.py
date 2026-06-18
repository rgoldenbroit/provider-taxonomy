"""Content-addressed evidence ledger — the "lockfile for facts".

Records every fetched page and every LLM call, keyed by a content hash, so a build
can be **replayed deterministically and offline** from the committed evidence. This
is what makes the catalog reproducible (replay the ledger → identical result) and
auditable (the ledger *is* the show-your-work trail).

Modes:
- ``record`` — live calls run; each result is written to the ledger (miss → compute → store).
- ``replay`` — no live calls; a miss raises ``LedgerMiss`` (the ledger must hold the evidence).
- ``off``    — bypass entirely (the legacy path; nothing is stored or required).

The achievable guarantee is **replay-determinism** (like ``npm ci`` reproducing from a
lockfile), not bit-reproducibility on fresh re-derivation — models and the web drift.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

RECORD, REPLAY, OFF = "record", "replay", "off"


def digest(*parts: str) -> str:
    """Stable content hash over the given parts (NUL-separated so concatenation is unambiguous)."""
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def llm_key(*, model: str, system: str, prompt: str, schema: Any) -> str:
    return digest("llm", model, system, prompt, json.dumps(schema, sort_keys=True, default=str))


def page_key(url: str) -> str:
    return digest("page", url)


class LedgerMiss(KeyError):
    """A replay-mode lookup for evidence the ledger does not contain."""


class Ledger:
    def __init__(self, root: str | Path, mode: str = OFF):
        self.root = Path(root)
        self.mode = mode

    @property
    def active(self) -> bool:
        return self.mode in (RECORD, REPLAY)

    def _path(self, space: str, key: str) -> Path:
        return self.root / space / key[:2] / f"{key}.json"   # 2-char shard to keep dirs small

    def get(self, space: str, key: str) -> dict | None:
        p = self._path(space, key)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return None

    def put(self, space: str, key: str, value: Any, meta: dict | None = None) -> None:
        p = self._path(space, key)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {"key": key, "value": value, **(meta or {})}
        p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def cached(self, space: str, key: str, compute: Callable[[], Any], meta: dict | None = None) -> Any:
        """Return stored evidence for ``key``; in record mode compute+store on miss; in
        replay mode a miss is an error (the build must be fully evidenced)."""
        hit = self.get(space, key)
        if hit is not None:
            return hit["value"]
        if self.mode == REPLAY:
            raise LedgerMiss(f"{space}/{key} not in ledger (replay mode — no live calls allowed)")
        value = compute()
        self.put(space, key, value, meta)
        return value

    def stats(self) -> dict[str, int]:
        return {space.name: sum(1 for _ in space.rglob("*.json"))
                for space in self.root.iterdir() if space.is_dir()} if self.root.exists() else {}
