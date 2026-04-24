"""
Intelligent Comparison and Correction Engine
============================================
Refines extracted invoice data by comparing it against raw document text.
Ensures no hallucinations and maintains logical consistency.
"""

import re
import json
from typing import Optional, List, Dict, Any

# ═══════════════════════════════════════════════════════════════
# Patterns and Rule Constants
# ═══════════════════════════════════════════════════════════════

GSTIN_PATTERN = r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]{3})\b"
PAN_PATTERN = r"\b([A-Z]{5}\d{4}[A-Z])\b"
EMAIL_PATTERN = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"

FIELDS_CONFIG = {
    "invoice_number": {
        "patterns": [
            r"(?:invoice|inv|bill|no\.?|number|#)\s*[:.\-]?\s*([A-Za-z0-9\-/]+)",
            r"\b([A-Za-z0-9]{4,}[/-][A-Za-z0-9]{2,})\b",
            r"\b([A-Z]*\d{4,}[A-Z]*)\b"
        ],
        "positive": ["invoice", "inv", "bill", "#", "no.", "number"],
        "negative": ["date", "phone", "contact", "pan", "gstin", "email"],
        "prefer_top": True,
        "weight": 1.0
    },
    "date": {
        "patterns": [
            r"\b(\d{1,2}[-/](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/]\d{2,4})\b",
            r"\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\b",
            r"\b(\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2})\b",
            r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*,?\s*\d{2,4})\b"
        ],
        "positive": ["date", "issued", "invoice date", "dated", "bill date"],
        "negative": ["due", "payment", "delivery"],
        "prefer_top": True,
        "weight": 1.0
    },
    "total": {
        "patterns": [r"(?:[\$₹€£%]|Rs\.?|INR)?\s*([\d,]+\.\d{2})"],
        "positive": ["grand total", "net amount", "amount due", "payable", "total payable", "total"],
        "negative": ["subtotal", "tax", "cgst", "sgst", "igst", "discount", "gstin"],
        "prefer_bottom": True,
        "weight": 1.5
    },
    "subtotal": {
        "patterns": [r"(?:[\$₹€£%]|Rs\.?|INR)?\s*([\d,]+\.\d{2})"],
        "positive": ["subtotal", "sub total", "taxable value", "amount before tax"],
        "negative": ["grand total", "total payable", "tax amount"],
        "prefer_bottom": True,
        "weight": 1.0
    },
    "tax": {
        "patterns": [r"(?:[\$₹€£%]|Rs\.?|INR)?\s*([\d,]+\.\d{2})"],
        "positive": ["cgst", "sgst", "igst", "vat", "tax amount", "tax"],
        "negative": ["gstin", "total", "subtotal"],
        "prefer_bottom": True,
        "weight": 1.0
    },
    "gstin": {
        "patterns": [GSTIN_PATTERN],
        "positive": ["gstin", "gst"],
        "negative": [],
        "weight": 1.0
    }
}

class CorrectionEngine:
    def __init__(self):
        self.debug_data = {}

    def refine(self, extracted_data: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
        """Main entry point to refine extracted data."""
        self.debug_data = {}
        text_lines = raw_text.split("\n")
        
        # Target structure as requested
        output = {
            "invoice_details": {
                "invoice_number": extracted_data.get("invoice_number"),
                "date": extracted_data.get("date")
            },
            "vendor_details": {
                "vendor_name": extracted_data.get("vendor_name"),
                "gstin": extracted_data.get("gstin")
            },
            "amount_details": {
                "subtotal": extracted_data.get("subtotal"),
                "tax": extracted_data.get("tax"),
                "total": extracted_data.get("total")
            },
            "meta": {
                "corrected": False,
                "fields_updated": []
            }
        }

        # List of fields to process (flattened for internal logic)
        fields_to_process = [
            ("invoice_number", "invoice_details"),
            ("date", "invoice_details"),
            ("vendor_name", "vendor_details"),
            ("gstin", "vendor_details"),
            ("subtotal", "amount_details"),
            ("tax", "amount_details"),
            ("total", "amount_details")
        ]

        for field, section in fields_to_process:
            original_value = str(output[section].get(field) or "")
            
            # Step 1: Validate existence
            is_valid = self._exists_in_text(original_value, raw_text) if original_value else False
            
            if is_valid:
                self._track_debug(field, original_value, original_value, 1.0, "Value exists in document")
                continue
            
            # Step 2 & 3: Candidate search and validation
            candidate_value = self._search_for_candidate(field, raw_text, text_lines)
            
            if candidate_value and candidate_value != original_value:
                output[section][field] = candidate_value
                output["meta"]["corrected"] = True
                output["meta"]["fields_updated"].append(field)
                self._track_debug(field, original_value, candidate_value, 0.8, "Better candidate found in text")
            else:
                # Retain original if uncertain
                self._track_debug(field, original_value, original_value, 0.5, "No better candidate found or original retained")

        # Step 5: Consistency Checks
        output = self._apply_consistency_checks(output)

        return output

    def _exists_in_text(self, value: str, raw_text: str) -> bool:
        if not value: return False
        # Escape any regex special chars in the value
        pattern = re.escape(value.strip())
        return bool(re.search(pattern, raw_text, re.IGNORECASE))

    def _search_for_candidate(self, field: str, raw_text: str, lines: List[str]) -> Optional[str]:
        if field == "vendor_name":
            return self._extract_vendor_name(lines)
        if field == "gstin":
            return self._extract_gstins(raw_text)

        config = FIELDS_CONFIG.get(field)
        if not config: return None

        candidates = []
        text_len = len(raw_text)

        for pattern in config["patterns"]:
            for match in re.finditer(pattern, raw_text, re.IGNORECASE):
                val = match.group(1) if match.lastindex else match.group(0)
                val = val.strip()
                if not val: continue

                # Context Window (±50 characters)
                start, end = match.span()
                context = raw_text[max(0, start-50):min(text_len, end+50)].lower()
                position = start / text_len

                # Scoring
                score = 0
                for kw in config["positive"]:
                    if kw in context: score += 1
                for kw in config["negative"]:
                    if kw in context: score -= 2
                
                # Proximity to label (simplified here as presence in same 50px-ish context)
                if config.get("prefer_top") and position < 0.3: score += 1
                if config.get("prefer_bottom") and position > 0.6: score += 1

                candidates.append({"value": val, "score": score})

        if candidates:
            # Sort by score descending
            candidates.sort(key=lambda x: x["score"], reverse=True)
            return candidates[0]["value"]
        
        return None

    def _extract_vendor_name(self, lines: List[str]) -> Optional[str]:
        """Vendor name specific logic: top 20%, uppercase preferred, reject numbers/gstin."""
        for i, line in enumerate(lines[:min(len(lines), 15)]): # Look in top few lines
            text = line.strip()
            if not text or len(text) < 3: continue
            
            # Reject numeric lines or lines with strict IDs
            if re.match(r"^[\d\s\W]+$", text): continue
            if re.search(GSTIN_PATTERN, text): continue
            if re.search(PAN_PATTERN, text): continue
            if re.search(EMAIL_PATTERN, text): continue
            
            # Prefer uppercase
            if text.isupper():
                return text
            
            # Fallback to the very first valid text line
            if i < 5: return text # Return if it's very high up
            
        return None

    def _extract_gstins(self, raw_text: str) -> Optional[str]:
        """GSTIN specific: first is vendor."""
        matches = re.findall(GSTIN_PATTERN, raw_text)
        return matches[0] if matches else None

    def _apply_consistency_checks(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure subtotal + tax = total."""
        amounts = data["amount_details"]
        try:
            sub = self._to_float(amounts.get("subtotal"))
            tax = self._to_float(amounts.get("tax"))
            tot = self._to_float(amounts.get("total"))

            if sub is not None and tax is not None and tot is not None:
                if abs((sub + tax) - tot) > 1.0:
                    data["meta"]["math_status"] = "inconsistent"
                else:
                    data["meta"]["math_status"] = "consistent"
        except Exception:
            pass
        return data

    def _to_float(self, val: Any) -> Optional[float]:
        if val is None: return None
        try:
            return float(str(val).replace(",", "").replace("₹", "").strip())
        except ValueError:
            return None

    def _track_debug(self, field, original, final, conf, reason):
        self.debug_data[field] = {
            "original_value": original,
            "final_value": final,
            "confidence": conf,
            "reason": reason
        }

    def get_debug_metadata(self) -> Dict[str, Any]:
        return self.debug_data

def refine_extraction(extracted_data: dict, raw_text: str) -> dict:
    engine = CorrectionEngine()
    refined = engine.refine(extracted_data, raw_text)
    # Check if we should add debug meta
    # refined["_correction_debug"] = engine.get_debug_metadata()
    return refined
