"""RDP display widget — renders FreeRDP frames and captures input events."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtGui import QPainter, QImage, QColor, QKeyEvent, QMouseEvent, QWheelEvent, QResizeEvent
from PySide6.QtCore import Qt, QSize
from typing import Optional

# Qt key → RDP scancode mapping (common keys, set 1 scancodes)
_KEY_SCANCODE_MAP: dict[int, tuple[int, bool]] = {
    Qt.Key_Escape:      (0x01, False),
    Qt.Key_1:           (0x02, False),
    Qt.Key_2:           (0x03, False),
    Qt.Key_3:           (0x04, False),
    Qt.Key_4:           (0x05, False),
    Qt.Key_5:           (0x06, False),
    Qt.Key_6:           (0x07, False),
    Qt.Key_7:           (0x08, False),
    Qt.Key_8:           (0x09, False),
    Qt.Key_9:           (0x0A, False),
    Qt.Key_0:           (0x0B, False),
    Qt.Key_Minus:       (0x0C, False),
    Qt.Key_Equal:       (0x0D, False),
    Qt.Key_Backspace:   (0x0E, False),
    Qt.Key_Tab:         (0x0F, False),
    Qt.Key_Q:           (0x10, False),
    Qt.Key_W:           (0x11, False),
    Qt.Key_E:           (0x12, False),
    Qt.Key_R:           (0x13, False),
    Qt.Key_T:           (0x14, False),
    Qt.Key_Y:           (0x15, False),
    Qt.Key_U:           (0x16, False),
    Qt.Key_I:           (0x17, False),
    Qt.Key_O:           (0x18, False),
    Qt.Key_P:           (0x19, False),
    Qt.Key_BracketLeft:  (0x1A, False),
    Qt.Key_BracketRight: (0x1B, False),
    Qt.Key_Enter:       (0x1C, False),  # main Enter
    Qt.Key_Control:     (0x1D, False),
    Qt.Key_A:           (0x1E, False),
    Qt.Key_S:           (0x1F, False),
    Qt.Key_D:           (0x20, False),
    Qt.Key_F:           (0x21, False),
    Qt.Key_G:           (0x22, False),
    Qt.Key_H:           (0x23, False),
    Qt.Key_J:           (0x24, False),
    Qt.Key_K:           (0x25, False),
    Qt.Key_L:           (0x26, False),
    Qt.Key_Semicolon:   (0x27, False),
    Qt.Key_Apostrophe:  (0x28, False),
    Qt.Key_QuoteLeft:   (0x29, False),
    Qt.Key_Shift:       (0x2A, False),
    Qt.Key_Backslash:   (0x2B, False),
    Qt.Key_Z:           (0x2C, False),
    Qt.Key_X:           (0x2D, False),
    Qt.Key_C:           (0x2E, False),
    Qt.Key_V:           (0x2F, False),
    Qt.Key_B:           (0x30, False),
    Qt.Key_N:           (0x31, False),
    Qt.Key_M:           (0x32, False),
    Qt.Key_Comma:       (0x33, False),
    Qt.Key_Period:      (0x34, False),
    Qt.Key_Slash:       (0x35, False),
    Qt.Key_Alt:         (0x38, False),
    Qt.Key_Space:       (0x39, False),
    Qt.Key_CapsLock:    (0x3A, False),
    Qt.Key_F1:          (0x3B, False),
    Qt.Key_F2:          (0x3C, False),
    Qt.Key_F3:          (0x3D, False),
    Qt.Key_F4:          (0x3E, False),
    Qt.Key_F5:          (0x3F, False),
    Qt.Key_F6:          (0x40, False),
    Qt.Key_F7:          (0x41, False),
    Qt.Key_F8:          (0x42, False),
    Qt.Key_F9:          (0x43, False),
    Qt.Key_F10:         (0x44, False),
    Qt.Key_F11:         (0x57, False),
    Qt.Key_F12:         (0x58, False),
    Qt.Key_Print:       (0x37, True),  # extended
    Qt.Key_ScrollLock:  (0x46, False),
    Qt.Key_Pause:       (0x45, False),
    Qt.Key_Insert:      (0x52, True),
    Qt.Key_Delete:      (0x53, True),
    Qt.Key_Home:        (0x47, True),
    Qt.Key_End:         (0x4F, True),
    Qt.Key_PageUp:      (0x49, True),
    Qt.Key_PageDown:    (0x51, True),
    Qt.Key_Up:          (0x48, True),
    Qt.Key_Down:        (0x50, True),
    Qt.Key_Left:        (0x4B, True),
    Qt.Key_Right:       (0x4D, True),
    Qt.Key_NumLock:     (0x45, False),
    Qt.Key_Meta:        (0x5B, True),  # Left Windows key
    Qt.Key_Menu:        (0x5D, True),  # Context menu
    # Numpad
    Qt.Key_Return:      (0x1C, True),  # Keypad Enter (extended)
}


class RdpDisplay(QWidget):
    """Widget that renders RDP frames and captures input events.

    Connects to an :class:`RdpClient` instance for frame reception
    and input forwarding.  Uses QPainter to draw the most recent
    frame, scaling it to fit the widget while preserving aspect ratio.
    """

    def __init__(
        self,
        rdp_client=None,  # RdpClient (lazy import to avoid circular deps)
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._client = rdp_client
        self._frame: Optional[QImage] = None
        self._scaled_frame: Optional[QImage] = None
        self._last_widget_size = QSize(0, 0)
        self._mouse_buttons: int = 0

        self.setMinimumSize(640, 480)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        if self._client is not None:
            self._client.frame_ready.connect(self._on_frame)

    # ── frame reception ──────────────────────────────────────────────────

    def _on_frame(self, image: QImage) -> None:
        """Slot: receive a new frame from RdpClient."""
        if image is None or image.isNull():
            return
        self._frame = image.copy()  # take ownership — safety copy
        self._scaled_frame = None   # force re-scale on next paint
        self.update()

    # ── painting ─────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        """Paint the current RDP frame, scaled to fit the widget."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        if self._frame is None or self._frame.isNull():
            # No frame yet — draw placeholder
            painter.fillRect(self.rect(), QColor(30, 30, 30))
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(
                self.rect(), Qt.AlignCenter,
                "RDP Display — waiting for connection..."
            )
            return

        # Re-scale if widget size changed or first paint
        widget_size = self.size()
        if self._scaled_frame is None or widget_size != self._last_widget_size:
            self._scaled_frame = self._frame.scaled(
                widget_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self._last_widget_size = widget_size

        # Center the scaled image
        scaled = self._scaled_frame
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2

        painter.fillRect(self.rect(), QColor(0, 0, 0))
        painter.drawImage(x, y, scaled)

    # ── keyboard events ──────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Forward key press to RdpClient as scancode."""
        if self._client is None:
            super().keyPressEvent(event)
            return

        scancode, extended = self._qt_key_to_scancode(event)
        if scancode is not None:
            self._client.send_key_scancode(scancode, True, extended)
            event.accept()
            return

        # Fallback: use native scan code if available
        native = event.nativeScanCode()
        if native > 0:
            self._client.send_key_scancode(native, True, False)
            event.accept()
            return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Forward key release to RdpClient as scancode."""
        if self._client is None:
            super().keyReleaseEvent(event)
            return

        scancode, extended = self._qt_key_to_scancode(event)
        if scancode is not None:
            self._client.send_key_scancode(scancode, False, extended)
            event.accept()
            return

        native = event.nativeScanCode()
        if native > 0:
            self._client.send_key_scancode(native, False, False)
            event.accept()
            return

        super().keyReleaseEvent(event)

    @staticmethod
    def _qt_key_to_scancode(event: QKeyEvent) -> tuple[Optional[int], bool]:
        """Map a Qt key event to an RDP scancode and extended flag.

        Returns (scancode, extended) or (None, False) if no mapping found.
        """
        key = event.key()
        if key in _KEY_SCANCODE_MAP:
            return _KEY_SCANCODE_MAP[key]
        return (None, False)

    # ── mouse events ─────────────────────────────────────────────────────

    def _make_mouse_flags(self, event: QMouseEvent) -> int:
        """Build FreeRDP PTR_FLAGS from a Qt mouse event."""
        from openadmindesk.core.rdp_client import (
            PTR_FLAGS_DOWN, PTR_FLAGS_BUTTON1, PTR_FLAGS_BUTTON2,
            PTR_FLAGS_BUTTON3, PTR_FLAGS_MOVE,
        )
        bt = event.buttons()

        flags = PTR_FLAGS_DOWN  # default: down
        if bt & Qt.LeftButton:
            flags |= PTR_FLAGS_BUTTON1
        if bt & Qt.RightButton:
            flags |= PTR_FLAGS_BUTTON2
        if bt & Qt.MiddleButton:
            flags |= PTR_FLAGS_BUTTON3

        # If no buttons are pressed, it's a move-only event
        if bt == Qt.NoButton:
            flags = PTR_FLAGS_MOVE

        return flags

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._handle_mouse(event)
        self.setFocus()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._handle_mouse(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._handle_mouse(event)

    def _handle_mouse(self, event: QMouseEvent) -> None:
        """Forward mouse event to RdpClient."""
        if self._client is None:
            return

        # Compute coordinates relative to the scaled frame
        x, y = self._widget_to_frame_coords(event.position().x(), event.position().y())

        flags = self._make_mouse_flags(event)
        self._client.send_mouse_event(int(x), int(y), flags, 0)
        event.accept()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Forward mouse wheel to RdpClient."""
        if self._client is None:
            return

        from openadmindesk.core.rdp_client import (
            PTR_FLAGS_WHEEL, PTR_FLAGS_WHEEL_NEGATIVE, PTR_FLAGS_MOVE,
        )

        delta = event.angleDelta().y()
        pos = event.position()
        x, y = self._widget_to_frame_coords(pos.x(), pos.y())

        flags = PTR_FLAGS_WHEEL
        if delta < 0:
            flags |= PTR_FLAGS_WHEEL_NEGATIVE

        self._client.send_mouse_event(int(x), int(y), flags, int(abs(delta)))
        event.accept()

    def _widget_to_frame_coords(self, wx: float, wy: float) -> tuple[float, float]:
        """Convert widget coordinates to RDP frame coordinates."""
        frame = self._frame
        if frame is None or frame.isNull():
            return (wx, wy)

        scaled = self._scaled_frame
        if scaled is None:
            return (wx, wy)

        # Calculate the offset and scale of the rendered image
        offset_x = (self.width() - scaled.width()) // 2
        offset_y = (self.height() - scaled.height()) // 2

        # Map widget coords → image coords
        img_x = wx - offset_x
        img_y = wy - offset_y

        if img_x < 0 or img_y < 0 or img_x >= scaled.width() or img_y >= scaled.height():
            return (0, 0)  # outside the frame

        # Scale up to original frame coordinates
        scale_x = frame.width() / scaled.width()
        scale_y = frame.height() / scaled.height()

        return (img_x * scale_x, img_y * scale_y)

    # ── resize ───────────────────────────────────────────────────────────

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Notify RdpClient when the widget is resized."""
        super().resizeEvent(event)
        if self._client is not None:
            new_size = event.size()
            self._client.resize_display(new_size.width(), new_size.height())

    # ── client management ────────────────────────────────────────────────

    def set_client(self, rdp_client) -> None:
        """Attach or replace the RdpClient after construction."""
        if self._client is not None:
            self._client.frame_ready.disconnect(self._on_frame)
        self._client = rdp_client
        if self._client is not None:
            self._client.frame_ready.connect(self._on_frame)

    @property
    def has_frame(self) -> bool:
        return self._frame is not None and not self._frame.isNull()
