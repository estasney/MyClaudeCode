# Domain File Format

Domain files are simple bullet lists with tags.

## Structure

```markdown
# {Domain}

- Friction point description. [tags]
- Another friction point. [tags]
```

## Example

```markdown
# Python Typing

- Use PEP 585 built-in generics (list, dict) not typing imports (List, Dict). [python, typing, pep585]
- Prefer `str | None` over `Optional[str]` in Python 3.10+. [python, typing, optional]
```

## Rules

- Concise, imperative descriptions
- Tags in [brackets] at end
- One bullet per friction point
- No sub-bullets or grouping
