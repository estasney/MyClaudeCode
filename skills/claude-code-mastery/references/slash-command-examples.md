# Slash Command Examples

## What Slash Commands Are

Single `.md` files in `.claude/commands/`. User invokes with `/name`. Supports `$ARGUMENTS` substitution.

## Basic Structure

```yaml
---
name: command-name
description: What this does
allowed-tools: Task, WebSearch, Read, Write    # Optional
---

# Command Title

Instructions and workflow. Use `$ARGUMENTS` to reference user input.
```

## Example 1: Multi-Source Research

**`.claude/commands/research.md`**:

```yaml
---
name: research
description: Conduct thorough research on a topic using web search, documentation, and codebase analysis in parallel
allowed-tools: Task, WebSearch, WebFetch, Grep, Glob, Read, Write
---

# Research: $ARGUMENTS

## Problem

$ARGUMENTS

## Research Strategy

Spawn three agents in parallel via Task tool:

1. **Web Research Agent** — Search documentation, tutorials, best practices. Find current recommendations.

2. **Codebase Agent** — Scan project for existing implementations. Extract relevant patterns and examples.

3. **Analysis Agent** — Synthesize findings. Identify trade-offs, gaps, and recommendations.

## Output

After agents complete, compile `docs/research-$TIMESTAMP.md` with:
- Problem statement
- Key findings (per source)
- Recommended approach
- Trade-offs and considerations
- Open questions
```

**Usage**: `/research how to optimize database queries`

## Example 2: Infrastructure Audit

**`.claude/commands/infra-audit.md`**:

```yaml
---
name: infra-audit
description: Comprehensive infrastructure review—security, performance, cost, reliability
allowed-tools: Task, Bash, Grep, Glob, Read
---

# Infrastructure Audit

Perform complete infrastructure audit via parallel agents:

**Security Check** — Review IAM, VPC rules, secrets. Output: `reports/security.md`

**Performance Audit** — Analyze queries, caching, CDN. Output: `reports/performance.md`

**Cost Optimization** — Identify unused resources, reserved instance opportunities. Output: `reports/cost.md`

**Reliability Review** — Test backups, failover, monitoring. Output: `reports/reliability.md`

Consolidate into `reports/infra-audit-summary.md`.
```

## Example 3: Quick Debug

**`.claude/commands/debug.md`**:

```yaml
---
name: debug
description: Debug a specific error or issue quickly
allowed-tools: Bash, Read, Grep, Glob
---

# Debug: $ARGUMENTS

## Error/Issue

$ARGUMENTS

## Approach

1. Search codebase for related code: `grep -r "error_pattern" .`
2. Read relevant files to understand context
3. Identify root cause
4. Suggest fix with code example

Output findings to stdout.
```

## Key Patterns

### $ARGUMENTS Substitution

Everything after command name becomes `$ARGUMENTS`:

```bash
/research machine learning frameworks
# $ARGUMENTS = "machine learning frameworks"

/debug TypeError: cannot read property 'name' of undefined
# $ARGUMENTS = "TypeError: cannot read property 'name' of undefined"
```

### Spawn Parallel Agents

Use Task tool syntax in markdown:

```markdown
Spawn three agents:
- Agent 1 description
- Agent 2 description  
- Agent 3 description

Wait for all to complete, then consolidate.
```

Claude detects Task tool invocation.

### Restrict Tools

Use `allowed-tools` to limit what command can do:

```yaml
---
name: safe-cleanup
description: Clean up old files
allowed-tools: Read, Bash, Glob  # No Write tool
---
```

## Auto-Invocation

Slash commands don't auto-trigger, but Claude may suggest them:

```
User: "Can you research this?"
Claude might suggest: `/research` if a research command exists
```

## Testing Commands

```bash
# List available commands
/help

# Run specific command
/research your-topic

# Debug command execution
claude --debug
# Then run /command and check logs
```
