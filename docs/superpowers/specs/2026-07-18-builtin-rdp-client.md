# Built-in RDP Client Specification

Date: 2026-07-18
Status: Design (pre-implementation)
Scope: Phase 10 of AUDIT_REMEDIATION_PLAN.md

## Goal

Replace subprocess-launched system RDP clients (xfreerdp, mstsc.exe) with a
built-in RDP client that renders inside the OpenAdminDesk application window
and works identically across all build variants (AppImage, deb, rpm, exe).

## Architecture

FreeRDP is a mature C library (Apache 2.0) implementing the full RDP protocol.
We wrap `libfreerdp-client3` via Python `ctypes` and render frames into a
Qt `QWidget` using `QImage`/`QPainter`.

### Component diagram

```
┌─────────────────────────────────────────────────┐
│  RdpSessionTab (UI)                             │
│  ┌───────────────────────────────────────────┐  │
│  │  RdpDisplay (QWidget)                     │  │
│  │  - Renders RDP frames via QPainter        │  │
│  │  - Handles mouse/keyboard events          │  │
│  │  - Resize → FreeRDP UpdateMonitor         │  │
│  └───────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────┐  │
│  │  Toolbar: Connect/Disconnect, Send Ctrl-  │  │
│  │  Alt-Del, Fullscreen toggle               │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
         │ signals/slots (main thread)
         ▼
┌─────────────────────────────────────────────────┐
│  RdpClient (core)                               │
│  - ctypes wrapper over libfreerdp-client3       │
│  - Runs on dedicated thread (Qt-style worker)   │
│  - Emits: frame_ready(QImage), connected(),     │
│    disconnected(), error(str)                   │
│  - Receives: connect(), disconnect(),           │
│    send_key_event(), send_mouse_event(),        │
│    resize(width, height)                        │
└─────────────────────────────────────────────────┘
         │ ctypes calls
         ▼
┌─────────────────────────────────────────────────┐
│  libfreerdp-client3.so / freerdp-client3.dll    │
│  (bundled with app)                             │
└─────────────────────────────────────────────────┘
```

### Key design decisions

1. **ctypes, not CFFI or Cython** — zero build-time dependencies, pure Python
   integration. FreeRDP public API is C ABI, stable enough for ctypes.

2. **Qt thread boundary** — `RdpClient` inherits `QObject`, runs on a
   `QThread`. Frame callbacks post `QImage` via signal to `RdpDisplay`.
   Matches the existing `SSHTerminalBackend` worker/signal pattern.

3. **Frame rendering** — FreeRDP provides raw BGRA/XRGB pixel buffers.
   We wrap them with `QImage` (zero-copy when possible) and paint via
   `QPainter::drawImage`. No intermediate copies.

4. **Bundling strategy**:
   - **AppImage**: `libfreerdp-client3.so` placed in `AppDir/usr/lib`,
     `LD_LIBRARY_PATH` adjusted in AppRun
   - **deb/rpm**: depend on `libfreerdp-client3` system package
   - **Windows exe**: PyInstaller collects `freerdp-client3.dll` as data file,
     placed next to exe
   - **Linux fallback**: if bundled .so not found, try system library path

5. **Authentication** — NLA (Network Level Authentication) via FreeRDP's
   built-in CredSSP. Credentials from Profile/Vault, never passed on
   command line.

6. **Security**: `/cert:tofu` equivalent via FreeRDP certificate callback —
   prompt user on first connect, store thumbprint.

### New files

- `src/openadmindesk/core/rdp_client.py` — ctypes wrapper for libfreerdp-client3
- `src/openadmindesk/ui/rdp_display.py` — QWidget for RDP frame rendering
- `tests/test_rdp_client.py` — unit tests for ctypes wrapper (mock library)
- `tests/test_rdp_display.py` — Qt widget tests

### Modified files

- `src/openadmindesk/core/rdp_backend.py` — replace subprocess with RdpClient calls
- `src/openadmindesk/ui/rdp_session_tab.py` — replace control panel with RdpDisplay widget
- `src/openadmindesk/platform/platform_utils.py` — add `find_freerdp_library()` replacing `find_rdp_binary()`
- `pyproject.toml` — no new Python dependencies (ctypes is stdlib)
- `tools/build.py` — add FreeRDP library bundling steps
- `packaging/linux/openadmindesk.desktop` — unchanged (no new system deps for AppImage)
- Debian control / RPM spec (in build.py) — add `libfreerdp-client3` dependency

### Profile model changes
None. Existing RDP Profile fields are sufficient.

### RdpClient API (ctypes wrapper)

```python
class RdpClient(QObject):
    # Signals (emitted from worker thread, queued to main thread)
    frame_ready = Signal(QImage)          # new frame available
    connected = Signal()                  # session established
    disconnected = Signal()               # session ended
    error_occurred = Signal(str)          # connection/ protocol error

    def __init__(self, profile: Profile, parent=None): ...
    def connect_to_host(self) -> None:    # starts async connection
    def disconnect(self) -> None:         # graceful disconnect
    def send_key_scancode(self, scancode: int, pressed: bool, extended: bool) -> None:
    def send_mouse_event(self, x: int, y: int, buttons: int, wheel: int) -> None:
    def resize_display(self, width: int, height: int) -> None:
    def send_ctrl_alt_del(self) -> None:
```

### RdpDisplay widget

```python
class RdpDisplay(QWidget):
    """Qt widget that renders RDP frames and captures input events."""

    def __init__(self, rdp_client: RdpClient, parent=None): ...
    def paintEvent(self, event) -> None:        # draw current frame
    def resizeEvent(self, event) -> None:       # notify FreeRDP
    def keyPressEvent(self, event) -> None:     # forward to RdpClient
    def keyReleaseEvent(self, event) -> None:   # forward to RdpClient
    def mousePressEvent(self, event) -> None:   # forward to RdpClient
    def mouseReleaseEvent(self, event) -> None: # forward to RdpClient
    def mouseMoveEvent(self, event) -> None:    # forward to RdpClient
    def wheelEvent(self, event) -> None:        # forward to RdpClient
    def _on_frame(self, image: QImage) -> None: # slot, calls update()
```

### FreeRDP library binding scope

Initial ctypes binding covers:
- `freerdp_client_context_new` / `freerdp_client_context_free`
- `freerdp_client_settings_parse_ini` or direct settings struct
- `freerdp_connect` / `freerdp_disconnect`
- `freerdp_client_start` / `freerdp_client_stop`
- Update callback registration (frame buffer pointer)
- Certificate verification callback
- Keyboard/mouse input functions
- Clipboard channel integration (later phase)

### Phase 10 task breakdown

- [ ] 10.1: Add `find_freerdp_library()` to platform_utils; ctypes struct definitions
- [ ] 10.2: Implement `RdpClient` core wrapper (connect, disconnect, event loop)
- [ ] 10.3: Implement `RdpDisplay` Qt widget (frame rendering, input forwarding)
- [ ] 10.4: Rewrite `RdpSessionTab` to use RdpDisplay (remove control panel)
- [ ] 10.5: Certificate verification UI (TOFU dialog)
- [ ] 10.6: NLA/CredSSP authentication integration
- [ ] 10.7: Packaging — bundle FreeRDP library for AppImage/deb/rpm/exe
- [ ] 10.8: Tests — mock FreeRDP for RdpClient, headless tests for RdpDisplay
- [ ] 10.9: Fullscreen toggle, Ctrl-Alt-Del, clipboard sync
- [ ] 10.10: Documentation — update INSTALL.md, USER_GUIDE.md, SECURITY_MODEL.md

### Non-goals for Phase 10

- Audio redirection (requires PulseAudio/pipewire integration)
- USB device redirection
- RemoteApp (seamless windows)
- RDP file import/export
- AVC/H.264 hardware decoding (software fallback only initially)
- Gateway load balancing

### Verification plan

Each sub-task requires:
- `python3 -m py_compile` for changed files
- `ruff check` for changed files
- Targeted `pytest` for the task's test files
- Full headless pytest before marking task complete

Manual smoke test: connect to Windows RDP host, verify display, keyboard,
mouse, resize, disconnect. Test on Linux and Windows.

### Dependencies and risks

- **FreeRDP version**: target FreeRDP 3.x (stable, actively maintained).
  FreeRDP 2.x is end-of-life.
- **ctypes complexity**: FreeRDP client API is ~50 functions; ctypes wrapper
  is straightforward but requires careful struct layout.
- **Platform differences**: Linux uses X11/Wayland; Windows uses Win32.
  FreeRDP abstracts these — our ctypes layer should work identically.
- **Performance**: Software rendering of RDP frames at 30+ fps is CPU-intensive.
  Acceptable for administration use (not video playback). Hardware acceleration
  is a future optimization.
- **Windows PyInstaller**: must include freerdp-client3.dll and all transitive
  DLL dependencies (libwinpr3.dll, libssl-3-x64.dll, etc.)
