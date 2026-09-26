#!/usr/bin/env python3
"""
Wrapper cua skill `anonymize`.

Tim package tools/anonymize roi chuyen tiep toan bo tham so cho CLI cua no.
Nho vay skill goi duoc tu bat ky thu muc lam viec nao ma khong can cai dat gi.

    python .agents/skills/anonymize/scripts/anonymize.py encrypt -i data.csv

Thu tu tim kiem:
  1. Bien moi truong ANONYMIZE_TOOLS_DIR (thu muc CHUA `tools/`)
  2. Di nguoc len tu vi tri file nay
  3. Di nguoc len tu thu muc lam viec hien tai
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PACKAGE_PATH = ("tools", "anonymize", "cli.py")


def _candidates() -> list[Path]:
    roots: list[Path] = []
    override = os.environ.get("ANONYMIZE_TOOLS_DIR")
    if override:
        roots.append(Path(override).expanduser().resolve())
    here = Path(__file__).resolve()
    roots.extend(here.parents)
    roots.extend(Path.cwd().resolve().parents)
    roots.append(Path.cwd().resolve())
    return roots


def find_project_root() -> Path:
    seen: set[Path] = set()
    for root in _candidates():
        if root in seen:
            continue
        seen.add(root)
        if root.joinpath(*PACKAGE_PATH).is_file():
            return root
    raise SystemExit(
        "Loi: khong tim thay package tools/anonymize.\n"
        "  -> Chay lenh tu trong thu muc du an, hoac dat bien moi truong:\n"
        "     ANONYMIZE_TOOLS_DIR=/duong/dan/den/thu-muc-chua-tools"
    )


def main() -> int:
    root = find_project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from tools.anonymize.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
