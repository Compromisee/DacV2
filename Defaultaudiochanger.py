"""
Defaultaudiochanger.py — MKV Default Audio Changer (DAC)
─────────────────────────────────────────────────────────
• Changes default audio track in MKV files
• Also supports subtitles
• Automatically scans MKV files and groups tracks by language
• Auto English mode: sets English audio + subtitles as default
• If no English found, sorts files into:
    /NO ENG SUB  – has audio but no English subtitles
    /NO ENG DUB  – has subtitles but no English audio
    /NO ENG      – no English at all
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# ─── Status helper (shared with Main.py) ──────────────────────────────────────
APP_DATA = Path(os.environ.get("APPDATA", Path.home())) / "PythonMedia"
STATUS_FILE = APP_DATA / "status.json"


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


# ─── MKVToolNix wrappers ──────────────────────────────────────────────────────
def mkvmerge_identify(path: Path) -> dict | None:
    """Return mkvmerge JSON identification for a file."""
    try:
        result = subprocess.run(
            ["mkvmerge", "--identify", "--identification-format", "json", str(path)],
            capture_output=True, text=True, check=True
        )
        return json.loads(result.stdout)
    except Exception as e:
        log(f"  [!] mkvmerge identify failed for {path.name}: {e}")
        return None


def get_tracks(info: dict) -> dict:
    """Parse tracks into {audio: [...], subtitles: [...]} with language info."""
    tracks = {"audio": [], "subtitles": []}
    for track in info.get("tracks", []):
        lang = (track.get("properties", {}).get("language") or "und").lower()
        t = {
            "id":      track["id"],
            "lang":    lang,
            "name":    track.get("properties", {}).get("track_name", ""),
            "default": track.get("properties", {}).get("default_track", False),
            "forced":  track.get("properties", {}).get("forced_track", False),
        }
        if track["type"] == "audio":
            tracks["audio"].append(t)
        elif track["type"] == "subtitles":
            tracks["subtitles"].append(t)
    return tracks


def is_english(lang_str: str) -> bool:
    """Check if a language tag represents English."""
    eng_tags = {"eng", "en", "english"}
    return lang_str.lower().strip() in eng_tags


def mkvpropedit_set_default(mkv_path: Path, track_id: int, track_type: str):
    """Use mkvpropedit to set a track as default in-place."""
    try:
        subprocess.run(
            ["mkvpropedit", str(mkv_path),
             "--edit", f"track:{track_type}{track_id}",
             "--set", "flag-default=1"],
            capture_output=True, check=True
        )
        return True
    except Exception as e:
        log(f"  [!] mkvpropedit failed: {e}")
        return False


def mkvpropedit_clear_defaults(mkv_path: Path, track_ids: list[int], track_type: str):
    """Clear default flag from a list of tracks."""
    args = ["mkvpropedit", str(mkv_path)]
    for tid in track_ids:
        args += ["--edit", f"track:{track_type}{tid}", "--set", "flag-default=0"]
    try:
        subprocess.run(args, capture_output=True, check=True)
    except Exception as e:
        log(f"  [!] Clear defaults failed: {e}")


# ─── Core logic ───────────────────────────────────────────────────────────────
class DACResult:
    SUCCESS  = "success"
    NO_ENG   = "no_eng"
    NO_SUB   = "no_eng_sub"
    NO_DUB   = "no_eng_dub"
    ERROR    = "error"


def process_file(mkv_path: Path, auto_english: bool = True) -> str:
    """
    Process a single MKV file.
    Returns a DACResult constant.
    """
    info = mkvmerge_identify(mkv_path)
    if not info:
        return DACResult.ERROR

    tracks = get_tracks(info)
    audio_tracks    = tracks["audio"]
    subtitle_tracks = tracks["subtitles"]

    eng_audio = [t for t in audio_tracks    if is_english(t["lang"])]
    eng_subs  = [t for t in subtitle_tracks if is_english(t["lang"])]

    has_eng_audio = bool(eng_audio)
    has_eng_subs  = bool(eng_subs)

    if auto_english:
        if has_eng_audio or has_eng_subs:
            # Clear existing defaults then set English ones
            if audio_tracks:
                mkvpropedit_clear_defaults(mkv_path, [t["id"] for t in audio_tracks], "a")
            if subtitle_tracks:
                mkvpropedit_clear_defaults(mkv_path, [t["id"] for t in subtitle_tracks], "s")

            if has_eng_audio:
                mkvpropedit_set_default(mkv_path, eng_audio[0]["id"], "a")
                log(f"  → Set audio default: track {eng_audio[0]['id']} ({eng_audio[0]['lang']})")
            if has_eng_subs:
                mkvpropedit_set_default(mkv_path, eng_subs[0]["id"], "s")
                log(f"  → Set subtitle default: track {eng_subs[0]['id']} ({eng_subs[0]['lang']})")

            if has_eng_audio and not has_eng_subs:
                return DACResult.NO_SUB
            if has_eng_subs and not has_eng_audio:
                return DACResult.NO_DUB
            return DACResult.SUCCESS

        else:
            return DACResult.NO_ENG
    else:
        # Manual: just log available tracks; caller decides
        log(f"  Audio tracks    : {audio_tracks}")
        log(f"  Subtitle tracks : {subtitle_tracks}")
        return DACResult.SUCCESS


def sort_file(mkv_path: Path, result: str, output_dir: Path):
    """Move/copy a file to its sort folder based on result."""
    folder_map = {
        DACResult.NO_ENG: output_dir / "NO ENG",
        DACResult.NO_SUB: output_dir / "NO ENG SUB",
        DACResult.NO_DUB: output_dir / "NO ENG DUB",
    }
    dest_folder = folder_map.get(result)
    if dest_folder:
        dest_folder.mkdir(parents=True, exist_ok=True)
        dest = dest_folder / mkv_path.name
        shutil.move(str(mkv_path), str(dest))
        log(f"  → Moved to {dest_folder.name}/")


# ─── Batch runner ─────────────────────────────────────────────────────────────
def run(input_path: str | Path, output_dir: str | Path = None,
        auto_english: bool = True, sort: bool = True):
    """
    Main entry point.
    input_path : file or directory
    output_dir : where to place sorted folders (defaults to input parent)
    """
    input_path = Path(input_path)
    if not input_path.exists():
        print(f"[ERROR] Path not found: {input_path}")
        return

    mkv_files = (
        [input_path] if input_path.is_file() and input_path.suffix.lower() == ".mkv"
        else sorted(input_path.rglob("*.mkv"))
    )

    if not mkv_files:
        print("[INFO] No MKV files found.")
        return

    output_dir = Path(output_dir) if output_dir else input_path if input_path.is_dir() else input_path.parent
    total = len(mkv_files)
    counts = {k: 0 for k in [DACResult.SUCCESS, DACResult.NO_SUB, DACResult.NO_DUB, DACResult.NO_ENG, DACResult.ERROR]}

    print(f"\n{'─'*60}")
    print(f"  MKV Default Audio Changer — {total} file(s)")
    print(f"  Auto English: {auto_english}  |  Sort: {sort}")
    print(f"{'─'*60}\n")

    for i, mkv in enumerate(mkv_files, 1):
        pct = int(i / total * 100)
        write_status({
            "running": True, "project": "Default Audio Changer",
            "progress": pct, "message": f"Processing {mkv.name} ({i}/{total})"
        })
        log(f"[{i}/{total}] {mkv.name}")
        result = process_file(mkv, auto_english=auto_english)
        counts[result] += 1
        log(f"  Result: {result}\n")

        if sort and result != DACResult.SUCCESS and result != DACResult.ERROR:
            sort_file(mkv, result, output_dir)

    # Summary
    print(f"\n{'─'*60}")
    print(f"  Done. Results:")
    for k, v in counts.items():
        if v:
            print(f"    {k:15} : {v}")
    print(f"{'─'*60}\n")

    write_status({"running": False, "project": None, "progress": 100, "message": "Done"})


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MKV Default Audio Changer (DAC)")
    parser.add_argument("input",  help="MKV file or folder to process")
    parser.add_argument("--output", "-o", default=None, help="Output/sort folder")
    parser.add_argument("--manual", action="store_true",
                        help="Manual mode — don't auto-set English defaults")
    parser.add_argument("--no-sort", action="store_true",
                        help="Don't sort files into subfolders")
    args = parser.parse_args()

    run(
        input_path   = args.input,
        output_dir   = args.output,
        auto_english = not args.manual,
        sort         = not args.no_sort,
    )
