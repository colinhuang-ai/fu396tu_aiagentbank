"""
tools/organize/dates.py - Lay ngay cua mot tai lieu.

Ba nguon, chon bang --date-from:
    mtime  lan sua cuoi (mac dinh - luon co)
    name   ngay doc duoc tu chinh ten file
    meta   ngay tao ghi trong metadata cua tai lieu (.docx .pdf .xlsx)

`name` va `meta` tu quay ve mtime khi khong tim thay gi.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

DATE_SOURCES = ("mtime", "name", "meta")

# Cac dang ngay hay gap trong ten file, thu tu tu ro rang nhat tro xuong
_NAME_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?<!\d)(20\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])(?!\d)"), "ymd"),
    (re.compile(r"(?<!\d)(0[1-9]|[12]\d|3[01])[-_.](0[1-9]|1[0-2])[-_.](20\d{2})(?!\d)"), "dmy"),
    (re.compile(r"(?<!\d)(20\d{2})[-_.](0[1-9]|1[0-2])(?!\d)"), "ym"),
)


def from_mtime(path: Path) -> date:
    return datetime.fromtimestamp(path.stat().st_mtime).date()


def from_name(path: Path) -> date | None:
    """Doc ngay tu ten file. Tra ve None neu khong thay."""
    for pattern, order in _NAME_PATTERNS:
        m = pattern.search(path.stem)
        if not m:
            continue
        try:
            if order == "ymd":
                return date(int(m[1]), int(m[2]), int(m[3]))
            if order == "dmy":
                return date(int(m[3]), int(m[2]), int(m[1]))
            return date(int(m[1]), int(m[2]), 1)
        except ValueError:
            continue           # vd 2026-02-30 -> thu mau tiep theo
    return None


def from_meta(path: Path) -> date | None:
    """Ngay tao ghi trong metadata tai lieu. Thieu thu vien -> tra ve None, khong bao loi."""
    suffix = path.suffix.lower()
    try:
        if suffix == ".docx":
            import docx

            created = docx.Document(path).core_properties.created
            return created.date() if created else None
        if suffix in (".xlsx", ".xlsm"):
            import openpyxl

            created = openpyxl.load_workbook(path, read_only=True).properties.created
            return created.date() if created else None
        if suffix == ".pdf":
            from pypdf import PdfReader

            created = PdfReader(path).metadata
            created = created.creation_date if created else None
            return created.date() if created else None
    except Exception:
        return None            # file hong / thieu thu vien -> de nguoi goi quay ve mtime
    return None


def resolve(path: Path, source: str = "mtime") -> date:
    """Ngay cua file theo nguon da chon, tu quay ve mtime khi khong tim thay."""
    if source not in DATE_SOURCES:
        raise ValueError(f"nguon ngay khong hop le: {source!r} (chon: {', '.join(DATE_SOURCES)})")
    if source == "name":
        return from_name(path) or from_mtime(path)
    if source == "meta":
        return from_meta(path) or from_mtime(path)
    return from_mtime(path)
