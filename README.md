# PDF to Audio Reader

A Python desktop application that converts study PDFs into natural-sounding spoken audio.

## Features

- **Natural neural voices** (Jenny, Aria, Ava, Emma, Sonia, Libby, Asilia and more) powered by `edge-tts`. Needs an internet connection and saves as `.mp3`.
- **Offline voices**: any voice installed on your computer is also listed and saves as `.wav`. If the internet is down, the app switches to an offline voice automatically.
- **Voice preview** button to hear a voice before converting a whole document.
- Smart text cleaning: removes headers, footers, page numbers, citations and links, and reads maths symbols aloud.
- OCR for scanned PDFs (optional).
- Play, pause, resume, stop, restart, speed and volume controls.

## Installation

1. Clone or download the project.
2. Install the dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
3. (Optional, for scanned PDFs) install [Tesseract-OCR](https://github.com/tesseract-ocr/tesseract).
4. Run:
   ```bash
   python main.py
   ```

Converted audio is saved in the `audio/` folder next to the program.

## Tips

- Pick a voice with "(Neural)" in the name for the best quality.
- A speed of about 165 to 185 WPM sounds the most natural.
- Space plays/pauses, Esc stops, Ctrl+O opens a PDF.
