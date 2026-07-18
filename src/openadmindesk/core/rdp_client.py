"""FreeRDP client ctypes definitions — structs, callbacks, and constants.

Wraps libfreerdp-client3 (FreeRDP 3.x) for built-in RDP sessions.
No Qt or threading dependencies — pure ctypes definitions.
"""

from __future__ import annotations

import ctypes
from ctypes import (
    c_void_p, c_char_p, c_bool, c_uint16, c_uint32,
    CFUNCTYPE, Structure,
)
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Connection error codes (freerdp.h)
FREERDP_ERROR_SUCCESS = 0
FREERDP_ERROR_CONNECT_FAILED = 1
FREERDP_ERROR_AUTHENTICATION_FAILED = 2
FREERDP_ERROR_CONNECT_CANCELLED = 3
FREERDP_ERROR_TLS_CONNECT_FAILED = 4

# Certificate verification results
CERT_STORE_RESULT_MATCH = 1
CERT_STORE_RESULT_MISMATCH = 2
CERT_STORE_RESULT_NOT_FOUND = 3

# Keyboard flags
KBD_FLAGS_DOWN = 0x0000
KBD_FLAGS_RELEASE = 0x8000
KBD_FLAGS_EXTENDED = 0x0100

# Mouse button flags
PTR_FLAGS_WHEEL = 0x0200
PTR_FLAGS_WHEEL_NEGATIVE = 0x0100
PTR_FLAGS_MOVE = 0x0800
PTR_FLAGS_DOWN = 0x8000
PTR_FLAGS_BUTTON1 = 0x1000
PTR_FLAGS_BUTTON2 = 0x2000
PTR_FLAGS_BUTTON3 = 0x4000

# ---------------------------------------------------------------------------
# Opaque handles (forward declarations)
# ---------------------------------------------------------------------------

class rdpContext(Structure):
    """Opaque RDP context — defined fully by FreeRDP internals."""
    _fields_: list = []  # opaque to us, passed as pointer


class rdpSettings(Structure):
    """Opaque RDP settings struct."""
    _fields_: list = []  # opaque


class rdpClientContext(Structure):
    """Client context containing rdpContext and client-specific data."""
    _fields_: list = []  # opaque


# ---------------------------------------------------------------------------
# Utility class for loading the FreeRDP shared library
# ---------------------------------------------------------------------------

class FreeRdpLibrary:
    """Loads and provides access to libfreerdp-client3 symbols via ctypes."""

    def __init__(self) -> None:
        self._lib: Optional[ctypes.CDLL] = None
        self._path: Optional[str] = None

    def load(self, path: str) -> bool:
        """Load the FreeRDP shared library from the given path.

        Returns True on success, False on failure.
        """
        try:
            self._lib = ctypes.CDLL(path)
            self._path = path
            return True
        except OSError:
            self._lib = None
            self._path = None
            return False

    @property
    def is_loaded(self) -> bool:
        return self._lib is not None

    @property
    def path(self) -> Optional[str]:
        return self._path

    @property
    def lib(self) -> Optional[ctypes.CDLL]:
        return self._lib


# ---------------------------------------------------------------------------
# Callback type definitions (matching FreeRDP C signatures)
# ---------------------------------------------------------------------------

# Certificate verification callback:
#   typedef BOOL (*pcCertVerify)(char* host, char* fingerprint, char* subject,
#                                char* issuer, DWORD flags);
CERT_VERIFY_CALLBACK = CFUNCTYPE(
    c_bool,
    c_char_p,   # host
    c_char_p,   # fingerprint
    c_char_p,   # subject
    c_char_p,   # issuer
    c_uint32,   # flags
)

# Frame update callback — called when FreeRDP has a new frame ready:
#   typedef BOOL (*pcUpdateBegin)(rdpContext* context);
# We define it generically for the frame buffer pointer callback.
FRAME_UPDATE_CALLBACK = CFUNCTYPE(
    c_bool,
    c_void_p,  # rdpContext*
)

# Connection result callback:
#   typedef DWORD (*pcFreerdpClientEvent)(rdpClientContext* context, DWORD event);
CLIENT_EVENT_CALLBACK = CFUNCTYPE(
    c_uint32,
    c_void_p,   # rdpClientContext*
    c_uint32,   # event id
)

# Keyboard event callback:
KEYBOARD_EVENT_CALLBACK = CFUNCTYPE(
    None,
    c_void_p,   # context
    c_uint16,   # flags
    c_uint16,   # scancode
)

# Mouse event callback:
MOUSE_EVENT_CALLBACK = CFUNCTYPE(
    None,
    c_void_p,   # context
    c_uint16,   # flags
    c_uint16,   # x
    c_uint16,   # y
)

# ---------------------------------------------------------------------------
# Frame buffer info struct
# ---------------------------------------------------------------------------

class RdpFrameBuffer(Structure):
    """Describes a decoded RDP frame buffer from FreeRDP.

    FreeRDP calls our update callback with this struct. The pixel data
    is in BGRA32 or XRGB32 format, width * height * 4 bytes.
    """
    _fields_ = [
        ("width", c_uint32),
        ("height", c_uint32),
        ("scanline", c_uint32),         # bytes per row (negative = top-down)
        ("bits_per_pixel", c_uint16),
        ("bytes_per_pixel", c_uint16),
        ("pixels", c_void_p),           # pointer to raw pixel buffer
        ("format", c_uint32),           # pixel format id
    ]


# ---------------------------------------------------------------------------
# Client entry point helper
# ---------------------------------------------------------------------------

def _resolve_symbol(lib: ctypes.CDLL, name: str, restype=None, argtypes=None):
    """Resolve and type-annotate a ctypes function symbol.

    Returns the typed function, or None if the symbol is not found.
    """
    try:
        func = getattr(lib, name)
        if restype is not None:
            func.restype = restype
        if argtypes is not None:
            func.argtypes = argtypes
        return func
    except AttributeError:
        return None

# ---------------------------------------------------------------------------
# RdpClient — QObject wrapper for FreeRDP client lifecycle
# ---------------------------------------------------------------------------

import logging
import queue
from PySide6.QtCore import QObject, QThread, Signal, Slot, QMutex, QMutexLocker
from PySide6.QtGui import QImage
from ctypes import c_int

try:
    from openadmindesk.core.profile import Profile
except ImportError:
    Profile = None

# FreeRDP setting IDs (from freerdp/settings.h)
FREERDP_SETTING_HOST = 0
FREERDP_SETTING_PORT = 1
FREERDP_SETTING_USERNAME = 2
FREERDP_SETTING_PASSWORD = 3
FREERDP_SETTING_CERT_ACCEPT = 32
FREERDP_SETTING_GATEWAY_HOST = 50
FREERDP_SETTING_GATEWAY_USERNAME = 51
FREERDP_SETTING_GATEWAY_PASSWORD = 52


logger = logging.getLogger(__name__)


class RdpClient(QObject):
    """Qt wrapper for a FreeRDP client session.

    Manages the FreeRDP library lifecycle on a dedicated QThread.
    All ctypes callbacks run on the worker thread; frame and status
    updates are posted to the main thread via signals.
    """

    frame_ready = Signal(QImage)
    connected = Signal()
    disconnected = Signal()
    error_occurred = Signal(str)

    def __init__(self, profile=None, parent=None):
        super().__init__(parent)
        self._profile = profile
        self._library = FreeRdpLibrary()
        self._thread = None
        self._worker = None
        self._mutex = QMutex()
        self._connected = False
        self._error_message = ""

    def connect_to_host(self):
        """Start an asynchronous RDP connection on a worker thread."""
        with QMutexLocker(self._mutex):
            if self._connected:
                return

            from openadmindesk.platform.platform_utils import find_freerdp_library
            lib_path = find_freerdp_library()
            if not lib_path:
                self.error_occurred.emit(
                    "FreeRDP library (libfreerdp-client3) not found."
                )
                return

            if not self._library.load(lib_path):
                self.error_occurred.emit(
                    f"Failed to load FreeRDP library from {lib_path}"
                )
                return

            self._thread = QThread()
            self._worker = _RdpWorker(self._profile, self._library)
            self._worker.moveToThread(self._thread)

            self._worker.frame_ready.connect(self._on_frame_ready)
            self._worker.connected.connect(self._on_connected)
            self._worker.disconnected.connect(self._on_disconnected)
            self._worker.error_occurred.connect(self._on_worker_error)

            self._thread.started.connect(self._worker.run)
            self._worker.finished.connect(self._thread.quit)
            self._worker.finished.connect(self._worker.deleteLater)
            self._thread.finished.connect(self._thread.deleteLater)
            self._thread.finished.connect(self._on_thread_finished)

            self._thread.start()

    def disconnect(self):
        """Request graceful disconnect."""
        with QMutexLocker(self._mutex):
            if self._worker is not None:
                self._worker.request_stop()

    def send_key_scancode(self, scancode, pressed, extended=False):
        worker = self._worker
        if worker is not None:
            worker.enqueue_key(scancode, pressed, extended)

    def send_mouse_event(self, x, y, buttons, wheel=0):
        worker = self._worker
        if worker is not None:
            worker.enqueue_mouse(x, y, buttons, wheel)

    def resize_display(self, width, height):
        worker = self._worker
        if worker is not None:
            worker.enqueue_resize(width, height)

    def send_ctrl_alt_del(self):
        worker = self._worker
        if worker is not None:
            worker.enqueue_ctrl_alt_del()

    def is_connected(self):
        return self._connected

    @property
    def error_message(self):
        return self._error_message

    @Slot(QImage)
    def _on_frame_ready(self, image):
        self.frame_ready.emit(image)

    @Slot()
    def _on_connected(self):
        self._connected = True
        self.connected.emit()

    @Slot()
    def _on_disconnected(self):
        self._connected = False
        self.disconnected.emit()

    @Slot(str)
    def _on_worker_error(self, message):
        self._error_message = message
        self.error_occurred.emit(message)

    @Slot()
    def _on_thread_finished(self):
        with QMutexLocker(self._mutex):
            self._connected = False
            self._thread = None
            self._worker = None


class _RdpWorker(QObject):
    """Internal worker — runs FreeRDP event loop on a QThread."""

    frame_ready = Signal(QImage)
    connected = Signal()
    disconnected = Signal()
    error_occurred = Signal(str)
    finished = Signal()

    def __init__(self, profile, library, parent=None):
        super().__init__(parent)
        self._profile = profile
        self._library = library
        self._stop_requested = False
        self._key_queue = queue.Queue()
        self._mouse_queue = queue.Queue()
        self._resize_requested = None
        self._ctrl_alt_del_requested = False
        self._context = None

    @Slot()
    def run(self):
        """Load FreeRDP symbols, create context, connect, and run event loop."""
        lib = self._library.lib
        if lib is None:
            self.error_occurred.emit("FreeRDP library not loaded")
            self.finished.emit()
            return

        freerdp_new = _resolve_symbol(lib, "freerdp_client_context_new",
                                      restype=ctypes.c_void_p,
                                      argtypes=[c_int])
        freerdp_free = _resolve_symbol(lib, "freerdp_client_context_free",
                                       restype=None,
                                       argtypes=[ctypes.c_void_p])
        freerdp_connect = _resolve_symbol(lib, "freerdp_connect",
                                          restype=c_int,
                                          argtypes=[ctypes.c_void_p])
        freerdp_start = _resolve_symbol(lib, "freerdp_client_start",
                                        restype=c_int,
                                        argtypes=[ctypes.c_void_p])
        freerdp_stop = _resolve_symbol(lib, "freerdp_client_stop",
                                       restype=c_int,
                                       argtypes=[ctypes.c_void_p])
        freerdp_disconnect = _resolve_symbol(lib, "freerdp_disconnect",
                                             restype=c_int,
                                             argtypes=[ctypes.c_void_p])

        if not all([freerdp_new, freerdp_free, freerdp_connect,
                    freerdp_start, freerdp_stop, freerdp_disconnect]):
            self.error_occurred.emit(
                "Required FreeRDP symbols missing in loaded library"
            )
            self.finished.emit()
            return

        ctx = freerdp_new(1)
        if not ctx:
            self.error_occurred.emit("freerdp_client_context_new returned NULL")
            self.finished.emit()
            return

        self._context = ctx
        self._configure_settings(ctx, lib)
        self._register_callbacks(ctx, lib)

        rc = freerdp_connect(ctx)
        if rc != 0:
            self.error_occurred.emit(f"RDP connection failed (code {rc})")
            self._cleanup(freerdp_disconnect, freerdp_free)
            self.finished.emit()
            return

        self.connected.emit()

        while not self._stop_requested:
            self._flush_input()
            rc = freerdp_start(ctx)
            if rc != 0:
                break
            QThread.msleep(10)

        freerdp_stop(ctx)
        self._cleanup(freerdp_disconnect, freerdp_free)
        self.disconnected.emit()
        self.finished.emit()

    def request_stop(self):
        self._stop_requested = True

    def _cleanup(self, freerdp_disconnect, freerdp_free):
        ctx = self._context
        if ctx is not None:
            try:
                freerdp_disconnect(ctx)
            except Exception:
                pass
            try:
                freerdp_free(ctx)
            except Exception:
                pass
            self._context = None

    def enqueue_key(self, scancode, pressed, extended):
        self._key_queue.put((scancode, pressed, extended))

    def enqueue_mouse(self, x, y, buttons, wheel):
        self._mouse_queue.put((x, y, buttons, wheel))

    def enqueue_resize(self, width, height):
        self._resize_requested = (width, height)

    def enqueue_ctrl_alt_del(self):
        self._ctrl_alt_del_requested = True

    def _flush_input(self):
        while not self._key_queue.empty():
            sc, pr, ext = self._key_queue.get_nowait()
            self._send_key_internal(sc, pr, ext)
        while not self._mouse_queue.empty():
            x, y, bt, wh = self._mouse_queue.get_nowait()
            self._send_mouse_internal(x, y, bt, wh)
        if self._resize_requested is not None:
            w, h = self._resize_requested
            self._resize_requested = None
            self._send_resize_internal(w, h)
        if self._ctrl_alt_del_requested:
            self._ctrl_alt_del_requested = False
            self._send_ctrl_alt_del_internal()

    def _send_key_internal(self, scancode, pressed, extended):
        ctx = self._context
        lib = self._library.lib
        if ctx is None or lib is None:
            return
        send_key = _resolve_symbol(lib, "freerdp_input_send_keyboard_event",
                                   restype=None,
                                   argtypes=[ctypes.c_void_p, c_uint16, c_uint16])
        if send_key is None:
            return
        flags = KBD_FLAGS_DOWN if pressed else KBD_FLAGS_RELEASE
        if extended:
            flags |= KBD_FLAGS_EXTENDED
        try:
            send_key(ctx, c_uint16(flags), c_uint16(scancode))
        except Exception:
            pass

    def _send_mouse_internal(self, x, y, buttons, wheel):
        ctx = self._context
        lib = self._library.lib
        if ctx is None or lib is None:
            return
        send_mouse = _resolve_symbol(lib, "freerdp_input_send_mouse_event",
                                     restype=None,
                                     argtypes=[ctypes.c_void_p, c_uint16, c_uint16, c_uint16])
        if send_mouse is None:
            return
        try:
            send_mouse(ctx, c_uint16(buttons), c_uint16(x), c_uint16(y))
        except Exception:
            pass

    def _send_resize_internal(self, width, height):
        ctx = self._context
        lib = self._library.lib
        if ctx is None or lib is None:
            return
        resize_func = _resolve_symbol(lib, "freerdp_client_resize_display",
                                      restype=None,
                                      argtypes=[ctypes.c_void_p, c_uint32, c_uint32])
        if resize_func is None:
            return
        try:
            resize_func(ctx, c_uint32(width), c_uint32(height))
        except Exception:
            pass

    def _send_ctrl_alt_del_internal(self):
        for sc, ext in [(0x1D, False), (0x38, False), (0x53, True)]:
            self._send_key_internal(sc, True, ext)
        for sc, ext in [(0x53, True), (0x38, False), (0x1D, False)]:
            self._send_key_internal(sc, False, ext)

    def _configure_settings(self, ctx, lib):
        profile = self._profile
        if profile is None:
            return
        set_server = _resolve_symbol(lib, "freerdp_settings_set_string",
                                     restype=None,
                                     argtypes=[ctypes.c_void_p, c_uint32, c_char_p])
        set_uint32 = _resolve_symbol(lib, "freerdp_settings_set_uint32",
                                     restype=None,
                                     argtypes=[ctypes.c_void_p, c_uint32, c_uint32])
        set_bool = _resolve_symbol(lib, "freerdp_settings_set_bool",
                                   restype=None,
                                   argtypes=[ctypes.c_void_p, c_uint32, c_bool])
        if set_server is None or set_uint32 is None:
            return
        if profile.host:
            set_server(ctx, FREERDP_SETTING_HOST, profile.host.encode("utf-8"))
        if profile.port:
            set_uint32(ctx, FREERDP_SETTING_PORT, profile.port)
        if profile.username:
            set_server(ctx, FREERDP_SETTING_USERNAME, profile.username.encode("utf-8"))
        if profile.password:
            set_server(ctx, FREERDP_SETTING_PASSWORD, profile.password.encode("utf-8"))
        if profile.rdp_gateway:
            set_server(ctx, FREERDP_SETTING_GATEWAY_HOST, profile.rdp_gateway.encode("utf-8"))
        if profile.rdp_gateway_username:
            set_server(ctx, FREERDP_SETTING_GATEWAY_USERNAME, profile.rdp_gateway_username.encode("utf-8"))
        if profile.rdp_gateway_password:
            set_server(ctx, FREERDP_SETTING_GATEWAY_PASSWORD, profile.rdp_gateway_password.encode("utf-8"))
        if set_bool and getattr(profile, "rdp_certificate_policy", "") in ("auto", "tofu"):
            set_bool(ctx, FREERDP_SETTING_CERT_ACCEPT, True)

    def _register_callbacks(self, ctx, lib):
        update_cb = FRAME_UPDATE_CALLBACK(self._on_frame_update)
        set_update = _resolve_symbol(lib, "freerdp_client_set_update_callback",
                                     restype=None,
                                     argtypes=[ctypes.c_void_p, FRAME_UPDATE_CALLBACK])
        if set_update is not None:
            set_update(ctx, update_cb)
        event_cb = CLIENT_EVENT_CALLBACK(self._on_client_event)
        set_event = _resolve_symbol(lib, "freerdp_client_set_event_callback",
                                    restype=None,
                                    argtypes=[ctypes.c_void_p, CLIENT_EVENT_CALLBACK])
        if set_event is not None:
            set_event(ctx, event_cb)

    def _on_frame_update(self, context_ptr):
        """FreeRDP frame update callback — stub (Phase 10.3 will add QImage emission)."""
        try:
            return True
        except Exception:
            return False

    def _on_client_event(self, context_ptr, event_id):
        try:
            if event_id == 1:
                self.request_stop()
            return 0
        except Exception:
            return -1
