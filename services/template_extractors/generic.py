"""
Data Extraction Engine
=======================
Extracts structured invoice fields from OCR results using
three complementary strategies:

1. Regex pattern matching
2. Keyword anchor detection
3. Positional logic (region-aware extraction)

Extracted fields:
- invoice_number
- date
- vendor_name
- subtotal
- tax
- total
- pan_number
- gstin
"""

import re
from typing import Optional


# ═══════════════════════════════════════════════════════════════
# Regex Pattern Banks
# ═══════════════════════════════════════════════════════════════

INVOICE_NUMBER_PATTERNS = [
    # Most specific first: "Invoice No." / "Invoice No:" followed by an alphanumeric code that ENDS in digits
    r"(?:Invoice|Inv|Bill)\s*(?:No\.?|Number|#|Num)\s*[:.#\-]?\s*([A-Za-z]{1,6}[\-/]?\d{3,}[A-Za-z0-9\-/]*)",
    # Plain "Invoice:" with a value that contains at least one digit
    r"(?:Invoice|Inv)\s*[:.#\-]\s*([A-Za-z0-9\-/]*\d+[A-Za-z0-9\-/]*)",
    # Hash-prefixed numbers (e.g., #HR2025-26-116532)
    r"#\s*([A-Za-z0-9]{2,15}[-/][A-Za-z0-9\-/]+)",
    r"#\s*([A-Za-z0-9]{4,})",
    # Bare INV-xxx patterns
    r"\b(INV[-/]?\d{4,})\b",
]

DATE_PATTERNS = [
    # DD-Mon-YY or DD-Mon-YYYY  e.g. "9-Feb-26", "15-Mar-2024"
    r"(\d{1,2}[-/](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/]\d{2,4})",
    # DD/MM/YYYY or DD-MM-YYYY (numeric months)
    r"\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\b",
    # YYYY/MM/DD or YYYY-MM-DD
    r"\b(\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2})\b",
    # Month name patterns: 15 Mar 2024, March 15 2024
    r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*,?\s*\d{2,4})",
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}\s*,?\s*\d{2,4})",
]

# Currency symbol pattern — heavily cleaned up because Rupee misreads 
# are now normalized at the OCR core service across all files and engines.
CURRENCY_PATTERN = r"(?:[\$₹€£%]|Rs\.?|INR)?"


AMOUNT_PATTERNS = {
    "subtotal": [
        r"(?:Sub\s*[-]?\s*Total|Subtotal)\s*[:.=]?\s*" + CURRENCY_PATTERN + r"\s*([\d,]+\.?\d*)",
    ],
    "tax": [
        # Use \bGST\b so that GSTIN does NOT accidentally match this pattern.
        # Negative lookahead (?!\s*(?:Amount|#|No\.?|Id|\d)) prevents matching 'Tax #:'
        r"(?:Tax(?!\s*(?:Amount|#|No\.?|Id|\d))|\bGST\b|CGST|SGST|IGST|VAT)[\s\d]*%?\s*(?:\([^)]*\))?\s*[:.=]?\s*" + CURRENCY_PATTERN + r"\s*([\d,]+\.?\d*)",
        r"(?:Tax\s*Amount)\s*[:.=]?\s*" + CURRENCY_PATTERN + r"\s*([\d,]+\.?\d*)",
    ],
    "total": [
        r"(?:Grand\s*Total|Total\s*(?:Amount|Due|Payable)?|Amount\s*Due|Net\s*Amount|Balance\s*Due)\s*[:.=]?\s*" + CURRENCY_PATTERN + r"\s*([\d,]+\.?\d*)",
        r"=\s*" + CURRENCY_PATTERN + r"\s*([\d,]+\.?\d*)",   # "= 35,36,673.00" style totals
        r"(?:Total)\s*[:.=]?\s*" + CURRENCY_PATTERN + r"\s*([\d,]+\.?\d*)",
    ],
}

PAN_PATTERN = r"\b([A-Z]{5}\d{4}[A-Z])\b"
GSTIN_PATTERN = r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]{3})\b"

# Keywords that indicate vendor/company name locations
VENDOR_KEYWORDS = [
    "bill from", "from", "vendor", "supplier", "seller",
    "company", "sold by", "ship from",
]

DATE_KEYWORDS = [
    "date", "invoice date", "bill date", "dated", "issue date", "issued",
]


def extract_invoice_data(ocr_data: dict, layout: dict) -> dict:
    """
    Extract structured invoice data from OCR results and layout analysis.

    Args:
        ocr_data: Merged OCR result with 'words' and 'raw_text'.
        layout: Layout analysis result from layout_engine.

    Returns:
        Dict with extracted fields.
    """
    raw_text = ocr_data.get("raw_text", "")
    lines = layout.get("lines", [])
    regions = layout.get("regions", {})
    kv_pairs = layout.get("key_value_pairs", [])

    result = {
        "invoice_number": None,
        "date": None,
        "vendor_name": None,
        "subtotal": None,
        "tax": None,
        "total": None,
        "pan_number": None,
        "gstin": None,
    }

    # ── Strategy 1: Keyword anchors from key-value pairs ──────
    # High confidence structural anchoring should take priority over blind regex.
    _enhance_with_kv_pairs(result, kv_pairs)

    # ── Strategy 1.5: Multi-line header scan ──────────────────
    # Handles common Tally/Busy invoice layout where header labels and their
    # values appear on consecutive lines, e.g.:
    #   Line N:   "Invoice No.  Dated"
    #   Line N+1: "MUM1012/2025-26  9-Feb-26"
    _enhance_with_multiline_header(result, raw_text)

    # ── Strategy 2: Regex on full text ────────────────────────
    # Fallback to generic text scans if structural mapping failed.
    if not result["invoice_number"]:
        result["invoice_number"] = _extract_invoice_number(raw_text)
    if not result["date"]:
        result["date"] = _extract_date(raw_text)
    if not result["pan_number"]:
        result["pan_number"] = _extract_pattern(raw_text, PAN_PATTERN)
    if not result["gstin"]:
        result["gstin"] = _extract_pattern(raw_text, GSTIN_PATTERN)

    # Extract amounts using anchored regex (highly reliable due to keywords)
    for field, patterns in AMOUNT_PATTERNS.items():
        if not result[field]:
            for pattern in patterns:
                match = re.search(pattern, raw_text, re.IGNORECASE)
                if match:
                    result[field] = _clean_amount(match.group(1))
                    break


    # ── Strategy 3: Positional logic (region-aware) ───────────
    _enhance_with_position(result, regions, lines)

    return result


def _extract_invoice_number(text: str) -> Optional[str]:
    """Extract invoice number using regex patterns."""
    for pattern in INVOICE_NUMBER_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Return the captured group if available, otherwise full match
            return match.group(1) if match.lastindex else match.group(0)
    return None


def _extract_date(text: str) -> Optional[str]:
    """Extract date using regex patterns."""
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _extract_pattern(text: str, pattern: str) -> Optional[str]:
    """Extract first match for a given regex pattern."""
    match = re.search(pattern, text)
    return match.group(1) if match else None


def _clean_amount(amount_str: str) -> str:
    """
    Validate that amount_str represents a real number and return it
    with its original comma formatting preserved (e.g. '35,36,673.00').
    Commas are only stripped temporarily to validate the value.
    """
    stripped = amount_str.replace(",", "").strip()
    try:
        float(stripped)
        return amount_str.strip()   # Return original with commas intact
    except ValueError:
        return amount_str


def _enhance_with_kv_pairs(result: dict, kv_pairs: list) -> None:
    """Use detected key-value pairs to fill missing fields."""
    for kv in kv_pairs:
        key_lower = kv["key"].lower().strip()
        value = kv["value"].strip()

        if not value:
            continue

        # Invoice number
        if result["invoice_number"] is None:
            if any(k in key_lower for k in ["invoice no", "invoice #", "inv no", "bill no", "invoice number"]):
                result["invoice_number"] = value

        # Date
        if result["date"] is None:
            if any(k in key_lower for k in DATE_KEYWORDS) and "due" not in key_lower:
                result["date"] = value

        # Vendor name
        if result["vendor_name"] is None:
            if any(k in key_lower for k in VENDOR_KEYWORDS):
                result["vendor_name"] = value

        # Amounts
        if result["subtotal"] is None and "sub" in key_lower and "total" in key_lower:
            amt = _try_extract_amount(value)
            if amt:
                result["subtotal"] = amt

        if result["tax"] is None and any(k in key_lower for k in ["tax", "gst", "vat", "cgst", "sgst"]):
            amt = _try_extract_amount(value)
            if amt:
                result["tax"] = amt

        if result["total"] is None and "total" in key_lower and "sub" not in key_lower:
            amt = _try_extract_amount(value)
            if amt:
                result["total"] = amt


def _enhance_with_position(result: dict, regions: dict, lines: list) -> None:
    """Use positional layout information to fill remaining gaps."""
    header_lines = regions.get("header", [])
    footer_lines = regions.get("footer", [])

    # ── Vendor name: usually first meaningful line in header ──
    if result["vendor_name"] is None and header_lines:
        # Keywords that signal non-vendor content that may appear on the same
        # layout line due to a two-column invoice design.
        _VENDOR_TERMINATORS = re.compile(
            r"\s+(?:Invoice|Inv\.|Bill\s*No|Dated|GSTIN|PAN|Tel|Contact|State\s*Name)",
            re.IGNORECASE,
        )
        for line in header_lines[:5]:
            text = line["text"].strip()
            # Skip lines that look like dates, numbers, or known non-vendor keywords
            if (
                len(text) > 3
                and not re.match(r"^\d", text)
                and not re.match(r"(?:invoice|date|bill|tax|phone|email|fax|tel|client|customer|buyer|ship\s*to)", text, re.IGNORECASE)
                and not re.match(r"^[\d\s/\-\.,]+$", text)
                and "www." not in text.lower()
            ):
                # Truncate at the first terminator keyword (handles two-column layouts)
                m = _VENDOR_TERMINATORS.search(text)
                result["vendor_name"] = text[:m.start()].strip() if m else text
                break

    # ── Total: look in footer region if not found ──
    if result["total"] is None and footer_lines:
        for line in reversed(footer_lines):
            text = line["text"]
            if re.search(r"total", text, re.IGNORECASE):
                amt = _try_extract_amount(text)
                if amt:
                    result["total"] = amt
                    break

    # ── Date: search header region specifically ──
    if result["date"] is None and header_lines:
        header_text = " ".join(l["text"] for l in header_lines)
        result["date"] = _extract_date(header_text)


def _try_extract_amount(text: str) -> Optional[str]:
    """Try to extract a numeric amount from a text string."""
    # Re-use global CURRENCY_PATTERN to correctly isolate numbers and ignore misread '2 ' symbols
    match = re.search(CURRENCY_PATTERN + r"\s*([\d,]+\.?\d*)", text)
    if match:
        return _clean_amount(match.group(1))
    return None


def _enhance_with_multiline_header(result: dict, raw_text: str) -> None:
    """
    Looks for headers like 'Invoice No. Dated' and extracts values from the next line.
    This is extremely common in Tally and Busy accounting software invoices.
    """
    if result["invoice_number"] and result["date"]:
        return  # Already found both, no need to scan
        
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        # Look for a line containing both invoice and date concepts closely packed
        if ("invoice" in line_lower or "inv " in line_lower or "bill " in line_lower) and \
           ("date" in line_lower or "dt" in line_lower):
            
            # The values are highly likely on the next line
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                parts = re.split(r'\s{2,}|\t|\s+', next_line)
                
                # Check parts for Invoice Number
                if not result["invoice_number"] and len(parts) >= 1:
                    potential_inv = parts[0]
                    # It should be reasonably long to be an invoice number, not just "The"
                    if len(potential_inv) >= 3 and not potential_inv.lower() in ['the', 'this', 'for']:
                        result["invoice_number"] = potential_inv
                
                # Check parts for Date
                if not result["date"]:
                    # Try extracting date from the entire next line to be safe
                    extracted_date = _extract_date(next_line)
                    if extracted_date:
                        result["date"] = extracted_date
