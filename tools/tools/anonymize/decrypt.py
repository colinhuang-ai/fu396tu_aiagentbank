"""
tools/decrypt.py - Tim token trong van ban va khoi phuc gia tri goc.

enc1e<token>@isb.ac.th  ->  loretoa@isb.ac.th
enc1p<token>            ->  +84 912 345 678

Sai khoa hoac du lieu bi sua doi -> AES-SIV bao InvalidTag, khong tra ra ket qua rac.
"""

from __future__ import annotations

import re
import sys

from cryptography.exceptions import InvalidTag

from .core import (
    AAD_NAME,
    AAD_PHONE,
    B32_ALPHABET,
    KINDS,
    KIND_EMAIL,
    KIND_NAME,
    TOKEN_PREFIX,
    AnonymizeError,
    Cipher,
)

# Token co the dung mot minh (dien thoai) hoac di kem @domain (email)
TOKEN_RE = re.compile(
    rf"{TOKEN_PREFIX}(?P<kind>[{KINDS}])(?P<body>[{B32_ALPHABET}]+)"
    rf"(?:@(?P<domain>[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+))?"
)


def decrypt_token(cipher: Cipher, kind: str, body: str, domain: str | None) -> str:
    """Giai ma mot token le. `domain` chi co voi token email."""
    if kind == KIND_EMAIL:
        if domain is None:
            raise AnonymizeError("token email thieu @domain")
        return f"{cipher.unseal(body, kind, domain.lower().encode('utf-8'))}@{domain}"
    aad = AAD_NAME if kind == KIND_NAME else AAD_PHONE
    return cipher.unseal(body, kind, aad)


def decrypt_text(text: str, cipher: Cipher, strict: bool = False) -> str:
    """
    Khoi phuc moi token trong `text`.

    strict=True  -> gap token loi thi dung han (AnonymizeError).
    strict=False -> canh bao ra stderr va giu nguyen token do.
    """

    def repl(m: re.Match[str]) -> str:
        try:
            plain = decrypt_token(cipher, m.group("kind"), m.group("body"), m.group("domain"))
        except (InvalidTag, AnonymizeError, ValueError, UnicodeDecodeError) as exc:
            reason = str(exc) or type(exc).__name__
            msg = f"khong giai ma duoc token '{m.group(0)[:32]}...': {reason}"
            if strict:
                raise AnonymizeError(
                    msg + "\n  -> Sai khoa (.env) hoac du lieu bi sua doi."
                ) from exc
            print(f"  [bo qua] {msg}", file=sys.stderr)
            return m.group(0)
        cipher.record(m.group(0), plain)   # de dem va hien thi vi du
        return plain

    return TOKEN_RE.sub(repl, text)
