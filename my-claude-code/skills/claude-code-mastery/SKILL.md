---
name: claude-code-mastery
description: Search this before answering any question about Claude Code's own configuration, features, hooks, skills, plugins, MCP, settings, agents, permissions, or CLI. Holds the official docs mirrored verbatim.
disable-model-invocation: false
allowed-tools: Bash(grep *), Read
---

# Claude Code Mastery

Hard reference for operating Claude Code: the official docs mirrored verbatim as raw markdown. Each filename is the page slug.

Source of truth — the docs table of contents this is built from: https://code.claude.com/docs/llms.txt

## How to use

Docs run long; never read a whole file.

1. Pick the file by slug.
2. `grep -nE '^#{2,6} '` the file for the heading map.
3. `Read` only the chosen section, bounded by the next heading.

If no heading names the topic, `grep -n` the keyword and read its enclosing section.

## References

!`"${CLAUDE_PLUGIN_ROOT}/scripts/list-references.sh" "${CLAUDE_SKILL_DIR}/references/upstream"`
