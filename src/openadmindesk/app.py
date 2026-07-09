"""Application entrypoint."""

from __future__ import annotations


def main() -> int:
    """Run the desktop application.

    The real PySide6 main window will be added in the application skeleton
    phase. Keeping this entrypoint import-light lets tests run before GUI
    dependencies are installed.
    """
    print("OpenAdminDesk application skeleton")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

