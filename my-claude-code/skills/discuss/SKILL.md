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

Your first move is to create the file, before replying and before reading anything. Only the raw ask, the timestamp and the status are knowable at that point, so those are all you write. `topic` stays empty; it is a conclusion, and you do not have one yet.

Your second move is to reply, saying back what you take the subject and the concern to be, and to get that confirmed. A topic line is a pointer, not a shared understanding. The user knows what they meant; you are guessing.

Only once the subject is agreed do you fill in `topic` and go read whatever it refers to. Gathering context against a guessed subject wastes the effort and, worse, settles you into the wrong reading before anyone has checked it.

Record the corrections this draws, not the confirmations. Being told you had the subject wrong is worth keeping; being told you had it right is not.

You are a participant and the scribe at once. As participant, think freely. As scribe, record only what has actually passed between the two of you: an idea becomes an entry when it is said, not when it is had. Your own reasoning is not minutes until the user has heard it.

Attribute every entry to `User:` or `Claude:`. That is the mechanism, not a formality — an unvoiced idea has no speaker to label, so it cannot be written down.

Keep minutes as the discussion moves, not only at the end, since a discussion rarely announces that it is over. Minutes, not a transcript: questions raised, objections made, solutions put to the other party, solution chosen. These are the kinds of entry worth making, not sections waiting to be filled. A discussion that has produced no solutions records none, and a new file starts empty, save for the frontmatter and structure.

Record only what stays true. No file names, line numbers, counts, or other details that drift out of date. Name the concept rather than its current shape. The reader is the user, a year from now, and the minutes have to still make sense to them. This governs how an entry is phrased, never whether it is made: compress what was said, do not improve it or leave it out.

### Where

!`"${CLAUDE_PLUGIN_ROOT}/scripts/discussion-dir.sh" "${CLAUDE_PROJECT_DIR}"`

First line is the directory. The rest are the existing discussions, newest first, each with its frontmatter inlined — enough to tell whether one of them already covers this topic without opening anything. If one does, read that file and resume it. Otherwise name a new file with about three slug words for the subject.

Frontmatter, every file, these four fields only:

```yaml
---
topic:
user-topic: |
  $ARGUMENTS
started: !`date -Is`
status: open
---
```

`topic` is left blank at creation and filled once the subject is agreed: one line naming it, fuller than the filename slug. The filename itself comes from the raw ask, so it is not a guess in the way `topic` would be; rename it only if the agreed subject turns out to be something else.

`user-topic` is the opening ask, verbatim, in the user's own words. Never reword it, never correct it, and never revise it on resume. It is the one field you did not write, and its worth to the user a year on is that it is unedited. Keep it a block scalar so punctuation in the raw text cannot break the frontmatter.

`started` arrives already filled and belongs to the file that is being created; on resume it stays whatever it was. Recency comes from the file itself, so there is no updated field to fall out of step. `status` becomes `settled` when a solution is chosen, and stays `open` otherwise, including when the discussion simply stops.
