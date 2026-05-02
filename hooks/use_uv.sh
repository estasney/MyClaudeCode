#!/usr/bin/env bash
# PreToolUse hook: block raw python invocations in Bash, require `uv run python`.
# Wire into ~/.claude/settings.json under hooks.PreToolUse with matcher "Bash".
set -euo pipefail

# Read the Bash command string from the hook's stdin JSON payload.
cmd=$(jq -r '.tool_input.command // ""')
[ -z "$cmd" ] && exit 0

# PCRE regex, broken down:
#   (?<!uv run )    negative lookbehind: skip when preceded by literal "uv run "
#   \b              word boundary (prevents matching inside ipython, mypython)
#   python[\d.]*    matches python, python3, python3.11, python2, etc.
#   (?=\s|$)        lookahead: next char is whitespace or end of string
#                   (prevents false positives on python-black, python_foo)
# grep -Pq needs PCRE. GNU grep on Linux is fine; macOS BSD grep needs
# `brew install grep` and the command swapped to `ggrep -Pq`.
if printf '%s' "$cmd" | grep -Pq '(?<!uv run )\bpython[\d.]*(?=\s|$)'; then
  msg="Raw 'python' invocation is blocked. Use 'uv run python ...' instead. Python is managed by uv."
  # Emit PreToolUse deny JSON on stdout. The harness reads permissionDecision
  # and refuses the tool call, showing permissionDecisionReason to the model.
  jq -n --arg r "$msg" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $r
    }
  }'
fi
