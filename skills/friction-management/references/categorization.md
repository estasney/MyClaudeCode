# Categorization Rules

## Directory Structure

Organize friction points hierarchically by specificity:

```
assets/
├── friction-index.md
├── {language}.md              # Top-level language frictions
├── {language}/
│   ├── {topic}.md             # Language-specific topic
│   └── {library}/
│       ├── {subtopic}.md      # Library-specific (e.g., pydantic/v1.md, pydantic/v2.md)
└── general/
    └── {tool}.md              # Language-agnostic (git, docker, etc.)
```

## Categorization Logic

Use tags to determine file location from most general to most specific:

1. **Top-level language**: `[python]` → `python.md`
2. **Language + topic**: `[python, typing]` → `python/typing.md`
3. **Language + library**: `[python, pandas]` → `python/pandas.md`
4. **Library + version/subtopic**: `[python, pydantic, v2]` → `python/pydantic/v2.md`

### Examples

- `[python, typing, pep585]` → `python/typing.md`
- `[python, pandas]` → `python/pandas.md`
- `[python, pydantic, v2, models]` → `python/pydantic/v2.md` (models stays in tags)
- `[javascript, react, hooks]` → `javascript/react/hooks.md`
- `[git, workflow]` → `general/git.md`

## When to Nest Deeper

Nest when there are **significant API/behavior differences**:
- Library versions (pydantic v1 vs v2, sqlalchemy 1.x vs 2.x)
- Major subsystems (sqlalchemy/orm vs sqlalchemy/core)

**Don't** nest for minor topics - keep them as tags within the parent file.

## Creating New Files

1. Determine specificity from tags
2. Create directory if needed
3. Add markdown file with brief header
4. Update friction-index.md
