import io
import logging
from typing import Tuple
from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader

logger = logging.getLogger("interviewiq.pdf_extractor")

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


async def extract_text_from_pdf_upload(file: UploadFile) -> str:
    """
    Extract raw text from an uploaded PDF file with strict validation.

    Validates:
    - Content-type / file extension
    - File size (capped at 5MB)
    - Magic bytes (%PDF-)
    - Readable text extraction (rejects empty/scanned PDFs with no selectable text)

    Does NOT log full resume text to protect candidate privacy.
    Ensures memory buffers are released cleanly.
    """
    filename = file.filename or "uploaded_file"

    # 1. Validate file extension
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload a valid PDF document (.pdf).",
        )

    # 2. Read bytes into memory
    content = await file.read()

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded PDF file is empty (0 bytes).",
        )

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The uploaded file exceeds the 5MB size limit ({len(content) / (1024 * 1024):.1f}MB).",
        )

    # 3. Check PDF magic header
    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is not a valid PDF document (missing PDF magic header).",
        )

    # 4. Parse PDF pages
    pdf_stream = None
    try:
        pdf_stream = io.BytesIO(content)
        reader = PdfReader(pdf_stream)

        if len(reader.pages) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded PDF has no pages.",
            )

        extracted_text_parts = []
        for page_idx, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            if page_text.strip():
                extracted_text_parts.append(page_text.strip())

        full_text = "\n\n".join(extracted_text_parts).strip()

    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("PDF parsing failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to parse PDF content. The document may be corrupted or password-protected.",
        ) from exc
    finally:
        # Clear buffer cleanly
        if pdf_stream is not None:
            pdf_stream.close()

    # 5. Check if any readable text was extracted
    if not full_text or len(full_text) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No readable text could be extracted from the uploaded PDF. "
                "Scanned image-only PDFs or encrypted documents are not supported. "
                "Please upload a standard text-based PDF resume."
            ),
        )

    logger.info("Successfully extracted %d characters from PDF resume '%s'", len(full_text), filename)
    return full_text
