# Pydantic Settings

- When refactoring a configuration model that previously used a single composite field (e.g., a file path, URL, or connection string),
  decompose it into multiple distinct fields representing each constituent part. To maintain usability, implement a computed property that recombines these parts for downstream consumers.
  [python, pydantic, configuration, refactoring, computed-field, models, inference, decomposition]
