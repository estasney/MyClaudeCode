# my-claude-mem

Session memory for Claude Code. Bundles the `claude-memory` MCP server: Chroma
collections with a SQLite FTS5 keyword index, fused by reciprocal rank fusion.

A `SessionStart` hook runs `uv sync --frozen` on the plugin root, so the locked
dependency set is installed into the plugin's own `.venv` before the MCP server
starts and the install cost stays outside the server's startup timeout. When
the environment already matches the lockfile the sync writes nothing. The
server then runs with `uv run --project`. Databases live under
`${CLAUDE_PLUGIN_DATA}`, which survives plugin updates.

Settings are read from `CLAUDE_MEMORY_*` environment variables; see
`src/claude_memory/settings.py`.
