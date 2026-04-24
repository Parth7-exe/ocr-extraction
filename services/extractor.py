"""
Extraction Orchestrator
=======================
Routes the raw OCR text to the pure dynamic key-value pair extractor.
"""

from services.dynamic_kvp_engine import stage1_clean_and_group, stage2_extract_key_values
from services.semantic_formatter import format_structured_data

def extract_document_data(ocr_data: dict, layout: dict) -> dict:
    """
    Main extraction pipeline.
    Returns both raw_text array and clean structured key-value data.
    """
    # 1. Raw Text Extraction (MANDATORY)
    raw_text_lines = stage1_clean_and_group(ocr_data, layout)
    
    # 2. Key-Value Extraction
    raw_kv_pairs = stage2_extract_key_values(raw_text_lines)
    
    # 3. Formatting, Filtering, and Validation
    structured_data = format_structured_data(raw_kv_pairs)
    
    return {
        "raw_text": raw_text_lines,
        "structured_data": structured_data
    }
