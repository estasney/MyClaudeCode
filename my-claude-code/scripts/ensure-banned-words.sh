#!/usr/bin/env bash
# Create the banned-words list inside the plugin's persistent data dir if it
# does not exist yet, and print its path.
#
# Args:
#   $1  plugin data dir  (pass "${CLAUDE_PLUGIN_DATA}")
set -euo pipefail

data_dir=${1:-}

if [[ -z $data_dir ]]; then
  echo "ensure-banned-words.sh: need plugin data dir as arg" >&2
  exit 1
fi

mkdir -p "$data_dir"
wordlist="${data_dir}/banned-words.txt"
touch "$wordlist"
printf '%s\n' "$wordlist"
