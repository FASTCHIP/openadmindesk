"""Tests for SFTP file browser UI behavior."""

from PySide6.QtCore import Qt

from openadmindesk.core.profile import Profile
from openadmindesk.core.remote_file import FileType, RemoteFile
from openadmindesk.ui.sftp_file_browser import SftpFileBrowser


class FakeBackend:
    def __init__(self) -> None:
        self.disconnect_calls = 0

    def disconnect(self) -> None:
        self.disconnect_calls += 1

    def close(self) -> None:
        pass


class FakeWorker:
    def __init__(self, running: bool = True) -> None:
        self._running = running
        self.cancel_calls = 0
        self.quit_calls = 0
        self.wait_calls: list[int] = []

    def isRunning(self) -> bool:
        return self._running

    def cancel(self) -> None:
        self.cancel_calls += 1

    def quit(self) -> None:
        self.quit_calls += 1

    def wait(self, timeout: int) -> None:
        self.wait_calls.append(timeout)
        self._running = False


class FakeListWorker(FakeWorker):
    pass


def _profile() -> Profile:
    return Profile(name="SFTP", host="example.com", username="user", port=22)


def _browser(monkeypatch) -> SftpFileBrowser:
    monkeypatch.setattr(SftpFileBrowser, "_connect_to_sftp", lambda self: None)
    return SftpFileBrowser(_profile())


def test_sftp_connection_success_marks_connected_and_loads(monkeypatch) -> None:
    browser = _browser(monkeypatch)
    loaded = []
    monkeypatch.setattr(browser, "_load_directory", lambda: loaded.append(browser.current_path))

    browser._on_connection_result(True)

    assert browser._connected
    assert "Connected" in browser.connection_label.text()
    assert loaded == ["/"]


def test_sftp_connection_failure_marks_disconnected(monkeypatch) -> None:
    browser = _browser(monkeypatch)

    browser._on_connection_result(False)

    assert not browser._connected
    assert "Disconnected" in browser.connection_label.text()


def test_sftp_directory_loaded_updates_tree_and_path(monkeypatch) -> None:
    browser = _browser(monkeypatch)
    files = [
        RemoteFile(
            path="/tmp/file.txt",
            name="file.txt",
            size=1536,
            file_type=FileType.FILE,
        )
    ]

    browser._on_directory_loaded(files, "/tmp")

    assert browser.path_input.text() == "/tmp"
    assert browser.file_tree.topLevelItemCount() == 1
    assert "file.txt" in browser.file_tree.topLevelItem(0).text(0)


def test_sftp_disconnect_cancels_workers_and_backend(monkeypatch) -> None:
    browser = _browser(monkeypatch)
    backend = FakeBackend()
    worker = FakeWorker()
    list_worker = FakeListWorker()
    browser.sftp_backend = backend  # type: ignore[assignment]
    browser._worker = worker  # type: ignore[assignment]
    browser._list_worker = list_worker  # type: ignore[assignment]
    browser._connected = True

    browser.disconnect()

    assert worker.cancel_calls == 1
    assert worker.quit_calls == 1
    assert worker.wait_calls == [1000]
    assert list_worker.quit_calls == 1
    assert list_worker.wait_calls == [1000]
    assert backend.disconnect_calls == 1
    assert not browser._connected
    assert browser.file_tree.topLevelItemCount() == 0


def test_sftp_directory_items_are_expandable_tree_nodes(monkeypatch) -> None:
    browser = _browser(monkeypatch)
    files = [
        RemoteFile(
            path="/var",
            name="var",
            size=0,
            file_type=FileType.DIRECTORY,
        ),
        RemoteFile(
            path="/file.txt",
            name="file.txt",
            size=1,
            file_type=FileType.FILE,
        ),
    ]

    browser._on_directory_loaded(files, "/")

    assert browser.file_tree.rootIsDecorated()
    first = browser.file_tree.topLevelItem(0)
    assert "var" in first.text(0)
    assert first.childCount() == 1
    assert first.child(0).text(0) == "Loading..."


def test_sftp_file_rows_are_compact_dark_table_entries(monkeypatch) -> None:
    browser = _browser(monkeypatch)
    files = [
        RemoteFile(
            path="/var",
            name="var",
            size=0,
            file_type=FileType.DIRECTORY,
            permissions=493,
            modified_at=1_617_041_630,
        ),
        RemoteFile(
            path="/file.txt",
            name="file.txt",
            size=1536,
            file_type=FileType.FILE,
            permissions="644",
            modified_at=1_617_041_630,
        ),
    ]

    browser._on_directory_loaded(files, "/")

    assert not browser.file_tree.alternatingRowColors()
    assert browser.file_tree.headerItem().text(3) == "Perm"
    folder = browser.file_tree.topLevelItem(0)
    file_item = browser.file_tree.topLevelItem(1)
    assert folder.text(0) == "[D] var"
    assert folder.text(2) == "Folder"
    assert folder.text(3) == "755"
    assert folder.text(4).startswith("2021-03-")
    assert file_item.text(0) == "    file.txt"
    assert file_item.text(1) == "1.5 KB"
    assert file_item.text(2) == "File"


def test_sftp_child_directory_load_populates_expanded_node(monkeypatch) -> None:
    browser = _browser(monkeypatch)
    parent_file = RemoteFile(
        path="/var",
        name="var",
        size=0,
        file_type=FileType.DIRECTORY,
    )
    parent_item = browser._directory_item(parent_file)
    children = [
        RemoteFile(
            path="/var/log",
            name="log",
            size=0,
            file_type=FileType.DIRECTORY,
        )
    ]

    browser._on_directory_loaded(children, "/var", parent_item)

    assert parent_item.childCount() == 1
    assert "log" in parent_item.child(0).text(0)
    assert parent_item.data(0, Qt.UserRole + 1) is True


def test_sftp_child_directory_load_ignores_deleted_items(monkeypatch) -> None:
    browser = _browser(monkeypatch)

    class DeletedItem:
        def treeWidget(self):
            raise RuntimeError("already deleted")

    browser._on_directory_loaded([], "/var", DeletedItem())


def test_sftp_edit_file_prompts_before_temp_download(monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    browser = _browser(monkeypatch)
    remote = RemoteFile(
        path="/home/user/AGENTS.md",
        name="AGENTS.md",
        size=1024,
        file_type=FileType.FILE,
    )
    item = browser._file_item(remote)
    asked = []
    monkeypatch.setattr(
        "openadmindesk.ui.sftp_file_browser.QMessageBox.question",
        lambda *args, **kwargs: asked.append(args) or QMessageBox.No,
    )

    browser._edit_file(item)

    assert asked


def test_sftp_navigation_history_tracks_path_changes(monkeypatch) -> None:
    browser = _browser(monkeypatch)
    browser._connected = True
    loaded: list[str] = []
    monkeypatch.setattr(browser, "_load_directory", lambda: loaded.append(browser.current_path))

    browser._navigate_to("/var")
    browser._navigate_to("/var/log")
    browser._go_back()
    browser._go_forward()

    assert loaded == ["/var", "/var/log", "/var", "/var/log"]
    assert browser.path_input.text() == "/var/log"
    assert browser.back_btn.isEnabled()
    assert not browser.forward_btn.isEnabled()


def test_sftp_path_input_normalizes_relative_paths(monkeypatch) -> None:
    browser = _browser(monkeypatch)
    browser._connected = True
    loaded: list[str] = []
    monkeypatch.setattr(browser, "_load_directory", lambda: loaded.append(browser.current_path))

    browser.path_input.setText("tmp//logs/")
    browser._navigate_from_path_input()

    assert browser.current_path == "/tmp/logs"
    assert loaded == ["/tmp/logs"]


def test_sftp_hidden_toggle_filters_dotfiles(monkeypatch) -> None:
    browser = _browser(monkeypatch)
    files = [
        RemoteFile(
            path="/visible.txt",
            name="visible.txt",
            size=1,
            file_type=FileType.FILE,
        ),
        RemoteFile(
            path="/.hidden",
            name=".hidden",
            size=1,
            file_type=FileType.FILE,
        ),
    ]

    browser._on_directory_loaded(files, "/")
    assert browser.file_tree.topLevelItemCount() == 1
    assert "visible.txt" in browser.file_tree.topLevelItem(0).text(0)

    browser.hidden_btn.setChecked(True)
    browser._on_directory_loaded(files, "/")
    names = [
        browser.file_tree.topLevelItem(index).text(0)
        for index in range(browser.file_tree.topLevelItemCount())
    ]
    assert any(".hidden" in name for name in names)
