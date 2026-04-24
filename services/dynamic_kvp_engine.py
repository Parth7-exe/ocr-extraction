"""
Dynamic Key-Value Extraction Engine
=====================================
Strict Two-Stage Pipeline:

  STAGE 1: Raw Text Cleaning & Grouping
    - Merges OCR word tokens into clean, readable lines
    - Uses Y-coordinate proximity from layout engine
    - Maintains reading order (top→bottom, left→right)
    - Produces a list of clean text lines — NO extraction here

  STAGE 2: Structured Key-Value Extraction
    - Takes clean lines from Stage 1
    - Extracts meaningful key-value pairs via pattern matching
    - Detects common entities (name, gender, date, ID)
    - Filters OCR noise, single words, broken tokens
    - Returns a flat dict of normalized keys → values
"""

import re
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════
#  STAGE 1:  RAW TEXT CLEANING + GROUPING
# ═══════════════════════════════════════════════════════════════════

def stage1_clean_and_group(ocr_data: dict, layout: dict) -> list:
    """
    Merge raw OCR tokens into clean lines and normalize digits.
    """
    def normalize_digits(text: str) -> str:
        devanagari_digits = "०१२३४५६७८९"
        for i, d in enumerate(devanagari_digits):
            text = text.replace(d, str(i))
        return text

    clean_lines = []
    
    # Prefer layout-engine lines for spatial accuracy
    layout_lines = layout.get("lines", [])
    if layout_lines:
        for line_obj in layout_lines:
            text = normalize_digits(line_obj.get("text", "").strip())
            if text:
                clean_lines.append(text)
    
    # If layout found significantly fewer lines than raw_text, fallback to raw_text
    # to ensure no data (like names/dates) is lost due to layout grouping errors.
    raw_text = ocr_data.get("raw_text", "")
    raw_lines = [normalize_digits(l.strip()) for l in raw_text.split("\n") if l.strip()]
    
    if len(raw_lines) > len(clean_lines):
        return raw_lines
        
    return clean_lines or raw_lines


# ═══════════════════════════════════════════════════════════════════
#  STAGE 2:  STRUCTURED KEY-VALUE EXTRACTION
# ═══════════════════════════════════════════════════════════════════

# --- Noise / header words to ignore as standalone entries ---
_NOISE_WORDS = {
    "of", "the", "and", "in", "is", "to", "for", "at", "by", "on",
    "a", "an", "or", "it", "as", "if", "no", "not", "be", "was",
    "are", "has", "had", "do", "did", "may", "can", "so", "up",
}

_HEADER_PHRASES = {
    "government of india", "republic of india", "india",
    "aadhaar", "unique identification authority",
    "my aadhaar my identity", "mera aadhaar meri pehchaan",
}


def stage2_extract_key_values(clean_lines: list) -> dict:
    """
    EXTRACT EVERYTHING:
    1. Entities (Name, DOB, ID, etc.)
    2. KV Patterns (KEY: VALUE)
    3. All remaining lines as sequential data
    """
    kv = {}
    used_indices = set()

    # Pass 1: Entity Detection
    _detect_entities(clean_lines, kv, used_indices)

    # Pass 2: Explicit Key-Value Patterns (Match anything with a colon/dash)
    kv_pattern = re.compile(r"^(.+?)\s*[:\-]\s*(.+)$")
    
    for i, line in enumerate(clean_lines):
        if i in used_indices:
            continue
        
        match = kv_pattern.match(line)
        if match:
            raw_key, raw_val = match.group(1).strip(), match.group(2).strip()
            n_key = _normalize_key(raw_key)

            # Lookahead for truncated dates (e.g. "DOB: 30/01" -> next line "1990" or "A99")
            if n_key in ("dob", "date") and len(raw_val) < 8:
                if (i + 1) < len(clean_lines) and (i + 1) not in used_indices:
                    next_line = clean_lines[i + 1].strip()
                    # If next line is a short alphanumeric chunk (like a year "1990" or OCR misread "A99")
                    if re.match(r"^[A-Za-z0-9]{2,4}$", next_line):
                        raw_val = f"{raw_val}/{next_line}"
                        used_indices.add(i + 1)

            n_val = _normalize_value(raw_val)
            if n_key and n_val:
                kv[n_key] = n_val
                used_indices.add(i)

    return kv


# ─── Entity Detection ─────────────────────────────────────────────

def _detect_entities(lines: list, kv: dict, used: set):
    """
    Detect common entities from clean lines when no explicit
    KEY: VALUE pattern was found for them.
    """

    # --- Date (DOB or standalone date) ---
    # Relaxed regex to handle spaces: "30 / 01 / 1990"
    date_regex = re.compile(
        r"\b([0-9]{1,4}\s*[/\\\-\.]\s*[0-9]{1,2}\s*[/\\\-\.]\s*[0-9]{2,4})\b"
    )
    for i, line in enumerate(lines):
        date_match = date_regex.search(line)
        if date_match:
            raw_date = date_match.group(0)
            # Remove spaces for normalization: "30 / 01 / 1990" -> "30/01/1990"
            clean_date = re.sub(r"\s+", "", raw_date)
            normalized = _try_normalize_date(clean_date)
            if normalized is None:
                continue

            # Determine key name from context
            line_upper = line.upper()
            prev_line_upper = lines[i - 1].upper() if i > 0 else ""
            if re.search(r"D[O0\.]*B|DATE OF BIRTH", line_upper) or re.search(r"D[O0\.]*B|DATE OF BIRTH", prev_line_upper):
                key = "dob"
            elif "date" not in kv and "dob" not in kv:
                key = "date"
            else:
                continue

            if key not in kv:
                kv[key] = normalized
                used.add(i)
                # Also mark previous line as used if it was just the DOB label
                if i > 0 and key == "dob" and re.match(r"^D[O0\.]*B\s*[:\-]?$", prev_line_upper.strip()):
                    used.add(i - 1)

    # --- Gender ---
    gender_regex = re.compile(r"\b(Male|Female|Transgender|पुरुष|महिला)\b", re.IGNORECASE)
    for i, line in enumerate(lines):
        if "gender" not in kv:
            g_match = gender_regex.search(line)
            if g_match:
                val = g_match.group(1).lower()
                if val in ("पुरुष", "male"):
                    kv["gender"] = "Male"
                elif val in ("महिला", "female"):
                    kv["gender"] = "Female"
                else:
                    kv["gender"] = val.capitalize()
                used.add(i)

    # --- 12-digit ID Number (Aadhaar pattern) ---
    # Relaxed spacing for ID to handle OCR noise like '1234.5678;9000'
    id_regex = re.compile(r"\b([0-9]{4})[^\w]*([0-9]{4})[^\w]*([0-9]{4})\b")
    for i, line in enumerate(lines):
        if "id_number" not in kv:
            id_match = id_regex.search(line)
            if id_match:
                kv["id_number"] = f"{id_match.group(1)} {id_match.group(2)} {id_match.group(3)}"
                used.add(i)

    # --- Name Detection ---
    if "name" not in kv:
        _detect_name(lines, kv, used)


def _detect_name(lines: list, kv: dict, used: set):
    """
    Detect name with support for 'Full Name' label hints.
    """
    # 1. Look for explicit "Full Name" or "Name" labels
    name_label_regex = re.compile(r"^(?:Full\s*)?Name\s*[:\-]?\s*(.+)$", re.IGNORECASE)
    for i, line in enumerate(lines):
        match = name_label_regex.match(line)
        if match:
            candidate = _clean_name_string(match.group(1))
            if candidate:
                kv["name"] = candidate
                used.add(i)
                return

    # 2. Heuristic fallback (lines above DOB/ID)
    anchor_idx = -1
    for i, line in enumerate(lines):
        if re.search(r"D[O0\.]*B|[0-9]{4}\s*[0-9]{4}\s*[0-9]{4}", line.upper()):
            anchor_idx = i
            break

    search_range = range(anchor_idx - 1, -1, -1) if anchor_idx > 0 else range(len(lines))
    for i in search_range:
        if i in used: continue
        line = lines[i]
        if _is_name_candidate(line):
            kv["name"] = _clean_name_string(line)
            used.add(i)
            return

def _clean_name_string(name: str) -> str:
    """Strip OCR noise characters from names."""
    # Remove characters often misread at the end/start of names (T, |, /, etc)
    # but only if they are isolated or look like noise.
    # For "SONIA SHARMAT", if T is a common misread of a border or line.
    name = re.sub(r"[\|\/\>\<\(\)\{\}\[\]\:]", "", name)
    # Strip single trailing capital letters that are often noise (like T from a line)
    # Only if the name already has 2 words.
    if len(name.split()) >= 2:
        name = re.sub(r"\s+[A-Z]$", "", name.strip())
    return name.strip()


def _is_name_candidate(text: str) -> bool:
    """Check if a line looks like a person's name."""
    text = text.strip()
    words = text.split()
    if len(words) < 1 or len(words) > 5:
        return False
    if re.search(r"\d", text):
        return False
    if text.lower().strip() in _HEADER_PHRASES:
        return False
    for phrase in _HEADER_PHRASES:
        if phrase in text.lower():
            return False
    if len(words) == 1 and words[0].lower() in _NOISE_WORDS:
        return False
    if not re.search(r"[A-Za-z]", text):
        return False
    return True


# ─── Normalization & Validation Helpers ───────────────────────────

def _normalize_key(key: str) -> str:
    """Convert 'Invoice No' → 'invoice_no'"""
    n = key.lower().strip()
    # Remove special characters except spaces
    n = re.sub(r"[^a-z0-9\s]", "", n)
    # Collapse whitespace to single underscore
    n = re.sub(r"\s+", "_", n.strip())
    n = n.strip("_")
    return n


def _normalize_value(value: str) -> str:
    """Clean value string; normalize dates; keep all characters."""
    # Convert Devanagari digits to English digits as a courtesy
    devanagari_digits = "०१२३४५६७८९"
    for i, d in enumerate(devanagari_digits):
        value = value.replace(d, str(i))

    val = value.strip()

    # Try date normalization
    date_normalized = _try_normalize_date(val)
    if date_normalized:
        return date_normalized

    # Strip leading/trailing punctuation noise
    val = re.sub(r"^[,.\-:;]+", "", val).strip()
    val = re.sub(r"[,.\-:;]+$", "", val).strip()
    return val


def _try_normalize_date(text: str) -> str | None:
    """Attempt to parse and normalize a date string to YYYY-MM-DD."""
    text = text.strip()
    for fmt in [
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%Y-%m-%d", "%Y/%m/%d",
        "%d/%b/%Y", "%d-%b-%Y",
        "%d/%m/%y", "%d-%m-%y",
    ]:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _is_meaningful(key: str, value: str) -> bool:
    """Keep everything for raw data extraction."""
    return bool(key and value)


# ═══════════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════════

def extract_dynamic_key_value_pairs(ocr_data: dict, layout: dict) -> dict:
    """
    Main entry point. Runs the strict two-stage pipeline:
      Stage 1 → Clean & group OCR tokens into lines
      Stage 2 → Extract structured key-value pairs
    """
    # STAGE 1: Clean text grouping
    clean_lines = stage1_clean_and_group(ocr_data, layout)

    # STAGE 2: Structured extraction
    kv_pairs = stage2_extract_key_values(clean_lines)

    return kv_pairs
