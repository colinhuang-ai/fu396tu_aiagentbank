"""
tools/organize/kinds.py - Phan loai file theo duoi.

Dung cho placeholder {kind} khi doi ten va khi sap xep vao thu muc.
"""

from __future__ import annotations

from pathlib import Path

# Thu tu khai bao khong quan trong - moi duoi chi thuoc dung mot nhom.
KIND_SUFFIXES: dict[str, tuple[str, ...]] = {
    "tai-lieu": (".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".pages", ".tex"),
    "bang-tinh": (".xls", ".xlsx", ".xlsm", ".csv", ".tsv", ".ods", ".numbers"),
    "trinh-chieu": (".ppt", ".pptx", ".odp", ".key"),
    "hinh-anh": (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".heic",
                 ".tif", ".tiff", ".ico"),
    "video": (".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".flv", ".m4v"),
    "am-thanh": (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"),
    "bien-ban": (".vtt", ".srt", ".sbv", ".ass"),
    "thu": (".eml", ".msg", ".mbox"),
    "nen": (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz"),
    "ma-nguon": (".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".h", ".cpp", ".cs",
                 ".go", ".rs", ".rb", ".php", ".sql", ".sh", ".ps1", ".html", ".css",
                 ".json", ".yaml", ".yml", ".xml", ".toml", ".ini"),
    "phong-chu": (".ttf", ".otf", ".woff", ".woff2"),
}

KIND_OTHER = "khac"

_BY_SUFFIX: dict[str, str] = {
    suffix: kind for kind, suffixes in KIND_SUFFIXES.items() for suffix in suffixes
}


def kind_of(path: str | Path) -> str:
    """Nhom cua mot file theo duoi. Khong nhan ra thi tra ve 'khac'."""
    return _BY_SUFFIX.get(Path(path).suffix.lower(), KIND_OTHER)


def all_kinds() -> list[str]:
    return [*KIND_SUFFIXES, KIND_OTHER]


def describe() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {"kind": kind, "suffixes": list(suffixes)} for kind, suffixes in KIND_SUFFIXES.items()
    ]
    rows.append({"kind": KIND_OTHER, "suffixes": []})
    return rows
