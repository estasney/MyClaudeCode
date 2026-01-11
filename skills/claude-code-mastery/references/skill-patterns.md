# Skill Patterns

## Skill Structure

```
my-skill/
├── SKILL.md              # Required: frontmatter + core instructions
├── references/           # Detailed docs (loaded on demand)
│   ├── schemas.md
│   ├── patterns.md
│   └── api-reference.md
├── scripts/              # Reusable code (Python/Bash/etc.)
│   ├── validate.py
│   └── transform.sh
└── assets/               # Files used in output (templates, etc.)
    ├── template.jsx
    └── styles.css
```

## Progressive Disclosure Pattern

Keep SKILL.md lean—move details to `references/` subdirectory.

**Good approach**:
- SKILL.md: Quick overview + core workflow
- references/: Full schemas, examples, detailed patterns

**Bad approach**:
- SKILL.md: 50 KB with every detail inline

### Example: SQLAlchemy Skill

**`SKILL.md`**:

```yaml
---
name: sqlalchemy-orm
description: SQLAlchemy ORM patterns—async queries, session management, custom types, transactions in Python 3.12+
---

# SQLAlchemy ORM

Use this for ORM queries, session management, and type-safe patterns.

## Quick Reference: Async Sessions

[See references/async-sessions.md for full patterns]

```python
async with AsyncSession(engine) as session:
    result = await session.execute(select(User).where(User.id == 1))
    user = result.scalar_one_or_none()
    await session.commit()
```

## Session Lifecycle

1. Create engine: `create_async_engine(url, echo=False)`
2. Get session: `async with AsyncSession(engine) as session`
3. Execute: `await session.execute(select(Model))`
4. Commit: `await session.commit()`

## Common Gotchas

- Sessions aren't thread-safe
- Always await async calls
- Use selectinload() for relationship eager loading

[See references/gotchas.md for detailed examples]
```

**`references/async-sessions.md`**:
```markdown
# Async Sessions: Complete Patterns

## Connection Pool Setup

[Full patterns with connection string examples, configuration options, etc.]

## Session Lifecycle Detail

[Complete walkthrough with error handling examples]

## Best Practices

[Detailed best practices with trade-offs]
```

## When to Use Each Directory

### `references/`

Loaded as needed. Include:
- Database schemas
- API specifications
- Detailed patterns
- Configuration examples
- Complete examples
- Reference documentation

**Use when**: Information is >5 KB or detailed reference material.

### `scripts/`

Reusable code executed by Claude or hooks. Include:
- Validation logic
- Data transformations
- Common procedures
- Build scripts

**Use when**: Code is repeated frequently or needs deterministic reliability.

### `assets/`

Files used in generated output. Include:
- HTML/React templates
- CSS stylesheets
- Boilerplate code
- Images, fonts

**Use when**: File gets copied or embedded in user output.

## Example: Testing Skill

**`SKILL.md`**:

```yaml
---
name: testing-patterns
description: pytest fixtures, parametrization, mocking, test organization. Async testing patterns.
hooks:
  PostToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "pytest tests/ --tb=short"
---

# Testing Patterns

Use this for pytest-related work.

## Fixtures

[See references/fixtures.md for complete fixture patterns]

Basic pattern:

```python
@pytest.fixture
def user():
    return User(name="Test")

def test_user(user):
    assert user.name == "Test"
```

## Parametrization

[See references/parametrization.md for advanced patterns]

Quick example:

```python
@pytest.mark.parametrize("input,expected", [
    (2, 4),
    (3, 9),
])
def test_square(input, expected):
    assert square(input) == expected
```

## Mocking

[See references/mocking.md for complete mocking guide]

## Test Organization

Tests go in `tests/` directory with structure matching `src/`.
```

**`references/fixtures.md`**: 50+ lines on fixture patterns, scopes, dependencies, etc.

**`scripts/validate-test-structure.py`**: Script to validate test directory structure.

## Key Principle

The description field triggers auto-discovery. Make it specific so Claude knows when to apply the skill.

**Good**:
```yaml
description: pytest fixtures, parametrization, mocking, and async test patterns
```

**Poor**:
```yaml
description: A skill for testing
```
