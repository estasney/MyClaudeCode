#!/usr/bin/env bash
# Print the filenames in a skill's references directory, one per line.
# Exists because a bare `ls` in a SKILL.md dynamic injection is blocked by
# the working-directory permission check once the plugin lives in the cache.
#
# Args:
#   $1  references dir  (pass "${CLAUDE_SKILL_DIR}/references/upstream")
set -euo pipefail

references_dir=${1:-}

if [[ -z $references_dir ]]; then
  echo "list-references.sh: need references dir as arg" >&2
  exit 1
fi

find "$references_dir" -maxdepth 1 -type f -printf '%f\n' | sort
