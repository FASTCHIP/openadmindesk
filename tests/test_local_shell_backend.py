"""Tests for local shell backend - focused on Windows command handling."""

import subprocess
from unittest.mock import MagicMock, patch

from openadmindesk.core.local_shell_backend import LocalShellBackend


class TestLocalShellBackendWindows:
    """Test Windows-specific behavior of local shell backend."""

    @patch("openadmindesk.core.local_shell_backend.is_windows", return_value=True)
    @patch("openadmindesk.core.local_shell_backend.subprocess.Popen")
    def test_windows_popen_uses_command_list_not_shell(
        self, mock_popen: MagicMock, mock_is_windows: MagicMock
    ) -> None:
        """Verify Windows Popen uses command list without shell=True."""
        backend = LocalShellBackend()
        
        # Mock the process
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process
        
        # Connect should call Popen with correct arguments
        result = backend.connect()
        
        # Should succeed
        assert result is True
        
        # Popen should be called exactly once
        assert mock_popen.call_count == 1
        
        # Get the call arguments
        call_args = mock_popen.call_args
        
        # Verify it's called with a command list (not shell string)
        assert call_args[0][0] == ["cmd.exe"]
        
        # Verify shell=True is NOT in the kwargs
        assert "shell" not in call_args[1] or call_args[1].get("shell") is False
        
        # Verify standard pipes are set up correctly
        assert call_args[1]["stdin"] == subprocess.PIPE
        assert call_args[1]["stdout"] == subprocess.PIPE
        assert call_args[1]["stderr"] == subprocess.STDOUT

    @patch("openadmindesk.core.local_shell_backend.is_windows", return_value=True)
    def test_windows_command_arg_list_is_preserved(self, mock_is_windows: MagicMock) -> None:
        """Verify Windows command argument list is preserved as-is."""
        backend = LocalShellBackend()
        
        with patch("openadmindesk.core.local_shell_backend.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process
            
            backend.connect()
            
            # Verify the command is passed as a list
            call_args = mock_popen.call_args
            cmd_list = call_args[0][0]
            
            # Should be exactly ["cmd.exe"] without any shell interpretation
            assert cmd_list == ["cmd.exe"]
            assert len(cmd_list) == 1
            assert cmd_list[0] == "cmd.exe"
