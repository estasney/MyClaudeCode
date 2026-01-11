# Component Comparison

| Aspect | Slash Command | Skill | Agent | Hook |
|--------|---------------|-------|-------|------|
| **Invocation** | Manual: `/name` | Automatic: Claude decides | Automatic or Task tool | Event-triggered |
| **Storage** | `.claude/commands/name.md` | `.claude/skills/name/SKILL.md` | `.claude/agents/name.md` | `settings.json` or frontmatter |
| **Files** | Single file | Directory (SKILL.md + supporting) | Single file | Config file |
| **Discovery** | Autocomplete in terminal | Description-based matching | Description-based matching | Runs on specified events |
| **Use Case** | Explicit workflows | Domain knowledge, reusable capabilities | Isolated tasks, parallel work | Rules, automation, formatting |
| **Tool Restriction** | Via `allowed-tools` | Via `allowed-tools` | Via `allowed-tools` | N/A (runs as script) |
| **Context** | Runs in main session | Runs in main session | Spawns isolated context | Subprocess |

## Decision Guide

**Use Slash Command when:**
- You want explicit, terminal control (`/command`)
- Workflow should only run when explicitly triggered
- Single file is sufficient

**Use Skill when:**
- Claude should auto-apply based on task context
- Reusable knowledge across multiple sessions
- May need supporting files (scripts, templates, docs)

**Use Agent when:**
- Task is specialized and isolated
- Work can run in parallel via Task tool
- Need different tools than main session

**Use Hook when:**
- Enforce rules or gates on tool use
- Auto-format after writes
- Suggest skills based on user input
- Clean up or initialize sessions
