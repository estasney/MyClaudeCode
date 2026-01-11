# Hook Implementation Examples

## Example 1: Security Gate (PreToolUse)

**Script**: `scripts/security-check.sh`

```bash
#!/bin/bash

# Read hook input from stdin
read -r hook_input

tool_name=$(echo "$hook_input" | jq -r '.tool_name')
tool_input=$(echo "$hook_input" | jq -r '.tool_input')

# Block dangerous bash commands
dangerous_patterns=(
  "rm -rf /"
  "dd if="
  "fork()"
  ":(){:|:&};"
  ">/dev/sd"
)

command=$(echo "$tool_input" | jq -r '.command // empty')

for pattern in "${dangerous_patterns[@]}"; do
  if [[ "$command" == *"$pattern"* ]]; then
    echo "Blocked dangerous command" >&2
    exit 2
  fi
done

exit 0
```

**Config**:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "./scripts/security-check.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

## Example 2: Auto-Formatting (PostToolUse)

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "cd ${CLAUDE_PROJECT_DIR} && black . && ruff check --fix .",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

## Example 3: Intelligent Skill Suggestion (UserPromptSubmit)

**Script**: `scripts/skill-matcher.js`

```javascript
const fs = require('fs');
const path = require('path');

let hookInput = '';
process.stdin.on('data', chunk => hookInput += chunk);
process.stdin.on('end', () => {
  const input = JSON.parse(hookInput);
  const projectDir = input.session_data.project_path;
  
  // Read all SKILL.md files
  const skillsDir = path.join(projectDir, '.claude', 'skills');
  const skills = fs.readdirSync(skillsDir)
    .filter(f => fs.statSync(path.join(skillsDir, f)).isDirectory())
    .map(dir => {
      const skillMd = path.join(skillsDir, dir, 'SKILL.md');
      const content = fs.readFileSync(skillMd, 'utf8');
      const match = content.match(/description:\s*([^\n]+)/);
      return {
        name: dir,
        description: match ? match[1] : ''
      };
    });

  // Score skills based on prompt keywords
  const userPrompt = input.user_input.toLowerCase();
  const scores = skills.map(skill => ({
    skill: skill.name,
    score: (skill.description.toLowerCase().split(' ')
      .filter(word => userPrompt.includes(word))
      .length)
  })).filter(s => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 3);

  if (scores.length > 0) {
    console.log(JSON.stringify({
      suggested_skills: scores.map(s => s.skill),
      confidence: 'high'
    }));
  }
  process.exit(0);
});
```

## Example 4: Component-Scoped Hooks in SKILL.md

```yaml
---
name: testing-patterns
description: pytest and unittest patterns, fixtures, parametrization, mocking
hooks:
  PostToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "cd ${CLAUDE_PROJECT_DIR} && pytest --tb=short tests/"
          timeout: 120
---
```

# Agent Implementation Examples

## Example 1: Code Review Agent

```yaml
---
name: code-reviewer
description: Expert code review specialist. Analyzes recent changes for quality, security, performance, and maintainability.
allowed-tools: Read, Grep, Glob, Bash
---

# Code Review Agent

You are a senior code reviewer with expertise in Python, TypeScript, and system design.

## When Invoked

1. Check recent changes: `git diff --name-only HEAD~1`
2. For each changed file:
   - Read the full file context
   - Focus on: type safety, error handling, security, performance
   - Compare against established patterns in the codebase

## Review Checklist

- [ ] Type annotations complete (Python 3.12+ style)
- [ ] Error handling: no bare `except`, proper context
- [ ] Security: no SQL injection, XSS, credential exposure
- [ ] Performance: no N+1 queries, proper caching
- [ ] Testing: changes have test coverage
- [ ] Documentation: docstrings for new functions

## Output Format

Provide scores (1-5) for each category:

```
FILE: src/app.py
Type Safety: 4/5 - Missing return type on handler()
Error Handling: 3/5 - Catch blocks too broad
Security: 5/5 - Input validation solid
Performance: 4/5 - Consider batch operations in line 42
```
```

## Example 2: Documentation Sync Agent

```yaml
---
name: docs-sync
description: Synchronizes code changes with project documentation, keeping README and API docs current.
allowed-tools: Read, Write, Grep, Bash, Glob
---

# Documentation Sync Agent

You update project documentation to reflect recent code changes.

## Workflow

1. List recent commits: `git log --oneline -n 20`
2. Identify documentation files: README.md, docs/, API docs
3. Find code changes that need doc updates:
   - New public APIs
   - Behavior changes
   - Configuration changes
   - Breaking changes

4. Update docs with:
   - New function signatures
   - Usage examples
   - Deprecation notices
   - Migration guides

## Output

Update `docs/CHANGELOG.md` with summary of documentation changes.
```

# Slash Command Examples

## Example 1: Multi-Source Research

```yaml
---
name: research
description: Conduct thorough research using web search, documentation, and codebase exploration in parallel. Returns comprehensive findings in research document.
allowed-tools: Task, WebSearch, WebFetch, Grep, Glob, Read, Write
---

# Research: $ARGUMENTS

## Problem

$ARGUMENTS

## Research Strategy

Spawn parallel research agents:

1. **Web Research Agent** - Search current best practices, tutorials
2. **Documentation Agent** - Official docs, patterns, examples
3. **Codebase Agent** - Repository examples, existing patterns

Wait for all agents to complete, then synthesize findings into `docs/research/$QUERY.md` with:
- Problem context
- Key findings per source
- Recommended approach
- Trade-offs
- Open questions
```

## Example 2: Infrastructure Audit

```yaml
---
name: infra-audit
description: Comprehensive infrastructure review covering security, performance, cost, and reliability. Identifies misconfigurations and optimization opportunities.
allowed-tools: Task, Bash, Grep, Glob, Read
---

# Infrastructure Audit

Perform complete infrastructure audit:

**Security Check**
- Review IAM policies, VPC rules, secrets management
- Check for exposed credentials, public S3 buckets
- Output: `reports/security-findings.md`

**Performance Audit**
- Database query analysis, connection pooling
- Cache hit rates, CDN effectiveness
- Output: `reports/performance-findings.md`

**Cost Optimization**
- Identify unused resources
- Reserved instance opportunities
- Output: `reports/cost-optimization.md`

**Reliability Review**
- Backup verification
- Failover testing
- Output: `reports/reliability-findings.md`

## Final Report

Consolidate all findings into `reports/infra-audit-summary.md`.
```
