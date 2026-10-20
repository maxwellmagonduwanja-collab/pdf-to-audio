import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from settings import (
    get_unique_audio_path,
    open_audio_folder,
    load_settings,
    save_settings
)
from pdf_processor import extract_pdf_data
from text_cleaner import clean_pdf_text
from tts_engine import (
    get_available_voices,
    generate_tts_audio,
    output_extension_for,
    DEFAULT_VOICE_ID,
)
from audio_manager import AudioManager

PREVIEW_TEXT = (
    "Hello! I will be reading your study notes today. "
    "Newton's second law says that force equals mass times acceleration."
)


class PDFToAudioApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PDF → Audio Reader")
        self.root.geometry("900x780")
        self.root.minsize(800, 680)

        self.setup_styles()

        # State
        self.settings = load_settings()
        self.current_pdf_path = None
        self.current_audio_path = None
        self.extracted_text = ""
        self.audio_manager = AudioManager()
        self.audio_manager.set_volume(float(self.settings.get("volume", 0.9)))
        self.voices = get_available_voices()
        self.is_processing = False
        self.cancel_event = threading.Event()
        self.preview_files = []
        self._progress_animation_id = None

        self.create_widgets()
        self.bind_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(500, self.monitor_audio_status)

    # ------------------------------------------------------------------ #
    # Styling & layout
    # ------------------------------------------------------------------ #
    def setup_styles(self):
        self.bg_color = "#0b1020"
        self.card_color = "#121a2b"
        self.raised_color = "#19253a"
        self.border_color = "#283650"
        self.fg_color = "#e8eef9"
        self.muted_color = "#9aa9c2"
        self.accent_color = "#8b7cff"
        self.accent_hover = "#7667f4"
        self.secondary_accent = "#3dd6b5"

        self.root.configure(bg=self.bg_color)

        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", background=self.bg_color, foreground=self.fg_color, font=("Segoe UI", 10))
        style.configure(
            "Header.TLabel", font=("Segoe UI", 21, "bold"),
            foreground=self.fg_color, background=self.bg_color
        )
        style.configure(
            "SubHeader.TLabel", font=("Segoe UI", 10),
            foreground=self.muted_color, background=self.bg_color
        )
        style.configure(
            "Eyebrow.TLabel", font=("Segoe UI", 9, "bold"),
            foreground=self.accent_color, background=self.bg_color
        )
        style.configure("Card.TFrame", background=self.card_color, relief="flat")
        style.configure("Card.TLabel", background=self.card_color, foreground=self.fg_color)
        style.configure(
            "Badge.TLabel", font=("Segoe UI", 9, "bold"),
            background=self.raised_color, foreground="#a9c7ff", padding=(9, 5)
        )

        style.configure(
            "TButton", font=("Segoe UI", 10), background=self.raised_color,
            foreground=self.fg_color, borderwidth=0, focusthickness=0,
            padding=(11, 7), relief="flat"
        )
        style.map(
            "TButton",
            background=[("disabled", self.card_color), ("active", "#263652")],
            foreground=[("disabled", "#66738a"), ("active", self.fg_color)]
        )
        style.configure(
            "Primary.TButton", font=("Segoe UI", 10, "bold"),
            background=self.accent_color, foreground="#ffffff",
            borderwidth=0, focusthickness=0, padding=(13, 8)
        )
        style.map(
            "Primary.TButton",
            background=[("disabled", "#45405f"), ("active", self.accent_hover)],
            foreground=[("disabled", "#a9a4bf"), ("active", "#ffffff")]
        )
        style.configure(
            "Success.TButton", font=("Segoe UI", 10, "bold"),
            background="#168c79", foreground="#ffffff",
            borderwidth=0, focusthickness=0, padding=(13, 8)
        )
        style.map(
            "Success.TButton",
            background=[("disabled", "#365d59"), ("active", "#20a890")],
            foreground=[("disabled", "#a8c0bc"), ("active", "#ffffff")]
        )
        style.configure(
            "TCombobox", fieldbackground=self.raised_color,
            background=self.raised_color, foreground=self.fg_color,
            arrowcolor=self.muted_color, borderwidth=0, padding=6
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", self.raised_color), ("disabled", self.card_color)],
            foreground=[("readonly", self.fg_color), ("disabled", self.muted_color)],
            selectbackground=[("readonly", self.accent_color)]
        )
        style.configure(
            "Horizontal.TScale", background=self.card_color,
            troughcolor=self.raised_color
        )
        style.configure(
            "TProgressbar", thickness=9, troughcolor=self.raised_color,
            background=self.secondary_accent, borderwidth=0
        )

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=22)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 16))
        ttk.Label(header_frame, text="PDF  /  AUDIO STUDIO", style="Eyebrow.TLabel").pack(anchor=tk.W, pady=(0, 4))
        ttk.Label(header_frame, text="PDF → AUDIO READER", style="Header.TLabel").pack(anchor=tk.W)
        ttk.Label(
            header_frame,
            text="Turn your educational study materials into clear spoken audio",
            style="SubHeader.TLabel"
        ).pack(anchor=tk.W, pady=(3, 0))

        # PDF controls & stats
        pdf_card = ttk.Frame(main_frame, style="Card.TFrame", padding=12)
        pdf_card.pack(fill=tk.X, pady=(0, 10))

        pdf_top_row = ttk.Frame(pdf_card, style="Card.TFrame")
        pdf_top_row.pack(fill=tk.X)

        self.btn_upload = ttk.Button(pdf_top_row, text="📁 Upload PDF", style="Primary.TButton", command=self.upload_pdf)
        self.btn_upload.pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_pdf_name = ttk.Label(pdf_top_row, text="No PDF selected", style="Card.TLabel", font=("Segoe UI", 10, "bold"))
        self.lbl_pdf_name.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_clean_text = ttk.Button(pdf_top_row, text="🧹 Clean Text", command=self.action_clean_text)
        self.btn_clean_text.pack(side=tk.RIGHT)

        stats_row = ttk.Frame(pdf_card, style="Card.TFrame")
        stats_row.pack(fill=tk.X, pady=(10, 0))

        self.lbl_pages = ttk.Label(stats_row, text="Pages: 0", style="Badge.TLabel")
        self.lbl_pages.pack(side=tk.LEFT, padx=(0, 10))
        self.lbl_words = ttk.Label(stats_row, text="Words: 0", style="Badge.TLabel")
        self.lbl_words.pack(side=tk.LEFT, padx=(0, 10))
        self.lbl_chars = ttk.Label(stats_row, text="Characters: 0", style="Badge.TLabel")
        self.lbl_chars.pack(side=tk.LEFT)

        # Text preview
        preview_card = ttk.Frame(main_frame, style="Card.TFrame", padding=12)
        preview_card.pack(fill=tk.BOTH, expand=True, pady=10)

        preview_header = ttk.Frame(preview_card, style="Card.TFrame")
        preview_header.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(preview_header, text="TEXT PREVIEW (editable)", style="Card.TLabel", font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)

        ttk.Button(preview_header, text="Copy", width=8, command=self.copy_text).pack(side=tk.RIGHT, padx=2)
        ttk.Button(preview_header, text="Clear", width=8, command=self.clear_text).pack(side=tk.RIGHT, padx=2)

        text_frame = ttk.Frame(preview_card)
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.txt_preview = tk.Text(
            text_frame, wrap=tk.WORD, bg="#0e1626", fg="#dbe5f5",
            insertbackground="#a99cff", selectbackground="#3b4662",
            relief="flat", borderwidth=0, highlightthickness=1,
            highlightbackground=self.border_color, highlightcolor=self.accent_color,
            padx=14, pady=12, font=("Segoe UI", 10), undo=True
        )
        scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.txt_preview.yview)
        self.txt_preview.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.txt_preview.bind("<<Modified>>", self.on_text_modified)

        # Voice & audio controls
        audio_card = ttk.Frame(main_frame, style="Card.TFrame", padding=12)
        audio_card.pack(fill=tk.X, pady=(0, 10))

        controls_grid = ttk.Frame(audio_card, style="Card.TFrame")
        controls_grid.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(controls_grid, text="Voice:", style="Card.TLabel").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        voice_names = [v["name"] for v in self.voices]
        self.cb_voice = ttk.Combobox(controls_grid, values=voice_names, state="readonly", width=44)
        self.cb_voice.grid(row=0, column=1, columnspan=3, sticky=tk.W, padx=5, pady=2)
        self.select_saved_voice()
        self.cb_voice.bind("<<ComboboxSelected>>", self.on_voice_change)

        self.btn_preview_voice = ttk.Button(controls_grid, text="🔊 Preview Voice", command=self.action_preview_voice)
        self.btn_preview_voice.grid(row=0, column=4, sticky=tk.W, padx=10, pady=2)

        ttk.Label(controls_grid, text="Speed (WPM):", style="Card.TLabel").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.slider_speed = ttk.Scale(controls_grid, from_=100, to=300, length=200,
                                      value=self.settings.get("speed", 175), command=self.on_speed_change)
        self.slider_speed.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        self.slider_speed.bind("<ButtonRelease-1>", lambda e: self.invalidate_audio())
        self.lbl_speed_val = ttk.Label(controls_grid, text=f"{int(self.slider_speed.get())}", style="Card.TLabel")
        self.lbl_speed_val.grid(row=1, column=2, sticky=tk.W, padx=2, pady=2)

        ttk.Label(controls_grid, text="Volume:", style="Card.TLabel").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.slider_volume = ttk.Scale(controls_grid, from_=0, to=100, length=200,
                                       value=float(self.settings.get("volume", 0.9)) * 100, command=self.on_volume_change)
        self.slider_volume.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        self.lbl_vol_val = ttk.Label(controls_grid, text=f"{int(self.slider_volume.get())}%", style="Card.TLabel")
        self.lbl_vol_val.grid(row=2, column=2, sticky=tk.W, padx=2, pady=2)

        btn_bar = ttk.Frame(audio_card, style="Card.TFrame")
        btn_bar.pack(fill=tk.X, pady=5)

        self.btn_play = ttk.Button(btn_bar, text="▶ Play", style="Success.TButton", command=self.action_play)
        self.btn_play.pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="⏸ Pause", command=self.action_pause).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="▶ Resume", command=self.action_resume).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="⏹ Stop", command=self.action_stop).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="🔄 Restart", command=self.action_restart).pack(side=tk.LEFT, padx=3)

        # Progress & export
        progress_card = ttk.Frame(main_frame, style="Card.TFrame", padding=12)
        progress_card.pack(fill=tk.X, pady=(0, 8))

        self.lbl_progress_status = ttk.Label(progress_card, text="Ready", style="Card.TLabel", font=("Segoe UI", 9, "bold"))
        self.lbl_progress_status.pack(anchor=tk.W)

        self.progress_bar = ttk.Progressbar(progress_card, orient=tk.HORIZONTAL, mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=5)

        action_bar = ttk.Frame(progress_card, style="Card.TFrame")
        action_bar.pack(fill=tk.X, pady=(5, 0))

        self.btn_export = ttk.Button(action_bar, text="💾 Convert & Save Audio", style="Primary.TButton", command=self.action_export_audio)
        self.btn_export.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_cancel = ttk.Button(action_bar, text="✖ Cancel", command=self.action_cancel, state=tk.DISABLED)
        self.btn_cancel.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(action_bar, text="📂 Open Audio Folder", command=open_audio_folder).pack(side=tk.LEFT)

        footer = ttk.Frame(main_frame)
        footer.pack(fill=tk.X, pady=(5, 0))
        self.lbl_status_log = ttk.Label(
            footer, text="System ready.", foreground="#8bb7ff",
            font=("Segoe UI", 9)
        )
        self.lbl_status_log.pack(side=tk.LEFT, anchor=tk.W)
        ttk.Label(
            footer, text="Created by Maxwell", style="SubHeader.TLabel"
        ).pack(side=tk.RIGHT, anchor=tk.E)

    def select_saved_voice(self):
        saved = self.settings.get("voice_id") or DEFAULT_VOICE_ID
        idx = next((i for i, v in enumerate(self.voices) if v["id"] == saved), 0)
        if self.voices:
            self.cb_voice.current(idx)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def bind_shortcuts(self):
        self.root.bind("<Control-o>", lambda e: self.upload_pdf())
        self.root.bind("<Control-O>", lambda e: self.upload_pdf())
        self.root.bind("<space>", self.on_space)
        self.root.bind("<Escape>", lambda e: self.action_stop())

    def on_space(self, event):
        # Do not hijack the space bar while the user is typing in the text box
        if isinstance(event.widget, (tk.Text, ttk.Combobox, tk.Entry)):
            return
        self.toggle_play_pause()
        return "break"

    def update_status(self, text: str, is_error: bool = False):
        color = "#f38ba8" if is_error else "#89b4fa"
        self.lbl_status_log.configure(text=text, foreground=color)

    def on_speed_change(self, val):
        self.lbl_speed_val.configure(text=f"{int(float(val))}")

    def on_volume_change(self, val):
        vol_val = int(float(val))
        self.lbl_vol_val.configure(text=f"{vol_val}%")
        self.audio_manager.set_volume(vol_val / 100.0)

    def on_voice_change(self, _event=None):
        self.invalidate_audio()
        self.update_status("Voice changed. Use Preview Voice to hear it.")

    def on_text_modified(self, _event=None):
        if self.txt_preview.edit_modified():
            self.invalidate_audio()
            self.txt_preview.edit_modified(False)

    def invalidate_audio(self):
        """Forget the last generated file so Play regenerates it with the new settings/text."""
        self.current_audio_path = None

    def get_selected_voice_id(self) -> str:
        idx = self.cb_voice.current()
        if 0 <= idx < len(self.voices):
            return self.voices[idx]["id"]
        return ""

    def update_progress_bar(self, percent: int, text: str):
        self.cancel_progress_animation()
        start = float(self.progress_bar["value"])
        target = max(0, min(100, int(percent)))
        started_at = time.monotonic()
        duration = 0.2
        self.lbl_progress_status.configure(text=f"{text} ({target}%)")

        def animate():
            progress = min((time.monotonic() - started_at) / duration, 1.0)
            eased = 1 - (1 - progress) ** 3
            self.progress_bar["value"] = start + (target - start) * eased
            if progress < 1:
                self._progress_animation_id = self.root.after(16, animate)
            else:
                self.progress_bar["value"] = target
                self._progress_animation_id = None

        animate()

    def cancel_progress_animation(self):
        if self._progress_animation_id is not None:
            self.root.after_cancel(self._progress_animation_id)
            self._progress_animation_id = None

    def set_busy(self, busy: bool):
        self.is_processing = busy
        self.btn_export.configure(state=tk.DISABLED if busy else tk.NORMAL)
        self.btn_preview_voice.configure(state=tk.DISABLED if busy else tk.NORMAL)
        self.btn_cancel.configure(state=tk.NORMAL if busy else tk.DISABLED)

    # ------------------------------------------------------------------ #
    # PDF & text actions
    # ------------------------------------------------------------------ #
    def upload_pdf(self):
        file_path = filedialog.askopenfilename(
            title="Select PDF Document",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
        )
        if not file_path:
            return

        pdf_path = Path(file_path)
        self.current_pdf_path = pdf_path
        self.lbl_pdf_name.configure(text=pdf_path.name)
        self.update_status(f"Extracting text from {pdf_path.name}...")
        self.invalidate_audio()

        def bg_extract():
            def progress_cb(current, total):
                pct = int((current / total) * 100)
                self.root.after(0, lambda: self.update_progress_bar(pct, f"Extracting page {current} of {total}..."))

            try:
                text, stats, is_scanned, ocr_msg = extract_pdf_data(str(pdf_path), progress_cb)
            except Exception as e:
                self.root.after(0, lambda: self.update_status(f"Could not read PDF: {e}", is_error=True))
                return

            def update_ui():
                self.extracted_text = text
                self.txt_preview.delete("1.0", tk.END)
                self.txt_preview.insert(tk.END, text)
                self.txt_preview.edit_modified(False)

                self.lbl_pages.configure(text=f"Pages: {stats['pages']}")
                self.lbl_words.configure(text=f"Words: {stats['words']:,}")
                self.lbl_chars.configure(text=f"Characters: {stats['chars']:,}")

                self.update_progress_bar(100, "Extraction complete")
                self.lbl_progress_status.configure(text="Extraction complete")

                if is_scanned and ocr_msg:
                    messagebox.showinfo("Scanned PDF Info", ocr_msg)

                self.update_status(f"Extracted {stats['words']:,} words from {pdf_path.name}")

            self.root.after(0, update_ui)

        threading.Thread(target=bg_extract, daemon=True).start()

    def action_clean_text(self):
        raw = self.txt_preview.get("1.0", tk.END)
        if not raw.strip():
            return
        cleaned = clean_pdf_text(raw)
        self.extracted_text = cleaned
        self.txt_preview.delete("1.0", tk.END)
        self.txt_preview.insert(tk.END, cleaned)

        self.lbl_words.configure(text=f"Words: {len(cleaned.split()):,}")
        self.lbl_chars.configure(text=f"Characters: {len(cleaned):,}")
        self.update_status("Text cleaned and normalized.")

    def copy_text(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.txt_preview.get("1.0", tk.END))
        self.update_status("Text copied to clipboard.")

    def clear_text(self):
        self.txt_preview.delete("1.0", tk.END)
        self.extracted_text = ""
        self.lbl_pages.configure(text="Pages: 0")
        self.lbl_words.configure(text="Words: 0")
        self.lbl_chars.configure(text="Characters: 0")
        self.update_status("Text cleared.")

    # ------------------------------------------------------------------ #
    # Voice preview
    # ------------------------------------------------------------------ #
    def action_preview_voice(self):
        if self.is_processing:
            return
        voice_id = self.get_selected_voice_id()
        speed = int(self.slider_speed.get())
        volume = self.slider_volume.get() / 100.0
        out = Path(tempfile.gettempdir()) / f"pdf_audio_preview_{int(time.time() * 1000)}{output_extension_for(voice_id)}"

        self.set_busy(True)
        self.btn_cancel.configure(state=tk.DISABLED)
        self.cancel_event.clear()
        self.audio_manager.stop()
        self.update_status("Preparing voice preview...")

        def bg_preview():
            path, msg = generate_tts_audio(PREVIEW_TEXT, out, voice_id=voice_id, rate=speed, volume=volume)

            def done():
                self.set_busy(False)
                if path and path.exists():
                    self.preview_files.append(path)
                    self.audio_manager.load(path)
                    self.audio_manager.set_volume(self.slider_volume.get() / 100.0)
                    self.audio_manager.play()
                    self.update_status("Playing voice preview.")
                else:
                    self.update_status(f"Preview failed: {msg}", is_error=True)

            self.root.after(0, done)

        threading.Thread(target=bg_preview, daemon=True).start()

    # ------------------------------------------------------------------ #
    # Conversion
    # ------------------------------------------------------------------ #
    def action_cancel(self):
        self.cancel_event.set()
        self.update_status("Canceling...")

    def action_export_audio(self, autoplay: bool = False):
        if self.is_processing:
            return
        text = self.txt_preview.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Empty Text", "Please upload a PDF or enter text before generating audio.")
            return

        voice_id = self.get_selected_voice_id()
        pdf_name = self.current_pdf_path.name if self.current_pdf_path else "Spoken_Document.pdf"
        output_path = get_unique_audio_path(pdf_name, output_extension_for(voice_id))

        speed = int(self.slider_speed.get())
        volume = self.slider_volume.get() / 100.0

        self.set_busy(True)
        self.cancel_event.clear()
        self.audio_manager.stop()
        self.cancel_progress_animation()
        self.progress_bar["value"] = 0

        def bg_generate():
            def progress_cb(current, total):
                pct = int((current / total) * 100)
                self.root.after(0, lambda: self.update_progress_bar(pct, f"Generating audio part {current} / {total}"))

            final_path, msg = generate_tts_audio(
                text=text,
                output_path=output_path,
                voice_id=voice_id,
                rate=speed,
                volume=volume,
                progress_callback=progress_cb,
                cancel_event=self.cancel_event
            )

            def on_done():
                self.set_busy(False)
                if final_path and final_path.exists():
                    self.current_audio_path = final_path
                    rel = f"audio/{final_path.name}"
                    self.update_progress_bar(100, "Conversion complete")
                    self.lbl_progress_status.configure(text="Conversion complete")
                    self.update_status(f"Audio saved: {rel}. {msg}")
                    self.audio_manager.load(final_path)
                    self.audio_manager.set_volume(volume)
                    if autoplay:
                        self.audio_manager.play()
                    else:
                        messagebox.showinfo("Conversion Complete", f"Audio saved successfully:\n{rel}\n\n{msg}")
                else:
                    self.lbl_progress_status.configure(text="Stopped")
                    self.update_status(f"Audio generation stopped: {msg}", is_error=True)

            self.root.after(0, on_done)

        threading.Thread(target=bg_generate, daemon=True).start()

    # ------------------------------------------------------------------ #
    # Playback
    # ------------------------------------------------------------------ #
    def action_play(self):
        if not self.current_audio_path or not self.current_audio_path.exists():
            # Nothing generated for the current text/voice yet: convert, then play automatically
            self.action_export_audio(autoplay=True)
            return

        if self.audio_manager.current_file != self.current_audio_path:
            self.audio_manager.load(self.current_audio_path)

        self.audio_manager.set_volume(self.slider_volume.get() / 100.0)
        self.audio_manager.play()
        self.update_status(f"Playing: audio/{self.current_audio_path.name}")

    def action_pause(self):
        self.audio_manager.pause()
        self.update_status("Playback paused.")

    def action_resume(self):
        self.audio_manager.resume()
        self.update_status("Playback resumed.")

    def action_stop(self):
        self.audio_manager.stop()
        self.update_status("Playback stopped.")

    def action_restart(self):
        self.audio_manager.restart()
        self.update_status("Playback restarted.")

    def toggle_play_pause(self):
        if self.audio_manager.is_playing:
            if self.audio_manager.is_paused:
                self.action_resume()
            else:
                self.action_pause()
        else:
            self.action_play()

    def monitor_audio_status(self):
        if not self.is_processing:
            if self.audio_manager.check_busy():
                self.lbl_progress_status.configure(text="▶ Audio Playing...")
            elif self.audio_manager.is_paused:
                self.lbl_progress_status.configure(text="⏸ Audio Paused")
        self.root.after(500, self.monitor_audio_status)

    # ------------------------------------------------------------------ #
    # Shutdown
    # ------------------------------------------------------------------ #
    def on_close(self):
        self.settings.update({
            "voice_id": self.get_selected_voice_id(),
            "speed": int(self.slider_speed.get()),
            "volume": round(self.slider_volume.get() / 100.0, 2),
        })
        save_settings(self.settings)
        self.cancel_event.set()
        self.cancel_progress_animation()
        self.audio_manager.stop()
        for f in self.preview_files:
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass
        self.root.destroy()
