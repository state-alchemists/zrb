"""PDF text extraction shared by the attachment pipeline and file_read tool."""

from __future__ import annotations


def extract_pdf_text(path: str) -> str | None:
    """Extract text from a PDF file.

    Args:
        path: File-system path to the PDF.

    Returns:
        Combined text of all pages joined by newlines, empty string when the
        PDF contains no extractable text (e.g. scanned/image-only), or
        ``None`` when pdfplumber is not installed or an unexpected error occurs.
    """
    try:
        # lazy: heavy third-party — pdfplumber loads pdfminer and PIL.
        import pdfplumber
    except ImportError:
        return None

    try:
        with pdfplumber.open(path) as pdf:
            texts = [p.extract_text() for p in pdf.pages if p.extract_text()]
            return "\n".join(texts) if texts else ""
    except Exception:
        return None
