"""
tools/handlers - Moi loai file mot handler rieng.

    text        CSV / TSV / TXT / JSON ...      plain.py
    xlsx        Excel .xlsx .xlsm               xlsx.py
    docx        Word .docx                      docx.py
    pdf         PDF van ban (xuat ra .txt)      pdf.py
    transcript  Bien ban / phu de cuoc hop      transcript.py
    email       Thu .eml                        eml.py

Chon handler bang duoi file; rieng transcript con doan them theo noi dung vi
bien ban cuoc hop thuong duoc luu duoi dang .txt. Co the ep tay bang --kind.
"""

from __future__ import annotations

from pathlib import Path

from ..core import AnonymizeError
from .base import Handler, TextHandler, transform_text
from .docx import DocxHandler
from .eml import EmailHandler
from .pdf import PdfHandler
from .plain import PlainHandler
from .transcript import TranscriptHandler, is_transcript
from .xlsx import XlsxHandler

PLAIN = PlainHandler()
TRANSCRIPT = TranscriptHandler()

HANDLERS: tuple[Handler, ...] = (
    PLAIN,
    XlsxHandler(),
    DocxHandler(),
    PdfHandler(),
    TRANSCRIPT,
    EmailHandler(),
)

BY_NAME: dict[str, Handler] = {h.name: h for h in HANDLERS}
BY_SUFFIX: dict[str, Handler] = {s: h for h in HANDLERS for s in h.suffixes}

KIND_AUTO = "auto"
KIND_CHOICES = (KIND_AUTO, *BY_NAME)


def get_handler(filename: str | Path, raw: bytes | None = None, kind: str = KIND_AUTO) -> Handler:
    """
    Chon handler cho mot file.

    kind != "auto" -> ep dung dung handler do.
    Nguoc lai: uu tien duoi file, sau do doan noi dung de bat transcript .txt.
    """
    if kind and kind != KIND_AUTO:
        try:
            return BY_NAME[kind]
        except KeyError:
            raise AnonymizeError(
                f"Khong co handler ten {kind!r}. Chon mot trong: {', '.join(KIND_CHOICES)}"
            ) from None

    handler = BY_SUFFIX.get(Path(filename).suffix.lower(), PLAIN)
    if handler is PLAIN and raw is not None and _sniff_transcript(raw):
        return TRANSCRIPT
    return handler


def _sniff_transcript(raw: bytes) -> bool:
    try:
        return is_transcript(raw[:16384].decode("utf-8-sig", errors="ignore"))
    except Exception:
        return False


def describe() -> list[dict[str, object]]:
    """Mo ta cac handler - dung cho CLI --list-kinds va giao dien web."""
    return [
        {
            "name": h.name,
            "label": h.label,
            "suffixes": list(h.suffixes),
            "output_suffix": h.output_suffix,
        }
        for h in HANDLERS
    ]


__all__ = [
    "BY_NAME",
    "BY_SUFFIX",
    "HANDLERS",
    "KIND_AUTO",
    "KIND_CHOICES",
    "DocxHandler",
    "EmailHandler",
    "Handler",
    "PdfHandler",
    "PlainHandler",
    "TextHandler",
    "TranscriptHandler",
    "XlsxHandler",
    "describe",
    "get_handler",
    "is_transcript",
    "transform_text",
]
