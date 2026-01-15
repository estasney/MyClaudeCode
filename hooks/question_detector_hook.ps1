#!/usr/bin/env pwsh
# Stop hook that detects when Claude asks 2+ questions without using AskUserQuestion tool
#
# Input structure (JSON via stdin):
# {
#   "session_id": "abc123",
#   "transcript_path": "~/.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
#   "cwd": "/path/to/project",
#   "permission_mode": "default",
#   "hook_event_name": "Stop",
#   "stop_hook_active": true
# }

$ErrorActionPreference = "Stop"

# Read input from stdin
$inputJson = [Console]::In.ReadToEnd()
$ccInput = $inputJson | ConvertFrom-Json

# Check if this is a Stop event
if ($ccInput.hook_event_name -ne "Stop") {
    exit 0
}

# Check if already processing a stop hook (prevent infinite loops)
$stopHookActive = if ($null -eq $ccInput.stop_hook_active) { $false } else { $ccInput.stop_hook_active }
if ($stopHookActive -eq $true) {
    exit 0
}

# Extract transcript path
$transcriptPath = $ccInput.transcript_path

# Get the last line from transcript
$lastLine = Get-Content -Path $transcriptPath -Tail 1 | ConvertFrom-Json

# Check if it's an assistant message, exit if not
if ($lastLine.message.role -ne "assistant") {
    exit 0
}

# Count question marks in text content
$questionCount = 0
foreach ($content in $lastLine.message.content) {
    if ($content.type -eq "text") {
        $questionCount += ($content.text -split '\?').Count - 1
    }
}

# If less than 2 questions, exit
if ($questionCount -lt 2) {
    exit 0
}

# Expected JSON schema for Stop hook response:
# {
#   "continue": boolean (optional),
#   "suppressOutput": boolean (optional),
#   "stopReason": string (optional),
#   "decision": "approve" | "block" (optional),
#   "reason": string (optional),
#   "systemMessage": string (optional),
#   "permissionDecision": "allow" | "deny" | "ask" (optional)
# }
#
# Note: systemMessage is only injected to Claude for UserPromptSubmit hooks.
# For Stop hooks with exit 0, Claude does not see stdout/systemMessage.

# Block Claude from stopping and inject reminder to use the tool
$response = @{
    decision = "block"
    reason = "<system-reminder>restate your questions and call the AskUserQuestion tool to get user input</system-reminder>"
    systemMessage = "Claude asked $questionCount questions but did not use the AskUserQuestion tool"
}

$response | ConvertTo-Json -Compress
exit 0
