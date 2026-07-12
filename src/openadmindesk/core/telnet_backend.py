"""Telnet backend using telnetlib3 (pure Python, async)."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Optional

# Telnet plaintext/insecure protocol retained only for explicit legacy compatibility
import telnetlib3  # nosec B401

from openadmindesk.core.profile import Profile

logger = logging.getLogger(__name__)


class TelnetBackend:
    """Telnet client backend using telnetlib3."""

    def __init__(self, profile: Profile) -> None:
        self.profile = profile
        self._connected = False
        self._reader = None
        self._writer = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._on_output: Optional[callable] = None

    def connect(self, on_output: Optional[callable] = None) -> bool:
        """Connect to the Telnet server.

        Args:
            on_output: Called with str data received from the server.
        """
        self._on_output = on_output
        try:
            host = self.profile.host
            port = self.profile.port or 23

            # Start asyncio loop in background thread
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(
                target=self._run_telnet, args=(host, port), daemon=True
            )
            self._thread.start()
            return True
        except Exception as e:
            logger.error(f"Telnet connection failed: {e}")
            return False

    def _run_telnet(self, host: str, port: int) -> None:
        """Run the telnet client in the dedicated event loop."""
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._telnet_session(host, port))
        except Exception as e:
            logger.error(f"Telnet session error: {e}")
        finally:
            self._connected = False

    async def _telnet_session(self, host: str, port: int) -> None:
        """Async telnet session using telnetlib3."""
        try:
            self._reader, self._writer = await telnetlib3.open_connection(
                host=host, port=port, term="xterm-256color",
                cols=120, rows=40, connect_minwait=1.0,
            )
            self._connected = True
            logger.info(f"Telnet connected to {host}:{port}")

            # Read loop
            while self._connected:
                try:
                    data = await asyncio.wait_for(self._reader.read(4096), timeout=0.5)
                    if data is None:
                        break
                    if self._on_output:
                        self._on_output(data)
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    break
        except Exception as e:
            logger.error(f"Telnet error: {e}")
        finally:
            self._connected = False
            if self._writer:
                try:
                    self._writer.close()
                except Exception:
                    pass

    def send(self, data: str) -> None:
        """Send data to the Telnet server."""
        if self._connected and self._writer and self._loop:
            try:
                self._loop.call_soon_threadsafe(
                    lambda: asyncio.ensure_future(
                        self._async_send(data), loop=self._loop
                    )
                )
            except Exception as e:
                logger.error(f"Telnet send error: {e}")

    async def _async_send(self, data: str) -> None:
        if self._writer:
            self._writer.write(data.encode("utf-8"))

    def disconnect(self) -> None:
        """Close the Telnet connection."""
        self._connected = False
        if self._loop:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass
            self._loop = None
        logger.info("Telnet disconnected")

    def is_connected(self) -> bool:
        return self._connected
