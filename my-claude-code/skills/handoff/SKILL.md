---
name: handoff
description: Write a handoff that gets the next session thinking like this one. Manual; invoke with /handoff.
argument-hint: [optional name or note]
allowed-tools: Bash, Write
disable-model-invocation: true
---

You are writing to the session that continues or builds upon this work.
This is not a record of what happened; it is what you wish you'd known at the start.
Get it thinking about the work as you do now, so it handles what comes next the way you would.

**The values** — name what this work taught you to care about — not the decisions you made, but what those decisions were for. State each as something you want, not something to avoid, with no example or mechanism inside it. Test each by asking "why does that matter?" — if you can answer, climb to the answer; the value is where "why" runs out. Keep only what the next session couldn't get from reading the code.

Then, only where they apply: the terms you coined and what they mean, and the next move — but only when the user named it.

**Drop:**

- What happened: steps taken, files touched, problems already closed.
- Praise, friction, corrections — keep the settled conclusion, not the episode.
- Anything the repo, git, or your standing rules already carry — it loads on its own.
- Internal labels and hedging — name things for what they are; assert what you know.

Shortest form that carries the meaning. Not a template — include only what applies.

Before saving: on a problem that never came up this session, would this note make the next session decide what you'd decide? If not, it isn't ready.

### Where

!`"${CLAUDE_PLUGIN_ROOT}/scripts/handoff-dir.sh" "${CLAUDE_PLUGIN_DATA}" "${CLAUDE_PROJECT_DIR}"`

First line is the directory; `new file prefix` is the timestamp that keeps handoffs ordered; the rest are existing handoffs, newest first. Name the file `<prefix>-<session-name-or-three-word-slug>.md`, using the prefix shown. 

<optional_user_argument>
`$ARGUMENTS`
</optional_user_argument>

If it holds a name or note, let it steer the filename and what the handoff emphasizes; if it's empty, ignore it.

Write it, then print the full path.
