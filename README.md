# 🎵 Lyra 🎵

A Friendly, Colorful Command-Line FrontEnd for [`spotdl`](https://github.com/spotDL/spotify-downloader).

Lyra wraps `spotdl` in a menu-driven interface so
you don't have to remember flags — while still supporting fully scriptable,
non-interactive usage for automation.

## ☄️ How to Install (Easy Way)
1. [Download the latest release.](https://github.com/ErfanNamira/Lyra/releases/latest)
2. Rename the downloaded file to `lyra.exe` (optional, just tidier).
3. In PowerShell, run: `.\lyra-windows-x86_64.exe --setup` (or `.\lyra.exe --setup` if renamed)
4. Run `.\lyra-windows-x86_64.exe` (or `.\lyra.exe`)

## 🌟 Features

- **Interactive menu** — download, batch-download, edit settings, view history, check
  dependencies, all from a single TUI.
- **Persistent config** — your preferred format, threads, lyrics provider, and output
  naming pattern are saved to `~/.config/lyra/config.json`.
- **Batch downloads** — feed Lyra a plain text file with one Spotify URL per line.
- **Download history** — every run is logged to `~/.config/lyra/history.json` with
  timestamp, URL, format, and status.
- **Dependency setup** — one menu option (or `--setup` flag) checks for `spotdl` and
  fetches its bundled `ffmpeg`/`deno` binaries for you.
- **Scriptable CLI mode** — pass URLs and flags directly for cron jobs / automation,
  no prompts required.
- **Single-file executables** — prebuilt binaries for Linux, macOS, and Windows via
  PyInstaller + GitHub Actions (see [Releases](https://github.com/ErfanNamira/Lyra/releases)).

## 🛠️ Requirements

- Python 3.11+
- [`spotdl`](https://pypi.org/project/spotdl/) (installed automatically as a dependency)
- `ffmpeg` and (optionally) `deno` — Lyra can fetch both for you, see below

## 💻 Installation

### ⚙️ Option A: from source

```bash
git clone https://github.com/<your-username>/lyra.git
cd lyra
pip install -r requirements.txt
python lyra.py
```

### ⚙️ Option B: prebuilt binary

Grab the latest single-file executable for your OS from the
[Releases](https://github.com/ErfanNamira/Lyra/releases) page — no Python install required. Then:

```bash
# Linux / macOS
chmod +x lyra-linux-x86_64
./lyra-linux-x86_64 --setup   # fetches ffmpeg + deno the first time

# Windows (PowerShell)
.\lyra-windows-x86_64.exe --setup
```

## 🚀 First-time setup (ffmpeg + deno)

`spotdl` needs `ffmpeg` for audio conversion, and some lyrics/metadata paths
benefit from `deno`. Lyra doesn't bundle these binaries directly inside the
executable (they're large and platform-specific) — instead it asks `spotdl`
to fetch and manage them for you, the same way it would if you'd installed
`spotdl` yourself:

```bash
lyra --setup          # interactive confirmation for each tool
lyra --setup --yes    # non-interactive, installs both without prompting
```

Under the hood this simply runs:

```bash
spotdl --download-ffmpeg
spotdl --download-deno
```

You can also trigger this from the interactive menu (option **6**).

## Usage

### 🧙‍♂️ Interactive mode

Just run it with no arguments:

```bash
python lyra.py
```

```
Main Menu
  1 Download a track / playlist / album
  2 Batch download from a text file (one URL per line)
  3 Edit settings
  4 View current settings
  5 View download history
  6 Check / install dependencies (spotdl, ffmpeg, deno)
  7 Reset settings to default
  8 Exit
```

### ⌨️ Non-interactive / scripted mode

```bash
# Single track, using your saved defaults
lyra.py "https://open.spotify.com/track/XXXXXXXXXXXX"

# Multiple URLs, format override
lyra.py URL1 URL2 --format flac --lyrics genius

# Batch file (one URL per line, '#' comments allowed)
lyra.py --batch playlists.txt

# Print recent history
lyra.py --history

# Print version
lyra.py --version
```

⚡ Available CLI flags:

| Flag | Description |
|---|---|
| `urls` (positional) | One or more Spotify track/playlist/album URLs |
| `--batch FILE` | Text file with one URL per line |
| `--format {mp3,flac,ogg,opus,m4a,wav}` | Audio format override |
| `--lyrics {synced,genius,musixmatch,azlyrics,none}` | Lyrics provider override |
| `--threads N` | Thread count override |
| `--output PATTERN` | Output naming pattern override |
| `--generate-lrc` / `--no-generate-lrc` | Force synced `.lrc` generation on/off |
| `--setup` | Check/install `spotdl`, `ffmpeg`, `deno`, then exit |
| `--yes`, `-y` | Assume yes for setup prompts |
| `--history` | Print recent download history and exit |
| `--version` | Print version and exit |

## 🧪 Configuration file

Located at `~/.config/lyra/config.json`:

```json
{
    "threads": 12,
    "yt_dlp_args": "--sleep-interval 1 --max-sleep-interval 2",
    "format": "opus",
    "lyrics": "synced",
    "generate_lrc": true,
    "output": "{artists} - {title} - {year}.{output-ext}"
}
```

Edit it directly, or use menu option **3** / the CLI override flags.

## 📦 Building a single-file executable yourself

```bash
pip install -r requirements-build.txt
pyinstaller lyra.spec --noconfirm --clean
# binary is at dist/lyra (or dist/lyra.exe on Windows)
```

## 📄 License

MIT — see [`LICENSE`](LICENSE).

## ⚠️ Disclaimer

Lyra is a UI/automation layer over `spotdl`. Only use it to download content you
have the rights to download, in accordance with YouTube and Spotify's Terms of Service and
applicable copyright law in your jurisdiction.
