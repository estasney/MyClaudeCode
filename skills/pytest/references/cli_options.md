# Pytest Command-Line Options Reference

Complete reference of pytest CLI flags. Run `pytest --help` for the most current list.

## Test Selection

```bash
# Run specific file
pytest test_module.py

# Run specific directory
pytest tests/unit/

# Run by node ID (module::class::method)
pytest test_module.py::TestClass::test_method

# Run by keyword expression
pytest -k "test_user and not test_admin"

# Run by marker
pytest -m slow
pytest -m "not slow"
pytest -m "slow and integration"

# Run last failed tests
pytest --lf  # or --last-failed

# Run failed tests first, then others
pytest --ff  # or --failed-first

# Run new tests first (based on file modification time)
pytest --nf  # or --new-first
```

## Output Control

```bash
# Verbosity levels
pytest -v          # Verbose
pytest -vv         # More verbose (shows diffs in full)
pytest -q          # Quiet
pytest -qq         # Very quiet

# Show local variables in tracebacks
pytest --showlocals
pytest -l  # Short form

# Traceback modes
pytest --tb=long   # Detailed traceback (default for first/last)
pytest --tb=short  # Shorter traceback
pytest --tb=line   # One line per failure
pytest --tb=native # Python standard library format
pytest --tb=no     # No traceback

# Show extra test summary info
pytest -r chars
# chars can be:
#   f - failed
#   E - error
#   s - skipped
#   x - xfailed
#   X - xpassed
#   p - passed
#   P - passed with output
#   a - all except passed
#   A - all
# Example: pytest -rA  # Show all
```

## Test Execution Control

```bash
# Stop after first failure
pytest -x  # or --exitfirst

# Stop after N failures
pytest --maxfail=3

# Run tests in parallel (requires pytest-xdist)
pytest -n 4          # 4 workers
pytest -n auto       # Auto-detect CPU count

# Run tests in random order (requires pytest-randomly)
pytest --randomly-seed=12345

# Timeout tests (requires pytest-timeout)
pytest --timeout=300         # Global timeout
pytest --timeout-method=thread

# Disable output capture (print statements visible)
pytest -s  # or --capture=no

# Set timeout for hanging tests
pytest --durations=10  # Show 10 slowest tests
pytest --durations=0   # Show all durations

# Run in debug mode
pytest --pdb                    # Drop to debugger on failure
pytest --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb  # Use IPython

# Trace execution
pytest --trace  # Drop to debugger at start of each test

# Step-through mode
pytest --stepwise              # Stop at first failure, resume from there next run
pytest --stepwise-skip         # Like --stepwise but skip first failure
```

## Logging

```bash
# Console logging
pytest --log-cli-level=DEBUG
pytest --log-cli-level=INFO
pytest --log-cli-format="%(levelname)s %(name)s: %(message)s"
pytest --log-cli-date-format="%Y-%m-%d %H:%M:%S"

# File logging
pytest --log-file=pytest.log
pytest --log-file-level=DEBUG
pytest --log-file-format="%(asctime)s [%(levelname)s] %(message)s"
pytest --log-file-date-format="%Y-%m-%d %H:%M:%S"

# Disable specific loggers
pytest --log-disable=urllib3
pytest --log-disable=requests
```

## Coverage (requires pytest-cov)

```bash
# Basic coverage
pytest --cov=mypackage

# Coverage with HTML report
pytest --cov=mypackage --cov-report=html

# Coverage report types
pytest --cov-report=term        # Terminal report
pytest --cov-report=term-missing  # Show missing lines
pytest --cov-report=html        # HTML report
pytest --cov-report=xml         # XML report
pytest --cov-report=json        # JSON report

# Fail if coverage below threshold
pytest --cov=mypackage --cov-fail-under=80

# Show missing lines
pytest --cov=mypackage --cov-report=term-missing
```

## Markers

```bash
# List all markers
pytest --markers

# Strict marker checking (fail on unknown markers)
pytest --strict-markers

# Register marker in pyproject.toml first:
# markers = [
#     "slow: marks slow tests",
# ]
```

## Fixtures

```bash
# Show available fixtures
pytest --fixtures

# Show where fixtures are defined
pytest --fixtures -v

# Setup show (show fixture setup/teardown)
pytest --setup-show
```

## Collection

```bash
# Collect tests without running
pytest --collect-only

# Show test collection tree
pytest --collect-only -q

# Ignore paths during collection
pytest --ignore=tests/legacy/
pytest --ignore-glob='**/legacy/*'

# Deselect tests by node ID
pytest --deselect=tests/test_slow.py::test_integration
```

## Warnings

```bash
# Show all warnings
pytest -W all

# Treat warnings as errors
pytest -W error

# Ignore specific warnings
pytest -W ignore::DeprecationWarning
pytest -W ignore::UserWarning:mymodule

# Show warnings summary
pytest --strict-warnings  # Fail if warnings present
```

## Cache

```bash
# Show cache contents
pytest --cache-show

# Clear cache
pytest --cache-clear

# Disable cache
pytest -p no:cacheprovider
```

## Plugins

```bash
# List plugins
pytest --version  # Shows pytest version and plugins
pytest -VV        # Verbose plugin info

# Disable specific plugin
pytest -p no:warnings
pytest -p no:cacheprovider
pytest -p no:doctest

# Load specific plugin
pytest -p myplugin
```

## Configuration

```bash
# Override config options
pytest -o timeout=300
pytest -o markers="slow: slow tests"

# Show configuration
pytest --co  # Show collection only
pytest --collect-only

# Specify root directory
pytest --rootdir=/path/to/project

# Use specific config file
pytest -c /path/to/pytest.ini
```

## Reporting

```bash
# JUnit XML output
pytest --junitxml=report.xml

# HTML report (requires pytest-html)
pytest --html=report.html

# JSON report (requires pytest-json-report)
pytest --json-report --json-report-file=report.json

# Quiet mode with short summary
pytest -q -ra
```

## Common Combinations

```bash
# Development: verbose, show locals, stop on first failure
pytest -vvs -l -x

# CI: coverage, JUnit XML, fail under threshold
pytest --cov=myapp --cov-fail-under=80 --junitxml=report.xml

# Debug specific test
pytest -vvs --pdb tests/test_module.py::test_function

# Quick smoke test
pytest -m smoke -x

# Full test with coverage and duration report
pytest --cov=myapp --cov-report=html --durations=10

# Parallel execution with live logging
pytest -n auto --log-cli-level=INFO

# Re-run failures from last run
pytest --lf -vv
```

## Environment Variables

```bash
# Add CLI options
export PYTEST_ADDOPTS="-v --tb=short"
pytest  # Runs with -v --tb=short automatically

# Disable color
export PYTEST_THEME=none
export NO_COLOR=1
```

## Custom Options

Add custom options in conftest.py:

```python
def pytest_addoption(parser):
    parser.addoption(
        "--env",
        action="store",
        default="dev",
        help="Environment to test against"
    )

@pytest.fixture
def env(request):
    return request.config.getoption("--env")
```

Then use:
```bash
pytest --env=prod
```

## Performance Tips

```bash
# Fastest: parallel, stop on failure, no cov
pytest -n auto -x

# Fast feedback loop during development
pytest -x --lf -vvs

# Full CI run
pytest -n auto --cov=myapp --cov-fail-under=80 --junitxml=report.xml
```
