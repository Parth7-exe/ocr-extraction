"""
Template Detector
=================
Evaluates the initial OCR payload (raw text, layout) and assigns the invoice
to a highly specific template if key indicators are found.
Falls back to "generic" if no specific template is confidently identified.
"""

import json
from pathlib import Path

LEARNED_DIR = Path("learned_templates")

def detect_template(ocr_data: dict, layout: dict) -> str:
    """
    Detects the invoice template based on identifiers in the text.
    First checks autonomously learned templates, then hardcoded templates.
    """
    raw_text = ocr_data.get("raw_text", "").lower()
    
    # ── 0. Check Auto-Learned Templates ───────────────────────
    if LEARNED_DIR.exists():
        for template_file in LEARNED_DIR.glob("*.json"):
            try:
                with open(template_file, "r", encoding="utf-8") as f:
                    schema = json.load(f)
                    vendor_id = schema.get("vendor_identifier", "").lower()
                    if vendor_id and vendor_id in raw_text:
                        print(f"[Template Detector] DETECTED: Learned template '{vendor_id}' matched.")
                        return f"learned:{template_file.name}"
            except Exception:
                continue

    # ── 1. Crescent Business Solutions ────────────────────────
    if "crescent business solutions" in raw_text:
        print("[Template Detector] DETECTED: 'crescent' template matched.")
        return "crescent"

        
    # ── 2. Zoho Invoice ───────────────────────────────────────
    # Looking for strong Zoho signatures.
    if "zoho invoice" in raw_text or "powered by zoho" in raw_text or "zoho.com/invoice" in raw_text:
        print("[Template Detector] DETECTED: 'zoho' template matched.")
        return "zoho"
        
    # ── Default Fallback ──────────────────────────────────────
    print("[Template Detector] NO SPECIFIC MATCH: Falling back to 'generic' extraction.")
    return "generic"
