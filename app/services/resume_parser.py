"""Extract plain text from an uploaded resume PDF."""

from io import BytesIO

from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_PDF_BYTES = 5 * 1024 * 1024  # 5 MB cap — resumes shouldn't exceed this


async def extract_resume_text(upload: UploadFile) -> str:
    """Read an UploadFile, decode the PDF, return its text. Raises 400 on failure."""
    if not upload.filename or not upload.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF resumes are supported.",
        )

    raw = await upload.read()
    if len(raw) > MAX_PDF_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Resume too large ({len(raw)} bytes). Max {MAX_PDF_BYTES}.",
        )

    try:
        reader = PdfReader(BytesIO(raw))
        pages = [page.extract_text() or "" for page in reader.pages]
    except PdfReadError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read PDF: {e}",
        ) from e

    text = "\n".join(pages).strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No extractable text found in the PDF (is it a scan?).",
        )
    return text
