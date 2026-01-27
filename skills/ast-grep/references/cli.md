# CLI Commands Reference

## ast-grep run

Execute one-time pattern searches and rewrites.

### Basic Usage

```bash
ast-grep run -p 'pattern'
ast-grep run -p 'pattern' -r 'replacement'
```

### Common Options

**Pattern and replacement:**
```bash
ast-grep run -p 'console.log($M)' -r 'logger.info($M)'
```

**Specify language:**
```bash
ast-grep run -p 'pattern' -l javascript
```

**Limit to files:**
```bash
ast-grep run -p 'pattern' src/
ast-grep run -p 'pattern' file1.js file2.js
```

**Debug pattern AST:**
```bash
ast-grep run -p 'pattern' --debug-query
```

### Output Options

**JSON format:**
```bash
ast-grep run -p 'pattern' --json
ast-grep run -p 'pattern' --json=compact
```

**Context lines:**
```bash
ast-grep run -p 'pattern' -C 3  # 3 lines before and after
ast-grep run -p 'pattern' -B 2 -A 4  # 2 before, 4 after
```

**Color control:**
```bash
ast-grep run -p 'pattern' --color never
```

### Interactive Mode

```bash
ast-grep run -p 'pattern' -r 'fix' -i
# Review each match:
# y - apply change
# n - skip
# e - edit in editor
# q - quit
```

### Update All

```bash
ast-grep run -p 'pattern' -r 'fix' -U
# Apply all changes without confirmation
```

### StdIn Mode

```bash
echo "code" | ast-grep run -p 'pattern' --stdin -l python
curl url | ast-grep run -p 'pattern' --stdin -l html
```

## ast-grep scan

Scan project with configured rules.

### Basic Usage

```bash
ast-grep scan  # Use sgconfig.yml
ast-grep scan -r rule.yml  # Single rule
ast-grep scan --inline-rules 'rule: {pattern: console.log($$$)}'
```

### Rule Filtering

```bash
ast-grep scan --filter 'no-*'  # Rules matching pattern
ast-grep scan --filter 'security/*'
```

### Severity Control

```bash
ast-grep scan --error  # All rules as errors
ast-grep scan --error=critical-rule --warning=minor-rule
ast-grep scan --off=noisy-rule
```

### Output Formats

**Rich (default):**
```bash
ast-grep scan
```

**Medium:**
```bash
ast-grep scan --report-style medium
```

**Short:**
```bash
ast-grep scan --report-style short
```

**JSON:**
```bash
ast-grep scan --json
ast-grep scan --json=stream  # One per line
```

**SARIF:**
```bash
ast-grep scan --format sarif > results.sarif
```

**GitHub Actions:**
```bash
ast-grep scan --format github
```

### File Filtering

**Include patterns:**
```bash
ast-grep scan --globs '*.js' --globs '*.ts'
```

**Ignore patterns:**
```bash
ast-grep scan --no-ignore hidden
ast-grep scan --no-ignore vcs  # Ignore .gitignore
```

## ast-grep test

Test rule configurations.

### Basic Usage

```bash
ast-grep test  # Run all tests
ast-grep test -f 'pattern'  # Filter tests
```

### Snapshot Management

```bash
ast-grep test -U  # Update all snapshots
ast-grep test -i  # Interactive update
ast-grep test --skip-snapshot-tests  # Skip output checks
```

### Test Configuration

```bash
ast-grep test -c config.yml
ast-grep test -t test-dir
ast-grep test --snapshot-dir snapshots
```

## ast-grep new

Create project scaffolding.

### Project Setup

```bash
ast-grep new project
ast-grep new project -b /path/to/create
```

### Create Rule

```bash
ast-grep new rule
ast-grep new rule -l javascript
ast-grep new rule rule-name -l python -y  # No prompts
```

### Create Test

```bash
ast-grep new test
ast-grep new test test-name -y
```

### Create Util

```bash
ast-grep new util
ast-grep new util util-name -l rust -y
```

## ast-grep lsp

Language server for editor integration.

```bash
ast-grep lsp  # Default port
ast-grep lsp -c custom-config.yml
```

## ast-grep completions

Generate shell completions.

```bash
ast-grep completions bash > /etc/bash_completion.d/ast-grep
ast-grep completions zsh > ~/.zsh/completion/_ast-grep
ast-grep completions fish > ~/.config/fish/completions/ast-grep.fish
```

## Advanced Usage

### Parallel Processing

```bash
ast-grep scan -j 8  # Use 8 threads
ast-grep run -p 'pattern' -j 4
```

### Follow Symlinks

```bash
ast-grep scan --follow
```

### Ignore Files

```bash
ast-grep scan --no-ignore hidden
ast-grep scan --no-ignore dot
ast-grep scan --no-ignore vcs
```

### Inspection

```bash
ast-grep scan --inspect summary
ast-grep scan --inspect entity
```

## Common Workflows

### Quick Search

```bash
ast-grep run -p 'pattern' | less
```

### Apply Codemod

```bash
ast-grep run -p 'old' -r 'new' -U
```

### Find and Review

```bash
ast-grep run -p 'pattern' -i
```

### Rule Development

```bash
# Test pattern
ast-grep run -p 'pattern' --debug-query

# Apply to file
ast-grep run -p 'pattern' file.js

# Convert to rule
ast-grep new rule

# Test rule
ast-grep test -U

# Apply rule
ast-grep scan -r rule.yml -i
```

### CI/CD Integration

```bash
# Lint in CI
ast-grep scan --json > results.json

# Strict mode (fail on any match)
ast-grep scan || exit 1

# Generate SARIF
ast-grep scan --format sarif > sarif.json
```

### Large Codebase

```bash
# Parallel scan
ast-grep scan -j 16

# Specific directories
ast-grep scan src/ lib/ app/

# With filters
ast-grep scan --filter 'critical-*' --error
```

## Environment Variables

```bash
# No colors
NO_COLOR=1 ast-grep scan

# Custom config
AST_GREP_CONFIG=/path/to/config.yml ast-grep scan
```

## Exit Codes

**ast-grep run:**
- 0: At least one match found
- 1: No matches found

**ast-grep scan:**
- 0: No rule violations
- 1: Rule violations found

**ast-grep test:**
- 0: All tests passed
- 1: Test failures

## Troubleshooting

### Debug Pattern Issues

```bash
# View pattern AST
ast-grep run -p 'pattern' --debug-query

# Try different strictness
ast-grep run -p 'pattern' --strictness cst
ast-grep run -p 'pattern' --strictness relaxed
```

### Performance Issues

```bash
# Reduce threads
ast-grep scan -j 2

# Limit file scope
ast-grep scan src/ --globs '*.js'

# Skip gitignore
ast-grep scan --no-ignore vcs
```

### No Matches

```bash
# Check language
ast-grep run -p 'pattern' -l javascript

# Verify file parsing
ast-grep run -p '$A' file.js  # Should match anything

# Debug with simple pattern
ast-grep run -k identifier file.js
```
