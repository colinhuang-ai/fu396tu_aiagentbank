"""
tools/handlers/transcript.py - Bien ban / phu de cuoc hop (.vtt, .srt, .txt).

Khac voi van ban thuong: trong transcript thi TEN NGUOI NOI moi la thong tin nhay cam
chinh, chu khong phai email. Handler nay ma hoa them:

    Nguyen Van A: xin chao        ->  enc1n<token>: xin chao
    [00:12] Tran Thi B: vang      ->  [00:12] enc1n<token>: vang
    <v Le Van C>noi gi do</v>     ->  <v enc1n<token>>noi gi do</v>

Moc thoi gian, so thu tu cue va noi dung thoai duoc giu nguyen.
Email / so dien thoai trong loi thoai van duoc xu ly nhu binh thuong.
"""

from __future__ import annotations

import re

from ..core import Cipher
from ..encrypt import encrypt_name, looks_like_person
from .base import TextHandler, transform_text

# Dang 1:  "Nguyen Van A: xin chao"  /  "[00:12] Tran Thi B: vang"
SPEAKER_RE = re.compile(
    r"^(?P<lead>[ \t]*(?:[\[(]\s*\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?\s*[\])]\s*)?)"
    r"(?P<name>[^\s:<>\[\](){}][^:\n<>]{0,48}?)"
    r"(?P<tail>:[ \t])",
    re.MULTILINE,
)

# Dang 2:  "0:01 - Nika@MARIO"  - ten chiem tron dong sau moc thoi gian
# (ban xuat cua Google Meet, Otter, Teams). Khong co dau hai cham nen dang 1 khong bat duoc.
# (?!->) de khong an nham dong moc thoi gian cua SRT/VTT: "00:00:01.000 --> 00:00:04.500".
# `\r` phai nam trong `tail`, khong duoc lot vao `name` - neu khong, file CRLF
# se bi mat ky tu `\r` o moi dong nguoi noi.
SPEAKER_LINE_RE = re.compile(
    r"^(?P<lead>[ \t]*\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?[ \t]*[-–—](?!->)[ \t]*)"
    r"(?P<name>\S[^\r\n]{0,58}?)"
    r"(?P<tail>[ \t]*\r?)$",
    re.MULTILINE,
)

# The <v Speaker> cua chuan WebVTT
VOICE_RE = re.compile(r"(?P<lead><v(?:\.[\w.-]+)*\s+)(?P<name>[^>]+?)(?P<tail>>)")

# Nhung tu khoa dung dau dong nhung KHONG phai ten nguoi
METADATA_KEYS = frozenset({
    "webvtt", "note", "region", "style", "cue", "chapter",
    "date", "time", "duration", "meeting", "subject", "title", "topic",
    "attendees", "participants", "present", "apologies", "location", "room",
    "recording", "transcript", "agenda", "action", "actions", "decision",
    "decisions", "notes", "summary", "next steps", "organizer", "host",
    "ngay", "gio", "thoi gian", "chu de", "dia diem", "thanh phan",
    "tham du", "noi dung", "ket luan", "ghi chu", "nguoi chu tri",
})


def looks_like_speaker(name: str) -> bool:
    """Ten dung truoc dau hai cham - phai chat, vi dong nao cung co the co dau hai cham."""
    cleaned = name.strip()
    return cleaned.lower() not in METADATA_KEYS and looks_like_person(cleaned)


def looks_like_label(name: str) -> bool:
    """
    Ten chiem tron dong sau moc thoi gian - chi can noi long.

    O day khong the nham lan voi noi dung khac, nen chap nhan ca dang
    "Nika@MARIO" hay "SPH Student Supp. Serv." ma looks_like_person() se tu choi.
    """
    cleaned = name.strip()
    if not cleaned or len(cleaned) > 60 or cleaned.lower() in METADATA_KEYS:
        return False
    return bool(re.search(r"[^\W\d_]", cleaned))   # phai co it nhat mot chu cai


def is_transcript(text: str) -> bool:
    """Doan xem mot file van ban co phai transcript khong (dung cho che do tu dong)."""
    head = text[:8000]
    if head.lstrip().upper().startswith("WEBVTT") or VOICE_RE.search(head):
        return True
    lines = [line for line in head.splitlines() if line.strip()]
    if len(lines) < 6:
        return False
    speakers = sum(
        1 for line in lines
        if ((m := SPEAKER_RE.match(line)) and looks_like_speaker(m.group("name")))
        or ((m := SPEAKER_LINE_RE.match(line)) and looks_like_label(m.group("name")))
    )
    return speakers >= 3 and speakers / len(lines) >= 0.2


# Tu khong duoc coi la ten rieng du xuat hien trong nhan nguoi noi
# (vd: "Unidentified Speaker" -> khong duoc che chu "Speaker" o khap noi)
NOT_A_NAME = frozenset({
    "speaker", "unidentified", "unknown", "guest", "host", "user", "admin",
    "student", "students", "teacher", "teachers", "parent", "staff", "support",
    "service", "services", "team", "group", "meeting", "participant", "attendee",
    "the", "and", "all", "everyone", "anonymous",
    "hoc", "sinh", "giao", "vien", "phu", "huynh", "khach", "moi", "nguoi",
})


def mention_candidates(speakers: list[str]) -> list[str]:
    """
    Tu danh sach nhan nguoi noi, dung ra cac chuoi can che khi duoc nhac trong loi thoai.

    Luon lay ca nhan day du. Rieng tung tu chi lay khi nhan trong giong mot ten
    nguoi that (2-3 tu, viet hoa, toan chu cai) - de khong che nham nhung tu chung
    nhu "Speaker" trong "Unidentified Speaker".
    """
    out: set[str] = set()
    for label in speakers:
        out.add(label)
        parts = label.split("@")[0].split() if "@" in label else label.split()
        if "@" in label:
            out.update(p for p in parts if len(p) >= 3 and p.isalpha())
            continue
        if not (2 <= len(parts) <= 3):
            continue
        if not all(p[:1].isupper() and p.replace("'", "").replace("’", "").isalpha()
                   for p in parts):
            continue
        out.update(p for p in parts if len(p) >= 3 and p.lower() not in NOT_A_NAME)
    # Chuoi dai truoc de "Colin Huang" duoc khop tron ven thay vi bi cat thanh "Colin"
    return sorted(out, key=len, reverse=True)


def mask_mentions(text: str, cipher: Cipher, speakers: list[str]) -> str:
    """Che cac lan ten nguoi noi duoc nhac den ngay trong loi thoai."""
    candidates = mention_candidates(speakers)
    if not candidates:
        return text
    pattern = re.compile(r"(?<![\w@])(" + "|".join(re.escape(c) for c in candidates) + r")\b")
    return pattern.sub(lambda m: encrypt_name(cipher, m.group(1)), text)


class TranscriptHandler(TextHandler):
    name = "transcript"
    label = "Bien ban / phu de cuoc hop"
    suffixes = (".vtt", ".srt", ".sbv")

    def transform(self, text: str, cipher: Cipher, mode: str, strict: bool) -> str:
        if mode == "encrypt":
            speakers: list[str] = []
            for pattern, accept in (
                (VOICE_RE, looks_like_speaker),
                (SPEAKER_LINE_RE, looks_like_label),
                (SPEAKER_RE, looks_like_speaker),
            ):
                text = pattern.sub(lambda m: self._sub(m, cipher, accept, speakers), text)
            if cipher.mask_mentions:
                text = mask_mentions(text, cipher, speakers)
        # Chieu giai ma: decrypt_text tu nhan ra moi token, khong can biet cau truc.
        return transform_text(text, cipher, mode, strict)

    @staticmethod
    def _sub(m: re.Match[str], cipher: Cipher, accept, speakers: list[str]) -> str:
        """Chi thay phan ten; moi ky tu khac trong doan khop deu duoc tra lai nguyen ven."""
        name = m.group("name")
        if not accept(name):
            return m.group(0)
        core = name.strip()
        speakers.append(core)
        left = name[: len(name) - len(name.lstrip())]
        right = name[len(name.rstrip()):]
        return (
            f"{m.group('lead')}{left}{encrypt_name(cipher, core)}{right}{m.group('tail')}"
        )
