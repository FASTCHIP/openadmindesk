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

