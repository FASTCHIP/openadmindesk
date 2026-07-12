"""Tests for remote file model."""

from openadmindesk.core.remote_file import RemoteFile, FileType


def test_remote_file_creation() -> None:
    """Test remote file creation."""
    file = RemoteFile(
        path="/home/user/test.txt",
        name="test.txt",
        size=1024,
        file_type=FileType.FILE,
        permissions="644",
        owner="user",
        group="group"
    )
    
    assert file.path == "/home/user/test.txt"
    assert file.name == "test.txt"
    assert file.size == 1024
    assert file.file_type == FileType.FILE
    assert file.permissions == "644"
    assert file.owner == "user"
    assert file.group == "group"


def test_remote_file_type_detection() -> None:
    """Test file type detection."""
    # File
    file = RemoteFile(path="/home/user/file.txt")
    assert file.is_file()
    assert not file.is_directory()
    
    # Directory
    directory = RemoteFile(path="/home/user/dir/")
    assert directory.is_directory()
    assert not directory.is_file()
    
    # File with extension
    file_with_ext = RemoteFile(path="/home/user/script.py")
    assert file_with_ext.get_extension() == "py"


def test_remote_file_post_init() -> None:
    """Test post initialization."""
    # Test with path only
    file = RemoteFile(path="/home/user/test.txt")
    assert file.name == "test.txt"
    assert file.file_type == FileType.FILE
    
    # Test with directory path
    directory = RemoteFile(path="/home/user/dir/")
    assert directory.name == "dir"
    assert directory.file_type == FileType.DIRECTORY