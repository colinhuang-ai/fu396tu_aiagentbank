"""
tools.organize - Doi ten hang loat va sap xep tai lieu vao thu muc.

Kien truc:

    kinds.py     phan loai file theo duoi  ({kind})
    naming.py    slugify tieng Viet, lam sach ten, dung ten tu mau
    dates.py     lay ngay tu mtime / ten file / metadata tai lieu
    core.py      quet file, dung ke hoach, thuc thi an toan
    journal.py   nhat ky thao tac va hoan tac
    cli.py       dong lenh
    selftest.py  kiem thu nhanh

Chieu phu thuoc mot chieu:  cli -> core -> naming, dates, kinds

Dung nhu thu vien:

    from pathlib import Path
    from tools.organize import build_plan, collect, sort_files

    root = Path("docs")
    plan = build_plan(root, sort_files(collect(root)), "{kind}/{date}-{slug}{ext}")
    for action in plan.changes:
        print(action.src.name, "->", action.dst.relative_to(root))
"""

from __future__ import annotations

from .core import (
    CONFLICT_POLICIES,
    SORT_KEYS,
    Action,
    OrganizeError,
    Plan,
    build_plan,
    collect,
    describe_fields,
    execute,
    prune_empty_dirs,
    sort_files,
)
from .dates import DATE_SOURCES
from .journal import JOURNAL_NAME, Journal, read_sessions, undo_last
from .kinds import all_kinds, kind_of
from .naming import render, sanitize, slugify, strip_accents

__version__ = "1.0"

__all__ = [
    "CONFLICT_POLICIES",
    "DATE_SOURCES",
    "JOURNAL_NAME",
    "SORT_KEYS",
    "Action",
    "Journal",
    "OrganizeError",
    "Plan",
    "all_kinds",
    "build_plan",
    "collect",
    "describe_fields",
    "execute",
    "kind_of",
    "prune_empty_dirs",
    "read_sessions",
    "render",
    "sanitize",
    "slugify",
    "sort_files",
    "strip_accents",
    "undo_last",
]
