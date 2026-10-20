from pathlib import Path

try:
    import pygame
    HAS_PYGAME = True
except Exception:
    pygame = None
    HAS_PYGAME = False


class AudioManager:
    """Handles audio playback, pause, resume, stop, and volume adjustments (WAV and MP3)."""

    def __init__(self):
        self.is_initialized = False
        self.current_file = None
        self.is_paused = False
        self.is_playing = False
        self.volume = 0.9

        if HAS_PYGAME:
            try:
                pygame.mixer.init()
                self.is_initialized = True
            except Exception as e:
                print(f"Failed to initialize Pygame mixer: {e}")

    def load(self, audio_path: Path) -> bool:
        if not self.is_initialized or not audio_path or not Path(audio_path).exists():
            return False
        try:
            pygame.mixer.music.stop()
            try:
                pygame.mixer.music.unload()  # releases the previous file
            except Exception:
                pass
            pygame.mixer.music.load(str(audio_path))
            pygame.mixer.music.set_volume(self.volume)
            self.current_file = Path(audio_path)
            self.is_paused = False
            self.is_playing = False
            return True
        except Exception as e:
            print(f"Error loading audio file: {e}")
            return False

    def play(self) -> bool:
        if not self.is_initialized or not self.current_file:
            return False
        try:
            pygame.mixer.music.play()
            self.is_playing = True
            self.is_paused = False
            return True
        except Exception as e:
            print(f"Error playing audio: {e}")
            return False

    def pause(self):
        if not self.is_initialized or not self.is_playing or self.is_paused:
            return
        pygame.mixer.music.pause()
        self.is_paused = True

    def resume(self):
        if not self.is_initialized:
            return
        if self.is_paused:
            pygame.mixer.music.unpause()
            self.is_paused = False
            self.is_playing = True

    def stop(self):
        if not self.is_initialized:
            return
        pygame.mixer.music.stop()
        self.is_playing = False
        self.is_paused = False

    def restart(self):
        if self.current_file:
            self.play()

    def set_volume(self, val_float: float):
        """val_float expected between 0.0 and 1.0"""
        self.volume = max(0.0, min(1.0, val_float))
        if self.is_initialized:
            try:
                pygame.mixer.music.set_volume(self.volume)
            except Exception:
                pass

    def check_busy(self) -> bool:
        """True while audio is actively playing. Also detects when playback has finished."""
        if self.is_initialized and self.is_playing and not self.is_paused:
            busy = pygame.mixer.music.get_busy()
            if not busy:
                self.is_playing = False
            return busy
        return False
