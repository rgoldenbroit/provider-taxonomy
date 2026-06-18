"""Phase A — add the 7 feature-level capability axes to the spine.

Adds them to BOTH the seed (examples.json, the source of truth) and the working
catalog (data/taxonomy.json). Idempotent: skips ids already present; inserts
before the reserved 'unclassified' bucket so it stays last. Validates both files.

    .venv/bin/python scripts/add_feature_axes.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from taxonomy.validate import validate  # noqa: E402

FEATURE_AXES = [
    {"id": "managed-agent-runtime", "tier": "developer_platform", "name": "Managed agent runtime",
     "description": "Provider-hosted execution of agents: the provider runs the agent loop and sandboxes its tools, instead of you self-hosting.",
     "aliases": ["managed agents", "hosted agents", "agent runtime"]},
    {"id": "mcp-connectors", "tier": "developer_platform", "name": "MCP & connectors",
     "description": "Model Context Protocol support: hosted MCP servers, connector registries, and managed tool connectors.",
     "aliases": ["MCP", "Model Context Protocol", "connectors", "hosted MCP"]},
    {"id": "agent-memory", "tier": "developer_platform", "name": "Agent memory",
     "description": "Persistent, cross-session memory an agent can read and write across runs.",
     "aliases": ["memory", "persistent memory", "agent memory"]},
    {"id": "code-execution-sandbox", "tier": "developer_platform", "name": "Code execution & sandbox",
     "description": "Server-side code execution in an isolated sandbox for agent actions.",
     "aliases": ["sandbox", "code interpreter", "code execution"]},
    {"id": "agent-evals-observability", "tier": "developer_platform", "name": "Agent evals & observability",
     "description": "Tracing, evaluation, and monitoring of agent runs.",
     "aliases": ["evals", "observability", "tracing", "monitoring"]},
    {"id": "guardrails-safety", "tier": "developer_platform", "name": "Guardrails & safety",
     "description": "Policy and safety controls on an agent's inputs, outputs, and actions.",
     "aliases": ["guardrails", "safety controls", "policy"]},
    {"id": "subagents-orchestration", "tier": "developer_platform", "name": "Subagents & orchestration",
     "description": "Spawning and coordinating multiple agents / subagents within a single task.",
     "aliases": ["subagents", "multi-agent", "orchestration"]},
]


def _add_axes(path: Path) -> int:
    doc = json.loads(path.read_text(encoding="utf-8"))
    caps = doc["capabilities"]
    have = {c["id"] for c in caps}
    new = [a for a in FEATURE_AXES if a["id"] not in have]
    if not new:
        print(f"  {path.name}: all 7 axes already present")
        return 0
    # insert before 'unclassified' so the reserved bucket stays last
    idx = next((i for i, c in enumerate(caps) if c["id"] == "unclassified"), len(caps))
    doc["capabilities"] = caps[:idx] + new + caps[idx:]
    issues = validate(doc)
    if issues:
        print(f"  {path.name}: ✗ {len(issues)} schema issue(s) — NOT writing")
        for i in issues[:5]:
            print("     ", i)
        return 1
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"  {path.name}: +{len(new)} axes → {len(doc['capabilities'])} capabilities, ✓ valid")
    return 0


def main() -> int:
    rc = 0
    for name in ("examples.json", "data/taxonomy.json"):
        rc |= _add_axes(ROOT / name)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
