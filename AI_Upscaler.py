"""
AI_Upscaler.py — AI Video/Image Upscaler
─────────────────────────────────────────
Upscaling options:
  • 480p  → 1080p  (real-esrgan, real content)
  • 720p  → 1080p  (anime4k / real-esrgan-anime)
  • 1080p → 4K     (real/anime)

Uses local AI models via Ollama or direct model binaries.
Supports bulk file/folder upscaling.
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# ─── Paths ────────────────────────────────────────────────────────────────────
APP_DATA    = Path(os.environ.get("APPDATA", Path.home())) / "PythonMedia"
STATUS_FILE = APP_DATA / "status.json"
HISTORY_FILE = APP_DATA / "History.json"

# Supported upscaling presets
PRESETS = {
    "480_to_1080_real":  {"scale": 2,  "model": "realesrgan-x4plus",       "tag": "real"},
    "720_to_1080_anime": {"scale": 2,  "model": "realesrgan-x4plus-anime",  "tag": "anime"},
    "1080_to_4k_real":   {"scale": 4,  "model": "realesrgan-x4plus",        "tag": "real"},
    "1080_to_4k_anime":  {"scale": 4,  "model": "realesrgan-x4plus-anime",  "tag": "anime"},
}

VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".mov", ".webm", ".m2ts", ".ts"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


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


def find_binary(names: list[str]) -> str | None:
    """Find the first available binary from a list of candidates."""
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


# ─── Model / dependency checks ────────────────────────────────────────────────
def check_realesrgan() -> str | None:
    binary = find_binary(["realesrgan-ncnn-vulkan", "realesrgan"])
    if binary:
        log(f"  [OK]  Real-ESRGAN found: {binary}")
    else:
        log("  [!!]  Real-ESRGAN not found. Install realesrgan-ncnn-vulkan.")
    return binary


def check_ffmpeg() -> str | None:
    binary = find_binary(["ffmpeg"])
    if binary:
        log(f"  [OK]  ffmpeg found: {binary}")
    else:
        log("  [!!]  ffmpeg not found. Install ffmpeg.")
    return binary


def list_available_models() -> list[str]:
    """Query Ollama for available models (for AI features)."""
    try:
        import urllib.request, json as _json
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
            data = _json.loads(r.read())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def download_model_prompt(model_name: str) -> bool:
    """Ask user if they want to pull an Ollama model."""
    ans = input(f"\n  Model '{model_name}' not found. Pull it now? [y/N] ").strip().lower()
    if ans == "y":
        log(f"  Pulling {model_name} via Ollama...")
        result = subprocess.run(["ollama", "pull", model_name], capture_output=False)
        return result.returncode == 0
    return False


# ─── Image upscaling ──────────────────────────────────────────────────────────
def upscale_image(src: Path, dst: Path, model: str, scale: int, realesrgan_bin: str) -> bool:
    """Upscale a single image using Real-ESRGAN."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        realesrgan_bin,
        "-i", str(src),
        "-o", str(dst),
        "-n", model,
        "-s", str(scale),
        "-f", dst.suffix.lstrip(".") or "png",
    ]
    log(f"  CMD: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"  [!] Real-ESRGAN error: {result.stderr.strip()}")
        return False
    return True


# ─── Video upscaling (frame extract → upscale → repack) ──────────────────────
def upscale_video(src: Path, dst: Path, model: str, scale: int,
                  realesrgan_bin: str, ffmpeg_bin: str) -> bool:
    """
    Upscale a video by:
    1. Extracting frames with ffmpeg
    2. Upscaling each frame with Real-ESRGAN
    3. Repacking frames + original audio into output video
    """
    import tempfile

    log(f"  Upscaling video: {src.name}")

    with tempfile.TemporaryDirectory(prefix="pm_upscale_") as tmpdir:
        frames_in  = Path(tmpdir) / "frames_in"
        frames_out = Path(tmpdir) / "frames_out"
        frames_in.mkdir()
        frames_out.mkdir()

        # 1. Extract frames
        log("  → Extracting frames...")
        extract = subprocess.run([
            ffmpeg_bin, "-i", str(src),
            "-vsync", "0",
            str(frames_in / "frame%08d.png"),
        ], capture_output=True, text=True)
        if extract.returncode != 0:
            log(f"  [!] Frame extraction failed: {extract.stderr[-300:]}")
            return False

        frame_files = sorted(frames_in.glob("*.png"))
        total_frames = len(frame_files)
        log(f"  → {total_frames} frames extracted")

        # 2. Upscale frames
        log("  → Upscaling frames...")
        for i, frame in enumerate(frame_files, 1):
            out_frame = frames_out / frame.name
            upscale_image(frame, out_frame, model, scale, realesrgan_bin)
            if i % 50 == 0 or i == total_frames:
                pct = int(i / total_frames * 100)
                write_status({"progress": pct, "message": f"Upscaling frames {i}/{total_frames}"})

        # 3. Get original fps
        probe = subprocess.run([
            ffmpeg_bin, "-i", str(src)
        ], capture_output=True, text=True)
        fps = "24"
        for line in probe.stderr.splitlines():
            if "fps" in line:
                import re
                m = re.search(r"(\d+(?:\.\d+)?)\s+fps", line)
                if m:
                    fps = m.group(1)
                    break

        # 4. Repack
        log("  → Repacking video...")
        dst.parent.mkdir(parents=True, exist_ok=True)
        repack = subprocess.run([
            ffmpeg_bin,
            "-framerate", fps,
            "-i", str(frames_out / "frame%08d.png"),
            "-i", str(src),
            "-map", "0:v", "-map", "1:a?",
            "-c:v", "libx264", "-crf", "18", "-preset", "slow",
            "-c:a", "copy",
            "-y", str(dst),
        ], capture_output=True, text=True)
        if repack.returncode != 0:
            log(f"  [!] Repack failed: {repack.stderr[-300:]}")
            return False

    log(f"  → Done: {dst}")
    return True


# ─── Batch runner ─────────────────────────────────────────────────────────────
def run(input_path: str | Path, output_dir: str | Path = None,
        preset: str = "1080_to_4k_real", quality: str = "high"):
    """
    Main entry point.
    input_path : file or folder
    output_dir : where upscaled files are saved
    preset     : one of the PRESETS keys
    quality    : "high" | "fast" (affects ffmpeg crf)
    """
    input_path = Path(input_path)
    if not input_path.exists():
        print(f"[ERROR] Path not found: {input_path}")
        return

    if preset not in PRESETS:
        print(f"[ERROR] Unknown preset '{preset}'. Available: {list(PRESETS.keys())}")
        return

    cfg = PRESETS[preset]

    # Dependency checks
    realesrgan_bin = check_realesrgan()
    ffmpeg_bin     = check_ffmpeg()
    if not realesrgan_bin or not ffmpeg_bin:
        print("\n[ERROR] Missing dependencies. Cannot upscale.")
        return

    # Collect files
    all_exts = VIDEO_EXTS | IMAGE_EXTS
    files = (
        [input_path]
        if input_path.is_file()
        else [f for f in input_path.rglob("*") if f.suffix.lower() in all_exts]
    )
    files = sorted(files)

    if not files:
        print("[INFO] No supported files found.")
        return

    output_dir = Path(output_dir) if output_dir else (
        input_path.parent / f"Upscaled_{preset}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    total = len(files)
    print(f"\n{'─'*60}")
    print(f"  AI Upscaler | Preset: {preset} | Files: {total}")
    print(f"  Model: {cfg['model']} | Scale: {cfg['scale']}x")
    print(f"  Output: {output_dir}")
    print(f"{'─'*60}\n")

    success, failed = 0, 0
    processed_files = []

    for i, src in enumerate(files, 1):
        write_status({
            "running": True, "project": "AI Upscaler",
            "progress": int(i / total * 100),
            "message": f"Processing {src.name} ({i}/{total})"
        })
        log(f"[{i}/{total}] {src.name}")

        dst = output_dir / src.name

        if src.suffix.lower() in IMAGE_EXTS:
            ok = upscale_image(src, dst, cfg["model"], cfg["scale"], realesrgan_bin)
        else:
            ok = upscale_video(src, dst, cfg["model"], cfg["scale"], realesrgan_bin, ffmpeg_bin)

        if ok:
            success += 1
            processed_files.append({"name": src.name, "size_bytes": src.stat().st_size})
        else:
            failed += 1

    # Record to history
    if processed_files:
        try:
            from Main import record_run
            record_run("AI Upscaler", processed_files)
        except ImportError:
            pass

    print(f"\n{'─'*60}")
    print(f"  Done. Success: {success} | Failed: {failed}")
    print(f"{'─'*60}\n")

    write_status({"running": False, "project": None, "progress": 100, "message": "Done"})


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI Video/Image Upscaler")
    parser.add_argument("input",   help="File or folder to upscale")
    parser.add_argument("--output", "-o", default=None, help="Output directory")
    parser.add_argument("--preset", "-p", default="1080_to_4k_real",
                        choices=list(PRESETS.keys()), help="Upscaling preset")
    parser.add_argument("--quality", "-q", default="high",
                        choices=["high", "fast"], help="Encoding quality")
    parser.add_argument("--list-presets", action="store_true",
                        help="List available presets and exit")

    args = parser.parse_args()

    if args.list_presets:
        print("\nAvailable presets:")
        for k, v in PRESETS.items():
            print(f"  {k:25} model={v['model']}, scale={v['scale']}x")
        sys.exit(0)

    run(
        input_path = args.input,
        output_dir = args.output,
        preset     = args.preset,
        quality    = args.quality,
    )
