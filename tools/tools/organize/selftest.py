"""tools/organize/selftest.py - Kiem thu nhanh tren thu muc tam."""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

from .core import build_plan, collect, execute, prune_empty_dirs, sort_files
from .journal import JOURNAL_NAME, Journal, undo_last
from .kinds import kind_of
from .naming import render, slugify, with_counter

FIXTURES = (
    "Biên bản họp Quý 3.docx",
    "Báo cáo 2026-03-15 (bản cuối).pdf",
    "anh chup man hinh.PNG",
    "notes.txt",
    "Danh sách HS.xlsx",
)


def _make_tree(root: Path) -> None:
    for name in FIXTURES:
        (root / name).write_text(f"noi dung {name}", encoding="utf-8")


def run_selftest() -> int:
    checks: list[tuple[str, bool]] = [
        ("slugify bo dau tieng Viet",
         slugify("Biên bản họp Quý 3") == "bien-ban-hop-quy-3"),
        ("slugify xu ly chu d gach",
         slugify("Đơn xin nghỉ") == "don-xin-nghi"),
        ("slugify dung dau gach duoi khi duoc yeu cau",
         slugify("Báo cáo tài chính", "_") == "bao_cao_tai_chinh"),
        ("phan loai theo duoi file",
         kind_of("a.pdf") == "tai-lieu" and kind_of("b.vtt") == "bien-ban"
         and kind_of("c.xyz") == "khac"),
        ("mau chan duong dan thoat ra ngoai",
         render("{name}{ext}", {"name": "../../etc/passwd", "ext": ".txt"}) == "etcpasswd.txt"),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_tree(root)

        # --- doi ten ---
        files = sort_files(collect(root), "name")
        checks.append(("quet du so file", len(files) == len(FIXTURES)))

        plan = build_plan(root, files, "{slug}{ext}")
        names = {a.dst.name for a in plan.actions}
        checks.append(("doi ten: bo dau va viet thuong",
                       "bien-ban-hop-quy-3.docx" in names and "danh-sach-hs.xlsx" in names))
        checks.append(("doi ten: duoi file duoc chuan hoa ve chu thuong",
                       "anh-chup-man-hinh.png" in names))
        checks.append(("xem truoc khong dong vao dia",
                       (root / FIXTURES[0]).exists()))

        # Hoi quy: rename -r khong duoc lam phang cay thu muc
        (root / "con").mkdir(exist_ok=True)
        (root / "con" / "Tệp con.txt").write_text("x", encoding="utf-8")
        deep = sort_files(collect(root, recursive=True), "name")
        in_place = build_plan(root, deep, "{slug}{ext}", anchor="parent")
        moved_out = [a for a in in_place.changes if a.src.parent != a.dst.parent]
        checks.append(("rename -r giu file o nguyen thu muc", not moved_out))
        checks.append(
            ("rename -r van doi ten trong thu muc con",
             any(a.dst.name == "tep-con.txt" for a in in_place.changes))
        )
        (root / "con" / "Tệp con.txt").unlink()
        (root / "con").rmdir()

        # --- ngay lay tu ten file ---
        dated = build_plan(root, files, "{date}-{slug}{ext}", date_source="name")
        checks.append(("lay duoc ngay tu ten file",
                       any(a.dst.name.startswith("2026-03-15-bao-cao") for a in dated.actions)))

        # --- danh so thu tu ---
        numbered = build_plan(root, files, "{n:03d}-{slug}{ext}")
        checks.append(("danh so {n:03d}",
                       numbered.actions[0].dst.name.startswith("001-")))

        # --- trung ten ---
        clash = build_plan(root, files, "chung{ext}")
        docx_targets = [a.dst.name for a in clash.actions if a.dst.suffix == ".docx"]
        checks.append(("trung ten thi them hau to", "chung.docx" in docx_targets))

        # Hoi quy: doi ten chi khac hoa/thuong phai duoc thuc hien that
        # (Windows khong phan biet hoa/thuong nen rat de bi bo qua nham)
        upper = root / "HOADON.TXT"
        upper.write_text("noi dung hoa don", encoding="utf-8")
        case_plan = build_plan(root, [upper], "{slug}{ext}", anchor="parent")
        checks.append(("doi ten chi khac hoa/thuong duoc nhan ra", len(case_plan.changes) == 1))
        with Journal(root / "case.jsonl", "selftest-case") as journal:
            execute(case_plan, journal)
        on_disk = {p.name for p in root.glob("*.txt")}
        checks.append(("doi ten hoa/thuong thuc hien duoc that", "hoadon.txt" in on_disk))
        checks.append(("doi ten hoa/thuong khong mat noi dung",
                       (root / "hoadon.txt").read_text(encoding="utf-8") == "noi dung hoa don"))
        (root / "hoadon.txt").unlink()
        (root / "case.jsonl").unlink()

        # --- thuc thi + hoan tac ---
        journal_path = root / JOURNAL_NAME
        with Journal(journal_path, "selftest") as journal:
            done = execute(build_plan(root, files, "{kind}/{slug}{ext}"), journal)
        checks.append(("da di chuyen het file", done == len(FIXTURES)))
        checks.append(("file nam dung thu muc nhom",
                       (root / "tai-lieu" / "notes.txt").is_file()))
        checks.append(("file goc khong con o cho cu",
                       not (root / "notes.txt").exists()))

        _at, restored, warnings = undo_last(journal_path, dry_run=False)
        checks.append(("hoan tac khoi phuc du file", len(restored) == len(FIXTURES)))
        checks.append(("hoan tac khong canh bao", not warnings))
        checks.append(("file da tro ve dung cho cu",
                       all((root / name).is_file() for name in FIXTURES)))

        removed = prune_empty_dirs(root)
        checks.append(("don duoc thu muc rong", len(removed) >= 1))

        # --- chi lay dung loai file ---
        only_pdf = collect(root, include=("*.pdf",))
        checks.append(("--include loc dung", len(only_pdf) == 1))

        taken: set[Path] = set()
        first = with_counter(root / "moi.txt", taken)
        taken.add(first)
        checks.append(("with_counter tang so khi da bi chiem",
                       with_counter(root / "moi.txt", taken).name == "moi-2.txt"))

    print("Kiem thu tools/organize\n")
    ok = True
    for name, passed in checks:
        print(f"  [{'OK  ' if passed else 'FAIL'}] {name}")
        ok &= passed
    print("\n" + ("Tat ca kiem thu deu dat." if ok else "CO KIEM THU THAT BAI."))
    return 0 if ok else 1
