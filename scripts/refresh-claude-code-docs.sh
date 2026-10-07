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
  agent-sdk/agent-loop
  agent-sdk/claude-code-features
  agent-sdk/configuration
  agent-sdk/cost-tracking
  agent-sdk/custom-tools
  agent-sdk/examples
  agent-sdk/file-checkpointing
  agent-sdk/hooks
  agent-sdk/hosting
  agent-sdk/mcp
  agent-sdk/migration-guide
  agent-sdk/modifying-system-prompts
  agent-sdk/observability
  agent-sdk/overview
  agent-sdk/permissions
  agent-sdk/plugins
  agent-sdk/python
  agent-sdk/quickstart
  agent-sdk/secure-deployment
  agent-sdk/session-storage
  agent-sdk/sessions
  agent-sdk/skills
  agent-sdk/streaming-output
  agent-sdk/streaming-vs-single-mode
  agent-sdk/structured-outputs
  agent-sdk/subagents
  agent-sdk/todo-tracking
  agent-sdk/tool-search
  agent-sdk/troubleshooting
  agent-sdk/typescript
  agent-sdk/typescript-v2-preview
  agent-sdk/user-input
  agent-teams
  agent-view
  agents
  analytics
  artifacts
  auto-mode-config
  best-practices
  changelog
  channels
  channels-reference
  checkpointing
  claude-directory
  cli-reference
  commands
  common-workflows
  context-window
  cross-session-messaging
  debug-your-config
  env-vars
  errors
  fast-mode
  feature-availability
  features-overview
  fullscreen
  glossary
  goal
  headless
  hooks
  hooks-guide
  how-claude-code-works
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
  plugin-evals
  plugins/anthropic-marketplaces
  plugins/cli-hints
  plugins/cli-reference
  plugins/code-intelligence
  plugins/components
  plugins/create
  plugins/create-marketplace
  plugins/dependencies
  plugins/host-marketplace
  plugins/install
  plugins/loading
  plugins/manifest-reference
  plugins/marketplace-reference
  plugins/measure
  plugins/mods/admin
  plugins/mods/api
  plugins/mods/create
  plugins/mods/events
  plugins/mods/gallery
  plugins/mods/interface
  plugins/mods/overview
  plugins/mods/reference
  plugins/mods/test
  plugins/mods/troubleshoot
  plugins/org
  plugins/overview
  plugins/publish
  plugins/relevance
  plugins/security
  plugins/troubleshooting
  prompt-caching
  prompt-library
  remote-control
  routines
  sandbox-environments
  sandboxing
  scheduled-tasks
  sessions
  settings
  settings-reference
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
    <(curl -fsSL --max-time "$FETCH_TIMEOUT_SECONDS" "$INDEX_URL" | grep -oE 'docs/en/[a-z0-9/-]+\.md' | sed -E 's#docs/en/##; s#\.md$##' | sort -u)
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
    mkdir -p "$(dirname "$MANAGED_DIR/$slug.md")"
    mv "$tmp" "$MANAGED_DIR/$slug.md"
    echo "ok    $slug  http=$code"
  fi
  sleep "$FETCH_DELAY_SECONDS"
done

# Prune files the manifest omits, then folders left empty.
shopt -s nullglob globstar
declare -A expected
for slug in "${slugs[@]}"; do expected["$slug.md"]=1; done
for path in "$MANAGED_DIR"/**/*.md; do
  name="${path#"$MANAGED_DIR"/}"
  if [[ -z "${expected[$name]:-}" ]]; then
    rm -f "$path"
    echo "prune $name"
  fi
done
find "$MANAGED_DIR" -mindepth 1 -type d -empty -delete

if (( ${#failed[@]} )); then
  echo "" >&2
  echo "Refresh incomplete; ${#failed[@]} failed:" >&2
  printf '  - %s\n' "${failed[@]}" >&2
  exit 1
fi
echo ""
echo "Done: ${#slugs[@]} docs reconciled in references/upstream/"
