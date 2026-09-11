#!/usr/bin/env bash
# Print every file under a skill's references/ directory as a path relative
# to the skill dir, one per line.
# Exists because a bare `ls` in a SKILL.md dynamic injection is blocked by
# the working-directory permission check once the plugin lives in the cache.
#
# Args:
#   $1  skill dir  (pass "${CLAUDE_SKILL_DIR}")
set -euo pipefail

skill_dir=${1:-}

if [[ -z $skill_dir ]]; then
  echo "list-references.sh: need skill dir as arg" >&2
  exit 1
fi

find "$skill_dir/references" -type f -printf 'references/%P\n' | sort
