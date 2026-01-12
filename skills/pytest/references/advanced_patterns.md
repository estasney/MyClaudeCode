# Advanced Pytest Patterns

## Fixture Factories

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

**Use factories when:**
- Multiple instances per test
- Varying attributes across instances
- Centralized cleanup logic
- Default values with override capability

## Indirect Parametrization

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

**`indirect=True` is essential when:**
- Parameters require resource setup/teardown
- Same fixture logic applies to different parameter sets
- Parameters need transformation before use
- Complex objects need construction from simple data

**Partial indirect for mixed parameters:**

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

## Combining Patterns

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
