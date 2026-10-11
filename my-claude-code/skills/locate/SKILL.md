---
name: locate
description: Use instead of Grep or Glob to find where code is defined, used, or explained. Takes a question and a repo path, returns the file paths and line ranges that answer it.
argument-hint: <question> <repo path>
context: fork
agent: my-claude-code:source-locator
background: false
---

$ARGUMENTS
