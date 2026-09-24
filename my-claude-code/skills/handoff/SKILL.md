---
name: handoff
description: Write a handoff so the next session can resume this work without rediscovering it. Manual; invoke with /handoff.
argument-hint: [optional name or note]
allowed-tools: Bash, Write
disable-model-invocation: true
---

You are serializing your context. A new session will read your handoff. 
When writing, ask: "Would a new session, without context, understand what I'm talking about?"
Write efficiently! Technical notes. Quick references. Ignore formatting. ascii notes.
Sentences may not use semicolons, em dashes or any other grammatical devices to extend sentence length.
Do not be overly specific. "Ran data analysis script over 86 files, 2169 symbols and 4687 occurrences on commit fd474ce". This is trivia.  
Do not rely on content from other handoffs. This must be self-contained.

Write these, in this order.

**Domain**

One sentence about the repo. What's it do?
One overall sentence that would describe the discussion and work.
One sentence per task completed.

**Conventions**

Conventions the user mentioned.
Goals the user mentioned.

**Decisions**

<important>
Claude must never represent derived, inferred, or consequential decisions here. 
</important>

One sentence per user decision. Explicitly. 
If you resumed from another handoff you can include those.

**Miscellany**

<important>
This is an optional section. It is not a catch-all.
</important>

Before saving, one test. Could the next session take the next step, without hunting for where it goes, or working out how this area is written? If not, it is not ready.

### Where

!`"${CLAUDE_PLUGIN_ROOT}/scripts/handoff-dir.sh" "${CLAUDE_PLUGIN_DATA}" "${CLAUDE_PROJECT_DIR}"`

First line is the directory; `new file prefix` is the timestamp that keeps handoffs ordered; the rest are existing handoffs, newest first. Name the file `<prefix>-<session-name-or-three-word-slug>.md`, using the prefix shown.

<optional_user_argument>
`$ARGUMENTS`
</optional_user_argument>

If it holds a name or note, let it steer the filename and what the handoff emphasizes; if it's empty, ignore it.

Write it, then print the full path.
