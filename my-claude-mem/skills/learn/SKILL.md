---
name: learn
description: Prompt Claude to learn
argument-hint: [additional context]
disable-model-invocation: true
---
The user is asking that you learn from the corrections they made in this session. A lesson is a point where your default and the user's norm differed. Draft one entry per lesson, with three fields. A new session reads each entry with no other context.

**Norm**: What the user expects, in words that hold beyond this incident.
**Default**: What you did before the user corrected it.
**Context**: The situation, in the words a later search would use.

Show one draft at a time. On approval, store it with the `add_entries` tool, in the `${user_config.lessons_space}` space unless the user specifies another, then show the next draft. The user may edit sections by name or number, or skip a draft.

If the space does not exist, download the `${user_config.embedding_repo_id}` model with the `download_embedding_model` tool. Then create the space with the `create_space` tool, that model as embedding_repo_id, and a readme that describes the lesson format.

Any text below narrows what to learn or names a different space.

---
`$ARGUMENTS`
---
