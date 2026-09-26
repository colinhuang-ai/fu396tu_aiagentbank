#!/usr/bin/env python3
"""
Loi tat cho cong cu tools/organize.

    python organize.py <lenh>     ==     python -m tools.organize <lenh>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tools.organize.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
