"""
Learned Engine Extractor
========================
Executes extraction exclusively using deterministic rules mapped
dynamically by the Template Learner.
"""

import json
from pathlib import Path
from services.template_extractors import generic # For the generic fallbacks if needed

LEARNED_DIR = Path("learned_templates")

def extract(ocr_data: dict, layout: dict, learned_vendor_filename: str) -> dict:
    """
    Extract data based on the JSON cached template.
    """
    result = {
        "invoice_number": None,
        "date": None,
        "vendor_name": None,
        "subtotal": None,
        "tax": None,
        "total": None,
        "pan_number": None,
        "gstin": None,
        "line_items": [] 
    }
    
    template_path = LEARNED_DIR / learned_vendor_filename
    if not template_path.exists():
        # Edge case: file deleted mid-run. Fall back generic
        return generic.extract_invoice_data(ocr_data, layout)
        
    with open(template_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
        
    result["vendor_name"] = schema.get("vendor_identifier")
    rules = schema.get("rules", {})
    kv_pairs = layout.get("key_value_pairs", [])
    
    # If the schema says any field requires generic fallback, we run it entirely once 
    # to populate shadows, but we OVERRIDE with our exact KV logic first taking priority.
    shadow_result = {}
    if any(r.get("strategy") == "generic_fallback" for r in rules.values()):
        shadow_result = generic.extract_invoice_data(ocr_data, layout)
        
    for field, rule in rules.items():
        if rule["strategy"] == "exact_kv":
            target_key = rule["anchor_key"].lower().strip()
            # Find the exact KV pair
            for kv in kv_pairs:
                if kv["key"].lower().strip() == target_key:
                    result[field] = kv["value"]
                    break
        elif rule["strategy"] == "generic_fallback":
            result[field] = shadow_result.get(field)
            
    return result
