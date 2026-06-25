# AI Provider Capability Matrix — Reference & Build Spec

Feed this whole file to Claude Code as the reference for building the comparison data.
It contains four things:

1. The **core idea** (one rule that makes everything scale)
2. The **schema** (the shape every entry must follow)
3. A **golden example** (Claude Code, rewritten into the neutral form — copy this pattern)
4. The **rules + definition of done** (paste the "done" block into `/goal`)

---

## 1. Core idea

> A **row** is a *capability*, phrased so any provider can answer it.
> The provider's *feature name* lives in the **cell**, not the row.

This is what keeps the matrix fair. If rows are named after one vendor's features,
that vendor always looks "complete" and everyone else looks full of gaps. Neutral
rows fix that — and they're also the "what, not how" framing the app is going for.

**Transformation examples (do this to every item):**

| Vendor wording (the "how") | Neutral capability (the "what") |
|---|---|
| CLAUDE.md files            | Project-scoped instruction file |
| /compact + auto compaction | Context compaction (manual + auto) |
| Skills                     | Packaged reusable extensions |
| Hooks                      | Lifecycle event hooks |
| /goal, /loop               | Goal-directed autonomous iteration |
| Worktrees                  | Parallel isolated workspaces |
| /advisor, Fast Mode        | Model & inference controls |

If a provider has a capability the others don't, **add it as a new neutral row**
with a note — do not drop it, and do not make it vendor-only.

---

## 2. Schema (YAML)

```yaml
product_category: agentic-coding          # one top-level capability from the grid
                                          # (e.g. agentic-coding, enterprise-chat, ...)
capability_groups:
  - name: <Group name>                    # e.g. Configuration, Context, Security
    layer: <user | platform | governance> # who cares about this group
    capabilities:
      - id: <kebab-case-id>
        name: <Neutral capability name>    # phrased as a yes/no/partial question any vendor can answer
        what: <1 sentence: what this capability is, vendor-neutral>
        tier: <core | advanced>            # core = differentiating must-haves; advanced = nice-to-have
        providers:
          anthropic:
            offering: <product name>       # e.g. Claude Code
            implementation: <vendor's name for it>   # or "unverified"
            status: <active | preview | sunset | none | unverified>
            evidence_url: <official docs URL>         # required unless status is unverified
            last_verified: <YYYY-MM-DD>               # date the evidence was checked
            notes: <optional caveats>
          google:
            offering: <product name>       # e.g. Antigravity
            implementation: ...
            status: ...
            evidence_url: ...
            last_verified: ...
            notes: ...
          openai:
            offering: <product name>       # e.g. Codex
            implementation: ...
            status: ...
            evidence_url: ...
            last_verified: ...
            notes: ...
```

**Status values** (reuse your existing system):
- `active` — shipping and generally available
- `preview` — beta / limited / early access
- `sunset` — being deprecated
- `none` — *confirmed* not offered (you found docs saying so)
- `unverified` — not yet checked. **This is the default.** Absence of evidence is NOT `none`.

---

## 3. Agentic-coding matrix — generated, grounded projection of the catalog

This section is GENERATED, not hand-edited. Rows come from `matrix/capabilities.yaml`; the
per-provider cells are grounded automatically by `scripts/build_matrix.py` — it projects the
official-docs-grounded catalog (`data/taxonomy.json`), then escalates to each vendor's official
doc pages and a domain-restricted live search, leaving a cell `unverified` only when no
first-party doc supports it. The canonical data is `data/agentic-matrix.json`; this block renders it.

7 capability groups, 37 neutral capabilities. **100/111 cells grounded, 11 honestly `unverified`** (no first-party doc — left
blank, not guessed). Every grounded cell links the official page it was verified against.

> Regenerate: `scripts/build_matrix.py` (re-ground, needs Vertex) → `scripts/render_matrix_md.py`
> (re-render this block) → `scripts/validate_matrix.py` (gate). The viewer reads the JSON directly.

```yaml
# matrix-data: agentic-coding   (the validator selects the YAML block containing this marker)
product_category: agentic-coding
capability_groups:
- name: Setup & extensibility
  layer: platform
  capabilities:
  - id: project-instruction-file
    name: Project-scoped instruction file
    what: A repo file giving the agent standing instructions and context.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: CLAUDE.md Project Memory
        status: active
        evidence_url: https://code.claude.com/docs/en/memory.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "CLAUDE.md Project Memory".
      google:
        offering: Antigravity
        implementation: Workspace Rules (.agents/rules)
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/rules-workflows.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Workspace Rules".
      openai:
        offering: Codex
        implementation: Project-Level AGENTS.md
        status: active
        evidence_url: https://developers.openai.com/codex/guides/agents-md.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Project-Level AGENTS.md".
  - id: packaged-extensions
    name: Packaged reusable extensions
    what: A way to bundle reusable capabilities/instructions the agent can load.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: Packaged reusable extensions
        status: active
        evidence_url: https://code.claude.com/docs/en/plugins-reference.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “A **plugin** is a self-contained directory of components that extends Claude Code with custom functionality. Plugin components include skills, agents, hooks, MC”'
      google:
        offering: Antigravity
        implementation: Plugins — namespaced bundles grouping skills, rules, MCP servers, and hooks
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/plugins.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Plugins".
      openai:
        offering: Codex
        implementation: Plugins
        status: active
        evidence_url: https://developers.openai.com/codex/plugins.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Plugins".
  - id: lifecycle-hooks
    name: Lifecycle event hooks
    what: Run custom logic on agent events (e.g. before/after a tool call, on stop).
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Agent Lifecycle Hooks
        status: preview
        evidence_url: https://code.claude.com/docs/en/agent-teams.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Agent Lifecycle Hooks".
      google:
        offering: Antigravity
        implementation: Lifecycle Hooks — custom local shell scripts at specific lifecycle points
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/hooks.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Lifecycle Hooks".
      openai:
        offering: Codex
        implementation: Lifecycle event hooks
        status: active
        evidence_url: https://developers.openai.com/codex/hooks.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “`PreToolUse`, `PermissionRequest`, `PostToolUse`, `PreCompact`, `PostCompact`, `UserPromptSubmit`, `SubagentStop`, and `Stop` run at turn scope. `SessionStart` ”'
  - id: output-customization
    name: Output & system-prompt customization
    what: Shape the agent's system prompt, persona, or output style.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Output Styles
        status: active
        evidence_url: https://code.claude.com/docs/en/agent-sdk/modifying-system-prompts.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Output Styles".
      google:
        offering: Antigravity
        implementation: Output & system-prompt customization
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/subagents.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Configuration: Define a custom system prompt and specific toolsets for read-only, write (including running terminal commands), and subagent delegation capabilit”'
      openai:
        offering: Codex
        implementation: Output & system-prompt customization
        status: active
        evidence_url: https://developers.openai.com/codex/guides/agents-md.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Codex reads `AGENTS.md` files before doing any work. By layering global guidance with project-specific overrides, you can start each task with consistent expect”'
  - id: model-selection
    name: Model selection
    what: Choose which underlying model the agent runs on.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: Model selection
        status: active
        evidence_url: https://code.claude.com/docs/en/model-config.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “For the `model` setting in Claude Code, you can configure either: A model alias or A model name... You can configure your model in several ways, listed in order”'
      google:
        offering: Antigravity
        implementation: Model selection
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/models.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Users can select which reasoning model they want to use within the model selector dropdown under the conversation prompt box”'
      openai:
        offering: Codex
        implementation: Per-Agent Model Selection
        status: active
        evidence_url: https://developers.openai.com/codex/subagents.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Per-Agent Model Selection".
- name: Connectors & context
  layer: platform
  capabilities:
  - id: tool-server-protocol
    name: External tool/connector protocol (MCP)
    what: A standard way to connect external tools, data, and services.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: Model Context Protocol (MCP)
        status: active
        evidence_url: https://code.claude.com/docs/en/mcp.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Model Context Protocol (MCP)".
      google:
        offering: Antigravity
        implementation: MCP Integration — Model Context Protocol support
        status: active
        evidence_url: https://antigravity.google/assets/docs/editor/ide-mcp.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "MCP Integration".
      openai:
        offering: Codex
        implementation: MCP (Model Context Protocol)
        status: active
        evidence_url: https://developers.openai.com/codex/concepts/customization.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "MCP (Model Context Protocol)".
  - id: mcp-server-management
    name: MCP server management & registry
    what: Install, configure, scope, and discover MCP servers.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: MCP server management & registry
        status: active
        evidence_url: https://code.claude.com/docs/en/agent-sdk/mcp.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Configure MCP servers to extend your agent with external tools. Covers transport types, tool search for large tool sets, authentication, and error handling. ...”'
      google:
        offering: Antigravity
        implementation: MCP Store — built-in store to browse, install, and authenticate MCP servers
        status: active
        evidence_url: https://antigravity.google/assets/docs/editor/ide-mcp.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "MCP Store".
      openai:
        offering: Codex
        implementation: MCP Server CLI Management
        status: active
        evidence_url: https://developers.openai.com/codex/concepts/customization.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "MCP Server CLI Management".
  - id: mcp-authentication
    name: MCP authentication
    what: Authenticate to MCP servers (OAuth, tokens).
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: MCP Auth Methods
        status: active
        evidence_url: https://code.claude.com/docs/en/agent-sdk/mcp.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "MCP Auth Methods".
      google:
        offering: Antigravity
        implementation: MCP Store — browse, install, and authenticate supported MCP servers
        status: active
        evidence_url: https://antigravity.google/assets/docs/editor/ide-mcp.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "MCP Store".
      openai:
        offering: Codex
        implementation: OAuth MCP Login
        status: active
        evidence_url: https://developers.openai.com/codex/mcp.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "OAuth MCP Login".
  - id: mcp-tool-governance
    name: MCP tool governance / allow-listing
    what: Control which MCP tools/resources the agent may use.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: MCP Tool Allow-listing
        status: active
        evidence_url: https://code.claude.com/docs/en/agent-sdk/mcp.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "MCP Tool Allow-listing".
      google:
        offering: Antigravity
        implementation: Per-Tool MCP Permission — grants access to a single named tool on a specific MCP server
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/permissions.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Per-Tool MCP Permission".
      openai:
        offering: Codex
        implementation: MCP tool governance / allow-listing
        status: active
        evidence_url: https://developers.openai.com/codex/config-reference
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “apps.<id>.tools.<tool>.enabled

          boolean

          Per-tool enabled override for an app tool (for example repos/list).”'
  - id: persistent-agent-memory
    name: Persistent agent memory
    what: Durable memory the agent keeps across turns/sessions.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Auto Memory (MEMORY.md)
        status: active
        evidence_url: https://code.claude.com/docs/en/glossary.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Auto Memory (MEMORY.md)".
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: '(Stage A: no catalog match — pending official-doc / Tavily grounding)'
      openai:
        offering: Codex
        implementation: Persistent agent memory
        status: active
        evidence_url: https://developers.openai.com/codex/memories
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Memories let Codex carry useful context from earlier threads into future work. After you enable memories, Codex can remember stable preferences, recurring workf”'
  - id: context-compaction
    name: Context compaction (manual + auto)
    what: Compress conversation/context to extend effective working memory.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: Context compaction (manual + auto)
        status: active
        evidence_url: https://code.claude.com/docs/en/context-window.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “kind: ''compact'', label: ''/compact'', tokens: 0, color: ''#D97757'', vis: ''brief'', desc: ''Replaces the conversation with a structured summary. You see a "Conversati”'
      google:
        offering: Antigravity
        implementation: Context compaction (manual + auto)
        status: preview
        evidence_url: https://ai.google.dev/gemini-api/docs/antigravity-agent
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Context compaction: Automatic context compaction (triggered at ~135k tokens) to support long-running, multi-turn sessions without losing context or hitting toke”'
      openai:
        offering: Codex
        implementation: Context compaction (manual + auto)
        status: active
        evidence_url: https://developers.openai.com/codex/cli
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Context management

          Compaction

          Counting tokens

          Prompt caching”'
  - id: prompt-caching
    name: Prompt / context caching
    what: Cache repeated context to cut latency and cost.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Prompt / context caching
        status: active
        evidence_url: https://code.claude.com/docs/en/prompt-caching.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Prompt caching makes Claude Code faster and more cost-efficient. Without caching, the API would reprocess your full history on every turn. With caching, it reus”'
      google:
        offering: Antigravity
        implementation: Prompt / context caching
        status: active
        evidence_url: https://ai.google.dev/gemini-api/docs/caching
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “In a typical AI workflow, you might pass the same input tokens over and over to a model. The Gemini API offers implicit caching to optimize performance and cost”'
      openai:
        offering: Codex
        implementation: Prompt / context caching
        status: active
        evidence_url: https://developers.openai.com/cookbook/examples/prompt_caching_201
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Prompt Caching can reduce time-to-first-token latency by up to 80% and input token costs by up to 90%. It works automatically on all API requests and has no add”'
- name: Agents & orchestration
  layer: user
  capabilities:
  - id: subagents
    name: Subagents / delegated agents
    what: Spawn focused sub-agents to handle parts of a task.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: Subagents
        status: active
        evidence_url: https://code.claude.com/docs/en/sub-agents.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Subagents".
      google:
        offering: Antigravity
        implementation: Subagents — multi-threaded async architecture delegating operations to parallel autonomous subagents
        status: active
        evidence_url: https://antigravity.google/assets/docs/cli/cli-subagents.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Subagents".
      openai:
        offering: Codex
        implementation: Subagent Workflows
        status: active
        evidence_url: https://developers.openai.com/codex/subagents.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Subagent Workflows".
  - id: agent-teams
    name: Multi-agent teams & messaging
    what: Coordinate multiple agents that share work and communicate.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Agent Teams
        status: preview
        evidence_url: https://code.claude.com/docs/en/agent-teams.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Agent Teams".
      google:
        offering: Antigravity
        implementation: Multi-Agent Orchestration — advanced orchestration with coordination, error recovery, and retries
        status: preview
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/subagents.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Multi-Agent Orchestration".
      openai:
        offering: Codex
        implementation: Project Manager Multi-Agent Workflow
        status: active
        evidence_url: https://developers.openai.com/codex/guides/agents-sdk.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Project Manager Multi-Agent Workflow".
  - id: workflows
    name: Workflows / saved automations
    what: Define repeatable, named multi-step task sequences.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Workflows / saved automations
        status: active
        evidence_url: https://code.claude.com/docs/en/workflows.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “When Claude writes a workflow for a task you''ll repeat, you can save that run''s script as a command. A process like a review you run on every branch then runs t”'
      google:
        offering: Antigravity
        implementation: Workflows — saved markdown files defining repeatable series of steps
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/rules-workflows.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Workflows".
      openai:
        offering: Codex
        implementation: Workflows / saved automations
        status: active
        evidence_url: https://developers.openai.com/codex/record-and-replay.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Record & Replay lets you demonstrate a workflow on your Mac and turn it into a reusable skill. Use it when the workflow is repetitive, depends on your preferenc”'
  - id: plan-mode
    name: Plan-then-execute mode
    what: Produce a reviewable plan before the agent edits anything.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Plan Mode
        status: active
        evidence_url: https://code.claude.com/docs/en/permission-modes.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Plan Mode".
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: '(Stage A: no catalog match — pending official-doc / Tavily grounding)'
      openai:
        offering: Codex
        implementation: Plan-then-execute mode
        status: active
        evidence_url: https://developers.openai.com/codex/cli
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Choose the approval mode that matches your comfort level before Codex edits or runs commands.”'
  - id: goal-directed-iteration
    name: Goal-directed autonomous iteration
    what: Set a verifiable "done" condition; the agent loops on its own until met.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: Goal-directed autonomous iteration
        status: active
        evidence_url: https://code.claude.com/docs/en/goal.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Set a completion condition with /goal and Claude keeps working across turns until the condition is met... The /goal command sets a completion condition and Clau”'
      google:
        offering: Antigravity
        implementation: Goal-directed autonomous iteration
        status: active
        evidence_url: https://antigravity.google/assets/docs/cli/cli-best-practices.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Once the agent proposes code, instruct it to run the local test command to verify its work. Watch the agent execute the command and iterate on the test outputs ”'
      openai:
        offering: Codex
        implementation: Goal-directed autonomous iteration
        status: active
        evidence_url: https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “A Goal gives Codex a completion condition: what should be true, how success should be checked, and what constraints must stay intact. ... With a Goal, Codex can”'
  - id: parallel-workspaces
    name: Parallel isolated workspaces
    what: Work on multiple branches/copies in parallel without collisions.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Worktree Isolation
        status: active
        evidence_url: https://code.claude.com/docs/en/glossary.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Worktree Isolation".
      google:
        offering: Antigravity
        implementation: Worktree Support — agents operate in dedicated Git worktrees to isolate parallel work
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/features.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Worktree Support".
      openai:
        offering: Codex
        implementation: Git Worktree Isolation
        status: active
        evidence_url: https://developers.openai.com/codex/app/automations.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Git Worktree Isolation".
- name: Runtime & background
  layer: platform
  capabilities:
  - id: cloud-execution-environment
    name: Cloud execution environment
    what: Run the agent in a managed cloud/container environment.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Claude Code on the Web
        status: preview
        evidence_url: https://code.claude.com/docs/en/claude-code-on-the-web.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Claude Code on the Web".
      google:
        offering: Antigravity
        implementation: Cloud execution environment
        status: preview
        evidence_url: https://ai.google.dev/gemini-api/docs/antigravity-agent
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “The Antigravity agent is a general-purpose managed agent on the Gemini API. A single API call gives you an agent that reasons, executes code, manages files, and”'
      openai:
        offering: Codex
        implementation: Cloud Environments
        status: active
        evidence_url: https://developers.openai.com/codex/cloud/environments.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Cloud Environments".
  - id: background-execution
    name: Background / async execution
    what: Run tasks in the background or asynchronously without blocking.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Background Agent Execution
        status: active
        evidence_url: https://code.claude.com/docs/en/sub-agents.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Background Agent Execution".
      google:
        offering: Antigravity
        implementation: Background Tasks — long-running operations asynchronously without blocking the primary agent
        status: active
        evidence_url: https://antigravity.google/assets/docs/cli/cli-subagents.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Background Tasks".
      openai:
        offering: Codex
        implementation: Standalone Automations
        status: active
        evidence_url: https://developers.openai.com/codex/app/automations.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Standalone Automations".
  - id: scheduled-runs
    name: Scheduled / triggered runs
    what: Run the agent on a schedule or trigger without supervision.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Schedule Trigger
        status: preview
        evidence_url: https://code.claude.com/docs/en/routines.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Schedule Trigger".
      google:
        offering: Antigravity
        implementation: Scheduled Tasks — schedule messages to agents with repeatable time-based triggers
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/features.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Scheduled Tasks".
      openai:
        offering: Codex
        implementation: Thread Automations
        status: active
        evidence_url: https://developers.openai.com/codex/app/automations.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Thread Automations".
- name: Execution & safety
  layer: governance
  capabilities:
  - id: sandboxing
    name: Sandboxed execution
    what: Run agent actions in an isolated environment to limit blast radius.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: Sandbox Runtime
        status: preview
        evidence_url: https://code.claude.com/docs/en/sandbox-environments.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Sandbox Runtime".
      google:
        offering: Antigravity
        implementation: Terminal Sandboxing — kernel-level / native OS isolation for terminal commands
        status: active
        evidence_url: https://antigravity.google/assets/docs/settings/ide-settings.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Terminal Sandboxing".
      openai:
        offering: Codex
        implementation: Sandbox
        status: active
        evidence_url: https://developers.openai.com/codex/concepts/sandboxing.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Sandbox".
  - id: permission-controls
    name: Tool permission controls
    what: Approve/deny what the agent is allowed to do.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: Permission System
        status: active
        evidence_url: https://code.claude.com/docs/en/permissions.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Permission System".
      google:
        offering: Antigravity
        implementation: Fine-Grained Permissions Engine — unified permission engine for every sensitive agent operation
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/permissions.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Fine-Grained Permissions Engine".
      openai:
        offering: Codex
        implementation: Approval Policy
        status: active
        evidence_url: https://developers.openai.com/codex/agent-approvals-security.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Approval Policy".
  - id: network-egress-control
    name: Network / egress control
    what: Restrict the agent's outbound network access.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Egress Firewall Control
        status: active
        evidence_url: https://code.claude.com/docs/en/devcontainer.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Egress Firewall Control".
      google:
        offering: Antigravity
        implementation: Independent Network Access Control — controls network connectivity for sandboxed commands
        status: active
        evidence_url: https://antigravity.google/assets/docs/settings/ide-settings.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Independent Network Access Control".
      openai:
        offering: Codex
        implementation: Network Access Control
        status: active
        evidence_url: https://developers.openai.com/codex/agent-approvals-security.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Network Access Control".
  - id: prompt-injection-protection
    name: Prompt-injection protection
    what: Defenses against malicious instructions in tool/web content.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Prompt Injection Protection
        status: active
        evidence_url: https://code.claude.com/docs/en/security.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Prompt Injection Protection".
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: '(Stage A: no catalog match — pending official-doc / Tavily grounding)'
      openai:
        offering: Codex
        implementation: Prompt-injection protection
        status: active
        evidence_url: https://developers.openai.com/codex/cloud/internet-access
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Prompt injection from untrusted web content... Prompt injection can happen when the agent retrieves and follows instructions from untrusted content (for example”'
  - id: security-scanning
    name: Security scanning / threat model
    what: Scan code/agent actions for security issues against a threat model.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Security Guidance Plugin
        status: active
        evidence_url: https://code.claude.com/docs/en/security-guidance.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Security Guidance Plugin".
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: '(Stage A: no catalog match — pending official-doc / Tavily grounding)'
      openai:
        offering: Codex
        implementation: Codex Security
        status: preview
        evidence_url: https://developers.openai.com/codex/security.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Codex Security".
  - id: dev-container-integration
    name: Dev-container integration
    what: Run the agent inside a defined dev container / isolated runtime.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Dev Container Integration
        status: active
        evidence_url: https://code.claude.com/docs/en/devcontainer.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Dev Container Integration".
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: '(Stage A: no catalog match — pending official-doc / Tavily grounding)'
      openai:
        offering: Codex
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: '(Stage A: no catalog match — pending official-doc / Tavily grounding)'
- name: Quality & ops
  layer: governance
  capabilities:
  - id: audit-logging
    name: Audit logging / telemetry
    what: A record of agent actions for review/compliance.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: OpenTelemetry Monitoring
        status: active
        evidence_url: https://code.claude.com/docs/en/monitoring-usage.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "OpenTelemetry Monitoring".
      google:
        offering: Antigravity
        implementation: Inspect Hooks — read-only, non-blocking hooks for logging, audit trails, and metrics
        status: active
        evidence_url: https://antigravity.google/assets/docs/sdk/sdk-overview.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Inspect Hooks".
      openai:
        offering: Codex
        implementation: Built-in Run Tracing
        status: active
        evidence_url: https://developers.openai.com/api/docs/guides/agents/integrations-observability.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Built-in Run Tracing".
  - id: code-review
    name: Automated code review
    what: The agent reviews diffs / PRs for issues before they land.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: Automated PR Code Review
        status: preview
        evidence_url: https://code.claude.com/docs/en/code-review.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Automated PR Code Review".
      google:
        offering: Antigravity
        implementation: Automated code review
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/skills.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “name: code-review

          description: Reviews code changes for bugs, style issues, and best practices. Use when reviewing PRs or checking code quality.”'
      openai:
        offering: Codex
        implementation: AI Code Review
        status: active
        evidence_url: https://developers.openai.com/codex/integrations/github.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "AI Code Review".
  - id: cost-usage-tracking
    name: Cost & usage tracking
    what: Track and cap token spend / usage.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Cost Tracking
        status: active
        evidence_url: https://code.claude.com/docs/en/admin-setup.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Cost Tracking".
      google:
        offering: Antigravity
        implementation: Cost & usage tracking
        status: active
        evidence_url: https://antigravity.google/assets/docs/cli/cli-credits.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “You can monitor your active quota and credit consumption directly inside the CLI: Statusline Indicator: The right side of the CLI statusline displays your remai”'
      openai:
        offering: Codex
        implementation: Cost & usage tracking
        status: active
        evidence_url: https://developers.openai.com/codex/enterprise/governance
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Workspace and personal usage breakdowns, including credit and token usage by product surface or model”'
  - id: evals-testing
    name: Evals / testing harness
    what: Run evaluations / test suites against the agent's behavior.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Evals / testing harness
        status: active
        evidence_url: https://docs.anthropic.com/en/docs/test-and-evaluate/eval-tool
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “The Claude Console features an Evaluation tool that allows you to test your prompts under various scenarios... If you update your original prompt text, you can ”'
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: '(Stage A: no catalog match — pending official-doc / Tavily grounding)'
      openai:
        offering: Codex
        implementation: Evals API
        status: sunset
        evidence_url: https://developers.openai.com/api/docs/guides/evals.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Evals API".
  - id: checkpoint-rewind
    name: Checkpoint / rewind
    what: Save points you can roll back to, and undo agent changes.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: Checkpoint / rewind
        status: active
        evidence_url: https://code.claude.com/docs/en/agent-sdk/file-checkpointing.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “File checkpointing tracks file modifications made through the Write, Edit, and NotebookEdit tools during an agent session, allowing you to rewind files to any p”'
      google:
        offering: Antigravity
        implementation: Checkpoint / rewind
        status: active
        evidence_url: https://antigravity.google/assets/docs/cli/cli-best-practices.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Type `/rewind` (or `/undo`) to roll back your conversation thread to a previous stable checkout.”'
      openai:
        offering: Codex
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: '(Stage A: no catalog match — pending official-doc / Tavily grounding)'
  - id: resume-session
    name: Resume / fork session
    what: Continue or branch a previous session.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Resume / fork session
        status: active
        evidence_url: https://code.claude.com/docs/en/sessions.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Branching creates a copy of the conversation so far and switches you into it, leaving the original intact. Use it to try a different approach without losing the”'
      google:
        offering: Antigravity
        implementation: Resume / fork session
        status: active
        evidence_url: https://antigravity.google/assets/docs/cli/cli-conversations.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Resume prior development threads, scope active histories to local workspaces, and fork conversations to experiment with alternate architectures. ... You can ret”'
      openai:
        offering: Codex
        implementation: Multi-Device Session Handoff
        status: active
        evidence_url: https://developers.openai.com/codex/remote-connections.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Multi-Device Session Handoff".
- name: Remote control & surfaces
  layer: user
  capabilities:
  - id: remote-control
    name: Remote control (mobile / web)
    what: Steer or approve agent runs from a phone or remote client.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Remote Control
        status: preview
        evidence_url: https://code.claude.com/docs/en/remote-control.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Remote Control".
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: '(Stage A: no catalog match — pending official-doc / Tavily grounding)'
      openai:
        offering: Codex
        implementation: Remote Action Approval
        status: active
        evidence_url: https://developers.openai.com/codex/remote-connections.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Remote Action Approval".
  - id: notifications
    name: Notifications
    what: Push notifications on run progress / completion.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Mobile Push Notifications
        status: active
        evidence_url: https://code.claude.com/docs/en/remote-control.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Mobile Push Notifications".
      google:
        offering: Antigravity
        implementation: Notifications
        status: active
        evidence_url: https://antigravity.google/assets/docs/cli/cli-reference.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “**`notifications`**           | boolean    | `false`             | Emits system desktop and terminal bell chime notifications upon task completions.”'
      openai:
        offering: Codex
        implementation: Task Completion Notifications
        status: active
        evidence_url: https://developers.openai.com/codex/remote-connections.md
        last_verified: '2026-06-22'
        notes: Catalog-grounded via "Task Completion Notifications".
  - id: chat-surface-integration
    name: Chat-surface integration
    what: Drive the agent from chat/issue tools (Slack, Linear, channels).
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Claude Code in Slack
        status: active
        evidence_url: https://code.claude.com/docs/en/slack.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Claude Code in Slack".
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: '(Stage A: no catalog match — pending official-doc / Tavily grounding)'
      openai:
        offering: Codex
        implementation: Codex for Linear
        status: active
        evidence_url: https://developers.openai.com/codex/integrations/linear.md
        last_verified: '2026-06-24'
        notes: Catalog-grounded via "Codex for Linear".
  - id: access-surfaces
    name: Access surfaces
    what: 'Where the agent can be used: terminal, IDE, web, cloud, mobile.'
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Access surfaces
        status: active
        evidence_url: https://code.claude.com/docs/en/desktop.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “Run on your machine, in the [cloud](#run-long-running-tasks-remotely), or over [SSH](#ssh-sessions)... The integrated terminal lets you run commands alongside y”'
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: '(Stage A: no catalog match — pending official-doc / Tavily grounding)'
      openai:
        offering: Codex
        implementation: Access surfaces
        status: active
        evidence_url: https://developers.openai.com/codex/cli/reference.md
        last_verified: '2026-06-25'
        notes: 'Grounded against official docs: “codex app: Launch the Codex desktop app on macOS or Windows. On macOS, Codex can open a workspace path; on Windows, Codex prints the path to open. ... codex: La”'
```

---

## 4. Rules for Claude Code

When extending this matrix to other providers and other product categories:

1. **Vendor-neutral rows only.** Never name a row after one vendor's feature. The vendor's
   name goes in `implementation`.
2. **New product category = new rows.** Do NOT reuse agentic-coding rows for enterprise-chat,
   etc. First draft a fresh neutral capability list for the category, then fill cells.
3. **No invented facts.** Every `active / preview / sunset / none` claim needs an
   `evidence_url` (official docs/changelog/pricing). If you can't verify, set `unverified`
   and leave evidence blank. Absence of evidence is NOT `none`.
4. **Capabilities a vendor uniquely has → add as a neutral row** with a note. Don't drop it,
   don't make it vendor-only.
5. **Tag every capability** `core` or `advanced`, and every group `user | platform | governance`.
6. **One change at a time, verifiable.** Work category-by-category (or provider-by-provider),
   not all at once.

---

## 5. Definition of done (paste into `/goal`)

> The agentic-coding matrix is complete when: every capability has all three providers
> (anthropic, google, openai) present; every cell has a `status` of active/preview/sunset/
> none/unverified; every cell whose status is NOT `unverified` has a non-empty `evidence_url`
> and a `last_verified` date; no row is named after a single vendor's feature; the YAML
> parses and validates against the schema in section 2; and a printed validation summary
> shows 0 errors. Stop after 30 turns if not met.

Have Claude write a small validator script that prints the summary, since `/goal`'s checker
only reads what's in the transcript — the printed result is what it evaluates against.
For large work, run this as a sequence of smaller goals (one provider or one category each)
rather than a single mega-goal.
