import re
from collections import Counter

MATH_SYMBOLS = {
    'α': ' alpha ', 'β': ' beta ', 'γ': ' gamma ', 'δ': ' delta ', 'ε': ' epsilon ',
    'ζ': ' zeta ', 'η': ' eta ', 'θ': ' theta ', 'ι': ' iota ', 'κ': ' kappa ',
    'λ': ' lambda ', 'μ': ' mu ', 'ν': ' nu ', 'ξ': ' xi ', 'ο': ' omicron ',
    'π': ' pi ', 'ρ': ' rho ', 'σ': ' sigma ', 'τ': ' tau ', 'υ': ' upsilon ',
    'φ': ' phi ', 'χ': ' chi ', 'ψ': ' psi ', 'ω': ' omega ',
    'Δ': ' Delta ', 'Σ': ' Sum of ', 'Ω': ' Omega ',
    '±': ' plus or minus ', '≠': ' is not equal to ',
    '≈': ' is approximately equal to ', '≤': ' is less than or equal to ',
    '≥': ' is greater than or equal to ', '∞': ' infinity ',
    '√': ' square root of ', '∫': ' integral of ',
    '×': ' times ', '÷': ' divided by ', '−': ' minus ', '→': ' goes to ',
    '°': ' degrees ', '²': ' squared ', '³': ' cubed ', '%': ' percent ',
}

# Characters that PDFs often contain and speech engines mispronounce
CHAR_FIXES = {
    '\u00ad': '',      # soft hyphen
    '\ufb01': 'fi', '\ufb02': 'fl', '\ufb00': 'ff', '\ufb03': 'ffi', '\ufb04': 'ffl',
    '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
    '\u2013': ', ', '\u2014': ', ', '\u2022': '. ', '\u00a0': ' ', '\u200b': '',
}

UNIT_FRACTIONS = {
    'm/s': 'meters per second', 'km/h': 'kilometers per hour', 'rad/s': 'radians per second',
    'mol/L': 'moles per liter', 'N/m': 'newtons per meter', 'kg/m': 'kilograms per meter',
}

NOT_FRACTIONS = {'and/or', 'he/she', 'his/her', 'yes/no', 'on/off', 'true/false', 'input/output'}


def _fraction_repl(m: re.Match) -> str:
    whole = f"{m.group(1)}/{m.group(2)}"
    if whole.lower() in NOT_FRACTIONS:
        return whole.lower().replace("/", " ") if m.group(1).lower() == "and" else f"{m.group(1)} or {m.group(2)}"
    return f"{m.group(1)} over {m.group(2)}"


def normalize_math_text(text: str) -> str:
    """
    Normalizes mathematical and scientific expressions for natural speech synthesis.
    Example: σ = F/A -> sigma equals F over A
    """
    for unit, spoken in UNIT_FRACTIONS.items():
        text = re.sub(rf'(?<![\w/]){re.escape(unit)}(?![\w/])', spoken, text)

    for sym, spoken in MATH_SYMBOLS.items():
        text = text.replace(sym, spoken)

    # Short simple fractions like F/A, 1/2, a/b (not dates, URLs or long words)
    text = re.sub(r'(?<![\w/])([A-Za-z0-9]{1,3})\s*/\s*([A-Za-z0-9]{1,3})(?![\w/])', _fraction_repl, text)

    # Equals sign
    text = re.sub(r'\s*=\s*', ' equals ', text)

    # Simple powers: x^2 -> x squared, x^n -> x to the power n
    text = re.sub(r'\^\s*2\b', ' squared ', text)
    text = re.sub(r'\^\s*3\b', ' cubed ', text)
    text = re.sub(r'\^\s*\{?(\w+)\}?', r' to the power \1 ', text)

    return text


def _remove_repeated_headers(lines: list[str]) -> list[str]:
    """Drops short lines that repeat many times (running headers/footers)."""
    counts = Counter(l.strip() for l in lines if 3 < len(l.strip()) < 80)
    repeated = {l for l, c in counts.items() if c >= 4 and not l.endswith(('.', '?', '!', ':'))}
    return [l for l in lines if l.strip() not in repeated]


def clean_pdf_text(raw_text: str) -> str:
    """
    Cleans raw PDF text for speech: removes hyphenation, headers/footers, page numbers,
    citations, URLs and odd characters, then normalizes mathematical notation.
    """
    if not raw_text:
        return ""

    text = raw_text.replace('\r\n', '\n').replace('\r', '\n')

    for bad, good in CHAR_FIXES.items():
        text = text.replace(bad, good)

    # Join words broken across lines ("engi-\nneering" -> "engineering")
    text = re.sub(r'(\w)-\n\s*([a-z])', r'\1\2', text)

    # Page numbers / page markers
    text = re.sub(r'(?im)^\s*(page\s+\d+(\s+of\s+\d+)?|\d+)\s*$', '', text)
    text = re.sub(r'(?m)^\s*---\s*\d+\s*---\s*$', '', text)

    # Citations like [12] or [3, 4], and web links
    text = re.sub(r'\[\s*\d+(\s*[,\-–]\s*\d+)*\s*\]', '', text)
    text = re.sub(r'https?://\S+|www\.\S+', ' link ', text)

    # Repeated running headers/footers
    text = "\n".join(_remove_repeated_headers(text.split('\n')))

    # Merge hard-wrapped lines into paragraphs, keep blank lines as paragraph breaks
    paragraphs, current = [], []
    for line in text.split('\n'):
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(stripped)
    if current:
        paragraphs.append(" ".join(current))

    text = "\n\n".join(paragraphs)

    text = normalize_math_text(text)

    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' +([,.;:!?])', r'\1', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()
