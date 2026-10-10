---
name: locate
description: Find the file line ranges that answer a question about code when you don't know where the answer is, keeping the search out of your context. Argument is the question and the repo path.
argument-hint: <question> <repo path>
context: fork
agent: my-claude-code:source-locator
background: false
---

$ARGUMENTS
