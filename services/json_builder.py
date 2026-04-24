"""
JSON Builder Service
=====================
Assembles the final structured JSON response from extracted data.
Supports dynamic schemas (Aadhaar, Invoice, Receipt, Generic).
Outputs the public API response with added context.
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
    Constructs the final API response JSON.
    The `extracted` dict dynamically conforms to the detected document type schema.
    We merge in runtime metadata and optional blocks.
    """
    doc_type = extracted.get("document_type", "generic")
    meta = extracted.get("meta", {})
    
    # Base response
    response = {
        "file_id": file_id,
        "document_type": doc_type
    }
    
    # Copy dynamically extracted fields based on schema type
    if doc_type == "invoice":
        response["invoice_details"] = extracted.get("invoice_details", {})
        response["vendor_details"] = extracted.get("vendor_details", {})
        response["amount_details"] = extracted.get("amount_details", {})
    elif doc_type == "aadhaar":
        if "name" in extracted: response["name"] = extracted["name"]
        if "dob" in extracted: response["dob"] = extracted["dob"]
        if "gender" in extracted: response["gender"] = extracted["gender"]
        if "aadhaar_number" in extracted: response["aadhaar_number"] = extracted["aadhaar_number"]
    elif doc_type == "receipt":
        if "merchant_name" in extracted: response["merchant_name"] = extracted["merchant_name"]
        if "date" in extracted: response["date"] = extracted["date"]
        if "total_amount" in extracted: response["total_amount"] = extracted["total_amount"]
    else:
        # Generic
        response["key_value_pairs"] = extracted.get("key_value_pairs", [])
        
    # Append common metadata and lists
    response["line_items"] = line_items if line_items is not None else []
    
    response["meta"] = {
        "source":          engine,
        "tables_detected": tables_detected,
        "template_used":   template,
        "corrected":       meta.get("corrected", False),
        "fields_updated":  meta.get("fields_updated", []),
        "math_status":     meta.get("math_status"),
    }
    
    response["raw_text"] = raw_text.splitlines() if raw_text else []

    # Include validation block optionally (legacy support for invoices)
    if validation is not None:
        response["validation"] = validation

    return response
