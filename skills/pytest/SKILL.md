---
name: pytest
description: Comprehensive pytest testing patterns covering fixtures, dependency injection, parametrization, mocking, and contract testing. Use when writing Python tests, debugging test failures, refactoring test suites, or implementing test patterns like fixture factories, indirect parametrization, or pytest-mock integration.
allowed-tools: Read(./*)
---

# Pytest Testing Patterns

## Why Parametrization Matters

**Default to parametrization.** Hardcoded test values are a code smell.

The instinct to write `user = User(name="Alice", age=30)` is strong, but it creates tests that:
- Test only one case when they should test many
- Hide edge cases (what about age=0? negative ages? age=150?)
- Are harder to extend (adding a case requires duplicating the entire test)
- Make patterns less obvious (is "Alice" special, or just an example?)

**Parametrization forces you to think about the test space:**

```python
# Bad: Hardcoded, tests one case
def test_discount_calculation():
    result = calculate_discount(100, 10)
    assert result == 90

# Good: Parametrized, tests multiple cases, makes contract explicit
@pytest.mark.parametrize('price,percent,expected', [
    (100, 10, 90),      # Normal case
    (100, 0, 100),      # No discount
    (100, 100, 0),      # Full discount
    (0, 10, 0),         # Zero price
    (50.5, 10, 45.45),  # Decimal handling
])
def test_discount_calculation(price, percent, expected):
    result = calculate_discount(price, percent)
    assert result == expected
```

The parametrized version:
- Covers 5 scenarios in the same space
- Makes edge cases explicit (zero price, full discount, decimals)
- Documents the contract through examples
- Is easier to extend (add a tuple, not copy-paste the function)

**Test IDs for readability:**

```python
# IDs can be strings
@pytest.mark.parametrize('given,expected', [
    (10, 100),
    (0, 0),
], ids=['positive', 'zero'])
def test_square(given, expected):
    assert square(given) == expected

# Or a callable for dynamic generation
def idfn(val):
    if isinstance(val, dict):
        return f"user_{val.get('role', 'unknown')}"
    return str(val)

@pytest.mark.parametrize('user_data', [
    {'name': 'Alice', 'role': 'admin'},
    {'name': 'Bob', 'role': 'user'},
], ids=idfn)
def test_user(user_data):
    ...
```

When you find yourself writing a hardcoded test value, ask: "What other values should I test here?"

## Fundamentals

### Assert with Debug Messages

Always include informative failure messages using the `assert condition, "message"` pattern:

```python
@pytest.mark.parametrize('age,is_valid', [
    (25, True),
    (150, False),
    (-1, False),
])
def test_user_age_validation(age, is_valid):
    user = User(age=age)
    assert user.is_valid() is is_valid, \
        f"User with age={age} should be {'valid' if is_valid else 'invalid'}"

@pytest.mark.parametrize('items,expected_total', [
    ([10, 20, 30], 60),
    ([100], 100),
    ([], 0),
])
def test_calculate_total(items, expected_total):
    result = calculate_total(items)
    assert result == expected_total, \
        f"Expected {expected_total}, got {result}. Input validation may be broken for {items}"
```

Pattern: `assert actual == expected, f"Expected {expected}, got {actual}. [Why this matters]"`

### Fixtures as Dependency Injection

Fixtures provide dependency injection, reducing duplication and isolating setup logic:

```python
@pytest.fixture
def database_connection():
    """Provides clean database connection per test."""
    conn = create_connection("postgresql://test_db")
    yield conn
    conn.close()

@pytest.fixture
def user_repository(database_connection):
    """Repository depends on database connection."""
    return UserRepository(database_connection)

@pytest.mark.parametrize('name,age', [
    ('Alice', 30),
    ('Bob', 25),
    ('Charlie', 35),
])
def test_user_creation(user_repository, name, age):
    user = user_repository.create(name=name, age=age)
    assert user.id is not None, f"User {name} should receive ID after creation"
    assert user.name == name, f"Expected name {name}, got {user.name}"
    assert user_repository.count() == 1, "Repository should contain exactly 1 user"
```

Key points:
- Fixtures are injected by name in test function signatures
- Fixtures can depend on other fixtures
- `yield` allows teardown logic after test execution
- Scope controls fixture lifetime: `function` (default), `class`, `module`, `session`

### conftest.py: Auto-imported Fixtures

Fixtures defined in `conftest.py` are automatically discovered and available to all tests without explicit imports.

**Structure:**

```
tests/
├── conftest.py              # Global fixtures for all tests
├── test_users.py
├── test_orders.py
└── integration/
    ├── conftest.py          # Fixtures only for integration tests
    └── test_api.py
```

**Example `tests/conftest.py`:**

```python
import pytest

@pytest.fixture
def database_connection():
    """Available to ALL tests in tests/ and subdirectories."""
    conn = create_connection("postgresql://test_db")
    yield conn
    conn.close()

@pytest.fixture
def user_repository(database_connection):
    """Also globally available, depends on database_connection."""
    return UserRepository(database_connection)
```

**Example `tests/integration/conftest.py`:**

```python
import pytest

@pytest.fixture
def api_client():
    """Only available to tests in tests/integration/ and below."""
    client = TestClient()
    yield client
    client.cleanup()
```

**Usage in tests (no imports needed):**

```python
# tests/test_users.py
@pytest.mark.parametrize('name,age', [
    ('Alice', 30),
    ('Bob', 25),
])
def test_user_creation(user_repository, name, age):
    # user_repository fixture auto-discovered from conftest.py
    user = user_repository.create(name=name, age=age)
    assert user.id is not None
```

**Benefits:**
- Fixtures available without import statements
- Scope fixtures to specific test directories
- Reduce boilerplate across test files
- Create hierarchical fixture availability (global → specific)

## Advanced Patterns

### Fixture Factories

Factory fixtures generate multiple instances per test:

```python
@pytest.fixture
def make_user():
    """Factory for creating users with custom attributes."""
    users = []
    
    def _make_user(name="Test User", age=25, **kwargs):
        user = User(name=name, age=age, **kwargs)
        users.append(user)
        return user
    
    yield _make_user
    
    # Cleanup all created users
    for user in users:
        user.delete()

@pytest.mark.parametrize('users_data,expected_older', [
    ([{'name': 'Alice', 'age': 30}, {'name': 'Bob', 'age': 25}], 'Alice'),
    ([{'name': 'Charlie', 'age': 20}, {'name': 'Diana', 'age': 35}], 'Diana'),
])
def test_age_comparison(make_user, users_data, expected_older):
    users = [make_user(**data) for data in users_data]
    older_user = max(users, key=lambda u: u.age)
    
    assert older_user.name == expected_older, \
        f"Expected {expected_older} to be older, got {older_user.name}"

@pytest.mark.parametrize('given,expected_name,expected_age', [
    ({}, "Test User", 25),
    ({'name': 'Custom'}, "Custom", 25),
    ({'age': 40}, "Test User", 40),
])
def test_user_defaults(make_user, given, expected_name, expected_age):
    user = make_user(**given)
    assert user.name == expected_name, f"Expected name {expected_name}, got {user.name}"
    assert user.age == expected_age, f"Expected age {expected_age}, got {user.age}"
```

Use factories when you need:
- Multiple instances per test
- Varying attributes across instances
- Centralized cleanup logic
- Default values with override capability

### Indirect Parametrization

Use `indirect=True` when parameters need preprocessing or setup before reaching the test:

```python
@pytest.fixture
def user(request):
    """Fixture that receives parameter and creates user."""
    user_data = request.param
    user = User(**user_data)
    yield user
    user.delete()

@pytest.mark.parametrize('user,expected_can_delete', [
    ({'name': 'Alice', 'age': 30, 'role': 'admin'}, True),
    ({'name': 'Bob', 'age': 25, 'role': 'user'}, False),
    ({'name': 'Charlie', 'age': 35, 'role': 'moderator'}, False),
], indirect=['user'])
def test_user_permissions(user, expected_can_delete):
    result = user.can_delete_users()
    assert result is expected_can_delete, \
        f"{user.role} {user.name} delete permission should be {expected_can_delete}, got {result}"
```

`indirect=True` is essential when:
- Parameters require resource setup/teardown
- Same fixture logic applies to different parameter sets
- Parameters need transformation before use
- Complex objects need construction from simple data

Partial indirect for mixed parameters:

```python
@pytest.fixture
def database(request):
    db = Database(request.param)
    yield db
    db.cleanup()

@pytest.mark.parametrize('database,query_type,expected_success', [
    ('postgres', 'SELECT', True),
    ('mysql', 'SELECT', True),
    ('postgres', 'INSERT', True),
], indirect=['database'])  # Only database is indirect
def test_query_execution(database, query_type, expected_success):
    result = database.execute(f"{query_type} * FROM users")
    assert (result is not None) is expected_success, \
        f"{query_type} on {database.type} should {'succeed' if expected_success else 'fail'}"
```

### Combining Advanced Patterns

Fixture factories + indirect parametrization + mocking:

```python
@pytest.fixture
def make_order(mocker):
    """Factory for orders with mocked payment processor."""
    orders = []
    mock_payment = mocker.patch('shop.PaymentProcessor')
    
    def _make_order(total, status='pending'):
        mock_payment.charge.return_value = f"txn_{len(orders)}"
        order = Order(total=total, status=status, payment_processor=mock_payment)
        orders.append(order)
        return order
    
    yield _make_order
    
    for order in orders:
        order.cancel()

@pytest.fixture
def order_data(request):
    """Receives parameters and creates order via factory."""
    make_order = request.getfixturevalue('make_order')
    return make_order(**request.param)

@pytest.mark.parametrize('order_data,expected_result', [
    ({'total': 100, 'status': 'pending'}, True),
    ({'total': 200, 'status': 'pending'}, True),
    ({'total': 50, 'status': 'paid'}, None),  # Already paid, no processing
], indirect=['order_data'])
def test_order_processing(order_data, expected_result):
    if order_data.status == 'pending':
        result = order_data.process_payment()
        assert result is expected_result, \
            f"Order {order_data.id} payment processing expected {expected_result}, got {result}"
    else:
        assert order_data.is_paid(), f"Order {order_data.id} should already be paid"
```

**Note on `request.getfixturevalue()`:** This is a last resort for accessing fixtures dynamically. Prefer direct fixture dependencies in function signatures when possible. Use `getfixturevalue()` only when fixture names need to be determined at runtime or when combining indirect parametrization with fixture factories.

## Programmatic Test Generation

Generate test cases dynamically at collection time instead of hardcoding them.

### pytest_generate_tests Hook

Use `pytest_generate_tests` when parametrization logic needs to be computed or depends on external data:

```python
# conftest.py
def pytest_generate_tests(metafunc):
    """Called for each test function to enable dynamic parametrization."""
    if "browser" in metafunc.fixturenames:
        # Generate based on environment variable
        browsers = os.getenv("TEST_BROWSERS", "chrome,firefox").split(",")
        metafunc.parametrize("browser", browsers)
    
    if "db_config" in metafunc.fixturenames:
        # Generate from external file
        configs = load_db_configs()  # Returns list of config dicts
        metafunc.parametrize("db_config", configs, indirect=True)
```

**When to use `pytest_generate_tests`:**
- Parameters depend on CLI options or environment variables
- Test data comes from files or databases
- Need conditional parametrization based on test context
- Complex parameter generation logic

**When NOT to use:**
- Simple, static parameter lists (use `@pytest.mark.parametrize`)
- Parameter logic fits in a fixture factory

### Storing Generated Parameters as Constants

For complex parameter generation, compute once and store as a constant:

```python
# test_api.py

def _load_test_cases():
    """Generate test cases from API schema."""
    schema = load_openapi_schema()
    test_cases = []
    for endpoint in schema['paths']:
        for method in schema['paths'][endpoint]:
            test_cases.append((method.upper(), endpoint))
    return test_cases

# Computed once at module load time
API_TEST_CASES = _load_test_cases()

@pytest.mark.parametrize('method,endpoint', API_TEST_CASES)
def test_api_endpoint(method, endpoint):
    response = api_client.request(method, endpoint)
    assert response.status_code in (200, 201, 204)
```

**Benefits:**
- Computation happens once at import time, not per test collection
- Parameters are visible and debuggable
- Can be shared across multiple test functions
- Easier to test the parameter generation logic separately

**Pattern:**
```python
# 1. Define generation function
def _generate_params():
    # Complex logic here
    return list_of_params

# 2. Store as module constant
PARAMS = _generate_params()

# 3. Use in parametrize
@pytest.mark.parametrize('param', PARAMS)
def test_something(param):
    ...
```

### Combining Approaches

```python
# conftest.py
def load_integration_configs():
    """Load from file or environment."""
    config_file = os.getenv("INTEGRATION_CONFIG", "configs/default.json")
    with open(config_file) as f:
        return json.load(f)

INTEGRATION_CONFIGS = load_integration_configs()

def pytest_generate_tests(metafunc):
    if "integration_config" in metafunc.fixturenames:
        metafunc.parametrize(
            "integration_config",
            INTEGRATION_CONFIGS,
            ids=[c['name'] for c in INTEGRATION_CONFIGS]
        )
```

## Configuration with pyproject.toml

Configure pytest behavior in `pyproject.toml` under `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
# Minimum pytest version required
minversion = "7.0"

# Directories containing tests
testpaths = ["tests", "integration"]

# Python import paths to add
pythonpath = ["src"]

# Default command-line options (runs every time)
addopts = [
    "-ra",                    # Show extra test summary
    "-q",                     # Quiet mode
    "--strict-markers",       # Error on unknown markers
    "--strict-config",        # Error on config issues
    "--cov=myapp",           # Coverage for myapp package
    "--cov-report=html",     # HTML coverage report
]

# Custom markers (must declare to avoid warnings with --strict-markers)
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests requiring external services",
    "smoke: critical tests that run first",
]

# Minimum line length for code in docstring examples
doctest_optionflags = ["NORMALIZE_WHITESPACE", "ELLIPSIS"]

# Ignore certain warnings
filterwarnings = [
    "error",                                 # Treat all warnings as errors
    "ignore::DeprecationWarning",           # Except deprecation warnings
    "ignore:.*urllib3.*:DeprecationWarning", # Specific warning pattern
]

# Logging configuration (see Logging section below)
log_cli = true
log_cli_level = "INFO"
log_cli_format = "%(asctime)s [%(levelname)8s] %(message)s"
log_cli_date_format = "%Y-%m-%d %H:%M:%S"

# File logging
log_file = "logs/pytest.log"
log_file_level = "DEBUG"
log_file_format = "%(asctime)s [%(levelname)8s] %(name)s: %(message)s"
log_file_date_format = "%Y-%m-%d %H:%M:%S"

# Timeout for tests (requires pytest-timeout plugin)
timeout = 300

# Directory for pytest cache
cache_dir = ".pytest_cache"

# Control test collection
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]

# Don't recurse into these directories
norecursedirs = [".git", ".tox", "dist", "build", "*.egg"]
```

**Key options:**
- `addopts`: Always-applied CLI options
- `testpaths`: Where to find tests
- `markers`: Declare custom markers (required with `--strict-markers`)
- `pythonpath`: Add to sys.path before running
- `filterwarnings`: Control warning behavior

## Logging

### Console Logging During Tests

Enable live logging to see output during test execution:

```toml
[tool.pytest.ini_options]
log_cli = true
log_cli_level = "INFO"
log_cli_format = "%(levelname)s %(name)s: %(message)s"
```

Or via CLI:
```bash
pytest --log-cli-level=DEBUG
```

### File Logging

Write logs to a file:

```toml
[tool.pytest.ini_options]
log_file = "tests/logs/test_run.log"
log_file_level = "DEBUG"
log_file_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s (%(filename)s:%(lineno)d)"
log_file_date_format = "%Y-%m-%d %H:%M:%S"
```

### Using Logging in Tests

```python
import logging

def test_something(caplog):
    logger = logging.getLogger(__name__)
    
    # Set level for this test
    caplog.set_level(logging.DEBUG)
    
    logger.info("Starting test")
    result = function_under_test()
    logger.debug(f"Result: {result}")
    
    # Assert on log messages
    assert "Starting test" in caplog.text
    assert any(record.levelname == "DEBUG" for record in caplog.records)
```

### Logging Patterns

```python
import logging

@pytest.fixture(autouse=True)
def log_test_name(request):
    """Log test name before/after each test."""
    logger = logging.getLogger(__name__)
    logger.info(f"Starting: {request.node.name}")
    yield
    logger.info(f"Finished: {request.node.name}")

@pytest.mark.parametrize('level,expected_output', [
    (logging.DEBUG, True),
    (logging.INFO, True),
    (logging.WARNING, False),
])
def test_logging_levels(caplog, level, expected_output):
    logger = logging.getLogger("myapp")
    caplog.set_level(level, logger="myapp")
    
    logger.debug("Debug message")
    logger.info("Info message")
    
    has_debug = any(r.levelname == "DEBUG" for r in caplog.records)
    assert has_debug is expected_output
```

For comprehensive CLI options reference, see [references/cli_options.md](references/cli_options.md).

## Property-Based Testing with Hypothesis

**Hypothesis is optional but powerful.** Use it when you need confidence that your code handles all edge cases, not just the examples you thought of.

Traditional parametrized tests check specific cases. Hypothesis generates hundreds of test cases automatically, including edge cases you didn't consider, then shrinks failures to minimal examples.

```bash
pip install hypothesis
```

### Basic Usage

```python
from hypothesis import given
from hypothesis import strategies as st

# Instead of hardcoding test cases:
@pytest.mark.parametrize('text', ['hello', 'world', ''])
def test_reverse_reverse(text):
    assert reverse(reverse(text)) == text

# Hypothesis generates hundreds of examples:
@given(st.text())
def test_reverse_reverse_property(text):
    assert reverse(reverse(text)) == text
```

Hypothesis runs the test 100 times (default) with different inputs, including edge cases like empty strings, unicode, very long strings, etc.

### Built-in Strategies

Strategies define the type and range of data to generate:

```python
from hypothesis import given, strategies as st

# Numeric types
@given(st.integers())
def test_int(n):
    assert isinstance(n, int)

@given(st.integers(min_value=0, max_value=100))
def test_bounded_int(n):
    assert 0 <= n <= 100

@given(st.floats(allow_nan=False, allow_infinity=False))
def test_float(f):
    assert isinstance(f, float)

# Text
@given(st.text())
def test_text(s):
    assert isinstance(s, str)

@given(st.text(alphabet='abc', min_size=1, max_size=10))
def test_constrained_text(s):
    assert 1 <= len(s) <= 10
    assert all(c in 'abc' for c in s)

# Collections
@given(st.lists(st.integers(), min_size=0, max_size=10))
def test_list(lst):
    assert len(lst) <= 10

@given(st.dictionaries(keys=st.text(), values=st.integers()))
def test_dict(d):
    assert isinstance(d, dict)

# Booleans, None
@given(st.booleans())
def test_bool(b):
    assert isinstance(b, bool)

@given(st.none())
def test_none(n):
    assert n is None

# Combinations
@given(st.one_of(st.integers(), st.text()))
def test_union(value):
    assert isinstance(value, (int, str))

# Tuples with mixed types
@given(st.tuples(st.integers(), st.text(), st.booleans()))
def test_tuple(t):
    num, text, flag = t
    assert isinstance(num, int)
```

### st.builds: Generate Class Instances

Use `st.builds()` to construct objects from strategies:

```python
from dataclasses import dataclass

@dataclass
class User:
    name: str
    age: int
    email: str

# Build User instances
user_strategy = st.builds(
    User,
    name=st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll')), min_size=1),
    age=st.integers(min_value=0, max_value=120),
    email=st.emails()
)

@given(user_strategy)
def test_user_validation(user):
    assert user.age >= 0
    assert '@' in user.email
    assert len(user.name) > 0
```

**When to use `st.builds()`:**
- Constructing objects from multiple strategies
- Testing with real domain objects, not just primitives
- Building complex nested structures

**Pattern:**
```python
# For a class
class Point:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

# Use st.builds to generate instances
points = st.builds(Point, x=st.integers(), y=st.integers())

@given(points)
def test_point_distance(p):
    assert distance(p, p) == 0
```

### Composite Strategies: Dependent Data

Use `@st.composite` when values depend on each other:

```python
@st.composite
def sorted_pairs(draw):
    """Generate (x, y) where x <= y."""
    x = draw(st.integers())
    y = draw(st.integers(min_value=x))  # y depends on x
    return (x, y)

@given(sorted_pairs())
def test_pair_is_sorted(pair):
    x, y = pair
    assert x <= y

@st.composite
def user_with_posts(draw):
    """Generate user with 1-10 posts."""
    user = draw(st.builds(
        User,
        name=st.text(min_size=1),
        age=st.integers(min_value=13, max_value=120)
    ))
    num_posts = draw(st.integers(min_value=1, max_value=10))
    posts = [
        draw(st.builds(
            Post,
            author_id=st.just(user.id),
            content=st.text(min_size=1, max_size=280)
        ))
        for _ in range(num_posts)
    ]
    return (user, posts)

@given(user_with_posts())
def test_user_has_posts(data):
    user, posts = data
    assert len(posts) >= 1
    assert all(post.author_id == user.id for post in posts)
```

**Composite vs builds:**
- Use `@st.composite` when values depend on each other
- Use `st.builds()` when values are independent
- Composite gives you full control via the `draw` function

### Chaining Strategies

Combine strategies to build complex data:

```python
# Chain with .map()
positive_floats = st.floats(min_value=0).map(abs)

# Chain with .filter()
even_ints = st.integers().filter(lambda x: x % 2 == 0)

# Chain with .flatmap()
@given(st.integers(min_value=1, max_value=10).flatmap(
    lambda n: st.lists(st.integers(), min_size=n, max_size=n)
))
def test_list_length_matches(lst):
    # List length was generated first, then list of that length
    assert 1 <= len(lst) <= 10

# Complex example: generate trees
@st.composite
def binary_trees(draw, elements=st.integers(), max_depth=5):
    """Recursively generate binary trees."""
    if max_depth == 0:
        return None
    
    if draw(st.booleans()):
        return None  # Leaf node
    
    value = draw(elements)
    left = draw(binary_trees(elements, max_depth - 1))
    right = draw(binary_trees(elements, max_depth - 1))
    
    return Node(value, left, right)

@given(binary_trees())
def test_tree_traversal(tree):
    if tree is None:
        assert tree_size(tree) == 0
    else:
        assert tree_size(tree) >= 1
```

**Strategy chaining patterns:**
- `.map(func)`: Transform generated values
- `.filter(predicate)`: Only keep values matching condition (use sparingly)
- `.flatmap(func)`: Generate strategy based on previous value
- Recursive strategies: Use `st.recursive()` or `@st.composite` for trees, graphs

### Integration with Pytest

Hypothesis works seamlessly with pytest:

```python
# Combine with parametrize
@pytest.mark.parametrize('operation', [
    lambda x: x + 0,
    lambda x: x * 1,
    lambda x: x - 0,
])
@given(st.integers())
def test_identity_operations(operation, x):
    assert operation(x) == x

# Use pytest fixtures
@pytest.fixture
def db_connection():
    conn = create_connection()
    yield conn
    conn.close()

@given(st.text(min_size=1))
def test_database_insert(db_connection, username):
    user_id = db_connection.insert_user(username)
    assert user_id is not None
    assert db_connection.get_user(user_id).name == username

# Configure hypothesis via pytest
@given(st.integers())
@pytest.mark.hypothesis(max_examples=1000, deadline=None)
def test_expensive_property(n):
    assert slow_computation(n) >= 0
```

### When to Use Hypothesis

**Use Hypothesis for:**
- Testing mathematical properties (commutativity, associativity, invariants)
- Parsers and serializers (round-trip tests)
- Data transformations (input/output relationships)
- Finding edge cases in complex logic
- Validation functions

**Don't use Hypothesis for:**
- Tests with specific business requirements (use parametrize)
- Tests where you need exact control over inputs
- Very slow functions (unless you reduce max_examples)

**Example: Testing a cache:**
```python
@given(st.lists(st.tuples(st.text(min_size=1), st.integers()), min_size=1))
def test_cache_properties(operations):
    cache = Cache(max_size=10)
    
    for key, value in operations:
        cache.set(key, value)
        # Property: immediate retrieval should work
        assert cache.get(key) == value
    
    # Property: cache size never exceeds max
    assert len(cache) <= 10
```

### Debugging Hypothesis Failures

When Hypothesis finds a failure, it shrinks to minimal example:

```python
@given(st.lists(st.integers()))
def test_sorted_property(lst):
    result = my_sort(lst)
    assert result == sorted(lst)

# Hypothesis might report:
# Falsifying example:
#     lst=[0, -1]
# 
# Even if the failure occurred with a 1000-element list,
# Hypothesis shrinks it to the minimal failing case
```

**Tips:**
- Hypothesis shows minimal failing example automatically
- Use `@example()` decorator to add regression test cases
- Use `hypothesis.note()` to add debug output
- Use `--hypothesis-show-statistics` flag to see generation stats

```python
from hypothesis import given, example, note

@given(st.integers())
@example(0)  # Always test this case
@example(-1)  # And this one
def test_with_examples(n):
    note(f"Testing with n={n}")  # Visible on failure
    assert my_function(n) >= 0
```

## Testing Contracts

For philosophy and detailed examples of **what to test**, see [references/testing_contracts.md](references/testing_contracts.md).

Core principle: Test the public interface and behavior guarantees (contracts), not implementation details. Focus on:
- Input/output relationships
- Side effects (database writes, API calls)
- Error conditions
- Invariants

Quick example:
```python
# Good: Tests contract with parametrization
@pytest.mark.parametrize('price,percent,expected', [
    (100, 10, 90),
    (100, 0, 100),
    (100, 100, 0),
])
def test_discount_calculation(price, percent, expected):
    result = calculate_discount(price, percent)
    assert result == expected, f"{percent}% discount on ${price} should be ${expected}, got ${result}"

# Bad: Tests implementation
def test_uses_specific_formula():
    source = inspect.getsource(calculate_discount)
    assert "price * (1 - percent/100)" in source  # Breaks on refactor
```

## Mocking External Dependencies

For comprehensive mocking patterns with pytest-mock, see [references/mocking.md](references/mocking.md).

Quick reference:
- Use `mocker.patch()` to mock external dependencies (APIs, databases, file systems)
- Use `mocker.MagicMock()` for auto-generating method chains
- Use `mocker.spy()` to verify calls to real functions
- Don't mock internal implementation details

## Common Patterns

**Note on `request.getfixturevalue()`:** This is a last resort for accessing fixtures dynamically. Prefer direct fixture dependencies in function signatures when possible. Use `getfixturevalue()` only when fixture names need to be determined at runtime or when combining indirect parametrization with fixture factories.

## Testing Contracts

For philosophy and detailed examples of **what to test**, see [references/testing_contracts.md](references/testing_contracts.md).

Core principle: Test the public interface and behavior guarantees (contracts), not implementation details. Focus on:
- Input/output relationships
- Side effects (database writes, API calls)
- Error conditions
- Invariants

Quick example:
```python
# Good: Tests contract with parametrization
@pytest.mark.parametrize('price,percent,expected', [
    (100, 10, 90),
    (100, 0, 100),
    (100, 100, 0),
])
def test_discount_calculation(price, percent, expected):
    result = calculate_discount(price, percent)
    assert result == expected, f"{percent}% discount on ${price} should be ${expected}, got ${result}"

# Bad: Tests implementation
def test_uses_specific_formula():
    source = inspect.getsource(calculate_discount)
    assert "price * (1 - percent/100)" in source  # Breaks on refactor
```

## Common Patterns

**Parametrize instead of hardcoding test values:**

Always prefer parametrization over hardcoded test values:

```python
# Good: Parametrized with clear given/expected structure
@pytest.mark.parametrize('given,expected', [
    (10, 100),
    (20, 400),
    (0, 0),
    (-5, 25),
], ids=['positive', 'larger', 'zero', 'negative'])
def test_square_calculation(given, expected):
    result = square(given)
    assert result == expected, f"square({given}) should equal {expected}, got {result}"

# Bad: Hardcoded single case
def test_square_calculation():
    assert square(10) == 100
```

The `given,expected` parameter naming pattern makes test intent explicit and scales naturally:

```python
@pytest.mark.parametrize('given,expected', [
    ({'price': 100, 'discount': 10}, 90),
    ({'price': 100, 'discount': 0}, 100),
    ({'price': 100, 'discount': 100}, 0),
], ids=['10_percent', 'no_discount', 'full_discount'])
def test_calculate_discounted_price(given, expected):
    result = calculate_discount(**given)
    assert result == expected, f"Discount calculation failed: {given} -> {result} (expected {expected})"
```

**Test helper functions for complex assertions:**

Extract complex verification logic into helper functions:

```python
def assert_user_valid(user, expected_name, expected_age):
    """Helper to verify user state matches expectations."""
    assert user.name == expected_name, f"Expected name '{expected_name}', got '{user.name}'"
    assert user.age == expected_age, f"Expected age {expected_age}, got {user.age}"
    assert user.is_active is True, f"User {user.name} should be active"
    assert user.created_at is not None, "User should have creation timestamp"

@pytest.mark.parametrize('user_data', [
    {'name': 'Alice', 'age': 30},
    {'name': 'Bob', 'age': 25},
    {'name': 'Charlie', 'age': 35},
])
def test_user_creation(user_data):
    user = create_user(**user_data)
    assert_user_valid(user, user_data['name'], user_data['age'])

def assert_api_response_valid(response, expected_status, expected_fields):
    """Helper to verify API response structure and content."""
    assert response.status_code == expected_status, \
        f"Expected status {expected_status}, got {response.status_code}"
    
    data = response.json()
    for field in expected_fields:
        assert field in data, f"Response missing required field: {field}"
        assert data[field] is not None, f"Field '{field}' should not be None"

@pytest.mark.parametrize('user_id,expected_fields', [
    (1, ['id', 'name', 'email', 'created_at']),
    (2, ['id', 'name', 'email', 'created_at']),
])
def test_user_endpoint_returns_complete_data(user_id, expected_fields):
    response = client.get(f'/users/{user_id}')
    assert_api_response_valid(response, 200, expected_fields)
```

Benefits of test helpers:
- DRY: Reuse complex assertions across tests
- Clarity: Descriptive function names document intent
- Maintainability: Update assertion logic in one place
- Debugging: Helper failures show which specific check failed

**Testing exceptions (contract: exception type raised):**

```python
from contextlib import nullcontext as does_not_raise

@pytest.mark.parametrize('age,expectation', [
    (-1, pytest.raises(ValueError)),
    (200, pytest.raises(ValueError)),
    (25, does_not_raise()),  # Valid age should not raise
    (0, does_not_raise()),
    (150, does_not_raise()),
])
def test_user_age_validation(age, expectation):
    with expectation:
        user = User(age=age)
        # If we reach here without exception, age was valid
        assert user.age == age
```

Use `nullcontext()` (aliased as `does_not_raise()` for clarity) to test that valid inputs don't raise exceptions. This allows testing both positive and negative cases in the same parametrized test.

**Fixture scope for expensive setup:**

```python
@pytest.fixture(scope='module')
def database_connection():
    """Single connection for entire test module."""
    conn = create_connection()
    yield conn
    conn.close()
```

**Autouse fixtures for universal setup:**

```python
@pytest.fixture(autouse=True)
def reset_database():
    """Runs before every test automatically."""
    db.clear()
```
