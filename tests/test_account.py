"""Tests for account model."""

from openadmindesk.core.account import Account


def test_account_creation() -> None:
    """Test account creation."""
    account = Account(
        name="Test Account",
        username="testuser",
        password="password123",
        host="example.com"
    )
    
    assert account.name == "Test Account"
    assert account.username == "testuser"
    assert account.password == "password123"
    assert account.host == "example.com"
    assert account.id is not None


def test_account_validation() -> None:
    """Test account validation."""
    # Valid account
    account = Account(
        name="Test Account",
        username="testuser",
        password="password123",
        host="example.com"
    )
    
    assert account.is_valid()
    
    # Invalid account - no name
    account_no_name = Account(
        name="",
        username="testuser",
        password="password123",
        host="example.com"
    )
    
    assert not account_no_name.is_valid()
    
    # Invalid account - no username
    account_no_username = Account(
        name="Test Account",
        username="",
        password="password123",
        host="example.com"
    )
    
    assert not account_no_username.is_valid()
    
    # Invalid account - no host
    account_no_host = Account(
        name="Test Account",
        username="testuser",
        password="password123",
        host=""
    )
    
    assert not account_no_host.is_valid()