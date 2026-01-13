---
name: friction
description: Document friction between Claude's behavior and user conventions for future context injection
argument-hint: "[reason]"
allowed-tools: Read, Write, Glob, Grep, ExitPlanMode, Skill
context: fork
---
# Friction Documentation

Capture friction points for the curated library. Use the `friction-management` skill for formatting guidance.

## Process

1. **Analyze Context**
   - Review recent conversation for friction points
   - Consider user reason: $ARGUMENTS
   - Identify patterns, not specific instances

2. **Invoke Friction Management Skill**
   - Use Skill tool to access formatting guidance
   - Follow domain file format and tag conventions
   - See skill for examples of good vs bad documentation

3. **Create Plan**
   - Enter plan mode for user review
   - Write concise bullets with tags in [brackets]
   - Multiple frictions = multiple bullets
   - Tags: [language, domain, library, operation]

4. **Exit & Ingest**
   - Call ExitPlanMode
   - After approval, call friction-ingest agent with plan file location
