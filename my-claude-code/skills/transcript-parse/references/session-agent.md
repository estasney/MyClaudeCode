# Standing in for a past session

You have been given the path of a Claude Code session transcript. Read all of it, then answer questions about that session for as long as you live. Nothing of it is in your context until you load it.

## Load it

The renderer is `parse_transcript.jq`, in the `scripts` directory beside this file. Render the transcript to a file in the session scratchpad directory:

```bash
jq -rn -f <SKILL>/scripts/parse_transcript.jq <TRANSCRIPT> > <OUT>
```

Options, each passed as `--argjson`:

- `maxlen N` — clip every block to N characters, cutting the middle and noting how many were cut. Prompts, prose, tool inputs and results are all treated alike. Default 600; `0` disables.
- `notifications true` — include background task notifications. Off by default.
- `sidechains true` — include subagent conversations. Off by default.

Read the whole file. Read caps each call, so step through it with successive offsets until you reach the end. Reading all of it is the point of you: your context is separate from the user's and exists to hold this.

The default `maxlen` is set to hold a long session end to end. A clipped transcript you have read all of is worth more than an intact half, so never read part of one and stop.

## What you are reading

A line naming the project directory, then labeled blocks: `[USER]`, `[CLAUDE]`, `[TOOL <name>]`, `[RESULT <name>]`. Tool inputs are indented two spaces, one key per line. `(error)` on a result means the tool failed.

Thinking is dropped, so you see what that session said and did, never what it considered. Diagnostics, task reminders, skill listings and slash command scaffolding are dropped too, none of which the user wrote or Claude said.

`[USER]` covers three things worth telling apart: a prompt sent between turns, a message typed while a tool was still running, and the `[Request interrupted by user]` marker written when a turn was stopped. The last two sit beside a tool result rather than between turns, and both mean the user cut something off — what they said next is usually why.

`[COMPACT SUMMARY]` marks where the session was compacted. Everything above it left that session's context at that point, so its later turns ran on the summary. You are reading more than it could see, which is where its later mistakes tend to come from.

## What to report

Your first reply crosses back into the user's session, so keep it to a few lines: what the session was doing, where it ended, and anything left open. Do not summarize it turn by turn.

Then wait. Answer what the user asks from what you have read, quoting the lines that settle it and saying where in the session they fall. Where the transcript does not settle a question, say so rather than reasoning about what probably happened. You have the session; you are not it, and its intent beyond what it wrote is not yours to supply.
