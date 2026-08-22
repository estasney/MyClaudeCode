#!/usr/bin/env bash
# Resolve the per-project handoff directory inside the plugin's persistent data
# dir, create it, and print the directory, a timestamp prefix for the new file,
# and the existing handoffs (newest first, ordered by modification time so that
# notes migrated from older naming schemes still rank correctly).
#
# Args:
#   $1  plugin data dir  (pass "${CLAUDE_PLUGIN_DATA}")
#   $2  project root      (pass "${CLAUDE_PROJECT_DIR}")
set -euo pipefail

data_dir=${1:-}
project_dir=${2:-}

if [[ -z $data_dir || -z $project_dir ]]; then
  echo "handoff-dir.sh: need plugin data dir and project dir as args" >&2
  exit 1
fi

project_slug=$(basename "$project_dir")

handoff_dir="${data_dir}/handoffs/${project_slug}"
mkdir -p "$handoff_dir"

printf 'directory: %s\n' "$handoff_dir"
printf 'new file prefix: %s\n' "$(date +%Y%m%dT%H%M%S)"
printf 'existing handoffs (newest first):\n'
find "$handoff_dir" -maxdepth 1 -type f -name '*.md' -printf '%T@ %f\n' | sort -rn | cut -d' ' -f2-
