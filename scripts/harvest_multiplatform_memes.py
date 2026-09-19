"""Compatibility entrypoint for the fail-closed live harvester.

The previous version mixed live responses with local fixtures and estimated
engagement. Keep this filename for existing deployment commands, but route it
to the source-of-truth implementation.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from harvest_live_sources import main


if __name__ == "__main__":
    main()
