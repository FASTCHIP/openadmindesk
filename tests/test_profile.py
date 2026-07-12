"""Tests for profile model."""

from openadmindesk.core.profile import Profile
from openadmindesk.core.profile_validation import validate_profile


def test_profile_creation() -> None:
    """Test profile creation."""
    profile = Profile(
        name="Test Server",
        host="example.com",
        port=22,
        username="user"
    )
    
    assert profile.name == "Test Server"
    assert profile.host == "example.com"
    assert profile.port == 22
    assert profile.username == "user"
    assert profile.is_valid()


def test_profile_validation() -> None:
    """Test profile validation."""
    # Valid profile
    profile = Profile(
        name="Test Server",
        host="example.com",
        port=22,
        username="user"
    )
    
    is_valid, error = validate_profile(profile)
    assert is_valid
    assert error is None
    
    # Invalid profile - no name
    profile_no_name = Profile(
        name="",
        host="example.com",
        port=22,
        username="user"
    )
    
    is_valid, error = validate_profile(profile_no_name)
    assert not is_valid
    assert error is not None
    
    # Invalid profile - no host
    profile_no_host = Profile(
        name="Test Server",
        host="",
        port=22,
        username="user"
    )
    
    is_valid, error = validate_profile(profile_no_host)
    assert not is_valid
    assert error is not None
    
    # Invalid profile - invalid host
    profile_invalid_host = Profile(
        name="Test Server",
        host="invalid..host",
        port=22,
        username="user"
    )
    
    is_valid, error = validate_profile(profile_invalid_host)
    assert not is_valid
    assert error is not None


def test_profile_valid_host_formats() -> None:
    """Test various valid host formats."""
    valid_hosts = [
        "example.com",
        "192.168.1.1",
        "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        "localhost"
    ]
    
    for host in valid_hosts:
        profile = Profile(
            name="Test Server",
            host=host,
            port=22,
            username="user"
        )
        assert profile.is_valid()

def test_profile_rejects_unsafe_username_and_proxy_command() -> None:
    unsafe_user = Profile(
        name="Unsafe User",
        host="example.com",
        port=22,
        username="user;rm",
    )
    assert not unsafe_user.is_valid()

    unsafe_proxy = Profile(
        name="Unsafe Proxy",
        host="example.com",
        port=22,
        username="user",
        proxy_command="ssh jump.example.com; rm -rf /",
    )
    is_valid, error = validate_profile(unsafe_proxy)
    assert not is_valid
    assert error is not None

    safe_proxy = Profile(
        name="Safe Proxy",
        host="example.com",
        port=22,
        username="user",
        proxy_command="ssh -W %h:%p jump.example.com",
    )
    is_valid, error = validate_profile(safe_proxy)
    assert is_valid
    assert error is None

def test_local_shell_profile_does_not_require_remote_host() -> None:
    from openadmindesk.core.profile import SessionType

    profile = Profile(name="Local Shell", host="", port=1, session_type=SessionType.LOCAL_SHELL)

    assert profile.is_valid()


# ── Metadata fields (Step 8) ─────────────────────────────────────────────────


def test_profile_favorite_default() -> None:
    """Profile favorite defaults to False."""
    p = Profile(name="test", host="example.com")
    assert p.favorite is False


def test_profile_tag_list_parsing() -> None:
    """Profile tag_list property parses comma-separated tags."""
    p = Profile(name="test", host="example.com", tags="  prod , linux , web  ")
    assert p.tag_list == ["prod", "linux", "web"]


def test_profile_tag_list_empty() -> None:
    """Profile tag_list returns [] for empty tags."""
    p = Profile(name="test", host="example.com")
    assert p.tag_list == []


def test_profile_last_metadata_defaults() -> None:
    """Profile last_connected/last_error/last_duration default to None."""
    p = Profile(name="test", host="example.com")
    assert p.last_connected is None
    assert p.last_error is None
    assert p.last_duration is None


def test_profile_metadata_round_trip(tmp_path) -> None:
    """Profile metadata fields survive save/load from store."""
    from openadmindesk.core.profile_store import ProfileStore
    store = ProfileStore(str(tmp_path / "profiles.db"))
    p = Profile(
        name="MetaTest",
        host="meta.example.com",
        port=22,
        username="admin",
        favorite=True,
        tags="prod,linux",
        icon_id="linux",
        last_connected="2026-07-11T12:00:00",
        last_error="",
        last_duration=120.5,
    )
    assert store.save_profile(p)
    loaded = store.load_profile("MetaTest")
    assert loaded is not None
    assert loaded.favorite is True
    assert loaded.tags == "prod,linux"
    assert loaded.icon_id == "linux"
    assert loaded.last_connected == "2026-07-11T12:00:00"
    assert loaded.last_duration == 120.5


def test_profile_icon_text_fallback_is_ascii() -> None:
    p = Profile(name="test", host="example.com")
    assert p.icon == "SSH"
