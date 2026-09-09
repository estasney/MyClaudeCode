---
name: claude-memory
description: Install, uninstall, or check the status of the SessionStart hook that injects the top-ranked memories for the current project. Use when the user asks to set up, remove, or inspect the memory hook.
argument-hint: [install | uninstall | status]
allowed-tools: Bash, Write
disable-model-invocation: true
---

# Memory hook

Plugins cannot install hooks that the user can toggle on their own, so this skill installs the hook into the user's `settings.json` and removes it on request.

The CLI lives in this skill directory as a uv project: `${CLAUDE_PLUGIN_ROOT}/skills/claude-memory`.
Data directory: `${CLAUDE_PLUGIN_DATA}`

Claude Code exports `CLAUDE_PLUGIN_DATA` only to plugin-declared hooks, and `${CLAUDE_PLUGIN_ROOT}` changes on every plugin update, so the CLI is installed into a virtual environment under the data directory and the wrapper script below carries the data directory as a literal path.

## Requested action

`$ARGUMENTS`

Match the request to one section below and follow only that section:

- **install**: see [Install](#install)
- **uninstall**: see [Uninstall](#uninstall)
- **status**: see [Status](#status)
- **empty or unclear**: run [Status](#status) and ask which action the user wants

## Install

1. `uv` must be on the PATH.
2. Create the virtual environment in the data directory so it outlives plugin updates:
   `uv venv "${CLAUDE_PLUGIN_DATA}/venv"`
3. Install the CLI into it:
   `uv pip install --python "${CLAUDE_PLUGIN_DATA}/venv/bin/python" "${CLAUDE_PLUGIN_ROOT}/skills/claude-memory"`
4. Write `${CLAUDE_PLUGIN_DATA}/memory-session-start.sh` from [Scripts](#scripts) with the placeholder replaced by the literal path, overwriting any existing copy, and `chmod +x` it.
5. Add the [hook entry](#hook-entry) to `SessionStart` under `hooks` in `~/.claude/settings.json`. Skip it if already present. Merge into the existing hook array; do not replace it.
6. Tell the user the hook takes effect on the next session. The CLI creates the database on first run.

## Uninstall

1. Remove only the `SessionStart` entry in `~/.claude/settings.json` whose `command` is `${CLAUDE_PLUGIN_DATA}/memory-session-start.sh`. Leave every other hook untouched.
2. Leave the virtual environment, the wrapper script, and the database in place. Uninstalling the plugin deletes the data directory.

## Status

Report installed when `~/.claude/settings.json` has a `SessionStart` entry referencing `${CLAUDE_PLUGIN_DATA}/memory-session-start.sh` and `${CLAUDE_PLUGIN_DATA}/venv/bin/claude-memory` exists, and not installed otherwise. Also report whether `${CLAUDE_PLUGIN_DATA}/memory.db` exists.

## Hook entry

Exec form, so the literal path is passed as one argument with no shell quoting:

```json
{
  "hooks": [
    {
      "type": "command",
      "command": "${CLAUDE_PLUGIN_DATA}/memory-session-start.sh",
      "args": []
    }
  ]
}
```

## Scripts

`${CLAUDE_PLUGIN_DATA}/memory-session-start.sh`, with `__DATA_DIR__` replaced by the literal value of `${CLAUDE_PLUGIN_DATA}`:

```bash
#!/usr/bin/env bash
# SessionStart hook: plain stdout reaches Claude as context on this event.
set -eu
[ -n "${CLAUDE_PROJECT_DIR:-}" ] || exit 0
export CLAUDE_PLUGIN_DATA="__DATA_DIR__"
"__DATA_DIR__/venv/bin/claude-memory" session-start
```
