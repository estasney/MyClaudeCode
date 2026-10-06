---
name: import
description: Bulk-load entries into a vexicon space using HybridClient.
argument-hint: [source] [space]
disable-model-invocation: true
---
Write a one-off conversion script in the scratchpad and run it with the plugin's own environment. The script talks to the same databases as the MCP server, so what it writes is what later searches find.

## Before writing the script

1. Resolve the target space with `describe_space`. If it does not exist, ask the user for its readme and embedding model rather than inventing them, download the model with `download_embedding_model`, then create the space with `create_space`. The library only loads models already on disk.
2. Note `embedding_max_tokens` from the space. Each entry's text must fit in half of it; longer text is truncated silently when embedded. Split or summarize the source accordingly.
3. Decide the ID scheme up front. IDs are kebab-case mnemonics, unique within the space, and a batch with an ID that already exists is rejected whole. Derive IDs from the source so a rerun collides instead of duplicating.

## The script

Pure conversion first, one `add_entries` call at the end. Parse the source into `NewEntry` objects, which validate the ID pattern, then write them in one batch so a failure leaves the space untouched.

```sh
cat > <scratchpad>/import.py <<'EOF'
from pathlib import Path

from vexicon import Device, HybridClient, NewEntry

SPACE = "..."
SOURCE = Path("...")


def entries_from(source: Path) -> list[NewEntry]:
    # Read the source, split it into units, and return one NewEntry per unit.
    # id: kebab-case, derived from the source. meta: scalars or lists of scalars.
    ...


with HybridClient(
    Path("${CLAUDE_PLUGIN_DATA}/chroma"),
    Path("${CLAUDE_PLUGIN_DATA}/hybrid.db"),
    device=Device("${user_config.device}"),
) as client:
    entries = entries_from(SOURCE)
    client.add_entries(SPACE, entries)
    print(f"added {len(entries)} entries to {SPACE}")
EOF
```

```sh
uv run --project ${CLAUDE_PLUGIN_ROOT} --frozen --no-dev --no-python-downloads python <scratchpad>/import.py
```

`meta` values must be str, int, float, bool, or lists of those. `created_at` is set by the library; do not put it in `meta`. The keys `readme`, `embedding_repo_id`, and `embedding_max_tokens` are reserved on spaces, not entries.

Errors to expect: `DuplicateEntryIdsError` when IDs repeat in the batch, `EntriesExistError` listing the IDs already stored, and `SpaceNotIndexedError` when the space name is wrong. Fix the conversion and rerun rather than catching them.

## After the import

The running MCP server keeps its own copy of Chroma in memory and does not see the new entries until it reloads, which happens after its idle timeout or when the user reconnects it with `/mcp`. Verify with `describe_space` or `search` after that.

Any text below names the source, the space, or narrows what to import.

---
`$ARGUMENTS`
---
