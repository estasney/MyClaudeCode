# Programmatic Test Generation

Generate test cases dynamically at collection time instead of hardcoding them.

## pytest_generate_tests Hook

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

## Storing Generated Parameters as Constants

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

## Combining Approaches

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
