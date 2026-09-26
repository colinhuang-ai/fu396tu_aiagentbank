"""
tools/handlers/eml.py - Thu dien tu (.eml / .mbox mot thu).

Xu ly co cau truc thay vi quet van ban tho, vi than thu thuong duoc ma hoa
base64 / quoted-printable - quet tho se bo sot hoan toan.

Duoc xu ly:
  * Header dia chi (From, To, Cc, Bcc, Reply-To, ...): ca dia chi lan ten hien thi
  * Subject va cac header van ban khac
  * Moi phan than kieu text/* (da giai ma transfer-encoding truoc khi quet)

Tep dinh kem nhi phan giu nguyen. Luu y: thu duoc dung lai (re-serialize) nen
header co the duoc chuan hoa - noi dung khoi phuc chinh xac, nhung file khong
giong tung byte nhu ban goc.
"""

from __future__ import annotations

import email
from email.message import Message
from email.utils import formataddr, getaddresses

from ..core import AnonymizeError, Cipher
from ..encrypt import encrypt_name, looks_like_person
from .base import Handler, transform_text

ADDRESS_HEADERS = (
    "from", "to", "cc", "bcc", "reply-to", "sender", "resent-from", "resent-to",
    "return-path", "delivered-to", "x-original-to", "x-envelope-to",
)
TEXT_HEADERS = ("subject", "thread-topic", "x-meeting-organizer")


class EmailHandler(Handler):
    name = "email"
    label = "Thu dien tu (.eml)"
    suffixes = (".eml", ".mbox", ".msg")
    binary = False

    def process(self, raw: bytes, cipher: Cipher, mode: str, strict: bool = False) -> bytes:
        if raw[:4] == b"\xd0\xcf\x11\xe0":
            raise AnonymizeError(
                "Day la .msg dinh dang Outlook nhi phan, chua ho tro.\n"
                "  -> Trong Outlook chon 'Save As' kieu .eml, hoac dung .txt xuat ra."
            )
        message = email.message_from_bytes(raw)
        self._process_headers(message, cipher, mode, strict)
        for part in message.walk():
            self._process_headers(part, cipher, mode, strict)
            self._process_body(part, cipher, mode, strict)
        return message.as_bytes()

    # -- header ---------------------------------------------------------
    def _process_headers(self, message: Message, cipher: Cipher, mode: str, strict: bool) -> None:
        for name, value in list(message.items()):
            key = name.lower()
            if key in ADDRESS_HEADERS:
                updated = self._address_header(value, cipher, mode, strict)
            elif key in TEXT_HEADERS:
                updated = transform_text(value, cipher, mode, strict)
            else:
                continue
            if updated != value:
                message.replace_header(name, updated)

    @staticmethod
    def _address_header(value: str, cipher: Cipher, mode: str, strict: bool) -> str:
        pairs = [(n, a) for n, a in getaddresses([value]) if n or a]
        if not pairs:
            return transform_text(value, cipher, mode, strict)

        rebuilt = []
        for display, address in pairs:
            if display:
                display = (
                    encrypt_name(cipher, display)
                    if mode == "encrypt" and looks_like_person(display)
                    else transform_text(display, cipher, mode, strict)
                )
            if address:
                address = transform_text(address, cipher, mode, strict)
            rebuilt.append(formataddr((display, address)))
        return ", ".join(rebuilt)

    # -- than thu -------------------------------------------------------
    @staticmethod
    def _process_body(part: Message, cipher: Cipher, mode: str, strict: bool) -> None:
        if part.is_multipart() or part.get_content_maintype() != "text":
            return
        payload = part.get_payload(decode=True)
        if payload is None:
            return
        charset = part.get_content_charset() or "utf-8"
        try:
            text = payload.decode(charset)
        except (LookupError, UnicodeDecodeError):
            return                      # khong doc duoc thi de nguyen, khong lam hong thu

        updated = transform_text(text, cipher, mode, strict)
        if updated == text:
            return
        del part["Content-Transfer-Encoding"]
        part.set_payload(updated, charset=charset)
