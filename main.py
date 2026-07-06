"""Top-level entry point for launching the application.

This wrapper allows running the project with:

    python main.py
"""

from __future__ import annotations

from pathlib import Path
import sys


# Ensure imports resolve to this checkout even when the script is launched from
# another working directory or an external tool.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import main


if __name__ == "__main__":
    main()
