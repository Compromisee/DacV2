"""
File_renamer.py — AI Media File Renamer
────────────────────────────────────────
• Detects if a file is from a series or movie via its name
• Renames to media-server-friendly format (e.g., Jellyfin/Plex)
• Removes junk words (x265, BluRay, HEVC, YTS, etc.)
• Looks up missing data (timestamps, episode titles) via free APIs
• Automatically sorts renamed files into organised folders
  e.g. /ShowName/Season XX/

Example:
  Before : One Piece S02E10 - Pilot Movie.mp4
  After  : One Piece S02E10 - Pilot [2000-10-09].mp4

  Before : Bleach S02E100 movie x265.mkv
  After  : Bleach S02E100 - Pilot [Date].mkv → /Bleach/Season 2/

Uses: TVmaze API (free, no key needed) for episode metadata.
Optional: TMDB API key for richer movie data.
"""

import os
import re
import sys
import json
import time
import shutil
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

# ─── Paths ────────────────────────────────────────────────────────────────────
APP_DATA     = Path(os.environ.get("APPDATA", Path.home())) / "PythonMedia"
STATUS_FILE  = APP_DATA / "status.json"
HISTORY_FILE = APP_DATA / "History.json"

MEDIA_EXTS = {
    ".mkv", ".mp4", ".avi", ".mov", ".webm", ".m2ts",
    ".ts", ".flv", ".wmv", ".m4v",
}

# Junk words to strip from filenames
JUNK_WORDS = re.compile(
    r"\b("
    r"x264|x265|h264|h265|hevc|avc|xvid|divx|"
    r"bluray|blu[_\-]?ray|bdrip|brrip|bdremux|"
    r"webrip|web[_\-]?dl|hdtv|hdrip|dvdrip|dvdscr|"
    r"1080p|720p|480p|2160p|4k|uhd|fhd|hd|"
    r"aac|ac3|dts|dtshd|flac|mp3|truehd|atmos|"
    r"yts|yify|rarbg|eztv|ettv|fgt|evo|ion10|"
    r"proper|repack|extended|theatrical|unrated|"
    r"10bit|8bit|hdr|sdr|dv|dolby|vision|"
    r"multi|dubbed|subbed|"
    r"www\.[a-z0-9\-\.]+\.[a-z]{2,4}"  # URL-like strings
    r")\b",
    re.IGNORECASE,
)


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


def api_get(url: str, timeout: int = 8) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PythonMediaSuite/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


# ─── Interpreter: parse filename ──────────────────────────────────────────────
SERIES_PATTERN = re.compile(
    r"^(.+?)[.\s_\-]+[Ss](\d{1,2})[Ee](\d{1,4})(.*)$"
)

def parse_filename(stem: str) -> dict:
    """
    Parse a filename stem into metadata.
    Returns dict with keys: type, show, season, episode, extra
    """
    # Fuzzy: replace dots/underscores with spaces
    clean = re.sub(r"[._]", " ", stem).strip()

    m = SERIES_PATTERN.match(clean)
    if m:
        show   = _clean_title(m.group(1))
        season = int(m.group(2))
        ep     = int(m.group(3))
        extra  = m.group(4).strip(" -.")
        return {"type": "series", "show": show, "season": season, "episode": ep, "extra": extra}

    # Movie fallback: strip year
    year_m = re.search(r"\b(19|20)\d{2}\b", clean)
    year   = year_m.group(0) if year_m else None
    title  = _clean_title(re.sub(r"\b(19|20)\d{2}\b", "", clean).strip())
    return {"type": "movie", "title": title, "year": year}


def _clean_title(s: str) -> str:
    """Remove junk words and tidy up a title string."""
    s = JUNK_WORDS.sub(" ", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip(" -_.")


# ─── API lookups ──────────────────────────────────────────────────────────────
_tvmaze_cache: dict = {}

def tvmaze_episode(show: str, season: int, episode: int) -> dict | None:
    """Fetch episode info from TVmaze (free, no key)."""
    cache_key = f"{show}|{season}|{episode}"
    if cache_key in _tvmaze_cache:
        return _tvmaze_cache[cache_key]

    # Search for the show
    query = urllib.parse.quote(show)
    results = api_get(f"https://api.tvmaze.com/singlesearch/shows?q={query}")
    if not results:
        return None

    show_id = results.get("id")
    if not show_id:
        return None

    ep_data = api_get(
        f"https://api.tvmaze.com/shows/{show_id}/episodebynumber"
        f"?season={season}&number={episode}"
    )
    _tvmaze_cache[cache_key] = ep_data
    time.sleep(0.2)  # be polite
    return ep_data


def get_episode_title(show: str, season: int, episode: int) -> str | None:
    data = tvmaze_episode(show, season, episode)
    if data:
        return data.get("name")
    return None


def get_episode_date(show: str, season: int, episode: int) -> str | None:
    data = tvmaze_episode(show, season, episode)
    if data:
        return data.get("airdate")  # YYYY-MM-DD
    return None


# ─── Rename logic ─────────────────────────────────────────────────────────────
def build_series_name(meta: dict, ep_title: str | None, air_date: str | None, ext: str) -> str:
    """
    Build final filename in format:
      ShowName SXXEYYY - Title [YYYY-MM-DD].ext
    """
    show  = meta["show"]
    s     = meta["season"]
    e     = meta["episode"]
    code  = f"S{s:02d}E{e:03d}"
    parts = [f"{show} {code}"]
    if ep_title:
        parts.append(f" - {ep_title}")
    if air_date:
        parts.append(f" [{air_date}]")
    return "".join(parts) + ext


def build_movie_name(meta: dict, ext: str) -> str:
    title = meta["title"]
    year  = meta.get("year")
    if year:
        return f"{title} ({year}){ext}"
    return f"{title}{ext}"


def destination_folder(output_dir: Path, meta: dict) -> Path:
    """Return the target folder for a renamed file."""
    if meta["type"] == "series":
        show_folder   = output_dir / _safe_name(meta["show"])
        season_folder = show_folder / f"Season {meta['season']:02d}"
        return season_folder
    else:
        return output_dir / "Movies"


def _safe_name(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", s).strip()


# ─── Batch runner ─────────────────────────────────────────────────────────────
def run(input_path: str | Path, output_dir: str | Path = None,
        copy_mode: bool = False, delete_source: bool = False,
        all_in_one: bool = False, api_key_tmdb: str = None,
        dry_run: bool = False):
    """
    Main entry point.
    input_path   : file or folder to rename
    output_dir   : where renamed files go
    copy_mode    : copy instead of move
    delete_source: delete source after copy (only in copy mode)
    all_in_one   : place all output in one flat directory
    dry_run      : print what would happen, don't actually rename
    """
    input_path = Path(input_path)
    if not input_path.exists():
        print(f"[ERROR] Path not found: {input_path}")
        return

    files = (
        [input_path]
        if input_path.is_file()
        else [f for f in input_path.rglob("*") if f.suffix.lower() in MEDIA_EXTS]
    )
    files = sorted(files)

    if not files:
        print("[INFO] No media files found.")
        return

    output_dir = Path(output_dir) if output_dir else (
        input_path.parent / "Renamed"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    total = len(files)
    print(f"\n{'─'*60}")
    print(f"  AI File Renamer | Files: {total} | Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"{'─'*60}\n")

    processed = []

    for i, src in enumerate(files, 1):
        write_status({
            "running": True, "project": "AI File Renamer",
            "progress": int(i / total * 100),
            "message": f"Renaming {src.name} ({i}/{total})"
        })

        log(f"[{i}/{total}] {src.name}")
        meta = parse_filename(src.stem)
        log(f"  Parsed: {meta}")

        if meta["type"] == "series":
            ep_title = get_episode_title(meta["show"], meta["season"], meta["episode"])
            air_date = get_episode_date(meta["show"], meta["season"], meta["episode"])
            new_name = build_series_name(meta, ep_title, air_date, src.suffix)
            log(f"  Episode: {ep_title or '?'} | Air: {air_date or '?'}")
        else:
            new_name = build_movie_name(meta, src.suffix)

        log(f"  → {new_name}")

        if all_in_one:
            dest_folder = output_dir
        else:
            dest_folder = destination_folder(output_dir, meta)

        dest = dest_folder / _safe_name(new_name)

        if not dry_run:
            dest_folder.mkdir(parents=True, exist_ok=True)
            if copy_mode:
                shutil.copy2(str(src), str(dest))
                if delete_source:
                    src.unlink()
            else:
                shutil.move(str(src), str(dest))

        log(f"  ✓ {'(dry)' if dry_run else ''} {dest}\n")
        processed.append({"name": src.name, "size_bytes": src.stat().st_size})

    # Record history
    if processed and not dry_run:
        try:
            from Main import record_run
            record_run("AI File Renamer", processed)
        except ImportError:
            pass

    print(f"\n{'─'*60}")
    print(f"  Done. {len(processed)} file(s) renamed.")
    print(f"{'─'*60}\n")

    write_status({"running": False, "project": None, "progress": 100, "message": "Done"})


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI Media File Renamer")
    parser.add_argument("input",    help="File or folder to rename")
    parser.add_argument("--output", "-o", default=None, help="Output directory")
    parser.add_argument("--copy",   action="store_true", help="Copy instead of move")
    parser.add_argument("--delete-source", action="store_true",
                        help="Delete source after copy (copy mode only)")
    parser.add_argument("--flat", action="store_true",
                        help="Place all output files in one directory")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without making changes")
    parser.add_argument("--tmdb-key", default=None,
                        help="Optional TMDB API key for movie data")
    args = parser.parse_args()

    run(
        input_path    = args.input,
        output_dir    = args.output,
        copy_mode     = args.copy,
        delete_source = args.delete_source,
        all_in_one    = args.flat,
        api_key_tmdb  = args.tmdb_key,
        dry_run       = args.dry_run,
    )
