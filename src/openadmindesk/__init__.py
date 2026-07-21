"""OpenAdminDesk package."""

import importlib.metadata
from pathlib import Path
import tomllib
import warnings

def _get_version() -> str:
    """Resolve package version from metadata or pyproject.toml."""
    try:
        return importlib.metadata.version("openadmindesk")
    except importlib.metadata.PackageNotFoundError:
        try:
            pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
            return data["project"]["version"]
        except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError) as e:
            warnings.warn(f"Could not resolve version from {pyproject_path}: {e}", RuntimeWarning, stacklevel=2)
            return "0+unknown"

__version__ = _get_version()

