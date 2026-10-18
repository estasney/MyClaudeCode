---
name: scaffold-python
description: Use when settling the interface of a large Python change with the user. Use when a change adds many symbols across modules.
allowed-tools: Bash(uv run:*)
---

# Scaffold Python

When the user invokes this skill, they want to start designing a large interface change. When you load it yourself, the change in front of you adds many symbols across modules.

## Workflow

1. Write the map to `.claude/scaffold/<change>.txt` in the repo, and revise it with the user until they approve it.
2. Run the script with `--check`, fix every reported issue, then run without `--check`.
3. Ask the user how they want imports and bodies written. Subagent, different model, etc. 

## How to Run

```bash
uv run "${CLAUDE_SKILL_DIR}/scripts/scaffold.py" "<SOURCE_ROOT>" "<MAP_FILE>" --check
uv run "${CLAUDE_SKILL_DIR}/scripts/scaffold.py" "<SOURCE_ROOT>" "<MAP_FILE>"
```

`SOURCE_ROOT` is the directory holding the top-level packages: `src` in a src layout, the repo root in a flat layout. Map paths start at the package name, matching import paths. Exit codes: 0 clean, 1 issues reported as `map:line  message`, 2 bad arguments.

## Map Format

Indentation nests. A line is one of:

```
pkg/                          directory
module.py                     file; children are module-level symbols
@decorator                    applies to the next class or def
class Name(Bases)             children are fields, methods, nested classes
def name(params) -> Ret       body: raise NotImplementedError
name: Type = default          field or module variable
```

A method of a `Protocol` class or a def under `@overload` gets `...`. A trailing `:line` marker from repo-tree output is ignored, so the map can start as that output with line numbers left in. Imports are not expressed; the fill step adds them.

```
shop/
  models/
    order.py
      class OrderLine(BaseModel)
        sku: str
        quantity: int
        def subtotal(self) -> Money
  repository.py
    class OrderRepository(Protocol)
      def get(self, order_id: int) -> Order
```

Additive only: new files are created, and an existing module or class gains the new members. Any other existing symbol named in the map is an issue. New directories get an empty `__init__.py` unless the map lists one.

## Output

The script prints each added symbol with its line in the written file. The user sees this output; report what is left to fill, not a re-listing.
