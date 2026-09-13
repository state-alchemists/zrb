"""Attachment upload handling for the web chat API.

`save_uploaded_attachment` writes under the shared temp directory, so these
cover where the bytes land and who is allowed to own the directory they land
in, alongside the happy path.
"""

import os
import stat
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

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


@needs_posix_modes
def testsave_uploaded_attachment_refuses_a_dir_swapped_after_validation(
    tmp_path, monkeypatch
):
    """Close the window between validating the directory and writing into it.

    Validating by path and then opening by path lets a local attacker replace
    the checked directory with a symlink in between. The write is done
    relative to a descriptor taken on the validated directory, so the swap has
    nothing left to redirect.

    `uuid.uuid4` is the seam: it runs after validation and before the write,
    so swapping the directory from inside it reproduces the race exactly.
    """
    import tempfile as tempfile_module
    import uuid as uuid_module

    from zrb.runner.chat.chat_api_route import save_uploaded_attachment

    monkeypatch.setattr(tempfile_module, "tempdir", str(tmp_path))
    victim = tmp_path / "victim"
    victim.mkdir()
    session_dir = tmp_path / "zrb_web_chat_uploads" / "sess"
    real_uuid4 = uuid_module.uuid4

    def swap_then_name():
        if session_dir.is_dir() and not session_dir.is_symlink():
            os.rmdir(session_dir)
            os.symlink(victim, session_dir)
        return real_uuid4()

    monkeypatch.setattr(uuid_module, "uuid4", swap_then_name)

    with pytest.raises(OSError):
        save_uploaded_attachment("sess", "x.png", b"pwned")
    assert list(victim.iterdir()) == []


@pytest.mark.asyncio
async def test_upload_attachment_rejects_a_file_over_the_cap(
    client: AsyncClient, monkeypatch
):
    """An oversized upload is refused without being read whole into memory."""
    from zrb.config.config import CFG

    monkeypatch.setattr(type(CFG), "LLM_MAX_ATTACHMENT_BYTES", 32)
    payload = b"\x89PNG\r\n\x1a\n" + b"x" * 4096

    response = await client.post(
        "/api/v1/chat/sessions/test/attachments",
        files={"file": ("big.png", payload, "image/png")},
    )

    assert response.status_code == 400
    assert "too large" in response.json()["error"]


@pytest.mark.asyncio
async def test_upload_attachment_success(client: AsyncClient, tmp_path):
    dest = tmp_path / "saved.png"
    with patch(
        "zrb.runner.chat.chat_api_route.save_uploaded_attachment",
        return_value=str(dest),
    ) as mock_save:
        response = await client.post(
            "/api/v1/chat/sessions/test/attachments",
            files={"file": ("photo.png", b"\x89PNG\r\n\x1a\n" + b"rest", "image/png")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["path"] == str(dest)
    assert data["name"] == "photo.png"
    mock_save.assert_called_once()
    assert mock_save.call_args[0][0] == "test"
    assert mock_save.call_args[0][1] == "photo.png"


@pytest.mark.asyncio
async def test_upload_attachment_rejects_unsupported_type(client: AsyncClient):
    response = await client.post(
        "/api/v1/chat/sessions/test/attachments",
        files={"file": ("evil.xyz", b"whatever", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["error"]


@pytest.mark.asyncio
async def test_upload_attachment_rejects_spoofed_content(client: AsyncClient):
    response = await client.post(
        "/api/v1/chat/sessions/test/attachments",
        files={"file": ("fake.png", b"not actually a png", "image/png")},
    )
    assert response.status_code == 400
    assert "doesn't look like" in response.json()["error"]


@pytest.mark.asyncio
async def test_upload_attachment_rejects_oversized(client: AsyncClient, monkeypatch):
    from zrb.config.config import CFG

    monkeypatch.setattr(CFG, "LLM_MAX_ATTACHMENT_BYTES", 4)
    response = await client.post(
        "/api/v1/chat/sessions/test/attachments",
        files={"file": ("photo.png", b"\x89PNG\r\n\x1a\n" + b"rest", "image/png")},
    )
    assert response.status_code == 400
    assert "too large" in response.json()["error"]


@pytest.mark.asyncio
async def test_upload_attachment_forbidden_without_access(client: AsyncClient):
    no_access_user = MagicMock()
    no_access_user.can_access_task.return_value = False
    mock_task = MagicMock()

    with (
        patch(
            "zrb.runner.chat.chat_api_route.get_user_from_request",
            new=AsyncMock(return_value=no_access_user),
        ),
        patch(
            "zrb.runner.chat.chat_api_route.get_llm_chat_task",
            new=AsyncMock(return_value=mock_task),
        ),
    ):
        response = await client.post(
            "/api/v1/chat/sessions/test/attachments",
            files={"file": ("photo.png", b"\x89PNG\r\n\x1a\n" + b"rest", "image/png")},
        )
    assert response.status_code == 403
