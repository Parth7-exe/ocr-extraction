"""
Table Extractor Service
=======================
Extracts structured line items natively from PDFs using pdfplumber's table parser.
Maps rows into specific fields: item, quantity, rate, amount.
"""

import pdfplumber

def extract_tables(file_path: str) -> list:
    """
    Extracts tabular line items natively from a digital PDF.
    Maps rows to standard fields.
    """
    line_items = []
    
    # We only process PDFs for tables natively. Images require heavy custom vision.
    if not str(file_path).lower().endswith(".pdf"):
        return line_items
        
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if not tables:
                    continue
                    
                for table in tables:
                    # Clean out None values
                    cleaned_table = [[str(cell).strip() if cell else "" for cell in row] for row in table]
                    
                    if not cleaned_table or len(cleaned_table) < 2:
                        continue
                        
                    # Find the header row to map index positions
                    # Support multi-line headers by flattening
                    headers = [str(h).lower().replace('\n', ' ') for h in cleaned_table[0]]
                    
                    # Fuzzy match column indices
                    item_idx = _find_idx(headers, ["item", "description", "product", "particulars", "name"])
                    qty_idx = _find_idx(headers, ["qty", "quantity", "pieces"])
                    rate_idx = _find_idx(headers, ["rate", "price", "unit"])
                    amount_idx = _find_idx(headers, ["amount", "total", "net"])
                    
                    # If we found at least an item and an amount column, it's a valid line items table
                    if item_idx is not None and amount_idx is not None:
                        for row in cleaned_table[1:]:
                            # Skip entirely empty or header-continuation rows
                            if not any(row):
                                continue
                                
                            item_val = row[item_idx].replace('\n', ' ') if item_idx < len(row) else ""
                            qty_val = row[qty_idx].replace('\n', '') if (qty_idx is not None and qty_idx < len(row)) else "1"
                            rate_val = row[rate_idx].replace('\n', '') if (rate_idx is not None and rate_idx < len(row)) else ""
                            amount_val = row[amount_idx].replace('\n', '') if amount_idx < len(row) else ""
                            
                            # Filter empty ghost rows
                            if item_val or amount_val:
                                line_items.append({
                                    "item": item_val,
                                    "quantity": qty_val,
                                    "rate": rate_val,
                                    "amount": amount_val
                                })
    except Exception as e:
        print(f"[Table Extractor] Failed to extract tables natively: {e}")
        
    return line_items

def _find_idx(headers: list, keywords: list):
    for idx, header in enumerate(headers):
        if any(kw in header for kw in keywords):
            return idx
    return None
