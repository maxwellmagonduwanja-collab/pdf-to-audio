import fitz  # PyMuPDF
from text_cleaner import clean_pdf_text

# Optional pytesseract & Pillow support for scanned PDFs
try:
    import pytesseract
    from PIL import Image
    HAS_OCR = True
except ImportError:
    HAS_OCR = False


def extract_pdf_data(pdf_path: str, progress_callback=None) -> tuple[str, dict, bool, str]:
    """
    Extracts text from a PDF file.
    Returns: (cleaned_text, stats_dict, is_scanned, warning_message)
    """
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    raw_text_chunks = []

    for page_idx in range(total_pages):
        page = doc[page_idx]
        text = page.get_text("text")
        raw_text_chunks.append(text)

        if progress_callback:
            progress_callback(page_idx + 1, total_pages)

    combined_raw = "\n\n".join(raw_text_chunks)
    cleaned_text = clean_pdf_text(combined_raw)

    words = cleaned_text.split()
    word_count = len(words)
    char_count = len(cleaned_text)
    avg_words_per_page = word_count / max(total_pages, 1)

    is_scanned = avg_words_per_page < 5
    ocr_message = ""

    # If document appears scanned and OCR is requested
    if is_scanned:
        if HAS_OCR:
            ocr_text_chunks = []
            ocr_message = "Scanned PDF detected. Running OCR processing..."
            for page_idx in range(total_pages):
                page = doc[page_idx]
                pix = page.get_pixmap(dpi=150)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                ocr_page_text = pytesseract.image_to_string(img)
                ocr_text_chunks.append(ocr_page_text)

                if progress_callback:
                    progress_callback(page_idx + 1, total_pages)

            cleaned_text = clean_pdf_text("\n\n".join(ocr_text_chunks))
            words = cleaned_text.split()
            word_count = len(words)
            char_count = len(cleaned_text)
            ocr_message = "OCR processing completed successfully."
        else:
            ocr_message = (
                "This PDF appears to contain scanned pages.\n\n"
                "OCR is required to extract text from images.\n"
                "To enable OCR support, install pytesseract and Tesseract-OCR:\n"
                "pip install pytesseract pillow"
            )

    doc.close()

    stats = {
        "pages": total_pages,
        "words": word_count,
        "chars": char_count
    }

    return cleaned_text, stats, is_scanned, ocr_message
