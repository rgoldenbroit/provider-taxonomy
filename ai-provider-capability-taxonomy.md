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

## 3. Agentic-coding matrix — complete, grounded in official docs

Every Anthropic / Google / OpenAI cell below is grounded in official documentation. The matrix
mirrors the catalog's own information architecture (`data/taxonomy.json`): 7 capability groups
spanning 37 neutral capabilities. Most cells were mined from the grounded catalog; cells the
catalog didn't cover were verified directly against each vendor's docs. Each `evidence_url` is the
documentation page that supports the cell, and `last_verified` is the date it was checked. Status is
mapped into this file's enum (`beta` → `preview`, `deprecated` → `sunset`).

**93/111 cells are grounded; 18 are honestly `unverified`** — where a provider has no
first-party doc for a capability (e.g. Antigravity, a desktop/CLI tool, has no grounded remote-control,
evals, or cost-tracking node). Those are left blank rather than guessed — honesty over false
completeness, per the engine's own pitch. (`implementation` may still name a likely in-product feature
on an `unverified` cell, as the schema allows.)

> Run `python scripts/validate_matrix.py` to re-check this block against the section-2 schema
> and the definition of done. It prints the validation summary `/goal` evaluates against.

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
        implementation: CLAUDE.md (+ imports, local/org scopes)
        status: active
        evidence_url: https://code.claude.com/docs/en/memory.md
        last_verified: '2026-06-24'
        notes: ''
      google:
        offering: Antigravity
        implementation: Rules / Global Rules (.md)
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/rules-workflows.md
        last_verified: '2026-06-24'
        notes: ''
      openai:
        offering: Codex
        implementation: AGENTS.md (+ overrides, global defaults)
        status: active
        evidence_url: https://developers.openai.com/codex/guides/agents-md.md
        last_verified: '2026-06-24'
        notes: ''
  - id: packaged-extensions
    name: Packaged reusable extensions
    what: A way to bundle reusable capabilities/instructions the agent can load.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: Skills (+ plugins)
        status: active
        evidence_url: https://code.claude.com/docs/en/sub-agents.md
        last_verified: '2026-06-22'
        notes: Grounded via skill preloading; Skills + plugins both supported.
      google:
        offering: Antigravity
        implementation: Plugins
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/plugins.md
        last_verified: '2026-06-24'
        notes: ''
      openai:
        offering: Codex
        implementation: Plugins / Skills
        status: active
        evidence_url: https://developers.openai.com/codex/plugins.md
        last_verified: '2026-06-24'
        notes: ''
  - id: lifecycle-hooks
    name: Lifecycle event hooks
    what: Run custom logic on agent events (e.g. before/after a tool call, on stop).
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Hooks (PreToolUse, etc.)
        status: active
        evidence_url: https://code.claude.com/docs/en/permissions.md
        last_verified: '2026-06-22'
        notes: Grounded on the permissions page; agent lifecycle hooks are in preview.
      google:
        offering: Antigravity
        implementation: Lifecycle hooks (Pre/PostToolUse, Stop)
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/hooks.md
        last_verified: '2026-06-24'
        notes: ''
      openai:
        offering: Codex
        implementation: Hooks (PreToolUse, SessionStart, Pre/PostCompact, Stop, …)
        status: active
        evidence_url: https://developers.openai.com/codex/hooks.md
        last_verified: '2026-06-25'
        notes: 'Full hooks framework: SessionStart, PreToolUse, PostToolUse, PermissionRequest, Pre/PostCompact, UserPromptSubmit, SubagentStop, Stop.'
  - id: output-customization
    name: Output & system-prompt customization
    what: Shape the agent's system prompt, persona, or output style.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Output styles + tailored system prompts
        status: active
        evidence_url: https://code.claude.com/docs/en/agent-sdk/modifying-system-prompts.md
        last_verified: '2026-06-24'
        notes: ''
      google:
        offering: Antigravity
        implementation: Rules (guide behavior + style)
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/rules-workflows.md
        last_verified: '2026-06-25'
        notes: Steered via Rules (the instruction mechanism), which guide agent behavior and style; no separate output-style preset.
      openai:
        offering: Codex
        implementation: personality / /personality + model_verbosity + instructions
        status: active
        evidence_url: https://developers.openai.com/codex/config-reference.md
        last_verified: '2026-06-25'
        notes: Dedicated 'personality' setting (per-thread or /personality) + model_verbosity override + model_instructions_file.
  - id: model-selection
    name: Model selection
    what: Choose which underlying model the agent runs on.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: /model (aliases + Sonnet / Opus / Haiku / Fable)
        status: active
        evidence_url: https://code.claude.com/docs/en/model-config.md
        last_verified: '2026-06-25'
        notes: Switch mid-session with /model, or set a default via the model setting in settings.json.
      google:
        offering: Antigravity
        implementation: Reasoning-model selector (+ /model)
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/models.md
        last_verified: '2026-06-25'
        notes: Model-selector dropdown (Gemini + Claude + GPT-OSS options); also the /model CLI command.
      openai:
        offering: Codex
        implementation: Per-agent model selection
        status: active
        evidence_url: https://developers.openai.com/codex/subagents.md
        last_verified: '2026-06-22'
        notes: ''
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
        implementation: MCP (Model Context Protocol)
        status: active
        evidence_url: https://code.claude.com/docs/en/mcp.md
        last_verified: '2026-06-24'
        notes: ''
      google:
        offering: Antigravity
        implementation: MCP integration
        status: active
        evidence_url: https://antigravity.google/assets/docs/editor/ide-mcp.md
        last_verified: '2026-06-24'
        notes: ''
      openai:
        offering: Codex
        implementation: MCP (client + server modes)
        status: active
        evidence_url: https://developers.openai.com/codex/mcp.md
        last_verified: '2026-06-24'
        notes: ''
  - id: mcp-server-management
    name: MCP server management & registry
    what: Install, configure, scope, and discover MCP servers.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: Managed MCP config, install scopes, desktop connectors
        status: active
        evidence_url: https://code.claude.com/docs/en/managed-mcp.md
        last_verified: '2026-06-24'
        notes: ''
      google:
        offering: Antigravity
        implementation: MCP Store + transport modes
        status: active
        evidence_url: https://antigravity.google/assets/docs/editor/ide-mcp.md
        last_verified: '2026-06-24'
        notes: ''
      openai:
        offering: Codex
        implementation: MCP server CLI management + transports
        status: active
        evidence_url: https://developers.openai.com/codex/mcp.md
        last_verified: '2026-06-24'
        notes: ''
  - id: mcp-authentication
    name: MCP authentication
    what: Authenticate to MCP servers (OAuth, tokens).
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: MCP auth methods
        status: active
        evidence_url: https://code.claude.com/docs/en/agent-sdk/mcp.md
        last_verified: '2026-06-22'
        notes: ''
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: No MCP-authentication-specific node grounded for Antigravity — verify.
      openai:
        offering: Codex
        implementation: OAuth + bearer-token MCP login
        status: active
        evidence_url: https://developers.openai.com/codex/mcp.md
        last_verified: '2026-06-22'
        notes: ''
  - id: mcp-tool-governance
    name: MCP tool governance / allow-listing
    what: Control which MCP tools/resources the agent may use.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: MCP tool allow-listing + connector suppression
        status: active
        evidence_url: https://code.claude.com/docs/en/agent-sdk/mcp.md
        last_verified: '2026-06-22'
        notes: ''
      google:
        offering: Antigravity
        implementation: Per-tool / wildcard MCP permissions
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/permissions.md
        last_verified: '2026-06-22'
        notes: ''
      openai:
        offering: Codex
        implementation: MCP tool/resource exposure controls
        status: active
        evidence_url: https://developers.openai.com/codex/concepts/customization.md
        last_verified: '2026-06-22'
        notes: ''
  - id: persistent-agent-memory
    name: Persistent agent memory
    what: Durable memory the agent keeps across turns/sessions.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Auto memory (MEMORY.md) + per-agent memory
        status: active
        evidence_url: https://code.claude.com/docs/en/glossary.md
        last_verified: '2026-06-24'
        notes: ''
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: No persistent agent-memory node grounded for Antigravity — verify.
      openai:
        offering: Codex
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: No persistent agent-memory node grounded for Codex — verify.
  - id: context-compaction
    name: Context compaction (manual + auto)
    what: Compress conversation/context to extend effective working memory.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: /compact + automatic compaction
        status: active
        evidence_url: https://code.claude.com/docs/en/context-window.md
        last_verified: '2026-06-25'
        notes: Manual /compact at task breaks + auto-compaction as the context window fills.
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: No official Antigravity doc describes context compaction/auto-summarization (checked the CLI slash-command reference, SDK lifecycle hooks, and IDE/CLI hook events) — genuine gap.
      openai:
        offering: Codex
        implementation: /compact + auto-compaction (model_auto_compact_token_limit)
        status: active
        evidence_url: https://developers.openai.com/codex/cli/slash-commands.md
        last_verified: '2026-06-25'
        notes: Manual /compact; automatic compaction via the model_auto_compact_token_limit config key.
  - id: prompt-caching
    name: Prompt / context caching
    what: Cache repeated context to cut latency and cost.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Automatic prompt caching
        status: active
        evidence_url: https://code.claude.com/docs/en/prompt-caching.md
        last_verified: '2026-06-25'
        notes: Claude Code manages server-side prefix caching automatically; no user config required.
      google:
        offering: Antigravity
        implementation: Context caching (via the Gemini API)
        status: active
        evidence_url: https://ai.google.dev/gemini-api/docs/caching
        last_verified: '2026-06-25'
        notes: A Gemini model-API feature Antigravity inherits; no Antigravity-specific caching doc page.
      openai:
        offering: Codex
        implementation: Automatic prompt caching (OpenAI API)
        status: active
        evidence_url: https://developers.openai.com/api/docs/guides/prompt-caching
        last_verified: '2026-06-25'
        notes: An OpenAI API platform feature (automatic prefix caching) that Codex inherits; not Codex-specific config.
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
        implementation: Subagents (+ Agent Teams)
        status: active
        evidence_url: https://code.claude.com/docs/en/sub-agents.md
        last_verified: '2026-06-24'
        notes: Agent Teams in preview.
      google:
        offering: Antigravity
        implementation: Subagents (sync + async)
        status: active
        evidence_url: https://antigravity.google/assets/docs/cli/cli-subagents.md
        last_verified: '2026-06-24'
        notes: ''
      openai:
        offering: Codex
        implementation: Subagents / custom agents
        status: active
        evidence_url: https://developers.openai.com/codex/subagents.md
        last_verified: '2026-06-24'
        notes: ''
  - id: agent-teams
    name: Multi-agent teams & messaging
    what: Coordinate multiple agents that share work and communicate.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Agent Teams + peer-to-peer messaging
        status: active
        evidence_url: https://code.claude.com/docs/en/agent-teams.md
        last_verified: '2026-06-24'
        notes: Agent Teams in preview; dispatch/monitor active.
      google:
        offering: Antigravity
        implementation: Multi-agent teamwork + inter-agent messaging
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/subagents.md
        last_verified: '2026-06-24'
        notes: Multi-agent teamwork in preview; inter-agent messaging active.
      openai:
        offering: Codex
        implementation: Multi-agent workflows + agent hand-offs
        status: active
        evidence_url: https://developers.openai.com/codex/guides/agents-sdk.md
        last_verified: '2026-06-24'
        notes: ''
  - id: workflows
    name: Workflows / saved automations
    what: Define repeatable, named multi-step task sequences.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Workflows (NL authoring, saved slash commands)
        status: active
        evidence_url: https://code.claude.com/docs/en/workflows.md
        last_verified: '2026-06-24'
        notes: ''
      google:
        offering: Antigravity
        implementation: Workflows (agent-generated)
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/rules-workflows.md
        last_verified: '2026-06-24'
        notes: ''
      openai:
        offering: Codex
        implementation: Agent SDK workflows
        status: active
        evidence_url: https://developers.openai.com/codex/guides/agents-sdk.md
        last_verified: '2026-06-24'
        notes: Workflow orchestration via the Agents SDK.
  - id: plan-mode
    name: Plan-then-execute mode
    what: Produce a reviewable plan before the agent edits anything.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Plan Mode (+ Ultraplan, plan-approval gate)
        status: active
        evidence_url: https://code.claude.com/docs/en/permission-modes.md
        last_verified: '2026-06-22'
        notes: ''
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: No distinct plan-then-execute mode grounded for Antigravity — verify.
      openai:
        offering: Codex
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: No distinct plan-mode node grounded for Codex (read-only sandbox mode exists, but that's not a plan gate) — verify.
  - id: goal-directed-iteration
    name: Goal-directed autonomous iteration
    what: Set a verifiable "done" condition; the agent loops on its own until met.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: /goal, /loop, Auto Mode, Routines
        status: active
        evidence_url: https://code.claude.com/docs/en/routines.md
        last_verified: '2026-06-24'
        notes: Auto Mode + Routines in preview; /goal + /loop run in the CLI (this matrix was built with /goal).
      google:
        offering: Antigravity
        implementation: Always-Proceed / autonomy levels
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/permissions.md
        last_verified: '2026-06-22'
        notes: An autonomy control, not a verifiable-goal loop — partial fit.
      openai:
        offering: Codex
        implementation: Full-access / workspace-write autonomy
        status: active
        evidence_url: https://developers.openai.com/codex/concepts/sandboxing.md
        last_verified: '2026-06-24'
        notes: An autonomy/approval mode, not a named goal-condition loop — partial fit.
  - id: parallel-workspaces
    name: Parallel isolated workspaces
    what: Work on multiple branches/copies in parallel without collisions.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Worktree isolation
        status: active
        evidence_url: https://code.claude.com/docs/en/glossary.md
        last_verified: '2026-06-24'
        notes: ''
      google:
        offering: Antigravity
        implementation: Worktree support
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/features.md
        last_verified: '2026-06-22'
        notes: ''
      openai:
        offering: Codex
        implementation: Git worktree isolation
        status: active
        evidence_url: https://developers.openai.com/codex/app/automations.md
        last_verified: '2026-06-22'
        notes: ''
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
        implementation: Cloud sessions (Claude Code on the Web) + SDK containers
        status: preview
        evidence_url: https://code.claude.com/docs/en/claude-code-on-the-web.md
        last_verified: '2026-06-24'
        notes: Web cloud sessions in preview; Agent SDK container deployment is active.
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: No managed cloud-execution environment grounded for Antigravity (a desktop/CLI tool) — verify.
      openai:
        offering: Codex
        implementation: Cloud environments (+ base image, container caching)
        status: active
        evidence_url: https://developers.openai.com/codex/cloud/environments.md
        last_verified: '2026-06-24'
        notes: ''
  - id: background-execution
    name: Background / async execution
    what: Run tasks in the background or asynchronously without blocking.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Background agent execution
        status: active
        evidence_url: https://code.claude.com/docs/en/sub-agents.md
        last_verified: '2026-06-22'
        notes: ''
      google:
        offering: Antigravity
        implementation: Asynchronous execution model
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/subagents.md
        last_verified: '2026-06-24'
        notes: ''
      openai:
        offering: Codex
        implementation: Delegated async cloud runs
        status: active
        evidence_url: https://developers.openai.com/codex/cloud/environments.md
        last_verified: '2026-06-24'
        notes: Codex delegates long tasks to async cloud runs.
  - id: scheduled-runs
    name: Scheduled / triggered runs
    what: Run the agent on a schedule or trigger without supervision.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Scheduled tasks / Routines (+ GitHub Actions)
        status: active
        evidence_url: https://code.claude.com/docs/en/scheduled-tasks.md
        last_verified: '2026-06-24'
        notes: Routines in preview.
      google:
        offering: Antigravity
        implementation: Scheduled / background tasks
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/features.md
        last_verified: '2026-06-24'
        notes: ''
      openai:
        offering: Codex
        implementation: Automations (scheduled / triggered)
        status: active
        evidence_url: https://developers.openai.com/codex/app/automations.md
        last_verified: '2026-06-24'
        notes: ''
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
        implementation: OS + container sandbox
        status: active
        evidence_url: https://code.claude.com/docs/en/sandboxing.md
        last_verified: '2026-06-22'
        notes: Sandbox Runtime in beta.
      google:
        offering: Antigravity
        implementation: Terminal / CLI sandbox
        status: active
        evidence_url: https://antigravity.google/assets/docs/cli/cli-sandbox.md
        last_verified: '2026-06-24'
        notes: ''
      openai:
        offering: Codex
        implementation: Seatbelt / Bubblewrap / Windows sandbox
        status: active
        evidence_url: https://developers.openai.com/codex/concepts/sandboxing.md
        last_verified: '2026-06-24'
        notes: ''
  - id: permission-controls
    name: Tool permission controls
    what: Approve/deny what the agent is allowed to do.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: Permission system (allow / ask / deny)
        status: active
        evidence_url: https://code.claude.com/docs/en/permissions.md
        last_verified: '2026-06-24'
        notes: ''
      google:
        offering: Antigravity
        implementation: Fine-grained permissions engine
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/permissions.md
        last_verified: '2026-06-24'
        notes: ''
      openai:
        offering: Codex
        implementation: Approval policy (+ permission profiles)
        status: active
        evidence_url: https://developers.openai.com/codex/agent-approvals-security.md
        last_verified: '2026-06-24'
        notes: Permission profiles in beta.
  - id: network-egress-control
    name: Network / egress control
    what: Restrict the agent's outbound network access.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Network isolation proxy + egress firewall
        status: active
        evidence_url: https://code.claude.com/docs/en/sandboxing.md
        last_verified: '2026-06-22'
        notes: ''
      google:
        offering: Antigravity
        implementation: Independent network access control
        status: active
        evidence_url: https://antigravity.google/assets/docs/settings/ide-settings.md
        last_verified: '2026-06-22'
        notes: ''
      openai:
        offering: Codex
        implementation: Network access control (+ sandbox proxy)
        status: active
        evidence_url: https://developers.openai.com/codex/agent-approvals-security.md
        last_verified: '2026-06-24'
        notes: Network rules / sandbox proxy in beta.
  - id: prompt-injection-protection
    name: Prompt-injection protection
    what: Defenses against malicious instructions in tool/web content.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Prompt-injection protection + input sanitization
        status: active
        evidence_url: https://code.claude.com/docs/en/security.md
        last_verified: '2026-06-24'
        notes: ''
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: No prompt-injection-specific defense node grounded for Antigravity — verify.
      openai:
        offering: Codex
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: No prompt-injection-specific defense node grounded for Codex (code security scanning exists, which is distinct) — verify.
  - id: security-scanning
    name: Security scanning / threat model
    what: Scan code/agent actions for security issues against a threat model.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Security guidance plugin + custom scan rules
        status: active
        evidence_url: https://code.claude.com/docs/en/security-guidance.md
        last_verified: '2026-06-24'
        notes: ''
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: No security-scanning node grounded for Antigravity — verify.
      openai:
        offering: Codex
        implementation: Codex security (scanning, threat model)
        status: active
        evidence_url: https://developers.openai.com/codex/security.md
        last_verified: '2026-06-24'
        notes: Cloud commit scanning in preview.
  - id: dev-container-integration
    name: Dev-container integration
    what: Run the agent inside a defined dev container / isolated runtime.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Dev container + reference template
        status: active
        evidence_url: https://code.claude.com/docs/en/devcontainer.md
        last_verified: '2026-06-24'
        notes: ''
      google:
        offering: Antigravity
        implementation: Sidecars (per-agent runtime containers)
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/sidecars.md
        last_verified: '2026-06-24'
        notes: Sidecars are Antigravity's per-agent container-runtime equivalent.
      openai:
        offering: Codex
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: Codex uses managed cloud container envs (see cloud-execution-environment); no local dev-container integration grounded — verify.
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
        implementation: OpenTelemetry + per-user attribution
        status: active
        evidence_url: https://code.claude.com/docs/en/monitoring-usage.md
        last_verified: '2026-06-24'
        notes: ''
      google:
        offering: Antigravity
        implementation: Observability (SDK)
        status: active
        evidence_url: https://antigravity.google/assets/docs/sdk/sdk-overview.md
        last_verified: '2026-06-24'
        notes: SDK-level observability; dedicated admin audit-log specifics unverified.
      openai:
        offering: Codex
        implementation: Run tracing / traces dashboard
        status: active
        evidence_url: https://developers.openai.com/api/docs/guides/agents/integrations-observability.md
        last_verified: '2026-06-24'
        notes: ''
  - id: code-review
    name: Automated code review
    what: The agent reviews diffs / PRs for issues before they land.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: Automated PR code review (+ /security-review)
        status: preview
        evidence_url: https://code.claude.com/docs/en/code-review.md
        last_verified: '2026-06-24'
        notes: In preview.
      google:
        offering: Antigravity
        implementation: Artifact review policy
        status: active
        evidence_url: https://antigravity.google/assets/docs/antigravity-2-0/artifact-review.md
        last_verified: '2026-06-24'
        notes: Reviews agent-produced artifacts before they land.
      openai:
        offering: Codex
        implementation: Automatic PR reviews (GitHub)
        status: active
        evidence_url: https://developers.openai.com/codex/integrations/github.md
        last_verified: '2026-06-24'
        notes: ''
  - id: cost-usage-tracking
    name: Cost & usage tracking
    what: Track and cap token spend / usage.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Cost tracking + spend dashboard / limits
        status: active
        evidence_url: https://code.claude.com/docs/en/admin-setup.md
        last_verified: '2026-06-24'
        notes: ''
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: No cost/usage-tracking node grounded for Antigravity — verify.
      openai:
        offering: Codex
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: No Codex-specific cost/usage-tracking node grounded (platform usage exists separately) — verify.
  - id: evals-testing
    name: Evals / testing harness
    what: Run evaluations / test suites against the agent's behavior.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: No agentic-coding eval-harness node grounded for Claude Code (code-review verification exists, which is distinct) — verify.
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: No evals/testing-harness node grounded for Antigravity — verify.
      openai:
        offering: Codex
        implementation: Evals (datasets, eval runs, testing criteria)
        status: active
        evidence_url: https://developers.openai.com/api/docs/guides/agent-evals.md
        last_verified: '2026-06-24'
        notes: OpenAI's evals harness, used with Codex/Agents SDK.
  - id: checkpoint-rewind
    name: Checkpoint / rewind
    what: Save points you can roll back to, and undo agent changes.
    tier: core
    providers:
      anthropic:
        offering: Claude Code
        implementation: /rewind + checkpointing (Esc-Esc)
        status: active
        evidence_url: https://code.claude.com/docs/en/checkpointing.md
        last_verified: '2026-06-25'
        notes: Auto-tracks file edits; /rewind or Esc-Esc restores conversation and/or code; checkpoints persist across sessions.
      google:
        offering: Antigravity
        implementation: /rewind (alias /undo)
        status: active
        evidence_url: https://antigravity.google/assets/docs/cli/cli-reference.md
        last_verified: '2026-06-25'
        notes: Rolls back the conversation thread to a previous message (CLI).
      openai:
        offering: Codex
        implementation: Undo support (features.undo config flag)
        status: preview
        evidence_url: https://developers.openai.com/codex/config-reference.md
        last_verified: '2026-06-25'
        notes: Opt-in (documented 'stable; off by default'); narrower than a full checkpoint/rewind UI. Not Codex Sites version-saving.
  - id: resume-session
    name: Resume / fork session
    what: Continue or branch a previous session.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Conversation fork / resume
        status: active
        evidence_url: https://code.claude.com/docs/en/agents.md
        last_verified: '2026-06-24'
        notes: ''
      google:
        offering: Antigravity
        implementation: /resume + /fork (alias /branch)
        status: active
        evidence_url: https://antigravity.google/assets/docs/cli/cli-conversations.md
        last_verified: '2026-06-25'
        notes: /resume loads a previous thread; /fork clones history into a new session; can also import desktop conversations.
      openai:
        offering: Codex
        implementation: Multi-device session handoff / codex-reply
        status: active
        evidence_url: https://developers.openai.com/codex/remote-connections.md
        last_verified: '2026-06-22'
        notes: ''
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
        implementation: Remote control (Claude mobile app, web)
        status: preview
        evidence_url: https://code.claude.com/docs/en/remote-control.md
        last_verified: '2026-06-24'
        notes: Steer/approve runs from the Claude mobile app; in preview.
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: No remote-control / mobile node grounded for Antigravity (a desktop/CLI tool) — verify.
      openai:
        offering: Codex
        implementation: Remote connections (mobile, multi-host)
        status: active
        evidence_url: https://developers.openai.com/codex/remote-connections.md
        last_verified: '2026-06-22'
        notes: ''
  - id: notifications
    name: Notifications
    what: Push notifications on run progress / completion.
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Mobile push notifications
        status: active
        evidence_url: https://code.claude.com/docs/en/remote-control.md
        last_verified: '2026-06-22'
        notes: ''
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: No notifications node grounded for Antigravity — verify.
      openai:
        offering: Codex
        implementation: Task-completion notifications
        status: active
        evidence_url: https://developers.openai.com/codex/remote-connections.md
        last_verified: '2026-06-22'
        notes: ''
  - id: chat-surface-integration
    name: Chat-surface integration
    what: Drive the agent from chat/issue tools (Slack, Linear, channels).
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Claude Code in Slack (+ channels)
        status: active
        evidence_url: https://code.claude.com/docs/en/slack.md
        last_verified: '2026-06-24'
        notes: ''
      google:
        offering: Antigravity
        implementation: unverified
        status: unverified
        evidence_url: ''
        last_verified: ''
        notes: No chat-surface (Slack/Linear/channels) integration grounded for Antigravity — verify.
      openai:
        offering: Codex
        implementation: Codex for Linear + app integrations
        status: active
        evidence_url: https://developers.openai.com/codex/integrations/linear.md
        last_verified: '2026-06-24'
        notes: ''
  - id: access-surfaces
    name: Access surfaces
    what: 'Where the agent can be used: terminal, IDE, web, cloud, mobile.'
    tier: advanced
    providers:
      anthropic:
        offering: Claude Code
        implementation: Terminal · IDE · web · Slack · mobile
        status: active
        evidence_url: https://code.claude.com/docs/en/claude-code-on-the-web.md
        last_verified: '2026-06-24'
        notes: Web surface + web↔terminal handoff in preview; terminal/IDE/Slack active.
      google:
        offering: Antigravity
        implementation: Agent-Manager IDE + CLI / terminal
        status: active
        evidence_url: https://antigravity.google/assets/docs/cli/cli-features.md
        last_verified: '2026-06-22'
        notes: ''
      openai:
        offering: Codex
        implementation: CLI · IDE · web/cloud · GitHub · mobile
        status: active
        evidence_url: https://developers.openai.com/codex/remote-connections.md
        last_verified: '2026-06-24'
        notes: ''
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
