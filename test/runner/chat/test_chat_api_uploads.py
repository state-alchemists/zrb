"""Attachment upload handling for the web chat API.

`save_uploaded_attachment` writes under the shared temp directory, so these
cover where the bytes land and who is allowed to own the directory they land
in, alongside the happy path.
"""

import os

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
