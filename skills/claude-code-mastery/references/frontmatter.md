# Frontmatter Reference

All Claude Code markdown components use YAML frontmatter.

## Basic Structure

```yaml
---
name: kebab-case-name
description: What this does and when Claude should use it
---
```

## All Fields

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `name` | Yes | String | Kebab-case identifier. Used for invocation (`/name` for commands) |
| `description` | Yes | String | Determines auto-discovery for skills/agents. Be specific about purpose and trigger conditions |
| `argument-hint` | No | String | Slash commands only. Shows expected arguments in autocomplete. Format: `arg1 [arg2] \| subcommand [arg]` |
| `allowed-tools` | No | CSV | Whitelist available tools. Valid: Task, Bash, Read, Write, Edit, Grep, Glob, WebSearch, WebFetch. If omitted, all available |
| `model` | No | String | Model to use (e.g., `claude-opus-4-20250805`). Default: `inherit` (use session model) |
| `hooks` | No | YAML object | Component-scoped hooks. See hooks.md for schema |
| `license` | No | String | License identifier (informational only) |

## argument-hint: Slash Command Syntax Help

The `argument-hint` field shows users what arguments a slash command expects. Displayed in terminal autocomplete.

### Format

```yaml
argument-hint: add [tagId] | remove [tagId] | list
```

Use:
- `arg` — Required argument
- `[arg]` — Optional argument
- `|` — Separates alternatives/subcommands
- Pipe syntax for multiple patterns

### Examples

**Single argument**:
```yaml
---
name: research
argument-hint: "[topic]"
---
```
Shows: `/research [topic]`

**Required + optional**:
```yaml
---
name: debug
argument-hint: "[error-message] [context]"
---
```

**Subcommands**:
```yaml
---
name: tag-manager
argument-hint: add [tagId] | remove [tagId] | list
---
```
Shows three options in autocomplete.

**Multiple patterns**:
```yaml
---
name: deploy
argument-hint: prod [version] | staging [version] | rollback [version]
---
```

## Examples

### Slash Command with argument-hint

```yaml
---
name: research
description: Investigate topics using web search and documentation
argument-hint: "[topic]"
allowed-tools: Task, WebSearch, WebFetch, Grep, Glob, Read, Write
---

# Research: $ARGUMENTS

Topic to investigate: $ARGUMENTS

## Workflow

1. Search web for "$ARGUMENTS"
2. Review official documentation
3. Compile findings
```

Autocomplete shows: `/research [topic]`

### Complex Command with Subcommands

```yaml
---
name: db-tool
description: Database management commands—migrate, seed, reset, backup
argument-hint: migrate [version] | seed [dataset] | reset | backup [name]
allowed-tools: Bash, Read, Write
---

# Database Tool: $ARGUMENTS

Operation: $ARGUMENTS

[Handles different operations...]
```

Autocomplete shows all subcommand options.

### Agent Frontmatter (no argument-hint)

```yaml
---
name: code-reviewer
description: Expert code review for quality, security, and maintainability
allowed-tools: Read, Grep, Glob, Bash
---
```

Agents don't use `argument-hint`—skills don't either.

## Parameter Hints

Available in slash commands, agents, and hooks:

| Parameter | Available In | Type | Notes |
|-----------|--------------|------|-------|
| `$ARGUMENTS` | Slash commands, agents | String | Everything after command name. Use in command body and agent instructions |
| `${CLAUDE_PROJECT_DIR}` | Hooks, bash scripts | Path | Project root. Use in hook commands and shell scripts |
| `${CLAUDE_PLUGIN_ROOT}` | Hooks, bash scripts | Path | Plugin directory if loaded via plugin |
| `${CLAUDE_SESSION_ID}` | Hooks, bash scripts | String | Session identifier |

### $ARGUMENTS in Slash Commands

Substitute user input into command content:

```yaml
---
name: research
description: Investigate topics
argument-hint: "[topic]"
---

# Research: $ARGUMENTS

Topic: $ARGUMENTS
```

Usage: `/research machine learning`
→ $ARGUMENTS = "machine learning"

### $ARGUMENTS in Agents

```yaml
---
name: summarizer
description: Summarize provided content
---

# Summarize: $ARGUMENTS

Content:
$ARGUMENTS
```

### Environment Variables in Hooks & Scripts

```bash
#!/bin/bash
PROJECT_DIR="$CLAUDE_PROJECT_DIR"
SESSION_ID="$CLAUDE_SESSION_ID"

cd "$PROJECT_DIR" || exit 1
```

### Stdin JSON in Hooks

```bash
read -r hook_input
tool=$(echo "$hook_input" | jq -r '.tool_name')
command=$(echo "$hook_input" | jq -r '.tool_input.command // empty')
```

See hooks.md for full schema.

## Critical: Description Field

For **skills** and **agents**, the `description` field triggers auto-discovery.

**Good**:
```yaml
description: SQLAlchemy ORM patterns for async queries, session management, custom types in Python 3.12+
```

**Poor**:
```yaml
description: A useful database skill
```

## Hook Field Reference

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `matcher` | String | Yes | Pipe-separated tool names: `Bash\|Write\|Edit` |
| `type` | String | Yes | `command` or `prompt` |
| `command` | String | If type=command | Script to execute. Supports ${CLAUDE_PROJECT_DIR} |
| `prompt` | String | If type=prompt | Question for LLM (Stop/SubagentStop only) |
| `timeout` | Number | No | Seconds before timeout (default: 30) |
| `once` | Boolean | No | Run only once per session (skills/commands only) |
