from main import main


def test_main_returns_hello():
    """Test that main function returns 'Hello'"""
    result = main()
    assert result == "Hello"
    print(f"✓ main() returned: '{result}'")


def test_main_returns_string():
    """Test that main function returns a string type"""
    result = main()
    assert isinstance(result, str)
    print(f"✓ main() returned a string: {type(result)}")


def test_main_returns_non_empty():
    """Test that main function returns a non-empty string"""
    result = main()
    assert result != ""
    assert len(result) > 0
    print(f"✓ main() returned non-empty string of length: {len(result)}")
