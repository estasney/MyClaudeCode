#!/usr/bin/env bash
# Sync the claude-memory virtualenv into the plugin data directory so it
# survives plugin updates. The lockfile copy in the data directory records
# which dependency set the venv was built from; a differing or missing copy
# triggers a sync.
set -euo pipefail

root="${CLAUDE_PLUGIN_ROOT:?CLAUDE_PLUGIN_ROOT is not set}"
data="${CLAUDE_PLUGIN_DATA:?CLAUDE_PLUGIN_DATA is not set}"
bundled_lock="${root}/uv.lock"
synced_lock="${data}/uv.lock"

mkdir -p "${data}"

if [ -d "${data}/.venv" ] && cmp -s "${bundled_lock}" "${synced_lock}"; then
    exit 0
fi

export UV_PROJECT_ENVIRONMENT="${data}/.venv"
if uv sync --project "${root}" --no-dev --frozen --quiet; then
    cp "${bundled_lock}" "${synced_lock}"
else
    rm -f "${synced_lock}"
    echo "claude-memory: uv sync failed; the memory MCP server may time out on startup" >&2
    exit 1
fi
