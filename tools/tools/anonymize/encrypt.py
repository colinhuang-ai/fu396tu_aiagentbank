"""
tools/encrypt.py - Nhan dien va ma hoa thong tin nhay cam.

Email  : loretoa@isb.ac.th  ->  enc1e<token>@isb.ac.th   (giu nguyen domain)
Dien thoai: +84 912 345 678 ->  enc1p<token>

Domain duoc dua vao AAD nen token cua a@x.com khong the bi "dan" sang @y.com.
"""

from __future__ import annotations

import re
import sys

from .core import (
    AAD_NAME,
    AAD_PHONE,
    EMAIL_LOCAL_MAX,
    KIND_EMAIL,
    KIND_NAME,
    KIND_PHONE,
    TOKEN_PATTERN,
    Cipher,
)

# --------------------------------------------------------------------------
# Mau nhan dien
# --------------------------------------------------------------------------

EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}"
)

# So dien thoai: bat dau bang + hoac chu so, cho phep space - . ( ) lam dau phan cach.
# So chu so duoc kiem tra lai trong is_phone_number() de tranh nhan nham ma so / ID.
# Luu y: dau phan cach chi gom khoang trang NGANG (space, tab) - khong co \n.
# Neu cho phep xuong dong, mot so dien thoai cuoi doan se nuot sang cac dong sau
# (vd: nuot luon moc thoi gian cua cue ke tiep trong file .vtt).
PHONE_RE = re.compile(r"(?<![\w+])(\+?\d[\d \t().\-]{7,20}\d)(?!\w)")

PHONE_MIN_DIGITS = 9
PHONE_MAX_DIGITS = 15

# Quet mot lan duy nhat: nhanh "token" dung truoc nen token vua sinh khong bi quet lai.
_SCAN_RE = re.compile(
    rf"(?P<token>{TOKEN_PATTERN})"
    rf"|(?P<email>{EMAIL_RE.pattern})"
    rf"|(?P<phone>{PHONE_RE.pattern})"
)


def normalize_phone_number(phone: str) -> str:
    """Chi giu dau + o dau va cac chu so -> cung so o nhieu dinh dang se ra cung token."""
    digits = re.sub(r"\D", "", phone)
    return ("+" + digits) if phone.lstrip().startswith("+") else digits


def is_phone_number(candidate: str) -> bool:
    digits = re.sub(r"\D", "", candidate)
    return PHONE_MIN_DIGITS <= len(digits) <= PHONE_MAX_DIGITS


# --------------------------------------------------------------------------
# Ma hoa tung gia tri
# --------------------------------------------------------------------------

def encrypt_email(cipher: Cipher, email: str) -> str:
    local, _, domain = email.rpartition("@")
    token = cipher.seal(local, KIND_EMAIL, domain.lower().encode("utf-8"))
    if len(token) > EMAIL_LOCAL_MAX:
        print(
            f"  [canh bao] local-part sau ma hoa dai {len(token)} ky tu (>64): {email}",
            file=sys.stderr,
        )
    result = f"{token}@{domain}"
    cipher.record(email, result)
    return result


def encrypt_phone(cipher: Cipher, phone: str) -> str:
    value = normalize_phone_number(phone) if cipher.normalize_phone else phone
    token = cipher.seal(value, KIND_PHONE, AAD_PHONE)
    cipher.record(phone, token)
    return token


# Ten nguoi hop le: bat dau bang chu cai (ke ca tieng Viet co dau), toi da 5 tu
PERSON_NAME_RE = re.compile(r"^[^\W\d_][\w'’.\- ]{0,48}$", re.UNICODE)


def looks_like_person(name: str) -> bool:
    """Kiem tra hinh dang cua mot ten nguoi (khong xet ngu canh)."""
    cleaned = name.strip()
    if not cleaned or "@" in cleaned or len(cleaned.split()) > 5:
        return False
    return bool(PERSON_NAME_RE.match(cleaned))


def encrypt_name(cipher: Cipher, name: str) -> str:
    """Ma hoa ten nguoi (nguoi noi trong transcript). Chuan hoa khoang trang de on dinh."""
    token = cipher.seal(" ".join(name.split()), KIND_NAME, AAD_NAME)
    cipher.record(name, token)
    return token


# --------------------------------------------------------------------------
# Ma hoa toan bo van ban
# --------------------------------------------------------------------------

def encrypt_text(text: str, cipher: Cipher) -> str:
    """Thay moi email / so dien thoai trong `text` bang token. Giu nguyen phan con lai."""

    def repl(m: re.Match[str]) -> str:
        if m.group("token"):
            return m.group(0)          # da ma hoa roi -> giu nguyen (idempotent)
        if m.group("email"):
            return encrypt_email(cipher, m.group("email"))
        candidate = m.group("phone")
        if candidate and is_phone_number(candidate):
            return encrypt_phone(cipher, candidate)
        return m.group(0)              # so ngan / ma ID -> khong dung toi

    return _SCAN_RE.sub(repl, text)
