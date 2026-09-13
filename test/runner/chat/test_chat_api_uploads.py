"""Attachment upload handling for the web chat API.

`save_uploaded_attachment` writes under the shared temp directory, so these
cover where the bytes land and who is allowed to own the directory they land
in, alongside the happy path.
"""

import os
import stat

import pytest

# `os.chmod` on Windows toggles only the read-only flag; a directory there
# reports 0o777 whatever mode it was created with, so the private-mode
# guarantee is POSIX-only. The symlink and ownership checks still apply.
needs_posix_modes = pytest.mark.skipif(
    os.name != "posix", reason="POSIX permission bits (the mode under test)"
)


def testsave_uploaded_attachment_writes_file_and_returns_path():
    from zrb.runner.chat.chat_api_route import save_uploaded_attachment

    path = save_uploaded_attachment("some-session", "photo.png", b"data")
    try:
        assert os.path.isfile(path)
        assert os.path.basename(path).endswith("_photo.png")
        with open(path, "rb") as f:
            assert f.read() == b"data"
    finally:
        os.remove(path)


def testsave_uploaded_attachment_refuses_a_symlinked_upload_root(tmp_path, monkeypatch):
    """A pre-created symlink at the upload root must not take delivery.

    The root is a fixed name under the shared temp directory, so a local user
    can point it at a directory of their choosing before the server starts;
    `makedirs(exist_ok=True)` alone follows it.
    """
    import tempfile as tempfile_module

    from zrb.runner.chat.chat_api_route import save_uploaded_attachment

    monkeypatch.setattr(tempfile_module, "tempdir", str(tmp_path))
    victim = tmp_path / "victim"
    victim.mkdir()
    try:
        (tmp_path / "zrb_web_chat_uploads").symlink_to(victim)
    except OSError as error:
        # Windows needs SeCreateSymbolicLinkPrivilege or Developer Mode to
        # create one; without it there is no attack here to reproduce.
        pytest.skip(f"cannot create a symlink on this platform: {error}")

    with pytest.raises(PermissionError):
        save_uploaded_attachment("some-session", "photo.png", b"data")
    assert list(victim.iterdir()) == []


@needs_posix_modes
def testsave_uploaded_attachment_creates_a_private_upload_dir(tmp_path, monkeypatch):
    import stat as stat_module
    import tempfile as tempfile_module

    from zrb.runner.chat.chat_api_route import save_uploaded_attachment

    monkeypatch.setattr(tempfile_module, "tempdir", str(tmp_path))
    path = save_uploaded_attachment("some-session", "photo.png", b"data")
    mode = stat_module.S_IMODE(os.stat(os.path.dirname(path)).st_mode)
    assert mode == 0o700


@pytest.mark.parametrize(
    "session_id",
    ["..", ".", "../../../../etc", "/etc", "a/../..", "....//", "..\\..\\x"],
)
def testsave_uploaded_attachment_keeps_traversal_inside_the_upload_root(
    tmp_path, monkeypatch, session_id
):
    """`session_id` is a request path parameter, so it is untrusted input.

    Unsanitised, `..` resolves the upload dir to the shared temp directory
    itself — the write lands outside the root and the directory's mode is
    restated to 0700, which on a shared machine locks every other user out of
    it.
    """
    import tempfile as tempfile_module

    from zrb.runner.chat.chat_api_route import save_uploaded_attachment

    monkeypatch.setattr(tempfile_module, "tempdir", str(tmp_path))
    tmp_path.chmod(0o755)
    root = tmp_path / "zrb_web_chat_uploads"

    path = save_uploaded_attachment(session_id, "x.png", b"d")

    assert os.path.commonpath([os.path.realpath(path), os.path.realpath(root)]) == str(
        os.path.realpath(root)
    )
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o755


def testsave_uploaded_attachment_rejects_an_empty_session_id(tmp_path, monkeypatch):
    import tempfile as tempfile_module

    from zrb.runner.chat.chat_api_route import save_uploaded_attachment

    monkeypatch.setattr(tempfile_module, "tempdir", str(tmp_path))
    with pytest.raises(ValueError):
        save_uploaded_attachment("", "x.png", b"d")


def testsave_uploaded_attachment_keeps_a_generated_session_id_intact(
    tmp_path, monkeypatch
):
    """A real id must survive sanitising, or every session shares one dir."""
    import tempfile as tempfile_module

    from zrb.runner.chat.chat_api_route import save_uploaded_attachment
    from zrb.util.string.name import get_random_name

    monkeypatch.setattr(tempfile_module, "tempdir", str(tmp_path))
    session_id = get_random_name()
    path = save_uploaded_attachment(session_id, "x.png", b"d")
    assert os.path.basename(os.path.dirname(path)) == session_id


def testsave_uploaded_attachment_keeps_a_delegated_session_id_intact(
    tmp_path, monkeypatch
):
    import tempfile as tempfile_module

    from zrb.llm.util.subagent_session_naming import format_delegated_session_name
    from zrb.runner.chat.chat_api_route import save_uploaded_attachment

    monkeypatch.setattr(tempfile_module, "tempdir", str(tmp_path))
    session_id = format_delegated_session_name("brave-otter-4821", "researcher", "01")
    path = save_uploaded_attachment(session_id, "x.png", b"d")
    assert os.path.basename(os.path.dirname(path)) == session_id
