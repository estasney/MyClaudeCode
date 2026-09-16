# my-claude-mem

Session memory for Claude Code. Bundles the `claude-memory` MCP server: Chroma
collections with a SQLite FTS5 keyword index, fused by reciprocal rank fusion.

The server runs over stdio via `uv run --project`. Its virtualenv and databases
live under `${CLAUDE_PLUGIN_DATA}`, which survives plugin updates. A
`SessionStart` hook (`scripts/ensure-venv.sh`) syncs the virtualenv whenever the
bundled `uv.lock` differs from the copy recorded in the data directory, so the
MCP server does not pay the install cost inside its 30 second startup window.

Settings are read from `CLAUDE_MEMORY_*` environment variables; see
`src/claude_memory/settings.py`.
