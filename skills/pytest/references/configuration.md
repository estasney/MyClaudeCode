# Pytest Configuration

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

# Logging configuration
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

## Key Options

**`addopts`**: Always-applied CLI options. Runs every time pytest is invoked.

**`testpaths`**: Directories to search for tests. Speeds up collection.

**`markers`**: Declare custom markers. Required with `--strict-markers`.

**`pythonpath`**: Add to sys.path before running tests. Useful for src layouts.

**`filterwarnings`**: Control warning behavior. Can treat warnings as errors or ignore specific ones.

**`log_cli`**: Enable live logging during test execution.

**`log_file`**: Write logs to file for post-run analysis.

**`norecursedirs`**: Skip these directories during collection. Speeds up test discovery.
