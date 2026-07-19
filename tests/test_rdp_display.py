"""Headless Qt tests for RdpDisplay widget."""

from __future__ import annotations

import pytest

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSize, QPoint, QObject, Signal
from PySide6.QtGui import QImage, QKeyEvent, QMouseEvent

from openadmindesk.ui.rdp_display import RdpDisplay


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication for headless tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class MockRdpClient(QObject):
    """Mock RdpClient that records calls for input forwarding tests."""
    
    frame_ready = Signal(QImage)
    
    def __init__(self):
        super().__init__()
        self.key_scancodes = []
        self.mouse_events = []
        self.resize_calls = []
        self.frame_ready_handlers = []
    
    def send_key_scancode(self, scancode, pressed, extended=False):
        self.key_scancodes.append((scancode, pressed, extended))
    
    def send_mouse_event(self, x, y, buttons, wheel=0):
        self.mouse_events.append((x, y, buttons, wheel))
    
    def resize_display(self, width, height):
        self.resize_calls.append((width, height))


class TestRdpDisplayDefaults:
    """Test RdpDisplay default properties and creation."""
    
    def test_creates_without_client(self, qapp):
        display = RdpDisplay()
        assert display.has_frame is False
        assert display.minimumWidth() == 640
        assert display.minimumHeight() == 480
        assert display.focusPolicy() == Qt.StrongFocus
    
    def test_creates_with_client(self, qapp):
        client = MockRdpClient()
        display = RdpDisplay(client)
        assert display.has_frame is False
    
    def test_sets_client_after_construction(self, qapp):
        client = MockRdpClient()
        display = RdpDisplay()
        display.set_client(client)
        assert display.has_frame is False


class TestRdpDisplayFrameRendering:
    """Test frame reception and rendering."""
    
    def test_receive_frame_updates_has_frame(self, qapp):
        """_on_frame should set has_frame to True."""
        client = MockRdpClient()
        display = RdpDisplay(client)
        
        image = QImage(100, 50, QImage.Format_ARGB32)
        image.fill(Qt.red)
        
        display._on_frame(image)
        assert display.has_frame is True
    
    def test_receive_null_frame_is_ignored(self, qapp):
        """Null QImage should be ignored."""
        client = MockRdpClient()
        display = RdpDisplay(client)
        
        display._on_frame(QImage())  # null image
        assert display.has_frame is False
    
    def test_paint_does_not_crash_without_frame(self, qapp):
        """Paint should handle null frame gracefully."""
        client = MockRdpClient()
        display = RdpDisplay(client)
        display.resize(800, 600)
        # Force repaint — should not crash
        display.repaint()
        assert True  # no crash


class TestRdpDisplayKeyboardEvents:
    """Test keyboard event forwarding through scancode mapping."""
    
    def test_key_press_forwarded_to_client(self, qapp):
        client = MockRdpClient()
        display = RdpDisplay(client)
        
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_A, Qt.NoModifier, "a")
        display.keyPressEvent(event)
        
        assert len(client.key_scancodes) >= 1
        # 'A' key should map to scancode 0x1E
        scancode, pressed, extended = client.key_scancodes[0]
        assert pressed is True
    
    def test_key_release_forwarded_to_client(self, qapp):
        client = MockRdpClient()
        display = RdpDisplay(client)
        
        event = QKeyEvent(QKeyEvent.KeyRelease, Qt.Key_A, Qt.NoModifier, "a")
        display.keyReleaseEvent(event)
        
        assert len(client.key_scancodes) >= 1
        scancode, pressed, extended = client.key_scancodes[0]
        assert pressed is False
    
    def test_escape_key_mapped_correctly(self, qapp):
        client = MockRdpClient()
        display = RdpDisplay(client)
        
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
        display.keyPressEvent(event)
        
        assert len(client.key_scancodes) >= 1
        assert client.key_scancodes[0][0] == 0x01  # Escape scancode
    
    def test_enter_key_mapped_correctly(self, qapp):
        client = MockRdpClient()
        display = RdpDisplay(client)
        
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Enter, Qt.NoModifier)
        display.keyPressEvent(event)
        
        assert len(client.key_scancodes) >= 1
        assert client.key_scancodes[0][0] == 0x1C  # Enter scancode
    
    def test_unmapped_key_no_forward(self, qapp):
        client = MockRdpClient()
        display = RdpDisplay(client)
        
        # Qt.Key_Dead_Grave has no mapping — should not forward
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Dead_Grave, Qt.NoModifier)
        display.keyPressEvent(event)
        
        assert len(client.key_scancodes) == 0
    
    def test_no_client_after_key_event(self, qapp):
        """Key event without client should not crash."""
        display = RdpDisplay()  # no client
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_A, Qt.NoModifier, "a")
        display.keyPressEvent(event)
        assert True  # no crash


class TestRdpDisplayMouseEvents:
    """Test mouse event forwarding."""
    
    def test_mouse_press_forwarded(self, qapp):
        client = MockRdpClient()
        display = RdpDisplay(client)
        display.resize(800, 600)
        
        event = QMouseEvent(
            QMouseEvent.MouseButtonPress, QPoint(100, 150), Qt.LeftButton,
            Qt.LeftButton, Qt.NoModifier
        )
        display.mousePressEvent(event)
        
        assert len(client.mouse_events) >= 1
        x, y, buttons, wheel = client.mouse_events[0]
        assert buttons != 0  # should have flags
    
    def test_mouse_move_forwarded(self, qapp):
        client = MockRdpClient()
        display = RdpDisplay(client)
        display.resize(800, 600)
        
        event = QMouseEvent(
            QMouseEvent.MouseMove, QPoint(200, 300), Qt.NoButton,
            Qt.NoButton, Qt.NoModifier
        )
        display.mouseMoveEvent(event)
        
        assert len(client.mouse_events) >= 1
    
    def test_no_client_after_mouse_event(self, qapp):
        """Mouse event without client should not crash."""
        display = RdpDisplay()
        display.resize(800, 600)
        event = QMouseEvent(
            QMouseEvent.MouseButtonPress, QPoint(100, 150), Qt.LeftButton,
            Qt.LeftButton, Qt.NoModifier
        )
        display.mousePressEvent(event)
        assert True  # no crash


class TestRdpDisplayResize:
    """Test resize handling."""
    
    def test_resize_notifies_client(self, qapp):
        from PySide6.QtGui import QResizeEvent
        client = MockRdpClient()
        display = RdpDisplay(client)
        
        new_size = QSize(1920, 1080)
        event = QResizeEvent(new_size, QSize(800, 600))
        display.resizeEvent(event)
        
        assert len(client.resize_calls) >= 1
        assert client.resize_calls[0] == (1920, 1080)
