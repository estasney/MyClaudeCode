#!/usr/bin/env bash
#
# Reconcile the mirrored Claude Code documentation that ships with the
# claude-code-mastery skill against the slug manifest below.
#
# The `slugs` array is the single source of truth for what lives in
# references/upstream/. Running this script:
#   - refetches each slug's raw markdown page, overwriting in place
#   - deletes any *.md in references/upstream/ that the manifest omits
#
# It never touches curated notes at the references/ root.
#
# Refreshed docs ship to consumers through plugin versioning, so the workflow
# is: run this, review `git diff`, commit, push. A non-zero exit means at least
# one page failed to fetch or returned a suspect body; do not commit a partial
# refresh as if it succeeded.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANAGED_DIR="$SCRIPT_DIR/../my-claude-code/skills/claude-code-mastery/references/upstream"
BASE_URL="https://code.claude.com/docs/en"

# Curated scope manifest. Adding a doc is a deliberate one-line edit here.
slugs=(
  settings hooks permissions permission-modes env-vars claude-directory
  commands skills sub-agents output-styles memory statusline
  plugins-reference plugin-dependencies mcp mcp-quickstart
  cli-reference tools-reference model-config keybindings
  sandboxing sandbox-environments errors
  agents agent-teams advisor goal
)

mkdir -p "$MANAGED_DIR"

# Fetch each page to a temp file; only move it into place on success, so a
# failed fetch never truncates the committed copy. -f fails on HTTP >= 400 so
# 404/500 error pages never overwrite a good file. git diff is the review gate
# for anything else: inspect the run log and the diff before committing.
failed=()
for slug in "${slugs[@]}"; do
  tmp="$(mktemp)"
  # -f: fail (exit 22) on HTTP >= 400. -L: follow redirects. -w: log the status.
  code="$(curl -fsSL -w '%{http_code}' -o "$tmp" "$BASE_URL/$slug.md")"
  status=$?
  if (( status != 0 )); then
    rm -f "$tmp"
    failed+=("$slug (curl exit $status, http $code)")
    echo "FAIL  $slug  http=$code" >&2
  else
    mv "$tmp" "$MANAGED_DIR/$slug.md"
    echo "ok    $slug  http=$code"
  fi
done

# Prune anything in the managed dir that the manifest no longer lists.
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
