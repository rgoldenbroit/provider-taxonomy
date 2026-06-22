"""Phase C — ground curated SUB-FEATURES (one level below features) for agentic-coding.

The engine won't reliably discover sub-feature granularity, so the operator curates the
claim + an official-doc target (hybrid); the trust pipeline GROUNDS each via `triage_one`
(the judge must find the claim on the fetched official page). ADMIT ONLY WHAT GROUNDS — an
ungrounded sub-feature is dropped (honest empty), never fabricated.

Per feature: one official-domain-scoped search finds the canonical doc URL, then every
sub-feature of that feature is grounded against it. Idempotent + upsert: an existing
`scaffold` id is replaced in place with the grounded record; new ones are appended.

    TAXO_OFFLINE=0 .venv/bin/python scripts/ground_subfeatures.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from taxonomy.config import settings  # noqa: E402
from taxonomy.retrieval import get_retrieval  # noqa: E402
from taxonomy.retrieval.base import RetrievalError  # noqa: E402
from taxonomy.schema import DEFAULT_DATA_PATH  # noqa: E402
from taxonomy.sources import OFFICIAL_DOMAINS  # noqa: E402
from taxonomy.triage import triage_one  # noqa: E402
from taxonomy.validate import validate  # noqa: E402
from taxonomy.vertex_client import get_llm  # noqa: E402

AS_OF = "2026-06-21"

# Precise official doc pages (override search where we know the canonical URL — the judge
# needs the SPECIFIC page that states the claim, not a release-notes/community page).
PRECISE_URLS = {
    "anthropic-claude-code-subagents-orchestration": "https://code.claude.com/docs/en/sub-agents",
    "anthropic-claude-code-mcp-connectors": "https://code.claude.com/docs/en/mcp",
    "anthropic-claude-code-agent-memory": "https://code.claude.com/docs/en/memory",
    "anthropic-claude-code-remote-control": "https://code.claude.com/docs/en/claude-code-on-the-web",
    "openai-codex-subagents-orchestration": "https://developers.openai.com/codex/config-reference",
    "google-antigravity-subagents-orchestration": "https://antigravity.google/docs/home",
}

# Each group: parent feature id, provider, axis, a search query to find the official doc,
# and the curated sub-features: (display name, id-slug, the verifiable claim = scope_note).
GROUPS = [
    # ---- Agent Management: subagents (the existing 9 scaffold, now grounded) ----
    ("anthropic-claude-code-subagents-orchestration", "Anthropic", "subagents-orchestration",
     "Claude Code subagents create custom",
     [("Definition files", "definition-files", "Claude Code subagents are defined as Markdown files with YAML frontmatter stored in a .claude/agents directory"),
      ("Tool scoping", "tool-scoping", "a Claude Code subagent can be granted a restricted set of allowed tools via its tools field"),
      ("Model per subagent", "model-per-subagent", "a Claude Code subagent can specify which model it runs on via its model field")]),
    ("openai-codex-subagents-orchestration", "OpenAI", "subagents-orchestration",
     "OpenAI Codex AGENTS.md agent instructions",
     [("Definition files", "definition-files", "Codex reads project instructions from an AGENTS.md file"),
      ("Tool scoping", "tool-scoping", "Codex can be configured to restrict the tools or commands an agent may run")]),
    ("google-antigravity-subagents-orchestration", "Google", "subagents-orchestration",
     "Antigravity agents manager multi-agent",
     [("Agent manager", "agent-manager", "Antigravity provides an Agent Manager surface to orchestrate multiple agents"),
      ("Artifacts", "artifacts", "Antigravity agents produce verifiable artifacts such as task lists and screenshots")]),

    # ---- Context & Memory: MCP (existing scaffold) + memory ----
    ("anthropic-claude-code-mcp-connectors", "Anthropic", "mcp-connectors",
     "Claude Code MCP connect servers",
     [("Local (stdio) servers", "local-stdio-servers", "Claude Code can connect to local MCP servers over stdio"),
      ("Remote (HTTP/SSE) servers", "remote-http-servers", "Claude Code can connect to remote MCP servers over HTTP or SSE")]),
    ("openai-openai-mcp-connectors-mcp-connectors", "OpenAI", "mcp-connectors",
     "OpenAI MCP connectors tools",
     [("Local (stdio) servers", "local-stdio-servers", "OpenAI tools can connect to local MCP servers"),
      ("Remote (HTTP/SSE) servers", "remote-http-servers", "OpenAI supports remote MCP servers over HTTP")]),
    ("anthropic-claude-code-agent-memory", "Anthropic", "agent-memory",
     "Claude Code memory CLAUDE.md",
     [("Project memory (CLAUDE.md)", "project-memory", "Claude Code reads project memory from a CLAUDE.md file in the project"),
      ("User memory", "user-memory", "Claude Code supports user-level memory shared across all projects")]),
    ("openai-codex-agent-memory", "OpenAI", "agent-memory",
     "OpenAI Codex AGENTS.md memory instructions",
     [("Project instructions (AGENTS.md)", "project-memory", "Codex persists project context via an AGENTS.md file")]),

    # ---- Execution & Safety: sandbox + guardrails ----
    ("anthropic-claude-code-code-execution-sandbox", "Anthropic", "code-execution-sandbox",
     "Claude Code sandbox network filesystem",
     [("Filesystem isolation", "filesystem-isolation", "Claude Code sandboxing restricts filesystem access for executed commands"),
      ("Network restrictions", "network-restrictions", "Claude Code sandboxing can restrict network access")]),
    ("openai-codex-code-execution-sandbox", "OpenAI", "code-execution-sandbox",
     "OpenAI Codex sandbox network access",
     [("Network policy", "network-policy", "Codex runs in a sandbox with configurable network access"),
      ("Filesystem isolation", "filesystem-isolation", "Codex executes in an isolated sandboxed environment")]),
    ("anthropic-anthropic-guardrails-guardrails-safety", "Anthropic", "guardrails-safety",
     "Claude Code permissions allowed tools",
     [("Permission modes", "permission-modes", "Claude Code offers permission modes that control when actions require approval"),
      ("Allow/deny tool rules", "allow-deny-rules", "Claude Code lets you allow or deny specific tools")]),
    ("openai-codex-guardrails-safety", "OpenAI", "guardrails-safety",
     "OpenAI Codex approval mode",
     [("Approval modes", "approval-modes", "Codex supports approval modes governing when it asks before acting")]),

    # ---- Quality & Ops: remote-control ----
    ("anthropic-claude-code-remote-control", "Anthropic", "remote-agent-control",
     "Claude Code on the web remote",
     [("Web sessions", "web-sessions", "Claude Code can run sessions from the web")]),
    ("openai-codex-cloud", "OpenAI", "remote-agent-control",
     "OpenAI Codex cloud delegate tasks",
     [("Cloud task delegation", "cloud-tasks", "Codex can delegate tasks to the cloud to run asynchronously")]),
]

# Missing FEATURE cells worth filling with a curated official source (parent = a product).
FEATURE_CELLS = [
    ("google-jules", "Google", "remote-agent-control", "Jules async coding agent GitHub",
     [("Jules async control", "jules-async", "Jules is an asynchronous agent that works on tasks remotely and opens pull requests")]),
]


def _slug_id(parent_id: str, slug: str) -> str:
    return f"{parent_id}-{slug}"


def _candidate(parent_id, provider, axis, name, slug, claim, url) -> dict:
    return {
        "id": _slug_id(parent_id, slug), "name": name, "kind": "feature",
        "parent_id": parent_id, "provider": provider,
        "capability_ids": [axis], "primary_capability_id": axis,
        "relation_within_capability": "partial", "surfaces": [], "status": "active",
        "review_status": "candidate", "scope_note": claim, "lifecycle": [],
        "source": {"url": url, "last_verified": AS_OF, "confidence": "low"},
    }


def _official_url(retrieval, provider, query, fallback=""):
    """Best official-domain result for the query; fall back to any top result, else ''."""
    doms = OFFICIAL_DOMAINS.get(provider, [])
    for scoped in (doms, None):
        try:
            res = retrieval.search(f"{query} 2026", max_results=6, include_domains=scoped)
        except (RetrievalError, NotImplementedError, TypeError):
            res = []
        if res:
            return res[0].url
    return fallback


def main() -> int:
    cfg = settings()
    if cfg.offline:
        print("ground_subfeatures needs live grounding + search: set TAXO_OFFLINE=0.", file=sys.stderr)
        return 1
    catalog = json.loads(DEFAULT_DATA_PATH.read_text(encoding="utf-8"))
    by_id = {p["id"]: i for i, p in enumerate(catalog["products"])}
    llm, retrieval = get_llm(cfg), get_retrieval(cfg)
    counts: Counter[str] = Counter()

    for parent_id, provider, axis, query, subs in (GROUPS + FEATURE_CELLS):
        if parent_id not in by_id:
            print(f"\n[SKIP missing parent] {parent_id}")
            continue
        url = PRECISE_URLS.get(parent_id) or _official_url(retrieval, provider, query)
        print(f"\n[{provider}] {parent_id}\n  source: {url or '(none found)'}")
        if not url:
            counts["no_source"] += len(subs)
            continue
        for name, slug, claim in subs:
            cand = _candidate(parent_id, provider, axis, name, slug, claim, url)
            try:
                outcome = triage_one(cand, dataset=catalog, llm=llm, retrieval=retrieval,
                                     evidence=claim, pinned_capability=axis)
            except (RetrievalError, NotImplementedError) as exc:
                print(f"  ERROR        {name:28} ({exc})")
                counts["error"] += 1
                continue
            rec = outcome.record
            rec["kind"], rec["parent_id"] = "feature", parent_id      # operator-known shape
            rec["primary_capability_id"], rec["capability_ids"] = axis, [axis]
            g = outcome.report.grounding.score
            print(f"  {outcome.decision.upper():12} {name:28} [g {g:.2f}]")
            counts[outcome.decision] += 1
            if outcome.decision in ("confirmed", "needs_review"):
                if rec["id"] in by_id:
                    catalog["products"][by_id[rec["id"]]] = rec    # upsert over the scaffold
                else:
                    by_id[rec["id"]] = len(catalog["products"])
                    catalog["products"].append(rec)
        DEFAULT_DATA_PATH.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")

    issues = validate(catalog)
    print(f"\n{dict(counts)}  ·  {'valid' if not issues else f'{len(issues)} schema issue(s)'}"
          f"  ·  {len(catalog['products'])} products total")
    for i in issues[:8]:
        print("   ", i)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
