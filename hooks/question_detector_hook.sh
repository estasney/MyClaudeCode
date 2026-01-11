#!/usr/bin/env bash
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

set -euo pipefail

# Read input from stdin
input=$(cat)

# Check if this is a Stop event
hook_event=$(echo "$input" | jq -r '.hook_event_name')
[[ "$hook_event" != "Stop" ]] && exit 0

# Check if already processing a stop hook (prevent infinite loops)
stop_hook_active=$(echo "$input" | jq -r '.stop_hook_active // false')
[[ "$stop_hook_active" == "true" ]] && exit 0

# Extract transcript path
transcript_path=$(echo "$input" | jq -r '.transcript_path')

# Get the last line from transcript
last_line=$(tail -1 "$transcript_path")

# Check if it's an assistant message, exit if not
role=$(echo "$last_line" | jq -r '.message.role')
[[ "$role" != "assistant" ]] && exit 0

# Count question marks in text content
question_count=$(echo "$last_line" | jq '
  .message.content[] |
  select(.type == "text") |
  .text |
  split("?") |
  length - 1
')

# If less than 2 questions, exit
[[ $question_count -lt 2 ]] && exit 0

# Block Claude from stopping and inject reminder to use the tool
jq -n --arg count "$question_count" '{
  decision: "block",
  reason: ("You asked \($count) questions without using the AskUserQuestion tool"),
  systemMessage: ("IMPORTANT: You just asked \($count) questions but did not use the AskUserQuestion tool. When you need to ask the user questions, you should use the AskUserQuestion tool instead of asking multiple questions in your response. Please use the AskUserQuestion tool now to gather the information you need.")
}'

exit 0
