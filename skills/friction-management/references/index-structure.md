# Index Structure

The friction index (`assets/friction-index.md`) maps tags to domain files for quick discovery.

## Format

```markdown
# Friction Point Index

Tag-based index mapping tags to friction point files.

---

## {Language}

**{Domain}**: `{path}` - Tags: tag1, tag2, tag3

## {Category}

**{Domain}**: `{path}` - Tags: tag1, tag2
```

## Example

```markdown
# Friction Point Index

---

## Python

**Typing**: `python/typing.md` - Tags: python, typing, pep585, generics
**I/O**: `python/io.md` - Tags: python, io, pathlib, filesystem
**Pydantic v2**: `python/pydantic/v2.md` - Tags: python, pydantic, v2, validation

## JavaScript

**React Hooks**: `javascript/react/hooks.md` - Tags: javascript, react, hooks, useeffect

## General

**Git**: `general/git.md` - Tags: git, workflow, commits
```

## Maintenance

- Add entry when creating new domain file
- Append tags as new friction points added
- Keep tags slug-formatted and deduplicated
- Group by top-level language/category
