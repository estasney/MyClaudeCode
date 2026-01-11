# Agent Examples

## What Agents Are

Specialized AI workers for isolated tasks. Spawned via Task tool from main session or explicitly. Useful for parallel work, deep investigation, or separating concerns.

## Agent Structure

Single `.md` file in `.claude/agents/`. Same frontmatter as skills.

```yaml
---
name: code-reviewer
description: Expert code review for quality, security, maintainability
allowed-tools: Read, Grep, Glob, Bash
model: inherit
---

# Code Review Agent

[Instructions and workflow...]
```

## Example 1: Code Review Agent

**`.claude/agents/code-reviewer.md`**:

```yaml
---
name: code-reviewer
description: Expert code review for quality, security, and maintainability. Analyzes code changes against best practices.
allowed-tools: Read, Grep, Glob, Bash
---

# Code Review Agent

You are a senior code reviewer. When invoked:

1. Run `git diff --name-only HEAD~1` to find changed files
2. For each changed file, read and evaluate:
   - Type safety (missing annotations, unsafe casts)
   - Error handling (bare except, missing guards)
   - Security (SQL injection, XSS, secrets exposure)
   - Performance (N+1 queries, missing indexes)
   - Testing (coverage, edge cases)

3. Output structured review:

```
FILE: src/app.py
Type Safety: 4/5 - Missing return type on handler()
Error Handling: 3/5 - Catch blocks too broad
Security: 5/5 - Input validation solid
Performance: 4/5 - Consider batch ops in line 42
```
```

**Invoke from slash command**:

```markdown
---
name: review-code
description: Run expert code review on recent changes
allowed-tools: Task
---

# Review Code Changes

Spawn code reviewer agent to analyze recent changes.
```

## Example 2: Documentation Sync Agent

**`.claude/agents/docs-sync.md`**:

```yaml
---
name: docs-sync
description: Keep project documentation in sync with code changes
allowed-tools: Read, Write, Grep, Bash, Glob
---

# Documentation Sync Agent

Sync docs to match recent code changes.

## Workflow

1. Check recent commits: `git log --oneline -n 10`
2. Identify documentation files (README.md, docs/, API docs)
3. Find code changes needing doc updates:
   - New public APIs
   - Behavior changes
   - Config changes
   - Breaking changes

4. Update docs with:
   - New function signatures
   - Usage examples
   - Deprecation notices
   - Migration guides

5. Update `docs/CHANGELOG.md` with summary
```

## Spawning Agents in Parallel

From slash command or skill, use Task tool to spawn multiple agents:

```markdown
## Research in Parallel

Spawn three research agents simultaneously:

**Web Research Agent** (searches documentation, tutorials)  
**Codebase Agent** (scans repository for examples)  
**Analysis Agent** (synthesizes findings)

Wait for completion, then consolidate into `docs/research.md`.
```

Claude handles Task tool invocation in markdown.

## Key Points

- **Isolation**: Agents run in separate context, don't clutter main session
- **Parallel**: Via Task tool, agents work simultaneously
- **Tool restriction**: Use `allowed-tools` to limit agent capabilities
- **Auto-discovery**: Description field for auto-triggering (like skills)
- **Explicit spawn**: Or invoke directly via Task tool for controlled invocation
