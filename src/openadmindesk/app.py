"""Application entrypoint."""

from __future__ import annotations

import argparse
import importlib.metadata
import sys

from PySide6.QtWidgets import QApplication
from openadmindesk.ui.main_window import create_main_window
from openadmindesk.ui.theme import apply_theme
from openadmindesk.platform.platform_utils import enable_portable_mode, is_portable


def _version() -> str:
    """Return installed package version, falling back during source runs."""
    try:
        return importlib.metadata.version("openadmindesk")
    except importlib.metadata.PackageNotFoundError:
        return "0.1.0"


def main() -> int:
    """Run the desktop application.

    Supports --portable flag: create portable mode marker and use app dir for data.
    """
    parser = argparse.ArgumentParser(prog="openadmindesk")
    parser.add_argument("--portable", action="store_true")
    parser.add_argument("--version", action="store_true")
    args, remaining = parser.parse_known_args(sys.argv[1:])

    if args.version:
        print(f"OpenAdminDesk {_version()}")
        return 0

    sys.argv[:] = [sys.argv[0], *remaining]
    if args.portable:
        enable_portable_mode()

    app = QApplication(sys.argv)
    apply_theme(app)
    window = create_main_window()
    if is_portable():
        window.setWindowTitle("OpenAdminDesk [PORTABLE]")
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

