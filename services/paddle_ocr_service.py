"""
PaddleOCR Service  (PRIMARY ENGINE)
====================================
Wraps PaddleOCR as the main/primary OCR extraction engine.

Returns structured word-level data matching the tesseract output format.
"""

import re
import numpy as np
import sys
import os
import site

# Fix for "ModuleNotFoundError: No module named 'tools.infer'" which occurs in some PaddleOCR environments
try:
    for p in site.getsitepackages() + [site.getusersitepackages()]:
        paddleocr_dir = os.path.join(p, "paddleocr")
        if os.path.exists(paddleocr_dir) and paddleocr_dir not in sys.path:
            sys.path.insert(0, paddleocr_dir)
except Exception:
    pass

# Lazy load so importing config/handlers doesn't freeze or lag initially
_paddle_ocr_engine = None

def get_paddle_engine():
    global _paddle_ocr_engine
    if _paddle_ocr_engine is None:
        from paddleocr import PaddleOCR
        # Initialize PaddleOCR
        # use_angle_cls=False initially for speed.
        # Ensure it downloads to default directories or handled locally.
        _paddle_ocr_engine = PaddleOCR(use_angle_cls=False, lang='en')
    return _paddle_ocr_engine


def run_paddle(preprocessed_img: np.ndarray) -> dict:
    """
    Run PaddleOCR on a preprocessed image.
    
    Args:
        preprocessed_img: Preprocessed grayscale numpy array.

    Returns:
        Dict with 'words', 'raw_text', 'confidence', and 'engine'.
    """
    ocr_engine = get_paddle_engine()
    
    # PaddleOCR expects a BGR numpy array ideally, but handles grayscale fine.
    # Run the model
    result_list = ocr_engine.ocr(preprocessed_img, cls=False)
    
    words = []
    raw_texts = []
    total_conf = 0.0
    valid_words = 0
    
    line_idx = 1
    
    # PaddleOCR 2.8+ returns a list where result_list[0] can be None if no text is found.
    if result_list and len(result_list) > 0 and result_list[0] is not None:
        for line in result_list[0]:
            box, txt_res = line
            text = txt_res[0]
            conf = txt_res[1] * 100  # Convert 0-1 scale to 0-100 to match Tesseract
            
            # Format: box = [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
            # x is min x, y is min y, width is max x - min x
            xs = [pt[0] for pt in box]
            ys = [pt[1] for pt in box]
            x_min = int(min(xs))
            y_min = int(min(ys))
            w = int(max(xs) - x_min)
            h = int(max(ys) - y_min)
            
            raw_texts.append(text)
            
            words.append({
                "text": text,
                "x": x_min,
                "y": y_min,
                "w": w,
                "h": h,
                "conf": conf,
                "block_num": 1,          # Simplified placeholder
                "line_num": line_idx,
                "word_num": 1,           # Paddle extracts phrase/line typically, not per word exactly
            })
            
            line_idx += 1
            total_conf += conf
            valid_words += 1

    avg_confidence = total_conf / valid_words if valid_words > 0 else 0
    raw_text = "\n".join(raw_texts)

    return {
        "words": words,
        "raw_text": raw_text,
        "confidence": avg_confidence,
        "engine": "paddle"
    }
