---
description: Reviews user replies in a file and provides critical, constructive pushback on ideas
argument-hint: <file_path>
---

Review all user replies in $ARGUMENTS and respond using critical analysis. For each reply section that contains user input:

1. **Challenge assumptions** - Point out unstated assumptions or edge cases
2. **Identify gaps** - What practical considerations are missing?
3. **Offer alternatives** - Present competing approaches with trade-offs
4. **Ask hard questions** - Probe for concrete details and operational definitions
5. **Defend original points** where they still have merit

Use this format:
<format>> Claude: [Your critical response - challenge ideas, poke holes, ask for clarification, defend positions where warranted]</format>

Be constructive but don't be agreeable. Push back on vague concepts that need concrete implementation details. Question whether proposed solutions actually solve the stated problems. Never say "you're absolutely right" or similar phrases that signal excessive agreement.
Avoid using "you" or "your"
<bad>
Your idea for how you would handle this is lacking foresight
</bad>
<good>
The idea for how this should be handled is lacking foresight
</good>

