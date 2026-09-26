"""
tools/organize/journal.py - Nhat ky thao tac va hoan tac.

Moi lan chay ghi mot phien vao file JSONL. Ghi NGAY SAU tung buoc thanh cong,
nen du chuong trinh dut giua chung van hoan tac duoc phan da lam.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .core import Action, OrganizeError

JOURNAL_NAME = ".organize-journal.jsonl"


class Journal:
    """Ghi nhat ky. Dung nhu context manager de tu dong dong file."""

    def __init__(self, path: Path, command: str = ""):
        self.path = path
        self.command = command
        self._fh = None
        self.session = datetime.now().isoformat(timespec="seconds")

    def __enter__(self) -> Journal:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8", newline="\n")
        self._write({"type": "session", "at": self.session, "command": self.command})
        return self

    def __exit__(self, *exc) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None

    def _write(self, row: dict) -> None:
        if self._fh is None:
            raise OrganizeError("nhat ky chua duoc mo")
        self._fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._fh.flush()

    def record(self, action: Action) -> None:
        self._write(
            {"type": "move", "at": self.session, "src": str(action.src), "dst": str(action.dst)}
        )


def read_sessions(path: Path) -> list[tuple[str, str, list[tuple[Path, Path]]]]:
    """Doc nhat ky -> [(thoi diem, lenh, [(src, dst), ...]), ...] theo thu tu thoi gian."""
    if not path.is_file():
        raise OrganizeError(
            f"Khong tim thay nhat ky: {path}\n"
            f"  -> Chi hoan tac duoc thao tac da chay voi --apply."
        )
    sessions: dict[str, list[tuple[Path, Path]]] = {}
    commands: dict[str, str] = {}
    order: list[str] = []

    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise OrganizeError(f"nhat ky hong o dong {line_no}: {exc}") from exc
        at = row.get("at", "?")
        if at not in sessions:
            sessions[at] = []
            order.append(at)
        if row.get("type") == "session":
            commands[at] = row.get("command", "")
        elif row.get("type") == "move":
            sessions[at].append((Path(row["src"]), Path(row["dst"])))

    return [(at, commands.get(at, ""), sessions[at]) for at in order]


def undo_last(path: Path, dry_run: bool = True) -> tuple[str, list[tuple[Path, Path]], list[str]]:
    """
    Hoan tac phien gan nhat: tra file ve cho cu, theo thu tu nguoc.

    Tra ve (thoi diem, cac cap se khoi phuc, canh bao).
    """
    sessions = [s for s in read_sessions(path) if s[2]]
    if not sessions:
        raise OrganizeError(f"Nhat ky {path} chua ghi thao tac nao.")

    at, _command, moves = sessions[-1]
    restored: list[tuple[Path, Path]] = []
    warnings: list[str] = []

    for src, dst in reversed(moves):
        if not dst.exists():
            warnings.append(f"khong con {dst} - da bi xoa hoac doi ten tiep")
            continue
        if src.exists() and not dst.samefile(src):
            warnings.append(f"cho cu da bi chiem: {src}")
            continue
        restored.append((dst, src))
        if not dry_run:
            src.parent.mkdir(parents=True, exist_ok=True)
            dst.rename(src)

    if not dry_run and restored:
        _drop_session(path, at)
    return at, restored, warnings


def _drop_session(path: Path, at: str) -> None:
    """Bo phien da hoan tac khoi nhat ky de lan undo sau lui tiep mot buoc."""
    kept = [
        line for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("at") != at
    ]
    path.write_text("".join(line + "\n" for line in kept), encoding="utf-8")
