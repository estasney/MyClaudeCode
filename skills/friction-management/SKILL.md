---
name: friction-management
description: Process and organize friction points into a curated library organized by domain and tags
allowed-tools: Read, Write, Glob, Grep, Edit
model: inherit
---

# Friction Management

Curate friction documentation into an organized, progressively disclosed library in `assets/`.

## Process

When given a friction documentation file (from `/friction` command):

1. **Extract Friction Points**
   - Read the plan file containing friction bullets
   - Each bullet has: description + tags in [brackets]

2. **Categorize by Domain**
   - Use tags to determine domain (python, javascript, formatting, etc.)
   - Group related frictions: `[python, typing]` → `assets/python-typing.md`
   - See: [Categorization rules](references/categorization.md)

3. **Update Domain Files**
   - Add friction point to appropriate file in `assets/`
   - Create new domain file if needed
   - Keep bullets concise with tags intact

4. **Update Index**
   - Update `assets/friction-index.md` mapping tags → domain files
   - Maintains discoverability

5. **Confirm**
   - Report what was added and where
   - Note any new domain files created

## Library Location

All friction points stored in `assets/` directory - this keeps the entire skill portable.
