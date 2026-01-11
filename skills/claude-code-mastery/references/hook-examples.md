# Hook Examples

## Example 1: Security Gate (PreToolUse + Bash)

**`.claude/settings.json`**:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "./scripts/security-check.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**`scripts/security-check.sh`**:

```bash
#!/bin/bash

read -r hook_input
command=$(echo "$hook_input" | jq -r '.tool_input.command // empty')

# Block dangerous patterns
if [[ "$command" == *"rm -rf"* ]] || \
   [[ "$command" == *"dd if="* ]] || \
   [[ "$command" == *":(){:|:&}:"* ]]; then
  echo "Blocked: dangerous command pattern" >&2
  exit 2
fi

exit 0
```

## Example 2: Auto-Format Code (PostToolUse)

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "cd ${CLAUDE_PROJECT_DIR} && black . && ruff check --fix .",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

Runs formatter automatically after every code write.

## Example 3: Skill Suggestion (UserPromptSubmit + Node.js)

**`.claude/settings.json`**:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node ${CLAUDE_PROJECT_DIR}/scripts/suggest-skills.js",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**`scripts/suggest-skills.js`**:

```javascript
const fs = require('fs');
const path = require('path');

let input = '';
process.stdin.on('data', chunk => input += chunk);

process.stdin.on('end', () => {
  const hook = JSON.parse(input);
  const projectDir = hook.session_data.project_path;
  const skillsDir = path.join(projectDir, '.claude', 'skills');
  
  if (!fs.existsSync(skillsDir)) {
    process.exit(0);
  }

  const userPrompt = hook.user_input.toLowerCase();
  const skills = fs.readdirSync(skillsDir)
    .filter(f => fs.statSync(path.join(skillsDir, f)).isDirectory());

  const suggestions = skills
    .map(skill => {
      const skillMd = path.join(skillsDir, skill, 'SKILL.md');
      const content = fs.readFileSync(skillMd, 'utf8');
      const match = content.match(/description:\s*([^\n]+)/);
      const description = match ? match[1].toLowerCase() : '';
      
      const score = description.split(' ')
        .filter(word => userPrompt.includes(word))
        .length;
      
      return { skill, score };
    })
    .filter(s => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 3)
    .map(s => s.skill);

  if (suggestions.length > 0) {
    console.log(JSON.stringify({
      suggested_skills: suggestions,
      confidence: 'high'
    }));
  }

  process.exit(0);
});
```

## Example 4: Component-Scoped Hook in Skill

**`.claude/skills/testing-patterns/SKILL.md`**:

```yaml
---
name: testing-patterns
description: pytest fixtures, parametrization, mocking, test organization
hooks:
  PostToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "cd ${CLAUDE_PROJECT_DIR} && pytest tests/ --tb=short -q"
          timeout: 120
---

# Testing Patterns

Use this skill for pytest-related tasks.

[Rest of skill content...]
```

This hook runs tests automatically after code changes, but only when the skill is active.

## Example 5: Intelligent Stop (Prompt-Based)

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Should Claude stop now? Evaluate: 1) Are all user tasks complete? 2) Are there pending operations? 3) Is the context healthy?"
          }
        ]
      }
    ]
  }
}
```

LLM decides whether to continue or stop, not a hardcoded check.

## Testing Your Hooks

1. Add hook to `settings.json`
2. Run with debug: `claude --debug`
3. Trigger the event (e.g., type a command for PreToolUse)
4. Check output: Hook logs show input, command execution, exit code
5. If exit code 2 (block), Claude sees the decision message
