#!/usr/bin/env python3
"""
anonymize.py - Ma hoa / giai ma thong tin nhay cam (email, so dien thoai) trong file du lieu.

Dac diem:
  * Deterministic (AES-SIV, RFC 5297): cung mot email luon ra cung mot token
    -> van join / dedup / group-by duoc tren du lieu da ma hoa.
  * Reversible: giai ma lai chinh xac 100% (lossless round-trip).
  * Email giu nguyen domain:  loretoa@isb.ac.th -> enc1e<token>@isb.ac.th
  * Khoa doc tu file .env (khong hardcode trong source).

Xem README.md de biet cach dung.
"""

from __future__ import annotations

import argparse
import base64
import csv
import os
import re
import sys
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

# --------------------------------------------------------------------------
# Cau hinh chung
# --------------------------------------------------------------------------

ENV_FILE_DEFAULT = ".env"
ENV_KEY = "ANONYMIZE_KEY"            # base64 cua 64 bytes -> AES-256-SIV
ENV_PASSPHRASE = "ANONYMIZE_PASSPHRASE"
ENV_SALT = "ANONYMIZE_SALT"

TOKEN_PREFIX = "enc1"                # phien ban dinh dang token
KIND_EMAIL = "e"
KIND_PHONE = "p"

# Bang chu cai base32 thuong: a-z2-7 -> hop le trong local-part email, an toan trong CSV
_B32 = "a-z2-7"

EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}"
)

# So dien thoai: bat dau bang + hoac chu so, cho phep space - . ( ) lam dau phan cach.
# So chu so duoc kiem tra lai trong _is_phone() de tranh nhan nham ma so / ID.
PHONE_RE = re.compile(r"(?<![\w+])(\+?\d[\d\s().\-]{7,20}\d)(?!\w)")

PHONE_MIN_DIGITS = 9
PHONE_MAX_DIGITS = 15
EMAIL_LOCAL_MAX = 64  # RFC 5321


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


def resolve_key(env_path: str | Path) -> bytes:
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


def generate_env(env_path: str | Path, force: bool = False) -> Path:
    p = Path(env_path)
    if p.exists() and not force:
        raise AnonymizeError(f"{p} da ton tai. Dung --force de ghi de (SE MAT KHOA CU!).")
    key_b64 = base64.b64encode(os.urandom(64)).decode()
    p.write_text(
        "# Khoa ma hoa cho anonymize.py - GIU BI MAT, KHONG commit len git.\n"
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
# Codec token
# --------------------------------------------------------------------------

def _b32_encode(data: bytes) -> str:
    return base64.b32encode(data).decode("ascii").rstrip("=").lower()


def _b32_decode(text: str) -> bytes:
    s = text.upper()
    s += "=" * (-len(s) % 8)
    return base64.b32decode(s)


class Anonymizer:
    """Ma hoa / giai ma cac gia tri nhay cam bang AES-SIV (deterministic AEAD)."""

    def __init__(self, key: bytes, normalize_phone: bool = False):
        self._siv = AESSIV(key)
        self.normalize_phone = normalize_phone
        # audit: cac cap (goc -> token) da xu ly trong lan chay nay
        self.mapping: dict[str, str] = {}

    # -- primitive -------------------------------------------------------
    def _encrypt(self, plaintext: str, kind: str, aad: bytes) -> str:
        ct = self._siv.encrypt(plaintext.encode("utf-8"), [kind.encode(), aad])
        return f"{TOKEN_PREFIX}{kind}{_b32_encode(ct)}"

    def _decrypt(self, body: str, kind: str, aad: bytes) -> str:
        return self._siv.decrypt(_b32_decode(body), [kind.encode(), aad]).decode("utf-8")

    # -- email -----------------------------------------------------------
    def encrypt_email(self, email: str) -> str:
        local, _, domain = email.rpartition("@")
        token = self._encrypt(local, KIND_EMAIL, domain.lower().encode("utf-8"))
        if len(token) > EMAIL_LOCAL_MAX:
            print(
                f"  [canh bao] local-part sau ma hoa dai {len(token)} ky tu (>64): {email}",
                file=sys.stderr,
            )
        result = f"{token}@{domain}"
        self.mapping[email] = result
        return result

    # -- phone -----------------------------------------------------------
    def encrypt_phone(self, phone: str) -> str:
        value = normalize_phone_number(phone) if self.normalize_phone else phone
        token = self._encrypt(value, KIND_PHONE, b"phone")
        self.mapping[phone] = token
        return token

    # -- decrypt ---------------------------------------------------------
    def decrypt_token(self, kind: str, body: str, domain: str | None) -> str:
        aad = domain.lower().encode("utf-8") if domain is not None else b"phone"
        return self._decrypt(body, kind, aad)


def normalize_phone_number(phone: str) -> str:
    """Chi giu dau + o dau va cac chu so -> cung so o nhieu dinh dang se ra cung token."""
    digits = re.sub(r"\D", "", phone)
    return ("+" + digits) if phone.lstrip().startswith("+") else digits


def _is_phone(candidate: str) -> bool:
    digits = re.sub(r"\D", "", candidate)
    return PHONE_MIN_DIGITS <= len(digits) <= PHONE_MAX_DIGITS


# --------------------------------------------------------------------------
# Xu ly text: quet mot lan, khong quet lai token vua sinh
# --------------------------------------------------------------------------

_SCAN_RE = re.compile(
    rf"(?P<token>{TOKEN_PREFIX}[{KIND_EMAIL}{KIND_PHONE}][{_B32}]+)"
    rf"|(?P<email>{EMAIL_RE.pattern})"
    rf"|(?P<phone>{PHONE_RE.pattern})"
)


def encrypt_text(text: str, anon: Anonymizer) -> str:
    def repl(m: re.Match[str]) -> str:
        if m.group("token"):
            return m.group(0)          # da ma hoa roi -> giu nguyen (idempotent)
        if m.group("email"):
            return anon.encrypt_email(m.group("email"))
        candidate = m.group("phone")
        if candidate and _is_phone(candidate):
            return anon.encrypt_phone(candidate)
        return m.group(0)              # so ngan / ma ID -> khong dung toi

    return _SCAN_RE.sub(repl, text)


# Token co the dung mot minh (phone) hoac di kem @domain (email)
_DECRYPT_RE = re.compile(
    rf"{TOKEN_PREFIX}(?P<kind>[{KIND_EMAIL}{KIND_PHONE}])(?P<body>[{_B32}]+)"
    rf"(?:@(?P<domain>[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+))?"
)


def decrypt_text(text: str, anon: Anonymizer, strict: bool = False) -> str:
    def repl(m: re.Match[str]) -> str:
        kind, body, domain = m.group("kind"), m.group("body"), m.group("domain")
        try:
            if kind == KIND_EMAIL:
                if domain is None:
                    raise AnonymizeError("token email thieu @domain")
                plain = f"{anon.decrypt_token(kind, body, domain)}@{domain}"
            else:
                plain = anon.decrypt_token(kind, body, None)
            anon.mapping[m.group(0)] = plain   # de dem va hien thi vi du
            return plain
        except (InvalidTag, AnonymizeError, ValueError, UnicodeDecodeError) as exc:
            reason = str(exc) or type(exc).__name__
            msg = f"khong giai ma duoc token '{m.group(0)[:32]}...': {reason}"
            if strict:
                raise AnonymizeError(msg + "\n  -> Sai khoa (.env) hoac du lieu bi sua doi.") from exc
            print(f"  [bo qua] {msg}", file=sys.stderr)
            return m.group(0)

    return _DECRYPT_RE.sub(repl, text)


# --------------------------------------------------------------------------
# Xu ly file
# --------------------------------------------------------------------------

BOM_UTF8 = b"\xef\xbb\xbf"

XLSX_SUFFIXES = (".xlsx", ".xlsm")


def process_text_bytes(raw: bytes, anon: Anonymizer, mode: str, strict: bool) -> bytes:
    """Giu nguyen BOM va kieu xuong dong (CRLF/LF) cua file goc."""
    has_bom = raw.startswith(BOM_UTF8)
    text = raw.decode("utf-8-sig")
    out = encrypt_text(text, anon) if mode == "encrypt" else decrypt_text(text, anon, strict)
    data = out.encode("utf-8")
    return BOM_UTF8 + data if has_bom else data


def process_xlsx_bytes(raw: bytes, anon: Anonymizer, mode: str, strict: bool) -> bytes:
    try:
        import openpyxl
    except ImportError as exc:
        raise AnonymizeError("Can cai openpyxl de xu ly .xlsx:  pip install openpyxl") from exc

    import io

    wb = openpyxl.load_workbook(io.BytesIO(raw))
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if not isinstance(cell.value, str):
                    continue
                cell.value = (
                    encrypt_text(cell.value, anon)
                    if mode == "encrypt"
                    else decrypt_text(cell.value, anon, strict)
                )
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def process_bytes(raw: bytes, filename: str, anon: Anonymizer, mode: str, strict: bool) -> bytes:
    """Diem vao chung cho ca CLI lan web UI."""
    if Path(filename).suffix.lower() in XLSX_SUFFIXES:
        return process_xlsx_bytes(raw, anon, mode, strict)
    return process_text_bytes(raw, anon, mode, strict)


def process_file(src: Path, dst: Path, anon: Anonymizer, mode: str, strict: bool) -> None:
    out = process_bytes(src.read_bytes(), src.name, anon, mode, strict)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(out)


def default_output(src: Path, mode: str) -> Path:
    stem, suffix = src.stem, src.suffix
    if mode == "encrypt":
        return src.with_name(f"{stem}.enc{suffix}")
    stem = stem[:-4] if stem.endswith(".enc") else f"{stem}.dec"
    return src.with_name(f"{stem}{suffix}")


def write_mapping(path: Path, anon: Anonymizer) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["original", "token"])
        for original, token in sorted(anon.mapping.items()):
            writer.writerow([original, token])


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

def run_selftest() -> int:
    anon = Anonymizer(os.urandom(64))
    sample = (
        "Cindy\tBAO\t21657@students.isb.ac.th\t\t\t\t\t1\t"
        "loretoa@isb.ac.th | miokc@isb.ac.th\tkevinc@isb.ac.th\t"
        "+84 912 345 678\t0987654321"
    )
    enc = encrypt_text(sample, anon)
    dec = decrypt_text(enc, anon, strict=True)

    checks: list[tuple[str, bool]] = [
        ("giai ma tra ve dung ban goc", dec == sample),
        ("giu nguyen domain isb.ac.th", "@isb.ac.th" in enc),
        ("khong con email goc", "loretoa@" not in enc and "kevinc@" not in enc),
        ("giu nguyen ten Cindy / BAO", "Cindy" in enc and "BAO" in enc),
        ("khong dung toi so ngan (cot '1')", "\t1\t" in enc),
        ("khong con so dien thoai goc", "912 345 678" not in enc and "0987654321" not in enc),
        ("deterministic (2 lan ma hoa giong nhau)", encrypt_text(sample, anon) == enc),
        ("idempotent (ma hoa lai khong doi)", encrypt_text(enc, anon) == enc),
    ]
    dup = encrypt_text("a@x.com b@x.com a@x.com", anon).split()
    checks.append(("gia tri trung lap -> token trung lap", dup[0] == dup[2] != dup[1]))
    other = Anonymizer(os.urandom(64))
    checks.append(("khoa khac khong giai ma duoc", decrypt_text(enc, other, strict=False) == enc))

    print("Vi du (ban goc):\n  " + sample.replace("\t", " | "))
    print("\nVi du (da ma hoa):\n  " + enc.replace("\t", " | "))
    print()
    ok = True
    for name, passed in checks:
        print(f"  [{'OK  ' if passed else 'FAIL'}] {name}")
        ok &= passed
    print("\n" + ("Tat ca kiem thu deu dat." if ok else "CO KIEM THU THAT BAI."))
    return 0 if ok else 1


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="anonymize.py",
        description="Ma hoa / giai ma email va so dien thoai trong file du lieu (co the giai ma nguoc).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Vi du:\n"
            "  python anonymize.py genkey\n"
            "  python anonymize.py encrypt -i students.tsv -o students.enc.tsv --mapping map.csv\n"
            "  python anonymize.py decrypt -i students.enc.tsv -o students.tsv\n"
            '  python anonymize.py encrypt -t "loretoa@isb.ac.th"\n'
            "  python anonymize.py selftest\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("genkey", help="Tao file .env voi khoa ngau nhien moi")
    p_gen.add_argument("--env", default=ENV_FILE_DEFAULT, help="duong dan file .env (mac dinh: .env)")
    p_gen.add_argument("--force", action="store_true", help="ghi de .env dang co (mat khoa cu)")

    for name, verb in (("encrypt", "Ma hoa"), ("decrypt", "Giai ma")):
        p = sub.add_parser(name, help=f"{verb} email / so dien thoai")
        src = p.add_mutually_exclusive_group(required=True)
        src.add_argument("-i", "--in", dest="input", help="file dau vao (.tsv .csv .txt .xlsx ...)")
        src.add_argument("-t", "--text", help="xu ly truc tiep mot chuoi")
        src.add_argument("--stdin", action="store_true", help="doc tu stdin")
        p.add_argument("-o", "--out", dest="output", help="file dau ra (mac dinh: them .enc / bo .enc)")
        p.add_argument("--env", default=ENV_FILE_DEFAULT, help="duong dan file .env")
        p.add_argument("--mapping", help="[encrypt] xuat file CSV doi chieu goc -> token")
        p.add_argument(
            "--normalize-phone",
            action="store_true",
            help="[encrypt] chuan hoa so dien thoai truoc khi ma hoa (cung so o nhieu dinh dang "
                 "-> cung token, nhung giai ma se tra ve dang da chuan hoa)",
        )
        p.add_argument("--strict", action="store_true", help="[decrypt] dung lai neu gap token loi")

    p_serve = sub.add_parser("serve", help="Mo giao dien web (keo tha file) tai localhost")
    p_serve.add_argument("--port", type=int, default=8765, help="cong lang nghe (mac dinh: 8765)")
    p_serve.add_argument("--env", default=ENV_FILE_DEFAULT, help="duong dan file .env")
    p_serve.add_argument("--no-browser", action="store_true", help="khong tu mo trinh duyet")

    sub.add_parser("selftest", help="Chay kiem thu nhanh voi khoa tam")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "selftest":
        return run_selftest()

    if args.command == "serve":
        import server
        return server.serve(port=args.port, env_path=args.env, open_browser=not args.no_browser)

    if args.command == "genkey":
        path = generate_env(args.env, args.force)
        print(f"Da tao khoa moi trong {path}")
        print("Hay sao luu file nay - mat khoa dong nghia khong giai ma lai duoc du lieu.")
        return 0

    mode = args.command
    anon = Anonymizer(resolve_key(args.env), normalize_phone=getattr(args, "normalize_phone", False))
    strict = getattr(args, "strict", False)

    # --- che do chuoi / stdin ---
    if args.text is not None or args.stdin:
        text = args.text if args.text is not None else sys.stdin.read()
        out = encrypt_text(text, anon) if mode == "encrypt" else decrypt_text(text, anon, strict)
        if args.output:
            Path(args.output).write_text(out, encoding="utf-8")
            print(f"Da ghi {args.output}")
        else:
            sys.stdout.write(out if out.endswith("\n") else out + "\n")
        if getattr(args, "mapping", None):
            write_mapping(Path(args.mapping), anon)
        return 0

    # --- che do file ---
    src = Path(args.input)
    if not src.is_file():
        raise AnonymizeError(f"Khong tim thay file dau vao: {src}")
    dst = Path(args.output) if args.output else default_output(src, mode)
    if dst.resolve() == src.resolve():
        raise AnonymizeError("File dau ra trung file dau vao - hay chi dinh -o khac.")

    process_file(src, dst, anon, mode, strict)

    print(f"{'Da ma hoa' if mode == 'encrypt' else 'Da giai ma'}: {src} -> {dst}")
    print(f"  {len(anon.mapping)} gia tri nhay cam da duoc xu ly.")
    if mode == "encrypt" and args.mapping:
        write_mapping(Path(args.mapping), anon)
        print(f"  Bang doi chieu: {args.mapping}  (chua du lieu goc - bao mat nhu .env!)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AnonymizeError as exc:
        print(f"Loi: {exc}", file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        sys.exit(130)
