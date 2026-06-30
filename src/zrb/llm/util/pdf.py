"""PDF text extraction shared by the attachment pipeline and file_read tool.

Callers add their own wrapping (error messages, line-range truncation,
notifications). This module owns only the core extraction.
"""

from __future__ import annotations


def extract_pdf_text(path: str) -> str | None:
    """Extract text from a PDF file.

    Args:
        path: File-system path to the PDF.

    Returns:
        Combined text of all pages joined by newlines, or ``None`` when the
        PDF is scanned/image-only, corrupted, pdfplumber is not installed,
        or an unexpected error occurs.
    """
    try:
        # lazy: pdfplumber is a core dependency but heavy to import at module
        # top — it transitively loads pdfminer, PIL, and others.
        import pdfplumber
    except ImportError:
        return None

    try:
        with pdfplumber.open(path) as pdf:
            texts = [p.extract_text() for p in pdf.pages if p.extract_text()]
            return "\n".join(texts) if texts else None
    except Exception:
        return None
