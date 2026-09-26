"""
tools/handlers/plain.py - CSV / TSV / TXT va moi file van ban khac.

Xu ly theo noi dung nen khong pha cau truc cot: mot o chua nhieu email
("a@x | b@x") van duoc thay tung cai mot, dau phay va dau nhay giu nguyen.
Giu nguyen BOM va CRLF de file mo bang Excel khong bi doi dinh dang.
"""

from __future__ import annotations

from .base import TextHandler


class PlainHandler(TextHandler):
    name = "text"
    label = "CSV / TSV / TXT"
    suffixes = (
        ".csv", ".tsv", ".txt", ".json", ".jsonl", ".ndjson",
        ".xml", ".yaml", ".yml", ".sql", ".log", ".md", ".ini", ".env",
    )
