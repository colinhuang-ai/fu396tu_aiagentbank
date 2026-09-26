"""
tools/handlers/base.py - Giao uoc chung cho moi handler theo loai file.

Mot handler biet cach LAY RA van ban tu mot dinh dang va DAT LAI van ban da xu ly
vao dung cho cu. Viec ma hoa / giai ma van do encrypt.py va decrypt.py dam nhiem.
"""

from __future__ import annotations

from ..core import BOM_UTF8, AnonymizeError, Cipher
from ..decrypt import decrypt_text
from ..encrypt import encrypt_text

MODES = ("encrypt", "decrypt")


def transform_text(text: str, cipher: Cipher, mode: str, strict: bool = False) -> str:
    """Cong tac chuyen giua hai chieu xu ly."""
    if mode == "encrypt":
        return encrypt_text(text, cipher)
    if mode == "decrypt":
        return decrypt_text(text, cipher, strict)
    raise AnonymizeError(f"mode khong hop le: {mode!r} (phai la encrypt hoac decrypt)")


class Handler:
    """Lop co so. Moi dinh dang ke thua va cai dat process()."""

    name = "base"                     # dinh danh dung cho --kind
    label = "Khong ro"                # ten hien thi
    suffixes: tuple[str, ...] = ()    # duoi file nhan dien tu dong
    output_suffix: str | None = None  # ep duoi file dau ra (None = giu nguyen)
    binary = False                    # True = khong xem truoc duoc dang van ban

    def process(self, raw: bytes, cipher: Cipher, mode: str, strict: bool = False) -> bytes:
        raise NotImplementedError

    def preview(self, raw: bytes) -> str | None:
        """Doan van ban dau file de hien thi tren giao dien web."""
        if self.binary:
            return None
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name}>"


class TextHandler(Handler):
    """Handler cho cac dinh dang van ban thuan. Giu nguyen BOM va kieu xuong dong."""

    name = "text"
    label = "Van ban thuan"

    def decode(self, raw: bytes) -> tuple[str, bool]:
        return raw.decode("utf-8-sig"), raw.startswith(BOM_UTF8)

    def encode(self, text: str, has_bom: bool) -> bytes:
        data = text.encode("utf-8")
        return BOM_UTF8 + data if has_bom else data

    def transform(self, text: str, cipher: Cipher, mode: str, strict: bool) -> str:
        """Diem mo rong cho cac dinh dang van ban co cau truc rieng (vd: transcript)."""
        return transform_text(text, cipher, mode, strict)

    def process(self, raw: bytes, cipher: Cipher, mode: str, strict: bool = False) -> bytes:
        text, has_bom = self.decode(raw)
        return self.encode(self.transform(text, cipher, mode, strict), has_bom)
