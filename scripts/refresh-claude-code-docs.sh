#!/usr/bin/env bash
#
# Mirror Claude Code docs into references/upstream/ to match the `slugs`
# manifest: refetch each, prune the rest. Curated notes in references/ are
# untouched. Workflow: run, review `git diff`, commit. Non-zero exit = a fetch
# failed; do not commit as complete.
#
# Slugs come from the docs index (INDEX_URL). See --help.

set -uo pipefail

usage() {
  cat <<'EOF'
Usage: refresh-claude-code-docs.sh [--unlisted | --help]

Mirror Claude Code docs into references/upstream/ to match the slug manifest
in this script: refetch each, prune the rest.

Options:
  --unlisted  Print docs-index slugs the manifest omits, one per line, and exit.
  --help      Show this help and exit.

Exit status: non-zero if any fetch failed; do not commit as complete.
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANAGED_DIR="$SCRIPT_DIR/../my-claude-code/skills/claude-code-mastery/references/upstream"
BASE_URL="https://code.claude.com/docs/en"
INDEX_URL="https://code.claude.com/docs/llms.txt"
FETCH_DELAY_SECONDS=0.5
FETCH_TIMEOUT_SECONDS=30

slugs=(
  advisor
  agent-teams
  agents
  analytics
  artifacts
  auto-mode-config
  best-practices
  changelog
  channels
  channels-reference
  claude-directory
  cli-reference
  commands
  common-workflows
  context-window
  cross-session-messaging
  env-vars
  errors
  feature-availability
  features-overview
  glossary
  goal
  hooks
  hooks-guide
  interactive-mode
  jetbrains
  keybindings
  large-codebases
  mcp
  mcp-quickstart
  memory
  model-config
  output-styles
  permission-modes
  permissions
  plugin-dependencies
  plugin-hints
  plugin-marketplaces
  plugins
  plugins-reference
  prompt-caching
  prompt-library
  remote-control
  routines
  sandbox-environments
  sandboxing
  sessions
  settings
  setup
  skills
  statusline
  sub-agents
  terminal-config
  tools-reference
  voice-dictation
  workflows
  worktrees
)

get_unlisted() {
  comm -13 \
    <(printf '%s\n' "${slugs[@]}" | sort -u) \
    <(curl -fsSL --max-time "$FETCH_TIMEOUT_SECONDS" "$INDEX_URL" | grep -oE 'docs/en/[a-z0-9-]+\.md' | sed -E 's#docs/en/##; s#\.md$##' | sort -u)
}

case "${1:-}" in
  '') ;;
  --unlisted) get_unlisted; exit $? ;;
  --help|-h) usage; exit 0 ;;
  *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
esac

mkdir -p "$MANAGED_DIR"

# Fetch to a temp file; move into place only on success (-f fails on HTTP >= 400).
# Pause between fetches to stay polite to the docs host.
failed=()
for slug in "${slugs[@]}"; do
  tmp="$(mktemp)"
  code="$(curl -fsSL --max-time "$FETCH_TIMEOUT_SECONDS" -w '%{http_code}' -o "$tmp" "$BASE_URL/$slug.md")"
  status=$?
  if (( status != 0 )); then
    rm -f "$tmp"
    failed+=("$slug (curl exit $status, http $code)")
    echo "FAIL  $slug  http=$code" >&2
  else
    mv "$tmp" "$MANAGED_DIR/$slug.md"
    echo "ok    $slug  http=$code"
  fi
  sleep "$FETCH_DELAY_SECONDS"
done

# Prune files the manifest omits.
shopt -s nullglob
declare -A expected
for slug in "${slugs[@]}"; do expected["$slug.md"]=1; done
for path in "$MANAGED_DIR"/*.md; do
  name="$(basename "$path")"
  if [[ -z "${expected[$name]:-}" ]]; then
    rm -f "$path"
    echo "prune $name"
  fi
done

if (( ${#failed[@]} )); then
  echo "" >&2
  echo "Refresh incomplete; ${#failed[@]} failed:" >&2
  printf '  - %s\n' "${failed[@]}" >&2
  exit 1
fi
echo ""
echo "Done: ${#slugs[@]} docs reconciled in references/upstream/"
