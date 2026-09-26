#!/usr/bin/env python3
"""
Loi tat cho cong cu tools/anonymize.

    python anonymize.py <lenh>     ==     python -m tools.anonymize <lenh>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tools.anonymize.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
