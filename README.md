# Offline Invoice OCR Extraction System

A production-grade, privacy-first invoice data extraction pipeline. This system is designed to run entirely locally with **zero external AI dependencies**. It guarantees high-fidelity, deterministic extraction of Line Items, Subtotals, Tax, Grand Totals, Dates, and Invoice Numbers across both physically scanned smartphone images and digitally-generated PDFs.

## 🚀 Key Features

*   **100% Offline & Private:** No cloud APIs (No AWS Textract, No LLMs, No OpenAI). Your financial data never leaves your hardware.
*   **Hybrid OCR Engine:** 
    *   **Tesseract:** Fast, primary OCR block.
    *   **PaddleOCR:** High-accuracy fallback triggered organically for heavily degraded documents.
*   **Dual-Pass PDF Architecture:**
    *   **Native Digital Parse (`pdfplumber`):** Extracts digital arrays mathematically out of generated PDFs yielding 100% pristine character accuracy without OCR hallucination.
    *   **Scan Fallback (`PyMuPDF` / OpenCV):** If a PDF is a wrapper for a scanned image, it intelligently falls back to executing OCR processing on all image layers.
*   **Reinforcement Template Learning (RL-Style):** Dynamic rule generation. If an unknown layout is successfully parsed using generic structural heuristics, an Autonomous Learner *memorizes* the exact layout anchor mapping and binds it to the vendor. The next upload instantly bypasses the guesswork and deterministically strips data using the learned mapping format.
*   **Advanced Pre-Processing:** Uses custom OpenCV CLAHE matrices and Unsharp Masking to flatten dark smartphone gradient shadows and artificially spike visual sharpness before OCR runs.

## 🛠 Tech Stack

*   **Python 3.12**
*   **FastAPI / Uvicorn** (REST Backend)
*   **OpenCV** (Image Enhancement)
*   **Tesseract-OCR / PaddleOCR** (Vision Text Extraction)
*   **pdfplumber / PyMuPDF (fitz)** (PDF Native Routing)
*   **python-docx** (Word Document unpacking)

## ⚙️ How It Works

1.  **Ingestion:** The route accepts `jpg`, `png`, `pdf`, or `docx` files.
2.  **Pre-routing:** Images are normalized/enhanced. PDFs are routed through the exact-match `pdfplumber` pass.
3.  **Extraction:** OCR normalizes the text (containing a custom global Rupee symbol filter).
4.  **Layout Analysis:** Identifies header/footer zones and maps loose coordinates to clustered Key-Value pairs.
5.  **Detection & Execution:** The Orchestrator (`extractor.py`) scans for `learned` JSON files or known hardcoded vendor templates (like Zoho). If missing, it activates the `generic` heuristic fallback and triggers the template learner mechanism.
6.  **Response:** Emits strict, validated JSON data output containing Amounts, GSTIN, PAN, and Vendors.

## 📦 Setup & Installation

1. Create a virtual environment and load the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. **Install System OCR Dependencies**: 
   Ensure `Tesseract OCR` is installed on your OS and the config variable internally points to your `.exe` or global alias.
3. Start the FastAPI Server:
   ```bash
   python main.py
   ```
4. Access the upload GUI via the mapped static localhost route!
