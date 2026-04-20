"""
Extraction Orchestrator
=======================
Routes the extraction logic to specific templates based on Template Detector findings.
Falls back to generic if no template matches.
"""

from services.template_detector import detect_template
from services.template_extractors import zoho, crescent, generic, learned_engine
from services import template_learner

def extract_invoice_data(ocr_data: dict, layout: dict) -> dict:
    """
    Main extraction pipeline. Discovers template, delegates.
    """
    # 1. Detect Template
    template_name = detect_template(ocr_data, layout)
    
    # 2. Delegate to appropriate extractor
    if template_name.startswith("learned:"):
        # e.g., "learned:abc_corp.json"
        filename = template_name.split(":", 1)[1]
        extracted = learned_engine.extract(ocr_data, layout, filename)
    elif template_name == "zoho":
        extracted = zoho.extract(ocr_data, layout)
    elif template_name == "crescent":
        extracted = crescent.extract(ocr_data, layout)
    else:
        # Fallback generic logic (regex, coordinate heuristics)
        extracted = generic.extract_invoice_data(ocr_data, layout)
        
        # ── RL/Learning Hook: Try to memorize this new format ──
        template_learner.attempt_learning(extracted, layout)
        
    # Append the template meta inside the expected structure 

    # (actually handled largely down in json_builder, but returning it here is safe)
    # The requirement is that json_builder receives the template name. We will attach it 
    # directly as a private key so file_handler can read it.
    extracted["_runtime_template_used_"] = template_name
        
    return extracted
