import json
from services.correction_engine import refine_extraction

def test_engine():
    raw_text = """
    Invoice
    ABC TECHNOLOGIES PVT LTD
    123 Main St, Bangalore
    GSTIN: 29ABCDE1234F1Z5
    
    Invoice No: INV/2024/001
    Date: 21-Apr-2026
    
    Description          Amount
    Software Services    1000.00
    
    Subtotal: 1000.00
    CGST (9%): 90.00
    SGST (9%): 90.00
    
    Grand Total: 1180.00
    """
    
    # Mock extracted data with some errors
    extracted_data = {
        "invoice_number": "INV-001", # Wrong format/value
        "date": "2026-04-21",       # Normalized but not in raw text
        "vendor_name": "ABC TECH",  # Incomplete
        "subtotal": "1000.00",      # Correct
        "tax": "180.00",            # Correct sum
        "total": "1100.00",          # Incorrect
        "gstin": "29ABCDE1234F1Z5"  # Correct
    }
    
    refined = refine_extraction(extracted_data, raw_text)
    
    print("Refined Output:")
    print(json.dumps(refined, indent=2))
    
    # Assertions
    # Invoice number should be corrected to INV/2024/001
    inv_num = refined["invoice_details"]["invoice_number"]
    assert inv_num == "INV/2024/001", f"Expected INV/2024/001, got {inv_num}"
    
    # Vendor name should be corrected to ABC TECHNOLOGIES PVT LTD
    vendor = refined["vendor_details"]["vendor_name"]
    assert "ABC TECHNOLOGIES PVT LTD" in vendor, f"Expected full vendor name, got {vendor}"
    
    # Total should be corrected to 1180.00
    total = refined["amount_details"]["total"]
    assert "1180.00" in total, f"Expected 1180.00, got {total}"
    
    print("\nTests passed successfully!")

if __name__ == "__main__":
    test_engine()
