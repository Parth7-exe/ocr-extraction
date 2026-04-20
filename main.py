"""
Invoice Data Extraction System (Hybrid Upgrade Mode) — Main Application
===================================================
A fully offline, production-grade FastAPI backend for extracting
structured invoice data from images, PDFs, and DOCX files.

No external APIs. No cloud OCR. No LLMs. Fully deterministic.
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from contextlib import asynccontextmanager

from config import UPLOAD_DIR, OUTPUT_DIR, HOST, PORT
from routes.upload import router as upload_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create required directories on startup."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[DIR] Upload directory: {UPLOAD_DIR}")
    print(f"[DIR] Output directory: {OUTPUT_DIR}")
    print("[OK] Invoice OCR Extraction System is ready.")
    yield
    print("[STOP] Shutting down...")


app = FastAPI(
    title="Invoice Data Extraction API",
    description=(
        "A robust offline invoice processing system that handles multiple formats "
        "(images, PDFs, DOCX), extracts structured data via Tesseract OCR, "
        "and outputs downloadable JSON with optional validation."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS middleware (allow local frontends) ──────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routes ──────────────────────────────────────────
app.include_router(upload_router)

# ── Serve static files & Frontend ────────────────────────────
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content=b"", media_type="image/x-icon")

@app.get("/", tags=["UI"], summary="Serve Web Frontend")
async def serve_frontend():
    """Serve the Nexus OCR Web Interface."""
    return FileResponse("frontend/index.html")

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "Invoice Data Extraction API",
        "version": "1.0.0",
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
