"""Generated session icons for OpenAdminDesk UI."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap

from openadmindesk.core.profile import SessionType


@dataclass(frozen=True)
class SessionIconSpec:
    icon_id: str
    label: str
    glyph: str
    bg: str
    fg: str = "#ffffff"


SESSION_ICON_SPECS: tuple[SessionIconSpec, ...] = (
    SessionIconSpec("ssh", "SSH", ">", "#207cca"),
    SessionIconSpec("terminal", "Terminal", "$", "#2d2d30"),
    SessionIconSpec("server", "Server", "SRV", "#52616b"),
    SessionIconSpec("linux", "Linux", "LX", "#3f7f3f"),
    SessionIconSpec("rdp", "RDP", "R", "#2b64d8"),
    SessionIconSpec("windows", "Windows", "WIN", "#0078d4"),
    SessionIconSpec("telnet", "Telnet", "TN", "#7a4fb7"),
    SessionIconSpec("vnc", "VNC", "V", "#c45a18"),
    SessionIconSpec("sftp", "SFTP", "S", "#1c8f72"),
    SessionIconSpec("ftp", "FTP", "F", "#b98500"),
    SessionIconSpec("shell", "Shell", "#", "#1f1f1f"),
    SessionIconSpec("database", "Database", "DB", "#8a6d3b"),
    SessionIconSpec("cloud", "Cloud", "CL", "#4d8fac"),
    SessionIconSpec("router", "Router", "RT", "#6b6f1f"),
    SessionIconSpec("lock", "Secure", "*", "#3a7d44"),
)


def icon_options() -> tuple[SessionIconSpec, ...]:
    """Return available generated session icon choices."""
    return SESSION_ICON_SPECS


def default_icon_id_for_session_type(session_type: SessionType) -> str:
    """Return a practical default icon id for a protocol type."""
    if session_type == SessionType.RDP:
        return "rdp"
    if session_type == SessionType.TELNET:
        return "telnet"
    if session_type == SessionType.LOCAL_SHELL:
        return "terminal"
    if session_type == SessionType.VNC:
        return "vnc"
    return "ssh"


def _spec_for(icon_id: str | None, session_type: SessionType | None = None) -> SessionIconSpec:
    wanted = icon_id or (
        default_icon_id_for_session_type(session_type) if session_type else "ssh"
    )
    for spec in SESSION_ICON_SPECS:
        if spec.icon_id == wanted:
            return spec
    return SESSION_ICON_SPECS[0]


@lru_cache(maxsize=64)
def _render_icon(icon_id: str, size: int) -> QIcon:
    spec = _spec_for(icon_id)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor("#111111"), max(1, size // 18)))
    painter.setBrush(QColor(spec.bg))
    margin = max(1, size // 10)
    painter.drawRoundedRect(
        margin,
        margin,
        size - margin * 2,
        size - margin * 2,
        max(3, size // 8),
        max(3, size // 8),
    )

    font = QFont("Arial")
    font.setBold(True)
    font.setPixelSize(size // (3 if len(spec.glyph) <= 1 else 4))
    painter.setFont(font)
    painter.setPen(QColor(spec.fg))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, spec.glyph)
    painter.end()

    return QIcon(pixmap)


def session_icon(icon_id: str | None, session_type: SessionType | None = None, size: int = 20) -> QIcon:
    """Return a generated QIcon for a saved icon id/protocol pair."""
    spec = _spec_for(icon_id, session_type)
    return _render_icon(spec.icon_id, size)

