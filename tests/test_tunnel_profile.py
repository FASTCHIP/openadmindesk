"""Tests for tunnel profile model."""

from openadmindesk.core.tunnel_profile import TunnelProfile, TunnelType


def test_tunnel_profile_creation() -> None:
    """Test tunnel profile creation."""
    profile = TunnelProfile(
        name="Test Tunnel",
        host="example.com",
        port=22,
        username="user",
        tunnel_type=TunnelType.LOCAL_FORWARD,
        local_port=8080,
        remote_port=80,
        remote_host="localhost"
    )
    
    assert profile.name == "Test Tunnel"
    assert profile.host == "example.com"
    assert profile.port == 22
    assert profile.username == "user"
    assert profile.tunnel_type == TunnelType.LOCAL_FORWARD
    assert profile.local_port == 8080
    assert profile.remote_port == 80
    assert profile.remote_host == "localhost"
    assert profile.id is not None


def test_tunnel_profile_validation() -> None:
    """Test tunnel profile validation."""
    # Valid local forward
    local_profile = TunnelProfile(
        name="Test Local",
        host="example.com",
        tunnel_type=TunnelType.LOCAL_FORWARD,
        local_port=8080,
        remote_port=80,
        remote_host="localhost"
    )
    
    assert local_profile.is_valid()
    
    # Valid remote forward
    remote_profile = TunnelProfile(
        name="Test Remote",
        host="example.com",
        tunnel_type=TunnelType.REMOTE_FORWARD,
        remote_port=8080,
        local_port=80,
        remote_host="localhost"
    )
    
    assert remote_profile.is_valid()
    
    # Invalid - no name
    invalid_profile = TunnelProfile(
        name="",
        host="example.com",
        tunnel_type=TunnelType.LOCAL_FORWARD,
        local_port=8080,
        remote_port=80,
        remote_host="localhost"
    )
    
    assert not invalid_profile.is_valid()
    
    # Invalid - no host
    invalid_profile2 = TunnelProfile(
        name="Test",
        host="",
        tunnel_type=TunnelType.LOCAL_FORWARD,
        local_port=8080,
        remote_port=80,
        remote_host="localhost"
    )
    
    assert not invalid_profile2.is_valid()


def test_tunnel_profile_ssh_options() -> None:
    """Test SSH options generation."""
    profile = TunnelProfile(
        name="Test Tunnel",
        host="example.com",
        port=2222,
        username="user",
        tunnel_type=TunnelType.LOCAL_FORWARD,
        local_port=8080,
        remote_port=80,
        remote_host="localhost"
    )
    
    options = profile.get_ssh_options()
    assert "-p" in options
    assert "2222" in options
    assert "-l" in options
    assert "user" in options
    assert "-L" in options

def test_tunnel_profile_rejects_unsafe_connection_fields() -> None:
    unsafe_host = TunnelProfile(
        name="Unsafe Host",
        host="example.com;rm",
        tunnel_type=TunnelType.LOCAL_FORWARD,
        local_port=8080,
        remote_port=80,
        remote_host="localhost",
    )
    assert not unsafe_host.is_valid()

    unsafe_user = TunnelProfile(
        name="Unsafe User",
        host="example.com",
        username="user;rm",
        tunnel_type=TunnelType.LOCAL_FORWARD,
        local_port=8080,
        remote_port=80,
        remote_host="localhost",
    )
    assert not unsafe_user.is_valid()

    unsafe_remote_host = TunnelProfile(
        name="Unsafe Remote Host",
        host="example.com",
        tunnel_type=TunnelType.LOCAL_FORWARD,
        local_port=8080,
        remote_port=80,
        remote_host="localhost;rm",
    )
    assert not unsafe_remote_host.is_valid()
