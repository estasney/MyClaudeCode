---
name: read-handoff
description: Resume work from a handoff note without rediscovering the codebase. Manual; invoke with /read-handoff.
argument-hint: [optional filename fragment or keyword]
allowed-tools: Bash, Read, Grep
disable-model-invocation: true
---

Resume the work a handoff describes.

!`"${CLAUDE_PLUGIN_ROOT}/scripts/handoff-dir.sh" "${CLAUDE_PLUGIN_DATA}" "${CLAUDE_PROJECT_DIR}"`

The first line is the handoff directory; the rest are existing handoffs, newest first.

<optional_user_argument>
`$ARGUMENTS`
</optional_user_argument>

If it is empty, read the newest file. Otherwise grep the handoff files for it; if several match, list them and ask which to load.
Read the chosen file and name it, so the user knows which one loaded.
Then open what it lists under where the work sits, reading the named symbols. The note is a description of that code and may be behind it.
Go no further. Take the conventions as given rather than checking them. Open what it lists under where to look only if a convention it states is unclear.

Handoffs may describe outstanding items. Some examples of how to address these:

H: "Nothing has been committed"
A: The user is solely responsible for this. Disregard.

H: "There is an unused import in File X"
A: Trivial, and easily found with linters. Disregard. 

H: "The scratchpad has a file called test_script.py"
A: Scratchpad is ephemeral. Disregard.

H: "The README has not been updated to reflect X"
A: Low priority. A "wrapping up" item. If code is still changing do not mention.

H: "DB migration 0001 is not applied"
A: Unless the codebase has no method to track migrations (unlikely), disregard.

H: "The user has not ruled on whether to suppress type error X"
A: Disregard. The user's prerogative.

H: "The user expressed that the next session should refactor X as Y"
A: High Priority. Mention and confirm

Finally...

Mention any high priority items. If you detect none, just confirm you've read and understood