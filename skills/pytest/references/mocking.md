# Mocking with pytest-mock

`pytest-mock` provides the `mocker` fixture, wrapping `unittest.mock`. Use mocking to isolate units under test from external dependencies (databases, APIs, file systems).

## When to Mock

Mock external dependencies:
- External API calls
- Database queries
- File system operations
- Time-dependent behavior
- Expensive computations
- Non-deterministic behavior

## When NOT to Mock

Don't mock:
- Internal implementation details of the unit under test
- Simple value objects
- Pure functions without side effects

## Basic Mocking

```python
@pytest.mark.parametrize('side_effects,expected_result,expected_calls', [
    ([Timeout("Connection timeout"), Mock(status_code=200, json=lambda: {'data': 'success'})], 
     {'data': 'success'}, 2),
    ([Mock(status_code=200, json=lambda: {'data': 'first_try'})], 
     {'data': 'first_try'}, 1),
])
def test_api_call_retry_logic(mocker, side_effects, expected_result, expected_calls):
    # Mock external API
    mock_requests = mocker.patch('myapp.requests.get')
    # Convert Mock objects in side_effects to mocker.Mock
    mock_requests.side_effect = [
        se if isinstance(se, Exception) else mocker.Mock(status_code=se.status_code, json=se.json)
        for se in side_effects
    ]
    
    client = APIClient()
    result = client.fetch_with_retry(url="https://api.example.com")
    
    assert result == expected_result, f"Expected {expected_result}, got {result}"
    assert mock_requests.call_count == expected_calls, \
        f"Expected {expected_calls} attempts, got {mock_requests.call_count}"
```

## MagicMock Auto-generation

MagicMock automatically creates attributes and methods on access:

```python
@pytest.mark.parametrize('user_id,expected_name', [
    (1, 'Alice'),
    (2, 'Bob'),
])
def test_user_service_integration(mocker, user_id, expected_name):
    # MagicMock auto-generates .query(), .filter(), .first() chain
    mock_db = mocker.MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = \
        User(id=user_id, name=expected_name)
    
    service = UserService(mock_db)
    user = service.get_user_by_id(user_id)
    
    assert user.name == expected_name, f"Expected user {expected_name}, got {user.name}"
    mock_db.query.assert_called_once_with(User)
    mock_db.query.return_value.filter.assert_called_once()
```

## Return Value vs Side Effect

```python
def test_mock_patterns(mocker):
    mock = mocker.MagicMock()
    
    # return_value: same result every call
    mock.get_price.return_value = 100
    assert mock.get_price() == 100
    assert mock.get_price() == 100
    
    # side_effect: different result per call (list)
    mock.get_stock.side_effect = [50, 40, 30]
    assert mock.get_stock() == 50
    assert mock.get_stock() == 40
    assert mock.get_stock() == 30
    
    # side_effect: raise exception
    mock.delete_user.side_effect = PermissionError("Access denied")
    with pytest.raises(PermissionError):
        mock.delete_user()
```

## Spy Pattern (Partial Mock)

Use spies when you need to verify calls to real functions:

```python
@pytest.mark.parametrize('input_value,expected_calls', [
    (5, 1),  # First call
    (5, 1),  # Cached, same input
])
def test_cache_decorator_calls_function(mocker, input_value, expected_calls):
    # Real function, but spy on calls
    spy = mocker.spy(myapp, 'expensive_calculation')
    
    @cache
    def cached_calculation(x):
        return expensive_calculation(x)
    
    # Clear cache before each test to ensure independence
    cached_calculation.cache_clear()
    
    result1 = cached_calculation(input_value)
    result2 = cached_calculation(input_value)  # Should use cache
    
    assert spy.call_count == expected_calls, \
        f"Expected {expected_calls} call(s) (cached 2nd time), got {spy.call_count}"
    assert result1 == result2, "Cache should return consistent results"
```

## Mock Assertions

```python
@pytest.mark.parametrize('user_id,email,expected_subject', [
    (1, 'test@example.com', 'Welcome'),
    (2, 'admin@example.com', 'Welcome'),
])
def test_mock_assertions(mocker, user_id, email, expected_subject):
    mock = mocker.MagicMock()
    
    service = EmailService(mock)
    service.send_welcome_email(user_id=user_id, email=email)
    
    # Verify call happened
    mock.send_email.assert_called_once()
    
    # Verify specific arguments
    mock.send_email.assert_called_with(
        to=email,
        subject=expected_subject,
        mocker.ANY  # Accept any value for body
    )
    
    # Verify call count
    assert mock.send_email.call_count == 1, \
        f"Expected 1 email, sent {mock.send_email.call_count}"
    
    # Access call arguments
    call_args = mock.send_email.call_args
    assert call_args.kwargs['to'] == email, \
        f"Expected email to {email}, got {call_args.kwargs['to']}"
```

### Common Assertion Methods

- `assert_called()`: Called at least once
- `assert_called_once()`: Called exactly once
- `assert_called_with(*args, **kwargs)`: Last call had these arguments
- `assert_called_once_with(*args, **kwargs)`: Only call had these arguments
- `assert_not_called()`: Never called
- `call_count`: Number of times called
- `call_args`: Arguments of last call
- `call_args_list`: All calls' arguments

## Combining Mocking with Fixtures

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

@pytest.mark.parametrize('total,status,expected_charged', [
    (100, 'pending', True),
    (50, 'paid', False),
])
def test_order_with_mock(make_order, total, status, expected_charged):
    order = make_order(total=total, status=status)
    if status == 'pending':
        result = order.process_payment()
        assert result is expected_charged
```
