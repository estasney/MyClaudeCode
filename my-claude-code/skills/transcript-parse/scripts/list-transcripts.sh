#!/usr/bin/env bash
# List the session transcripts recorded for a project, newest first, each with
# the title Claude Code gave the session so one can be chosen without opening
# any of them. Titles come from the last ai-title record, falling back to the
# first prompt the user sent.
#
# The transcript directory is found by matching against the listing of
# ~/.claude/projects, never by building the directory name from the project
# path. Only the flattening of separators into dashes is established; the rest
# of the rule is not, so a constructed name can be wrong where a matched one
# cannot. Sessions started in a subdirectory are filed under that subdirectory,
# so more than one directory can match, and every match is listed.
#
# Args:
#   $1  project root, or any name to match against the listing
#       (pass "${CLAUDE_PROJECT_DIR}" for the current project)
#   $2  current session id, optional  (pass "${CLAUDE_SESSION_ID}")
set -euo pipefail

target=${1:-}
session_id=${2:-}

if [[ -z $target ]]; then
  echo "list-transcripts.sh: need a project dir or name as arg 1" >&2
  exit 1
fi

projects_dir="${HOME}/.claude/projects"

if [[ ! -d $projects_dir ]]; then
  echo "list-transcripts.sh: no such directory: ${projects_dir}" >&2
  exit 1
fi

# A path arrives as its own name flattened, so the last segment is what
# survives into the directory name and is the part worth matching on.
name=$(basename "$target")

list_directory() {
  local dir=$1

  printf 'directory: %s\n' "$dir"

  # One find pass carries the sort key, the modification time, the size and the
  # path, so no per-file stat or du is needed.
  find "$dir" -maxdepth 1 -type f -name '*.jsonl' \
    -printf '%T@\t%TY-%Tm-%Td %TH:%TM\t%s\t%p\n' |
    sort -rn |
    cut -f2- |
    while IFS=$'\t' read -r when bytes path; do
      local id kb size title marker
      id=$(basename "$path" .jsonl)

      kb=$((bytes / 1024))
      if ((kb >= 1024)); then size="$((kb / 1024))M"; else size="${kb}K"; fi

      # One streaming pass: keep the newest title and the earliest user prompt.
      title=$(jq -rn '
        reduce inputs as $x ({title: null, prompt: null};
          if $x.type == "ai-title" then .title = $x.aiTitle
          elif .prompt == null and $x.promptSource != null
               and ($x.message.content | type) == "string"
            then .prompt = $x.message.content
          else . end)
        | (.title // .prompt // "untitled")
        | gsub("\\s+"; " ") | .[0:90]' "$path" 2>/dev/null || echo "unreadable")

      if [[ $id == "$session_id" ]]; then marker="  (this session)"; else marker=""; fi

      printf '%s  %6s  %s  %s%s\n' "$when" "$size" "$id" "$title" "$marker"
    done
}

matches=$(find "$projects_dir" -mindepth 1 -maxdepth 1 -type d -name "*${name}*" | sort)

if [[ -z $matches ]]; then
  printf 'no transcript directory matches %s\n' "$name"
  printf 'projects with transcripts:\n'
  find "$projects_dir" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort
  exit 0
fi

printf 'transcripts (newest first):\n'
printf '%s\n' "$matches" | while read -r dir; do list_directory "$dir"; done
