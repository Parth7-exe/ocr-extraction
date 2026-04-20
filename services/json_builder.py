"""
JSON Builder Service
=====================
Assembles the final structured JSON response from extracted data.

Two output modes:
- Validation OFF: Returns raw extracted data only.
- Validation ON:  Includes validation results and confidence score.
"""

from typing import Optional


def build_json_response(
    file_id: str,
    extracted: dict,
    raw_text: str,
    validation: Optional[dict] = None,
    engine: str = "tesseract",
    template: str = "generic",
) -> dict:
    """
    Build the final JSON output structure based on strictly defined schema.

    Returns:
        Structured JSON-serializable dict.
    """
    response = {
        "file_id": file_id,
        "invoice_details": {
            "invoice_number": extracted.get("invoice_number"),
            "date": extracted.get("date"),
        },
        "vendor_details": {
            "name": extracted.get("vendor_name"),
            # Including these as bonuses since they are extracted
            "pan_number": extracted.get("pan_number"),
            "gstin": extracted.get("gstin"),
        },
        "amount_details": {
            "subtotal": extracted.get("subtotal"),
            "tax": extracted.get("tax"),
            "total": extracted.get("total"),
        },
        "line_items": extracted.get("line_items", []),
        "meta": {
            "ocr_engine": engine,
            "template_used": template,
        },
        "raw_text": raw_text.splitlines() if raw_text else []
    }

    # Include validation block optionally (legacy support from prior architecture)
    if validation is not None:
        response["validation"] = validation

    return response

