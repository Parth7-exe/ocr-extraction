"""
Zoho Template Extractor
======================
High-accuracy coordinate and keyword-based extraction designed
specifically for Zoho standard invoice templates.
"""
import re

def extract(ocr_data: dict, layout: dict) -> dict:
    """
    Extract data assuming a Zoho invoice format.
    """
    raw_text = ocr_data.get("raw_text", "")
    lines = layout.get("lines", [])
    
    result = {
        "invoice_number": None,
        "date": None,
        "vendor_name": None,
        "subtotal": None,
        "tax": None,
        "total": None,
        "pan_number": None,
        "gstin": None,
        "line_items": [] # Bonus array for future
    }
    
    # 1. Vendor Name
    # In Zoho, vendor is usually the prominent text at the top left before standard labels.
    if lines:
        result["vendor_name"] = lines[0]["text"].strip()
        
    # 2. Extract cleanly via Key-Values mapping (Zoho uses very standardized labels)
    for kv in layout.get("key_value_pairs", []):
        key = kv["key"].lower()
        val = kv["value"].strip()
        
        if "invoice#" in key or "invoice #" in key or key == "invoice":
            result["invoice_number"] = val
        elif key == "invoice date" or key == "date":
            result["date"] = val
        elif "sub total" in key or "subtotal" in key:
            result["subtotal"] = _try_extract_amount(val)
        elif "total" in key and "sub" not in key and "grand" not in key:
            result["total"] = _try_extract_amount(val)
        elif "tax" in key or "gst" in key and "sub" not in key:
            result["tax"] = _try_extract_amount(val)
            
    # 3. Positional Fallbacks
    if not result["total"]:
        # Find largest number near the bottom right block
        footer_lines = layout.get("regions", {}).get("footer", [])
        for line in reversed(footer_lines):
            t = _try_extract_amount(line["text"])
            if t:
                result["total"] = t
                break
                
    return result

def _try_extract_amount(text: str) -> str:
    """Helper to scrub amount string"""
    match = re.search(r"([\d,]+\.\d{2})", text)
    return match.group(1) if match else None
