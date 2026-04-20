"""
Centralized configuration for the Invoice OCR Extraction System.
All paths, limits, and constants are defined here.
"""

import os
from pathlib import Path

# ──────────────────────────────────────────────
# Base directories
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"

# ──────────────────────────────────────────────
# File validation
# ──────────────────────────────────────────────
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".docx"}
MAX_UPLOAD_SIZE_MB = 20
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024  # 20 MB

# Magic byte signatures for file type verification
FILE_SIGNATURES = {
    ".jpg":  [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".png":  [b"\x89PNG\r\n\x1a\n"],
    ".pdf":  [b"%PDF"],
    ".docx": [b"PK\x03\x04"],  # ZIP-based format
}

# ──────────────────────────────────────────────
# Tesseract OCR configuration
# ──────────────────────────────────────────────
# Set TESSERACT_CMD environment variable if tesseract is not on PATH
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe" if os.name == "nt" else "tesseract")

OCR_MODE = os.environ.get("OCR_MODE", "hybrid")  # "fast" (tesseract only), "accurate" (run both), "hybrid" (fallback)
MIN_HYBRID_CONFIDENCE = 85  # Confidence threshold to trigger fallback
# ──────────────────────────────────────────────
# PDF Preprocessing
# ──────────────────────────────────────────────
# PyMuPDF is used natively, no external binaries required.

# ──────────────────────────────────────────────
# Image preprocessing
# ──────────────────────────────────────────────
TARGET_DPI = 300
MIN_CONFIDENCE = 10  # Minimum OCR confidence to keep a word

# ──────────────────────────────────────────────
# Layout engine
# ──────────────────────────────────────────────
LINE_Y_TOLERANCE = 10    # Pixel tolerance for grouping words into lines
HEADER_RATIO = 0.25      # Top 25% of page = header region
FOOTER_RATIO = 0.75      # Bottom 25% of page = footer region

# ──────────────────────────────────────────────
# Server
# ──────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8000
