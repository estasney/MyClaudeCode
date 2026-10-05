# vexicon

General knowledge store for Claude Code. Runs the
[`vexicon`](https://pypi.org/project/vexicon/) MCP server, which the plugin
installs from PyPI as a locked dependency: Chroma collections with a SQLite
FTS5 keyword index, fused by reciprocal rank fusion.

A `SessionStart` hook runs `uv sync --frozen` on the plugin root, so the locked
dependency set is installed into the plugin's own `.venv` before the MCP server
starts and the install cost stays outside the server's startup timeout. When
the environment already matches the lockfile the sync writes nothing. The
server then runs with `uv run --project`. Databases live under
`${CLAUDE_PLUGIN_DATA}`, which survives plugin updates.

The server reads its settings from `VEXICON_*` environment variables defined by
the `vexicon` package. The plugin manifest sets the database paths and the
embedding device.
