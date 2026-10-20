import json
import os
import re
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "audio"
SETTINGS_FILE = BASE_DIR / "settings.json"

# Ensure the dedicated audio folder exists on launch
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def get_unique_audio_path(pdf_filename: str, extension: str = ".mp3") -> Path:
    """
    Generates a unique output path inside the audio/ folder based on the PDF filename.
    Example: Engineering_Mechanics.pdf -> audio/Engineering_Mechanics.mp3
    If the file exists, appends an incrementing counter (_1, _2, etc.) to prevent overwriting.
    """
    if not extension.startswith("."):
        extension = "." + extension

    stem = Path(pdf_filename).stem
    safe_stem = re.sub(r'[^\w\-_]', '_', stem).strip('_')
    if not safe_stem:
        safe_stem = "converted_audio"

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    candidate = AUDIO_DIR / f"{safe_stem}{extension}"
    counter = 1
    while candidate.exists() or candidate.with_suffix(".wav").exists() or candidate.with_suffix(".mp3").exists():
        candidate = AUDIO_DIR / f"{safe_stem}_{counter}{extension}"
        counter += 1
    return candidate


def open_audio_folder():
    """Opens the audio output folder in the OS native file explorer."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    folder_str = str(AUDIO_DIR)

    if sys.platform == "win32":
        os.startfile(folder_str)
    elif sys.platform == "darwin":
        subprocess.run(["open", folder_str])
    else:
        subprocess.run(["xdg-open", folder_str])


def load_settings() -> dict:
    """Loads user settings from settings.json if available."""
    default_settings = {
        "voice_id": "edge:en-US-JennyNeural",
        "speed": 175,
        "volume": 0.9
    }
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_settings.update(data)
        except Exception:
            pass
    return default_settings


def save_settings(settings: dict):
    """Saves user settings to settings.json."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")
