---
allowed-tools: mcp__chroma
argument-hint: focus [what to query]
description: Read conversation context from handoff collection for agent onboarding
model: global.anthropic.claude-haiku-4-5-20251001-v1:0
---

# Chroma Read Handoff Command

You should retrieve conversation context from the "handoff" collection to understand recent work and continue seamlessly.

If the mcp tool is not available, retry - it is likely starting up. If it is still not available stop and ask the user if you should retry.

Do not read or write any files. Only retrieve from chroma

## Collection Access
- Verify "handoff" collection exists
- Get collection information and document count

## Context Retrieval Strategy

<optional-query>$ARGUMENTS</optional-query>

<important>NEVER include embeddings or distances in your chroma queries. These quickly fill up context</important>

### If query provided
- Use semantic search with the provided query text
- Return relevant documents matching the query
- Limit results to most relevant matches (10 documents)

### If no query provided
- Retrieve all documents from the handoff collection
- Present organized overview of conversation context
- Group information by topic (recent work, technical focus, next steps, etc.)

## Information Processing
- Present retrieved context in organized, readable format
- Highlight key decisions and patterns from recent conversation
- Summarize what was accomplished and current state
- Identify specific implementations and files created/modified
- Note any blockers or important insights discovered

## Output Format
- Start with conversation summary and recent accomplishments
- Organize by conversation topics and technical areas covered
- Use clear headings and bullet points
- Emphasize actionable next steps for continuing work
- Include document IDs for reference if needed

## Error Handling
- Check if handoff collection exists before querying
- Handle empty collections gracefully
- Provide clear messages if no relevant documents found
- Suggest alternative queries if initial search yields poor results

