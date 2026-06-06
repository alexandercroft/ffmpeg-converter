# FFMPEG // Converter

A tiny local web app that converts **any** media file into **MOV** (ProRes / H.264 /
H.265) or extracts audio (MP3 / WAV) — with a live "magnetic-tape" progress bar.
Runs at `http://localhost:8000`, drag-and-drop, no cloud, no upload anywhere.

Built on [FFmpeg](https://ffmpeg.org/) + Python standard library. **Zero pip
dependencies.**

```
drag a file  →  pick a format  →  watch the tape fill  →  download
```

---

## Quick start

```bash
git clone https://github.com/alexandercroft/ffmpeg-converter.git
cd ffmpeg-converter
./run.sh
```

`run.sh` checks your dependencies, **installs anything missing automatically**, then
opens the browser. That's it.

On Windows, double-click **`run.bat`** instead.

---

## What you need (and what `run.sh` does if it's missing)

| Dependency | Required | If missing, `run.sh` will… |
|---|---|---|
| **Python 3** | yes (runs the server) | print the one-line install command for your OS |
| **FFmpeg + ffprobe** | yes (does the conversion) | install via Homebrew / apt / dnf / pacman — or, if you have no package manager, **download a static binary into `./bin/`** so nothing system-wide is needed |

You normally don't install anything by hand — just run `./run.sh`.

To only check status (used by AI installers, see below):

```bash
./run.sh --check     # prints OK / MISSING for each dependency, exits 0 if all OK
./run.sh --install   # install missing deps but don't start the server
```

---

## Formats (presets)

| Preset | Codec | Container | Use for |
|---|---|---|---|
| **ProRes 422 HQ** | `prores_ks`, 10-bit, PCM audio | `.mov` | editing (DaVinci / Premiere / FCP) |
| **H.264** | macOS: `h264_videotoolbox` · else `libx264` | `.mov` | delivery / storage |
| **H.265 / HEVC** | macOS: `hevc_videotoolbox` · else `libx265` | `.mov` | smaller files |
| **→ MP3** | `libmp3lame` | `.mp3` | extract audio |
| **→ WAV** | `pcm_s16le` | `.wav` | extract audio, lossless |

Input can be anything FFmpeg reads (mp4, mkv, avi, mov, webm, …). The UI only shows
presets your installed FFmpeg build actually supports.

Converted files land in **`./out/`**.

---

## Platform notes

- **macOS** is the primary target: H.264/H.265 use Apple's hardware **VideoToolbox**
  encoders (fast). This is the recommended platform.
- **Linux / Windows** work too: H.264/H.265 fall back to software `libx264` / `libx265`
  automatically. ProRes / MP3 / WAV work everywhere.

---

## Install via an AI assistant

You can hand this repo's URL to an AI coding agent (Claude Code, etc.) and ask it to
set everything up. See **[AGENTS.md](AGENTS.md)** — it contains a deterministic
install/check protocol the agent should follow (`./run.sh --check` → install missing →
`./run.sh`).

---

## Troubleshooting

- **"FFmpeg not found" after install** — close and reopen the terminal so `PATH`
  refreshes, then `./run.sh` again. The downloaded binary lives in `./bin/`.
- **macOS blocks the downloaded ffmpeg** ("cannot be opened") — `run.sh` already strips
  the quarantine flag; if it persists: `xattr -dr com.apple.quarantine ./bin`.
- **Port 8000 busy** — run on another port: `PORT=8080 ./run.sh`.
- **Static binary won't run on Apple Silicon** — install Rosetta
  (`softwareupdate --install-rosetta`) or just use Homebrew (`brew install ffmpeg`),
  which is the native arm64 build.

---

## How it works

- `server.py` — a stdlib HTTP server. Each conversion runs in a background thread;
  progress is parsed from FFmpeg's own `-progress` stream and exposed at
  `/api/status/<id>`.
- `index.html` — the UI (drag-drop, preset chips, the tape progress bar).
- `run.sh` / `run.bat` — launchers that resolve dependencies first.

Files you upload are stored in `./uploads/` only during conversion and deleted right
after. Nothing leaves your machine.

## License

MIT — see [LICENSE](LICENSE).
