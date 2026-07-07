#!/usr/bin/env python3
"""
Lyra - A friendly command-line frontend for spotdl
Requires: pip install spotdl rich

Lyra can be used interactively (just run it with no arguments) or
non-interactively for scripting:

    lyra.py "https://open.spotify.com/track/..." --format flac
    lyra.py "https://open.spotify.com/playlist/..." --download-path D:/Music
    lyra.py --batch urls.txt
    lyra.py --setup

Downloads are auto-organized under the chosen download path (default: the
current working directory): single tracks go in a "Singles" subfolder,
playlists and albums each get their own subfolder named after them.

Run `lyra.py --help` for the full list of CLI options.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

VERSION = "1.0.0"

CONFIG_DIR = Path.home() / ".config" / "lyra"
CONFIG_PATH = CONFIG_DIR / "config.json"
HISTORY_PATH = CONFIG_DIR / "history.json"
LOG_PATH = CONFIG_DIR / "lyra.log"

console = Console()

DEFAULTS = {
    "threads": 12,
    "yt_dlp_args": "--sleep-interval 1 --max-sleep-interval 2",
    "format": "opus",
    "lyrics": "synced",
    "generate_lrc": True,
    "output": "{artists} - {title} - {year}.{output-ext}",
    # Empty string means "use the current working directory at run time",
    # rather than freezing whatever directory happened to be current when
    # the setting was saved.
    "download_path": "",
}

SINGLES_SUBFOLDER = "Singles"
LIST_SUBFOLDER = "{list-name}"

FORMAT_CHOICES = ["mp3", "flac", "ogg", "opus", "m4a", "wav"]
LYRICS_CHOICES = ["synced", "genius", "musixmatch", "azlyrics", "none"]

MAX_HISTORY_ENTRIES = 500


# --------------------------------------------------------------------------- #
# Config handling
# --------------------------------------------------------------------------- #

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = DEFAULTS.copy()
            merged.update(data)
            return merged
        except (json.JSONDecodeError, OSError):
            console.print("[yellow]⚠ Config file corrupted, using defaults.[/]")
            return DEFAULTS.copy()
    return DEFAULTS.copy()


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)


# --------------------------------------------------------------------------- #
# History handling
# --------------------------------------------------------------------------- #

def load_history() -> list:
    if HISTORY_PATH.exists():
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def append_history(entry: dict) -> None:
    history = load_history()
    history.append(entry)
    history = history[-MAX_HISTORY_ENTRIES:]
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except OSError:
        pass


def log(message: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# UI helpers
# --------------------------------------------------------------------------- #

def banner():
    text = Text(justify="center")
    text.append("🎵  ", style="bold magenta")
    text.append("LYRA", style="bold yellow")
    text.append("  🎵\n", style="bold magenta")
    text.append("🎧  ", style="bold magenta")
    text.append("Summoning Songs from Spotify", style="italic cyan")
    text.append("  🎧\n", style="bold magenta")
    text.append("✨ ", style="bold magenta")
    text.append("SpotDL Downloader", style="bold white")
    text.append(" ✨", style="bold magenta")
    panel = Panel(
        Align.center(text, vertical="middle"),
        title="[bold cyan]♪[/]",
        border_style="bright_blue",
        subtitle=f"[dim]v{VERSION}[/]",
        width=60,
        padding=(1, 2),
    )
    console.print(panel)
    console.print()


def show_settings(config: dict):
    table = Table(title="Current Settings", show_header=True, header_style="bold magenta")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Threads", str(config["threads"]))
    table.add_row("yt-dlp args", config["yt_dlp_args"])
    table.add_row("Format", config["format"])
    table.add_row("Lyrics", config["lyrics"])
    table.add_row("Generate .lrc", "Yes" if config["generate_lrc"] else "No")
    table.add_row("Output pattern", config["output"])
    download_path = config.get("download_path", "")
    table.add_row(
        "Download path",
        f"{download_path}" if download_path else f"{Path.cwd()} [dim](current directory)[/]",
    )
    table.add_row(
        "Folder layout",
        f"tracks → {SINGLES_SUBFOLDER}/, playlists & albums → {LIST_SUBFOLDER}/",
    )

    console.print(table)
    console.print()


def show_history(limit: int = 20):
    history = load_history()
    if not history:
        console.print("[dim]No downloads recorded yet.[/]\n")
        return

    table = Table(title=f"Recent Downloads (last {min(limit, len(history))})", header_style="bold magenta")
    table.add_column("When", style="cyan", no_wrap=True)
    table.add_column("URL", style="white", overflow="fold")
    table.add_column("Format", style="green")
    table.add_column("Status", style="bold")

    for entry in history[-limit:][::-1]:
        status = entry.get("status", "unknown")
        status_style = {
            "success": "[green]✔ success[/]",
            "error": "[red]✘ error[/]",
            "cancelled": "[yellow]⚠ cancelled[/]",
        }.get(status, status)
        table.add_row(
            entry.get("timestamp", "-"),
            entry.get("url", "-"),
            entry.get("format", "-"),
            status_style,
        )
    console.print(table)
    console.print()


def main_menu() -> str:
    console.print("[bold yellow]Main Menu[/]")
    console.print("  [cyan]1[/] Download a track / playlist / album")
    console.print("  [cyan]2[/] Batch download from a text file (one URL per line)")
    console.print("  [cyan]3[/] Edit settings")
    console.print("  [cyan]4[/] View current settings")
    console.print("  [cyan]5[/] View download history")
    console.print("  [cyan]6[/] Check / install dependencies (spotdl, ffmpeg, deno)")
    console.print("  [cyan]7[/] Reset settings to default")
    console.print("  [cyan]8[/] Exit")
    console.print()
    return Prompt.ask("Select an option", choices=[str(i) for i in range(1, 9)], default="1")


# --------------------------------------------------------------------------- #
# Dependency setup (spotdl, ffmpeg, deno)
# --------------------------------------------------------------------------- #

def spotdl_available() -> bool:
    return shutil.which("spotdl") is not None


def run_spotdl_setup_command(args: list, description: str) -> bool:
    console.print(f"[cyan]→ {description}...[/]")
    try:
        result = subprocess.run(["spotdl", *args], check=False)
        if result.returncode == 0:
            console.print(f"[green]✔ {description} - done.[/]\n")
            return True
        console.print(f"[red]✘ {description} failed (exit code {result.returncode}).[/]\n")
        return False
    except FileNotFoundError:
        console.print("[red]✘ 'spotdl' is not installed or not on PATH.[/]\n")
        return False


def check_dependencies(auto_install: bool = False):
    console.print("[bold yellow]Dependency Check[/]\n")

    table = Table(header_style="bold magenta")
    table.add_column("Tool", style="cyan")
    table.add_column("Status", style="white")

    spotdl_ok = spotdl_available()
    table.add_row("spotdl", "[green]✔ found[/]" if spotdl_ok else "[red]✘ missing[/]")
    console.print(table)
    console.print()

    if not spotdl_ok:
        console.print(
            "[yellow]spotdl was not found on your PATH.[/] "
            "Install it with: [cyan]pip install spotdl[/]\n"
        )
        return

    do_ffmpeg = auto_install or Confirm.ask(
        "Download/verify bundled ffmpeg via spotdl?", default=True
    )
    if do_ffmpeg:
        run_spotdl_setup_command(["--download-ffmpeg"], "Downloading ffmpeg")

    do_deno = auto_install or Confirm.ask(
        "Download/verify bundled deno via spotdl?", default=True
    )
    if do_deno:
        run_spotdl_setup_command(["--download-deno"], "Downloading deno")

    console.print("[green]✔ Dependency setup complete.[/]\n")


# --------------------------------------------------------------------------- #
# Settings editor
# --------------------------------------------------------------------------- #

def edit_settings(config: dict) -> dict:
    console.print("[bold yellow]Edit Settings[/] [dim](press Enter to keep current value)[/]\n")

    threads = IntPrompt.ask("Threads", default=config["threads"])
    config["threads"] = threads

    yt_dlp_args = Prompt.ask("yt-dlp extra args", default=config["yt_dlp_args"])
    config["yt_dlp_args"] = yt_dlp_args

    console.print(f"Available formats: {', '.join(FORMAT_CHOICES)}")
    fmt = Prompt.ask("Audio format", choices=FORMAT_CHOICES, default=config["format"])
    config["format"] = fmt

    console.print(f"Available lyrics providers: {', '.join(LYRICS_CHOICES)}")
    lyrics = Prompt.ask("Lyrics provider (or 'none' to disable)", choices=LYRICS_CHOICES, default=config["lyrics"])
    config["lyrics"] = lyrics

    if lyrics != "none":
        config["generate_lrc"] = Confirm.ask("Generate synced .lrc files?", default=config["generate_lrc"])
    else:
        config["generate_lrc"] = False

    output = Prompt.ask("Output naming pattern (filename only, no folder)", default=config["output"])
    config["output"] = output

    console.print(
        "\n[dim]Downloads are auto-organized into subfolders: tracks go in "
        f"'{SINGLES_SUBFOLDER}/', playlists and albums go in a folder named after "
        "them.[/]"
    )
    current_dl_path = config.get("download_path", "") or "(current directory)"
    download_path = Prompt.ask(
        "Default download path (leave as-is or type '.' for current working directory)",
        default=current_dl_path,
    )
    if download_path.strip() in ("", ".", "(current directory)"):
        config["download_path"] = ""
    else:
        config["download_path"] = download_path.strip()

    save_config(config)
    console.print("\n[green]✔ Settings saved.[/]\n")
    return config


# --------------------------------------------------------------------------- #
# Download path / output template logic
# --------------------------------------------------------------------------- #

def detect_spotify_type(url: str) -> str:
    """Returns 'track', 'playlist', 'album', or 'unknown' based on the URL/URI."""
    match = re.search(r"(track|playlist|album)", url, re.IGNORECASE)
    return match.group(1).lower() if match else "unknown"


def subfolder_for(url: str) -> str:
    """Subfolder (relative to the download path) content of this type lands in."""
    url_type = detect_spotify_type(url)
    if url_type == "track":
        return SINGLES_SUBFOLDER
    if url_type in ("playlist", "album"):
        return LIST_SUBFOLDER
    return ""


def resolve_download_path(download_path: str) -> Path:
    """Empty/blank download_path means 'current working directory, right now'."""
    if download_path and download_path.strip():
        return Path(download_path).expanduser()
    return Path.cwd()


def build_output_template(download_path: str, url: str, filename_pattern: str) -> str:
    base = resolve_download_path(download_path)
    sub = subfolder_for(url)
    full_path = (base / sub / filename_pattern) if sub else (base / filename_pattern)
    return str(full_path)


# --------------------------------------------------------------------------- #
# Download logic
# --------------------------------------------------------------------------- #

def build_command(url: str, config: dict) -> list:
    cmd = ["spotdl", "download", url]

    cmd += ["--threads", str(config["threads"])]

    if config["yt_dlp_args"].strip():
        cmd += ["--yt-dlp-args", config["yt_dlp_args"]]

    cmd += ["--format", config["format"]]

    if config["lyrics"] != "none":
        cmd += ["--lyrics", config["lyrics"]]
        if config["generate_lrc"]:
            cmd += ["--generate-lrc"]

    output_template = build_output_template(
        config.get("download_path", ""), url, config["output"]
    )
    cmd += ["--output", output_template]

    return cmd


def execute_download(url: str, config: dict) -> str:
    """Runs spotdl for a single URL. Returns one of 'success', 'error', 'cancelled'."""
    cmd = build_command(url, config)

    console.print()
    console.print(Panel(" ".join(cmd), title="[bold green]Running Command[/]", border_style="green"))
    console.print()

    status = "error"
    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode == 0:
            console.print("\n[bold green]✔ Download finished successfully.[/]\n")
            status = "success"
        else:
            console.print(f"\n[bold red]✘ spotdl exited with an error (code {result.returncode}).[/]\n")
            status = "error"
    except FileNotFoundError:
        console.print(
            "\n[bold red]✘ Could not find 'spotdl'.[/] "
            "Make sure it's installed: [cyan]pip install spotdl[/]\n"
        )
        status = "error"
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Download cancelled by user.[/]\n")
        status = "cancelled"

    append_history({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "url": url,
        "format": config["format"],
        "status": status,
    })
    log(f"download url={url} format={config['format']} status={status}")
    return status


def run_download(config: dict):
    console.print()
    url = Prompt.ask("[bold cyan]Enter Spotify URL[/] (track / playlist / album)")
    if not url.strip():
        console.print("[red]No URL entered, returning to menu.[/]\n")
        return
    url = url.strip()

    default_dl_path = config.get("download_path", "") or str(Path.cwd())
    download_path = Prompt.ask(
        "[bold cyan]Download path[/]", default=default_dl_path
    ).strip() or default_dl_path

    sub = subfolder_for(url)
    if sub:
        console.print(f"[dim]Will be saved under: {Path(download_path) / sub}[/]")
    console.print()

    session_config = config.copy()
    session_config["download_path"] = download_path

    override = Confirm.ask("Use current default settings for this download?", default=True)

    if not override:
        session_config["threads"] = IntPrompt.ask("Threads", default=config["threads"])
        session_config["yt_dlp_args"] = Prompt.ask("yt-dlp extra args", default=config["yt_dlp_args"])
        session_config["format"] = Prompt.ask(
            "Audio format", choices=FORMAT_CHOICES, default=config["format"]
        )
        session_config["lyrics"] = Prompt.ask(
            "Lyrics provider", choices=LYRICS_CHOICES, default=config["lyrics"]
        )
        if session_config["lyrics"] != "none":
            session_config["generate_lrc"] = Confirm.ask(
                "Generate synced .lrc files?", default=config["generate_lrc"]
            )
        else:
            session_config["generate_lrc"] = False
        session_config["output"] = Prompt.ask("Output naming pattern", default=config["output"])

    execute_download(url, session_config)


def run_batch_download(config: dict, file_path: Optional[str] = None):
    console.print()
    if file_path is None:
        file_path = Prompt.ask("[bold cyan]Path to text file with URLs (one per line)[/]")

    path = Path(file_path).expanduser()
    if not path.exists():
        console.print(f"[red]✘ File not found: {path}[/]\n")
        return

    urls = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    urls = [u for u in urls if u and not u.startswith("#")]

    if not urls:
        console.print("[yellow]No URLs found in file.[/]\n")
        return

    default_dl_path = config.get("download_path", "") or str(Path.cwd())
    download_path = Prompt.ask(
        "[bold cyan]Download path for this batch[/] "
        "(each URL still lands in its own Singles/playlist/album subfolder)",
        default=default_dl_path,
    ).strip() or default_dl_path
    session_config = config.copy()
    session_config["download_path"] = download_path

    console.print(f"[bold]Found {len(urls)} URL(s). Starting batch download...[/]\n")

    results = {"success": 0, "error": 0, "cancelled": 0}
    for i, url in enumerate(urls, start=1):
        console.print(f"[bold blue]--- [{i}/{len(urls)}] {url} ---[/]")
        status = execute_download(url, session_config)
        results[status] = results.get(status, 0) + 1
        if status == "cancelled":
            if not Confirm.ask("Continue with remaining URLs?", default=False):
                break

    console.print(
        Panel(
            f"[green]✔ {results['success']} succeeded[/]   "
            f"[red]✘ {results['error']} failed[/]   "
            f"[yellow]⚠ {results['cancelled']} cancelled[/]",
            title="Batch Summary",
            border_style="cyan",
        )
    )
    console.print()


# --------------------------------------------------------------------------- #
# CLI (non-interactive) mode
# --------------------------------------------------------------------------- #

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lyra",
        description="Lyra - a friendly command-line frontend for spotdl",
    )
    parser.add_argument(
        "urls", nargs="*", help="Spotify track/playlist/album URL(s) to download"
    )
    parser.add_argument("--batch", metavar="FILE", help="Text file with one URL per line")
    parser.add_argument("--format", choices=FORMAT_CHOICES, help="Audio format override")
    parser.add_argument("--lyrics", choices=LYRICS_CHOICES, help="Lyrics provider override")
    parser.add_argument("--threads", type=int, help="Thread count override")
    parser.add_argument("--output", help="Output naming pattern override (filename only, no folder)")
    parser.add_argument(
        "--download-path", metavar="PATH",
        help="Base download path (default: current working directory). "
             "Tracks go in a Singles/ subfolder, playlists/albums in a subfolder named after them.",
    )
    parser.add_argument(
        "--generate-lrc", dest="generate_lrc", action="store_true", default=None,
        help="Force-enable synced .lrc generation",
    )
    parser.add_argument(
        "--no-generate-lrc", dest="generate_lrc", action="store_false",
        help="Force-disable synced .lrc generation",
    )
    parser.add_argument(
        "--setup", action="store_true",
        help="Check and install dependencies (ffmpeg, deno via spotdl) and exit",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Assume yes for any confirmation prompts during --setup",
    )
    parser.add_argument(
        "--history", action="store_true", help="Print recent download history and exit"
    )
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    return parser


def apply_cli_overrides(config: dict, args: argparse.Namespace) -> dict:
    session_config = config.copy()
    if args.format:
        session_config["format"] = args.format
    if args.lyrics:
        session_config["lyrics"] = args.lyrics
    if args.threads is not None:
        session_config["threads"] = args.threads
    if args.output:
        session_config["output"] = args.output
    if args.download_path:
        session_config["download_path"] = args.download_path
    if args.generate_lrc is not None:
        session_config["generate_lrc"] = args.generate_lrc
    return session_config


def run_cli_mode(args: argparse.Namespace) -> int:
    if args.version:
        console.print(f"Lyra v{VERSION}")
        return 0

    if args.history:
        show_history()
        return 0

    if args.setup:
        check_dependencies(auto_install=args.yes)
        return 0

    config = load_config()
    session_config = apply_cli_overrides(config, args)

    if args.batch:
        run_batch_download(session_config, file_path=args.batch)
        return 0

    if args.urls:
        overall_ok = True
        for url in args.urls:
            status = execute_download(url, session_config)
            if status != "success":
                overall_ok = False
        return 0 if overall_ok else 1

    return -1  # signal: no CLI action requested, fall through to interactive mode


# --------------------------------------------------------------------------- #
# Main loop (interactive)
# --------------------------------------------------------------------------- #

def interactive_main():
    console.clear()
    banner()

    if not spotdl_available():
        console.print(
            "[yellow]⚠ spotdl was not found on your PATH.[/] "
            "You can still browse the menu, but downloads will fail until it's installed "
            "([cyan]pip install spotdl[/]) or you run option 6 to check dependencies.\n"
        )

    config = load_config()

    while True:
        choice = main_menu()
        console.print()

        if choice == "1":
            run_download(config)
        elif choice == "2":
            run_batch_download(config)
        elif choice == "3":
            config = edit_settings(config)
        elif choice == "4":
            show_settings(config)
        elif choice == "5":
            show_history()
        elif choice == "6":
            check_dependencies()
        elif choice == "7":
            if Confirm.ask("Reset all settings to default?", default=False):
                config = DEFAULTS.copy()
                save_config(config)
                console.print("[green]✔ Settings reset to default.[/]\n")
        elif choice == "8":
            console.print("[bold cyan]Goodbye! 🎵[/]")
            sys.exit(0)


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    # If any CLI-mode flag/arg was passed, run non-interactively.
    cli_triggered = bool(
        args.urls or args.batch or args.setup or args.history or args.version
    )

    if cli_triggered:
        exit_code = run_cli_mode(args)
        if exit_code != -1:
            sys.exit(exit_code)

    interactive_main()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Bye![/]")
        sys.exit(0)
