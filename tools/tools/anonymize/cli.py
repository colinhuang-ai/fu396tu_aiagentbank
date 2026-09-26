"""tools/cli.py - Giao dien dong lenh."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import ENV_FILE_DEFAULT, AnonymizeError, Cipher, generate_env, resolve_key
from .fileio import default_output, process_file, transform_text, write_mapping
from .handlers import KIND_AUTO, KIND_CHOICES, describe
from .selftest import run_selftest

PROG = "anonymize.py"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Ma hoa / giai ma email va so dien thoai trong file du lieu (co the giai ma nguoc).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Vi du:\n"
            f"  python {PROG} genkey\n"
            f"  python {PROG} serve\n"
            f"  python {PROG} encrypt -i students.tsv -o students.enc.tsv --mapping map.csv\n"
            f"  python {PROG} decrypt -i students.enc.tsv -o students.tsv\n"
            f'  python {PROG} encrypt -t "loretoa@isb.ac.th"\n'
            f"  python {PROG} selftest\n"
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
        p.add_argument(
            "--mask-mentions",
            action="store_true",
            help="[encrypt][transcript] che luon cac lan ten nguoi noi duoc nhac trong loi thoai "
                 "(vd: \"Colin and Rose, would you...\"), khong chi nhan nguoi noi",
        )
        p.add_argument(
            "--kind",
            default=KIND_AUTO,
            choices=KIND_CHOICES,
            help="ep dung handler cho mot loai file (mac dinh: auto - doan theo duoi file va noi dung)",
        )

    p_serve = sub.add_parser("serve", help="Mo giao dien web (keo tha file) tai localhost")
    p_serve.add_argument("--port", type=int, default=8765, help="cong lang nghe (mac dinh: 8765)")
    p_serve.add_argument("--env", default=ENV_FILE_DEFAULT, help="duong dan file .env")
    p_serve.add_argument("--no-browser", action="store_true", help="khong tu mo trinh duyet")

    sub.add_parser("kinds", help="Liet ke cac loai file duoc ho tro")
    sub.add_parser("selftest", help="Chay kiem thu nhanh voi khoa tam")
    return parser


def _run(args: argparse.Namespace) -> int:
    if args.command == "selftest":
        return run_selftest()

    if args.command == "kinds":
        print(f"{'--kind':<12} {'Loai file':<32} Duoi file")
        print("-" * 78)
        for info in describe():
            suffixes = " ".join(info["suffixes"]) or "(mac dinh cho moi file van ban)"
            if info["output_suffix"]:
                suffixes += f"   -> xuat ra {info['output_suffix']}"
            print(f"{info['name']:<12} {info['label']:<32} {suffixes}")
        return 0

    if args.command == "genkey":
        path = generate_env(args.env, args.force)
        print(f"Da tao khoa moi trong {path}")
        print("Hay sao luu file nay - mat khoa dong nghia khong giai ma lai duoc du lieu.")
        return 0

    if args.command == "serve":
        from . import server
        return server.serve(port=args.port, env_path=args.env, open_browser=not args.no_browser)

    mode = args.command
    cipher = Cipher(
        resolve_key(args.env),
        normalize_phone=getattr(args, "normalize_phone", False),
        mask_mentions=getattr(args, "mask_mentions", False),
    )
    strict = getattr(args, "strict", False)
    kind = getattr(args, "kind", KIND_AUTO)

    # --- che do chuoi / stdin ---
    if args.text is not None or args.stdin:
        text = args.text if args.text is not None else sys.stdin.read()
        out = transform_text(text, cipher, mode, strict)
        if args.output:
            Path(args.output).write_text(out, encoding="utf-8")
            print(f"Da ghi {args.output}")
        else:
            sys.stdout.write(out if out.endswith("\n") else out + "\n")
        if getattr(args, "mapping", None):
            write_mapping(Path(args.mapping), cipher)
        return 0

    # --- che do file ---
    src = Path(args.input)
    if not src.is_file():
        raise AnonymizeError(f"Khong tim thay file dau vao: {src}")
    dst = Path(args.output) if args.output else default_output(src, mode, kind, src.read_bytes())
    if dst.resolve() == src.resolve():
        raise AnonymizeError("File dau ra trung file dau vao - hay chi dinh -o khac.")

    process_file(src, dst, cipher, mode, strict, kind)

    print(f"{'Da ma hoa' if mode == 'encrypt' else 'Da giai ma'}: {src} -> {dst}")
    print(f"  {len(cipher.mapping)} gia tri nhay cam da duoc xu ly.")
    if mode == "encrypt" and args.mapping:
        write_mapping(Path(args.mapping), cipher)
        print(f"  Bang doi chieu: {args.mapping}  (chua du lieu goc - bao mat nhu .env!)")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Diem vao cua CLI. Tra ve ma thoat, khong nem AnonymizeError ra ngoai."""
    args = build_parser().parse_args(argv)
    try:
        return _run(args)
    except AnonymizeError as exc:
        print(f"Loi: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
