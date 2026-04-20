"""
Crescent Business Solutions Template Extractor
============================================
Highly tuned parsing for Crescent Business Solutions "Bill Of Supply".
"""
import re

def extract(ocr_data: dict, layout: dict) -> dict:
    raw_text = ocr_data.get("raw_text", "")
    lines = layout.get("lines", [])
    
    result = {
        "invoice_number": None,
        "date": None,
        "vendor_name": "Crescent Business Solutions Pvt Ltd.", # Hardcoded accuracy for template
        "subtotal": None,
        "tax": None,
        "total": None,
        "pan_number": None,
        "gstin": None,
        "line_items": []
    }
    
    # Static Regex parsing logic unique to Crescent layout
    
    # PAN / GSTIN usually present in same place
    pan_match = re.search(r"PAN/IT\s*No\s*[:]\s*([A-Z]{5}\d{4}[A-Z])", raw_text)
    if pan_match:
         result["pan_number"] = pan_match.group(1)
         
    gst_match = re.search(r"GSTIN/UIN[:\s]+([0-9]{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]{3})", raw_text)
    if gst_match:
         result["gstin"] = gst_match.group(1)
         
    # Expected: "Invoice No. Dated\nMUM1012/2025-26 9-Feb-26"
    multiline_match = re.search(r"Invoice\s*No\.?\s*Dated\s*\n(\S+)\s+(\S+)", raw_text, re.IGNORECASE)
    if multiline_match:
        result["invoice_number"] = multiline_match.group(1)
        result["date"] = multiline_match.group(2)
        
    # Amounts
    # In Crescent total looks like:  "= 35,36,673.00" 
    # Or "Amount Chargeable..."
    total_match = re.search(r"=\s*([\d,]+\.?\d*)", raw_text)
    if total_match:
        result["total"] = total_match.group(1).replace(",", "").strip()
        
    # Usually Bill Of supply is exempt from GST, so tax = None
    
    return result
