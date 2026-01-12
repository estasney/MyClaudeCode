---
argument-hint: <topic>
description: Start or resume a discussion about the specified topic
---

## Discuss Command

### Purpose
Start or resume a discussion about the specified topic: **$ARGUMENTS**

### Workflow
You should:
1. Use the topic from **$ARGUMENTS** to identify the discussion
2. Check if a discussion already exists in the `.claude/discussions/` directory by searching for files containing the topic
3. If no existing discussion is found:
   - Generate a descriptive slug from **$ARGUMENTS** (lowercase, hyphen-separated)
   - Create a new markdown file in `.claude/discussions/` 
   - Use the filename format: `{YYYY-MM-DD}-{slug}.md`
   - Initialize with discussion template

4. If resuming an existing discussion:
   - Open the most recent file related to the topic from **$ARGUMENTS**
   - Append new discussion points with current timestamp
   - Update status and action items

### Discussion File Structure
Each discussion file should contain:
- **Topic**: Clear title based on **$ARGUMENTS**
- **Date Started**: Initial creation date
- **Last Updated**: Most recent modification
- **Key Points**: Bullet points of main discussion items
- **Decisions Made**: Concrete outcomes and choices
- **Action Items**: Tasks to be completed
- **Status**: Open/Resolved/Ongoing

### Tracking Guidelines
- Keep entries concise and focused on outcomes
- Use bullet points for clarity
- Avoid verbatim transcripts
- Focus on actionable insights and decisions
- Update existing discussions rather than creating duplicates

### Example Usage
```
# Start discussing project architecture
$ claude discuss "project architecture refactoring"

# Resume database optimization discussion
$ claude discuss "database performance"
```

### Command Flow

This is an interactive discussion! Primarily, this is a conversation. Continue offering alternative view points where applicable. Ultimately when the discussion ends update the discussion file with the reached decision.
Ultimately, it is my decision to make, do not represent that a decision has been made unless I indicate it.