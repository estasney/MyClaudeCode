---
allowed-tools: mcp__chroma
argument-hint: focus [optional, what to focus on]
description: Create handoff collection with current conversation context and recent work
---

# Handoff Command

Your task is to capture and condense the current conversation's context. This is to allow for a new session to start in a seamless manner.

The user had the option to provide additional guidance. 

<optional-guidance>
$ARGUMENTS
</optional-guidance>

The optional-guidance may be blank.

## Before Start
- Delete existing "handoff" collection. If not found, ignore this error.
- Create new "handoff" collection with default embedding function.

## Conversation Context to Capture

### Codebase
- Project Structure and layout. Locations of important modules.
- Frameworks, if any
- Programming patterns and conventions implicitly understood
- Programming patterns and conventions explicitly stated by the user, if any

### Current Work Session
- What we accomplished in this conversation
- Key decisions made and architectural choices
- Specific implementations completed
- Files created or modified during this session

### Current State and Next Steps
- Where we left off in the work
- Pending tasks or next logical steps explicitly agreed to by user, if any
- Any blockers or issues identified

### Key Insights and Learnings
- Important discoveries or realizations from this session
- Best practices established

### Context for Continuation
- What a new agent would need to know to pick up where we left off
- Important background context from earlier in conversation
- Relevant examples or patterns established
- Current project phase or milestone

## Storage Strategy
- Store conversation highlights as searchable documents
- Include specific examples and code patterns discussed
- Use clear document IDs reflecting conversation topics
- Focus on actionable context for continuation

## Completion Requirements
- Capture essence of current conversation and work
- Ensure new agent can continue seamlessly
- Include specific technical details discussed
- Verify collection creation and document storage