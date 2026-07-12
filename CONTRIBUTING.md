# Contributing to OpenAdminDesk

## Welcome

Thank you for your interest in OpenAdminDesk! This is an open source remote
administration workbench for Linux desktops, and every contribution helps.

## How to Contribute

### Reporting Bugs

1. Check the existing issues to avoid duplicates.
2. Include:
   - Your Linux distribution and version
   - Python version (`python3 --version`)
   - PySide6 version
   - Steps to reproduce
   - Expected vs actual behavior
   - Relevant logs or error output

### Suggesting Features

1. First check `docs/ROADMAP.md` and `docs/PRODUCT_REQUIREMENTS.md` to see if
   it's already planned.
2. Open an issue describing the feature, its motivation, and a rough sketch of
   the implementation.

### Code Contributions

#### Small Model Notice

This project is designed to be implemented by small LLM agents with limited
planning ability. To make this work, we enforce strict rules:

- **One task = one small change.** Never combine UI, storage, and protocol work
  in one commit.
- **Read AGENTS.md first.** It contains the mandatory operating rules.
- **Update docs/WORKLOG.md** with every task.
- **Run verification** after every change.

#### Getting Started

```bash
# Clone the repository
git clone https://github.com/FASTCHIP/openadmindesk.git
cd openadmindesk

# Set up a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Verify the app launches
PYTHONPATH=src python3 -m openadmindesk.app
```

#### Code Style

- Python 3.12+ with type annotations
- Line length: 88 characters (matching Ruff defaults)
- Format with `ruff format` before committing
- Import order: standard library, third-party, local

#### Architecture Rules

| Rule | Detail |
|------|--------|
| UI ↔ Core | UI (`ui/`) imports Core (`core/`); Core never imports Qt |
| Commands | Always build as argument lists, never `shell=True` |
| Secrets | Never log, never pass through argv, never commit |
| Async | Blocking operations use `run_in_executor` with ThreadPoolExecutor |
| Caching | TTL-based caches (default 5 min) for repeated operations |

#### Testing

```bash
# Run core tests (no Qt required)
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py"

# Run specific test
PYTHONPATH=src python3 -m unittest tests.test_profile_store

# Install test dependencies
pip install ".[dev]"
```

#### Commit Messages

- Use the imperative mood ("Add feature" not "Added feature")
- Keep the first line under 72 characters
- Reference issues when relevant

```
Short description under 72 characters

More detailed explanation if needed. Wrap at 72 characters.
Refs #123
```

### Pull Request Process

1. Create a branch from `main` with a descriptive name:
   - `feature/short-description`
   - `fix/short-description`
   - `docs/short-description`
2. Make small, focused commits.
3. Update `docs/WORKLOG.md` with your changes.
4. Run existing tests and add new ones for new functionality.
5. Create the PR with a clear description of what changed and why.

### Code of Conduct

This project follows a simple principle: be respectful and constructive.
Harassment, trolling, and personal attacks are not welcome.

## License

By contributing, you agree that your contributions will be licensed under the
GNU General Public License v3.0 or later.
