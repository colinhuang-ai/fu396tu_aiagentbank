"""
tools/server.py - Giao dien web (keo tha file).

Chi dung thu vien chuan cua Python, khong can Flask/FastAPI.
Server chi lang nghe tren 127.0.0.1 - khoa trong .env khong bao gio roi khoi may ban.

Chay:  python anonymize.py serve
"""

from __future__ import annotations

import base64
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .core import ENV_FILE_DEFAULT, AnonymizeError, Cipher, resolve_key
from .fileio import MODES, default_output, mapping_csv, process_bytes
from .handlers import KIND_AUTO, KIND_CHOICES, describe, get_handler

# Giao dien nam ngay trong package -> tool tu chua, di chuyen di dau cung chay duoc
WEB_DIR = Path(__file__).resolve().parent / "web"
MAX_UPLOAD = 64 * 1024 * 1024  # 64 MB
PREVIEW_CHARS = 2500

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
}

# duong dan .env dang duoc dung, do serve() dat
ENV_PATH: str = ENV_FILE_DEFAULT


def _clip(text: str | None) -> str | None:
    if text is None:
        return None
    return text[:PREVIEW_CHARS] + ("\n..." if len(text) > PREVIEW_CHARS else "")


class Handler(BaseHTTPRequestHandler):
    server_version = "anonymize/2.0"

    # -- tien ich ------------------------------------------------------
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def log_message(self, fmt: str, *args) -> None:  # bot log mac dinh cho gon
        if args and "/api/" in str(args[0]):
            sys.stderr.write(f"  {args[0]} -> {args[1]}\n")

    # -- GET -----------------------------------------------------------
    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/status":
            try:
                resolve_key(ENV_PATH)
                self._send_json(200, {"ok": True, "env": str(ENV_PATH), "kinds": describe()})
            except AnonymizeError as exc:
                self._send_json(
                    200, {"ok": False, "error": str(exc), "env": str(ENV_PATH), "kinds": describe()}
                )
            return

        rel = "index.html" if path == "/" else path.lstrip("/")
        target = (WEB_DIR / rel).resolve()
        if not target.is_relative_to(WEB_DIR.resolve()) or not target.is_file():
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        ctype = CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream")
        self._send(200, target.read_bytes(), ctype)

    # -- POST ----------------------------------------------------------
    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/process":
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return

        query = parse_qs(parsed.query)

        def flag(name: str) -> bool:
            return query.get(name, ["0"])[0] == "1"

        mode = query.get("mode", ["encrypt"])[0]
        if mode not in MODES:
            self._send_json(400, {"ok": False, "error": "mode phai la encrypt hoac decrypt"})
            return
        kind = query.get("kind", [KIND_AUTO])[0]
        if kind not in KIND_CHOICES:
            self._send_json(400, {"ok": False, "error": f"kind khong hop le: {kind}"})
            return
        filename = unquote(query.get("name", ["data.txt"])[0]) or "data.txt"

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            self._send_json(400, {"ok": False, "error": "Khong nhan duoc noi dung file"})
            return
        if length > MAX_UPLOAD:
            self._send_json(
                413, {"ok": False, "error": f"File qua lon (toi da {MAX_UPLOAD // 1024 // 1024} MB)"}
            )
            return
        raw = self.rfile.read(length)

        try:
            cipher = Cipher(
                resolve_key(ENV_PATH),
                normalize_phone=flag("normalize"),
                mask_mentions=flag("mask"),
            )
            in_handler = get_handler(filename, raw, kind)
            out = process_bytes(raw, filename, cipher, mode, flag("strict"), kind)
        except AnonymizeError as exc:
            self._send_json(200, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:  # loi ngoai du kien -> van tra JSON de UI hien thi
            self._send_json(200, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            return

        out_name = default_output(Path(filename), mode, kind, raw).name
        payload = {
            "ok": True,
            "mode": mode,
            "kind": in_handler.name,
            "kind_label": in_handler.label,
            "filename": out_name,
            "count": len(cipher.mapping),
            "size_in": len(raw),
            "size_out": len(out),
            "before": _clip(in_handler.preview(raw)),
            "after": _clip(get_handler(out_name, out, KIND_AUTO).preview(out)),
            "samples": [{"original": o, "token": t} for o, t in list(cipher.mapping.items())[:5]],
            "data": base64.b64encode(out).decode("ascii"),
        }
        if mode == "encrypt" and flag("mapping") and cipher.mapping:
            payload["mapping"] = base64.b64encode(
                mapping_csv(cipher, bom=True).encode("utf-8")
            ).decode("ascii")
        self._send_json(200, payload)


def serve(port: int = 8765, env_path: str = ENV_FILE_DEFAULT, open_browser: bool = True) -> int:
    global ENV_PATH
    ENV_PATH = env_path

    if not WEB_DIR.is_dir():
        raise AnonymizeError(f"Khong tim thay thu muc giao dien: {WEB_DIR}")

    url = f"http://127.0.0.1:{port}/"
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        raise AnonymizeError(
            f"Khong mo duoc cong {port}: {exc}\n"
            f"  -> Thu doi cong:  python anonymize.py serve --port 8080"
        ) from exc

    print(f"Giao dien web dang chay tai:  {url}")
    print(f"  File khoa: {env_path}")
    print("  Nhan Ctrl+C de dung.")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nDa dung server.")
    finally:
        httpd.server_close()
    return 0
