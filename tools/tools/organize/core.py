"""
tools/organize/core.py - Quet file, dung ke hoach, thuc thi an toan.

Nguyen tac:
  * Khong bao gio ghi de - ten trung thi them hau to, bo qua, hoac bao loi (tuy chinh sach).
  * Moi dich den phai nam trong thu muc goc.
  * Ke hoach duoc kiem tra tron ven truoc khi dong vao dia.
  * Moi thao tac thanh cong deu duoc ghi nhat ky de hoan tac duoc.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import naming
from .dates import resolve as resolve_date
from .kinds import kind_of

CONFLICT_POLICIES = ("suffix", "skip", "fail")
# Mau duoc tinh tuong doi so voi dau:
#   parent = thu muc dang chua file  -> doi ten TAI CHO (lenh rename)
#   root   = thu muc goc             -> duoc phep chuyen thu muc (lenh arrange)
ANCHORS = ("parent", "root")
SORT_KEYS = ("name", "date", "size")

DEFAULT_EXCLUDES = (".git", "__pycache__", "node_modules", ".venv", "venv", ".idea", ".vscode")


class OrganizeError(Exception):
    """Loi nghiep vu - in ra goi y thay vi traceback."""


@dataclass(frozen=True)
class Action:
    src: Path
    dst: Path

    # So sanh bang CHUOI, khong bang Path: tren Windows, Path("a.txt") == Path("A.TXT")
    # la True, nen doi ten chi khac hoa/thuong se bi coi nham la khong co gi thay doi.
    @property
    def is_move(self) -> bool:
        return str(self.src.parent) != str(self.dst.parent)

    @property
    def is_noop(self) -> bool:
        return str(self.src) == str(self.dst)


@dataclass
class Plan:
    root: Path
    actions: list[Action] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def changes(self) -> list[Action]:
        return [a for a in self.actions if not a.is_noop]

    @property
    def unchanged(self) -> list[Action]:
        return [a for a in self.actions if a.is_noop]

    def __bool__(self) -> bool:
        return bool(self.changes)


# --------------------------------------------------------------------------
# Quet file
# --------------------------------------------------------------------------

def collect(
    root: Path,
    recursive: bool = False,
    include: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
    hidden: bool = False,
) -> list[Path]:
    """Danh sach file se duoc xu ly, da sap xep on dinh."""
    if not root.is_dir():
        raise OrganizeError(f"Khong phai thu muc: {root}")

    candidates = sorted(root.rglob("*") if recursive else root.glob("*"))
    files: list[Path] = []
    for path in candidates:
        if not path.is_file():
            continue
        parts = path.relative_to(root).parts
        if not hidden and any(p.startswith(".") for p in parts):
            continue
        if any(p in DEFAULT_EXCLUDES for p in parts):
            continue
        if include and not any(path.match(pattern) for pattern in include):
            continue
        if exclude and any(path.match(pattern) for pattern in exclude):
            continue
        files.append(path)
    return files


def sort_files(files: list[Path], key: str = "name") -> list[Path]:
    if key not in SORT_KEYS:
        raise OrganizeError(f"khoa sap xep khong hop le: {key!r} (chon: {', '.join(SORT_KEYS)})")
    if key == "date":
        return sorted(files, key=lambda p: (p.stat().st_mtime, str(p).lower()))
    if key == "size":
        return sorted(files, key=lambda p: (p.stat().st_size, str(p).lower()))
    return sorted(files, key=lambda p: str(p).lower())


# --------------------------------------------------------------------------
# Bien cua mau
# --------------------------------------------------------------------------

def _short_hash(path: Path, length: int = 8) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:length]


def fields_for(
    path: Path,
    root: Path,
    index: int,
    when: date,
    separator: str = "-",
    need_hash: bool = False,
) -> dict[str, object]:
    """Gia tri cac bien dung cho mot file."""
    relative = path.relative_to(root)
    return {
        "name": path.stem,
        "slug": naming.slugify(path.stem, separator),
        "ext": path.suffix.lower(),
        "EXT": path.suffix.upper().lstrip("."),
        "date": when.isoformat(),
        "year": f"{when.year:04d}",
        "month": f"{when.month:02d}",
        "day": f"{when.day:02d}",
        "kind": kind_of(path),
        "parent": relative.parent.name or root.name,
        "n": index,
        "hash": _short_hash(path) if need_hash else "",
    }


def describe_fields() -> list[tuple[str, str]]:
    return [
        ("{name}", "ten goc, chua ke duoi file"),
        ("{slug}", "ten goc da bo dau, viet thuong, noi bang dau gach"),
        ("{ext}", "duoi file viet thuong, co san dau cham (.pdf)"),
        ("{EXT}", "duoi file viet hoa, khong dau cham (PDF)"),
        ("{date}", "ngay dang 2026-09-19"),
        ("{year} {month} {day}", "tung phan cua ngay"),
        ("{kind}", "nhom tai lieu (tai-lieu, hinh-anh, bien-ban...)"),
        ("{parent}", "ten thu muc chua file"),
        ("{n}", "so thu tu; dung {n:03d} de ra 001"),
        ("{hash}", "8 ky tu dau cua SHA-256 noi dung - tien de phat hien trung"),
    ]


# --------------------------------------------------------------------------
# Dung ke hoach
# --------------------------------------------------------------------------

def build_plan(
    root: Path,
    files: list[Path],
    template: str,
    date_source: str = "mtime",
    separator: str = "-",
    conflict: str = "suffix",
    start: int = 1,
    anchor: str = "root",
) -> Plan:
    """
    Dung ke hoach doi ten / di chuyen.

    `template` cho ra duong dan TUONG DOI so voi `anchor`; co dau '/' thi tao thu muc con.

    anchor="parent": file o lai dung thu muc cua no (doi ten tai cho).
    anchor="root":   duong dan tinh tu thu muc goc, nen file co the chuyen thu muc.
    """
    if anchor not in ANCHORS:
        raise OrganizeError(f"anchor khong hop le: {anchor!r} (chon: {', '.join(ANCHORS)})")
    if conflict not in CONFLICT_POLICIES:
        raise OrganizeError(
            f"chinh sach trung ten khong hop le: {conflict!r} "
            f"(chon: {', '.join(CONFLICT_POLICIES)})"
        )
    need_hash = "hash" in naming.placeholders(template)

    plan = Plan(root=root)
    taken: set[Path] = set()

    for offset, src in enumerate(files):
        when = resolve_date(src, date_source)
        values = fields_for(src, root, start + offset, when, separator, need_hash)
        try:
            relative = naming.render(template, values)
        except ValueError as exc:
            raise OrganizeError(str(exc)) from exc

        base = src.parent if anchor == "parent" else root
        # Dung abspath chu khong dung resolve(): tren Windows, resolve() tra ve dung
        # hoa/thuong dang co tren dia, khien "BAOCAO.TXT" -> "baocao.txt" bi coi la
        # khong doi gi va khong bao gio duoc thuc hien.
        dst = Path(os.path.abspath(base / relative))
        if not dst.is_relative_to(Path(os.path.abspath(root))):
            raise OrganizeError(f"mau dua file ra ngoai thu muc goc: {dst}")

        if str(dst) == str(Path(os.path.abspath(src))):
            plan.actions.append(Action(src, src))
            taken.add(dst)
            continue

        if dst in taken or (dst.exists() and not _same_file(src, dst)):
            if conflict == "skip":
                plan.skipped.append((src, f"da co {dst.relative_to(root)}"))
                continue
            if conflict == "fail":
                raise OrganizeError(
                    f"trung ten: {src.name} -> {dst.relative_to(root)} da ton tai.\n"
                    f"  -> Dung --on-conflict suffix de tu them hau to, hoac skip de bo qua."
                )
            dst = naming.with_counter(dst, taken, separator)

        taken.add(dst)
        plan.actions.append(Action(src, dst))

    return plan


def _same_file(a: Path, b: Path) -> bool:
    """Cung mot file tren dia (quan trong tren Windows: ten chi khac hoa/thuong)."""
    try:
        return a.resolve().samefile(b)
    except (OSError, ValueError):
        return False


# --------------------------------------------------------------------------
# Thuc thi
# --------------------------------------------------------------------------

def execute(plan: Plan, journal=None) -> int:
    """Thuc hien ke hoach. Tra ve so file da doi. Ghi nhat ky sau tung buoc."""
    done = 0
    for action in plan.changes:
        action.dst.parent.mkdir(parents=True, exist_ok=True)
        _move(action.src, action.dst)
        if journal is not None:
            journal.record(action)
        done += 1
    return done


def _move(src: Path, dst: Path) -> None:
    if dst.exists() and not _same_file(src, dst):
        raise OrganizeError(f"dich den bi chiem giua chung: {dst}")

    if _same_file(src, dst):
        # Windows khong phan biet hoa/thuong -> phai doi ten qua mot buoc trung gian
        temp = dst.with_name(f".__organize__{dst.name}")
        src.rename(temp)
        temp.rename(dst)
        return

    shutil.move(str(src), str(dst))


def prune_empty_dirs(root: Path) -> list[Path]:
    """Xoa cac thu muc rong con lai sau khi di chuyen. Khong dong vao chinh `root`."""
    removed: list[Path] = []
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and path != root and not any(path.iterdir()):
            path.rmdir()
            removed.append(path)
    return removed
