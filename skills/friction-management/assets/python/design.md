# Python Design

- Follow functional core/imperative shell pattern. Keep functions focused on single responsibilities. Avoid functions that combine data fetching, processing, and filtering. Instead, create separate functions: one to fetch all data, separate pure functions for processing/transforming. [python, design, architecture, functional-core, separation-of-concerns]
- Avoid default arguments in functions. Prefer explicit configuration objects or settings rather than embedding defaults in function signatures. This reduces brittleness and makes configuration more maintainable. [python, design, configuration, default-arguments, maintainability]
- Hoist constant logic outside loops. Avoid repeated conditional checks in loops when the result is invariant across iterations. [python, performance, functional-programming, loops]
- Use strict=True with zip by default. [python, zip, strict]
