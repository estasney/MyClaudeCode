# Pytest Logging

## Console Logging During Tests

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

## File Logging

Write logs to a file:

```toml
[tool.pytest.ini_options]
log_file = "tests/logs/test_run.log"
log_file_level = "DEBUG"
log_file_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s (%(filename)s:%(lineno)d)"
log_file_date_format = "%Y-%m-%d %H:%M:%S"
```

## Using Logging in Tests

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

## Logging Patterns

### Auto-log Test Names

```python
import logging

@pytest.fixture(autouse=True)
def log_test_name(request):
    """Log test name before/after each test."""
    logger = logging.getLogger(__name__)
    logger.info(f"Starting: {request.node.name}")
    yield
    logger.info(f"Finished: {request.node.name}")
```

### Test Logging Levels

```python
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

### Clear Logs Between Tests

```python
def test_first(caplog):
    logging.info("First test")
    assert "First test" in caplog.text

def test_second(caplog):
    # caplog is automatically cleared between tests
    logging.info("Second test")
    assert "First test" not in caplog.text
    assert "Second test" in caplog.text
```

### Log to Different Handlers

```python
def test_with_file_logging(tmp_path, caplog):
    log_file = tmp_path / "test.log"
    
    # Configure file handler
    handler = logging.FileHandler(log_file)
    logger = logging.getLogger("myapp")
    logger.addHandler(handler)
    
    # Also capture in caplog
    caplog.set_level(logging.DEBUG, logger="myapp")
    
    logger.info("Test message")
    
    # Verify both
    assert "Test message" in caplog.text
    assert "Test message" in log_file.read_text()
```
