---
name: learn
description: Prompt Claude to learn
argument-hint: [additional context]
disable_model_invocation: true
---
The user is asking that you learn from your recent interactions with them. Each lesson is one memory. Draft one note per lesson, with three fields.

**Context**: Sufficient detail that a future reader understands what occurred.
**Behavior**: The preference or rejection the user showed.
**Conclusion**: What Claude should do in the future.

Show one draft at a time. On approval, store it with the `remember` tool, in the default memory space unless the user specifies another, then show the next draft. The user may edit sections by name or number, or skip a draft.

Any text below narrows what to learn or names a different memory space.

---
`$ARGUMENTS`
---
