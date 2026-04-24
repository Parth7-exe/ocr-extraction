import json
from services.extractor import extract_document_data
from services.layout_engine import analyze_layout

def test_sonia_sharma():
    ocr_data = {
        "raw_text": (
            "भारत सरकार\n"
            "Government of India\n"
            "Full Name\n"
            "SONIA SHARMA T\n"
            "DOB: 30 / 01 / 1990\n"
            "Gender: FEMALE\n"
            "1234 5678 9000\n"
            "मेरा आधार, मेरी पहचान"
        )
    }
    
    layout = analyze_layout(ocr_data)
    extracted = extract_document_data(ocr_data, layout)
    
    print(json.dumps(extracted, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test_sonia_sharma()
