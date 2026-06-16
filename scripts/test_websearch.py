"""Probe: does the Vertex web_search server tool work on this project (org policy)?"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anthropic import AnthropicVertex

from taxonomy.config import settings

cfg = settings()
client = AnthropicVertex(project_id=cfg.project_id, region=cfg.region)

for tool_version in ("web_search_20250305", "web_search_20260209"):
    print(f"\n=== trying {tool_version} ===")
    try:
        resp = client.messages.create(
            model=cfg.model,
            max_tokens=1024,
            tools=[{"type": tool_version, "name": "web_search", "max_uses": 3}],
            messages=[{"role": "user", "content":
                       "As of June 2026, what is Google's single most capable flagship Gemini "
                       "model, and does Google have an agentic coding product called Antigravity? "
                       "Search the web and cite sources."}],
        )
        print("stop_reason:", resp.stop_reason)
        for b in resp.content:
            if b.type == "text":
                print("TEXT:", b.text[:700])
            else:
                print("block:", b.type)
        print(f"\n>>> {tool_version} WORKS")
        break
    except Exception as exc:  # report the exact failure (likely org policy or unknown tool)
        print(f">>> {tool_version} FAILED: {type(exc).__name__}: {str(exc)[:300]}")
