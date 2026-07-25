#!/usr/bin/env bash
# Resolve the project's discussion directory, create it, and print the directory
# followed by the existing discussions (newest first by modification time) with
# their frontmatter inlined, so that choosing between resume and start costs no
# file reads.
#
# Args:
#   $1  project root  (pass "${CLAUDE_PROJECT_DIR}")
set -euo pipefail

project_dir=${1:-}

if [[ -z $project_dir ]]; then
  echo "discussion-dir.sh: need project dir as arg" >&2
  exit 1
fi

discussion_dir="${project_dir}/.claude/discussions"
mkdir -p "$discussion_dir"

printf 'directory: %s\n' "$discussion_dir"
printf 'existing discussions (newest first):\n'

# Frontmatter is everything between a leading '---' and the next '---'. Files
# without it contribute their name alone. Two spaces of indent nest each block
# under its list item, keeping the whole listing parseable as YAML.
print_frontmatter() {
  awk '
    NR == 1 { if ($0 != "---") exit; next }
    $0 == "---" { exit }
    { print "  " $0 }
  ' "$1"
}

find "$discussion_dir" -maxdepth 1 -type f -name '*.md' -printf '%T@ %p\n' |
  sort -rn |
  cut -d' ' -f2- |
  while IFS= read -r file; do
    printf -- '- file: %s\n' "${file##*/}"
    print_frontmatter "$file"
  done
