#!/usr/bin/env python3
"""
server.py - Giao dien web (keo tha file) cho anonymize.py

Chi dung thu vien chuan cua Python, khong can Flask/FastAPI.
Server chi lang nghe tren 127.0.0.1 - khoa trong .env khong bao gio roi khoi may ban.

Chay:  python anonymize.py serve
   hoac  python server.py
"""

from __future__ import annotations

import base64
import io
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import anonymize
from anonymize import AnonymizeError, Anonymizer

HERE = Path(__file__).resolve().parent
WEB_DIR = HERE / "web"
MAX_UPLOAD = 64 * 1024 * 1024  # 64 MB
PREVIEW_CHARS = 2500

# duong dan .env dang duoc dung, do lenh serve() dat
ENV_PATH = anonymize.ENV_FILE_DEFAULT


def _preview(raw: bytes, filename: str) -> str | None:
    """Trich mot doan dau file de hien thi. Tra ve None neu khong phai file van ban."""
    if Path(filename).suffix.lower() in anonymize.XLSX_SUFFIXES:
        return None
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None
    return text[:PREVIEW_CHARS] + ("\n..." if len(text) > PREVIEW_CHARS else "")


def _mapping_csv(anon: Anonymizer) -> str:
    import csv

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(["original", "token"])
    for original, token in sorted(anon.mapping.items()):
        writer.writerow([original, token])
    return buf.getvalue()


def _output_name(name: str, mode: str) -> str:
    p = Path(name)
    return str(anonymize.default_output(p, mode).name)


class Handler(BaseHTTPRequestHandler):
    server_version = "anonymize/1.0"

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
        if "/api/" in (args[0] if args else ""):
            sys.stderr.write(f"  {args[0]} -> {args[1]}\n")

    # -- GET -----------------------------------------------------------
    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/status":
            try:
                anonymize.resolve_key(ENV_PATH)
                self._send_json(200, {"ok": True, "env": str(ENV_PATH)})
            except AnonymizeError as exc:
                self._send_json(200, {"ok": False, "error": str(exc), "env": str(ENV_PATH)})
            return

        rel = "index.html" if path == "/" else path.lstrip("/")
        target = (WEB_DIR / rel).resolve()
        if not str(target).startswith(str(WEB_DIR.resolve())) or not target.is_file():
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
        }.get(target.suffix.lower(), "application/octet-stream")
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
        if mode not in ("encrypt", "decrypt"):
            self._send_json(400, {"ok": False, "error": "mode phai la encrypt hoac decrypt"})
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
            anon = Anonymizer(
                anonymize.resolve_key(ENV_PATH), normalize_phone=flag("normalize")
            )
            out = anonymize.process_bytes(raw, filename, anon, mode, flag("strict"))
        except AnonymizeError as exc:
            self._send_json(200, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:  # loi ngoai du kien -> van tra JSON de UI hien thi
            self._send_json(200, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            return

        payload = {
            "ok": True,
            "mode": mode,
            "filename": _output_name(filename, mode),
            "count": len(anon.mapping),
            "size_in": len(raw),
            "size_out": len(out),
            "before": _preview(raw, filename),
            "after": _preview(out, filename),
            "samples": [
                {"original": o, "token": t} for o, t in list(anon.mapping.items())[:5]
            ],
            "data": base64.b64encode(out).decode("ascii"),
        }
        if mode == "encrypt" and flag("mapping") and anon.mapping:
            payload["mapping"] = base64.b64encode(
                ("﻿" + _mapping_csv(anon)).encode("utf-8")
            ).decode("ascii")
        self._send_json(200, payload)


def serve(port: int = 8765, env_path: str = anonymize.ENV_FILE_DEFAULT, open_browser: bool = True) -> int:
    global ENV_PATH
    ENV_PATH = env_path

    if not WEB_DIR.is_dir():
        raise AnonymizeError(f"Khong tim thay thu muc giao dien: {WEB_DIR}")

    url = f"http://127.0.0.1:{port}/"
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        raise AnonymizeError(
            f"Khong mo duoc cong {port}: {exc}\n  -> Thu doi cong:  python anonymize.py serve --port 8080"
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


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Giao dien web cho anonymize.py")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--env", default=anonymize.ENV_FILE_DEFAULT)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    try:
        sys.exit(serve(a.port, a.env, not a.no_browser))
    except AnonymizeError as exc:
        print(f"Loi: {exc}", file=sys.stderr)
        sys.exit(2)
