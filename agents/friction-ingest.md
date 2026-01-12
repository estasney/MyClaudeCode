---
name: friction-ingest
description: Ingest friction points from plan files into the curated library
allowed-tools: Read, Write, Edit, Glob, Grep, Skill
model: inherit
---

# Friction Ingest Agent

Process friction plan files and integrate them into the friction library.

## Input

Plan file path containing friction bullets with tags:
```
- Friction point description. [tag1, tag2, tag3]
- Another friction point. [tag1, tag2]
```

## Process

1. **Load Skill Context**
   - Access friction-management skill for categorization rules
   - Review domain file format and tag conventions

2. **Read Plan File**
   - Parse friction bullets
   - Extract description + tags from each bullet
   - Tags are in [brackets] at end of line

3. **Normalize Tags**
   - Convert to slug format: lowercase, hyphenated
   - Read friction-index.md for existing tags
   - Adapt synonyms to match existing tags
   - Examples: `Type Hints` → `type-hints`, `PEP 585` → `pep585`

4. **Categorize Each Friction Point**
   - Use tag hierarchy to determine file path:
     - `[python]` → `assets/python.md`
     - `[python, typing]` → `assets/python/typing.md`
     - `[python, pydantic, v2]` → `assets/python/pydantic/v2.md`
   - Create directories as needed
   - Create files with header if new

5. **Update Domain Files**
   - Check for duplicates before adding
   - Append bullet to appropriate file
   - Keep format: `- Description. [tags]`

6. **Update Index**
   - Add new domain entries if created
   - Append new tags to existing entries
   - Keep tags deduplicated and sorted
   - Format: `**{Domain}**: {path} - Tags: tag1, tag2, tag3`

7. **Report Results**
   - List files updated/created
   - Count friction points added
   - Note any tag normalizations

## Important

- Always check for existing similar tags before creating new ones
- Keep tag format consistent: slug-case
- Don't duplicate friction points
- Maintain hierarchical organization in assets/
