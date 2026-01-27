# Pattern Syntax Reference

## Metavariables

### Single Node Capture

`$VAR` matches exactly one AST node:

```yaml
pattern: function $NAME() {}
# Matches: function foo() {}
# $NAME = foo
```

### Multiple Node Capture

`$$$VAR` matches zero or more nodes:

```yaml
pattern: array($$$ITEMS)
# Matches: array(1, 2, 3)
# $$$ITEMS = 1, 2, 3
```

### Anonymous Metavariables

Use `$_` or `$$$_` when you don't need the captured value:

```yaml
pattern: console.log($_)
# Matches any console.log call, ignores argument
```

## Pattern Context

### Basic Context

When pattern is ambiguous, provide context:

```yaml
pattern:
  context: 'class A { $FIELD = $INIT }'
  selector: field_definition
```

### Context Use Cases

**JavaScript class fields:**
```yaml
# Without context: parsed as assignment
# With context: parsed as field_definition
pattern:
  context: 'class A { $FIELD = $VALUE }'
  selector: field_definition
```

**Go function calls:**
```yaml
pattern:
  context: '$FUNC($$$);'
  selector: call_expression
```

**Rust function parameters:**
```yaml
pattern:
  context: 'fn f($PARAM) {}'
  selector: parameter
```

## Strictness Modes

Control how strictly patterns match:

### `cst` (Concrete Syntax Tree)
All nodes including punctuation must match:
```yaml
rule:
  pattern:
    context: 'function $F() {}'
    strictness: cst
# Only matches: function foo() {}
# Not: async function foo() {}
```

### `smart` (Default)
Skip unnamed nodes in target, all pattern nodes must match:
```yaml
rule:
  pattern: function $F() {}
# Matches: function foo() {}
# Matches: async function foo() {}
# The 'async' is an unnamed node, so it's skipped
```

### `ast` (Abstract Syntax Tree)
Only named nodes in both pattern and target:
```yaml
rule:
  pattern:
    context: 'function $F() {}'
    strictness: ast
# More lenient matching of function structures
```

### `relaxed`
Named nodes only, ignores comments:
```yaml
rule:
  pattern:
    context: '$CODE'
    strictness: relaxed
# Matches code with or without comments
```

### `signature`
Only node kinds, ignores text:
```yaml
rule:
  pattern:
    context: 'function $F($P) {}'
    strictness: signature
# Matches any function regardless of name/parameter names
```

## Special Patterns

### Nested Captures

Capture nested structures:
```yaml
pattern: if ($COND) { return $RET; }
# $COND captures the condition
# $RET captures the return value
```

### Field Access

Match specific fields:
```yaml
pattern: $OBJ.$PROP
constraints:
  PROP: { regex: '^get|set' }
```

### Method Calls

Chain matching:
```yaml
pattern: $OBJ.$METHOD1().$METHOD2($ARG)
```

### Destructuring

Match destructured patterns:
```yaml
pattern: 'const { $KEY } = $OBJ'
pattern: 'const [$FIRST, $$$REST] = $ARR'
```

## Language-Specific Patterns

### JavaScript/TypeScript

**Arrow functions:**
```yaml
pattern: ($$$PARAMS) => $BODY
```

**Template literals:**
```yaml
pattern: '`${$EXPR}`'
```

**Spread operator:**
```yaml
pattern: [...$ARR]
```

**JSX elements:**
```yaml
pattern: <$TAG $$$ATTRS>$$$CHILDREN</$TAG>
```

### Python

**List comprehensions:**
```yaml
pattern: '[$EXPR for $VAR in $ITER]'
```

**Decorators:**
```yaml
pattern: |
  @$DECORATOR
  def $FUNC(): $$$BODY
```

**Context managers:**
```yaml
pattern: 'with $CTX as $VAR: $$$BODY'
```

### Rust

**Match expressions:**
```yaml
pattern: |
  match $EXPR {
    $$$ARMS
  }
```

**Lifetimes:**
```yaml
pattern: "fn $F<'$L>($$$) -> &'$L $T"
```

### Go

**Defer statements:**
```yaml
pattern: defer $FUNC($$$)
```

**Goroutines:**
```yaml
pattern: go $FUNC($$$)
```

## Pattern Pitfalls

### Avoid Over-Specificity

❌ **Too specific:**
```yaml
pattern: const foo = 123
```

✅ **Better:**
```yaml
pattern: const $VAR = $VALUE
```

### Handle Multiple Forms

❌ **Single form:**
```yaml
pattern: function $F() {}
```

✅ **Multiple forms:**
```yaml
any:
  - pattern: function $F() {}
  - pattern: const $F = () => {}
  - pattern: const $F = function() {}
```

### Use Ellipsis for Lists

❌ **Fixed count:**
```yaml
pattern: fn($A, $B, $C)
```

✅ **Variable count:**
```yaml
pattern: fn($$$ARGS)
```

## Debugging Patterns

### View Pattern AST

```bash
ast-grep run -p 'your pattern' --debug-query
```

### Test in Playground

Use ast-grep playground to visualize AST:
https://ast-grep.github.io/playground.html

### Common Issues

**Pattern doesn't match:**
1. Check AST structure with `--debug-query`
2. Verify node kinds in playground
3. Try different strictness levels
4. Use pattern context if needed

**Too many matches:**
1. Add constraints on metavariables
2. Use relational rules (inside, has)
3. Make pattern more specific
