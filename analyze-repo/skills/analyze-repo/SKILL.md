---
name: analyze-repo
description: Index a Python git repository into a symbol and reference database, then answer questions about where a symbol is defined, who references it, what calls it, what it calls, and what it does, and to find the code that answers a natural language question. Use when asked how a codebase fits together, how to do something with it, what depends on a function or class, or for a description of an unfamiliar symbol, before reading files by hand.
---

# Repository Analysis

## Overview

The `analyze-repo` MCP server indexes one git commit of a repository at a time. basedpyright supplies the symbols in each tracked Python file and the locations that reference each symbol; tree-sitter labels each location with its syntactic role, so a call site is distinguishable from an attribute access or a type annotation. The index is stored in sqlite under the plugin data directory and survives across sessions. Python only.

## Tools

- `index_repository(repo_root, toolchain_overrides)` — indexes the working tree. The interpreter of the repository's own environment is discovered from the one virtual environment under `repo_root`, so imports resolve against its installed packages; `toolchain_overrides` maps `python` onto an explicit interpreter path when discovery fails. A second call for an unchanged tree returns the stored snapshot without re-indexing. Returns the snapshot id and row counts.
- `summarize_repository(snapshot_id)` — asks a model for a three-sentence description of every class, function and method that lacks one. Summaries are keyed by body hash, so bodies unchanged between commits are described once. Costs one model call per body; run it once per repository, not per question.
- `search_symbols(snapshot_id, name_fragment, scope)` — symbols whose dotted qualified name contains the fragment, with file, line span, kind, decorators and summary. Qualified names join enclosing names with dots, so `Client.connect` finds a method and `connect` finds every symbol named that. Scope `module_and_class` returns definitions and class members; `all` adds parameters and locals.
- `list_references(symbol_id)` — every location that refers to the symbol, with its file, line, syntactic role (`node_kind`, `parent_kind`, `parent_field`) and the symbol whose body contains it.
- `list_callers(symbol_id)` — symbols whose body calls this symbol.
- `list_callees(symbol_id)` — symbols this symbol's body calls.
- `embed_repository(snapshot_id)` — writes a search document for every class, function, method, parameter, and module or class level variable, then embeds each document text the configured model has not embedded yet. Definitions are described by their summary and values by their source line, so run `summarize_repository` first when function-level questions matter. Vectors are keyed by text and model, so re-running after summaries are added embeds only the changed documents.
- `search_code(snapshot_id, question, limit)` — symbols relevant to a natural language question, ranked by fusing keyword (BM25) and embedding similarity. A matching parameter is listed under the function that declares it in `matched_parameters`. `entry_points` lists the callers reached from the symbol that nothing calls in turn, with their decorators, which is where a user-facing tool, command or test usually sits.

## Workflow

1. Confirm the repository is a git checkout and locate its interpreter.
2. `index_repository`, then keep the returned `snapshot_id` for the session.
3. `search_symbols` to turn a name into a `symbol_id`.
4. `list_callers`, `list_callees`, or `list_references` to walk the graph from there.
5. `summarize_repository` only when the user asks what code does, or when orientation in a large unfamiliar repository is the task.
6. For a question phrased in words rather than names ("how do I set the batch size"), run `embed_repository` once per snapshot, then `search_code`. Answer from the hits and their entry points, then confirm with `list_references` or by reading the file.

## Reading the Results

- Every source file on disk that git does not ignore is indexed, tracked or not. Ignored files contribute no symbols and no references.
- Calls are derived from references whose `parent_kind` is `call` and `parent_field` is `function`. A method reached through an attribute chain such as `client.connect()` or `self.connect()` counts: the role is read at the whole attribute expression, whose `node_kind` is `attribute`. A symbol passed as a callback, decorated, or invoked through `getattr` is a reference but not a call edge.
- References resolve only within the repository. Uses from other repositories or from installed packages are not seen.
- A symbol with no references may still be alive: entry points, framework-invoked handlers, and names exported for external importers show as unreferenced.
- Every symbol records its parent symbol, so parameters and locals are stored and can be reached with scope `all`; the default question about a codebase wants `module_and_class`. Parameters have kind `parameter`; locals keep kind `variable`.
- A call made through a protocol or base class links to the protocol method, not to the implementations, so an implementation's entry points may show only its tests.
- Entry points are listed only for classes, functions and methods. A symbol that nothing calls is its own entry point.
