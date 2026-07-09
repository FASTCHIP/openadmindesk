# Development Environment

These commands are the default path for agents working on the server.

## Server Path

```bash
cd /ai/openadmindesk
```

## Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

If network access is unavailable, record the failure in `docs/WORKLOG.md` and
continue with documentation or standard-library-only tasks.

## Run Checks

```bash
source .venv/bin/activate
pytest
ruff check .
```

Before the virtual environment exists, this smoke check should work:

```bash
PYTHONPATH=src python3 -m openadmindesk.app
```

## Ubuntu System Dependencies

Initial expected packages:

```bash
sudo apt install python3 python3-venv openssh-client
```

Later UI and terminal work may need Qt, VTE, X11, and packaging dependencies.

## Fedora/RHEL-Family System Dependencies

Initial expected packages:

```bash
sudo dnf install python3 python3-pip openssh-clients
```

Package names for VTE, Qt, and AppImage tooling must be verified when packaging
work begins.

