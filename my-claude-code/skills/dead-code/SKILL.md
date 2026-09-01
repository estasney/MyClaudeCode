---
name: dead-code
description: Find dead code in a Python codebase - counts references for every module-level class, function and variable through basedpyright's language server and lists what nothing points at. Use when asked to find dead code, unused functions, or unreferenced symbols, or to gauge how widely a symbol is used before removing or changing it.
allowed-tools: Bash(uv run:*)
---

# Dead Code Detection

## Overview

Starts basedpyright's language server over the target, collects every module-level class, function, variable and constant it can see, and asks the server for the references to each. A symbol with zero references is a dead-code candidate. A class is counted as one unit: its methods and attributes are not checked individually, so a referenced class can still contain dead methods this tool will not see. Python only.

## When to Use

- Asked to find dead or unused code
- Deciding whether a symbol is safe to remove
- Sizing the blast radius of a change: the reference count says how widely a symbol is used

## How to Run

Run with the Bash tool:

```bash
uv run "${CLAUDE_SKILL_DIR}/scripts/refcount.py" "<PROJECT_ROOT>" [<PATH> ...] --zero-only
```

`uv` resolves basedpyright automatically on first run; no setup needed.

Options:

- `--zero-only` — only symbols with zero references. The default for dead-code hunting; omit it when the question is how much a symbol is used rather than whether.
- `--json` — structured output instead of the table.
- `--timeout` — seconds to wait for any single language server message; default 120. On expiry the script prints one line to stderr and exits 1, as it does for any other failure.

The project root is where references are searched; the language server is rooted there, so it picks up the project's basedpyright config and a `src` directory. When the root lands inside a package, the script ascends to the package's parent for the search scope, since imports only resolve from there — a package detected by its `__init__.py` files, so a namespace package needs the parent passed explicitly. Code outside that resolved scope contributes no references.

The optional paths — Python files or directories inside the root — control which symbols get counted; with none given, every file under the root is counted. A relative path is taken relative to the root, not the working directory. Output paths are relative to the root.

Pass the production package or module as a path rather than counting the whole root: scanning a whole repo counts test functions and scripts as candidate symbols, and every pytest test reads 0 because nothing references tests.

<critical>Every symbol costs one references request, so runtime scales with symbol count. Narrowing the paths to a package or module cuts the symbols counted, not the reference search, and is safe.</critical>

## Output

One line per symbol, fewest references first, followed by the files the references come from with a per-file count:

```
   0  function  build_legacy_index  (search/index.py:41)
   0  class     LegacyExporter  (export/exporter.py:60)
   2  class     Exporter  (export/exporter.py:12)  <- tests/test_exporter.py (2)
   5  function  load_config  (config.py:8)  <- app.py (3), tests/test_config.py (2)
```

In JSON the same appears as `referenced_from`, a list of `{file, count}`.

## Reading the Results

Zero references is a candidate, not a verdict — in both directions.

A nonzero count can still be dead: a symbol referenced only by its own tests reads as alive while nothing actually uses it. The source files after `<-` make this visible — when every source is a test file, the symbol is a candidate. What counts as a test is a per-repo naming convention; the script lists the files and you make the call.

A zero can still be alive. Before calling a symbol dead, rule out:

- Entry points — `__main__` blocks, console scripts in pyproject.toml, things invoked by name from CI or scripts.
- Framework-invoked code — pytest fixtures and hooks, route handlers, CLI subcommands, task-queue jobs. Registered by decorator, called by the framework, referenced by nothing.
- Dynamic access — `getattr`, `globals()`, `importlib`, names assembled from strings in configs, templates, or UI markup (Kivy kv files, Django templates).
- Public API — names exported through `__all__` or a package `__init__` exist for importers outside the analyzed tree.

Counts are not transitive: a symbol referenced only by dead symbols still shows a nonzero count. After deleting confirmed dead code, run again — removal exposes the next layer.

The user sees the raw output; report the verdicts, not a re-listing.
