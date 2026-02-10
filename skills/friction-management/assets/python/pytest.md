# Python Pytest

## Test Fixtures

- Avoid complex conditional logic in test fixtures (if existing/else create pattern). Prefer simple, predictable setup: find ANY matching record, always update it for test, restore in cleanup. [python, pytest, fixtures, test-setup, simplicity]
- Test fixtures for database modifications should accept multiple parameters as tuples via request.param to test query constraints (user_id, thresholds, date ranges) not just single values. [python, pytest, fixtures, parametrization, database-testing]
- Initialize fixture variables (original_claimed_by = None, booking_contract = None) before queries as defensive programming - ensures variables exist in cleanup scope even if queries fail. [python, pytest, fixtures, defensive-programming, error-handling]
- Reuse same SQL UPDATE statement for fixture setup and cleanup with different bound parameters (DRY) instead of writing separate restore statements. [python, pytest, fixtures, sql, dry]

## Domain Knowledge

- Understand full domain context before writing database tests. For booking queries, both claimed_and_managed_by AND buying_program_type_id affect "unclaimed" logic - updating only one creates invalid test state. [python, pytest, domain-knowledge, database-testing, context]

## Test Structure

- Use separate transaction blocks (with engine.begin()) for different query scenarios in same test instead of executing multiple queries in one transaction - cleaner separation and easier debugging. [python, pytest, sqlalchemy, transactions, test-structure]
- Use set comprehensions for result sets when testing membership ({row.field for row in results}) instead of list comprehensions - more efficient and Pythonic. [python, pytest, performance, collections]

## Debugging and Assertions

- Include debug utilities in database tests (parse_stmt fixture to print compiled SQL with literal binds) for troubleshooting query issues. [python, pytest, debugging, sql, utilities]
- Write assertion messages that explain business logic and WHY test should pass ("The query is too permissive") not just WHAT failed - aids debugging. [python, pytest, assertions, clarity, debugging]
