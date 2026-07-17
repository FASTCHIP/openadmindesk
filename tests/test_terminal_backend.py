"""Tests for terminal backend."""

import pytest
import paramiko

from openadmindesk.core.host_key import TrustOnFirstUsePolicy
from openadmindesk.core.terminal_backend import TerminalBackend
from openadmindesk.core.ssh_terminal_backend import SSHTerminalBackend
from openadmindesk.core.profile import Profile


def test_terminal_backend_interface_is_abstract() -> None:
    """TerminalBackend cannot be instantiated directly."""
    with pytest.raises(TypeError):
        TerminalBackend()


def test_ssh_terminal_backend_initial_state_and_interface_behavior() -> None:
    profile = Profile(name="test", host="localhost", username="user")
    backend = SSHTerminalBackend(profile)

    assert not backend.is_connected()
    assert backend.read() == ""
    assert backend.get_pid() is None
    assert backend.get_size() == (24, 80)
    assert backend.get_connection_info() == {
        "host": "localhost",
        "port": 22,
        "username": "user",
        "connected": False,
    }

    backend.write("ignored while disconnected")
    backend.set_size(40, 120)
    backend.disconnect()
    assert not backend.is_connected()


def test_ssh_terminal_backend_uses_explicit_tofu_host_key_policy(monkeypatch) -> None:
    """SSH terminal backend must require explicit trust for unknown host keys."""
    created_clients = []

    class FakeSSHClient:
        def __init__(self) -> None:
            self.policy = None
            self.loaded_system_host_keys = False
            created_clients.append(self)

        def load_system_host_keys(self) -> None:
            self.loaded_system_host_keys = True

        def set_missing_host_key_policy(self, policy) -> None:
            self.policy = policy

        def connect(self, **kwargs) -> None:
            raise paramiko.SSHException("stop before network")

    monkeypatch.setattr(paramiko, "SSHClient", FakeSSHClient)

    profile = Profile(name="test", host="example.com", username="user")
    backend = SSHTerminalBackend(profile)

    assert backend.connect() is False
    assert len(created_clients) == 1
    assert created_clients[0].loaded_system_host_keys
    assert isinstance(created_clients[0].policy, TrustOnFirstUsePolicy)

def test_ssh_backend_does_not_autodiscover_keys_without_explicit_key(monkeypatch) -> None:
    import paramiko

    from openadmindesk.core.profile import Profile
    from openadmindesk.core.ssh_terminal_backend import SSHTerminalBackend

    captured = {}

    class FakeSSHClient:
        def load_system_host_keys(self) -> None:
            pass

        def set_missing_host_key_policy(self, policy) -> None:
            pass

        def connect(self, **kwargs) -> None:
            captured.update(kwargs)
            raise paramiko.SSHException("stop before network")

    monkeypatch.setattr(paramiko, "SSHClient", FakeSSHClient)

    profile = Profile(name="SSH", host="example.com", username="user")
    backend = SSHTerminalBackend(profile)

    assert backend.connect() is False
    assert captured["allow_agent"] is False
    assert captured["look_for_keys"] is False
    assert "key_filename" not in captured


def test_ssh_backend_uses_only_explicit_private_key(monkeypatch) -> None:
    import paramiko

    from openadmindesk.core.profile import Profile
    from openadmindesk.core.ssh_terminal_backend import SSHTerminalBackend

    captured = {}

    class FakeSSHClient:
        def load_system_host_keys(self) -> None:
            pass

        def set_missing_host_key_policy(self, policy) -> None:
            pass

        def connect(self, **kwargs) -> None:
            captured.update(kwargs)
            raise paramiko.SSHException("stop before network")

    monkeypatch.setattr(paramiko, "SSHClient", FakeSSHClient)

    profile = Profile(
        name="SSH",
        host="example.com",
        username="user",
        private_key_path="/tmp/id_ed25519",
    )
    backend = SSHTerminalBackend(profile)

    assert backend.connect() is False
    assert captured["look_for_keys"] is True
    assert captured["key_filename"] == "/tmp/id_ed25519"


# ── ProxyCommand connect-time revalidation (Phase 9.7) ─────────────────


@pytest.mark.parametrize("unsafe_command, expected_fragment", [
    ("ssh -J host; rm -rf /", "shell metacharacters"),
    ("/usr/bin/nmap -sV target", "Unsupported proxy command binary"),
    ("ssh\x00example.com", "control characters"),
    ('ssh -p "unclosed', "Invalid proxy command quoting"),
])
def test_ssh_proxy_command_unsafe_rejected(
    unsafe_command: str, expected_fragment: str, monkeypatch
) -> None:
    """Unsafe proxy commands are rejected without creating SSHClient or ProxyCommand."""
    ssh_client_calls: list[str] = []
    proxy_command_calls: list[str] = []

    class FakeSSHClient:
        def __init__(self) -> None:
            ssh_client_calls.append("created")
        def load_system_host_keys(self) -> None:
            pass
        def set_missing_host_key_policy(self, policy) -> None:
            pass
        def connect(self, **kwargs) -> None:
            pass

    class FakeProxyCommand:
        def __init__(self, cmd: str) -> None:
            proxy_command_calls.append(cmd)

    monkeypatch.setattr(paramiko, "SSHClient", FakeSSHClient)
    monkeypatch.setattr(paramiko, "ProxyCommand", FakeProxyCommand)

    # Create valid Profile/backend first, then mutate proxy_command to unsafe.
    profile = Profile(
        name="test", host="example.com", username="user",
        proxy_command="ssh -W %h:%p jump.example.com",
    )
    backend = SSHTerminalBackend(profile)
    profile.proxy_command = unsafe_command

    assert backend.connect() is False
    assert expected_fragment in backend.last_error()
    assert len(ssh_client_calls) == 0, "SSHClient should not be created"
    assert len(proxy_command_calls) == 0, "ProxyCommand should not be created"


def test_ssh_proxy_command_valid_allowed(monkeypatch) -> None:
    """Valid proxy command creates ProxyCommand and passes same sock to client.connect."""
    captured_kwargs: dict = {}
    ssh_client_calls: list[str] = []
    proxy_sock = object()

    class FakeSSHClient:
        def __init__(self) -> None:
            ssh_client_calls.append("created")
        def load_system_host_keys(self) -> None:
            pass
        def set_missing_host_key_policy(self, policy) -> None:
            pass
        def connect(self, **kwargs) -> None:
            captured_kwargs.update(kwargs)
            raise paramiko.SSHException("stop before network")

    def fake_proxy_command(cmd: str):
        return proxy_sock

    monkeypatch.setattr(paramiko, "SSHClient", FakeSSHClient)
    monkeypatch.setattr(paramiko, "ProxyCommand", fake_proxy_command)

    profile = Profile(
        name="test", host="example.com", username="user",
        proxy_command="ssh -W %h:%p jump.example.com",
    )
    backend = SSHTerminalBackend(profile)

    assert backend.connect() is False
    assert len(ssh_client_calls) == 1
    assert captured_kwargs.get("sock") is proxy_sock


def test_ssh_proxy_command_empty_not_affected(monkeypatch) -> None:
    """Empty proxy_command does not affect normal connection flow."""
    captured_kwargs: dict = {}

    class FakeSSHClient:
        def load_system_host_keys(self) -> None:
            pass
        def set_missing_host_key_policy(self, policy) -> None:
            pass
        def connect(self, **kwargs) -> None:
            captured_kwargs.update(kwargs)
            raise paramiko.SSHException("stop before network")

    monkeypatch.setattr(paramiko, "SSHClient", FakeSSHClient)

    profile = Profile(name="test", host="example.com", username="user")
    backend = SSHTerminalBackend(profile)
    # Default proxy_command is None/empty — no proxy path in connect.
    assert not profile.proxy_command

    assert backend.connect() is False
    assert "sock" not in captured_kwargs

