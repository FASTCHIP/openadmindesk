"""Tests for SFTP backend — behavioral backend coverage."""

from __future__ import annotations

import paramiko
import stat

from openadmindesk.core import sftp_backend
from openadmindesk.core.remote_file import FileType
from openadmindesk.core.host_key import TrustOnFirstUsePolicy
from openadmindesk.core.sftp_backend import SftpBackend


def test_sftp_backend_creation() -> None:
    """SFTP backend creates in disconnected state."""
    backend = SftpBackend()
    assert backend is not None
    assert backend.is_connected() is False


def test_sftp_backend_list_directory_disconnected() -> None:
    """Listing directory while disconnected returns empty list."""
    backend = SftpBackend()
    result = backend.list_directory("/")
    assert result == []


def test_sftp_backend_download_disconnected() -> None:
    """Download while disconnected returns False."""
    backend = SftpBackend()
    result = backend.download_file("/etc/hosts", "/tmp/test")
    assert result is False


def test_sftp_backend_upload_disconnected() -> None:
    """Upload while disconnected returns False."""
    backend = SftpBackend()
    result = backend.upload_file("/tmp/test", "/etc/hosts")
    assert result is False


def test_sftp_backend_make_directory_disconnected() -> None:
    """Create directory while disconnected returns False."""
    backend = SftpBackend()
    result = backend.make_directory("/tmp/newdir")
    assert result is False


def test_sftp_backend_remove_file_disconnected() -> None:
    """Remove file while disconnected returns False."""
    backend = SftpBackend()
    result = backend.remove_file("/tmp/somefile")
    assert result is False


def test_sftp_backend_disconnect_when_not_connected() -> None:
    """Disconnect when not connected is a no-op."""
    backend = SftpBackend()
    backend.disconnect()  # Should not raise
    assert backend.is_connected() is False

def test_sftp_backend_uses_explicit_tofu_host_key_policy(monkeypatch) -> None:
    """SFTP must require explicit trust for unknown host keys."""
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

        def connect(self, *args, **kwargs) -> None:
            raise paramiko.SSHException("stop before network")

    monkeypatch.setattr(sftp_backend, "SSHClient", FakeSSHClient)

    backend = SftpBackend()
    assert backend.connect("example.com", username="user") is False

    assert len(created_clients) == 1
    assert created_clients[0].loaded_system_host_keys
    assert isinstance(created_clients[0].policy, TrustOnFirstUsePolicy)


def test_sftp_stat_attributes_without_filename_are_supported() -> None:
    class Attr:
        st_mode = stat.S_IFREG | 0o644
        st_size = 42
        st_uid = 1000
        st_gid = 1000
        st_mtime = 1_617_041_630

    remote = SftpBackend()._attr_to_remote_file(
        Attr(),
        "/home/user",
        filename="AGENTS.md",
    )

    assert remote.path == "/home/user/AGENTS.md"
    assert remote.name == "AGENTS.md"
    assert remote.file_type == FileType.FILE
    assert remote.permissions == "644"
