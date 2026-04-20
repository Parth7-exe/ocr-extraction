"""
Upload & Download Routes
=========================
POST /upload   — Accept file + enable_validation flag, process, return JSON.
GET  /download/{file_id} — Download the generated JSON result file.
"""

import uuid
import json
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse

from config import (
    UPLOAD_DIR, OUTPUT_DIR,
    ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE_BYTES,
    FILE_SIGNATURES,
)
from services.file_handler import process_file

router = APIRouter(tags=["Invoice Processing"])


def _validate_extension(filename: str) -> str:
    """Validate file extension and return it."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    return ext


def _validate_magic_bytes(content: bytes, ext: str) -> None:
    """Verify file content matches expected magic bytes for the extension."""
    signatures = FILE_SIGNATURES.get(ext, [])
    if signatures and not any(content.startswith(sig) for sig in signatures):
        raise HTTPException(
            status_code=400,
            detail=f"File content does not match expected format for '{ext}'."
        )


def _sanitize_filename(filename: str) -> str:
    """Remove path traversal characters from filename."""
    return Path(filename).name.replace("..", "").replace("/", "").replace("\\", "")


@router.post("/upload", summary="Upload and process an invoice file")
async def upload_invoice(
    file: UploadFile = File(..., description="Invoice file (JPG, PNG, PDF, or DOCX)"),
    enable_validation: bool = Form(
        default=False,
        description="Enable validation checks (PAN, GST, date, amount consistency)"
    ),
):
    """
    Upload an invoice file for processing.

    - **file**: The invoice file to process (image, PDF, or DOCX)
    - **enable_validation**: If true, includes validation results and confidence scores

    Returns structured JSON with extracted invoice data.
    """
    # ── Validate file ────────────────────────────────────────
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    ext = _validate_extension(file.filename)

    # Read file content
    content = await file.read()

    # Size check
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB."
        )

    # Magic byte verification
    _validate_magic_bytes(content, ext)

    # ── Save file ────────────────────────────────────────────
    file_id = str(uuid.uuid4())
    safe_name = _sanitize_filename(file.filename)
    saved_path = UPLOAD_DIR / f"{file_id}_{safe_name}"
    saved_path.write_bytes(content)

    # ── Process ──────────────────────────────────────────────
    try:
        result = process_file(
            file_path=str(saved_path),
            file_ext=ext,
            file_id=file_id,
            enable_validation=enable_validation,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Processing failed: {str(e)}"
        )

    # ── Save JSON output ────────────────────────────────────
    output_path = OUTPUT_DIR / f"{file_id}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return result


@router.get("/download/{file_id}", summary="Download processed JSON result")
async def download_result(file_id: str):
    """
    Download the JSON result file for a previously processed invoice.

    - **file_id**: The unique identifier returned from the /upload endpoint.
    """
    output_path = OUTPUT_DIR / f"{file_id}.json"

    if not output_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No result found for file_id '{file_id}'."
        )

    return FileResponse(
        path=str(output_path),
        media_type="application/json",
        filename=f"invoice_{file_id}.json",
        headers={"Content-Disposition": f'attachment; filename="invoice_{file_id}.json"'}
    )
