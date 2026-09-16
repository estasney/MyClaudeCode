# my-claude-mem

Session memory for Claude Code. Bundles the `claude-memory` MCP server: Chroma
collections with a SQLite FTS5 keyword index, fused by reciprocal rank fusion.

The server runs over stdio via `uv run --project`. Its databases live under
`${CLAUDE_PLUGIN_DATA}`.

Settings are read from `CLAUDE_MEMORY_*` environment variables; see
`src/claude_memory/settings.py`.
