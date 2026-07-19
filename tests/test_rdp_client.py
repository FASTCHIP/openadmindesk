"""Tests for RDP client certificate TOFU and trust store."""

from __future__ import annotations

import json
import threading

from openadmindesk.core.rdp_client import RdpCertTrustStore


class TestRdpCertTrustStore:

    def test_default_path(self):
        store = RdpCertTrustStore()
        assert "openadmindesk" in str(store.path)
        assert store.path.name == "rdp_known_certs.json"

    def test_load_nonexistent_returns_empty(self, tmp_path):
        store = RdpCertTrustStore(tmp_path / "nonexistent.json")
        assert store.is_trusted("example.com", "abc123") is False

    def test_add_and_check_trust(self, tmp_path):
        store = RdpCertTrustStore(tmp_path / "certs.json")
        store.add_trust("rdp.example.com", "aabbccdd", "CN=server", "CN=CA")
        assert store.is_trusted("rdp.example.com", "aabbccdd") is True
        assert store.is_trusted("rdp.example.com", "wrongfp") is False
        assert store.is_trusted("other.host", "aabbccdd") is False

    def test_persistence_across_reload(self, tmp_path):
        path = tmp_path / "certs.json"
        store1 = RdpCertTrustStore(path)
        store1.add_trust("host1", "fp1")
        store2 = RdpCertTrustStore(path)
        assert store2.is_trusted("host1", "fp1") is True

    def test_file_mode_0600(self, tmp_path):
        store = RdpCertTrustStore(tmp_path / "certs.json")
        store.add_trust("h", "f")
        mode = (tmp_path / "certs.json").stat().st_mode & 0o777
        assert mode == 0o600

    def test_remove_trust(self, tmp_path):
        store = RdpCertTrustStore(tmp_path / "certs.json")
        store.add_trust("host", "fp")
        assert store.remove_trust("host") is True
        assert store.is_trusted("host", "fp") is False
        assert store.remove_trust("nonexistent") is False

    def test_add_trust_stores_metadata(self, tmp_path):
        store = RdpCertTrustStore(tmp_path / "certs.json")
        store.add_trust("h", "fp", "CN=server", "CN=CA")
        data = json.loads((tmp_path / "certs.json").read_text())
        assert data["h"]["thumbprint"] == "fp"
        assert data["h"]["subject"] == "CN=server"
        assert data["h"]["issuer"] == "CN=CA"
        assert "first_seen" in data["h"]

    def test_corrupt_json_fallback(self, tmp_path):
        path = tmp_path / "certs.json"
        path.write_text("{corrupt")
        store = RdpCertTrustStore(path)
        assert store.is_trusted("h", "f") is False

    def test_thread_safety(self, tmp_path):
        store = RdpCertTrustStore(tmp_path / "certs.json")
        errors = []
        def writer():
            for i in range(100):
                store.add_trust(f"host{i}", f"fp{i}")
        def reader():
            for i in range(100):
                try:
                    store.is_trusted(f"host{i}", f"fp{i}")
                except Exception as e:
                    errors.append(e)
        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert len(errors) == 0


    def test_fingerprint_case_sensitive(self, tmp_path):
        store = RdpCertTrustStore(tmp_path / "certs.json")
        store.add_trust("host", "ABC123")
        assert store.is_trusted("host", "abc123") is False
        assert store.is_trusted("host", "ABC123") is True


def test_rdp_client_nla_settings_in_configure() -> None:
    """Test that NLA and domain constants are correctly defined."""
    from openadmindesk.core.rdp_client import FREERDP_SETTING_NLA, FREERDP_SETTING_DOMAIN
    assert FREERDP_SETTING_NLA == 12
    assert FREERDP_SETTING_DOMAIN == 4
    assert isinstance(FREERDP_SETTING_NLA, int)
    assert isinstance(FREERDP_SETTING_DOMAIN, int)
