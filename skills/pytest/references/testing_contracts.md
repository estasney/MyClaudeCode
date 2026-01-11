# Testing Contracts: What to Test

## Core Principle

Test the **contracts**, not the implementation. A contract is the public interface and behavior guarantees your code makes to its consumers.

## What Are Contracts?

Contracts define:
- **Input expectations**: What arguments/data the code accepts
- **Output guarantees**: What the code returns or produces
- **Side effects**: What state changes occur (database writes, file operations, API calls)
- **Error conditions**: What exceptions are raised under what circumstances
- **Invariants**: Properties that must always hold true

## Concrete Examples

### Example 1: Function Contract

```python
def calculate_discount(price: float, discount_percent: float) -> float:
    """Apply discount to price.
    
    Contract:
    - Input: price >= 0, discount_percent in [0, 100]
    - Output: discounted price (price * (1 - discount_percent/100))
    - Raises: ValueError if inputs invalid
    """
```

**Test the contract:**
```python
@pytest.mark.parametrize('price,discount', [
    (100, 10),
    (50, 20),
    (200, 0),
])
def test_calculate_discount_normal_case(price, discount):
    expected = price * (1 - discount / 100)
    assert calculate_discount(price, discount) == expected

@pytest.mark.parametrize('price,discount', [
    (100, 150),
    (100, -10),
])
def test_calculate_discount_invalid_percent(price, discount):
    # Test contract: ValueError raised for invalid input
    # Don't test error message - that's implementation detail
    with pytest.raises(ValueError):
        calculate_discount(price, discount)
```

**Don't test implementation details:**
```python
# BAD: Testing internal calculation method
def test_uses_multiplication():
    # This breaks when you refactor internal logic
    assert "price * (1 - discount_percent/100)" in inspect.getsource(calculate_discount)
```

### Example 2: Class Contract

```python
class ShoppingCart:
    """Shopping cart manages items and total.
    
    Contract:
    - add_item(item): adds item to cart
    - remove_item(item_id): removes item, raises ValueError if not found
    - get_total(): returns sum of all item prices
    - items property: returns list of items
    """
```

**Test the contract:**
```python
@pytest.mark.parametrize('items,expected_total', [
    ([Item("Book", 10.00), Item("Pen", 2.50)], 12.50),
    ([Item("Laptop", 999.99)], 999.99),
    ([], 0.0),
])
def test_cart_add_and_total(items, expected_total):
    cart = ShoppingCart()
    for item in items:
        cart.add_item(item)
    
    assert cart.get_total() == expected_total
    assert len(cart.items) == len(items)

def test_cart_remove_nonexistent_raises():
    cart = ShoppingCart()
    with pytest.raises(ValueError):
        cart.remove_item("nonexistent")
```

**Don't test:**
```python
# BAD: Testing internal data structure choice
def test_cart_uses_list():
    cart = ShoppingCart()
    assert isinstance(cart._items, list)  # Internal detail
```

### Example 3: API Integration Contract

```python
class PaymentProcessor:
    """Process payments via external API.
    
    Contract:
    - charge(amount, card): returns transaction_id on success
    - charge(): raises PaymentError on failure
    - charge(): records transaction in database
    """
```

**Test the contract using mocks:**
```python
def test_charge_success_returns_transaction_id(mocker):
    # Mock external API
    mock_api = mocker.patch('payment.api.charge')
    mock_api.return_value = {'transaction_id': 'txn_123'}
    
    processor = PaymentProcessor()
    txn_id = processor.charge(100.00, card_token="tok_123")
    
    assert txn_id == 'txn_123'
    mock_api.assert_called_once_with(100.00, "tok_123")

def test_charge_failure_raises_payment_error(mocker):
    mock_api = mocker.patch('payment.api.charge')
    mock_api.side_effect = APIError("Card declined")
    
    processor = PaymentProcessor()
    with pytest.raises(PaymentError, match="Card declined"):
        processor.charge(100.00, card_token="tok_123")

def test_charge_records_transaction(mocker, db_session):
    mock_api = mocker.patch('payment.api.charge')
    mock_api.return_value = {'transaction_id': 'txn_123'}
    
    processor = PaymentProcessor(db_session)
    processor.charge(100.00, card_token="tok_123")
    
    # Verify side effect: transaction recorded
    txn = db_session.query(Transaction).filter_by(id='txn_123').first()
    assert txn is not None
    assert txn.amount == 100.00
```

## Red Flags: You're Probably NOT Testing Contracts If...

1. **Test breaks when refactoring without changing behavior**
   - If you rename a private method and tests fail, you're testing implementation

2. **Test depends on internal state inspection**
   - Accessing `._private_attribute` in tests is usually wrong

3. **Test duplicates the production code logic**
   - If test contains same calculation as code, it's not validating behavior

4. **Test is tightly coupled to framework internals**
   - Testing that Django uses a specific ORM method instead of testing query results

## Guidelines

1. **Focus on boundaries**: Test inputs, outputs, exceptions, side effects
2. **Use black-box thinking**: Test from consumer perspective
3. **Mock external dependencies**: Database, APIs, file system
4. **Test error paths**: Not just happy path
5. **Test exception types, not messages**: Error messages are implementation details that change frequently. The contract is that `ValueError` is raised, not what it says.
6. **Verify side effects**: Database writes, file creation, API calls
7. **Keep tests independent**: One test shouldn't rely on another's state
