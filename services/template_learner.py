"""
Template Learner Service
========================
Intercepts successful generic extractions. Analyzes how the data was found 
by dynamically mapping extracted values back to their OCR Key-Value anchors.
Saves deterministic layout rules as JSON to 'learned_templates/'.
"""

import json
from pathlib import Path

LEARNED_DIR = Path("learned_templates")

def attempt_learning(extracted: dict, layout: dict) -> None:
    """
    Called by the Orchestrator after generic extraction.
    If the extraction is rich enough, it learns the template.
    """
    vendor = extracted.get("vendor_name")
    
    # We only learn if we have a solid Vendor Identity + minimum 3 standard fields
    if not vendor:
        return
        
    filled_fields = sum(1 for v in extracted.values() if v is not None and v != [])
    if filled_fields < 4:  # Vendor + 3 fields
        return
        
    # Standardize vendor string to use as filename
    safe_vendor = "".join(c for c in vendor if c.isalnum() or c in " _-").strip()
    template_path = LEARNED_DIR / f"{safe_vendor.replace(' ', '_').lower()}.json"
    
    if template_path.exists():
        # Already learned!
        return
        
    # Start building reverse-mapped rules
    rules = {}
    kv_pairs = layout.get("key_value_pairs", [])
    
    for field, extract_val in extracted.items():
        if field in ["vendor_name", "_runtime_template_used_", "_extraction_metadata"] or extract_val in [None, [], {}]:
            continue
            
        # Reverse map this value to a KV pair to memorize the exact Key anchor
        # that generated this value.
        mapped_key = None
        for kv in kv_pairs:
            # Simple soft match (since value may have been cleaned like comma stripping)
            if str(extract_val).lower() in kv["value"].lower() or kv["value"].lower() in str(extract_val).lower():
                mapped_key = kv["key"]
                break
                
        if mapped_key:
            rules[field] = {"strategy": "exact_kv", "anchor_key": mapped_key}
        else:
            # Fallback: memorize it was found globally via regex, so learned engine
            # will just re-run the generic regex for this specific field.
            rules[field] = {"strategy": "generic_fallback"}
            
    # Save the learned template schema
    template_data = {
        "vendor_identifier": vendor,
        "rules": rules
    }
    
    try:
        if not LEARNED_DIR.exists():
            LEARNED_DIR.mkdir(parents=True, exist_ok=True)
        with open(template_path, "w", encoding="utf-8") as f:
            json.dump(template_data, f, indent=4)
        print(f"[Template Learner] ⚡ SUCCESS: Learned new template for '{vendor}'! Cached to {template_path}")
    except Exception as e:
        print(f"[Template Learner] Warning: Failed to save template for {vendor}: {e}")
