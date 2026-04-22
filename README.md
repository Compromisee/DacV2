**DAC V2**

README & Dependency Guide

_Local AI · Media Processing · No Cloud · No Subscription_

# **Overview**

PythonMedia Suite is a collection of four Python tools for processing your local media library. Everything runs on your machine - no cloud uploads, no subscriptions, no API keys required for core features. The suite is controlled via a unified HTML dashboard or directly from the command line.

Entry point: **python Main.py** - launches the HTML dashboard in your browser via a local HTTP server.

# **Project File Structure**

| PythonMedia/                                                  |
| ------------------------------------------------------------- |
| ├── Main.py ← Entry point (run this)                          |
| ├── Dashboard.html ← HTML UI dashboard                        |
| ├── index.html ← Public landing / advertising page            |
| └── projects/                                                 |
| ├── Merger.py ← Video / audio file merger                     |
| ├── AI_Upscaler.py ← AI video / image upscaler                |
| ├── File_renamer.py ← AI media file renamer                   |
| └── Defaultaudiochanger.py ← MKV default audio/subtitle fixer |
|                                                               |
| AppData/Roaming/PythonMedia/ ← Auto-created on first run      |
| ├── status.json ← Live progress (polled by dashboard)         |
| └── History.json ← All-time processing log                    |

# **Quick Start**

### **Step 1 - Install Python 3.11+**

| \# Download from <https://python.org>     |
| ----------------------------------------- |
| python --version # must be 3.11 or higher |

### **Step 2 - Install system tools**

| \# Windows (winget)                  |
| ------------------------------------ |
| winget install Gyan.FFmpeg           |
| winget install MKVToolNix.MKVToolNix |
|                                      |
| \# macOS (Homebrew)                  |
| brew install ffmpeg mkvtoolnix       |
|                                      |
| \# Linux (Debian/Ubuntu)             |
| sudo apt install ffmpeg mkvtoolnix   |

### **Step 3 - Launch**

| cd PythonMedia                                   |
| ------------------------------------------------ |
| python Main.py # opens Dashboard.html in browser |
| python Main.py --cli # CLI interactive mode      |
| python Main.py --check # verify all dependencies |

# **All Dependencies**

## **System Tools**

| **Dependency**      | **Required?**    | **Purpose**                           | **Install**                    |
| ------------------- | ---------------- | ------------------------------------- | ------------------------------ |
| **Python 3.11+**    | **Required**     | Runtime for all scripts               | python.org                     |
| **ffmpeg**          | **Required**     | Video merge, frame extraction, repack | winget install Gyan.FFmpeg     |
| **mkvmerge**        | **Required\***   | Identify MKV tracks (DAC tool)        | mkvtoolnix.download            |
| **mkvpropedit**     | **Required\***   | Set default flags in-place (DAC tool) | included with MKVToolNix       |
| **realesrgan-ncnn** | **Required\*\*** | AI upscaling binary                   | github.com/xinntao/Real-ESRGAN |
| **Ollama**          | **Optional**     | Local LLM server for AI features      | ollama.ai                      |

**\*** mkvmerge and mkvpropedit are only needed for the Default Audio Changer tool.

**\*\*** realesrgan-ncnn-vulkan is only needed for the AI Upscaler tool.

## **Python Packages - None Required**

The suite uses only Python standard library modules. No pip install is needed for core functionality:

| \# All standard library - zero pip installs needed:        |
| ---------------------------------------------------------- |
| os, sys, json, re, shutil, subprocess, pathlib, threading, |
| http.server, socketserver, urllib.request, urllib.parse,   |
| datetime, time, tempfile, argparse, webbrowser             |

# **Ollama - Local AI Setup**

Ollama runs AI language models entirely on your machine. It is optional - all four core tools work without it. Ollama is used for enhanced AI features in the File Renamer and can be extended to any tool in the suite.

## **Installing Ollama**

| \# Windows / macOS - download installer:        |
| ----------------------------------------------- |
| \# <https://ollama.ai>                          |
|                                                 |
| \# Linux (one-liner install)                    |
| curl -fsSL <https://ollama.ai/install.sh> \| sh |
|                                                 |
| \# Verify Ollama is running:                    |
| curl <http://localhost:11434>                   |
| \# Expected response: Ollama is running         |
|                                                 |
| \# If not running, start it manually:           |
| ollama serve                                    |

## **Recommended Ollama Models**

Use ollama pull &lt;model&gt; to download a model. Larger models are slower but more accurate. Pick based on your available RAM/VRAM:

| **Model**        | **Size on Disk** | **Best For**                                     | **Pull Command**             |
| ---------------- | ---------------- | ------------------------------------------------ | ---------------------------- |
| **phi3:mini**    | ~2 GB            | Fastest. Lowest RAM. Good for basic renaming.    | **ollama pull phi3:mini**    |
| **llama3.2:3b**  | ~2 GB            | Fast + accurate. Recommended starting point.     | **ollama pull llama3.2:3b**  |
| **llama3.1:8b**  | ~5 GB            | Best everyday accuracy. Recommended if possible. | **ollama pull llama3.1:8b**  |
| **mistral:7b**   | ~4 GB            | Great structured output. Good for metadata.      | **ollama pull mistral:7b**   |
| **qwen2.5:7b**   | ~5 GB            | Excellent for media metadata and filenames.      | **ollama pull qwen2.5:7b**   |
| **llama3.1:70b** | ~40 GB           | Maximum accuracy. Requires 48 GB+ VRAM.          | **ollama pull llama3.1:70b** |

**💡 Recommendation:** Start with llama3.2:3b - it is fast and small. Upgrade to llama3.1:8b or qwen2.5:7b if you have 8 GB+ VRAM for better results.

## **GPU / RAM Requirements for Ollama**

| **VRAM / RAM**              | **Recommended Model**     | **Notes**                                             |
| --------------------------- | ------------------------- | ----------------------------------------------------- |
| No GPU / CPU only           | phi3:mini or llama3.2:3b  | Works but slow. 30-120 seconds per response.          |
| 4 GB VRAM                   | llama3.2:3b               | Good speed. Fine for all suite AI features.           |
| 8 GB VRAM                   | llama3.1:8b or mistral:7b | Fast. Best everyday model tier.                       |
| 16 GB+ VRAM                 | Any 13B or 70B model      | Excellent. Can run larger, more accurate models.      |
| CPU-only, 16 GB+ system RAM | llama3.1:8b (slow)        | Possible via RAM offloading. Expect 2-5 min/response. |

# **Real-ESRGAN - AI Upscaler Setup**

The AI Upscaler uses Real-ESRGAN-ncnn-Vulkan - a compiled binary that runs on any GPU via Vulkan. It does NOT require CUDA, so it works on NVIDIA, AMD, and Intel GPUs.

## **Installing Real-ESRGAN**

| \# 1. Download from GitHub releases:                          |
| ------------------------------------------------------------- |
| \# <https://github.com/xinntao/Real-ESRGAN/releases>          |
| \# File: realesrgan-ncnn-vulkan-\[version\]-\[your-os\].zip   |
|                                                               |
| \# 2. Extract the zip. Inside you will find:                  |
| \# - realesrgan-ncnn-vulkan.exe (Windows)                     |
| \# - realesrgan-ncnn-vulkan (Linux/macOS)                     |
| \# - models/ folder (REQUIRED - keep this next to the binary) |
|                                                               |
| \# 3. Add to PATH:                                            |
| \# Windows: add the extracted folder to System PATH           |
| \# macOS/Linux: mv realesrgan-ncnn-vulkan /usr/local/bin/     |
|                                                               |
| \# 4. Verify:                                                 |
| realesrgan-ncnn-vulkan --help                                 |

## **Built-in Models (Bundled in Zip)**

These models are included in the Real-ESRGAN download and selected automatically by the preset you choose:

| **Model File**              | **Used For**                               | **Preset**                          |
| --------------------------- | ------------------------------------------ | ----------------------------------- |
| **realesrgan-x4plus**       | Real-world content (live action, photos)   | 480_to_1080_real, 1080_to_4k_real   |
| **realesrgan-x4plus-anime** | Anime / cartoon content                    | 720_to_1080_anime, 1080_to_4k_anime |
| **realesr-animevideov3**    | Anime video (faster, optimised for motion) | Can be used manually via CLI        |

## **GPU Requirements for Upscaling**

**⚠️ Warning:** Video upscaling is extremely GPU-intensive. A 1-hour 1080p→4K upscale can take 2-12+ hours depending on your GPU. Image upscaling is fast (seconds per image).

| **GPU**                       | **Speed (video)** | **Notes**                                                |
| ----------------------------- | ----------------- | -------------------------------------------------------- |
| No GPU - CPU only             | ~0.1-0.5 fps      | Possible but extremely slow. Not recommended for video.  |
| Integrated GPU (4 GB shared)  | ~1-3 fps          | OK for images. Video is slow but doable for short clips. |
| Mid-range GPU (RTX 3060 etc.) | ~10-25 fps        | Good for video upscaling. 1080p→4K in reasonable time.   |
| High-end GPU (RTX 4080+)      | 30+ fps           | Real-time or faster. Excellent for bulk processing.      |

# **MKVToolNix - Audio Changer Setup**

The Default Audio Changer tool uses two binaries from MKVToolNix: **mkvmerge** (reads MKV track information) and **mkvpropedit** (sets default flags in-place without re-encoding).

| \# Windows - download installer from mkvtoolnix.download |
| -------------------------------------------------------- |
| \# Check 'Add to PATH' during installation               |
|                                                          |
| \# macOS                                                 |
| brew install mkvtoolnix                                  |
|                                                          |
| \# Linux (Debian/Ubuntu)                                 |
| sudo apt install mkvtoolnix                              |
| \# Linux (Fedora)                                        |
| sudo dnf install mkvtoolnix                              |
|                                                          |
| \# Verify both binaries are available:                   |
| mkvmerge --version                                       |
| mkvpropedit --version                                    |

# **ffmpeg - Video Processing Setup**

**ffmpeg** is required by two tools: the Merger (for concat) and the Upscaler (for frame extraction and repacking). It must be in your system PATH.

| \# Windows                                              |
| ------------------------------------------------------- |
| winget install Gyan.FFmpeg                              |
| \# Or: download from <https://ffmpeg.org/download.html> |
| \# Extract zip, add the /bin folder to PATH manually    |
|                                                         |
| \# macOS                                                |
| brew install ffmpeg                                     |
|                                                         |
| \# Linux (Debian/Ubuntu)                                |
| sudo apt install ffmpeg                                 |
|                                                         |
| \# Verify:                                              |
| ffmpeg -version                                         |

# **Free APIs - File Renamer**

The AI File Renamer uses free public APIs to look up episode titles and air dates. No account or key is needed for default use.

## **TVmaze (Default - No API Key Needed)**

Used automatically for all TV series. Provides episode titles, air dates, season/episode numbers, and show metadata:

| \# No setup needed - the script calls TVmaze automatically.        |
| ------------------------------------------------------------------ |
| \# Endpoints used:                                                 |
| \# <https://api.tvmaze.com/singlesearch/shows?q=<showname>&gt;     |
| \# <https://api.tvmaze.com/shows/<id>/episodebynumber?season=X>=Y> |
| #                                                                  |
| \# Rate limit: ~20 requests/second                                 |
| \# The script sleeps 200ms between calls to be polite.             |

## **TMDB - Optional, for Movies**

For better movie metadata (release year, proper title), you can provide a free TMDB API key:

- Create a free account at themoviedb.org
- Go to Settings → API → Create → Developer
- Copy your API Read Access Token
- Pass it with **\--tmdb-key YOUR_KEY** when running the script

python projects/File_renamer.py /media/folder --tmdb-key YOUR_KEY_HERE

# **Per-Tool Dependency Summary**

| **Tool**                   | **Dependencies**                                                                     |
| -------------------------- | ------------------------------------------------------------------------------------ |
| **Main.py**                | **Python 3.11+** \| No extra installs required \| Ollama optional (for status check) |
| **Merger.py**              | **Python 3.11+** \| **ffmpeg** (required)                                            |
| **AI_Upscaler.py**         | **Python 3.11+** \| **ffmpeg** \| **realesrgan-ncnn-vulkan** \| Ollama (optional)    |
| **File_renamer.py**        | **Python 3.11+** \| TVmaze API auto (free, no key) \| TMDB key (optional)            |
| **Defaultaudiochanger.py** | **Python 3.11+** \| **mkvmerge** \| **mkvpropedit**                                  |

# **CLI Quick Reference**

## **Main.py**

| python Main.py # Launch HTML dashboard in browser             |
| ------------------------------------------------------------- |
| python Main.py --cli # Interactive CLI mode                   |
| python Main.py --check # Verify all dependencies              |
| python Main.py --run merger # Run Merger directly             |
| python Main.py --run upscaler # Run AI Upscaler directly      |
| python Main.py --run renamer # Run File Renamer directly      |
| python Main.py --run dac # Run Default Audio Changer directly |

## **Merger.py**

| python projects/Merger.py /folder                                 |
| ----------------------------------------------------------------- |
| python projects/Merger.py file1.mkv file2.mkv --output merged.mkv |
| python projects/Merger.py /folder --sort date --output out.mp4    |
| python projects/Merger.py /folder --reencode --interactive        |

## **AI_Upscaler.py**

| python projects/AI_Upscaler.py /folder                                   |
| ------------------------------------------------------------------------ |
| python projects/AI_Upscaler.py video.mkv --preset 1080_to_4k_anime       |
| python projects/AI_Upscaler.py /folder --preset 480_to_1080_real -o /out |
| python projects/AI_Upscaler.py --list-presets                            |
|                                                                          |
| \# Available presets:                                                    |
| \# 480_to_1080_real 720_to_1080_anime 1080_to_4k_real 1080_to_4k_anime   |

## **File_renamer.py**

| python projects/File_renamer.py /media/folder                           |
| ----------------------------------------------------------------------- |
| python projects/File_renamer.py /folder --dry-run # preview, no changes |
| python projects/File_renamer.py /folder --copy -o /Renamed              |
| python projects/File_renamer.py /folder --flat # no subfolders          |
| python projects/File_renamer.py /folder --tmdb-key KEY                  |

## **Defaultaudiochanger.py**

| python projects/Defaultaudiochanger.py /mkv/folder                |
| ----------------------------------------------------------------- |
| python projects/Defaultaudiochanger.py /folder -o /sorted         |
| python projects/Defaultaudiochanger.py /folder --manual --no-sort |

# **Troubleshooting**

### **mkvmerge / mkvpropedit not found**

- Install MKVToolNix from mkvtoolnix.download
- Windows: re-run the installer, check 'Add to PATH'
- Test in a new terminal: **mkvmerge --version**

### **ffmpeg not found**

- Windows: run **winget install Gyan.FFmpeg** then open a new terminal
- macOS/Linux: brew install ffmpeg OR sudo apt install ffmpeg

### **Ollama not reachable**

- Run **ollama serve** in a terminal and keep it open
- Test: **curl <http://localhost:11434>** - should return 'Ollama is running'
- Firewall: ensure port 11434 is not blocked

### **realesrgan-ncnn-vulkan not found**

- Download from github.com/xinntao/Real-ESRGAN/releases
- Keep the models/ folder next to the binary
- Add the folder to your system PATH

### **Dashboard shows no progress / status**

- Make sure you launched the dashboard via Main.py (it runs an HTTP server)
- Do not open Dashboard.html directly as a file:// URL - it needs the HTTP server to read status.json

_PythonMedia Suite - Open Source · Local First · No Telemetry_
