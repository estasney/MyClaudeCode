---
name: slow-steady
description: Announce each edit, then act.
disable-model-invocation: true
---
The user has invoked slow-steady mode.

These rules hold for every file change from now until the session ends or the user asks you to exit slow-steady mode.

Before each Write or Edit, say in one sentence what the edit does and which step it enables next.

Make one edit per tool call, each after its own sentence. Do not batch edits in parallel.

Keep going until the change is complete. Do not pause to ask whether to continue. The user stops you by message, by interrupting, or by rejecting an edit.

Size each edit by how likely the user is to reject it. Where rejection seems likely, keep the diff small so a rejection costs little. Otherwise prefer fewer, larger edits, since every step costs tokens.

When the user rejects an edit with a reason, revise that step to address it and continue. When the user rejects an edit without a reason, ask why before going further.
