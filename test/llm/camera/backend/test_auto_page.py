"""`AutoCameraBackend` with a page attached: which name goes to which camera.

The rule the rest of the camera package already keeps is the one held here: a
device that was named does not become another camera's photo. So a name this
machine does not have is the page's, a name it does have stays its own, and a
page that refuses leaves no photo at all rather than the laptop's.
"""

from __future__ import annotations

import pytest

from zrb.llm.camera.backend.auto import AutoCameraBackend
from zrb.llm.camera.backend.ffmpeg import FfmpegCameraBackend
from zrb.llm.camera.backend.remote import RemoteCameraBackend
from zrb.llm.camera.backend.termux import TermuxCameraBackend

from .conftest import JPEG


class LocalCamera(FfmpegCameraBackend):
    """This machine's camera, answering without one: records who asked it what."""

    def __init__(self, names: tuple[str, ...] = ("0", "1")) -> None:
        super().__init__(timeout=0)
        self._names = list(names)
        self.asked: list[str | None] = []
        self.refreshes = 0  # how often its slow listing was asked to settle

    def list_devices(self) -> list[str]:
        return list(self._names)

    async def refresh_devices(self) -> list[str]:
        self.refreshes += 1
        return list(self._names)

    async def capture_by(
        self, device: str | None, deadline: float | None
    ) -> bytes | None:
        self.asked.append(device)
        return b"local-photo"

    def get_failure_hint(self) -> str:
        return "  local hint\n"


class LateListingCamera(LocalCamera):
    """A machine whose slow listing has a camera the fast one has not found yet."""

    def __init__(self, fast: tuple[str, ...], slow: tuple[str, ...]) -> None:
        super().__init__(fast)
        self._slow = list(slow)

    async def refresh_devices(self) -> list[str]:
        self.refreshes += 1
        self._names = list(self._slow)
        return list(self._names)


class BrokenListingCamera(LocalCamera):
    """A machine whose slow listing fails, as a missing ffmpeg does."""

    async def refresh_devices(self) -> list[str]:
        self.refreshes += 1
        raise RuntimeError("ffmpeg is gone")


class FailingLocalCamera(LocalCamera):
    """A camera on this machine that cannot open, as one held by another app does."""

    async def capture_by(
        self, device: str | None, deadline: float | None
    ) -> bytes | None:
        self.asked.append(device)
        return None


def _backend(face_page, local: LocalCamera, timeout: float = 5.0):
    # termux is real and unused: these run where `is_termux()` is false, so the
    # ffmpeg one is the branch under test.
    page = RemoteCameraBackend(face_page.url, timeout=timeout)
    backend = AutoCameraBackend(
        termux=TermuxCameraBackend(timeout=0),
        ffmpeg=local,
        timeout=timeout,
        remote=page,
    )
    return backend, page


@pytest.mark.asyncio
async def test_a_name_this_machine_does_not_have_is_the_pages(face_page):
    local = LocalCamera()
    backend, page = _backend(face_page, local)
    await page.refresh_devices()

    assert await backend.capture("phone-back") == JPEG
    assert local.asked == []
    assert face_page.frame_requests == ["/frame?device=phone-back"]


@pytest.mark.asyncio
async def test_a_name_this_machine_has_stays_this_machines(face_page):
    local = LocalCamera()
    backend, page = _backend(face_page, local)
    await page.refresh_devices()

    assert await backend.capture("0") == b"local-photo"
    assert local.asked == ["0"]
    assert face_page.frame_requests == []


@pytest.mark.asyncio
async def test_a_camera_listed_late_is_still_this_machines(face_page):
    """The slow listings land behind the fast one, so a missing name is not yet
    a name this machine does not have."""
    local = LateListingCamera(fast=("0", "1"), slow=("0", "1", "USB Camera"))
    backend, page = _backend(face_page, local)
    await page.refresh_devices()

    assert await backend.capture("USB Camera") == b"local-photo"
    assert local.asked == ["USB Camera"]
    assert face_page.frame_requests == []
    assert local.refreshes == 1


@pytest.mark.asyncio
async def test_a_name_this_machine_already_has_settles_nothing(face_page):
    """Settling costs a probe, so the names already listed skip it."""
    local = LateListingCamera(fast=("0", "1"), slow=("0", "1", "USB Camera"))
    backend, page = _backend(face_page, local)
    await page.refresh_devices()

    assert await backend.capture("0") == b"local-photo"
    assert local.refreshes == 0


@pytest.mark.asyncio
async def test_a_listing_that_breaks_leaves_the_name_to_the_page(face_page):
    local = BrokenListingCamera()
    backend, page = _backend(face_page, local)
    await page.refresh_devices()

    assert await backend.capture("phone-back") == JPEG
    assert local.asked == []
    assert local.refreshes == 1


@pytest.mark.asyncio
async def test_no_device_is_this_machines_as_it_always_was(face_page):
    local = LocalCamera()
    backend, page = _backend(face_page, local)
    await page.refresh_devices()

    assert await backend.capture(None) == b"local-photo"
    assert face_page.frame_requests == []


@pytest.mark.asyncio
async def test_a_page_camera_that_fails_is_not_the_laptops_photo(face_page):
    local = LocalCamera()
    backend, page = _backend(face_page, local)
    await page.refresh_devices()
    face_page.status = 503
    face_page.failure = "no page is open"

    assert await backend.capture("phone-back") is None
    assert local.asked == []
    assert "no page is open" in backend.get_failure_hint()


@pytest.mark.asyncio
async def test_a_local_failure_hints_the_local_camera_after_a_page_failure(face_page):
    """The hint follows the attempt, not the last error anyone recorded."""
    local = FailingLocalCamera()
    backend, page = _backend(face_page, local)
    await page.refresh_devices()
    face_page.status = 503
    face_page.failure = "no page is open"

    assert await backend.capture("phone-back") is None  # the page went first
    assert await backend.capture("0") is None  # and then this machine's camera

    hint = backend.get_failure_hint()
    assert "local hint" in hint
    assert "no page is open" not in hint


@pytest.mark.asyncio
async def test_a_page_failure_hints_the_page_after_a_local_failure(face_page):
    local = FailingLocalCamera()
    backend, page = _backend(face_page, local)
    await page.refresh_devices()

    assert await backend.capture("0") is None  # this machine's camera went first
    face_page.status = 503
    face_page.failure = "no page is open"
    assert await backend.capture("phone-back") is None

    assert "no page is open" in backend.get_failure_hint()


@pytest.mark.asyncio
async def test_the_pages_names_are_offered_after_this_machines(face_page):
    local = LocalCamera()
    backend, page = _backend(face_page, local)
    await page.refresh_devices()

    assert backend.list_devices() == ["0", "1", "phone-back", "phone-front"]


@pytest.mark.asyncio
async def test_without_a_page_only_this_machines_are_offered(face_page):
    local = LocalCamera()
    backend = AutoCameraBackend(
        termux=TermuxCameraBackend(timeout=0), ffmpeg=local, timeout=5.0
    )

    assert backend.list_devices() == ["0", "1"]
    assert await backend.capture("phone-back") == b"local-photo"
