# Decision Matrix

## Quick Decision Tree

**Do you want Claude to auto-apply based on task context?**
→ Yes: Skill
→ No: Go to next question

**Should user explicitly trigger from terminal?**
→ Yes: Slash Command
→ No: Go to next question

**Is this isolated work, possibly parallel?**
→ Yes: Agent
→ No: Hook

**Need to enforce rules or auto-format?**
→ Yes: Hook
→ No: Reconsider your use case

## Detailed Decision Table

| Scenario | Component | Why |
|----------|-----------|-----|
| Auto-apply reusable knowledge when context matches | Skill | Description-based auto-discovery |
| User types `/research something` | Slash Command | Explicit invocation, single file |
| Code review after every change | Agent + Hook | Hook triggers, agent runs isolated review |
| Suggest skills based on user input | Hook (UserPromptSubmit) | Analyze prompt, output skill recommendations |
| Auto-format Python after writes | Hook (PostToolUse) | Runs script automatically |
| Security gate for bash commands | Hook (PreToolUse) | Check before execution |
| Parallel research from multiple sources | Slash Command spawning agents | Command orchestrates parallel work |
| Domain-specific patterns (testing, ORM, etc.) | Skill | Claude applies when relevant |
| One-time infrastructure audit | Slash Command | `/infra-audit` |
| Session startup configuration | Hook (SessionStart) | Initialize environment |

## Common Combinations

**Skill + Hook**:
- Skill provides knowledge
- Hook auto-formats or validates when skill is active

**Slash Command + Agents**:
- Command as entry point
- Agents handle parallel work

**Hook (UserPromptSubmit) + Skills**:
- Hook analyzes prompt
- Suggests relevant skills

## Anti-Patterns

**Don't use:**
- Skill when you need explicit control → Use slash command
- Hook for complex logic → Use agent with skill
- Agent for simple reusable knowledge → Use skill
- Slash command when auto-apply needed → Use skill
