"""tools/anonymize/selftest.py - Kiem thu nhanh toan bo luong voi mot khoa tam."""

from __future__ import annotations

import os

from .core import Cipher
from .decrypt import decrypt_text
from .encrypt import encrypt_text
from .handlers.transcript import TranscriptHandler

SAMPLE = (
    "Cindy\tBAO\t21657@students.isb.ac.th\t\t\t\t\t1\t"
    "loretoa@isb.ac.th | miokc@isb.ac.th\tkevinc@isb.ac.th\t"
    "+84 912 345 678\t0987654321"
)

# Transcript dung CRLF, dang "moc thoi gian - Ten" (ban xuat Google Meet / Otter)
TRANSCRIPT_CRLF = (
    b"0:01 - Nika@MARIO\r\n"
    b"Okay, that is me.\r\n"
    b"0:20 - Tran Thi B\r\n"
    b"Vang a, lien he loretoa@isb.ac.th.\r\n"
)


def run_selftest() -> int:
    cipher = Cipher(os.urandom(64))
    enc = encrypt_text(SAMPLE, cipher)
    dec = decrypt_text(enc, cipher, strict=True)

    checks: list[tuple[str, bool]] = [
        ("giai ma tra ve dung ban goc", dec == SAMPLE),
        ("giu nguyen domain isb.ac.th", "@isb.ac.th" in enc),
        ("khong con email goc", "loretoa@" not in enc and "kevinc@" not in enc),
        ("giu nguyen ten Cindy / BAO", "Cindy" in enc and "BAO" in enc),
        ("khong dung toi so ngan (cot '1')", "\t1\t" in enc),
        ("khong con so dien thoai goc", "912 345 678" not in enc and "0987654321" not in enc),
        ("deterministic (2 lan ma hoa giong nhau)", encrypt_text(SAMPLE, cipher) == enc),
        ("idempotent (ma hoa lai khong doi)", encrypt_text(enc, cipher) == enc),
    ]

    # Hoi quy: so dien thoai cuoi dong khong duoc nuot sang cac dong sau
    multiline = "Goi +84 912 345 678.\n\n3\n00:00:09.000 --> 00:00:12.000\n"
    enc_multi = encrypt_text(multiline, cipher)
    checks.append(
        ("so dien thoai khong nuot qua xuong dong", "00:00:09.000 --> 00:00:12.000" in enc_multi)
    )
    checks.append(
        ("moc thoi gian khong bi ma hoa", decrypt_text(enc_multi, cipher, True) == multiline)
    )

    # Hoi quy: transcript CRLF khong duoc mat ky tu CR o dong nguoi noi
    handler = TranscriptHandler()
    enc_crlf = handler.process(TRANSCRIPT_CRLF, cipher, "encrypt")
    checks.append(("transcript: ten nguoi noi duoc ma hoa", b"Nika@MARIO" not in enc_crlf))
    checks.append(("transcript: giu nguyen so luong CRLF", enc_crlf.count(b"\r\n") == 4))
    checks.append(
        (
            "transcript CRLF round-trip dung tung byte",
            handler.process(enc_crlf, cipher, "decrypt", True) == TRANSCRIPT_CRLF,
        )
    )

    dup = encrypt_text("a@x.com b@x.com a@x.com", cipher).split()
    checks.append(("gia tri trung lap -> token trung lap", dup[0] == dup[2] != dup[1]))
    other = Cipher(os.urandom(64))
    checks.append(("khoa khac khong giai ma duoc", decrypt_text(enc, other, strict=False) == enc))

    print("Vi du (ban goc):\n  " + SAMPLE.replace("\t", " | "))
    print("\nVi du (da ma hoa):\n  " + enc.replace("\t", " | "))
    print()
    ok = True
    for name, passed in checks:
        print(f"  [{'OK  ' if passed else 'FAIL'}] {name}")
        ok &= passed
    print("\n" + ("Tat ca kiem thu deu dat." if ok else "CO KIEM THU THAT BAI."))
    return 0 if ok else 1
