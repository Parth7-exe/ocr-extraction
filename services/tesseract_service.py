"""
Tesseract OCR Service
=====================
Wraps pytesseract to extract text, bounding boxes, and confidence
from preprocessed images using `image_to_data`.

Returns structured word-level data and average confidence.
"""

import pytesseract
from pytesseract import Output
import numpy as np
from PIL import Image

from config import TESSERACT_CMD, MIN_CONFIDENCE

# Configure tesseract path
if TESSERACT_CMD != "tesseract":
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

def run_tesseract(preprocessed_img: np.ndarray) -> dict:
    """
    Run Tesseract OCR on a preprocessed image.

    Args:
        preprocessed_img: Preprocessed grayscale numpy array.

    Returns:
        Dict with 'words', 'raw_text', 'confidence', and 'engine'.
    """
    # Convert numpy array to PIL Image for pytesseract
    pil_img = Image.fromarray(preprocessed_img)

    # Get detailed word-level data with bounding boxes and confidence
    data = pytesseract.image_to_data(pil_img, output_type=Output.DICT)

    # Get full text output
    raw_text = pytesseract.image_to_string(pil_img).strip()

    # Parse word data and calculate confidence
    words = []
    n_entries = len(data["text"])
    total_conf = 0.0
    valid_words = 0

    for i in range(n_entries):
        text = data["text"][i].strip()
        conf = int(data["conf"][i])

        # Skip empty text and low-confidence results
        if not text or conf < MIN_CONFIDENCE:
            continue

        words.append({
            "text": text,
            "x": data["left"][i],
            "y": data["top"][i],
            "w": data["width"][i],
            "h": data["height"][i],
            "conf": conf,
            "block_num": data["block_num"][i],
            "line_num": data["line_num"][i],
            "word_num": data["word_num"][i],
        })
        
        total_conf += conf
        valid_words += 1

    avg_confidence = total_conf / valid_words if valid_words > 0 else 0

    return {
        "words": words,
        "raw_text": raw_text,
        "confidence": avg_confidence,
        "engine": "tesseract"
    }
