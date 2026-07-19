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

# ---------------------------------------------------------------------------
# Mock FreeRDP infrastructure for testing worker methods
# ---------------------------------------------------------------------------

class MockFreeRdpLib:
    """Mock CDLL that records calls for assertion."""
    def __init__(self):
        self.calls = {}
    def __getattr__(self, name):
        def dummy(*args, **kwargs):
            self.calls.setdefault(name, []).append(args)
            if name == "freerdp_client_context_new":
                return 98765
            if name in ("freerdp_connect", "freerdp_disconnect", "freerdp_client_stop"):
                return 0
            if name == "freerdp_client_start":
                return 0
            if name == "freerdp_client_context_free":
                return None
            return 0
        return dummy


class TestRdpWorkerConfigureSettings:

    def test_settings_host_port_user_pass(self, monkeypatch):
        from openadmindesk.core.rdp_client import _RdpWorker, FreeRdpLibrary
        from openadmindesk.core.profile import Profile, SessionType
        mock_lib = MockFreeRdpLib()
        library = FreeRdpLibrary()
        monkeypatch.setattr(library, "_lib", mock_lib, raising=False)
        monkeypatch.setattr(type(library), "lib", property(lambda s: mock_lib), raising=False)
        profile = Profile(name="test", host="10.0.0.1", port=3390, username="admin", password="secret", session_type=SessionType.RDP)
        worker = _RdpWorker(profile, library)
        worker._configure_settings(123, mock_lib)
        calls = mock_lib.calls.get("freerdp_settings_set_string", [])
        set_string_args = [t[2] for t in calls]
        assert any(b"10.0.0.1" in a for a in set_string_args)
        assert any(b"admin" in a for a in set_string_args)
        int_calls = mock_lib.calls.get("freerdp_settings_set_uint32", [])
        assert int_calls

    def test_settings_nla_and_domain(self, monkeypatch):
        from openadmindesk.core.rdp_client import _RdpWorker, FreeRdpLibrary
        from openadmindesk.core.profile import Profile, SessionType
        mock_lib = MockFreeRdpLib()
        library = FreeRdpLibrary()
        monkeypatch.setattr(library, "_lib", mock_lib, raising=False)
        monkeypatch.setattr(type(library), "lib", property(lambda s: mock_lib), raising=False)
        profile = Profile(name="nla", host="nla.example.com", port=3389, session_type=SessionType.RDP, rdp_nla=True, rdp_domain="MYDOMAIN")
        worker = _RdpWorker(profile, library)
        worker._configure_settings(789, mock_lib)
        calls = mock_lib.calls.get("freerdp_settings_set_string", [])
        set_str = [t[2] for t in calls]
        assert any(b"MYDOMAIN" in a for a in set_str)


class TestRdpWorkerRegisterCallbacks:

    def test_callbacks_registered(self, monkeypatch):
        from openadmindesk.core.rdp_client import _RdpWorker, FreeRdpLibrary
        from openadmindesk.core.profile import Profile, SessionType
        mock_lib = MockFreeRdpLib()
        library = FreeRdpLibrary()
        monkeypatch.setattr(library, "_lib", mock_lib, raising=False)
        monkeypatch.setattr(type(library), "lib", property(lambda s: mock_lib), raising=False)
        profile = Profile(name="cb", host="cb.example.com", session_type=SessionType.RDP)
        worker = _RdpWorker(profile, library)
        worker._register_callbacks(111, mock_lib)
        update_calls = mock_lib.calls.get("freerdp_client_set_update_callback", [])
        event_calls = mock_lib.calls.get("freerdp_client_set_event_callback", [])
        assert len(update_calls) >= 1
        assert len(event_calls) >= 1

    def test_cert_verify_cb_ref_saved(self, monkeypatch):
        from openadmindesk.core.rdp_client import _RdpWorker, FreeRdpLibrary
        from openadmindesk.core.profile import Profile, SessionType
        mock_lib = MockFreeRdpLib()
        library = FreeRdpLibrary()
        monkeypatch.setattr(library, "_lib", mock_lib, raising=False)
        monkeypatch.setattr(type(library), "lib", property(lambda s: mock_lib), raising=False)
        profile = Profile(name="cert", host="cert.example.com", session_type=SessionType.RDP)
        worker = _RdpWorker(profile, library)
        worker._register_cert_verify_callback(222, mock_lib)
        cert_calls = mock_lib.calls.get("freerdp_client_set_cert_verify_callback", [])
        assert len(cert_calls) >= 1
        assert hasattr(worker, "_cert_verify_cb")


class TestRdpWorkerCallbackHandlers:

    def test_client_event_runs(self, monkeypatch):
        from openadmindesk.core.rdp_client import _RdpWorker, FreeRdpLibrary
        from openadmindesk.core.profile import Profile, SessionType
        mock_lib = MockFreeRdpLib()
        library = FreeRdpLibrary()
        monkeypatch.setattr(library, "_lib", mock_lib, raising=False)
        monkeypatch.setattr(type(library), "lib", property(lambda s: mock_lib), raising=False)
        profile = Profile(name="ev", host="ev.example.com", session_type=SessionType.RDP)
        worker = _RdpWorker(profile, library)
        result = worker._on_client_event(0, 0)
        assert isinstance(result, (int, bool))

    def test_cert_verify_trusted_no_prompt(self, monkeypatch, tmp_path):
        from openadmindesk.core.rdp_client import _RdpWorker, FreeRdpLibrary, RdpCertTrustStore
        from openadmindesk.core.profile import Profile, SessionType
        trust_path = tmp_path / "rdp_known_certs.json"
        trust_store = RdpCertTrustStore(trust_path)
        trust_store.add_trust("trusted.host", "AA:BB:CC", "CN=srv", "CN=ca")
        mock_lib = MockFreeRdpLib()
        library = FreeRdpLibrary()
        monkeypatch.setattr(library, "_lib", mock_lib, raising=False)
        monkeypatch.setattr(type(library), "lib", property(lambda s: mock_lib), raising=False)
        profile = Profile(name="cert", host="cert.example.com", session_type=SessionType.RDP)
        worker = _RdpWorker(profile, library)
        worker._cert_trust_store = trust_store
        prompts = []
        worker.certificate_prompt.connect(lambda h, fp, s, i: prompts.append((h, fp)))
        result = worker._on_cert_verify(b"trusted.host", b"AA:BB:CC", b"CN=srv", b"CN=ca")
        assert result is True
        assert len(prompts) == 0


class TestRdpWorkerInputForwarding:

    def test_keyboard_enqueue_flush(self, monkeypatch):
        from openadmindesk.core.rdp_client import _RdpWorker, FreeRdpLibrary
        from openadmindesk.core.profile import Profile, SessionType
        mock_lib = MockFreeRdpLib()
        library = FreeRdpLibrary()
        monkeypatch.setattr(library, "_lib", mock_lib, raising=False)
        monkeypatch.setattr(type(library), "lib", property(lambda s: mock_lib), raising=False)
        profile = Profile(name="kbd", host="kbd.example.com", session_type=SessionType.RDP)
        worker = _RdpWorker(profile, library)
        worker._context = 5555
        worker.enqueue_key(0x1E, True, False)
        worker._flush_input()
        key_calls = mock_lib.calls.get("freerdp_input_send_keyboard_event", [])
        assert len(key_calls) >= 1

    def test_mouse_enqueue_flush(self, monkeypatch):
        from openadmindesk.core.rdp_client import _RdpWorker, FreeRdpLibrary
        from openadmindesk.core.profile import Profile, SessionType
        mock_lib = MockFreeRdpLib()
        library = FreeRdpLibrary()
        monkeypatch.setattr(library, "_lib", mock_lib, raising=False)
        monkeypatch.setattr(type(library), "lib", property(lambda s: mock_lib), raising=False)
        profile = Profile(name="mouse", host="mouse.example.com", session_type=SessionType.RDP)
        worker = _RdpWorker(profile, library)
        worker._context = 6666
        worker.enqueue_mouse(100, 200, 0x8000, 0)
        worker._flush_input()
        mouse_calls = mock_lib.calls.get("freerdp_input_send_mouse_event", [])
        assert len(mouse_calls) >= 1

    def test_resize_enqueue_flush(self, monkeypatch):
        from openadmindesk.core.rdp_client import _RdpWorker, FreeRdpLibrary
        from openadmindesk.core.profile import Profile, SessionType
        mock_lib = MockFreeRdpLib()
        library = FreeRdpLibrary()
        monkeypatch.setattr(library, "_lib", mock_lib, raising=False)
        monkeypatch.setattr(type(library), "lib", property(lambda s: mock_lib), raising=False)
        profile = Profile(name="resize", host="resize.example.com", session_type=SessionType.RDP)
        worker = _RdpWorker(profile, library)
        worker._context = 7777
        worker.enqueue_resize(1920, 1080)
        worker._flush_input()
        resize_calls = mock_lib.calls.get("freerdp_client_resize_display", [])
        assert len(resize_calls) >= 1


class TestRdpClipboardInfrastructure:

    def test_clipboard_callback_type_exists(self):
        from openadmindesk.core.rdp_client import CLIPBOARD_EVENT_CALLBACK
        assert isinstance(CLIPBOARD_EVENT_CALLBACK, type)

    def test_clipboard_signal_exists_on_client(self):
        from openadmindesk.core.rdp_client import RdpClient
        client = RdpClient()
        assert hasattr(client, "clipboard_text_received")

    def test_worker_has_clipboard_queue(self, monkeypatch):
        from openadmindesk.core.rdp_client import _RdpWorker, FreeRdpLibrary
        from openadmindesk.core.profile import Profile, SessionType
        mock_lib = MockFreeRdpLib()
        library = FreeRdpLibrary()
        monkeypatch.setattr(library, "_lib", mock_lib, raising=False)
        monkeypatch.setattr(type(library), "lib", property(lambda s: mock_lib), raising=False)
        profile = Profile(name="clip", host="clip.example.com", session_type=SessionType.RDP)
        worker = _RdpWorker(profile, library)
        assert hasattr(worker, "_clipboard_queue")
        assert hasattr(worker, "clipboard_received")

    def test_worker_clipboard_callback_runs(self, monkeypatch):
        from openadmindesk.core.rdp_client import _RdpWorker, FreeRdpLibrary
        from openadmindesk.core.profile import Profile, SessionType
        mock_lib = MockFreeRdpLib()
        library = FreeRdpLibrary()
        monkeypatch.setattr(library, "_lib", mock_lib, raising=False)
        monkeypatch.setattr(type(library), "lib", property(lambda s: mock_lib), raising=False)
        profile = Profile(name="cb", host="cb.example.com", session_type=SessionType.RDP)
        worker = _RdpWorker(profile, library)
        received = []
        worker.clipboard_received.connect(lambda t: received.append(t))
        import ctypes
        data = ctypes.create_string_buffer(b"hello from remote")
        result = worker._on_clipboard_event(0, 0, ctypes.cast(data, ctypes.c_void_p), 17)
        assert result is True
        assert len(received) == 1
        assert received[0] == "hello from remote"

    def test_fullscreen_toggle_on_session_tab(self):
        from PySide6.QtWidgets import QApplication
        import sys
        if not QApplication.instance():
            QApplication(sys.argv)
        from openadmindesk.ui.rdp_session_tab import RdpSessionTab
        from openadmindesk.core.profile import Profile, SessionType
        profile = Profile(name="fs", host="fs.example.com", session_type=SessionType.RDP)
        tab = RdpSessionTab(profile)
        assert hasattr(tab, "_fullscreen_button")
        assert tab._fullscreen_button.text() in ("Fullscreen", "Window")
