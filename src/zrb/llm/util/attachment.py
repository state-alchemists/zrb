from typing import TYPE_CHECKING, Any, Callable

from zrb.context.any_context import AnyContext

if TYPE_CHECKING:
    from pydantic_ai.messages import UserContent


def normalize_attachments(
    attachments: "list[UserContent]", print_fn: Callable[[str], Any] = print
) -> "list[UserContent]":
    import os
    from pathlib import Path

    from pydantic_ai import BinaryContent

    from zrb.llm.util.attachment import get_media_type

    final_attachments = []
    for item in attachments:
        if isinstance(item, str):
            # Treat as path
            path = os.path.abspath(os.path.expanduser(item))
            if os.path.exists(path):
                media_type = get_media_type(path)
                if media_type:
                    try:
                        data = Path(path).read_bytes()
                        final_attachments.append(
                            BinaryContent(data=data, media_type=media_type)
                        )
                    except Exception as e:
                        print_fn(f"Failed to read attachment {path}: {e}")
                else:
                    print_fn(f"Unknown media type for {path}")
            else:
                print_fn(f"Attachment file not found: {path}")
        else:
            # Assume it's already a suitable object (e.g. BinaryContent)
            final_attachments.append(item)
    return final_attachments


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
