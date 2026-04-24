import re

def detect_document_type(ocr_text: str) -> str:
    """
    STRICT RULE-BASED LOGIC to detect document type.
    NO AI, NO ML, NO LLMs used here.
    """
    text_lower = ocr_text.lower()
    
    # ── Aadhaar Check ─────────────────────────────────────
    aadhaar_keywords = ["aadhaar", "government of india", "unique identification"]
    has_aadhaar_kw = any(kw in text_lower for kw in aadhaar_keywords)
    # 12 digit number pattern (often spaced like XXXX XXXX XXXX or contiguous)
    has_aadhaar_num = bool(re.search(r"\b\d{4}\s?\d{4}\s?\d{4}\b", ocr_text))
    
    if has_aadhaar_kw and has_aadhaar_num:
        return "aadhaar"
        
    # ── Invoice Check ─────────────────────────────────────
    invoice_keywords = ["invoice", "bill to", "gstin", "subtotal", "tax invoice"]
    inv_score = sum(1 for kw in invoice_keywords if kw in text_lower)
    has_total = "total" in text_lower
    
    if inv_score >= 2 or (has_total and "invoice" in text_lower) or ("gstin" in text_lower and "invoice" in text_lower):
        return "invoice"
        
    # ── Receipt Check ─────────────────────────────────────
    receipt_keywords = ["receipt", "cashier", "pos", "transaction id", "payment receipt", "merchant"]
    rec_score = sum(1 for kw in receipt_keywords if kw in text_lower)
    
    if rec_score >= 2 or ("receipt" in text_lower and "total" in text_lower):
        return "receipt"
        
    # ── Fallback ──────────────────────────────────────────
    return "generic"
