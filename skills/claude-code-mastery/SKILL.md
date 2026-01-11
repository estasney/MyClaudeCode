---
name: claude-code-mastery
description: Build Claude Code extensions—hooks, agents, skills, slash commands. Learn when to use each and how to implement them.
---

# Claude Code Mastery

Claude Code has four extension points. This skill teaches when to use each and how to build them.

## The Four Components

**Slash Commands** — User types `/name` → single `.md` file in `.claude/commands/`  
**Skills** — Claude auto-applies when relevant → directory with `SKILL.md` + supporting files  
**Agents** — Specialized workers spawned via Task tool → `.md` files in `.claude/agents/`  
**Hooks** — Event-driven automation → `settings.json` or component frontmatter  

See: [Component comparison](references/components.md)

## Frontmatter Structure

All markdown components start with YAML frontmatter. Critical fields:

- `name`: Kebab-case identifier
- `description`: Determines auto-discovery for skills/agents
- `allowed-tools`: Optional tool whitelist
- `model`: Leave as `inherit` unless overriding
- `hooks`: Optional component-scoped hooks

See: [Frontmatter reference](references/frontmatter.md)

## Hooks: Event-Driven Automation

Respond to lifecycle events with bash commands or LLM evaluation.

**Common events**: PreToolUse, PostToolUse, UserPromptSubmit, Stop, SessionStart

**Two execution modes**:
1. Bash command (exit code 0=allow, 2=block with feedback)
2. Prompt-based (LLM decides, Stop/SubagentStop only)

See: [Hook events](references/hooks.md) | [Hook examples](references/hook-examples.md)

## Agents: Specialized Workers

Focused AI workers for isolated tasks. Spawn via Task tool for parallel execution.

Structure: Frontmatter + instructions. Can restrict available tools.

See: [Agent examples](references/agent-examples.md)

## Skills: Auto-Invoked Domain Knowledge

Claude auto-applies when description matches task context.

Structure:
```
my-skill/
├── SKILL.md              # Required: frontmatter + instructions
├── references/           # Detailed docs (loaded as needed)
├── scripts/              # Reusable code (Python/Bash)
└── assets/               # Files used in output (templates, etc.)
```

Progressive disclosure: Keep SKILL.md focused on procedure, move detailed reference material to `references/` subdirectory.

See: [Skill patterns](references/skill-patterns.md)

## Slash Commands: User-Triggered Workflows

Single `.md` file. Manual invocation via `/command-name`. Supports `$ARGUMENTS` substitution.

Use for: Explicit, repeatable workflows.

See: [Slash command examples](references/slash-command-examples.md)

## When to Use Each

- Need explicit, repeatable workflow? → Slash Command
- Want Claude to auto-apply knowledge? → Skill
- Building isolated, specialized task? → Agent
- Enforcing rules or auto-formatting? → Hook

See: [Decision matrix](references/decision-matrix.md)

## Quick Start

[Implementation examples with working code](references/implementation-examples.md)
