#!/usr/bin/env python3
"""Dependency checker for OpenAdminDesk.

Usage:
    python3 tools/check_deps.py          # Full check
    python3 tools/check_deps.py --quiet  # Only show missing
    python3 tools/check_deps.py --json   # Machine-readable output
"""

from __future__ import annotations

import sys
import json
import shutil
import os
from typing import List, Dict


class Dependency:
    """Represents a single dependency."""

    def __init__(self, name: str, category: str, check_type: str,
                 check_value: str, doc_url: str = "",
                 optional: bool = False) -> None:
        self.name = name
        self.category = category
        self.check_type = check_type
        self.check_value = check_value
        self.doc_url = doc_url
        self.optional = optional

    def check(self) -> tuple[bool, str]:
        """Check if this dependency is satisfied.

        Returns:
            Tuple of (satisfied: bool, detail: str)
        """
        if self.check_type == "binary":
            return self._check_binary()
        elif self.check_type == "python_module":
            return self._check_python_module()
        elif self.check_type == "env_var":
            return self._check_env_var()
        elif self.check_type == "path":
            return self._check_path()
        elif self.check_type == "file":
            return self._check_file()
        return False, f"Unknown check type: {self.check_type}"

    def _check_binary(self) -> tuple[bool, str]:
        path = shutil.which(self.check_value)
        if path:
            return True, f"Found at {path}"
        return False, "Not found in PATH"

    def _check_python_module(self) -> tuple[bool, str]:
        try:
            mod = __import__(self.check_value)
            version = getattr(mod, "__version__", "unknown")
            return True, f"Found, version {version}"
        except ImportError:
            return False, "Not installed"

    def _check_env_var(self) -> tuple[bool, str]:
        val = os.environ.get(self.check_value)
        if val:
            return True, f"Set to '{val}'"
        return False, "Not set"

    def _check_path(self) -> tuple[bool, str]:
        if os.path.exists(self.check_value):
            return True, "Exists"
        return False, "Not found"

    def _check_file(self) -> tuple[bool, str]:
        if os.path.isfile(self.check_value):
            return True, f"Found at {self.check_value}"
        return False, "Not found"


# Define all dependencies
DEPENDENCIES: List[Dependency] = [
    # --- Python ---
    Dependency("Python 3.12+", "python", "binary", "python3",
              "https://python.org"),
    Dependency("pip", "python", "binary", "pip3"),

    # --- SSH ---
    Dependency("OpenSSH client", "ssh", "binary", "ssh",
              "https://www.openssh.com/"),
    Dependency("ssh-keygen", "ssh", "binary", "ssh-keygen"),
    Dependency("sshpass (optional)", "ssh", "binary", "sshpass",
              optional=True),

    # --- SFTP ---
    Dependency("SFTP client", "sftp", "binary", "sftp",
              "https://www.openssh.com/"),

    # --- X11 ---
    Dependency("X11 display", "x11", "env_var", "DISPLAY",
              optional=True),
    Dependency("xauth", "x11", "binary", "xauth",
              "https://www.x.org/", optional=True),
    Dependency("X11 socket", "x11", "path", "/tmp/.X11-unix",
              optional=True),

    # --- Python packages (from pyproject.toml) ---
    Dependency("PySide6", "python_pkg", "python_module", "PySide6",
              "https://pyside.org/"),
    Dependency("cryptography", "python_pkg", "python_module", "cryptography",
              "https://cryptography.io/"),
    Dependency("argon2-cffi", "python_pkg", "python_module", "argon2",
              "https://github.com/hynek/argon2-cffi"),
    Dependency("paramiko", "python_pkg", "python_module", "paramiko",
              "https://paramiko.org/"),

    # --- System libraries ---
    Dependency("libGL", "system", "binary", "ldconfig",
              optional=True),
]


def check_all(quiet: bool = False, as_json: bool = False) -> List[Dict]:
    """Check all dependencies.

    Args:
        quiet: If True, only print missing dependencies.
        as_json: If True, suppress all text output.

    Returns:
        List of result dicts.
    """
    results = []
    last_category = ""

    for dep in DEPENDENCIES:
        if dep.category != last_category and not quiet and not as_json:
            if last_category:
                print()
            print(f"── {dep.category.upper()} ──")
            last_category = dep.category

        satisfied, detail = dep.check()
        results.append({
            "name": dep.name,
            "category": dep.category,
            "satisfied": satisfied,
            "detail": detail,
            "optional": dep.optional,
            "doc_url": dep.doc_url,
        })

        if not as_json:
            if quiet:
                if not satisfied and not dep.optional:
                    print(f"  MISSING: {dep.name} — {detail}")
            else:
                status = "✓" if satisfied else ("?" if dep.optional else "✗")
                print(f"  {status} {dep.name}: {detail}")

    return results


def main() -> int:
    """Run the dependency checker."""
    quiet = "--quiet" in sys.argv
    as_json = "--json" in sys.argv

    results = check_all(quiet, as_json)

    if as_json:
        print(json.dumps(results, indent=2))
        return 0

    # Summary
    required_missing = [
        r for r in results if not r["satisfied"] and not r["optional"]
    ]
    optional_missing = [
        r for r in results if not r["satisfied"] and r["optional"]
    ]

    print()
    print("── SUMMARY ──")
    print(f"  Total checks:     {len(results)}")
    print(f"  Passed:           {len(results) - len(required_missing) - len(optional_missing)}")
    print(f"  Missing required: {len(required_missing)}")
    print(f"  Missing optional: {len(optional_missing)}")

    if required_missing:
        print()
        print("Install missing required dependencies:")
        for r in required_missing:
            print(f"  • {r['name']} — {r['detail']}")
            if r["doc_url"]:
                print(f"    See: {r['doc_url']}")

    if optional_missing:
        print()
        print("Optional dependencies not found:")
        for r in optional_missing:
            print(f"  • {r['name']} — {r['detail']}")

    return 1 if required_missing else 0


if __name__ == "__main__":
    sys.exit(main())
