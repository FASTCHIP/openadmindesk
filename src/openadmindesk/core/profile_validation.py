"""Profile validation utilities."""

from __future__ import annotations

import re
import shlex
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from openadmindesk.core.profile import Profile

_DANGEROUS_CHARS_RE = re.compile(r'[;&|`$(){}<>]')
_ALLOWED_PROXY_BINARIES = {"ssh", "nc", "ncat", "socat", "connect-proxy"}


def validate_profile(profile: "Profile") -> tuple[bool, Optional[str]]:
    """Validate a profile and return (is_valid, error_message)."""
    if not profile.name:
        return False, "Profile name is required"

    if not profile.host:
        return False, "Host is required"

    if not _is_valid_host(profile.host):
        return False, f"Invalid host format: {profile.host}"

    if profile.username and not is_safe_ssh_token(profile.username):
        return False, "Username contains unsupported characters"

    if not (1 <= profile.port <= 65535):
        return False, f"Invalid port: {profile.port}. Must be between 1 and 65535"

    if profile.proxy_command:
        is_valid_proxy, proxy_error = validate_proxy_command(profile.proxy_command)
        if not is_valid_proxy:
            return False, proxy_error

    return True, None


def is_safe_ssh_token(value: str) -> bool:
    """Return True when a string is safe to pass as one SSH argument."""
    if not value:
        return False
    if any(ord(char) < 32 for char in value):
        return False
    if _DANGEROUS_CHARS_RE.search(value):
        return False
    return True


def validate_proxy_command(command: str) -> tuple[bool, Optional[str]]:
    """Validate the supported ProxyCommand subset.

    Supported commands are intentionally narrow and must be expressible as a
    simple argument vector without shell operators: ssh, nc, ncat, socat, and
    connect-proxy. OpenSSH placeholders such as %h, %p, and %r are allowed.
    """
    if not command.strip():
        return False, "Proxy command is empty"
    if any(ord(char) < 32 for char in command):
        return False, "Proxy command contains control characters"
    if _DANGEROUS_CHARS_RE.search(command):
        return False, "Proxy command contains shell metacharacters"

    try:
        parts = shlex.split(command)
    except ValueError as exc:
        return False, f"Invalid proxy command quoting: {exc}"

    if not parts:
        return False, "Proxy command is empty"

    binary = parts[0].rsplit("/", 1)[-1]
    if binary not in _ALLOWED_PROXY_BINARIES:
        return False, f"Unsupported proxy command binary: {parts[0]}"

    return True, None


def _is_valid_host(host: str) -> bool:
    """Validate host address format."""
    if not is_safe_ssh_token(host):
        return False

    # IPv4 address
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', host):
        # Validate each octet
        octets = host.split('.')
        for octet in octets:
            if int(octet) > 255:
                return False
        return True

    # IPv6 address
    if re.match(r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$', host):
        return True

    # Hostname
    if re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$', host):
        return True

    return False
