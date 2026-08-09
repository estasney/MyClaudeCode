---
name: transcript-parse
description: Load a past Claude Code session into an agent that has read all of it, then put questions to it. Manual; invoke with /transcript-parse.
argument-hint: [optional keyword, session id, or project name]
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/list-transcripts.sh:*) Bash(ls:*) Bash(jq:*) Read Grep
disable-model-invocation: true
---

Hand a past session's transcript to an agent that reads all of it, then relay questions to that agent.

You pick the transcript and confirm it. The agent cannot ask anything once it starts, so an unconfirmed guess costs a whole reload.

### Which transcript?

Transcripts live in `~/.claude/projects/<slug>/<session-id>.jsonl`, one directory per project. The slug is the project's absolute path with its separators flattened into dashes, and a session started in a subdirectory is filed under that subdirectory rather than under the project root. Session ids say nothing about their contents, so one call lists them newest first with the time each was last active, its size, and the title Claude Code gave the session:

```bash
"${CLAUDE_SKILL_DIR}/scripts/list-transcripts.sh" "${CLAUDE_PROJECT_DIR}" "${CLAUDE_SESSION_ID}"
```

That is one ordinary Bash call. `~/.claude/projects` sits outside the working directories, so it raises a permission prompt the user can approve, once, for the whole listing. Do not move it into a `!` injection: an injected command runs before the skill reaches the session, where the same prompt has nobody to approve it and the command fails outright. `allowed-tools` does not open that gate either — the working directory scope is a separate one.

The first argument is matched against the listing rather than used to build a directory name, so a bare project name works too when the question is about another project. Where nothing matches, the script prints the projects that do have transcripts.

<optional_user_argument>
`$ARGUMENTS`
</optional_user_argument>

If it is empty, the newest transcript for this project is the candidate. Otherwise read it as a project name, a session id, or a keyword to match against the titles the listing prints.

Put the candidates to the user with their titles and when each ran, most likely first. Confirm before spawning anything, even when only one matches. Where nothing matches, say so and stop.

### Spawn the agent

Spawn one general-purpose agent. Give it the absolute path of the confirmed transcript, and tell it to read `${CLAUDE_SKILL_DIR}/references/session-agent.md` and follow it. Nothing else — the brief carries the rest, and repeating it here would let the two drift apart.

### After it reports

Relay what it says. It holds the transcript; you do not, and rendering the transcript into your own context would spend on one question what the agent is holding for all of them.

Put the user's follow-up questions to it with `SendMessage` rather than answering from what it has already told you. It read the session and you read a few lines about it.
