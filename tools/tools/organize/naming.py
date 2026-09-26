"""
tools/organize/naming.py - Chuan hoa ten va dung ten moi tu mau (template).

slugify() xu ly tieng Viet co dau: "Biên bản họp Quý 3" -> "bien-ban-hop-quy-3".
"""

from __future__ import annotations

import re
import string
import unicodedata
from pathlib import Path

# Ky tu Windows khong cho phep trong ten file, cong cac ky tu dieu khien
ILLEGAL_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Ten bi Windows giu cho
RESERVED_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})

MAX_STEM = 120   # chua ke duoi file, de duong dan tong khong cham gioi han he thong


def strip_accents(text: str) -> str:
    """Bo dau tieng Viet. Rieng d/D co gach phai xu ly tay vi khong tach duoc bang NFD."""
    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def slugify(text: str, separator: str = "-", keep_case: bool = False) -> str:
    """Chuoi an toan cho ten file: chi con chu cai ASCII, chu so va dau phan cach."""
    text = strip_accents(text)
    if not keep_case:
        text = text.lower()
    text = re.sub(r"[^A-Za-z0-9]+", separator, text)
    return text.strip(separator + " .")


def sanitize(name: str) -> str:
    """Giu nguyen ten nguoi dung nhung loai bo ky tu he thong khong chap nhan."""
    # Cat dau cham o CA HAI dau: dau cham dau ten tao ra file an tren Unix,
    # cuoi ten thi bi Windows tu bo di.
    cleaned = ILLEGAL_RE.sub("", name).strip().strip(". ")
    if not cleaned:
        return "khong-ten"
    if cleaned.upper().split(".")[0] in RESERVED_NAMES:
        cleaned = "_" + cleaned
    return cleaned[:MAX_STEM]


class _Fields(dict):
    """dict cho format_map - bao loi ro rang khi mau dung bien khong ton tai."""

    def __missing__(self, key: str):
        raise KeyError(key)


def placeholders(template: str) -> set[str]:
    """Cac bien duoc dung trong mau, vd '{date}_{slug}{ext}' -> {'date','slug','ext'}."""
    return {
        field for _, field, _, _ in string.Formatter().parse(template)
        if field
    }


def render(template: str, fields: dict[str, object]) -> str:
    """
    Dung chuoi tu mau. Tra ve duong dan TUONG DOI - mau co the chua '/' de tao thu muc.

    Moi doan duong dan duoc lam sach rieng, nen bien chua '/' khong the pha ra ngoai.
    """
    safe = {
        key: (sanitize(str(value)).replace("/", "-") if isinstance(value, str) else value)
        for key, value in fields.items()
    }
    # {ext} da co dau cham o dau, sanitize() se cat mat -> tra lai nguyen ban
    if "ext" in fields:
        safe["ext"] = ILLEGAL_RE.sub("", str(fields["ext"]))

    try:
        rendered = template.format_map(_Fields(safe))
    except KeyError as exc:
        known = ", ".join(sorted(fields))
        raise ValueError(f"mau dung bien khong ton tai: {exc}. Bien co san: {known}") from exc

    parts = [sanitize(p) for p in rendered.replace("\\", "/").split("/") if p not in ("", ".", "..")]
    if not parts:
        raise ValueError(f"mau {template!r} cho ra ten rong")
    return "/".join(parts)


def with_counter(path: Path, taken: set[Path], separator: str = "-") -> Path:
    """Them hau to so khi ten da bi chiem: bao-cao.pdf -> bao-cao-2.pdf."""
    if path not in taken and not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for index in range(2, 10_000):
        candidate = path.with_name(f"{stem}{separator}{index}{suffix}")
        if candidate not in taken and not candidate.exists():
            return candidate
    raise ValueError(f"khong tim duoc ten trong cho {path}")
