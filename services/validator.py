"""
Validation Service (Optional Execution)
=========================================
Performs validation checks on extracted invoice data.
Only executed when enable_validation=True.

Checks:
- PAN format validation
- GST format validation
- Date normalization
- Amount consistency (subtotal + tax ≈ total)
- Per-field confidence scoring
"""

import re
from datetime import datetime
from typing import Optional


# PAN: 5 uppercase letters, 4 digits, 1 uppercase letter
PAN_REGEX = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")

# GSTIN: 2 digits, 5 uppercase letters, 4 digits, 1 letter, 1 digit, Z, 1 alphanumeric
GSTIN_REGEX = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]$")

# Common date formats for normalization
DATE_FORMATS = [
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y",
    "%Y/%m/%d", "%Y-%m-%d", "%Y.%m.%d",
    "%d/%m/%y", "%d-%m-%y",
    "%d %b %Y", "%d %B %Y",
    "%b %d, %Y", "%B %d, %Y",
    "%b %d %Y", "%B %d %Y",
]


def validate_extraction(extracted: dict, ocr_data: dict) -> dict:
    """
    Run all validation checks on extracted data.

    Args:
        extracted: Dict of extracted invoice fields.
        ocr_data: Original OCR data with word-level confidence.

    Returns:
        Validation result dict with status, confidence_score, and field_level.
    """
    field_validations = {}
    all_passed = True

    # ── PAN format check ──────────────────────────────────────
    pan = extracted.get("pan_number")
    if pan:
        is_valid = bool(PAN_REGEX.match(pan))
        field_validations["pan_number"] = {
            "valid": is_valid,
            "value": pan,
            "note": "Valid PAN format" if is_valid else "Invalid PAN format (expected: ABCDE1234F)",
        }
        if not is_valid:
            all_passed = False
    else:
        field_validations["pan_number"] = {
            "valid": None,
            "value": None,
            "note": "PAN not found in document",
        }

    # ── GST format check ──────────────────────────────────────
    gstin = extracted.get("gstin")
    if gstin:
        is_valid = bool(GSTIN_REGEX.match(gstin))
        field_validations["gstin"] = {
            "valid": is_valid,
            "value": gstin,
            "note": "Valid GSTIN format" if is_valid else "Invalid GSTIN format (expected: 22AAAAA0000A1Z5)",
        }
        if not is_valid:
            all_passed = False
    else:
        field_validations["gstin"] = {
            "valid": None,
            "value": None,
            "note": "GSTIN not found in document",
        }

    # ── Date normalization ────────────────────────────────────
    date = extracted.get("date")
    normalized_date = _normalize_date(date) if date else None
    if date:
        field_validations["date"] = {
            "valid": normalized_date is not None,
            "value": date,
            "normalized": normalized_date,
            "note": f"Normalized to {normalized_date}" if normalized_date else "Could not parse date format",
        }
        if normalized_date is None:
            all_passed = False
    else:
        field_validations["date"] = {
            "valid": None,
            "value": None,
            "note": "Date not found in document",
        }

    # ── Invoice number check ──────────────────────────────────
    inv_num = extracted.get("invoice_number")
    field_validations["invoice_number"] = {
        "valid": inv_num is not None and len(str(inv_num)) >= 2,
        "value": inv_num,
        "note": "Invoice number found" if inv_num else "Invoice number not found",
    }

    # ── Amount consistency check ──────────────────────────────
    amount_valid, amount_note = _check_amount_consistency(extracted)
    field_validations["amount_consistency"] = {
        "valid": amount_valid,
        "note": amount_note,
        "subtotal": extracted.get("subtotal"),
        "tax": extracted.get("tax"),
        "total": extracted.get("total"),
    }
    if amount_valid is False:
        all_passed = False

    # ── Vendor name check ─────────────────────────────────────
    vendor = extracted.get("vendor_name")
    field_validations["vendor_name"] = {
        "valid": vendor is not None and len(str(vendor)) >= 2,
        "value": vendor,
        "note": "Vendor name detected" if vendor else "Vendor name not found",
    }

    # ── Confidence score ──────────────────────────────────────
    confidence_score = _compute_confidence(ocr_data, extracted)

    # Determine overall status
    status = "passed" if all_passed else "failed"

    return {
        "status": status,
        "confidence_score": round(confidence_score, 2),
        "field_level": field_validations,
    }


def _normalize_date(date_str: str) -> Optional[str]:
    """Attempt to normalize a date string to YYYY-MM-DD format."""
    if not date_str:
        return None

    cleaned = date_str.strip().replace(",", "").strip()

    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def _check_amount_consistency(extracted: dict) -> tuple:
    """
    Check if subtotal + tax ≈ total (within ±1.0 tolerance).
    Returns (is_valid: bool | None, note: str).
    """
    subtotal = _to_float(extracted.get("subtotal"))
    tax = _to_float(extracted.get("tax"))
    total = _to_float(extracted.get("total"))

    if total is None:
        return None, "Total amount not found — cannot verify"

    if subtotal is None and tax is None:
        return None, "Subtotal and tax not found — cannot verify consistency"

    if subtotal is not None and tax is not None:
        expected_total = subtotal + tax
        diff = abs(expected_total - total)
        if diff <= 1.0:
            return True, f"Consistent: {subtotal} + {tax} = {expected_total} ≈ {total}"
        else:
            return False, f"Inconsistent: {subtotal} + {tax} = {expected_total} ≠ {total} (diff: {diff:.2f})"

    if subtotal is not None:
        if subtotal <= total:
            return None, f"Subtotal ({subtotal}) ≤ Total ({total}), tax not found for full check"
        else:
            return False, f"Subtotal ({subtotal}) > Total ({total}) — suspicious"

    return None, "Insufficient data for full consistency check"


def _to_float(value) -> Optional[float]:
    """Safely convert a value to float."""
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return None


def _compute_confidence(ocr_data: dict, extracted: dict) -> float:
    """
    Compute an overall confidence score based on:
    - Average OCR word confidence
    - Percentage of fields successfully extracted
    """
    words = ocr_data.get("words", [])

    # OCR confidence (average)
    if words:
        ocr_confidences = [w["conf"] for w in words if w["conf"] > 0]
        avg_ocr_conf = sum(ocr_confidences) / len(ocr_confidences) if ocr_confidences else 0
    else:
        avg_ocr_conf = 0

    # Field extraction success rate
    fields = ["invoice_number", "date", "vendor_name", "total"]
    found = sum(1 for f in fields if extracted.get(f) is not None)
    extraction_rate = (found / len(fields)) * 100

    # Weighted combination: 60% OCR confidence, 40% extraction rate
    confidence = (avg_ocr_conf * 0.6) + (extraction_rate * 0.4)

    return min(confidence, 100.0)
