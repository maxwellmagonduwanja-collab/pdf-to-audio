import asyncio
import re
import shutil
import tempfile
import time
import wave
from pathlib import Path

try:
    import pyttsx3
    HAS_PYTTSX3 = True
except Exception:
    pyttsx3 = None
    HAS_PYTTSX3 = False

try:
    import edge_tts
    HAS_EDGE = True
except Exception:
    edge_tts = None
    HAS_EDGE = False

EDGE_PREFIX = "edge:"
SYS_PREFIX = "sys:"

# Curated high-quality neural voices (need an internet connection).
# Female voices first, since they tend to be the warmest for long study sessions.
NEURAL_VOICES = [
    ("en-US-JennyNeural",   "Jenny - US Female (Neural, warm & friendly)"),
    ("en-US-AriaNeural",    "Aria - US Female (Neural, expressive)"),
    ("en-US-AvaNeural",     "Ava - US Female (Neural, natural)"),
    ("en-US-EmmaNeural",    "Emma - US Female (Neural, clear)"),
    ("en-US-MichelleNeural", "Michelle - US Female (Neural, soft)"),
    ("en-GB-SoniaNeural",   "Sonia - UK Female (Neural, elegant)"),
    ("en-GB-LibbyNeural",   "Libby - UK Female (Neural, gentle)"),
    ("en-GB-MaisieNeural",  "Maisie - UK Female (Neural, young)"),
    ("en-AU-NatashaNeural", "Natasha - Australian Female (Neural)"),
    ("en-IN-NeerjaNeural",  "Neerja - Indian Female (Neural)"),
    ("en-KE-AsiliaNeural",  "Asilia - Kenyan Female (Neural)"),
    ("en-NG-EzinneNeural",  "Ezinne - Nigerian Female (Neural)"),
    ("en-ZA-LeahNeural",    "Leah - South African Female (Neural)"),
    ("en-US-GuyNeural",     "Guy - US Male (Neural, calm)"),
    ("en-US-AndrewNeural",  "Andrew - US Male (Neural, warm)"),
    ("en-US-BrianNeural",   "Brian - US Male (Neural, clear)"),
    ("en-GB-RyanNeural",    "Ryan - UK Male (Neural)"),
    ("en-GB-ThomasNeural",  "Thomas - UK Male (Neural)"),
]

DEFAULT_VOICE_ID = EDGE_PREFIX + "en-US-JennyNeural"
BASE_WPM = 175  # speaking speed that maps to the neural voice's natural pace


# --------------------------------------------------------------------------- #
# Text chunking
# --------------------------------------------------------------------------- #
def _hard_split(piece: str, max_chars: int) -> list[str]:
    """Splits an over-long sentence on commas/semicolons/spaces."""
    if len(piece) <= max_chars:
        return [piece]
    parts = re.split(r'(?<=[,;:])\s+', piece)
    out, cur = [], ""
    for part in parts:
        if len(part) > max_chars:  # no punctuation at all: split on spaces
            if cur:
                out.append(cur)
                cur = ""
            words, buf = part.split(), ""
            for w in words:
                if len(buf) + len(w) + 1 > max_chars and buf:
                    out.append(buf)
                    buf = w
                else:
                    buf = f"{buf} {w}".strip()
            if buf:
                out.append(buf)
            continue
        if len(cur) + len(part) + 1 > max_chars and cur:
            out.append(cur)
            cur = part
        else:
            cur = f"{cur} {part}".strip()
    if cur:
        out.append(cur)
    return out


def split_text_into_chunks(text: str, max_chars: int = 1200) -> list[str]:
    """
    Splits long text into chunks that respect paragraph and sentence boundaries,
    so speech is never cut off mid-sentence.
    """
    chunks = []
    current = ""

    def flush():
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for para in re.split(r'\n\s*\n', text):
        para = para.strip()
        if not para:
            continue
        sentences = re.split(r'(?<=[.!?])\s+', para)
        pieces = []
        for s in sentences:
            s = s.strip()
            if s:
                pieces.extend(_hard_split(s, max_chars))
        for piece in pieces:
            if len(current) + len(piece) + 1 > max_chars:
                flush()
            current = f"{current} {piece}".strip()
        # Paragraph break: newline gives a natural pause in most engines
        current += "\n"
    flush()
    return chunks


# --------------------------------------------------------------------------- #
# Voices
# --------------------------------------------------------------------------- #
def get_system_voices() -> list[dict]:
    """Offline voices installed on this computer (Windows SAPI5, macOS, espeak)."""
    voices_list = []
    if not HAS_PYTTSX3:
        return voices_list

    female_keywords = ('female', 'woman', 'zira', 'susan', 'karen', 'vicki', 'heather',
                       'hannah', 'joyce', 'rachel', 'samantha', 'lisa', 'emma', 'kate',
                       'mia', 'nova', 'sarah', 'tara', 'lucia', 'helena', 'elsa', 'hazel',
                       'catherine', 'linda', 'eva', 'moira', 'fiona', 'victoria')
    try:
        engine = pyttsx3.init()
        for v in engine.getProperty('voices'):
            name = getattr(v, 'name', None) or v.id
            gender = str(getattr(v, 'gender', '') or '').lower()
            is_female = 'female' in gender or any(k in name.lower() for k in female_keywords)
            voices_list.append({
                "id": SYS_PREFIX + v.id,
                "name": f"{name} (Offline)",
                "is_female": is_female,
            })
        try:
            engine.stop()
        except Exception:
            pass
        voices_list.sort(key=lambda v: (not v["is_female"], v["name"].lower()))
    except Exception as e:
        print(f"Error initializing system voices: {e}")

    for v in voices_list:
        v.pop("is_female", None)
    return voices_list


def get_available_voices() -> list[dict]:
    """Neural voices first (best quality), then installed offline voices."""
    voices = []
    if HAS_EDGE:
        voices.extend({"id": EDGE_PREFIX + vid, "name": label} for vid, label in NEURAL_VOICES)
    voices.extend(get_system_voices())
    if not voices:
        voices.append({"id": "", "name": "Default System Voice"})
    return voices


def output_extension_for(voice_id: str) -> str:
    """Neural voices produce MP3, offline voices produce WAV."""
    if voice_id.startswith(EDGE_PREFIX) and HAS_EDGE:
        return ".mp3"
    return ".wav"


# --------------------------------------------------------------------------- #
# Neural (edge-tts) synthesis
# --------------------------------------------------------------------------- #
def _edge_rate_string(wpm: int) -> str:
    pct = int(round((wpm - BASE_WPM) / BASE_WPM * 100))
    pct = max(-50, min(100, pct))
    return f"{pct:+d}%"


async def _edge_save(text: str, voice: str, rate: str, path: Path):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(str(path))


def _synthesize_edge(chunks, output_path, voice, rate, progress_callback, cancel_event, temp_dir):
    rate_str = _edge_rate_string(rate)
    with open(output_path, "wb") as out:
        for idx, chunk in enumerate(chunks):
            if cancel_event and cancel_event.is_set():
                return False, "Canceled."

            part = temp_dir / f"part_{idx:05d}.mp3"
            last_err = None
            for attempt in range(3):
                try:
                    asyncio.run(_edge_save(chunk, voice, rate_str, part))
                    if part.exists() and part.stat().st_size > 0:
                        last_err = None
                        break
                except Exception as e:
                    last_err = e
                    time.sleep(1.5 * (attempt + 1))
            if last_err is not None or not part.exists():
                return False, f"Neural voice unavailable: {last_err}"

            out.write(part.read_bytes())
            part.unlink(missing_ok=True)

            if progress_callback:
                progress_callback(idx + 1, len(chunks))
    return True, "OK"


# --------------------------------------------------------------------------- #
# Offline (pyttsx3) synthesis
# --------------------------------------------------------------------------- #
def combine_wav_files(wav_paths: list[Path], output_path: Path) -> bool:
    """Merges multiple WAV files into one using only the standard library."""
    if not wav_paths:
        return False
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        out_w = None
        for path in wav_paths:
            try:
                with wave.open(str(path), 'rb') as w:
                    if out_w is None:
                        out_w = wave.open(str(output_path), 'wb')
                        out_w.setparams(w.getparams())
                    out_w.writeframes(w.readframes(w.getnframes()))
            except Exception as e:
                print(f"Error reading WAV chunk {path}: {e}")
        if out_w is None:
            return False
        out_w.close()
        return True
    except Exception as e:
        print(f"Error combining WAV files: {e}")
        return False


def _synthesize_system(chunks, output_path, voice_id, rate, volume,
                       progress_callback, cancel_event, temp_dir):
    if not HAS_PYTTSX3:
        return False, "No offline voice engine found. Run: pip install pyttsx3"

    wavs = []
    try:
        for idx, chunk in enumerate(chunks):
            if cancel_event and cancel_event.is_set():
                return False, "Canceled."

            chunk_file = temp_dir / f"chunk_{idx:05d}.wav"
            # A fresh engine per chunk avoids the well-known pyttsx3 hang on repeated runAndWait()
            engine = pyttsx3.init()
            engine.setProperty('rate', rate)
            engine.setProperty('volume', volume)
            if voice_id:
                try:
                    engine.setProperty('voice', voice_id)
                except Exception:
                    pass
            engine.save_to_file(chunk, str(chunk_file))
            engine.runAndWait()
            try:
                engine.stop()
            except Exception:
                pass
            del engine

            if chunk_file.exists() and chunk_file.stat().st_size > 0:
                wavs.append(chunk_file)

            if progress_callback:
                progress_callback(idx + 1, len(chunks))

        if combine_wav_files(wavs, output_path):
            return True, "OK"
        return False, "Could not combine audio chunks."
    except Exception as e:
        return False, f"Offline voice error: {e}"


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def generate_tts_audio(
    text: str,
    output_path: Path,
    voice_id: str = "",
    rate: int = BASE_WPM,
    volume: float = 1.0,
    progress_callback=None,
    cancel_event=None,
):
    """
    Converts text to speech.
    Returns (final_path or None, message).
    If a neural voice is chosen but the internet is unavailable, it automatically
    falls back to an offline system voice and saves a .wav instead.
    """
    output_path = Path(output_path)
    temp_dir = Path(tempfile.mkdtemp(prefix="pdf_audio_"))
    try:
        use_edge = voice_id.startswith(EDGE_PREFIX) and HAS_EDGE
        chunks = split_text_into_chunks(text, max_chars=1200 if use_edge else 600)
        if not chunks:
            return None, "There is no readable text."

        note = ""
        if use_edge:
            ok, msg = _synthesize_edge(chunks, output_path, voice_id[len(EDGE_PREFIX):],
                                       rate, progress_callback, cancel_event, temp_dir)
            if ok:
                return output_path, "Saved using neural voice."
            if msg == "Canceled.":
                output_path.unlink(missing_ok=True)
                return None, msg
            # Fallback to an offline voice
            output_path.unlink(missing_ok=True)
            note = f"{msg}. Switched to offline voice. "
            output_path = output_path.with_suffix(".wav")
            n = 1
            while output_path.exists():
                output_path = output_path.with_name(f"{output_path.stem}_{n}.wav")
                n += 1
            chunks = split_text_into_chunks(text, max_chars=600)
            sys_voice = ""
        else:
            sys_voice = voice_id[len(SYS_PREFIX):] if voice_id.startswith(SYS_PREFIX) else voice_id

        ok, msg = _synthesize_system(chunks, output_path, sys_voice, rate, volume,
                                     progress_callback, cancel_event, temp_dir)
        if ok:
            return output_path, note + "Saved using offline voice."
        output_path.unlink(missing_ok=True)
        return None, note + msg
    except Exception as e:
        return None, f"Error during audio generation: {e}"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
