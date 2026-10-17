import os
import shlex
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse
from urllib.request import url2pathname

from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.llm.util.image_scale import scale_image_bytes
from zrb.llm.util.pdf import extract_pdf_text

if TYPE_CHECKING:
    from zrb.llm.agent.types import UserContent


def normalize_attachments(
    attachments: "Sequence[UserContent | None]",
    print_fn: Callable[[str], Any] = print,
) -> "list[UserContent]":

    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import BinaryContent

    final_attachments = []
    for item in attachments:
        if item is None:
            continue
        if isinstance(item, str):
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
            final_attachments.append(item)
    return _without_duplicates(final_attachments)


def _without_duplicates(attachments: "list[UserContent]") -> "list[UserContent]":
    # A file queued both as a path (`/attach`) and as bytes (a paste) reads
    # to equal content here, the one point where both forms meet.
    unique: "list[UserContent]" = []
    for attachment in attachments:
        if attachment not in unique:
            unique.append(attachment)
    return unique


def get_oversized_by(path: str) -> "tuple[int, int] | None":
    """``(actual_size, limit)`` when *path* exceeds the configured cap, else None.

    None too when the size cannot be read, e.g. a temp file removed since it
    was found: the read that follows reports it, so this check never raises.
    """
    limit = CFG.LLM_MAX_ATTACHMENT_BYTES
    if limit <= 0:
        return None
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    return (size, limit) if size > limit else None


# Magic-byte signatures; audio/video/office containers have too many variants
# to verify by prefix, so they are not checked.
# covers images + PDF only; extend the table if spoofing other
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
    sniff, else None. For callers that hold bytes, not a path."""
    limit = CFG.LLM_MAX_ATTACHMENT_BYTES
    if limit > 0 and len(data) > limit:
        return f"too large ({len(data)} bytes, limit {limit} bytes)"
    if sniff_mismatch(data, media_type):
        return f"doesn't look like {media_type}"
    return None


def get_attachments(
    ctx: AnyContext,
    attachment: "UserContent | list[UserContent] | Callable[[AnyContext], UserContent | list[UserContent] | None] | None" = None,  # noqa
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


# A paste longer than this is prose or a log, never a handful of file paths;
# skip it before tokenizing so a large paste costs no filesystem lookups.
_MAX_PASTED_PATHS_LENGTH = 4096


def get_pasted_attachment_paths(text: str) -> list[str] | None:
    """The attachable files a paste names, when the paste is nothing but them.

    Terminals paste a file as its path: iTerm2's "Save to Temp File and Paste
    Path" for a clipboard image, and dragging files from a file manager into
    most terminals. Paths may be quoted, backslash-escaped or ``file://`` URIs,
    several to a paste. Any token that is not an existing attachable file (a
    word, a missing path) returns None, so a path mentioned inside a sentence
    stays text.

    Text types (``.md``, ``.txt``, ``.csv``, ``.html``) are not attachable
    here: a pasted path to one is usually a reference the agent can read with
    its own tools, so it stays text. ``/attach`` still takes them.
    """
    stripped = text.strip()
    if not stripped or len(stripped) > _MAX_PASTED_PATHS_LENGTH:
        return None
    tokens = _split_pasted_paths(stripped)
    if not tokens:
        return None
    paths = [_to_local_path(token) for token in tokens]
    if all(_is_pasteable_attachment(path) for path in paths):
        return paths
    return None


def _split_pasted_paths(text: str) -> list[str]:
    # Windows paths use backslashes, which POSIX shlex reads as escapes.
    posix = os.name != "nt"
    try:
        tokens = shlex.split(text, posix=posix)
    except ValueError:
        return []  # unbalanced quote: prose, not a path list
    if not posix:
        tokens = [token.strip('"') for token in tokens]
    return tokens


def _to_local_path(token: str) -> str:
    if token.startswith("file://"):
        parsed = urlparse(token)
        # url2pathname turns Windows' `/C:/x` into `C:\x`; a host other than
        # localhost is a UNC share, `file://server/share/x`.
        host = "" if parsed.netloc in ("", "localhost") else parsed.netloc
        token = url2pathname(f"//{host}{parsed.path}" if host else parsed.path)
    return os.path.abspath(os.path.expanduser(token))


def _is_pasteable_attachment(path: str) -> bool:
    media_type = get_media_type(path)
    return (
        media_type is not None
        and not media_type.startswith("text/")
        and os.path.isfile(path)
    )


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
