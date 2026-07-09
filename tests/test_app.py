from openadmindesk.app import main


def test_main_returns_success() -> None:
    assert main() == 0

