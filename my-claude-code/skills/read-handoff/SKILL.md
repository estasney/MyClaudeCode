---
name: read-handoff
description: Resume work from a handoff note without rediscovering the codebase. Manual; invoke with /read-handoff.
argument-hint: [optional filename fragment or keyword]
disable-model-invocation: true
---

Resume the work a handoff describes.

!`"${CLAUDE_PLUGIN_ROOT}/scripts/handoff-dir.sh" "${CLAUDE_PLUGIN_DATA}" "${CLAUDE_PROJECT_DIR}"`

The first line is the handoff directory; the rest are existing handoffs, newest first.

<optional_user_argument>
`$ARGUMENTS`
</optional_user_argument>

If it is empty, read the newest file. Otherwise grep the handoff files for it; if several match, list them and ask which to load.

Read the chosen file and name it, so the user knows which one loaded.

Then open what it lists under where the work sits, reading the named symbols. The note is a description of that code and may be behind it.

Go no further. Take the conventions as given rather than checking them. Open what it lists under where to look only if a convention it states is unclear.

Restate the remaining work as numbered items, in the note's order, one line each. Use your own words, not the note's — repeating it back verbatim shows nothing about what you understood. Say so where an item already looks done, or where the code no longer matches what the note claims.

<example>
[1] Add status, shipped_at, carrier and tracking_code to OrderResponse and OrderCreate in api/schemas/order.py.
[2] Extend migrations/versions/8f21_add_order_shipping.py to set status and shipped_at NOT NULL once the backfill has run.
[3] Fix the shipped_at serializer so it emits timestamptz. tests/api/test_orders.py fails on it now.
</example>

Then stop and wait. The user confirms the list, corrects an item, or strikes one, answering by number. Start nothing before they reply.

Where the note leaves you short, ask the user. Do not go reading to fill the gap. A handoff that cannot be resumed from is worth knowing about, and a survey hides that by making it work anyway.

Once confirmed, take the first item still standing.
