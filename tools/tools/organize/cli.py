"""tools/organize/cli.py - Giao dien dong lenh."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import (
    CONFLICT_POLICIES,
    SORT_KEYS,
    OrganizeError,
    Plan,
    build_plan,
    collect,
    describe_fields,
    execute,
    prune_empty_dirs,
    sort_files,
)
from .dates import DATE_SOURCES
from .journal import JOURNAL_NAME, Journal, undo_last
from .kinds import describe as describe_kinds
from .selftest import run_selftest

PROG = "organize.py"

DEFAULT_TEMPLATE = "{slug}{ext}"

# Loi tat cho --by, deu la mau binh thuong nen co the sao chep ra --into de chinh them
PRESETS = {
    "kind": "{kind}/{name}{ext}",
    "date": "{year}/{month}/{name}{ext}",
    "kind-date": "{kind}/{year}-{month}/{name}{ext}",
    "ext": "{EXT}/{name}{ext}",
    "year": "{year}/{name}{ext}",
}

PREVIEW_LIMIT = 40


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Doi ten hang loat va sap xep tai lieu vao thu muc. Mac dinh chi xem truoc.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Vi du:\n"
            f"  python {PROG} rename docs                                  # xem truoc\n"
            f'  python {PROG} rename docs --template "{{date}}-{{slug}}{{ext}}" --apply\n'
            f"  python {PROG} arrange docs --by kind-date --apply\n"
            f'  python {PROG} arrange docs --into "{{kind}}/{{year}}" --apply\n'
            f"  python {PROG} undo --apply\n"
            f"  python {PROG} fields\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("directory", help="thu muc can xu ly")
        p.add_argument("--apply", action="store_true",
                       help="thuc su doi tren dia (mac dinh chi xem truoc)")
        p.add_argument("-r", "--recursive", action="store_true", help="xu ly ca thu muc con")
        p.add_argument("--include", nargs="*", default=[], metavar="MAU",
                       help="chi lay file khop mau, vd: --include '*.pdf' '*.docx'")
        p.add_argument("--exclude", nargs="*", default=[], metavar="MAU",
                       help="bo qua file khop mau")
        p.add_argument("--hidden", action="store_true", help="xu ly ca file/thu muc an")
        p.add_argument("--date-from", default="mtime", choices=DATE_SOURCES,
                       help="nguon ngay cho {date}/{year}/{month}/{day} (mac dinh: mtime)")
        p.add_argument("--sep", default="-", help="dau phan cach trong {slug} (mac dinh: -)")
        p.add_argument("--on-conflict", default="suffix", choices=CONFLICT_POLICIES,
                       help="khi ten dich da ton tai (mac dinh: suffix)")
        p.add_argument("--sort", default="name", choices=SORT_KEYS,
                       help="thu tu danh so {n} (mac dinh: name)")
        p.add_argument("--start", type=int, default=1, help="so bat dau cho {n} (mac dinh: 1)")
        p.add_argument("--journal", help=f"duong dan nhat ky (mac dinh: <thu muc>/{JOURNAL_NAME})")

    p_rename = sub.add_parser("rename", help="Doi ten file tai cho")
    add_common(p_rename)
    p_rename.add_argument("-t", "--template", default=DEFAULT_TEMPLATE,
                          help=f"mau ten moi (mac dinh: {DEFAULT_TEMPLATE})")

    p_arrange = sub.add_parser("arrange", help="Sap xep file vao thu muc con")
    add_common(p_arrange)
    group = p_arrange.add_mutually_exclusive_group()
    group.add_argument("--by", choices=sorted(PRESETS), help="cach sap xep dung san")
    group.add_argument("--into", help="mau duong dan tu viet, vd '{kind}/{year}-{month}/{name}{ext}'")
    p_arrange.add_argument("--prune", action="store_true",
                           help="xoa cac thu muc rong con lai sau khi di chuyen")

    p_undo = sub.add_parser("undo", help="Hoan tac phien gan nhat")
    p_undo.add_argument("directory", nargs="?", default=".", help="thu muc da xu ly (mac dinh: .)")
    p_undo.add_argument("--apply", action="store_true", help="thuc su hoan tac")
    p_undo.add_argument("--journal", help="duong dan nhat ky")

    sub.add_parser("fields", help="Liet ke cac bien dung duoc trong mau")
    sub.add_parser("kinds", help="Liet ke cac nhom tai lieu")
    sub.add_parser("selftest", help="Chay kiem thu nhanh")
    return parser


# --------------------------------------------------------------------------
# In ket qua
# --------------------------------------------------------------------------

def _print_plan(plan: Plan, apply: bool) -> None:
    changes = plan.changes
    if not changes:
        print("Khong co gi phai doi.")
    else:
        width = max(len(str(a.src.relative_to(plan.root))) for a in changes[:PREVIEW_LIMIT])
        width = min(width, 60)
        for action in changes[:PREVIEW_LIMIT]:
            src = str(action.src.relative_to(plan.root))
            dst = str(action.dst.relative_to(plan.root))
            print(f"  {src:<{width}}  ->  {dst}")
        if len(changes) > PREVIEW_LIMIT:
            print(f"  ... va {len(changes) - PREVIEW_LIMIT} file nua")

    print()
    parts = [f"{len(changes)} file se doi"]
    if plan.unchanged:
        parts.append(f"{len(plan.unchanged)} da dung ten")
    if plan.skipped:
        parts.append(f"{len(plan.skipped)} bi bo qua")
    print("  " + ", ".join(parts) + ".")

    for path, reason in plan.skipped[:10]:
        print(f"    [bo qua] {path.name}: {reason}")
    if len(plan.skipped) > 10:
        print(f"    ... va {len(plan.skipped) - 10} file bi bo qua nua")

    if changes and not apply:
        print("\n  Day moi la xem truoc. Them --apply de thuc su doi.")


# --------------------------------------------------------------------------
# Cac lenh
# --------------------------------------------------------------------------

def _run_plan_command(args: argparse.Namespace, template: str, anchor: str) -> int:
    root = Path(args.directory).resolve()
    files = sort_files(
        collect(
            root,
            recursive=args.recursive,
            include=tuple(args.include),
            exclude=tuple(args.exclude),
            hidden=args.hidden,
        ),
        args.sort,
    )
    if not files:
        print(f"Khong tim thay file nao trong {root}")
        return 0

    plan = build_plan(
        root, files, template,
        date_source=args.date_from,
        separator=args.sep,
        conflict=args.on_conflict,
        start=args.start,
        anchor=anchor,
    )

    print(f"Thu muc : {root}")
    print(f"Mau     : {template}")
    print(f"Quet duoc {len(files)} file\n")
    _print_plan(plan, args.apply)

    if not args.apply or not plan.changes:
        return 0

    journal_path = Path(args.journal) if args.journal else root / JOURNAL_NAME
    command = f"{args.command} {args.directory} --template {template}"
    with Journal(journal_path, command) as journal:
        done = execute(plan, journal)

    print(f"\nDa doi {done} file.")
    if getattr(args, "prune", False):
        removed = prune_empty_dirs(root)
        if removed:
            print(f"Da xoa {len(removed)} thu muc rong.")
    print(f"Nhat ky : {journal_path}")
    print(f"Hoan tac: python {PROG} undo {args.directory} --apply")
    return 0


def _run_undo(args: argparse.Namespace) -> int:
    root = Path(args.directory).resolve()
    journal_path = Path(args.journal) if args.journal else root / JOURNAL_NAME
    at, restored, warnings = undo_last(journal_path, dry_run=not args.apply)

    print(f"Phien : {at}")
    if not restored:
        print("Khong con gi de khoi phuc.")
    else:
        def show(path: Path) -> str:
            try:
                return str(path.relative_to(root))
            except ValueError:
                return str(path)

        width = min(max(len(show(s)) for s, _ in restored[:PREVIEW_LIMIT]), 60)
        for src, dst in restored[:PREVIEW_LIMIT]:
            print(f"  {show(src):<{width}}  ->  {show(dst)}")
        if len(restored) > PREVIEW_LIMIT:
            print(f"  ... va {len(restored) - PREVIEW_LIMIT} file nua")
        print(f"\n  {len(restored)} file se tro ve cho cu.")

    for warning in warnings:
        print(f"    [canh bao] {warning}")

    if restored and not args.apply:
        print("\n  Day moi la xem truoc. Them --apply de thuc su hoan tac.")
    elif restored:
        print(f"\nDa khoi phuc {len(restored)} file.")
    return 0


def _run(args: argparse.Namespace) -> int:
    if args.command == "selftest":
        return run_selftest()

    if args.command == "fields":
        print("Bien dung duoc trong mau:\n")
        for name, desc in describe_fields():
            print(f"  {name:<22} {desc}")
        print("\nLoi tat cho `arrange --by`:\n")
        for name, template in sorted(PRESETS.items()):
            print(f"  {name:<12} {template}")
        return 0

    if args.command == "kinds":
        print(f"{'Nhom':<14} Duoi file")
        print("-" * 78)
        for row in describe_kinds():
            suffixes = " ".join(row["suffixes"]) or "(moi duoi khong nam trong nhom nao)"
            print(f"{row['kind']:<14} {suffixes}")
        return 0

    if args.command == "undo":
        return _run_undo(args)

    if args.command == "rename":
        # Doi ten tai cho: file o lai thu muc cua no, ke ca khi chay -r
        return _run_plan_command(args, args.template, anchor="parent")

    template = args.into or PRESETS[args.by or "kind"]
    return _run_plan_command(args, template, anchor="root")


def main(argv: list[str] | None = None) -> int:
    """Diem vao cua CLI. Tra ve ma thoat, khong nem OrganizeError ra ngoai."""
    args = build_parser().parse_args(argv)
    try:
        return _run(args)
    except OrganizeError as exc:
        print(f"Loi: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
