# Compatibility Notes

## Ubuntu

Primary initial target:

- Ubuntu 24.04 LTS desktop.

Expected system dependencies:

- Python 3.11 or newer.
- OpenSSH client.
- Qt runtime through PySide6 packages or bundled wheels.
- Optional: VTE libraries for native terminal embedding.

## Red Hat Family

Secondary initial targets:

- Fedora Workstation current release.
- Rocky Linux 9 or AlmaLinux 9.

Expected system dependencies:

- Python 3.11 or newer where available.
- OpenSSH client.
- Qt runtime through PySide6 packages or bundled wheels.
- Optional: VTE libraries for native terminal embedding.

## Packaging Goals

- `.deb` package for Ubuntu.
- `.rpm` package for Fedora/Rocky/AlmaLinux.
- AppImage can be evaluated later if native packages become too slow.

## Known Risk

Terminal embedding is the highest portability risk. The MVP should isolate this
behind a small interface so the project can switch between VTE, external
terminal process embedding, or a fallback terminal implementation.

