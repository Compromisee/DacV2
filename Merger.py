"""
Merger.py — Video / Audio File Merger
──────────────────────────────────────
• Merges multiple video/audio files into one
• Drag-and-drop ordering (via ordered file list)
• Sorting options: alphanumeric, date, file size, custom
• Supports multiple file types
• Converts into any video/audio format via ffmpeg
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

# ─── Paths ────────────────────────────────────────────────────────────────────
APP_DATA     = Path(os.environ.get("APPDATA", Path.home())) / "PythonMedia"
STATUS_FILE  = APP_DATA / "status.json"
HISTORY_FILE = APP_DATA / "History.json"

SUPPORTED_EXTS = {
    ".mkv", ".mp4", ".avi", ".mov", ".webm", ".m2ts", ".ts",
    ".mp3", ".aac", ".flac", ".ogg", ".wav", ".m4a", ".opus",
}

SORT_MODES = ("alphanumeric", "date", "size", "custom")


# ─── Helpers ──────────────────────────────────────────────────────────────────
def write_status(data: dict):
    APP_DATA.mkdir(parents=True, exist_ok=True)
    existing = {}
    if STATUS_FILE.exists():
        try:
            existing = json.loads(STATUS_FILE.read_text())
        except Exception:
            pass
    existing.update(data)
    STATUS_FILE.write_text(json.dumps(existing, indent=2))


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def find_ffmpeg() -> str | None:
    import shutil
    return shutil.which("ffmpeg")


# ─── File collection & sorting ────────────────────────────────────────────────
def collect_files(paths: list[Path]) -> list[Path]:
    """Expand directories; keep only supported media files."""
    result = []
    for p in paths:
        if p.is_dir():
            result.extend(f for f in sorted(p.iterdir()) if f.suffix.lower() in SUPPORTED_EXTS)
        elif p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            result.append(p)
    return result


def sort_files(files: list[Path], mode: str) -> list[Path]:
    """Sort a list of files according to the chosen mode."""
    if mode == "alphanumeric":
        return sorted(files, key=lambda f: f.name.lower())
    elif mode == "date":
        return sorted(files, key=lambda f: f.stat().st_mtime)
    elif mode == "size":
        return sorted(files, key=lambda f: f.stat().st_size)
    elif mode == "custom":
        # Custom: user provides order; just return as-is (already user-ordered)
        return files
    else:
        raise ValueError(f"Unknown sort mode: {mode}")


def display_file_list(files: list[Path]):
    """Print a numbered list of files with sizes."""
    print(f"\n  {'#':>3}  {'Size':>10}  Name")
    print(f"  {'─'*3}  {'─'*10}  {'─'*50}")
    total = 0
    for i, f in enumerate(files, 1):
        size = f.stat().st_size
        total += size
        size_str = _fmt_size(size)
        print(f"  {i:>3}  {size_str:>10}  {f.name}")
    print(f"\n  Total: {_fmt_size(total)} across {len(files)} file(s)")


def _fmt_size(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


# ─── ffmpeg concat ────────────────────────────────────────────────────────────
def build_concat_list(files: list[Path], tmp_path: Path):
    """Write an ffmpeg concat demuxer file."""
    lines = []
    for f in files:
        safe = str(f).replace("'", r"'\''")
        lines.append(f"file '{safe}'")
    tmp_path.write_text("\n".join(lines), encoding="utf-8")


def merge(files: list[Path], output: Path, ffmpeg_bin: str,
          re_encode: bool = False, output_format: str = None) -> bool:
    """
    Merge files using ffmpeg concat demuxer.
    re_encode: False = stream copy (fast), True = re-encode (compatible but slow)
    """
    import tempfile

    if not files:
        log("[!] No files to merge.")
        return False

    # Build concat list
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                     delete=False, encoding="utf-8") as tmp:
        tmp_path = Path(tmp.name)
        for f in files:
            tmp.write(f"file '{str(f).replace(chr(39), \"'\\\\''\")}'\n")

    output.parent.mkdir(parents=True, exist_ok=True)

    if re_encode:
        cmd = [
            ffmpeg_bin, "-f", "concat", "-safe", "0",
            "-i", str(tmp_path),
            "-c:v", "libx264", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-y", str(output),
        ]
    else:
        cmd = [
            ffmpeg_bin, "-f", "concat", "-safe", "0",
            "-i", str(tmp_path),
            "-c", "copy",
            "-y", str(output),
        ]

    log(f"  Running: {' '.join(cmd[:8])} ...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    tmp_path.unlink(missing_ok=True)

    if result.returncode != 0:
        log(f"  [!] ffmpeg error:\n{result.stderr[-500:]}")
        return False

    log(f"  ✓ Merged → {output}")
    return True


# ─── Interactive reorder ──────────────────────────────────────────────────────
def interactive_reorder(files: list[Path]) -> list[Path]:
    """Let the user re-order files by entering a custom sequence."""
    display_file_list(files)
    print("\n  Enter new order as comma-separated numbers (e.g. 3,1,2)")
    print("  Or press Enter to keep current order:")
    raw = input("  Order> ").strip()
    if not raw:
        return files
    try:
        indices = [int(x.strip()) - 1 for x in raw.split(",")]
        reordered = [files[i] for i in indices]
        # Append any files not mentioned
        remaining = [f for f in files if f not in reordered]
        return reordered + remaining
    except (ValueError, IndexError):
        log("  [!] Invalid order input. Using original order.")
        return files


# ─── Main run ─────────────────────────────────────────────────────────────────
def run(inputs: list[str | Path], output: str | Path = None,
        sort_mode: str = "alphanumeric", re_encode: bool = False,
        interactive: bool = False):
    """
    Main entry point.
    inputs    : list of files/folders to merge
    output    : output file path
    sort_mode : alphanumeric | date | size | custom
    re_encode : True to re-encode (more compatible), False for stream copy
    interactive: True for interactive reorder prompt
    """
    ffmpeg_bin = find_ffmpeg()
    if not ffmpeg_bin:
        print("[ERROR] ffmpeg not found. Please install ffmpeg.")
        return

    inputs = [Path(p) for p in inputs]
    files  = collect_files(inputs)

    if not files:
        print("[INFO] No supported media files found.")
        return

    files = sort_files(files, sort_mode if sort_mode != "custom" else "alphanumeric")

    if interactive or sort_mode == "custom":
        files = interactive_reorder(files)

    display_file_list(files)

    if output is None:
        base   = files[0].parent
        suffix = files[0].suffix
        output = base / f"merged_output{suffix}"
    output = Path(output)

    print(f"\n  Output : {output}")
    print(f"  Mode   : {'Re-encode' if re_encode else 'Stream copy'}\n")

    write_status({
        "running": True, "project": "Merger",
        "progress": 0, "message": f"Merging {len(files)} files..."
    })

    ok = merge(files, output, ffmpeg_bin, re_encode=re_encode)

    if ok:
        try:
            from Main import record_run
            record_run("Merger", [{"name": f.name, "size_bytes": f.stat().st_size} for f in files])
        except ImportError:
            pass

    write_status({"running": False, "project": None, "progress": 100, "message": "Done"})
    return ok


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Video/Audio File Merger")
    parser.add_argument("inputs", nargs="+", help="Files or folders to merge")
    parser.add_argument("--output", "-o", default=None, help="Output file path")
    parser.add_argument("--sort", "-s", default="alphanumeric",
                        choices=SORT_MODES, help="Sort mode")
    parser.add_argument("--reencode", action="store_true",
                        help="Re-encode instead of stream copy")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Interactively reorder files before merging")
    args = parser.parse_args()

    run(
        inputs      = args.inputs,
        output      = args.output,
        sort_mode   = args.sort,
        re_encode   = args.reencode,
        interactive = args.interactive,
    )
