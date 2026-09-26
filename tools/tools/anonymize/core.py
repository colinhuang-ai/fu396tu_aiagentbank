"""
tools/core.py - Nen tang dung chung cho ca ma hoa lan giai ma.

Chua: hang so dinh dang token, doc khoa tu .env, va lop Cipher boc AES-SIV.
Khong chua logic nhan dien email / so dien thoai - phan do nam o encrypt.py va decrypt.py.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

# --------------------------------------------------------------------------
# Hang so
# --------------------------------------------------------------------------

ENV_FILE_DEFAULT = ".env"
ENV_KEY = "ANONYMIZE_KEY"            # base64 cua 32/48/64 bytes
ENV_PASSPHRASE = "ANONYMIZE_PASSPHRASE"
ENV_SALT = "ANONYMIZE_SALT"

TOKEN_PREFIX = "enc1"                # phien ban dinh dang token
KIND_EMAIL = "e"                     # local-part cua email
KIND_PHONE = "p"                     # so dien thoai
KIND_NAME = "n"                      # ten nguoi noi trong transcript
KINDS = KIND_EMAIL + KIND_PHONE + KIND_NAME

# AAD (associated data) cho tung loai - rang buoc token vao dung ngu canh
AAD_PHONE = b"phone"
AAD_NAME = b"speaker"

# Bang chu cai base32 thuong: a-z2-7 -> hop le trong local-part email, an toan trong CSV
B32_ALPHABET = "a-z2-7"

# Mau regex cua mot token (dung chung: encrypt de bo qua, decrypt de tim)
TOKEN_PATTERN = rf"{TOKEN_PREFIX}[{KINDS}][{B32_ALPHABET}]+"

EMAIL_LOCAL_MAX = 64                 # RFC 5321
BOM_UTF8 = b"\xef\xbb\xbf"
XLSX_SUFFIXES = (".xlsx", ".xlsm")


class AnonymizeError(Exception):
    """Loi nghiep vu - in ra goi y thay vi traceback."""


# --------------------------------------------------------------------------
# .env  &  khoa
# --------------------------------------------------------------------------

def load_env_file(path: str | Path) -> dict[str, str]:
    """Doc file .env don gian (KEY=VALUE, bo qua comment va dong trong)."""
    env: dict[str, str] = {}
    p = Path(path)
    if not p.is_file():
        return env
    for raw in p.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        env[key.strip()] = value
    return env


def resolve_key(env_path: str | Path = ENV_FILE_DEFAULT) -> bytes:
    """
    Lay khoa theo thu tu uu tien:
      1. Bien moi truong hoac .env : ANONYMIZE_KEY (base64 cua 32/48/64 bytes)
      2. ANONYMIZE_PASSPHRASE + ANONYMIZE_SALT (dan xuat bang scrypt)
    """
    file_env = load_env_file(env_path)

    def get(name: str) -> str:
        return os.environ.get(name) or file_env.get(name, "")

    raw_key = get(ENV_KEY).strip()
    if raw_key:
        try:
            key = base64.b64decode(raw_key, validate=True)
        except Exception as exc:
            raise AnonymizeError(f"{ENV_KEY} khong phai base64 hop le: {exc}") from exc
        if len(key) not in (32, 48, 64):
            raise AnonymizeError(
                f"{ENV_KEY} phai la 32/48/64 bytes sau khi giai base64 (dang co {len(key)}). "
                f"Chay: python anonymize.py genkey"
            )
        return key

    passphrase = get(ENV_PASSPHRASE)
    if passphrase:
        salt = get(ENV_SALT)
        if not salt:
            raise AnonymizeError(f"Da co {ENV_PASSPHRASE} nhung thieu {ENV_SALT} trong {env_path}")
        kdf = Scrypt(salt=salt.encode("utf-8"), length=64, n=2 ** 15, r=8, p=1)
        return kdf.derive(passphrase.encode("utf-8"))

    raise AnonymizeError(
        f"Khong tim thay khoa. Tao file {env_path} bang lenh:\n"
        f"    python anonymize.py genkey"
    )


def generate_env(env_path: str | Path = ENV_FILE_DEFAULT, force: bool = False) -> Path:
    """Tao file .env moi voi khoa ngau nhien 64 bytes."""
    p = Path(env_path)
    if p.exists() and not force:
        raise AnonymizeError(f"{p} da ton tai. Dung --force de ghi de (SE MAT KHOA CU!).")
    key_b64 = base64.b64encode(os.urandom(64)).decode()
    p.write_text(
        "# Khoa ma hoa cho anonymize - GIU BI MAT, KHONG commit len git.\n"
        "# Mat khoa nay = khong the giai ma lai du lieu.\n"
        f"{ENV_KEY}={key_b64}\n",
        encoding="utf-8",
    )
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return p


# --------------------------------------------------------------------------
# Codec base32
# --------------------------------------------------------------------------

def b32_encode(data: bytes) -> str:
    return base64.b32encode(data).decode("ascii").rstrip("=").lower()


def b32_decode(text: str) -> bytes:
    s = text.upper()
    s += "=" * (-len(s) % 8)
    return base64.b32decode(s)


# --------------------------------------------------------------------------
# Cipher
# --------------------------------------------------------------------------

class Cipher:
    """
    Giu khoa va thuc hien nguyen thuy AES-SIV (deterministic AEAD, RFC 5297).

    Deterministic -> cung mot dau vao luon ra cung mot token, nen du lieu da ma hoa
    van JOIN / GROUP BY / dem trung lap duoc.

    `mapping` ghi lai cac cap da xu ly trong lan chay nay (encrypt: goc -> token,
    decrypt: token -> goc) de dem so luong va xuat bang doi chieu.
    """

    def __init__(
        self,
        key: bytes,
        normalize_phone: bool = False,
        mask_mentions: bool = False,
    ):
        self._siv = AESSIV(key)
        # cau hinh cho mot lan chay, cac handler doc lai tu day
        self.normalize_phone = normalize_phone
        self.mask_mentions = mask_mentions
        self.mapping: dict[str, str] = {}

    def seal(self, plaintext: str, kind: str, aad: bytes) -> str:
        """Ma hoa -> chuoi token day du (ke ca tien to)."""
        ct = self._siv.encrypt(plaintext.encode("utf-8"), [kind.encode(), aad])
        return f"{TOKEN_PREFIX}{kind}{b32_encode(ct)}"

    def unseal(self, body: str, kind: str, aad: bytes) -> str:
        """Giai ma phan than token (da bo tien to) -> chuoi goc."""
        return self._siv.decrypt(b32_decode(body), [kind.encode(), aad]).decode("utf-8")

    def record(self, source: str, result: str) -> None:
        self.mapping[source] = result
