"""
tools/handlers/xlsx.py - Bang tinh Excel (.xlsx / .xlsm).

Quet moi sheet, chi dung toi cac o kieu chuoi - o so, ngay thang, cong thuc
va dinh dang bang deu giu nguyen.
"""

from __future__ import annotations

import io

from ..core import AnonymizeError, Cipher
from .base import Handler, transform_text


class XlsxHandler(Handler):
    name = "xlsx"
    label = "Excel (.xlsx/.xlsm)"
    suffixes = (".xlsx", ".xlsm")
    binary = True

    def process(self, raw: bytes, cipher: Cipher, mode: str, strict: bool = False) -> bytes:
        try:
            import openpyxl
        except ImportError as exc:
            raise AnonymizeError("Can cai openpyxl de xu ly .xlsx:  pip install openpyxl") from exc

        wb = openpyxl.load_workbook(io.BytesIO(raw))
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if isinstance(cell.value, str):
                        cell.value = transform_text(cell.value, cipher, mode, strict)
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
