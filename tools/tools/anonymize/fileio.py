"""
tools/fileio.py - Dieu phoi file: chon handler, dat ten file dau ra, xuat bang doi chieu.

Diem vao chung cho ca CLI lan web UI la process_bytes().
Viec doc/ghi tung dinh dang do package handlers dam nhiem.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from .core import AnonymizeError, Cipher
from .handlers import KIND_AUTO, get_handler, transform_text

MODES = ("encrypt", "decrypt")

__all__ = [
    "KIND_AUTO",
    "MODES",
    "default_output",
    "get_handler",
    "mapping_csv",
    "process_bytes",
    "process_file",
    "transform_text",
    "write_mapping",
]


# --------------------------------------------------------------------------
# Xu ly
# --------------------------------------------------------------------------

def process_bytes(
    raw: bytes,
    filename: str,
    cipher: Cipher,
    mode: str,
    strict: bool = False,
    kind: str = KIND_AUTO,
) -> bytes:
    """Xu ly noi dung mot file trong bo nho. Dung chung cho CLI va web UI."""
    if mode not in MODES:
        raise AnonymizeError(f"mode khong hop le: {mode!r} (phai la encrypt hoac decrypt)")
    return get_handler(filename, raw, kind).process(raw, cipher, mode, strict)


def process_file(
    src: Path,
    dst: Path,
    cipher: Cipher,
    mode: str,
    strict: bool = False,
    kind: str = KIND_AUTO,
) -> None:
    out = process_bytes(src.read_bytes(), src.name, cipher, mode, strict, kind)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(out)


# --------------------------------------------------------------------------
# Ten file dau ra
# --------------------------------------------------------------------------

def default_output(src: Path, mode: str, kind: str = KIND_AUTO, raw: bytes | None = None) -> Path:
    """
    data.csv -> data.enc.csv (encrypt);  data.enc.csv -> data.csv (decrypt).

    Handler nao ep duoi file rieng (PDF -> .txt) thi theo handler do.
    """
    suffix = get_handler(src.name, raw, kind).output_suffix or src.suffix
    stem = src.stem
    if mode == "encrypt":
        return src.with_name(f"{stem}.enc{suffix}")
    stem = stem[:-4] if stem.endswith(".enc") else f"{stem}.dec"
    return src.with_name(f"{stem}{suffix}")


# --------------------------------------------------------------------------
# Bang doi chieu
# --------------------------------------------------------------------------

def mapping_csv(cipher: Cipher, bom: bool = False) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(["original", "token"])
    for original, token in sorted(cipher.mapping.items()):
        writer.writerow([original, token])
    return ("﻿" if bom else "") + buf.getvalue()


def write_mapping(path: Path, cipher: Cipher) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(mapping_csv(cipher, bom=True), encoding="utf-8", newline="")
