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
- Think critically - how can this be written to generalize within the domain?

## Generalization Examples

<bad_example>
When asked to add a configurable field that was previously a single composite value (path, URL, connection string),
infer that it should be split into N separately configurable constituent parts, not just partially decomposed. Use
computed_field/property to recompose the parts and hide complexity downstream. Example: splitting `data_file` into `data_dir`  
should also introduce `data_file_name`, not hardcode the filename.  
Example: splitting `db_url` into `db_host` should also add `db_port`, `db_name`, etc. [python, pydantic, configuration, design, computed-field, models, inference, decomposition]
</bad_example>

<good_example>
When refactoring a configuration model that previously used a single composite field (e.g., a file path, URL, or connection string),
decompose it into multiple distinct fields representing each constituent part. To maintain usability, implement a computed property that recombines these parts for downstream consumers.
</good_example>
