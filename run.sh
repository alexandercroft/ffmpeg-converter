#!/usr/bin/env bash
# FFMPEG converter — self-healing launcher.
#   ./run.sh           check deps, install what's missing, start the server
#   ./run.sh --check    print dependency status (machine-readable) and exit
#   ./run.sh --install  only install missing deps, don't start
#
# Missing FFmpeg is resolved automatically: Homebrew/apt/dnf/pacman if present,
# otherwise a static binary is downloaded into ./bin (no system install needed).
set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"
BIN="$ROOT/bin"
OS="$(uname -s)"
ARCH="$(uname -m)"
PORT="${PORT:-8000}"

# --- colors (no-op if not a tty) ---
if [ -t 1 ]; then R=$'\033[0;31m'; G=$'\033[0;32m'; D=$'\033[2m'; B=$'\033[1m'; X=$'\033[0m'
else R=; G=; D=; B=; X=; fi

have(){ command -v "$1" >/dev/null 2>&1; }
ffmpeg_path(){ if [ -x "$BIN/ffmpeg" ]; then echo "$BIN/ffmpeg"; elif have ffmpeg; then command -v ffmpeg; fi; }
ffprobe_path(){ if [ -x "$BIN/ffprobe" ]; then echo "$BIN/ffprobe"; elif have ffprobe; then command -v ffprobe; fi; }
python_path(){ if have python3; then command -v python3; elif have python; then command -v python; fi; }
openurl(){ case "$OS" in Darwin) open "$1";; Linux) xdg-open "$1" >/dev/null 2>&1 || true;; esac; }

# ---------- dependency status ----------
do_check(){
  local ok=0 p f pr
  p="$(python_path)"; f="$(ffmpeg_path)"; pr="$(ffprobe_path)"
  if [ -n "$p" ]; then echo "${G}OK${X}      python3   $p"; else echo "${R}MISSING${X} python3"; ok=1; fi
  if [ -n "$f" ]; then echo "${G}OK${X}      ffmpeg    $f"; else echo "${R}MISSING${X} ffmpeg"; ok=1; fi
  if [ -n "$pr" ]; then echo "${G}OK${X}      ffprobe   $pr"; else echo "${R}MISSING${X} ffprobe"; ok=1; fi
  return $ok
}

# ---------- static binary fallback ----------
download_static_mac(){
  mkdir -p "$BIN"; local tmp; tmp="$(mktemp -d)"
  echo "  ${D}downloading static ffmpeg + ffprobe (evermeet.cx)…${X}"
  curl -fL "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip"  -o "$tmp/ffmpeg.zip"
  curl -fL "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip" -o "$tmp/ffprobe.zip"
  unzip -o -q "$tmp/ffmpeg.zip"  -d "$BIN"
  unzip -o -q "$tmp/ffprobe.zip" -d "$BIN"
  chmod +x "$BIN/ffmpeg" "$BIN/ffprobe"
  xattr -dr com.apple.quarantine "$BIN" 2>/dev/null || true
  rm -rf "$tmp"
}
download_static_linux(){
  mkdir -p "$BIN"; local tmp a url d; tmp="$(mktemp -d)"
  case "$ARCH" in x86_64) a=amd64;; aarch64|arm64) a=arm64;; armv7l) a=armhf;; *) a=amd64;; esac
  url="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-${a}-static.tar.xz"
  echo "  ${D}downloading static ffmpeg ($a)…${X}"
  curl -fL "$url" -o "$tmp/ff.tar.xz"
  tar -xJf "$tmp/ff.tar.xz" -C "$tmp"
  d="$(find "$tmp" -maxdepth 1 -type d -name 'ffmpeg-*' | head -1)"
  cp "$d/ffmpeg" "$d/ffprobe" "$BIN/"; chmod +x "$BIN/ffmpeg" "$BIN/ffprobe"
  rm -rf "$tmp"
}

install_ffmpeg(){
  echo "${B}FFmpeg not found — installing…${X}"
  case "$OS" in
    Darwin)
      if have brew; then brew install ffmpeg; else download_static_mac; fi ;;
    Linux)
      if   have apt-get; then sudo apt-get update && sudo apt-get install -y ffmpeg
      elif have dnf;     then sudo dnf install -y ffmpeg
      elif have pacman;  then sudo pacman -S --noconfirm ffmpeg
      elif have zypper;  then sudo zypper install -y ffmpeg
      else download_static_linux; fi ;;
    *) echo "${R}Auto-install not supported on $OS. Install ffmpeg manually, then re-run.${X}"; exit 1 ;;
  esac
}

ensure_python(){
  if [ -z "$(python_path)" ]; then
    echo "${R}Python 3 not found.${X}"
    case "$OS" in
      Darwin) echo "  Install:  xcode-select --install   ${D}(or: brew install python)${X}" ;;
      Linux)  echo "  Install:  sudo apt-get install -y python3   ${D}(or your distro's package)${X}" ;;
      *)      echo "  Install Python 3 from https://www.python.org/downloads/" ;;
    esac
    exit 1
  fi
}

ensure_ffmpeg(){
  if [ -z "$(ffmpeg_path)" ] || [ -z "$(ffprobe_path)" ]; then
    install_ffmpeg
  fi
  if [ -z "$(ffmpeg_path)" ]; then
    echo "${R}ffmpeg still missing after install. See README.md → Troubleshooting.${X}"
    exit 1
  fi
}

# ---------- modes ----------
case "${1:-}" in
  --check|check) do_check; exit $? ;;
  --install)     ensure_python; ensure_ffmpeg; echo "${G}All dependencies ready.${X}"; exit 0 ;;
esac

ensure_python
ensure_ffmpeg
PY="$(python_path)"

# ---------- banner ----------
echo ""
echo "  ${R}■${X} ${B}SYS/ONLINE${X}  ${D}LOCAL · 127.0.0.1:${PORT}${X}"
echo "  ${B}FFMPEG${X}${R}.${X}  ${D}UNIVERSAL FORMAT CONVERTER${X}"
echo "  ${D}─────────────────────────────────────────${X}"
echo "  open    →  ${B}http://localhost:${PORT}${X}"
echo "  ffmpeg  →  ${D}$(ffmpeg_path)${X}"
echo "  output  →  ${D}$ROOT/out${X}"
echo "  stop    →  ${D}Ctrl+C${X}"
echo ""

( sleep 1; openurl "http://localhost:${PORT}" ) &
PATH="$BIN:$PATH" PORT="$PORT" exec "$PY" server.py
