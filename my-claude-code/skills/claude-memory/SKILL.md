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

User-level hooks do not receive `CLAUDE_PLUGIN_DATA`, and `${CLAUDE_PLUGIN_ROOT}` changes on every plugin update, so the wrapper script below must contain literal paths resolved at install time.

## Requested action

`$ARGUMENTS`

Match the request to one section below and follow only that section:

- **install**: see [Install](#install)
- **uninstall**: see [Uninstall](#uninstall)
- **status**: see [Status](#status)
- **empty or unclear**: run [Status](#status) and ask which action the user wants

## Install

1. `uv` must be on the PATH.
2. Install the CLI as a uv tool so it has a stable path independent of the plugin version:
   `uv tool install --reinstall ${CLAUDE_PLUGIN_ROOT}/skills/claude-memory`
3. Resolve the tool bin directory with `uv tool dir --bin` and confirm `claude-memory` exists there.
4. Write `${CLAUDE_PLUGIN_DATA}/memory-session-start.sh` from [Scripts](#scripts) with both placeholders replaced by literal paths, overwriting any existing copy, and `chmod +x` it.
5. Add a `SessionStart` entry to `hooks` in `~/.claude/settings.json` whose `command` is the literal path of that script. Skip it if already present. Merge into the existing hook array; do not replace it.
6. Tell the user the hook takes effect on the next session. The CLI creates the database on first run.

## Uninstall

1. Remove only the `SessionStart` entry in `~/.claude/settings.json` whose `command` is `${CLAUDE_PLUGIN_DATA}/memory-session-start.sh`. Leave every other hook untouched.
2. Run `uv tool uninstall claude-memory`.
3. Leave the wrapper script and the database in place.

## Status

Report installed when `~/.claude/settings.json` has a `SessionStart` entry referencing `${CLAUDE_PLUGIN_DATA}/memory-session-start.sh` and `uv tool list` includes `claude-memory`, and not installed otherwise. Also report whether `${CLAUDE_PLUGIN_DATA}/memory.db` exists.

## Scripts

`${CLAUDE_PLUGIN_DATA}/memory-session-start.sh`, with `__DATA_DIR__` and `__BIN_DIR__` replaced by the literal values of `${CLAUDE_PLUGIN_DATA}` and `uv tool dir --bin`:

```bash
#!/usr/bin/env bash
# SessionStart hook: plain stdout reaches Claude as context on this event.
set -eu
[ -n "${CLAUDE_PROJECT_DIR:-}" ] || exit 0
export CLAUDE_PLUGIN_DATA="__DATA_DIR__"
exec "__BIN_DIR__/claude-memory" session-start
```
