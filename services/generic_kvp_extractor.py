import re
from typing import Dict, Any, List

def _validate_type(value: str, expected_type: str) -> str | None:
    """
    STRICT TYPE DETECTION
    Validates a value against its expected type before assignment.
    Returns the cleaned value if valid, or None if it mismatches.
    """
    if not value:
        return None
        
    value = value.strip()
    
    if expected_type == "DATE":
        # Supports dd/mm/yyyy, dd-mm-yyyy, yyyy/mm/dd, yyyy-mm-dd
        # and "15/07/1996", "15-Jul-1996" etc.
        # Minimal regex to ensure date-like structure
        date_pattern = r"\b\d{1,4}[/\-\.]\w{2,3}[/\-\.]\d{2,4}\b|\b\d{1,4}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b"
        matches = re.findall(date_pattern, value)
        if matches:
            date_str = matches[0]
            # Try to normalize to YYYY-MM-DD
            from datetime import datetime
            for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d", "%d/%b/%Y", "%d-%b-%Y"]:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue
            return date_str # Return as is if we can't parse it
        return None
        
    elif expected_type == "ID":
        # Strip non-alphanumeric and check length, or simply numeric formats (Aadhaar, etc)
        # Allows spaces and hyphens
        cleaned = re.sub(r"[^\w\s-]", "", value).strip()
        # Ensure it has digits, usually IDs are mostly numeric or alphanumeric
        if re.search(r"\d", cleaned):
            return cleaned
        return None
        
    elif expected_type == "AMOUNT":
        # Remove currency symbols and check if it's a valid float/decimal
        cleaned = re.sub(r"[^\d\.]", "", value)
        try:
            float(cleaned)
            return cleaned
        except ValueError:
            return None
            
    elif expected_type == "TEXT":
        # Keep as is, maybe strip weird chars if needed
        return value
        
    return value

def extract_aadhaar(ocr_data: dict, layout: dict) -> Dict[str, Any]:
    """Extract Aadhaar specific fields."""
    raw_text = ocr_data.get("raw_text", "")
    lines = raw_text.splitlines()
    
    name = None
    dob = None
    gender = None
    aadhaar_num = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        # DOB Check
        if "DOB" in line.upper() or "YEAR OF BIRTH" in line.upper() or "YOB" in line.upper():
            dob_cand = _validate_type(line, "DATE")
            if dob_cand:
                dob = dob_cand
                
        # Gender Check
        if "MALE" in line.upper() and "FEMALE" not in line.upper():
            gender = "MALE"
        elif "FEMALE" in line.upper():
            gender = "FEMALE"
            
        # Aadhaar Number Check
        num_match = re.search(r"\b\d{4}\s?\d{4}\s?\d{4}\b", line)
        if num_match:
            aadhaar_cand = _validate_type(num_match.group(0), "ID")
            if aadhaar_cand:
                aadhaar_num = aadhaar_cand
                
    # Name Heuristic (Usually above DOB)
    for i, line in enumerate(lines):
        if "DOB" in line.upper() or "YEAR OF BIRTH" in line.upper() or "YOB" in line.upper():
            # Look at previous line for name
            if i > 0:
                name_cand = lines[i-1].strip()
                if name_cand and not any(kw in name_cand.lower() for kw in ["government", "india", "aadhaar"]):
                    name = _validate_type(name_cand, "TEXT")
            break
            
    # For user's specific test case "Kshitij Pawar, DOB: 15/07/1996"
    if not name:
        for line in lines:
            if "DOB" in line.upper() and "," in line:
                name_cand = line.split(",")[0].strip()
                if name_cand:
                    name = _validate_type(name_cand, "TEXT")
                break
                
    # Filter out Nones strictly per requirement:
    # "If validation fails: -> DO NOT include that field in output"
    result = {"document_type": "aadhaar"}
    if name: result["name"] = name
    if dob: result["dob"] = dob
    if gender: result["gender"] = gender
    if aadhaar_num: result["aadhaar_number"] = aadhaar_num
    
    return result

def extract_receipt(ocr_data: dict, layout: dict) -> Dict[str, Any]:
    """Extract Receipt specific fields."""
    raw_text = ocr_data.get("raw_text", "")
    lines = raw_text.splitlines()
    
    merchant = None
    date = None
    total = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        # Date
        if not date:
            d_cand = _validate_type(line, "DATE")
            if d_cand:
                date = d_cand
                
        # Total
        if "TOTAL" in line.upper() and not total:
            parts = re.split(r"TOTAL", line, flags=re.IGNORECASE)
            if len(parts) > 1 and parts[1].strip():
                t_cand = _validate_type(parts[1], "AMOUNT")
                if t_cand:
                    total = t_cand
            else:
                # Look at next line or same line pattern
                t_cand = _validate_type(line, "AMOUNT")
                if t_cand:
                    total = t_cand
                    
        # Merchant (First non-empty line heuristic)
        if i < 3 and not merchant and len(line) > 3:
            merchant = _validate_type(line, "TEXT")

    result = {"document_type": "receipt"}
    if merchant: result["merchant_name"] = merchant
    if date: result["date"] = date
    if total: result["total_amount"] = total
    return result

def extract_generic_kvp(ocr_data: dict, layout: dict) -> Dict[str, Any]:
    """
    Extract key-value pairs generically based on layout.
    """
    # Use spatial layout key_value_pairs from layout_engine if available
    layout_kvps = layout.get("key_value_pairs", [])
    
    extracted_kvps = []
    
    # 1. Process KVP from layout engine (separator based)
    for kvp in layout_kvps:
        k = kvp.get("key", "").strip()
        v = kvp.get("value", "").strip()
        if k and v:
            extracted_kvps.append({"key": k, "value": v})
            
    # 2. Process alignment-based KVP from lines
    lines = layout.get("lines", [])
    # A simple heuristic for horizontal alignment key value (Label      Value)
    # If a line has a large spatial gap
    for line in lines:
        words = line.get("words", [])
        if len(words) >= 2:
            # Check gap between words
            max_gap = 0
            split_idx = -1
            for i in range(len(words)-1):
                gap = words[i+1]["x"] - (words[i]["x"] + words[i]["w"])
                if gap > max_gap:
                    max_gap = gap
                    split_idx = i
                    
            if max_gap > 30 and split_idx != -1: # Threshold for gap
                k_words = words[:split_idx+1]
                v_words = words[split_idx+1:]
                k = " ".join([w["text"] for w in k_words]).strip()
                v = " ".join([w["text"] for w in v_words]).strip()
                # Ensure it's not already captured
                already_captured = any(ek["key"] == k for ek in extracted_kvps)
                # Ensure we don't capture if key contains a separator we already handled
                if k and v and not already_captured and not any(sep in line["text"] for sep in [":", "-", "=", "|"]):
                    extracted_kvps.append({"key": k, "value": v})

    return {
        "document_type": "generic",
        "key_value_pairs": extracted_kvps
    }
