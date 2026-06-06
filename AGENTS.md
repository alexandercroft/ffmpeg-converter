# AGENTS.md — install & run protocol for AI assistants

This file tells an AI coding agent how to get this project running on the user's
machine, including installing any missing system dependencies. Follow it top to bottom.

## What this project needs

- **Python 3** — to run `server.py` (uses only the standard library, no pip installs).
- **FFmpeg + ffprobe** — to do the actual conversion.

That's all. There are no Python package dependencies.

## Step 1 — check what's already installed

From the repo root, run:

```bash
./run.sh --check
```

It prints one line per dependency (`OK` / `MISSING`) and exits `0` if everything is
present, non-zero otherwise. Example:

```
OK      python3   /opt/homebrew/bin/python3
MISSING ffmpeg
MISSING ffprobe
```

If every line is `OK`, skip to Step 3.

## Step 2 — install whatever is MISSING

Easiest path — let the launcher do it:

```bash
./run.sh --install
```

This installs missing dependencies using whatever is available, in this order:

- **macOS**: Homebrew (`brew install ffmpeg`); if Homebrew is absent, it downloads a
  static FFmpeg binary into `./bin/` (no system install, no sudo).
- **Linux**: `apt-get` / `dnf` / `pacman` / `zypper` (may prompt for sudo); if none
  exist, it downloads a static binary into `./bin/`.
- **Python 3 missing**: the script prints the exact install command for the OS — run
  that yourself (e.g. macOS `xcode-select --install`, Debian/Ubuntu
  `sudo apt-get install -y python3`), then re-run `./run.sh --install`.

If `--install` can't complete non-interactively (e.g. it needs sudo and you can't
provide it), fall back to installing FFmpeg manually for the user's OS, then verify
with `./run.sh --check` again.

## Step 3 — start it

```bash
./run.sh
```

The server starts at `http://localhost:8000` and the default browser opens. Use
`PORT=8080 ./run.sh` to change the port.

## Verifying it works (optional)

```bash
# create a 2s test clip and convert it to ProRes via the API
ffmpeg -f lavfi -i testsrc=duration=2:size=320x240:rate=30 -y /tmp/_t.mp4
# (server must be running) start a job and poll status:
curl -s -X POST "http://localhost:8000/api/convert?name=_t.mp4&preset=prores" --data-binary @/tmp/_t.mp4
# -> {"job_id":"abc123",...}; then GET /api/status/abc123 until {"status":"done"}
```

A converted file appearing in `./out/` means it works.

## Notes / constraints

- Do **not** add pip dependencies — the project is intentionally stdlib-only.
- Downloaded binaries live in `./bin/` and are git-ignored; don't commit them.
- `./uploads/` and `./out/` are working dirs and git-ignored.
- macOS uses hardware VideoToolbox encoders for H.264/H.265; other OSes use software
  `libx264`/`libx265` automatically — no action needed from you.
