import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.llm.util.image_scale import scale_image_bytes
from zrb.llm.util.pdf import extract_pdf_text

if TYPE_CHECKING:
    from pydantic_ai.messages import UserContent


def normalize_attachments(
    attachments: "list[UserContent]", print_fn: Callable[[str], Any] = print
) -> "list[UserContent]":

    # lazy: pydantic_ai is heavy; only loaded when there are attachments to wrap.
    from pydantic_ai import BinaryContent

    final_attachments = []
    for item in attachments:
        if item is None:
            continue
        if isinstance(item, str):
            # Treat as path
            path = os.path.abspath(os.path.expanduser(item))
            if not os.path.isfile(path):
                print_fn(f"Attachment file not found: {path}")
                continue
            media_type = get_media_type(path)
            if not media_type:
                print_fn(f"Unknown media type for {path}")
                continue
            oversized_by = get_oversized_by(path)
            if oversized_by is not None:
                print_fn(
                    f"Attachment too large, skipping: {path} "
                    f"({oversized_by[0]} bytes, limit {oversized_by[1]} bytes)"
                )
                continue
            try:
                if media_type == "application/pdf":
                    pdf_text = extract_pdf_text(path)
                    if pdf_text is not None:
                        final_attachments.append(pdf_text)
                        continue
                    # Fall through to binary if extraction failed
                    print_fn("Failed to extract text from PDF — attaching as binary")
                data = Path(path).read_bytes()
                mismatch = sniff_mismatch(data, media_type)
                if mismatch:
                    print_fn(
                        f"Attachment content doesn't look like {media_type}, "
                        f"skipping: {path} ({mismatch})"
                    )
                    continue
                if media_type.startswith("image/"):
                    scaled = scale_image_bytes(data, media_type=media_type)
                    data = scaled.data
                    media_type = scaled.media_type
                final_attachments.append(
                    BinaryContent(data=data, media_type=media_type)
                )
            except Exception as e:
                print_fn(f"Failed to read attachment {path}: {e}")
        else:
            # Assume it's already a suitable object (e.g. BinaryContent)
            final_attachments.append(item)
    return final_attachments


def get_oversized_by(path: str) -> "tuple[int, int] | None":
    """``(actual_size, limit)`` when *path* exceeds the configured cap, else None."""
    limit = CFG.LLM_MAX_ATTACHMENT_BYTES
    if limit <= 0:
        return None
    size = os.path.getsize(path)
    return (size, limit) if size > limit else None


# Magic-byte signatures for the formats we can cheaply and reliably verify.
# Audio/video/office containers have too many valid variants to check with a
# short prefix list, so those media types are intentionally left unverified.
# ponytail: covers images + PDF only; extend the table if spoofing other
# extensions becomes a real problem.
_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),  # followed by size + "WEBP"; checked separately
    "application/pdf": (b"%PDF-",),
}


def sniff_mismatch(data: bytes, media_type: str) -> str | None:
    """Reason string when *data*'s magic bytes contradict *media_type*, else None."""
    signatures = _SIGNATURES.get(media_type)
    if not signatures:
        return None
    if media_type == "image/webp":
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return None
        return "missing RIFF/WEBP header"
    if any(data.startswith(sig) for sig in signatures):
        return None
    return f"expected signature for {media_type}, found {data[:8]!r}"


def check_attachment_bytes(data: bytes, media_type: str) -> str | None:
    """Reason string when in-memory *data* fails the size cap or signature
    sniff, else None.

    For entry points that already hold the bytes (web upload, Telegram) and
    so can't check size against the file on disk first the way
    `get_oversized_by` does for path-based callers (`normalize_attachments`,
    the CLI's `/attach`).
    """
    limit = CFG.LLM_MAX_ATTACHMENT_BYTES
    if limit > 0 and len(data) > limit:
        return f"too large ({len(data)} bytes, limit {limit} bytes)"
    if sniff_mismatch(data, media_type):
        return f"doesn't look like {media_type}"
    return None


def get_attachments(
    ctx: AnyContext,
    attachment: "UserContent | list[UserContent] | Callable[[AnyContext], UserContent | list[UserContent]] | None" = None,  # noqa
) -> "list[UserContent]":
    if attachment is None:
        return []
    if callable(attachment):
        result = attachment(ctx)
        if result is None:
            return []
        if isinstance(result, list):
            return result
        return [result]
    if isinstance(attachment, list):
        return attachment
    return [attachment]


def get_media_type(filename: str) -> str | None:
    """Guess media type string based on file extension."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    mapping: dict[str, str] = {
        # Audio
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "ogg": "audio/ogg",
        "flac": "audio/flac",
        "aiff": "audio/aiff",
        "aac": "audio/aac",
        # Image
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        # Document
        "pdf": "application/pdf",
        "txt": "text/plain",
        "csv": "text/csv",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "html": "text/html",
        "htm": "text/html",
        "md": "text/markdown",
        "doc": "application/msword",
        "xls": "application/vnd.ms-excel",
        # Video
        "mkv": "video/x-matroska",
        "mov": "video/quicktime",
        "mp4": "video/mp4",
        "webm": "video/webm",
        "flv": "video/x-flv",
        "mpeg": "video/mpeg",
        "mpg": "video/mpeg",
        "wmv": "video/x-ms-wmv",
        "3gp": "video/3gpp",
    }
    return mapping.get(ext)
