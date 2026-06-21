# Agentic Coding — Feature Taxonomy

> Reference taxonomy for one product function, broken down
> **function → product → category → feature → sub-feature**, with each provider's
> counterpart aligned. Built to be read by an agent (e.g. Claude Code) to understand the
> intended *shape* of an app's feature set — not just the names.
>
> **Status legend:** `GA` shipped · `Preview` limited/early access · `Beta` public but unstable ·
> `none found` = checked, no counterpart exists (an empty cell never means "we didn't look").
> Data here is **illustrative** — it captures structure, not a guarantee of current availability.

- **Function:** Agentic Coding
- **Providers compared:** Anthropic · Google · OpenAI
- **Reading order:** scan categories → features; expand sub-features where a feature has internal structure.

---

## Level 1–2 · The function and its products

| Provider | Product | Status | What it is | Sibling surfaces |
|---|---|---|---|---|
| Anthropic | **Claude Code** | GA | Terminal-native agentic coding agent that fans out across every surface. | CLI · IDE · web · mobile · CI |
| Google | **Antigravity** | Preview | Agent-first IDE built around managed, supervised coding agents. | Gemini CLI · Jules |
| OpenAI | **Codex** | GA | Cloud and local coding agent with parallel task execution. | Codex CLI · Codex cloud |

---

## Level 3–5 · The breakdown

### Category: Surfaces
*Where the coding agent runs and how you reach it.*

| Feature | Anthropic (Claude Code) | Google (Antigravity) | OpenAI (Codex) |
|---|---|---|---|
| Terminal / CLI | Claude Code CLI `GA` | Gemini CLI `GA` | Codex CLI `GA` |
| IDE extension | VS Code & JetBrains `GA` | Antigravity IDE `Preview` | Codex IDE extension `GA` |
| Web / cloud | Claude Code on the web `Beta` | Jules async agent `Preview` | Codex on the web `GA` |
| Mobile | Claude iOS app `Beta` | *none found* | Codex in ChatGPT app `Preview` |
| CI / GitHub | GitHub Actions `Beta` | Jules for GitHub `Preview` | Codex cloud tasks `GA` |

### Category: Agent Management
*Defining, specializing, and orchestrating agents.*

| Feature | Anthropic (Claude Code) | Google (Antigravity) | OpenAI (Codex) |
|---|---|---|---|
| **Sub agents** — task-scoped agents with their own context window and tools | Subagents `GA` | Custom agents `Preview` | *none found* |
| &nbsp;&nbsp;└ Definition files | `.claude/agents/*.md` `GA` | Agent config `Preview` | *none found* |
| &nbsp;&nbsp;└ Tool scoping | Per-agent tools `GA` | Scoped tools `Preview` | *none found* |
| &nbsp;&nbsp;└ Model per agent | Model override `GA` | Model per agent `Preview` | *none found* |
| **Agent teams** — several agents coordinating on one task | Orchestrator–worker `Beta` | Agent groups `Preview` | *none found* |
| **Custom personas** — persistent instructions & style per agent | Output styles `GA` | Agent profiles `Preview` | AGENTS.md `GA` |
| **Skills** — reusable, model-invoked capability bundles | Agent Skills `Beta` | *none found* | *none found* |

---

## Machine-readable source

The same taxonomy as structured data. Treat this block as the source of truth; the tables above
are a rendering of it. Each provider slot is either `{ "offering": "...", "status": "GA|Preview|Beta" }`
or `null` (none found).

```json
{
  "function": "Agentic Coding",
  "providers": [
    { "id": "anthropic", "name": "Anthropic", "product": "Claude Code", "status": "GA" },
    { "id": "google",    "name": "Google",    "product": "Antigravity", "status": "Preview" },
    { "id": "openai",    "name": "OpenAI",    "product": "Codex",       "status": "GA" }
  ],
  "categories": [
    {
      "name": "Surfaces",
      "definition": "Where the coding agent runs and how you reach it.",
      "features": [
        {
          "name": "Terminal / CLI",
          "anthropic": { "offering": "Claude Code CLI", "status": "GA" },
          "google":    { "offering": "Gemini CLI", "status": "GA" },
          "openai":    { "offering": "Codex CLI", "status": "GA" }
        },
        {
          "name": "IDE extension",
          "anthropic": { "offering": "VS Code & JetBrains", "status": "GA" },
          "google":    { "offering": "Antigravity IDE", "status": "Preview" },
          "openai":    { "offering": "Codex IDE extension", "status": "GA" }
        },
        {
          "name": "Web / cloud",
          "anthropic": { "offering": "Claude Code on the web", "status": "Beta" },
          "google":    { "offering": "Jules async agent", "status": "Preview" },
          "openai":    { "offering": "Codex on the web", "status": "GA" }
        },
        {
          "name": "Mobile",
          "anthropic": { "offering": "Claude iOS app", "status": "Beta" },
          "google":    null,
          "openai":    { "offering": "Codex in ChatGPT app", "status": "Preview" }
        },
        {
          "name": "CI / GitHub",
          "anthropic": { "offering": "GitHub Actions", "status": "Beta" },
          "google":    { "offering": "Jules for GitHub", "status": "Preview" },
          "openai":    { "offering": "Codex cloud tasks", "status": "GA" }
        }
      ]
    },
    {
      "name": "Agent Management",
      "definition": "Defining, specializing, and orchestrating agents.",
      "features": [
        {
          "name": "Sub agents",
          "definition": "Task-scoped agents with their own context window and tools.",
          "anthropic": { "offering": "Subagents", "status": "GA" },
          "google":    { "offering": "Custom agents", "status": "Preview" },
          "openai":    null,
          "subfeatures": [
            {
              "name": "Definition files",
              "anthropic": { "offering": ".claude/agents/*.md", "status": "GA" },
              "google":    { "offering": "Agent config", "status": "Preview" },
              "openai":    null
            },
            {
              "name": "Tool scoping",
              "anthropic": { "offering": "Per-agent tools", "status": "GA" },
              "google":    { "offering": "Scoped tools", "status": "Preview" },
              "openai":    null
            },
            {
              "name": "Model per agent",
              "anthropic": { "offering": "Model override", "status": "GA" },
              "google":    { "offering": "Model per agent", "status": "Preview" },
              "openai":    null
            }
          ]
        },
        {
          "name": "Agent teams",
          "definition": "Several agents coordinating on one task.",
          "anthropic": { "offering": "Orchestrator–worker", "status": "Beta" },
          "google":    { "offering": "Agent groups", "status": "Preview" },
          "openai":    null
        },
        {
          "name": "Custom personas",
          "definition": "Persistent instructions & style per agent.",
          "anthropic": { "offering": "Output styles", "status": "GA" },
          "google":    { "offering": "Agent profiles", "status": "Preview" },
          "openai":    { "offering": "AGENTS.md", "status": "GA" }
        },
        {
          "name": "Skills",
          "definition": "Reusable, model-invoked capability bundles.",
          "anthropic": { "offering": "Agent Skills", "status": "Beta" },
          "google":    null,
          "openai":    null
        }
      ]
    }
  ]
}
```

---

## How to use this as a reference

- **Treat the JSON block as canonical.** The Markdown tables are a human rendering of it; if they
  disagree, the JSON wins.
- **Map categories → app IA / nav, features → screens or settings, sub-features → controls.** The
  nesting depth is the intended information architecture.
- **`null` is a signal, not a blank.** It marks a deliberate gap — a place a competitor *could*
  build but hasn't — useful for prioritization, not something to silently skip.
- **Extend by adding categories** (e.g. Session Management, Memory Management, Context Management,
  Tooling & Extensibility / MCP, Permissions & Safety, Workflow & Automation) following the same
  per-feature, three-provider shape.
