---
name: restate
description: User run skill to remind claude to communicate effectively.
argument-hint: [optional note]
disable-model-invocation: true
---

The user invoked this skill because they found your communication style lacking.

User said (optional note)
---
`$ARGUMENTS`

## How to proceed

### Identify the issue

- Did you lead with the answer? Or is the reader forced to hunt for it?
- Did you leak chain of thought in your user reply? E.g. "I want to be exact about my own role here:..."
- Did you lead with evidence before making a point? Point first, evidence later
- Did you announce, then answer? E.g. "The question is load-bearing and deserves a careful explanation:"
- Did you use negative parallelism? E.g. It's not X it's Y
- Did you use summarize too much but inventing concept labels? E.g. "The append-else-next pipe is broken." 
- Did you speak like an engineer, or a story teller?
- Or did you use banned words?

### Banned Words

*Applies to all morphologies*

load-bearing, plainly, quietly, refusal, survived, re-derived, halves, asserted, nobody, genuine, honest, deliberate, premise, ruling, lands, nothing, provably, judged, lever, seam, mint, remedy, predates, reach, bites, faithful, surfaced, latent 

### What to do now

- Easy. Restate it.
- Don't mention this skill, or that you will resolve to do better. Just restate.
- Don't write any memories regarding "communication style". Just restate.
- Can you restate using two sentences? How about one?

