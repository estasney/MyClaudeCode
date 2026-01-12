# Processing Workflow

Step-by-step process for adding friction points to the library.

## Input

Friction plan file from `/friction` command containing bullets with tags:

```markdown
- Use PEP 585 built-in generics (list, dict) not typing imports. [python, typing, pep585]
- Prefer pathlib.Path over os.path for file operations. [python, io, pathlib]
```

## Steps

1. **Parse bullets**
   - Extract description + tags from each bullet
   - Tags are in [brackets] at end

2. **Normalize tags**
   - Convert to slug format: lowercase, hyphenated
   - `[Python, Typing, PEP 585]` → `[python, typing, pep585]`
   - Check friction-index.md for existing tags
   - Adapt synonyms to existing tags:
     - Existing has `file-io`, new has `io` → use `file-io`
     - Existing has `type-hints`, new has `typing` → use `typing`

3. **Determine file location**
   - Use categorization rules: `references/categorization.md`
   - `[python, typing, pep585]` → `assets/python/typing.md`
   - `[python, io, pathlib]` → `assets/python/io.md`

4. **Update/create domain files**
   - Create directory if needed
   - Create file with header if new
   - Append bullet to file with normalized tags
   - Check for duplicates before adding

5. **Update index**
   - Add domain to index if new
   - Add normalized tags to domain entry
   - Example: `**Typing**: python/typing.md - Tags: python, typing, pep585`

6. **Report**
   - List what was added where
   - Note new files created
   - Note any tag normalizations

## Tag Normalization Examples

- `Type Hints` → `type-hints`
- `PEP 585` → `pep585`
- `File I/O` → `file-io`
- `SQLAlchemy 2.0` → `sqlalchemy-2.0` or `sqlalchemy, v2`
