---
name: repo-tree
description: Generate tree-sitter parsed repository maps for codebase analysis. Use when you need a structured overview of a repository's file organization and structure.
allowed-tools: Read(./*)
---

# Repository Tree Generation

## Overview

This skill uses tree-sitter parsing to generate a comprehensive map of a repository's structure.

## When to Use

- Need a high-level overview of codebase organization
- Want to understand file hierarchy and relationships
- Analyzing project structure before making changes
- Documenting codebase layout

## How to Generate

<critical>The paths must be quoted!</critical>
<critical>This can generate *a lot* of tokens. Avoid running on the entire repo, focus on modules</critical>



Use the Bash tool to run:

```bash
uv run "C:\Users\estasney\my_programs\scripts\parse_repo.py" "<PATH_TO_REPO>"
```

Where `<PATH_TO_REPO>` is the absolute path to the repository you want to analyze.

The script output will be captured automatically and can be used for analysis.

## Output

The tool generates a tree-sitter parsed representation of the repository, providing:
- File structure and organization
- Directory hierarchy
- Project layout patterns
