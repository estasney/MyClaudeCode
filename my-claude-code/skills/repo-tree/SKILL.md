---
name: repo-tree
description: One command maps a codebase - every file with the classes, functions, and signatures it defines, with line numbers. Reach for this FIRST when exploring unfamiliar code, locating a symbol, or choosing which files to read; one run replaces a whole chain of Glob/Grep/Read calls.
allowed-tools: Bash(uv run:*)
---

# Repository Tree Generation

## Overview

Prints a directory tree of a repository where each source file is annotated with the symbols it defines (classes, functions, methods, types), each with its full signature including return type and its line number for direct navigation. Function bodies are not descended into: the map shows module-level and class-level symbols only, not local helpers.

Parsing is done with tree-sitter. Supported languages: Python, JavaScript, TypeScript/TSX, Go, Rust. Files in other languages are listed without symbols.

## When to Use

- Need a high-level overview of codebase organization and its API surface
- Orienting in an unfamiliar module before making changes
- Documenting codebase layout

## How to Generate

Run with the Bash tool:

```bash
uv run "${CLAUDE_SKILL_DIR}/scripts/parse_repo.py" "<PATH>"
```

The path can be a directory or a single file; a file target prints just that file's symbols.

`uv` resolves the script's dependencies automatically on first run; no setup needed.

<critical>Output scales with repo size and can consume a lot of tokens. Scope the path to a package or module rather than a whole large repo.</critical>

Options:

- `--source-only` — omit files that have no parsed symbols (assets, configs, docs). Use this to cut noise in mixed repos.

## Output

```
mypackage/
  core/
    config.py
      class Settings  :12
        def load(cls, path: Path) -> Settings  :24
    service.ts
      interface RetryPolicy  :3
      function fetchAll(client: Client): Promise<Item[]>  :18
```

File discovery respects `.gitignore` when the target is inside a git repository; otherwise hidden directories and well-known artifact directories (node_modules, __pycache__, dist, and similar) are skipped.

The user sees the output, there is no need to summarize or re-hash unless requested