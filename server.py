#!/usr/bin/env python3
"""FFMPEG — локальный конвертер видео в MOV (+ извлечение аудио).

Запуск:  python3 server.py   (или ./run.sh)
Открыть: http://localhost:8000

Без внешних зависимостей — только стандартная библиотека Python.
Каждый файл конвертируется в фоновом потоке; прогресс читается из самого
FFmpeg (-progress) и отдаётся в UI через /api/status, как «лента».

Кодеры выбираются под платформу:
  • macOS  — аппаратные h264_videotoolbox / hevc_videotoolbox (быстро);
  • прочее — софтовые libx264 / libx265.
ProRes (prores_ks), MP3 (libmp3lame) и WAV (pcm) работают везде.
FFmpeg ищется сначала в ./bin, затем в PATH.
"""

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOADS = os.path.join(ROOT, "uploads")
OUT = os.path.join(ROOT, "out")
PORT = int(os.environ.get("PORT", 8000))
IS_MAC = platform.system() == "Darwin"
IS_WIN = os.name == "nt"

JOBS = {}          # job_id -> dict
JOBS_LOCK = threading.Lock()


def resolve_bin(name):
    """Бинарник из ./bin (приоритет), иначе из PATH."""
    exe = name + (".exe" if IS_WIN else "")
    local = os.path.join(ROOT, "bin", exe)
    if os.path.isfile(local):
        return local
    return shutil.which(name)


FFMPEG = resolve_bin("ffmpeg")
FFPROBE = resolve_bin("ffprobe")


def available_encoders():
    if not FFMPEG:
        return set()
    try:
        out = subprocess.run([FFMPEG, "-hide_banner", "-encoders"],
                             capture_output=True, text=True).stdout
        return set(re.findall(r"^\s*[A-Z.]{6}\s+(\S+)", out, re.M))
    except OSError:
        return set()


ENC = available_encoders()


def _aac():
    return ["-c:a", "aac", "-b:a", "256k"]   # нативный aac есть в любой сборке


def _h264():
    if IS_MAC and "h264_videotoolbox" in ENC:
        return ["-c:v", "h264_videotoolbox", "-b:v", "12M", "-tag:v", "avc1"]
    if "libx264" in ENC:
        return ["-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-pix_fmt", "yuv420p", "-tag:v", "avc1"]
    return None


def _hevc():
    if IS_MAC and "hevc_videotoolbox" in ENC:
        return ["-c:v", "hevc_videotoolbox", "-b:v", "8M", "-tag:v", "hvc1"]
    if "libx265" in ENC:
        return ["-c:v", "libx265", "-preset", "medium", "-crf", "24",
                "-tag:v", "hvc1"]
    return None


def build_presets():
    p = {
        "prores": ("ProRes 422 HQ", ".mov",
            ["-c:v", "prores_ks", "-profile:v", "3", "-vendor", "apl0",
             "-pix_fmt", "yuv422p10le", "-c:a", "pcm_s16le"]),
        "mp3": ("Audio MP3", ".mp3", ["-vn", "-c:a", "libmp3lame", "-q:a", "2"]),
        "wav": ("Audio WAV", ".wav", ["-vn", "-c:a", "pcm_s16le"]),
    }
    h264, hevc = _h264(), _hevc()
    if h264:
        p["h264"] = ("H.264", ".mov", h264 + _aac() + ["-movflags", "+faststart"])
    if hevc:
        p["hevc"] = ("H.265 HEVC", ".mov", hevc + _aac() + ["-movflags", "+faststart"])
    return p


PRESETS = build_presets()


def human_size(n):
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if n < 1024 or unit == "ГБ":
            return f"{n:.0f} {unit}" if unit == "Б" else f"{n:.1f} {unit}"
        n /= 1024


def probe_duration(path):
    """Длительность входа в секундах (или None)."""
    if not FFPROBE:
        return None
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nk=1:nw=1", path],
            capture_output=True, text=True).stdout.strip()
        d = float(out)
        return d if d > 0 else None
    except (ValueError, OSError):
        return None


def run_job(job_id, in_path, preset):
    label, ext, args = PRESETS[preset]
    stem = os.path.splitext(os.path.basename(in_path))[0]
    out_name = f"{stem}_{preset}{ext}"
    out_path = os.path.join(OUT, out_name)
    duration = probe_duration(in_path)

    cmd = [FFMPEG, "-y", "-i", in_path, "-progress", "pipe:1", "-nostats",
           *args, out_path]
    errfile = tempfile.TemporaryFile(mode="w+")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errfile, text=True)

    time_re = re.compile(r"^out_time_us=(\d+)")
    for line in proc.stdout:
        m = time_re.match(line.strip())
        if m and duration:
            done = int(m.group(1)) / 1_000_000 / duration * 100
            pct = max(0, min(99, int(done)))
            with JOBS_LOCK:
                JOBS[job_id]["progress"] = pct
    proc.wait()

    with JOBS_LOCK:
        job = JOBS[job_id]
        if proc.returncode == 0 and os.path.isfile(out_path):
            job.update(status="done", progress=100, output=out_name,
                       size=human_size(os.path.getsize(out_path)),
                       url="/download?file=" + urllib.parse.quote(out_name))
        else:
            errfile.seek(0)
            tail = "\n".join(errfile.read().strip().splitlines()[-3:])
            job.update(status="error", error=tail or "ошибка ffmpeg")
    errfile.close()
    try:
        os.remove(in_path)
    except OSError:
        pass


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            with open(os.path.join(ROOT, "index.html"), "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/presets":
            self._json(200, {k: v[0] for k, v in PRESETS.items()})
        elif path.startswith("/api/status/"):
            jid = path.rsplit("/", 1)[-1]
            with JOBS_LOCK:
                job = JOBS.get(jid)
                self._json(200, dict(job) if job else {"status": "error", "error": "no job"})
        elif path == "/download":
            self._download()
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/convert":
            self._convert()
        elif path == "/api/reveal":
            self._reveal()
        else:
            self._json(404, {"error": "not found"})

    def _download(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = os.path.basename(qs.get("file", [""])[0])
        fp = os.path.join(OUT, name)
        if not name or not os.path.isfile(fp):
            self._json(404, {"error": "file not found"})
            return
        with open(fp, "rb") as f:
            data = f.read()
        disp = "attachment; filename*=UTF-8''" + urllib.parse.quote(name)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", disp)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _reveal(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or "{}")
        name = os.path.basename(body.get("output", ""))
        fp = os.path.join(OUT, name)
        has_file = bool(name) and os.path.isfile(fp)
        try:
            if IS_MAC:
                subprocess.run(["open", "-R", fp] if has_file else ["open", OUT])
            elif IS_WIN:
                os.startfile(OUT)  # noqa: F821
            else:
                subprocess.run(["xdg-open", OUT])
        except OSError:
            pass
        self._json(200, {"ok": True})

    def _convert(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = os.path.basename(qs.get("name", [""])[0])
        preset = qs.get("preset", [""])[0]
        if preset not in PRESETS:
            self._json(400, {"error": f"пресет '{preset}' недоступен в этой сборке ffmpeg"})
            return
        if not name:
            self._json(400, {"error": "нет имени файла"})
            return
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            self._json(400, {"error": "пустой файл"})
            return

        in_path = os.path.join(UPLOADS, name)
        with open(in_path, "wb") as f:
            remaining = length
            while remaining > 0:
                chunk = self.rfile.read(min(1 << 20, remaining))
                if not chunk:
                    break
                f.write(chunk)
                remaining -= len(chunk)

        job_id = uuid.uuid4().hex[:6]
        with JOBS_LOCK:
            JOBS[job_id] = {"status": "working", "progress": None,
                            "name": name, "preset": preset,
                            "label": PRESETS[preset][0]}
        threading.Thread(target=run_job, args=(job_id, in_path, preset),
                         daemon=True).start()
        self._json(200, {"job_id": job_id, "preset": preset,
                         "label": PRESETS[preset][0]})


def main():
    os.makedirs(UPLOADS, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    if not FFMPEG:
        sys.exit("FFmpeg не найден. Запусти ./run.sh — он доустановит, "
                 "или поставь вручную (brew install ffmpeg).")
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"\n  FFMPEG // CONVERTER  ->  http://localhost:{PORT}")
    print(f"  ffmpeg: {FFMPEG}")
    print(f"  presets: {', '.join(PRESETS)}")
    print(f"  output: {OUT}")
    print("  Ctrl+C - stop\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")


if __name__ == "__main__":
    main()
