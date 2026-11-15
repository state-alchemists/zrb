"""The page's cameras: one photo asked of the face server, its names cached.

No phone and no face server reaches a test, so `conftest.py` plays the server's
half on a real loopback port. What is held here is the contract in both
directions: a name reaches the route that asks for *that* camera, and a route
that refuses reaches the user as a sentence rather than as a photo of something
else.
"""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

from zrb.config.config import CFG
from zrb.llm.camera.backend import remote
from zrb.llm.camera.backend.remote import RemoteCameraBackend

from .conftest import JPEG


def _backend(page, timeout: float = 5.0, token: str = "") -> RemoteCameraBackend:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return RemoteCameraBackend(page.url, headers=headers, timeout=timeout)


@pytest.mark.asyncio
async def test_a_named_device_asks_the_page_for_that_camera(face_page):
    backend = _backend(face_page)

    photo = await backend.capture("phone-back")

    assert photo == JPEG
    assert face_page.requests == [("/frame?device=phone-back", None)]


@pytest.mark.asyncio
async def test_no_device_asks_the_page_for_its_own_default(face_page):
    backend = _backend(face_page)

    assert await backend.capture(None) == JPEG
    assert face_page.requests == [("/frame", None)]


@pytest.mark.asyncio
async def test_a_refused_capture_is_no_photo_and_says_what_the_server_said(
    face_page,
):
    face_page.status = 503
    face_page.failure = "no page is open"
    backend = _backend(face_page)

    assert await backend.capture("phone-back") is None
    assert "no page is open" in (backend.last_error or "")
    assert "no page is open" in backend.get_failure_hint()


@pytest.mark.asyncio
async def test_an_answer_that_is_not_a_jpeg_is_not_a_photo(face_page):
    """A server in front of the face server can answer 200 with its own page."""
    face_page.jpeg = b"<html><body>Welcome</body></html>"
    face_page.content_type = "text/html"
    backend = _backend(face_page)

    assert await backend.capture(None) is None
    assert "not a JPEG" in (backend.last_error or "")


@pytest.mark.asyncio
async def test_a_page_that_never_answers_is_given_up_on(face_page):
    face_page.delay_seconds = 1.0
    backend = _backend(face_page, timeout=0.2)

    assert await backend.capture("phone-back") is None
    assert backend.last_error


@pytest.mark.asyncio
async def test_a_body_that_stops_short_is_no_photo_rather_than_a_crash(face_page):
    """`IncompleteRead` is an `HTTPException`, not an `OSError`.

    A proxy that closes the connection mid-body raises it out of `read()`, and a
    failure path that only knows `OSError` lets it escape as a crash in the middle
    of a tool call instead of a camera that did not answer.
    """
    face_page.truncate_at = 6

    assert await _backend(face_page).capture("phone-back") is None


@pytest.mark.asyncio
async def test_a_body_that_drips_in_is_given_up_on_at_the_deadline(face_page):
    """A socket timeout bounds one read, not the body.

    A server that sends a byte every few hundred milliseconds keeps every read
    alive, so a capture that trusted the per-read timeout would wait for as long
    as the page cared to take.
    """
    face_page.jpeg = JPEG + b"\x00" * 40  # long enough to outlast the deadline
    face_page.trickle = (1, 0.05)
    backend = _backend(face_page, timeout=0.4)
    started = time.monotonic()

    assert await backend.capture("phone-back") is None
    assert time.monotonic() - started < 1.5
    assert backend.last_error


@pytest.mark.asyncio
async def test_a_capture_that_timed_out_leaves_no_thread_behind(face_page):
    """The thread is hung up on, not merely stopped being waited for.

    A blocked read does not wake when the response is closed; it wakes when the
    socket is shut down. Without that, every capture that timed out kept a
    thread and a socket for as long as the page kept trickling.
    """
    face_page.jpeg = JPEG + b"\x00" * 400
    face_page.trickle = (1, 0.05)
    backend = _backend(face_page, timeout=0.3)

    assert await backend.capture("phone-back") is None

    for _ in range(50):
        if not _frame_threads():
            break
        await asyncio.sleep(0.02)
    assert _frame_threads() == []


def _frame_threads() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name == "zrb-camera-frame"]


@pytest.mark.asyncio
async def test_the_token_travels_with_the_photo(face_page):
    backend = _backend(face_page, token="s3cret")

    await backend.capture("phone-front")

    assert face_page.requests == [("/frame?device=phone-front", "Bearer s3cret")]


@pytest.mark.asyncio
async def test_the_names_are_the_pages_own(face_page):
    backend = _backend(face_page)

    assert await backend.refresh_devices() == ["phone-back", "phone-front"]
    assert backend.list_devices() == ["phone-back", "phone-front"]


def test_listing_devices_does_not_wait_for_a_network(face_page):
    """Called while a completion is drawn: an answer now, not a request now."""
    backend = _backend(face_page)

    assert backend.list_devices() == []
    assert face_page.requests == []


@pytest.mark.asyncio
async def test_a_listing_that_fails_keeps_the_names_it_had(face_page):
    backend = _backend(face_page)
    await backend.refresh_devices()
    face_page.status = 503

    assert await backend.refresh_devices() == ["phone-back", "phone-front"]


@pytest.mark.asyncio
async def test_a_stale_listing_refreshes_behind_the_call(face_page, monkeypatch):
    backend = _backend(face_page)
    await backend.refresh_devices()
    face_page.devices = ["phone-back"]
    monkeypatch.setattr(remote, "DEVICE_CACHE_TTL_SECONDS", 0)

    # The list answered is the one from before; the refresh that brings the new
    # one is already running, and the next call reads it.
    assert backend.list_devices() == ["phone-back", "phone-front"]
    for _ in range(50):
        if len(face_page.requests) >= 2:
            break
        await asyncio.sleep(0.02)
    assert backend.list_devices() == ["phone-back"]


@pytest.mark.asyncio
async def test_a_timeout_of_zero_means_no_limit_rather_than_a_dead_socket(face_page):
    """`HTTPConnection(timeout=0)` is a non-blocking socket, not an endless wait."""
    backend = _backend(face_page, timeout=0)

    assert await backend.refresh_devices() == ["phone-back", "phone-front"]
    assert await backend.capture("phone-back") == JPEG


@pytest.mark.asyncio
async def test_a_page_that_never_accepts_is_given_up_on_without_a_thread(face_page):
    """A black-holed address: the connection is never established.

    `HTTPConnection` hands its timeout to `socket.create_connection`, so the
    connect is bounded by the same number the response read is — the worker ends
    with the capture rather than waiting for the operating system to give up.
    """
    backend = RemoteCameraBackend("http://10.255.255.1:9", timeout=0.4)
    started = time.monotonic()

    assert await backend.capture(None) is None
    assert time.monotonic() - started < 3
    for _ in range(100):
        if not _frame_threads():
            break
        await asyncio.sleep(0.02)
    assert _frame_threads() == []


def test_the_hint_names_the_setting_that_holds_the_page():
    backend = RemoteCameraBackend("http://127.0.0.1:7777")

    hint = backend.get_failure_hint()

    assert f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL" in hint


def test_a_url_that_is_not_http_is_refused_when_the_backend_is_built():
    """A typo would otherwise be spoken to in cleartext, with its token attached."""
    with pytest.raises(ValueError):
        RemoteCameraBackend("htp://127.0.0.1:7777")


def test_a_url_with_no_host_is_refused_when_the_backend_is_built():
    with pytest.raises(ValueError):
        RemoteCameraBackend("http://")


def test_the_page_backend_is_reachable_from_the_package():
    """The other built-ins are imported from `zrb.llm.camera`; this one too."""
    from zrb.llm.camera import RemoteCameraBackend as from_package

    assert from_package is RemoteCameraBackend
