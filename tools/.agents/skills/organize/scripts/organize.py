#!/usr/bin/env python3
"""
Wrapper cua skill `organize`.

Tim package tools/organize roi chuyen tiep toan bo tham so cho CLI cua no.
Nho vay skill goi duoc tu bat ky thu muc lam viec nao ma khong can cai dat gi.

    python .agents/skills/organize/scripts/organize.py rename docs

Thu tu tim kiem:
  1. Bien moi truong ORGANIZE_TOOLS_DIR (thu muc CHUA `tools/`)
  2. Di nguoc len tu vi tri file nay
  3. Di nguoc len tu thu muc lam viec hien tai
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PACKAGE_PATH = ("tools", "organize", "cli.py")


def _candidates() -> list[Path]:
    roots: list[Path] = []
    override = os.environ.get("ORGANIZE_TOOLS_DIR")
    if override:
        roots.append(Path(override).expanduser().resolve())
    roots.extend(Path(__file__).resolve().parents)
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
        "Loi: khong tim thay package tools/organize.\n"
        "  -> Chay lenh tu trong thu muc du an, hoac dat bien moi truong:\n"
        "     ORGANIZE_TOOLS_DIR=/duong/dan/den/thu-muc-chua-tools"
    )


def main() -> int:
    root = find_project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from tools.organize.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
