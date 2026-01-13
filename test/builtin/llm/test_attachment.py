from zrb.builtin.llm.attachment import get_media_type


def test_get_media_type_audio():
    assert get_media_type("test.wav") == "audio/wav"
    assert get_media_type("test.MP3") == "audio/mpeg"
    assert get_media_type("test.ogg") == "audio/ogg"
    assert get_media_type("test.flac") == "audio/flac"
    assert get_media_type("test.aiff") == "audio/aiff"
    assert get_media_type("test.aac") == "audio/aac"


def test_get_media_type_image():
    assert get_media_type("test.jpg") == "image/jpeg"
    assert get_media_type("test.jpeg") == "image/jpeg"
    assert get_media_type("test.png") == "image/png"
    assert get_media_type("test.gif") == "image/gif"
    assert get_media_type("test.webp") == "image/webp"


def test_get_media_type_document():
    assert get_media_type("test.pdf") == "application/pdf"
    assert get_media_type("test.txt") == "text/plain"
    assert get_media_type("test.csv") == "text/csv"
    assert (
        get_media_type("test.docx")
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert (
        get_media_type("test.xlsx")
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert get_media_type("test.html") == "text/html"
    assert get_media_type("test.htm") == "text/html"
    assert get_media_type("test.md") == "text/markdown"
    assert get_media_type("test.doc") == "application/msword"
    assert get_media_type("test.xls") == "application/vnd.ms-excel"


def test_get_media_type_video():
    assert get_media_type("test.mkv") == "video/x-matroska"
    assert get_media_type("test.mov") == "video/quicktime"
    assert get_media_type("test.mp4") == "video/mp4"
    assert get_media_type("test.webm") == "video/webm"
    assert get_media_type("test.flv") == "video/x-flv"
    assert get_media_type("test.mpeg") == "video/mpeg"
    assert get_media_type("test.mpg") == "video/mpeg"
    assert get_media_type("test.wmv") == "video/x-ms-wmv"
    assert get_media_type("test.3gp") == "video/3gpp"


def test_get_media_type_unknown():
    assert get_media_type("test.unknown") is None
    assert get_media_type("test") is None
    assert get_media_type("") is None
