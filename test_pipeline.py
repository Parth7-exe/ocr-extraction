"""Quick smoke test for the full extraction pipeline."""
import cv2
import json
from services.preprocessing import preprocess_image
from services.ocr_service import run_ocr
from services.layout_engine import analyze_layout
from services.extractor import extract_invoice_data

img = cv2.imread("test_invoice.png")
if img is None:
    print("ERROR: Could not load test_invoice.png")
    exit(1)

preprocessed = preprocess_image(img)
ocr_result = run_ocr(preprocessed)
print(f"[OCR] Engine: {ocr_result['engine']}, Confidence: {ocr_result['confidence']:.1f}%")
print(f"[OCR] Words found: {len(ocr_result['words'])}")

layout = analyze_layout(ocr_result)
extracted = extract_invoice_data(ocr_result, layout)

# Remove internal key for display
extracted.pop("_runtime_template_used_", None)

print()
print("=== FINAL STRUCTURED OUTPUT ===")
print(json.dumps(extracted, indent=2, ensure_ascii=False))
