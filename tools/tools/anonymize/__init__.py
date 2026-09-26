"""
tools - Bo cong cu ma hoa / giai ma thong tin nhay cam.

Kien truc:

    core.py        khoa (.env), nguyen thuy AES-SIV, lop Cipher
    encrypt.py     nhan dien + ma hoa email / so dien thoai / ten nguoi
    decrypt.py     tim token + khoi phuc gia tri goc
    fileio.py      dieu phoi file, dat ten dau ra, bang doi chieu
    handlers/      moi loai file mot module (text, xlsx, docx, pdf, transcript, email)
    cli.py         dong lenh
    server.py      giao dien web keo tha
    selftest.py    kiem thu nhanh

Dung nhu thu vien:

    from tools import Cipher, resolve_key, process_bytes

    cipher = Cipher(resolve_key(".env"))
    out = process_bytes(raw, "data.csv", cipher, "encrypt")
"""

from __future__ import annotations

from .core import (
    ENV_FILE_DEFAULT,
    AnonymizeError,
    Cipher,
    generate_env,
    resolve_key,
)
from .decrypt import decrypt_text, decrypt_token
from .encrypt import encrypt_email, encrypt_name, encrypt_phone, encrypt_text
from .fileio import (
    default_output,
    mapping_csv,
    process_bytes,
    process_file,
    transform_text,
    write_mapping,
)
from .handlers import KIND_AUTO, KIND_CHOICES, describe, get_handler

__version__ = "2.0"

__all__ = [
    "ENV_FILE_DEFAULT",
    "KIND_AUTO",
    "KIND_CHOICES",
    "AnonymizeError",
    "Cipher",
    "decrypt_text",
    "decrypt_token",
    "default_output",
    "describe",
    "encrypt_email",
    "encrypt_name",
    "encrypt_phone",
    "encrypt_text",
    "generate_env",
    "get_handler",
    "mapping_csv",
    "process_bytes",
    "process_file",
    "resolve_key",
    "transform_text",
    "write_mapping",
]
