"""
tools/handlers/pdf.py - PDF dang van ban.

PDF khong sua duoc tai cho ma khong pha bo cuc (chu duoc dat theo toa do tuyet doi),
nen handler nay TRICH van ban ra roi ma hoa, xuat ket qua thanh file .txt.
Do la lua chon co y: giu duoc kha nang giai ma chinh xac, doi lai mat bo cuc trang.

Chieu nguoc lai giai ma tu chinh file .txt do (PlainHandler lo).
PDF anh scan khong co lop van ban -> bao loi ro rang, can OCR truoc.
"""

from __future__ import annotations

import io

from ..core import AnonymizeError, Cipher
from .base import Handler, transform_text

PAGE_SEPARATOR = "\n\n===== Trang {n} =====\n\n"


class PdfHandler(Handler):
    name = "pdf"
    label = "PDF van ban (xuat ra .txt)"
    suffixes = (".pdf",)
    output_suffix = ".txt"
    binary = True

    def process(self, raw: bytes, cipher: Cipher, mode: str, strict: bool = False) -> bytes:
        if mode != "encrypt":
            raise AnonymizeError(
                "Khong giai ma nguoc vao file PDF duoc.\n"
                "  -> Ma hoa PDF sinh ra file .txt; hay giai ma chinh file .txt do."
            )
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise AnonymizeError("Can cai pypdf de xu ly PDF:  pip install pypdf") from exc

        try:
            reader = PdfReader(io.BytesIO(raw))
        except Exception as exc:
            raise AnonymizeError(f"Khong doc duoc PDF: {exc}") from exc
        if reader.is_encrypted:
            raise AnonymizeError("PDF dang duoc bao ve bang mat khau - hay go mat khau truoc.")

        chunks: list[str] = []
        for index, page in enumerate(reader.pages, start=1):
            chunks.append(PAGE_SEPARATOR.format(n=index))
            chunks.append(page.extract_text() or "")
        text = "".join(chunks).lstrip("\n")

        if not text.strip():
            raise AnonymizeError(
                "PDF khong co lop van ban nao (co the la ban scan) - can chay OCR truoc."
            )
        return transform_text(text, cipher, mode, strict).encode("utf-8")
