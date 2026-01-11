#!/bin/bash
# Read JSON input once
input=$(cat)

# Helper functions for common extractions
get_model_name() { echo "$input" | jq -r '.model.display_name'; }
get_current_dir() { echo "$input" | jq -r '.workspace.current_dir'; }
get_project_dir() { echo "$input" | jq -r '.workspace.project_dir'; }
get_version() { echo "$input" | jq -r '.version'; }
get_cost() { echo "$input" | jq -r '.cost.total_cost_usd'; }
get_duration() { echo "$input" | jq -r '.cost.total_duration_ms'; }
get_lines_added() { echo "$input" | jq -r '.cost.total_lines_added'; }
get_lines_removed() { echo "$input" | jq -r '.cost.total_lines_removed'; }
get_input_tokens() { echo "$input" | jq -r '.context_window.total_input_tokens'; }
get_output_tokens() { echo "$input" | jq -r '.context_window.total_output_tokens'; }
get_context_window_size() { echo "$input" | jq -r '.context_window.context_window_size'; }

# Calculate total tokens
total_input=$(get_input_tokens)
total_output=$(get_output_tokens)
total=$((total_input + total_output))

# Get detailed token breakdown from current_usage
current_usage=$(echo "$input" | jq '.context_window.current_usage')
if [ "$current_usage" != "null" ]; then
    cache_creation=$(echo "$current_usage" | jq -r '.cache_creation_input_tokens // 0')
    cache_read=$(echo "$current_usage" | jq -r '.cache_read_input_tokens // 0')
else
    cache_creation=0
    cache_read=0
fi

# Get model and cost
model=$(get_model_name)
cost=$(get_cost)

# Format cost with 2 decimals, fallback to 0.00 if null/empty
if [ "$cost" = "null" ] || [ -z "$cost" ]; then
    cost="0.00"
else
    cost=$(printf "%.2f" "$cost")
fi

# Format tokens with commas
formatted_total=$(printf "%'d" "$total" 2>/dev/null || echo "$total")
formatted_input=$(printf "%'d" "$total_input" 2>/dev/null || echo "$total_input")
formatted_output=$(printf "%'d" "$total_output" 2>/dev/null || echo "$total_output")
formatted_cache_creation=$(printf "%'d" "$cache_creation" 2>/dev/null || echo "$cache_creation")
formatted_cache_read=$(printf "%'d" "$cache_read" 2>/dev/null || echo "$cache_read")

# Build the status content
CONTENT=$(printf '%s (%s) $%s | ↓%s ↑%s ⊕ %s ⊙ %s' "$model" "$formatted_total" "$cost" "$formatted_input" "$formatted_output" "$formatted_cache_creation" "$formatted_cache_read")

# Right-justification code (commented out for left-aligned display)
# Get terminal width using stty with /dev/tty
# cols=$(stty size </dev/tty 2>/dev/null | cut -d' ' -f2)
# if [ -z "$cols" ]; then
#     cols=${COLUMNS:-80}
# fi
#
# content_len=${#CONTENT}
# # Account for unicode symbols that may display as 2 columns wide
# # We have 4 symbols: ↓ ↑ ⊕ ⊙ - add extra space for their visual width
# visual_width=$((content_len + 4))
# pad=$((cols - visual_width))
# (( pad < 0 )) && pad=0
#
# # Print with right alignment using ANSI escape codes
# # Move cursor to the right position
# printf '\033[%dG%s' "$((pad + 1))" "$CONTENT"

# Print with left alignment
printf '%s' "$CONTENT"
