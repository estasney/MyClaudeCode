# Rule Configuration Reference

## YAML Structure

```yaml
id: unique-rule-id
language: JavaScript
severity: error
message: Error message with $METAVAR
note: |
  Detailed explanation in Markdown.
  Can use multiple lines.
rule:
  pattern: code pattern
constraints:
  METAVAR: { constraint rules }
transform:
  NEW_VAR: transformation
fix: replacement code
```

## Rule Components

### Atomic Rules

**pattern:**
```yaml
rule:
  pattern: console.log($MSG)
```

**kind:**
```yaml
rule:
  kind: function_declaration
```

**regex:**
```yaml
rule:
  regex: 'console\.(log|warn|error)'
```

**nthChild:**
```yaml
rule:
  kind: number
  nthChild: 2  # Second child
```

**range:**
```yaml
rule:
  range:
    start: { line: 0, column: 0 }
    end: { line: 5, column: 10 }
```

### Relational Rules

**inside:**
```yaml
rule:
  pattern: this.$PROP
  inside:
    kind: method_definition
```

**has:**
```yaml
rule:
  kind: function_declaration
  has:
    kind: return_statement
```

**precedes:**
```yaml
rule:
  pattern: const $A = $B
  precedes:
    pattern: $A.use()
```

**follows:**
```yaml
rule:
  pattern: $VAR.finalize()
  follows:
    pattern: $VAR.init()
```

### Composite Rules

**all:**
```yaml
rule:
  all:
    - pattern: $FN($$$)
    - inside: { kind: try_statement }
    - not: { inside: { kind: catch_clause } }
```

**any:**
```yaml
rule:
  any:
    - pattern: var $V = $I
    - pattern: let $V = $I
    - pattern: const $V = $I
```

**not:**
```yaml
rule:
  kind: function_declaration
  not:
    has:
      kind: return_statement
```

**matches:**
```yaml
utils:
  is-async:
    kind: function_declaration
    has:
      kind: async

rule:
  pattern: $FN()
  matches: is-async
```

## Constraints

Refine metavariable matches:

### Kind Constraint

```yaml
constraints:
  ARG: { kind: string_literal }
```

### Regex Constraint

```yaml
constraints:
  NAME:
    regex: '^test'
```

### Pattern Constraint

```yaml
constraints:
  INIT:
    pattern: new $CLASS($$$)
```

### Combined Constraints

```yaml
constraints:
  METHOD:
    any:
      - regex: '^get'
      - regex: '^set'
```

## Transformations

Modify metavariables before using in fix:

### substring

```yaml
transform:
  TRIMMED:
    substring:
      source: $VAR
      startChar: 1
      endChar: -1
```

### replace

```yaml
transform:
  CLEANED:
    replace:
      source: $TEXT
      replace: 'old'
      by: 'new'
```

### convert

```yaml
transform:
  UPPER:
    convert:
      source: $NAME
      toCase: upperCase
```

Options: `lowerCase`, `upperCase`, `capitalize`, `camelCase`, `pascalCase`, `snakeCase`, `kebabCase`

### rewrite

```yaml
transform:
  WRAPPED:
    rewrite:
      rewriters:
        - id: wrap
          rule: { pattern: $CODE }
          fix: '($CODE)'
```

### String Form (v0.38.3+)

```yaml
transform:
  TRIMMED: substring($VAR, startChar=1, endChar=-1)
  UPPER: convert($NAME, toCase=upperCase)
```

### Conditional Text

Add text only when metavar matches:

```yaml
transform:
  COMMA:
    replace:
      source: $$$ARGS
      replace: '^.+'
      by: ', '
fix: fn(newArg$COMMA$$$ARGS)
```

## Fix Configurations

### Simple Fix

```yaml
fix: logger.log($MSG)
```

### Fix with Expand

```yaml
fix:
  template: logger.log($MSG)
  expandEnd: rule
```

Options: `end`, `rule`, `neighbor`

## Utility Rules

### Local Utils

```yaml
utils:
  has-await:
    kind: await_expression
  in-async:
    kind: arrow_function
    has:
      kind: async

rule:
  pattern: $FN($$$)
  matches: has-await
  inside:
    matches: in-async
```

### Global Utils

File: `utils/common.yml`
```yaml
id: is-promise
language: JavaScript
rule:
  pattern: $EXPR.then($$$)
```

Usage in rule:
```yaml
rule:
  pattern: $VAR = $INIT
  constraints:
    INIT:
      matches: is-promise
```

## Rewriters

Complex transformations:

```yaml
rewriters:
  - id: remove-console
    rule:
      pattern: console.$METHOD($$$)
    fix: ''
  
  - id: await-async
    rule:
      pattern: $FN($$$)
      constraints:
        FN:
          matches: is-promise
    fix: await $FN($$$)

fix:
  rewriters:
    - remove-console
    - await-async
  source: $CODE
```

## Metadata

### Basic Metadata

```yaml
id: no-console
language: JavaScript
severity: error
url: https://example.com/rules/no-console
```

Severity options: `error`, `warning`, `info`, `hint`, `off`

### Rich Messages

```yaml
message: Unexpected $METHOD call
note: |
  Console methods should not be used in production.
  Use a proper logging library instead.

labels:
  METHOD:
    style: primary
    message: This method should be replaced
```

Label styles: `primary`, `secondary`

### Custom Metadata

```yaml
metadata:
  category: best-practices
  tags: [console, logging]
  author: team-name
  since: 2024-01-01
```

## File Filtering

### Include Files

```yaml
files:
  - 'src/**/*.js'
  - 'lib/**/*.ts'
```

Case-insensitive:
```yaml
files:
  - glob: 'README.md'
    caseInsensitive: true
```

### Ignore Files

```yaml
ignores:
  - 'test/**'
  - '**/*.test.js'
  - 'node_modules/**'
```

## Multiple Rules

Separate with `---`:

```yaml
id: no-var
rule:
  pattern: var $V = $I
fix: let $V = $I
---
id: no-function
rule:
  pattern: function $F() { $$$B }
fix: const $F = () => { $$$B }
```

## Advanced Patterns

### Nested Matching

```yaml
rule:
  pattern: if ($COND) { $$$BODY }
  has:
    pattern: throw new Error($MSG)
  not:
    has:
      kind: catch_clause
```

### Field-Specific Rules

```yaml
rule:
  kind: object
  has:
    field: key
    pattern: $KEY
    constraints:
      KEY:
        regex: '^data'
```

### Contextual Constraints

```yaml
rule:
  pattern: $OBJ.$METHOD($$$)
  inside:
    all:
      - kind: class_body
      - has:
          kind: decorator
          pattern: '@Component'
```

## Testing Rules

### Test Structure

```yaml
id: test-no-console
rule:
  pattern: console.log($$$)
---
valid:
  - logger.info('test')
  - print('test')

invalid:
  - console.log('test')
  - console.log('a', 'b')
```

### Snapshot Testing

```bash
ast-grep test  # Run tests
ast-grep test -U  # Update snapshots
ast-grep test -i  # Interactive mode
```

## Common Rule Patterns

### Require Await in Async

```yaml
rule:
  kind: arrow_function
  has:
    kind: async
  not:
    has:
      kind: await_expression
```

### No Shadow Variables

```yaml
rule:
  pattern: let $V = $I
  inside:
    any:
      - kind: function_declaration
      - kind: arrow_function
    has:
      pattern: let $V = $_
```

### Enforce Type Annotations

```yaml
rule:
  pattern: function $F($$$PARAMS) { $$$BODY }
  not:
    has:
      kind: type_annotation
```

### Deprecated API Usage

```yaml
rule:
  pattern: $OBJ.$METHOD($$$)
  constraints:
    METHOD:
      regex: '^(deprecated|legacy)'
```
