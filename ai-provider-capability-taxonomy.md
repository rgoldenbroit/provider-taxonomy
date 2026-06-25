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

Every Anthropic / Google / OpenAI cell below is grounded in official documentation. Most were
mined from `data/taxonomy.json` (this project's official-docs-grounded catalog); the cells the
catalog didn't cover were then verified directly against each vendor's own docs. Each
`evidence_url` is the documentation page that supports the cell, and `last_verified` is the date
it was checked. Status is mapped into this file's enum (`beta` → `preview`, `deprecated` → `sunset`).

**One cell remains `unverified`:** context compaction for Antigravity — no official Google doc
describes a compaction / auto-summarization feature for it (the CLI slash-command reference, the
SDK's lifecycle hooks, and the IDE/CLI hook events were all checked and none cover it). Left
honest rather than guessed — honesty over false completeness, per the engine's own pitch.

> Run `python scripts/validate_matrix.py` to re-check this block against the section-2 schema
> and the definition of done. It prints the validation summary `/goal` evaluates against.

```yaml
# matrix-data: agentic-coding   (the validator selects the YAML block containing this marker)
product_category: agentic-coding
capability_groups:

  - name: Configuration
    layer: platform
    capabilities:
      - id: project-instruction-file
        name: Project-scoped instruction file
        what: A repo file giving the agent standing instructions and context.
        tier: core
        providers:
          anthropic:
            offering: Claude Code
            implementation: "CLAUDE.md (+ imports, local/org scopes)"
            status: active
            evidence_url: "https://code.claude.com/docs/en/memory.md"
            last_verified: "2026-06-24"
            notes: ""
          google:
            offering: Antigravity
            implementation: "Rules / Global Rules (.md)"
            status: active
            evidence_url: "https://antigravity.google/assets/docs/antigravity-2-0/rules-workflows.md"
            last_verified: "2026-06-24"
            notes: ""
          openai:
            offering: Codex
            implementation: "AGENTS.md (+ overrides, global defaults)"
            status: active
            evidence_url: "https://developers.openai.com/codex/guides/agents-md.md"
            last_verified: "2026-06-24"
            notes: ""

  - name: Extensions
    layer: platform
    capabilities:
      - id: packaged-extensions
        name: Packaged reusable extensions
        what: A way to bundle reusable capabilities/instructions the agent can load.
        tier: core
        providers:
          anthropic:
            offering: Claude Code
            implementation: "Skills (+ plugins)"
            status: active
            evidence_url: "https://code.claude.com/docs/en/sub-agents.md"
            last_verified: "2026-06-22"
            notes: "Grounded via skill preloading; Skills + plugins both supported."
          google:
            offering: Antigravity
            implementation: "Plugins"
            status: active
            evidence_url: "https://antigravity.google/assets/docs/antigravity-2-0/plugins.md"
            last_verified: "2026-06-24"
            notes: ""
          openai:
            offering: Codex
            implementation: "Plugins / Skills"
            status: active
            evidence_url: "https://developers.openai.com/codex/plugins.md"
            last_verified: "2026-06-24"
            notes: ""
      - id: tool-server-protocol
        name: External tool/connector protocol (MCP)
        what: A standard way to connect external tools, data, and services.
        tier: core
        providers:
          anthropic:
            offering: Claude Code
            implementation: "MCP (Model Context Protocol)"
            status: active
            evidence_url: "https://code.claude.com/docs/en/mcp.md"
            last_verified: "2026-06-24"
            notes: ""
          google:
            offering: Antigravity
            implementation: "MCP integration (+ MCP Store)"
            status: active
            evidence_url: "https://antigravity.google/assets/docs/editor/ide-mcp.md"
            last_verified: "2026-06-24"
            notes: ""
          openai:
            offering: Codex
            implementation: "MCP (client + server modes)"
            status: active
            evidence_url: "https://developers.openai.com/codex/mcp.md"
            last_verified: "2026-06-24"
            notes: ""
      - id: lifecycle-hooks
        name: Lifecycle event hooks
        what: Run custom logic on agent events (e.g. before/after a tool call, on stop).
        tier: advanced
        providers:
          anthropic:
            offering: Claude Code
            implementation: "Hooks (PreToolUse, etc.)"
            status: active
            evidence_url: "https://code.claude.com/docs/en/permissions.md"
            last_verified: "2026-06-22"
            notes: "Grounded on the permissions page; agent lifecycle hooks are in preview."
          google:
            offering: Antigravity
            implementation: "Lifecycle hooks (Pre/PostToolUse, Stop)"
            status: active
            evidence_url: "https://antigravity.google/assets/docs/antigravity-2-0/hooks.md"
            last_verified: "2026-06-24"
            notes: ""
          openai:
            offering: Codex
            implementation: "Hooks (PreToolUse, SessionStart, Pre/PostCompact, Stop, …)"
            status: active
            evidence_url: "https://developers.openai.com/codex/hooks.md"
            last_verified: "2026-06-25"
            notes: "Full hooks framework: SessionStart, PreToolUse, PostToolUse, PermissionRequest, Pre/PostCompact, UserPromptSubmit, SubagentStop, Stop."

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
            implementation: "Subagents (+ Agent Teams)"
            status: active
            evidence_url: "https://code.claude.com/docs/en/sub-agents.md"
            last_verified: "2026-06-24"
            notes: "Agent Teams in preview."
          google:
            offering: Antigravity
            implementation: "Subagents (sync + async)"
            status: active
            evidence_url: "https://antigravity.google/assets/docs/cli/cli-subagents.md"
            last_verified: "2026-06-24"
            notes: ""
          openai:
            offering: Codex
            implementation: "Subagents / custom agents"
            status: active
            evidence_url: "https://developers.openai.com/codex/subagents.md"
            last_verified: "2026-06-24"
            notes: ""
      - id: goal-directed-iteration
        name: Goal-directed autonomous iteration
        what: Set a verifiable "done" condition; the agent loops on its own until met.
        tier: core
        providers:
          anthropic:
            offering: Claude Code
            implementation: "/goal, /loop, Auto Mode, Routines"
            status: active
            evidence_url: "https://code.claude.com/docs/en/routines.md"
            last_verified: "2026-06-24"
            notes: "Auto Mode + Routines in preview; /goal + /loop run in the CLI (this matrix was built with /goal)."
          google:
            offering: Antigravity
            implementation: "Always-Proceed / autonomy levels"
            status: active
            evidence_url: "https://antigravity.google/assets/docs/antigravity-2-0/permissions.md"
            last_verified: "2026-06-22"
            notes: "An autonomy control, not a verifiable-goal loop — partial fit."
          openai:
            offering: Codex
            implementation: "Full-access / workspace-write autonomy"
            status: active
            evidence_url: "https://developers.openai.com/codex/concepts/sandboxing.md"
            last_verified: "2026-06-24"
            notes: "An autonomy/approval mode, not a named goal-condition loop — partial fit."
      - id: parallel-workspaces
        name: Parallel isolated workspaces
        what: Work on multiple branches/copies in parallel without collisions.
        tier: advanced
        providers:
          anthropic:
            offering: Claude Code
            implementation: "Worktree isolation"
            status: active
            evidence_url: "https://code.claude.com/docs/en/glossary.md"
            last_verified: "2026-06-24"
            notes: ""
          google:
            offering: Antigravity
            implementation: "Worktree support"
            status: active
            evidence_url: "https://antigravity.google/assets/docs/antigravity-2-0/features.md"
            last_verified: "2026-06-22"
            notes: ""
          openai:
            offering: Codex
            implementation: "Git worktree isolation"
            status: active
            evidence_url: "https://developers.openai.com/codex/app/automations.md"
            last_verified: "2026-06-22"
            notes: ""

  - name: Context & memory
    layer: platform
    capabilities:
      - id: context-compaction
        name: Context compaction (manual + auto)
        what: Compress conversation/context to extend effective working memory.
        tier: core
        providers:
          anthropic:
            offering: Claude Code
            implementation: "/compact + automatic compaction"
            status: active
            evidence_url: "https://code.claude.com/docs/en/context-window.md"
            last_verified: "2026-06-25"
            notes: "Manual /compact at task breaks + auto-compaction as the context window fills."
          google:
            offering: Antigravity
            implementation: "unverified"
            status: unverified
            evidence_url: ""
            last_verified: ""
            notes: "No official Antigravity doc describes context compaction/auto-summarization (checked the CLI slash-command reference, SDK lifecycle hooks, and IDE/CLI hook events) — genuine gap."
          openai:
            offering: Codex
            implementation: "/compact + auto-compaction (model_auto_compact_token_limit)"
            status: active
            evidence_url: "https://developers.openai.com/codex/cli/slash-commands.md"
            last_verified: "2026-06-25"
            notes: "Manual /compact; automatic compaction via the model_auto_compact_token_limit config key."
      - id: prompt-caching
        name: Prompt / context caching
        what: Cache repeated context to cut latency and cost.
        tier: advanced
        providers:
          anthropic:
            offering: Claude Code
            implementation: "Automatic prompt caching"
            status: active
            evidence_url: "https://code.claude.com/docs/en/prompt-caching.md"
            last_verified: "2026-06-25"
            notes: "Claude Code manages server-side prefix caching automatically; no user config required."
          google:
            offering: Antigravity
            implementation: "Context caching (via the Gemini API)"
            status: active
            evidence_url: "https://ai.google.dev/gemini-api/docs/caching"
            last_verified: "2026-06-25"
            notes: "A Gemini model-API feature Antigravity inherits; no Antigravity-specific caching doc page."
          openai:
            offering: Codex
            implementation: "Automatic prompt caching (OpenAI API)"
            status: active
            evidence_url: "https://developers.openai.com/api/docs/guides/prompt-caching"
            last_verified: "2026-06-25"
            notes: "An OpenAI API platform feature (automatic prefix caching) that Codex inherits; not Codex-specific config."

  - name: Session control
    layer: user
    capabilities:
      - id: checkpoint-rewind
        name: Checkpoint / rewind
        what: Save points you can roll back to, and undo agent changes.
        tier: core
        providers:
          anthropic:
            offering: Claude Code
            implementation: "/rewind + checkpointing (Esc-Esc)"
            status: active
            evidence_url: "https://code.claude.com/docs/en/checkpointing.md"
            last_verified: "2026-06-25"
            notes: "Auto-tracks file edits; /rewind or Esc-Esc restores conversation and/or code; checkpoints persist across sessions."
          google:
            offering: Antigravity
            implementation: "/rewind (alias /undo)"
            status: active
            evidence_url: "https://antigravity.google/assets/docs/cli/cli-reference.md"
            last_verified: "2026-06-25"
            notes: "Rolls back the conversation thread to a previous message (CLI)."
          openai:
            offering: Codex
            implementation: "Undo support (features.undo config flag)"
            status: preview
            evidence_url: "https://developers.openai.com/codex/config-reference.md"
            last_verified: "2026-06-25"
            notes: "Opt-in (documented 'stable; off by default'); narrower than a full checkpoint/rewind UI. Not Codex Sites version-saving."
      - id: resume-session
        name: Resume / fork session
        what: Continue or branch a previous session.
        tier: advanced
        providers:
          anthropic:
            offering: Claude Code
            implementation: "Conversation fork / resume"
            status: active
            evidence_url: "https://code.claude.com/docs/en/agents.md"
            last_verified: "2026-06-24"
            notes: ""
          google:
            offering: Antigravity
            implementation: "/resume + /fork (alias /branch)"
            status: active
            evidence_url: "https://antigravity.google/assets/docs/cli/cli-conversations.md"
            last_verified: "2026-06-25"
            notes: "/resume loads a previous thread; /fork clones history into a new session; can also import desktop conversations."
          openai:
            offering: Codex
            implementation: "Multi-device session handoff / codex-reply"
            status: active
            evidence_url: "https://developers.openai.com/codex/remote-connections.md"
            last_verified: "2026-06-22"
            notes: ""

  - name: Security & governance
    layer: governance
    capabilities:
      - id: sandboxing
        name: Sandboxed execution
        what: Run agent actions in an isolated environment to limit blast radius.
        tier: core
        providers:
          anthropic:
            offering: Claude Code
            implementation: "OS + container sandbox"
            status: active
            evidence_url: "https://code.claude.com/docs/en/sandboxing.md"
            last_verified: "2026-06-22"
            notes: "Sandbox Runtime in beta."
          google:
            offering: Antigravity
            implementation: "Terminal / CLI sandbox"
            status: active
            evidence_url: "https://antigravity.google/assets/docs/cli/cli-sandbox.md"
            last_verified: "2026-06-24"
            notes: ""
          openai:
            offering: Codex
            implementation: "Seatbelt / Bubblewrap / Windows sandbox"
            status: active
            evidence_url: "https://developers.openai.com/codex/concepts/sandboxing.md"
            last_verified: "2026-06-24"
            notes: ""
      - id: permission-controls
        name: Tool permission controls
        what: Approve/deny what the agent is allowed to do.
        tier: core
        providers:
          anthropic:
            offering: Claude Code
            implementation: "Permission system (allow / ask / deny)"
            status: active
            evidence_url: "https://code.claude.com/docs/en/permissions.md"
            last_verified: "2026-06-24"
            notes: ""
          google:
            offering: Antigravity
            implementation: "Fine-grained permissions engine"
            status: active
            evidence_url: "https://antigravity.google/assets/docs/antigravity-2-0/permissions.md"
            last_verified: "2026-06-24"
            notes: ""
          openai:
            offering: Codex
            implementation: "Approval policy (+ permission profiles)"
            status: active
            evidence_url: "https://developers.openai.com/codex/agent-approvals-security.md"
            last_verified: "2026-06-24"
            notes: "Permission profiles in beta."
      - id: audit-logging
        name: Audit logging
        what: A record of agent actions for review/compliance.
        tier: advanced
        providers:
          anthropic:
            offering: Claude Code
            implementation: "OpenTelemetry + per-user attribution"
            status: active
            evidence_url: "https://code.claude.com/docs/en/monitoring-usage.md"
            last_verified: "2026-06-24"
            notes: ""
          google:
            offering: Antigravity
            implementation: "Observability (SDK)"
            status: active
            evidence_url: "https://antigravity.google/assets/docs/sdk/sdk-overview.md"
            last_verified: "2026-06-24"
            notes: "SDK-level observability; dedicated admin audit-log specifics unverified."
          openai:
            offering: Codex
            implementation: "Run tracing / traces dashboard"
            status: active
            evidence_url: "https://developers.openai.com/api/docs/guides/agents/integrations-observability.md"
            last_verified: "2026-06-24"
            notes: ""

  - name: Models & inference
    layer: platform
    capabilities:
      - id: model-selection
        name: Model selection
        what: Choose which underlying model the agent runs on.
        tier: core
        providers:
          anthropic:
            offering: Claude Code
            implementation: "/model (aliases + Sonnet / Opus / Haiku / Fable)"
            status: active
            evidence_url: "https://code.claude.com/docs/en/model-config.md"
            last_verified: "2026-06-25"
            notes: "Switch mid-session with /model, or set a default via the model setting in settings.json."
          google:
            offering: Antigravity
            implementation: "Reasoning-model selector (+ /model)"
            status: active
            evidence_url: "https://antigravity.google/assets/docs/antigravity-2-0/models.md"
            last_verified: "2026-06-25"
            notes: "Model-selector dropdown (Gemini + Claude + GPT-OSS options); also the /model CLI command."
          openai:
            offering: Codex
            implementation: "Per-agent model selection"
            status: active
            evidence_url: "https://developers.openai.com/codex/subagents.md"
            last_verified: "2026-06-22"
            notes: ""

  - name: Scheduling & background
    layer: platform
    capabilities:
      - id: scheduled-runs
        name: Scheduled / background runs
        what: Run the agent on a schedule or in the background without supervision.
        tier: advanced
        providers:
          anthropic:
            offering: Claude Code
            implementation: "Scheduled tasks / Routines (+ GitHub Actions)"
            status: active
            evidence_url: "https://code.claude.com/docs/en/scheduled-tasks.md"
            last_verified: "2026-06-24"
            notes: "Routines in preview."
          google:
            offering: Antigravity
            implementation: "Scheduled / background tasks"
            status: active
            evidence_url: "https://antigravity.google/assets/docs/antigravity-2-0/features.md"
            last_verified: "2026-06-24"
            notes: ""
          openai:
            offering: Codex
            implementation: "Automations (scheduled / triggered)"
            status: active
            evidence_url: "https://developers.openai.com/codex/app/automations.md"
            last_verified: "2026-06-24"
            notes: ""
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
