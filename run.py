#!/usr/bin/env python3
"""Developer run script."""

import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

if __name__ == "__main__":
    from openadmindesk.app import main
    raise SystemExit(main())