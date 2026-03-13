---
name: friction
description: Document friction between Claude's behavior and user conventions for future context injection
argument-hint: "[reason]"
allowed-tools: Read, Write, Glob, Grep, ExitPlanMode, Skill, Bash(~/.claude/skills/friction-management)
---
# Friction Documentation

Capture friction points for the curated domain, language, library or operation. Use the `friction-management` skill for this task.

## Process

1. **Analyze Context**
   - Review recent conversation for friction points
   - Consider user reason: $ARGUMENTS

2. **Invoke Friction Management Skill**
   - Use Skill tool to access formatting guidance
   - Follow domain file format and tag conventions
   - See skill for examples of good vs bad documentation

3. **Prepare Initial Suggestions**
   - Determine if a new file is needed or if one or more existing files can be updated. Remember these.
   - Consider what tags are appropriate for each friction point.
   - Think of how to express the friction point with varying degrees of specificity.

4. **Interactive Drafting**
   - Important: use this AskUserQuestion tool for this process. Each friction point should be self-contained. This may require multiple iterations.
   - Important: Always include a field for direct user input.
   - Ask for File: If a new file is needed, suggest a file path and name. Otherwise, reference existing files. If you have a recommendation, indicate it in the suggestion.
   - Ask for Tags: Multiple choice selection of tags for the friction point. Include an option for user-defined tags. Treat this user input as comma-delimited.
   - Ask for Friction Point: Provide a multiple choice list of 2-5 suggested friction point descriptions based on the context and reason. Include an option for user-defined description. Ensure these cover a spectrum of specificity from general to specific.
   - Continue to loop over this process until all friction points are captured and approved by the user.

5. **Exit & Handoff**
   - After approval, call friction-ingest and explicitly pass the path(s) of the file(s) to be updated/created along with the friction points, verbatim.
