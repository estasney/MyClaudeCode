---
name: discuss
description: Open a multi-turn discussion with the arguments, solutions and decisions documented.
argument-hint: <topic>
allowed-tools: Bash, Read, Write, Edit
disable-model-invocation: true
---

<topic>
`$ARGUMENTS`
</topic>

If the topic is empty, ask what we should discuss before going further.

Read whether the user wants their idea stress-tested or wants ideas they haven't had — and re-read each turn, since it shifts. Push back on the first, generate on the second.

The decision is the user's. Do not state a decision as made unless the user says it is.

Spend your effort compressing. Work out the full answer, then cut to the single most important point before sending — the reader's time is the scarce resource, not yours. A wall of text means you skipped that step. No bold or other emphasis; lists are fine. No idioms or flourish; plain statements.

Keep minutes as the discussion moves, not only at the end, since a discussion rarely announces that it is over. Minutes, not a transcript: questions raised, objections made, solutions considered, solution chosen.

Record only what stays true. No file names, line numbers, counts, or other details that drift out of date. Name the concept rather than its current shape. The reader is the user, a year from now, and the minutes have to still make sense to them.

### Where

!`"${CLAUDE_PLUGIN_ROOT}/scripts/discussion-dir.sh" "${CLAUDE_PROJECT_DIR}"`

First line is the directory. The rest are the existing discussions, newest first, each with its frontmatter inlined — enough to tell whether one of them already covers this topic without opening anything. If one does, read that file and resume it. Otherwise name a new file with about three slug words for the subject.

Frontmatter, every file, these four fields only:

```yaml
---
topic: one line naming the subject, fuller than the filename slug
user-topic: |
  $ARGUMENTS
started: !`date -Is`
status: open
---
```

`user-topic` is the opening ask, verbatim, in the user's own words. Never reword it, never correct it, and never revise it on resume. It is the one field you did not write, and its worth to the user a year on is that it is unedited. Keep it a block scalar so punctuation in the raw text cannot break the frontmatter.

`started` arrives already filled and belongs to the file that is being created; on resume it stays whatever it was. Recency comes from the file itself, so there is no updated field to fall out of step. `status` becomes `settled` when a solution is chosen, and stays `open` otherwise, including when the discussion simply stops.
