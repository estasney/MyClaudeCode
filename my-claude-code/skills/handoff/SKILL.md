---
name: handoff
description: Write a handoff so the next session can resume this work without rediscovering it. Manual; invoke with /handoff.
argument-hint: [optional name or note]
allowed-tools: Bash, Write
disable-model-invocation: true
---

You are writing to the session that picks this work up next.
It should be able to continue as if the work had not stopped.
It cannot, exactly. The note is lossy. Spend words where re-deriving costs most.

Never leave a reference the reader has to resolve. Anything that raises the question "which ones?" sends them into the codebase or the history, and that lookup is the cost this note exists to prevent. Name things. Do not count them and do not allude to them.

Write these, in this order.

**What is left to do.** The steps that remain, in the order to take them. The reader acts on this, so it opens the note. Every step names something specific to this work. A step that could stand in any handoff is filler — it is written to look complete, and it hedges instead of committing to what is actually unfinished. Confirm and verify are hedges: they presume the outcome and set no criterion. A step that exists to check whether another step worked is pointing at the real work, which is making that step correct by construction.

<examples>
<example>
<good>Add status, shipped_at, carrier and tracking_code to the response models in api/schemas/order.py. DbOrder in api/orm/order.py already has them.</good>
<bad>Add the four new columns to the response models.</bad>
<fault>Counting instead of naming. The reader leaves to find out which four, and which models.</fault>
</example>

<example>
<good>migrations/versions/8f21_add_order_shipping.py adds status and shipped_at as nullable and backfills them. Requires additional script to set as NOT NULL.</good>
<bad>Apply the migration and confirm the backfill leaves no nulls.</bad>
<fault>Inspecting for what the schema should enforce, and confirm presumes its own answer.</fault>
</example>

<example>
<good>pytest tests/api/test_orders.py fails on the shipped_at serializer, which still emits a date. The column is now timestamptz. Fix the serializer, not the test.</good>
<bad>Run the tests.</bad>
<fault>True of every handoff ever written, so it carries nothing.</fault>
</example>

<example>
<good>status is typed as str in api/schemas/order.py. Decide whether it becomes an enum or stays a string. The user has not ruled on this.</good>
<bad>Decide how to handle the status field.</bad>
<fault>Neither the choice nor its location is readable, so the open question is recorded in name only.</fault>
</example>
</examples>

**Where the work sits, and how it is written.** Paths from the repository root. No line numbers.

<example>
Files:
- api/schemas/order.py
  Symbols: OrderResponse, OrderCreate
- api/orm/order.py
  Symbols: DbOrder

Conventions:
- Response models are frozen. Field names come from an alias generator.
- ORM classes carry no validation. It lives in the schema layer.
</example>

Conventions are what you worked out about this area. They go here because rediscovering them costs a survey of several files, and because a note read tomorrow can be specific in a way lasting documentation cannot.

**What was decided, and what it was for.** Each decision with the reason behind it.

<example>
Decisions:
- shipped_at is timestamptz, not date. Carriers report in their own time zones.
- Rejected: a separate shipments table. An order ships once, so the join bought nothing.
</example>

Record rejections above all. Nothing else carries them, and the next session reaches for the same idea. State the reason and stop. Do not climb from a reason to a principle.

**Where to look, and how little to read.** Places that demonstrate the conventions, where the files above do not.

<example>
Look at:
- api/schemas/customer.py, CustomerResponse — the alias generator applied cleanly.
- tests/api/test_customers.py, test_response_shape — how these models get asserted.
</example>

These are the only places worth opening. Read the named symbol, not the surrounding file.

Before saving, one test. Could the next session take the next step, without hunting for where it goes, or working out how this area is written? If not, it is not ready.

### Where

!`"${CLAUDE_PLUGIN_ROOT}/scripts/handoff-dir.sh" "${CLAUDE_PLUGIN_DATA}" "${CLAUDE_PROJECT_DIR}"`

First line is the directory; `new file prefix` is the timestamp that keeps handoffs ordered; the rest are existing handoffs, newest first. Name the file `<prefix>-<session-name-or-three-word-slug>.md`, using the prefix shown.

<optional_user_argument>
`$ARGUMENTS`
</optional_user_argument>

If it holds a name or note, let it steer the filename and what the handoff emphasizes; if it's empty, ignore it.

Write it, then print the full path.
