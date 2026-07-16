"""Tests for tunnel manager — behavioral."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

from openadmindesk.core.tunnel_profile import TunnelProfile, TunnelType
from openadmindesk.core import tunnel_manager
from openadmindesk.core.tunnel_manager import TunnelManager, TunnelProcess


# Define sentinel values for testing
SENTINEL_PROFILE_NAME = "test-profile-sentinel"
SENTINEL_HOST = "sentinel-host.example.com"
SENTINEL_USERNAME = "sentinel-user"
SENTINEL_KEY_PATH = "/home/user/.ssh/sentinel_key"
SENTINEL_STDERR_SECRET = "sentinel stderr content"
SENTINEL_EXCEPTION_SECRET = "sentinel exception message with sensitive data"


def test_tunnel_manager_creation() -> None:
    """Tunnel manager creates in empty state."""
    manager = TunnelManager()
    assert manager is not None


def test_tunnel_manager_start_stop_without_ssh() -> None:
    """Starting tunnel should not crash (may succeed if SSH is available)."""
    manager = TunnelManager()
    profile = TunnelProfile(
        name="Test Tunnel",
        host="localhost",
        tunnel_type=TunnelType.LOCAL_FORWARD,
        local_port=18080,
        remote_port=80,
        remote_host="localhost",
    )
    result = manager.start_tunnel(profile)
    # Should not raise an exception — result depends on SSH availability
    assert isinstance(result, bool)


def test_tunnel_manager_stop_nonexistent() -> None:
    """Stopping a nonexistent tunnel should not raise."""
    manager = TunnelManager()
    manager.stop_tunnel("nonexistent-id")  # Should not raise


def test_tunnel_manager_status_nonexistent() -> None:
    """Getting status of nonexistent tunnel returns None."""
    manager = TunnelManager()
    status = manager.get_tunnel_status("nonexistent-id")
    assert status is None


def test_tunnel_process_captures_stderr(monkeypatch) -> None:
    """Tunnel status should expose captured SSH stderr diagnostics."""
    captured = {}

    class FakeProcess:
        def __init__(self) -> None:
            self.stderr = ["bind failed\n"]
            self.returncode = 0

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(tunnel_manager.subprocess, "Popen", fake_popen)
    profile = TunnelProfile(
        name="Test Tunnel",
        host="example.com",
        tunnel_type=TunnelType.LOCAL_FORWARD,
        local_port=18080,
        remote_port=80,
        remote_host="localhost",
    )

    process = TunnelProcess(profile)
    assert process.start()
    process._stderr_thread.join(timeout=1)
    assert process._thread is not None
    process._thread.join(timeout=1)
    assert not process._thread.is_alive()

    status = process.get_status()
    assert captured["kwargs"]["stderr"] == tunnel_manager.subprocess.PIPE
    assert status["last_error"] == "bind failed"


def test_tunnel_logging_success_and_failure(caplog) -> None:
    """Test that tunnel lifecycle events are logged appropriately with comprehensive secret filtering."""
    # Test successful tunnel start
    profile = TunnelProfile(
        id="test-tunnel-123",
        name=SENTINEL_PROFILE_NAME,
        host=SENTINEL_HOST,
        username=SENTINEL_USERNAME,
        tunnel_type=TunnelType.LOCAL_FORWARD,
        local_port=18080,
        remote_port=80,
        remote_host="localhost",
        private_key_path=SENTINEL_KEY_PATH,
    )

    # Mock subprocess.Popen to return a fake process with sentinel stderr
    class FakeProcess:
        def __init__(self) -> None:
            self.stderr = [f"{SENTINEL_STDERR_SECRET}\n"]
            self.returncode = None

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            pass

    with caplog.at_level(logging.INFO):
        # Mock the Popen call
        with patch.object(tunnel_manager.subprocess, 'Popen', return_value=FakeProcess()):
            process = TunnelProcess(profile)
            result = process.start()

            # Should succeed
            assert result is True

            # Verify that _stderr_thread is not None and join it
            assert process._stderr_thread is not None
            process._stderr_thread.join(timeout=1)
            assert not process._stderr_thread.is_alive()

            # Verify that last_error contains the sentinel stderr
            status = process.get_status()
            assert status["last_error"] == SENTINEL_STDERR_SECRET

            # Check that start was logged
            start_requested_logged = any(record.message == "Tunnel start requested" for record in caplog.records)
            assert start_requested_logged is True
            start_logged = any(record.message == "Tunnel started successfully" for record in caplog.records)
            assert start_logged is True

            # Build a comprehensive view of records including message and extra
            records_view = []
            for record in caplog.records:
                record_info = {
                    "message": record.message,
                    "extra": getattr(record, 'extra', {}),
                    "dict": record.__dict__
                }
                records_view.append(record_info)

            # Verify that no forbidden sentinel values are present in any record
            for record_info in records_view:
                record_str = str(record_info)
                assert SENTINEL_PROFILE_NAME not in record_str
                assert SENTINEL_HOST not in record_str
                assert SENTINEL_USERNAME not in record_str
                assert SENTINEL_KEY_PATH not in record_str
                assert SENTINEL_STDERR_SECRET not in record_str

            # Now stop the tunnel
            stop_result = process.stop()
            assert stop_result is True

            # Check that stop was logged
            stop_requested_logged = any(record.message == "Tunnel stop requested" for record in caplog.records)
            assert stop_requested_logged is True
            stop_logged = any(record.message == "Tunnel stopped" for record in caplog.records)
            assert stop_logged is True

            # Verify that stop records also don't contain forbidden values
            for record_info in records_view:
                record_str = str(record_info)
                assert SENTINEL_PROFILE_NAME not in record_str
                assert SENTINEL_HOST not in record_str
                assert SENTINEL_USERNAME not in record_str
                assert SENTINEL_KEY_PATH not in record_str
                assert SENTINEL_STDERR_SECRET not in record_str


def test_tunnel_logging_failure_start(caplog) -> None:
    """Test that tunnel start failures are logged appropriately without secrets."""
    profile = TunnelProfile(
        id="test-tunnel-failure-start",
        name=SENTINEL_PROFILE_NAME,
        host=SENTINEL_HOST,
        username=SENTINEL_USERNAME,
        tunnel_type=TunnelType.LOCAL_FORWARD,
        local_port=18080,
        remote_port=80,
        remote_host="localhost",
        private_key_path=SENTINEL_KEY_PATH,
    )

    # Mock subprocess.Popen to raise an exception with sentinel message
    with caplog.at_level(logging.WARNING):
        with patch.object(tunnel_manager.subprocess, 'Popen', side_effect=RuntimeError(SENTINEL_EXCEPTION_SECRET)):
            process = TunnelProcess(profile)
            result = process.start()

            # Should fail
            assert result is False

            # Verify that the exception class is logged but not the message
            warning_records = [record for record in caplog.records if record.levelno == logging.WARNING]
            assert len(warning_records) >= 1

            # Check that the warning record contains the exception class but not the message
            warning_record = warning_records[0]
            assert "Tunnel start failed" in warning_record.message
            assert "exception_class" in warning_record.__dict__
            assert "RuntimeError" in warning_record.__dict__["exception_class"]
            # Verify that the sentinel message is NOT in the warning record
            assert SENTINEL_EXCEPTION_SECRET not in str(warning_record)

            # Verify that forbidden values are not in the warning record
            warning_str = str(warning_record)
            assert SENTINEL_PROFILE_NAME not in warning_str
            assert SENTINEL_HOST not in warning_str
            assert SENTINEL_USERNAME not in warning_str
            assert SENTINEL_KEY_PATH not in warning_str


def test_tunnel_logging_failure_stop(caplog) -> None:
    """Test that tunnel stop failures are logged appropriately without secrets."""
    profile = TunnelProfile(
        id="test-tunnel-failure-stop",
        name=SENTINEL_PROFILE_NAME,
        host=SENTINEL_HOST,
        username=SENTINEL_USERNAME,
        tunnel_type=TunnelType.LOCAL_FORWARD,
        local_port=18080,
        remote_port=80,
        remote_host="localhost",
        private_key_path=SENTINEL_KEY_PATH,
    )

    # Mock subprocess.Popen to return a fake process
    fake_process = MagicMock()
    fake_process.poll.return_value = None  # Process is running
    fake_process.returncode = None

    with caplog.at_level(logging.WARNING):
        # Mock the Popen call
        with patch.object(tunnel_manager.subprocess, 'Popen', return_value=fake_process):
            process = TunnelProcess(profile)
            result = process.start()
            assert result is True

            # Mock process.poll() to return None (running) and then make terminate() raise exception
            with patch.object(fake_process, 'terminate', side_effect=RuntimeError(SENTINEL_EXCEPTION_SECRET)):
                stop_result = process.stop()
                assert stop_result is False

                # Verify that the stop failure is logged
                warning_records = [record for record in caplog.records if record.levelno == logging.WARNING]
                assert len(warning_records) >= 1

                # Check that the warning record contains the exception class but not the message
                warning_record = warning_records[-1]  # Get the last warning (stop failure)
                assert "Tunnel stop failed" in warning_record.message
                assert "exception_class" in warning_record.__dict__
                assert "RuntimeError" in warning_record.__dict__["exception_class"]
                # Verify that the sentinel message is NOT in the warning record
                assert SENTINEL_EXCEPTION_SECRET not in str(warning_record)

                # Verify that forbidden values are not in the warning record
                warning_str = str(warning_record)
                assert SENTINEL_PROFILE_NAME not in warning_str
                assert SENTINEL_HOST not in warning_str
                assert SENTINEL_USERNAME not in warning_str
                assert SENTINEL_KEY_PATH not in warning_str


def test_tunnel_logging_with_exit_code(caplog) -> None:
    """Test that tunnel process completion logs exit code."""
    # Mock a tunnel with a completed process
    profile = TunnelProfile(
        id="test-tunnel-456",
        name="Test Tunnel 2",
        host="example2.com",
        tunnel_type=TunnelType.REMOTE_FORWARD,
        local_port=18081,
        remote_port=81,
        remote_host="localhost2",
    )

    # Mock subprocess.Popen to return a fake process
    fake_process = MagicMock()
    fake_process.poll.return_value = 0  # Process finished with exit code 0
    fake_process.returncode = 0

    with caplog.at_level(logging.INFO):
        # Mock the Popen call
        with patch.object(tunnel_manager.subprocess, 'Popen', return_value=fake_process):
            process = TunnelProcess(profile)
            result = process.start()

            # Should succeed
            assert result is True

            # Simulate process completion
            process._process = fake_process
            process._monitor_process()

            # Check that completion was logged
            completion_logged = any(record.message == "Tunnel process completed" for record in caplog.records)
            assert completion_logged is True

            # Verify that exit_code is in the log
            completion_records = [record for record in caplog.records if record.message == "Tunnel process completed"]
            assert len(completion_records) >= 1
            completion_record = completion_records[0]
            assert "exit_code" in completion_record.__dict__
            assert completion_record.__dict__["exit_code"] == 0
