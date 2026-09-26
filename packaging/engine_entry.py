"""PyInstaller entry point for the self-contained JanesCriber CLI / service engine."""

from __future__ import annotations

import sys
from janescriber.__main__ import main


if __name__ == "__main__":
    sys.exit(main())
