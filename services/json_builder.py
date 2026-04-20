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
    engine: str = "hybrid",
    template: str = "generic",
    tables_detected: bool = False,
    line_items: Optional[list] = None,
) -> dict:
    """
    Constructs the final rigorous JSON schema enforcing validation rules.
    """
    response = {
        "file_id": file_id,
        "invoice_details": {
            "invoice_number": extracted.get("invoice_number"),
            "date": extracted.get("date"),
        },
        "amount_details": {
            "subtotal": extracted.get("subtotal"),
            "tax": extracted.get("tax"),
            "total": extracted.get("total"),
        },
        "vendor_details": {
            "vendor_name": extracted.get("vendor_name"),
            "pan_number": extracted.get("pan_number"),
            "gstin": extracted.get("gstin"),
        },
        "line_items": line_items if line_items is not None else [],
        "meta": {
            "source": engine,
            "tables_detected": tables_detected,
            "template_used": template
        },
        "raw_text": raw_text.splitlines() if raw_text else []
    }

    # Include validation block optionally (legacy support from prior architecture)
    if validation is not None:
        response["validation"] = validation

    return response

