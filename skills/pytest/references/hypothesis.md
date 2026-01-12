# Property-Based Testing with Hypothesis

**Hypothesis is optional but powerful.** Use it when you need confidence that your code handles all edge cases, not just the examples you thought of.

Traditional parametrized tests check specific cases. Hypothesis generates hundreds of test cases automatically, including edge cases you didn't consider, then shrinks failures to minimal examples.

```bash
pip install hypothesis
```

## Basic Usage

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

## Built-in Strategies

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

## st.builds: Generate Class Instances

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

## Composite Strategies: Dependent Data

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

## Chaining Strategies

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

## Integration with Pytest

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

## When to Use Hypothesis

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

## Debugging Hypothesis Failures

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
