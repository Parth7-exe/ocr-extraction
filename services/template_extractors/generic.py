"""
Data Extraction Engine
=======================
Extracts structured invoice fields from OCR results using
robust context-aware candidate generation and scoring.

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
# Patterns and Constants
# ═══════════════════════════════════════════════════════════════

CURRENCY_PATTERN = r"(?:[\$₹€£%]|Rs\.?|INR)?"
PAN_PATTERN = r"\b([A-Z]{5}\d{4}[A-Z])\b"
GSTIN_PATTERN = r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]{3})\b"

CANDIDATE_PATTERNS = {
    "invoice_number": [
        r"(?:(?:invoice|inv|bill|no\.?|number)\b|#)\s*[:.\-]?\s*([A-Za-z0-9\-/]+)",
        r"\b([A-Za-z]{1,6}[\-/]?\d{3,}[A-Za-z0-9\-/]*)\b",
    ],
    "date": [
        r"\b(\d{1,2}[-/](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/]\d{2,4})\b",
        r"\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\b",
        r"\b(\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2})\b",
        r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*,?\s*\d{2,4})\b",
        r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}\s*,?\s*\d{2,4})\b",
    ],
    "amount": [
        # Must have decimal
        CURRENCY_PATTERN + r"\s*([\d,]+\.\d{1,4})",
        # Or must have a currency symbol
        r"(?:[\$₹€£%]|Rs\.?|INR)\s*([\d,]+)",
    ]
}

FIELD_RULES = {
    "total": {
        "positive": ["grand total", "net amount", "amount due", "payable", "total", "balance due", "amount payable"],
        "positive_weight": 5.0,
        "negative": ["subtotal", "sub-total", "tax", "gst", "cgst", "sgst", "igst", "discount"],
        "negative_weight": 20.0,
        "prefer_bottom": True,
        "position_weight": 3.0
    },
    "subtotal": {
        "positive": ["subtotal", "sub-total", "sub total", "gross", "amount before tax", "total amount before"],
        "positive_weight": 5.0,
        "negative": ["grand total", "amount due", "net amount", "payable", "balance due", "tax", "cgst", "sgst"],
        "negative_weight": 20.0,
        "prefer_bottom": False,
        "position_weight": 0.0
    },
    "tax": {
        "positive": ["cgst", "sgst", "igst", "vat", "gst", "tax amount", "tax"],
        "positive_weight": 8.0, # Increased from 4.0
        "negative": ["gstin", "no.", "number", "invoice", "date", "subtotal", "sub-total"],
        "negative_weight": 10.0,
        "prefer_bottom": False,
        "position_weight": 0.0
    },
    "invoice_number": {
        "positive": ["invoice", "inv", "bill", "#", "no.", "number"],
        "positive_weight": 3.0,
        "negative": ["date", "time", "phone", "contact", "pan", "gstin"],
        "negative_weight": 10.0,
        "prefer_top": True,
        "position_weight": 2.0
    },
    "vendor_name": {
        "positive": ["from", "vendor", "supplier", "seller", "company", "sold by", "ship from", "private limited", "ltd"],
        "positive_weight": 5.0,
        "negative": ["invoice", "date", "bill", "tax", "phone", "email", "fax", "tel", "client", "customer", "buyer", "ship to", "gstin", "pan", "#", "no.", "due"],
        "negative_weight": 15.0,
        "prefer_top": True,
        "position_weight": 10.0,
        "is_upper_weight": 5.0
    },
    "date": {
        "positive": ["date", "invoice date", "bill date", "dated", "issue date", "issued"],
        "positive_weight": 3.0,
        "negative": ["due", "dob", "delivery", "payment"],
        "negative_weight": 5.0,
        "prefer_top": True,
        "position_weight": 1.0
    }
}

# ═══════════════════════════════════════════════════════════════
# Candidate Generation
# ═══════════════════════════════════════════════════════════════

def generate_regex_candidates(text: str, patterns: list, field_type: str, context_window: int = 30) -> list:
    candidates = []
    text_length = len(text)
    if text_length == 0:
        return candidates
        
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = match.group(1) if match.lastindex else match.group(0)
            value = value.strip()
            if not value:
                continue
                
            start_idx = match.start()
            end_idx = match.end()
            ctx_start = max(0, start_idx - context_window)
            ctx_end = min(text_length, end_idx + context_window)
            context = text[ctx_start:ctx_end].lower()
            
            position = start_idx / text_length
            candidates.append({
                "type": field_type,
                "value": value,
                "context": context,
                "position": position,
            })
    return candidates

def generate_kv_candidates(kv_pairs: list, field_type: str) -> list:
    candidates = []
    for kv in kv_pairs:
        key = kv.get("key", "").strip()
        val = kv.get("value", "").strip()
        if not val:
            continue
            
        candidates.append({
            "type": field_type,
            "value": val,
            "context": key.lower() + " " + val.lower(),
            "position": 0.5, # default middle position or map if available
        })
    return candidates

def generate_line_candidates(lines: list, field_type: str) -> list:
    candidates = []
    total_lines = len(lines)
    if total_lines == 0:
        return candidates
        
    for idx, line in enumerate(lines):
        text = line.get("text", "").strip()
        if not text:
            continue
            
        candidates.append({
            "type": field_type,
            "value": text,
            "context": text.lower(),
            "position": idx / total_lines,
        })
    return candidates

# ═══════════════════════════════════════════════════════════════
# Scoring Engine
# ═══════════════════════════════════════════════════════════════

def score_candidate(candidate: dict, rules: dict) -> float:
    score = 0.0
    context = candidate["context"]
    pos = candidate["position"]
    
    for kw in rules.get("positive", []):
        # Context matching usually prefers whole words somewhat
        kw_pattern = r"\b" + re.escape(kw) + r"\b" if kw.isalpha() else re.escape(kw)
        if re.search(kw_pattern, context):
            score += rules.get("positive_weight", 1.0)
            
    for kw in rules.get("negative", []):
        kw_pattern = r"\b" + re.escape(kw) + r"\b" if kw.isalpha() else re.escape(kw)
        if re.search(kw_pattern, context):
            score -= rules.get("negative_weight", 1.0)
            
    if rules.get("prefer_bottom"):
        score += pos * rules.get("position_weight", 0.0)
    elif rules.get("prefer_top"):
        score += (1.0 - pos) * rules.get("position_weight", 0.0)
        
    if rules.get("is_upper_weight") and candidate["value"].isupper():
        score += rules.get("is_upper_weight", 0.0)
        
    return score

def _clean_amount_float(val: str) -> Optional[float]:
    val = val.replace(",", "").replace(r"₹", "").strip()
    # sometimes there are trailing non-digit chars
    val = re.sub(r"[^\d.]", "", val)
    try:
        return float(val)
    except ValueError:
        return None

def _format_amount(val: float) -> str:
    return f"{val:.2f}"

# ═══════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════

def extract_invoice_data(ocr_data: dict, layout: dict) -> dict:
    raw_text = ocr_data.get("raw_text", "")
    lines = layout.get("lines", [])
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
        "_extraction_metadata": {}
    }
    
    # 1. Deterministic Multi-Matches (GSTIN/PAN)
    gstin_matches = list(re.finditer(GSTIN_PATTERN, raw_text))
    if gstin_matches:
        result["gstin"] = gstin_matches[0].group(1)
        # First is typically vendor, if needed we can extract second as buyer
        
    pan_matches = list(re.finditer(PAN_PATTERN, raw_text))
    if pan_matches:
        result["pan_number"] = pan_matches[0].group(1)

    # 2. Collect Candidates
    amount_candidates = generate_regex_candidates(raw_text, CANDIDATE_PATTERNS["amount"], "amount")
    amount_candidates += generate_kv_candidates(kv_pairs, "amount")
    
    date_candidates = generate_regex_candidates(raw_text, CANDIDATE_PATTERNS["date"], "date")
    date_candidates += generate_kv_candidates(kv_pairs, "date")
    
    inv_candidates = generate_regex_candidates(raw_text, CANDIDATE_PATTERNS["invoice_number"], "invoice_number")
    inv_candidates += generate_kv_candidates(kv_pairs, "invoice_number")
    
    line_candidates = generate_line_candidates(lines, "line")

    def select_best(candidates, field_name, is_amount=False):
        rules = FIELD_RULES.get(field_name, {})
        valid_candidates = []
        for c in candidates:
            val = c["value"]
            if is_amount:
                num = _clean_amount_float(val)
                if num is None:
                    continue
                c["numeric_value"] = num
            elif field_name == "vendor_name":
                if len(val) < 4:
                    continue
                if re.search(PAN_PATTERN, val) or re.search(GSTIN_PATTERN, val):
                    continue
                if re.match(r"^[\d\s/\-\.,]+$", val):
                    continue
            elif field_name == "invoice_number":
                if len(val) < 3:
                     continue
            
            c_copy = dict(c)
            c_copy["score"] = score_candidate(c_copy, rules)
            valid_candidates.append(c_copy)
            
        if not valid_candidates:
            return None, []
            
        valid_candidates.sort(key=lambda x: x["score"], reverse=True)
        return valid_candidates[0], valid_candidates

    # Extract Fields
    best_vendor, _ = select_best(line_candidates, "vendor_name")
    if best_vendor:
        result["vendor_name"] = best_vendor["value"]
        result["_extraction_metadata"]["vendor_name"] = best_vendor
        
    best_date, _ = select_best(date_candidates, "date")
    if best_date:
        result["date"] = best_date["value"]
        result["_extraction_metadata"]["date"] = best_date
        
    best_inv, _ = select_best(inv_candidates, "invoice_number")
    if best_inv:
        result["invoice_number"] = best_inv["value"]
        result["_extraction_metadata"]["invoice_number"] = best_inv
        
    best_total, _ = select_best(amount_candidates, "total", is_amount=True)
    if best_total:
        result["total"] = _format_amount(best_total["numeric_value"])
        result["_extraction_metadata"]["total"] = best_total
        
    best_subtotal, _ = select_best(amount_candidates, "subtotal", is_amount=True)
    if best_subtotal:
        result["subtotal"] = _format_amount(best_subtotal["numeric_value"])
        result["_extraction_metadata"]["subtotal"] = best_subtotal
        
    _, all_tax_candidates = select_best(amount_candidates, "tax", is_amount=True)
    if all_tax_candidates:
        tax_sum = 0.0
        used_taxes = []
        seen_vals = set()
        exclude_vals = set()
        if best_total:
            exclude_vals.add(best_total["numeric_value"])
        if best_subtotal:
            exclude_vals.add(best_subtotal["numeric_value"])

        for t in all_tax_candidates:
            if t["score"] > 2.0 and t["numeric_value"] not in exclude_vals:
                # Use a more generous rounding for position to avoid duplicates
                # from overlapping regex/kv matches in roughly the same area.
                pos_bucket = round(t["position"], 3) 
                val = t["numeric_value"]
                uniq = f"{val}_{pos_bucket}"
                
                if uniq not in seen_vals:
                    # Also check if we've seen this exact value very recently (within 5% of document)
                    # to avoid double counting same tax mentioned in summary and table.
                    is_duplicate = False
                    for st in used_taxes:
                        if st["numeric_value"] == val and abs(st["position"] - t["position"]) < 0.05:
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        seen_vals.add(uniq)
                        tax_sum += val
                        used_taxes.append(t)
                    
        if tax_sum > 0:
            result["tax"] = _format_amount(tax_sum)
            result["_extraction_metadata"]["tax"] = {
                "value": result["tax"],
                "score": sum(t["score"] for t in used_taxes),
                "context": " | ".join([t["context"] for t in used_taxes]),
                "position": used_taxes[0]["position"] if used_taxes else 0
            }

    return result
