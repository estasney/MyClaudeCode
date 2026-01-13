# Python SQL

- Verify column names exist in schema before using in queries - do not infer column names from context. [python, sql, database, schema, verification]
- Prefer dataclass or TypedDict over dict for SQL query results containing structured data. Simple aggregations (value counts, frequency maps) can use dict. Use dataclass if common in codebase, otherwise TypedDict. [python, sql, typing, return-types, structured-data]
