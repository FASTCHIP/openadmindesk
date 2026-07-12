"""Tests for SSH host-key trust helpers."""

from __future__ import annotations

import pytest
import paramiko

from openadmindesk.core.host_key import HostKeyTrustStore, TrustOnFirstUsePolicy


def _key() -> paramiko.PKey:
    return paramiko.RSAKey.generate(1024)


def test_fingerprint_is_sha256_prefixed() -> None:
    fingerprint = HostKeyTrustStore.fingerprint_sha256(_key())

    assert fingerprint.startswith("SHA256:")
    assert "=" not in fingerprint


def test_trust_store_saves_and_loads_host_key(tmp_path) -> None:
    store = HostKeyTrustStore(tmp_path / "known_hosts")
    key = _key()

    store.save_host_key("example.com", key)

    host_keys = paramiko.HostKeys(str(store.path))
    assert host_keys.lookup("example.com")[key.get_name()] == key


def test_tofu_policy_rejects_unknown_key_and_keeps_pending(tmp_path) -> None:
    store = HostKeyTrustStore(tmp_path / "known_hosts")
    policy = TrustOnFirstUsePolicy(store)
    client = paramiko.SSHClient()
    key = _key()

    with pytest.raises(paramiko.SSHException, match="Unknown host key"):
        policy.missing_host_key(client, "example.com", key)

    assert policy.pending is not None
    assert policy.pending.hostname == "example.com"
    assert policy.pending.fingerprint_sha256.startswith("SHA256:")


def test_tofu_policy_can_accept_unknown_key(tmp_path) -> None:
    store = HostKeyTrustStore(tmp_path / "known_hosts")
    key = _key()
    policy = TrustOnFirstUsePolicy(store, decision_callback=lambda prompt: True)
    client = paramiko.SSHClient()

    policy.missing_host_key(client, "example.com", key)

    assert policy.pending is None
    assert store.path.exists()
    assert client.get_host_keys().lookup("example.com")[key.get_name()] == key
