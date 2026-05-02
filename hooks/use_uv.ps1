#!/usr/bin/env pwsh
# PreToolUse hook: block raw python invocations in Bash, require `uv run python`.
# Wire into ~/.claude/settings.json (Windows/pwsh) under hooks.PreToolUse with matcher "Bash".
$ErrorActionPreference = 'Stop'

# Read the Bash command string from the hook's stdin JSON payload.
$payload = [Console]::In.ReadToEnd()
if ([string]::IsNullOrEmpty($payload)) { exit 0 }
$cmd = $payload | jq -r '.tool_input.command // ""'
if ([string]::IsNullOrWhiteSpace($cmd)) { exit 0 }

# .NET regex, broken down (same semantics as use_uv.sh):
#   (?<!uv run )    negative lookbehind: skip when preceded by literal "uv run "
#   \b              word boundary (prevents matching inside ipython, mypython)
#   python[\d.]*    matches python, python3, python3.11, python2, etc.
#   (?=\s|$)        lookahead: next char is whitespace or end of string
#                   (prevents false positives on python-black, python_foo)
# PowerShell -match uses .NET regex which supports PCRE-style lookbehind natively.
if ($cmd -match '(?<!uv run )\bpython[\d.]*(?=\s|$)') {
  $msg = "Raw 'python' invocation is blocked. Use 'uv run python ...' instead. Python is managed by uv."
  # Emit PreToolUse deny JSON on stdout. The harness reads permissionDecision
  # and refuses the tool call, showing permissionDecisionReason to the model.
  jq -n --arg r $msg '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $r
    }
  }'
}
exit 0
