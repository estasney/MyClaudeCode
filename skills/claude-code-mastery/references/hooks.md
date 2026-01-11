# Hooks: Events and Execution

## All Hook Events

| Event | Trigger | Use Case |
|-------|---------|----------|
| `PreToolUse` | Before any tool executes | Security gates, permission checks |
| `PostToolUse` | After tool completes | Auto-format, linting, validation |
| `PermissionRequest` | Tool requests permission | Gate sensitive operations |
| `Notification` | System notifications | Custom logging |
| `UserPromptSubmit` | Before Claude processes input | Skill suggestions, prompt analysis |
| `Stop` | Before session ends | Context cleanup, resource release |
| `SubagentStop` | Before subagent terminates | Subagent-specific cleanup |
| `PreCompact` | Before context compaction | Save state before compression |
| `SessionStart` | Session initialization | Load env, setup state |
| `SessionEnd` | Session shutdown | Final cleanup, logging |

## Bash Command Hooks

Hooks with `type: command` execute a script and receive JSON on stdin.

### Input Schema

```json
{
  "tool_name": "Bash|Write|Edit|Read|Grep|Glob|Task|WebSearch|WebFetch",
  "tool_input": {
    "command": "string",
    "file_path": "string",
    "search_query": "string"
  },
  "session_data": {
    "project_path": "/path/to/project",
    "session_id": "unique-id",
    "claude_version": "claude-sonnet-4-20250514"
  }
}
```

### Exit Codes

| Code | Behavior |
|------|----------|
| `0` | Allow operation to proceed |
| `2` | Block operation, show decision to Claude |
| Other (1, 3+) | Error, block operation |

### Environment Variables

Available to hook scripts:

```
$CLAUDE_PROJECT_DIR    # Project root
$CLAUDE_PLUGIN_ROOT    # Plugin directory (if via plugin)
$CLAUDE_SESSION_ID     # Session identifier
```

### Example: Parse Hook Input

```bash
#!/bin/bash
read -r hook_input
tool_name=$(echo "$hook_input" | jq -r '.tool_name')
command=$(echo "$hook_input" | jq -r '.tool_input.command // empty')

if [[ "$command" == *"dangerous_pattern"* ]]; then
  echo "Blocked: dangerous operation" >&2
  exit 2
fi

exit 0
```

## Prompt-Based Hooks

Only supported for `Stop` and `SubagentStop` events. LLM evaluates context.

### Schema

```json
{
  "Stop": [
    {
      "hooks": [
        {
          "type": "prompt",
          "prompt": "Should Claude stop? Check: all tasks complete, no pending operations."
        }
      ]
    }
  ]
}
```

### LLM Response

```json
{
  "should_stop": true,
  "reason": "All tasks completed successfully"
}
```

Uses fast model (Haiku) for evaluation.

## Hook Configuration in settings.json

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "./scripts/security.sh",
            "timeout": 30,
            "once": false
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "prettier --write .",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

### Field Reference

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `matcher` | String | Yes | Pipe-separated tool names to match |
| `type` | String | Yes | `command` or `prompt` |
| `command` | String | If type=command | Script to execute |
| `prompt` | String | If type=prompt | Question for LLM |
| `timeout` | Number | No | Seconds before timeout (default: 30) |
| `once` | Boolean | No | Run only once per session (skills/commands only) |

## Debugging Hooks

Run Claude Code with debug flag to see hook execution:

```bash
claude --debug
```

Logs show:
- Hook triggering
- Input/output
- Exit codes
- Execution time
