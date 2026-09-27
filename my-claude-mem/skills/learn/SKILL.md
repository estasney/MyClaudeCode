---
name: learn
description: Prompt Claude to learn
argument-hint: [additional context]
disable-model-invocation: true
---
The user is asking that you learn from your recent interactions with them. Each lesson is one entry. Draft one note per lesson, with three fields. Each entry must make sense to a reader who has not seen this session or the other entries.

**Context**: Sufficient detail that a future reader understands what occurred.
**Behavior**: The preference or rejection the user showed.
**Conclusion**: What Claude should do in the future.

Show one draft at a time. On approval, store it with the `add_entries` tool, in the `${user_config.lessons_space}` space unless the user specifies another, then show the next draft. The user may edit sections by name or number, or skip a draft.

If the space does not exist, download the `${user_config.embedding_repo_id}` model with the `download_embedding_model` tool. Then create the space with the `create_space` tool, that model as embedding_repo_id, and a readme that describes the lesson format.

Any text below narrows what to learn or names a different space.

---
`$ARGUMENTS`
---
