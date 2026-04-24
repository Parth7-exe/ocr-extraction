import re
from datetime import datetime

_NOISE_WORDS = {
    "of", "the", "and", "in", "is", "to", "for", "at", "by", "on",
    "a", "an", "or", "it", "as", "if", "no", "not", "be", "was",
    "are", "has", "had", "do", "did", "may", "can", "so", "up",
}

def format_structured_data(raw_kv_pairs: dict) -> dict:
    """
    Takes raw key-value pairs from the dynamic extractor and:
    1. Normalizes keys
    2. Processes values (currency, numbers, dates)
    3. Filters out noise and invalid keys
    """
    structured_data = {}
    
    for key, value in raw_kv_pairs.items():
        # 1. Normalize Key
        n_key = _normalize_key(key)
        
        # Filter purely numeric keys or single char keys or noise words
        if not n_key or len(n_key) < 2 or n_key.isdigit():
            continue
        if n_key in _NOISE_WORDS:
            continue
            
        # 2. Process Value
        n_val = _process_value(value)
        
        # 3. Filter empty/invalid values
        if not n_val:
            continue
            
        structured_data[n_key] = n_val

    return structured_data

def _normalize_key(key: str) -> str:
    """Lowercase and replace spaces with underscores."""
    n = key.lower().strip()
    n = re.sub(r"[^a-z0-9_\s]", "", n)
    n = re.sub(r"\s+", "_", n.strip())
    return n.strip("_")

def _process_value(value: str) -> str:
    """Remove currency, normalize numbers and dates."""
    val = value.strip()
    
    # Check if it's a date
    date_normalized = _try_normalize_date(val)
    if date_normalized:
        return date_normalized
        
    # Check if it's an amount/number with currency
    # E.g. "₹2,740.50", "$ 100", "Rs. 500"
    amount_normalized = _try_normalize_amount(val)
    if amount_normalized:
        return amount_normalized
        
    # General cleanup (strip leading/trailing punctuation)
    val = re.sub(r"^[,.\-:;]+", "", val).strip()
    val = re.sub(r"[,.\-:;]+$", "", val).strip()
    
    return val

def _try_normalize_date(text: str) -> str | None:
    """Attempt to parse and normalize a date string to YYYY-MM-DD."""
    text = text.strip()
    for fmt in [
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%Y-%m-%d", "%Y/%m/%d",
        "%d %b %Y", "%d %B %Y",
        "%d/%b/%Y", "%d-%b-%Y",
        "%d/%m/%y", "%d-%m-%y",
    ]:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

def _try_normalize_amount(text: str) -> str | None:
    """
    Remove currency symbols and commas from amounts.
    Only returns a normalized string if the rest is a valid number.
    """
    # Remove common currency symbols and words
    clean_text = re.sub(r"[₹$\£\€]|Rs\.?|INR", "", text, flags=re.IGNORECASE).strip()
    # Remove commas
    clean_text = clean_text.replace(",", "")
    
    # Check if what's left is a valid float/int
    if re.match(r"^-?\d+(\.\d+)?$", clean_text):
        return clean_text
        
    return None
