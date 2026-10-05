---
name: lsp-trace
description: Diagnose the python-lsp plugin when basedpyright resolves imports against the wrong interpreter or virtual environment, or when Python diagnostics differ between machines or platforms. Covers capturing a wire trace from the lsp_mux proxy and reading which interpreter basedpyright chose.
---

# Tracing the Python LSP

## Overview

The plugin registers one language server, `lsp_mux.py`, which runs basedpyright and ruff as child processes and presents them to Claude Code as a single server. Interpreter selection happens inside basedpyright, so finding out why it picked the wrong venv means capturing what Claude Code sent and what basedpyright logged back.

## Capturing a trace

The mux reads two environment variables, which it inherits from the shell that launches `claude`:

- `LSP_MUX_LOG` — file path; the mux appends its own log lines and the child servers' stderr there.
- `LSP_MUX_DEBUG` — `1` traces routing; `2` also dumps every wire message, truncated per message.

Level `2` is required, because basedpyright reports its environment through `window/logMessage` notifications, which only appear in the wire dump.

basedpyright's default log level hides the interpreter report. Set `basedpyright.analysis.logLevel` to `Trace` in the `settings` block of `.lsp.json` for the traced session, and remove it afterward.

Set the variables with the syntax of the shell in use: `export` in bash, `$env:` in PowerShell, `set` in cmd. Then start `claude` from that shell and open a Python file so the server starts.

## Reading the trace

- **initialize** (client to mux): `rootUri` and `workspaceFolders` are the root basedpyright uses as its project root.
- **workspace/configuration** (basedpyright to client) and its response: the settings basedpyright received, after any variable expansion by Claude Code.
- **Execution environment** (basedpyright log line): the interpreter basedpyright settled on. A bare `python` means it found no venv and fell back to whatever `python` is on its PATH, which is the uvx tool environment basedpyright itself runs in.
- **Search paths** (basedpyright log lines following it): the `site-packages` directory listed there should belong to the project's venv.

## How basedpyright picks an interpreter

In order of precedence:

1. `python.pythonPath` from settings, or `pythonPath` from a config file.
2. `venvPath` joined with `venv`. `venvPath` may come from settings or a config file, but `venv` is read only from a config file (`pyproject.toml` or `pyrightconfig.json`); `python.venv` in language-server settings is ignored.
3. `.venv` in the project root, checked only when none of `pythonPath`, `venvPath`, or `venv` is set. The interpreter looked for is `.venv/bin/python` on POSIX and `.venv\Scripts\python.exe` on Windows.
4. `python` on PATH.

Consequences for this plugin:

- Claude Code does not expand `${...}` variables inside `settings`. basedpyright drops any path setting that still contains `${` after its own expansion, which only knows `${workspaceFolder}` and a few `${env:...}` names.
- A `venvPath` that resolves to an existing path, set without a config-file `venv`, switches off step 3 and leaves basedpyright on step 4.
- The project root is the workspace root from `initialize`, or the directory of a `pyproject.toml` or `pyrightconfig.json` found there. A workspace root that is a parent of the project, such as a monorepo root, misses a `.venv` that sits in a subproject.
