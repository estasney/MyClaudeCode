---
name: writing-style-hooks
description: Install, uninstall, or check the status of the writing-style hooks that enforce the user's banned-word list. Use when the user asks to set up, remove, or inspect writing-style hooks, or to add or remove banned words.
argument-hint: [install | uninstall | status | test | add <word or phrase> | remove <word or phrase>]
allowed-tools: Bash, Write
disable-model-invocation: true
---

# Writing style hooks

Plugins cannot install hooks that the user can toggle on their own, so this skill installs them into the user's `settings.json` and removes them on request.

Data directory: `${CLAUDE_PLUGIN_DATA}`
Word list: !`"${CLAUDE_PLUGIN_ROOT}/scripts/ensure-banned-words.sh" "${CLAUDE_PLUGIN_DATA}"`

## Requested action

`$ARGUMENTS`

Match the request to one section below and follow only that section:

- **install**: see [Install](#install)
- **uninstall**: see [Uninstall](#uninstall)
- **status**: see [Status](#status)
- **test**: see [Test](#test)
- **add or remove words**: see [Add or remove words](#add-or-remove-words)
- **empty or unclear**: run [Status](#status) and ask which action the user wants

## Install

1. Pick the platform: PowerShell when running on Windows without Git Bash or when `CLAUDE_CODE_USE_POWERSHELL_TOOL=1`, otherwise bash. On bash, `jq` must be on the PATH.
2. Write the platform's two scripts from [Scripts](#scripts), overwriting any existing copy so they match this skill version. On bash, `chmod +x` both scripts.
3. Add a `SessionStart` entry and a `Stop` entry to `hooks` in `~/.claude/settings.json`. Skip an entry that is already present. Merge into existing hook arrays; do not replace them.
   - bash: `command` is `${CLAUDE_PLUGIN_DATA}/session-start.sh` or `${CLAUDE_PLUGIN_DATA}/stop.sh`.
   - PowerShell: `command` is `powershell.exe` with `args` `["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "<script>"]` where `<script>` is `${CLAUDE_PLUGIN_DATA}/session-start.ps1` or `${CLAUDE_PLUGIN_DATA}/stop.ps1`.
4. Tell the user hooks take effect on the next session.

## Uninstall

Remove only the hook entries in `~/.claude/settings.json` whose `command` or `args` reference a path under `${CLAUDE_PLUGIN_DATA}/`. Leave every other hook, the scripts, and the word list untouched.

## Status

Report installed when `~/.claude/settings.json` has both a `SessionStart` entry and a `Stop` entry referencing `${CLAUDE_PLUGIN_DATA}/session-start.*` and `${CLAUDE_PLUGIN_DATA}/stop.*`, partial when only one exists, and not installed otherwise. Also report the number of words in `${CLAUDE_PLUGIN_DATA}/banned-words.txt`.

## Test

1. Read `${CLAUDE_PLUGIN_DATA}/banned-words.txt`. If it is empty, say so and stop.
2. End your turn with a short nonsense reply that uses one or more of the banned words on purpose, and say nothing else.
3. The Stop hook should fire and feed back the matched words. If it does, restate the reply without them and report that the test passed. If no feedback arrives, report that the test failed and run [Status](#status).

## Add or remove words

Append or delete only the entries the user names in the word list, one per line, lower case. An entry may be a single word or a literal phrase with single spaces between words; no wildcards or regex. Do not reorder or reformat the rest of the file. No hook changes are needed; the scripts read the file on every event.

## Scripts

The word-start anchor without a word-end anchor is deliberate in both Stop scripts: "surface" matches "surfaced" and "surfaces".

### bash

`${CLAUDE_PLUGIN_DATA}/session-start.sh`

```bash
#!/usr/bin/env bash
# SessionStart hook: plain stdout reaches Claude as context on this event.
set -eu
wordlist="${CLAUDE_PLUGIN_DATA}/banned-words.txt"
[ -f "$wordlist" ] || exit 0
words=$(sed '/^[[:space:]]*$/d' "$wordlist" | paste -sd, - | sed 's/,/, /g')
[ -n "$words" ] || exit 0
echo "The user has banned these words from your replies, in any form (case insensitive, all inflections): $words"
```

`${CLAUDE_PLUGIN_DATA}/stop.sh`

```bash
#!/usr/bin/env bash
# Stop hook: scan the final reply for banned words and feed back the matches.
set -eu
wordlist="${CLAUDE_PLUGIN_DATA}/banned-words.txt"
[ -f "$wordlist" ] || exit 0
jq -c --rawfile w "$wordlist" '
  ($w | split("\n") | map(select(test("^\\s*$") | not))) as $words
  | select(.stop_hook_active != true and ($words | length) > 0)
  | (.last_assistant_message // "") as $reply
  | [$words[] as $word | select($reply | test("\\b" + $word; "i")) | $word]
  | select(length > 0)
  | {hookSpecificOutput: {hookEventName: "Stop", additionalContext: ("Your reply used banned words: " + join(", ") + ". Restate without them.")}}
'
```

### PowerShell

`${CLAUDE_PLUGIN_DATA}/session-start.ps1`

```powershell
# SessionStart hook: plain stdout reaches Claude as context on this event.
$wordlist = "${CLAUDE_PLUGIN_DATA}/banned-words.txt"
if (-not (Test-Path $wordlist)) { exit 0 }
$words = Get-Content $wordlist | Where-Object { $_.Trim() -ne "" }
if ($words.Count -eq 0) { exit 0 }
Write-Output "The user has banned these words from your replies, in any form (case insensitive, all inflections): $($words -join ', ')"
```

`${CLAUDE_PLUGIN_DATA}/stop.ps1`

```powershell
# Stop hook: scan the final reply for banned words and feed back the matches.
$wordlist = "${CLAUDE_PLUGIN_DATA}/banned-words.txt"
if (-not (Test-Path $wordlist)) { exit 0 }
$payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
if ($payload.stop_hook_active -eq $true) { exit 0 }
$words = Get-Content $wordlist | Where-Object { $_.Trim() -ne "" }
if ($words.Count -eq 0) { exit 0 }
$reply = [string]$payload.last_assistant_message
$matches = @($words | Where-Object { $reply -imatch ("\b" + [regex]::Escape($_)) })
if ($matches.Count -eq 0) { exit 0 }
@{
  hookSpecificOutput = @{
    hookEventName = "Stop"
    additionalContext = "Your reply used banned words: $($matches -join ', '). Restate without them."
  }
} | ConvertTo-Json -Compress
```
