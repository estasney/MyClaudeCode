---
name: read-handoff
description: Read a handoff note from the plugin's per-project handoff store. Manual; invoke with /read-handoff.
argument-hint: [optional filename fragment or keyword]
allowed-tools: Bash, Read
disable-model-invocation: true
---

Read handoff note(s) for this project.

!`"${CLAUDE_PLUGIN_ROOT}/scripts/handoff-dir.sh" "${CLAUDE_PLUGIN_DATA}" "${CLAUDE_PROJECT_DIR}"`

The first line is the handoff directory; the rest are existing handoffs, newest first.

<optional_user_argument>
`$ARGUMENTS`
</optional_user_argument>

If it's empty, read the newest file (top of the list). Otherwise grep the handoff files for it; if several match, list them and ask which to load.

Read the chosen file — name it, so the user knows which loaded. Recite its values, then state what they mean to you. If the handoff named a next move, offer to pick it up; otherwise ask what's next.
