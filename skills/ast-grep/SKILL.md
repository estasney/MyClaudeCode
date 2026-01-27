---
name: ast-grep
description: Pattern-based code searching and refactoring using abstract syntax tree (AST) matching. Use when searching for code patterns, performing code transformations, linting custom rules, or analyzing code structure across multiple files. Works with JavaScript, TypeScript, Python, Rust, Go, Java, C/C++, and 20+ other languages.
---

# AST Grep

## Quick Start

Basic pattern search:
```bash
ast-grep run -p 'console.log($ARG)'
```

Pattern with rewrite:
```bash
ast-grep run -p 'console.log($ARG)' -r 'logger.info($ARG)'
```

Apply rule from YAML file:
```bash
ast-grep scan -r rules/no-console.yml
```

## Core Capabilities

### Pattern Syntax

Patterns match AST nodes using metavariables:
- `$VAR` - matches single node
- `$$$ARGS` - matches multiple nodes (ellipsis)

```yaml
pattern: function $NAME($$$PARAMS) { $$$BODY }
```

### Rule Types

**Atomic Rules** - Basic matching:
- `pattern` - Match code structure
- `kind` - Match node type (e.g., `function_declaration`)
- `regex` - Match node text with regex

**Relational Rules** - Match based on context:
- `inside` - Node appears within another
- `has` - Node contains child
- `precedes` - Node comes before another
- `follows` - Node comes after another

**Composite Rules** - Combine rules:
- `all` - Node matches all conditions
- `any` - Node matches any condition
- `not` - Node doesn't match condition
- `matches` - Reuse utility rules

### Common Patterns

Match function without return type:
```yaml
rule:
  kind: arrow_function
  not:
    has:
      kind: type_annotation
```

Find nested callbacks:
```yaml
rule:
  pattern: $FN($$$, function($$$) { $$$ })
  inside:
    kind: call_expression
```

Match class methods:
```yaml
rule:
  pattern:
    context: 'class A { $METHOD() { $$$ } }'
    selector: method_definition
```

## YAML Configuration

Structure:
```yaml
id: rule-name
language: JavaScript
severity: error
message: Descriptive error message
rule:
  pattern: code pattern
fix: replacement code
```

With constraints:
```yaml
rule:
  pattern: $OBJ.$METHOD($ARG)
constraints:
  OBJ: { regex: '^(console|window)$' }
fix: logger.$METHOD($ARG)
```

With transformations:
```yaml
transform:
  UPPER_NAME:
    convert:
      source: $NAME
      toCase: upperCase
fix: const $UPPER_NAME = $VALUE
```

## Advanced Features

### Contextual Patterns

Use `context` and `selector` for ambiguous syntax:
```yaml
pattern:
  context: 'class A { $FIELD = $INIT }'
  selector: field_definition
```

### Strictness Levels

Control matching precision:
- `cst` - All nodes must match exactly
- `smart` - Skip unnamed nodes (default)
- `ast` - Only named nodes
- `relaxed` - Ignore comments
- `signature` - Only node kinds

### Multiple Rules per File

Separate with `---`:
```yaml
rule:
  pattern: var $A = $B
fix: const $A = $B
---
rule:
  pattern: function $F() {}
fix: const $F = () => {}
```

## CLI Workflow

Project setup:
```bash
ast-grep new project
ast-grep new rule --lang python
```

Scan with filters:
```bash
ast-grep scan --filter 'no-*'
ast-grep scan --error=critical-rule
```

Interactive mode:
```bash
ast-grep scan -i  # Review changes one by one
ast-grep run -p 'pattern' -r 'fix' -U  # Auto-apply all
```

JSON output:
```bash
ast-grep run -p 'pattern' --json | jq
```

## Testing Rules

Create test file:
```yaml
id: test-rule
rule:
  pattern: console.log($MSG)
---
valid:
  - logger.info('test')
invalid:
  - console.log('test')
```

Run tests:
```bash
ast-grep test
ast-grep test --update-all  # Update snapshots
```

## Language Support

Built-in: JavaScript, TypeScript, Python, Rust, Go, Java, C/C++, Ruby, Kotlin, Swift, Scala, Elixir, Lua, and more.

Check language name:
```bash
ast-grep run --lang help
```

## Advanced Resources

For complex patterns, rule composition, and language-specific features, see:
- [references/patterns.md](references/patterns.md) - Pattern syntax deep dive
- [references/rules.md](references/rules.md) - Rule configuration reference
- [references/cli.md](references/cli.md) - CLI commands and options
