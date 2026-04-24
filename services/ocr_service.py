"""
OCR Service
=============
Acts as the coordinator for the hybrid OCR pipeline, utilizing
PaddleOCR as the PRIMARY engine and Tesseract OCR as the FALLBACK
based on configuration and confidence thresholds.

Pipeline Priority:
  1. PaddleOCR  (primary — higher accuracy, layout-aware)
  2. Tesseract  (fallback — triggered when Paddle confidence is low)
"""

import numpy as np
import re
from config import OCR_MODE, MIN_HYBRID_CONFIDENCE
from services.tesseract_service import run_tesseract
from services.paddle_ocr_service import run_paddle

def _check_required_fields(raw_text: str) -> bool:
    """
    Perform a quick check on the raw text to see if key invoice fields 
    are likely present to help decide if fallback OCR is needed.
    """
    text_lower = raw_text.lower()
    
    # Quick checks for basics
    has_date = bool(re.search(r'\b(date|dated)\b', text_lower) or re.search(r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}', text_lower))
    has_total = bool(re.search(r'\b(total|amount|due|balance|subtotal|tax)\b', text_lower) or re.search(r'[\$₹€£]?\s*[\d,]+\.\d{2}', text_lower))
    has_invoice = bool(re.search(r'\b(invoice|inv|bill)\b', text_lower))
    
    score = sum([has_date, has_total, has_invoice])
    return score >= 2  # Consider it valid if at least 2 key categories are seen

def _normalize_all_rupees(ocr_result: dict) -> dict:
    """
    Globally fixes the Rupee (₹) symbol being misread across both engines 
    without destroying standard numbers. Applies directly to OCR outputs.
    """
    def fix_text(text: str) -> str:
        # 1. Z, %, ?, Rs. are extremely safe to replace unconditionally before any digits
        # (e.g. Z100 -> ₹100, %120 -> ₹120)
        text = re.sub(
            r"(?<![a-zA-Z0-9])(?:Z\.?|%|\?|Rs\.?)\s*(?=\d)",
            "₹", text, flags=re.IGNORECASE
        )
        
        # 2. Isolated tokens with periods. (Standalone '2.' but NEVER bare '2')
        text = re.sub(
            r"(?<![a-zA-Z0-9])(?:2\.|Z\.)(?![a-zA-Z0-9])",
            "₹", text, flags=re.IGNORECASE
        )
        
        # 3. Fused 2 with strict decimal (e.g. 2100.50 -> ₹100.50)
        text = re.sub(
            r"(?<![a-zA-Z0-9])(?:2)\s*(?=\d{1,3}(?:,\d{3})*(?:\.\d{2})\b)",
            "₹", text, flags=re.IGNORECASE
        )

        # 4. Fused 2 without decimals (e.g. 2100 -> ₹100).
        # We must be extremely careful NOT to destroy years (2024, 2025, 2026) 
        # or typical invoice numbers (e.g. INV-2345).
        # We only replace '2' if it's NOT followed by '0xx' (which would form 20xx years).
        # We also enforce that it strictly follows space or start of line (no dashes or #).
        text = re.sub(
            r"(?<![a-zA-Z0-9\-\#])2(?![0]\d{2}\b)(?=\d{1,5}\b)",
            "₹", text
        )

        return text

    if "raw_text" in ocr_result:
        ocr_result["raw_text"] = fix_text(ocr_result["raw_text"])
        
    for word in ocr_result.get("words", []):
        word["text"] = fix_text(word["text"])
        
    return ocr_result


def run_ocr(preprocessed_img: np.ndarray) -> dict:
    """
    Main OCR orchestrator per page/image.
    
    Modes:
      - "fast":     PaddleOCR only (no fallback).
      - "accurate": Run BOTH engines, pick the highest confidence result.
      - "hybrid":   PaddleOCR first; fall back to Tesseract if Paddle 
                    confidence is below threshold or key fields are missing.
    """
    mode = str(OCR_MODE).strip().lower()
    
    if mode == "fast":
        # ── Fast mode: PaddleOCR only ──────────────────────────
        print("[OCR] Fast mode — running PaddleOCR only")
        return _normalize_all_rupees(run_paddle(preprocessed_img))
        
    elif mode == "accurate":
        # ── Accurate mode: run both, pick best ─────────────────
        print("[OCR] Accurate mode — running both engines")
        p_res = run_paddle(preprocessed_img)
        t_res = run_tesseract(preprocessed_img)
        best = p_res if p_res["confidence"] >= t_res["confidence"] else t_res
        print(f"[OCR] Winner: {best['engine']} (Paddle={p_res['confidence']:.1f}%, Tesseract={t_res['confidence']:.1f}%)")
        return _normalize_all_rupees(best)
        
    else:
        # ── Hybrid mode (default): PaddleOCR primary, Tesseract fallback ──
        print("[OCR] Hybrid mode — PaddleOCR primary, Tesseract fallback")
        p_res = run_paddle(preprocessed_img)
        required_fields = _check_required_fields(p_res.get("raw_text", ""))
        
        if p_res.get("confidence", 0) >= MIN_HYBRID_CONFIDENCE and required_fields:
            print(f"[OCR] PaddleOCR accepted (confidence={p_res['confidence']:.1f}%)")
            return _normalize_all_rupees(p_res)
            
        # PaddleOCR didn't meet the bar — trigger Tesseract fallback
        print(f"[OCR] PaddleOCR below threshold (confidence={p_res.get('confidence', 0):.1f}%, fields_ok={required_fields}). Triggering Tesseract fallback...")
        t_res = run_tesseract(preprocessed_img)
        
        # Pick whichever engine produced the better result
        best = t_res if t_res.get("confidence", 0) > p_res.get("confidence", 0) else p_res
        print(f"[OCR] Final pick: {best['engine']} (Paddle={p_res.get('confidence', 0):.1f}%, Tesseract={t_res.get('confidence', 0):.1f}%)")
        return _normalize_all_rupees(best)
