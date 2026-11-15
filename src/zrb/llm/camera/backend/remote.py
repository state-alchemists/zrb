"""A camera that is not on this machine: the one a page holds.

`RemoteCameraBackend` asks the face server for one JPEG and waits for the page to
answer it. Which physical camera a name means is the page's business — the phone
calls its rear lens `phone-back`, and nothing here has an opinion about that.

The names come from the page too, off GET /frame/devices, and they are cached:
`list_devices` is called while a completion is being drawn and must not wait on a
network, so a stale list is served from memory and refreshed behind it. A device
name that has never been seen is still attempted — a list that is a second old is
not a reason to refuse a photo, and the route fails loudly enough on its own.

One rule is shared with the rest of the camera package: a device that was named
does not become another camera's photo. If the page does not answer, there is no
photo, and `get_failure_hint` says where to look rather than the request quietly
landing on this laptop's camera instead.
"""

from __future__ import annotations

import asyncio
import http.client
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, TypeVar

from zrb.config.config import CFG
from zrb.llm.camera.backend.any_camera_backend import AnyCameraBackend
from zrb.llm.util.deadline import create_deadline, get_earlier, get_remaining
from zrb.llm.util.face_server import CAMERA_DEVICES_PATH, CAMERA_PATH
from zrb.util.async_thread import run_in_daemon

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

# How long a cached device list stands before the next `list_devices` refreshes
# it behind the completion that asked. A page's cameras change when the phone is
# picked up, not while a name is being typed, so a minute is generous.
DEVICE_CACHE_TTL_SECONDS = 60

# Every JPEG starts this way. A route that answered 200 with a page of HTML — an
# error page from something in front of the face server — is a photo of nothing.
_JPEG_START = b"\xff\xd8"


class RemoteCameraBackend(AnyCameraBackend):
    """The page's cameras, through *url*: a face server asked one photo at a time.

    *headers* travel with every request, so a server holding a token is reached
    the same way its audio routes are. A capture taking over *timeout* seconds is
    abandoned; ``0`` means no limit.
    """

    def __init__(
        self, url: str, headers: dict[str, str] | None = None, timeout: float = 15.0
    ) -> None:
        self._url = url.rstrip("/")
        self._headers = dict(headers or {})
        self._timeout = timeout
        self._last_error: str | None = None
        self._cached_devices: list[str] = []
        self._cached_at = 0.0
        # The in-flight listing, which is also what says one is running: a task
        # nobody holds is collected, and every later refresh would be wedged.
        self._refresh_task: "asyncio.Task[None] | None" = None

    @property
    def name(self) -> str:
        return "remote"

    @property
    def last_error(self) -> str | None:
        """What the page's server said about the last failed capture."""
        return self._last_error

    async def capture(self, device: str | None) -> bytes | None:
        return await self.capture_by(device, None)

    async def capture_by(
        self, device: str | None, deadline: float | None
    ) -> bytes | None:
        """`capture`, giving up at *deadline* (`time.monotonic()`) or after this
        backend's own timeout, whichever comes first."""
        deadline = get_earlier(deadline, create_deadline(self._timeout))
        self._last_error = None
        timeout = get_remaining(deadline)
        if timeout == 0:
            return None
        try:
            return await self._within(
                self._request_frame,
                device,
                timeout,
                name="zrb-camera-frame",
                limit=timeout,
            )
        except (OSError, RuntimeError, ValueError) as e:
            # A refused route, an unreachable server, a body that is not a
            # photo: all of them are no photo, and all of them are said.
            self._last_error = str(e) or type(e).__name__
            return None

    def list_devices(self) -> list[str]:
        """The page's cameras as last listed, refreshed behind this call."""
        self.schedule_device_refresh()
        return list(self._cached_devices)

    async def refresh_devices(self) -> list[str]:
        """Ask the page for its cameras, keeping the last list if it cannot say."""
        try:
            devices = await self._within(
                self._request_devices,
                self._timeout,
                name="zrb-camera-devices",
                limit=self._timeout,
            )
        except (OSError, RuntimeError, ValueError) as e:
            logger.debug(f"The page's cameras could not be listed: {e}")
            # The attempt is what gets remembered, so a page that is down is
            # asked once a minute rather than once per keystroke of a completion.
            self._cached_at = time.monotonic()
            return list(self._cached_devices)
        self._cached_devices = devices
        self._cached_at = time.monotonic()
        return devices

    def schedule_device_refresh(self) -> "asyncio.Task[None] | None":
        """Start `refresh_devices` in the background when the cache is stale.

        Returns the task, or ``None`` when the cache is fresh, a refresh is
        already running, or there is no running loop to put one on.
        """
        if self._refresh_task is not None or self._is_cache_fresh():
            return None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return None

        async def refresh() -> None:
            try:
                await self.refresh_devices()
            finally:
                self._refresh_task = None

        self._refresh_task = loop.create_task(refresh())
        return self._refresh_task

    def get_failure_hint(self) -> str:
        hint = (
            "  The camera belongs to the page: open it on the face server that "
            f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL names, grant that page "
            "camera access, and name one of the devices it lists, as in "
            "/photo <device>.\n"
        )
        if self._last_error:
            hint += f"  The page's server said: {self._last_error}\n"
        return hint

    def _is_cache_fresh(self) -> bool:
        # Age, not content: a page that has no cameras has still been asked, and
        # asking again on every keystroke would answer the same nothing.
        if self._cached_at == 0.0:
            return False
        return time.monotonic() - self._cached_at < DEVICE_CACHE_TTL_SECONDS

    async def _within(
        self,
        func: Callable[..., _T],
        *args: object,
        name: str,
        limit: float | None,
    ) -> _T:
        """*func* on a daemon thread, given up on after *limit* seconds.

        `urlopen`'s own timeout bounds one socket operation, not the body: a
        server that sends a byte every few hundred milliseconds keeps every read
        alive and holds `read()` open past any limit the request was given. So
        the deadline is enforced around the whole call here as well.

        The thread cannot be stopped, and it is left where it is: it ends on its
        next socket timeout, it writes nothing shared, and a value that lands
        after the caller has gone is dropped by `run_in_daemon` rather than
        reported. *limit* of ``0`` or ``None`` is no limit, as everywhere else
        in this package.
        """
        limit = limit if limit and limit > 0 else None
        try:
            return await asyncio.wait_for(
                run_in_daemon(func, *args, name=name), timeout=limit
            )
        except asyncio.TimeoutError as e:
            raise TimeoutError(
                f"the page did not answer within {limit:.1f}s"
                if limit
                else "the page did not answer"
            ) from e

    def _request_frame(self, device: str | None, timeout: float) -> bytes:
        """The page's answer for *device*, or a `RuntimeError` saying what came
        back instead. Blocking: it belongs on a daemon thread."""
        url = self._url + CAMERA_PATH
        if device:
            url += "?device=" + urllib.parse.quote(device)
        data = self._read(url, timeout)
        if not data.startswith(_JPEG_START):
            raise RuntimeError(
                f"{url} answered {len(data)} bytes, and they are not a JPEG"
            )
        return data

    def _request_devices(self, timeout: float) -> list[str]:
        """The names the page gives its cameras. Blocking, as above."""
        url = self._url + CAMERA_DEVICES_PATH
        payload = json.loads(self._read(url, timeout).decode() or "{}")
        names = payload.get("devices") if isinstance(payload, dict) else None
        if not isinstance(names, list):
            raise RuntimeError(f"{url} answered without a list of devices")
        return [str(name) for name in names if str(name).strip()]

    def _read(self, url: str, timeout: float) -> bytes:
        """*url*'s body, with a failed status turned into what the server said.

        `send_error(code, sentence)` puts the sentence in the status line, so a
        route that is refusing says why in one place and this side repeats it
        rather than guessing.
        """
        request = urllib.request.Request(url, headers=self._headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{url} answered {e.code}: {e.reason}") from e
        except http.client.HTTPException as e:
            # A connection that ended mid-body — `IncompleteRead` — or a status
            # line that is not one. These are `HTTPException`s and not `OSError`s,
            # so the caller's failure path would not hold them: a proxy that
            # closes early would be a crash rather than a missing photo.
            raise RuntimeError(f"{url} stopped answering: {e!r}") from e
