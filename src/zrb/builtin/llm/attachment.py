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
