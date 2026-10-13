import asyncio
from unittest.mock import MagicMock

import pytest

from zrb.config.config import CFG
from zrb.llm.camera import AnyCameraBackend, CameraConfig, enable_camera
from zrb.llm.camera.feature import create_camera_commands, create_camera_tools
from zrb.llm.permission.capability import Capability, tool_capability


class FakeCamera(AnyCameraBackend):
    def __init__(self, photo: bytes | None, devices: list[str] | None = None):
        self.photo = photo
        self.devices = devices or []
        self.captured_from: list[str | None] = []

    async def capture(self, device):
        self.captured_from.append(device)
        return self.photo

    def list_devices(self):
        return self.devices

    def get_failure_hint(self):
        return "  plug the camera in\n"


class FakeUI:
    def __init__(self):
        self.background_tasks: set = set()
        self.pending_attachments: list = []
        self.outputs: list[str] = []

    def append_to_output(self, text):
        self.outputs.append(text)

    def invalidate_ui(self):
        pass


async def _run(command, text_args: dict, ui: FakeUI) -> None:
    command.handle(text_args, ui)
    await asyncio.gather(*ui.background_tasks)
    await asyncio.sleep(0)


def _photo_command(camera: FakeCamera, **config):
    config = CameraConfig(commands=["/photo"], backend=camera, **config).resolve()
    return create_camera_commands(config)[0]


@pytest.mark.asyncio
async def test_photo_is_attached_to_the_next_message():
    camera = FakeCamera(b"\xff\xd8\xff-fake-jpeg")
    ui = FakeUI()

    await _run(_photo_command(camera), {"device": ""}, ui)

    assert len(ui.pending_attachments) == 1
    assert any("Photo captured" in output for output in ui.outputs)
    assert camera.captured_from == [None]


@pytest.mark.asyncio
async def test_the_typed_device_wins_over_the_configured_one():
    camera = FakeCamera(b"jpeg")

    await _run(_photo_command(camera, device="0"), {"device": "1"}, FakeUI())
    await _run(_photo_command(camera, device="0"), {"device": ""}, FakeUI())

    assert camera.captured_from == ["1", "0"]


@pytest.mark.asyncio
async def test_failed_capture_explains_what_to_do():
    ui = FakeUI()

    await _run(_photo_command(FakeCamera(None)), {"device": ""}, ui)

    assert ui.pending_attachments == []
    assert any("plug the camera in" in output for output in ui.outputs)


def test_device_completion_comes_from_the_backend():
    command = _photo_command(FakeCamera(None, devices=["/dev/video0", "0"]))
    assert command.get_arg_completions("/dev") == ["/dev/video0"]


def test_one_command_per_alias():
    config = CameraConfig(commands=["/photo", "/p"], backend=FakeCamera(None))
    commands = create_camera_commands(config.resolve())
    assert [command.command for command in commands] == ["/photo", "/p"]


def test_enable_camera_reads_cfg_when_a_session_starts(monkeypatch):
    chat = MagicMock()
    enable_camera(chat)
    (create_commands,) = chat.append_custom_command.call_args.args

    monkeypatch.setattr(CFG, "LLM_CAMERA_COMMANDS", ["/snap"])
    assert [command.command for command in create_commands()] == ["/snap"]


def test_an_empty_command_list_leaves_the_camera_out():
    chat = MagicMock()
    enable_camera(chat, CameraConfig(commands=[]))
    (create_commands,) = chat.append_custom_command.call_args.args

    assert create_commands() == []


def test_enabling_the_camera_again_replaces_the_first_call():
    from zrb.llm.task.chat.task import LLMChatTask

    chat = LLMChatTask(name="camera-twice")
    enable_camera(chat)
    enable_camera(chat, CameraConfig(commands=["/snap"]))

    commands = [
        command
        for factory in chat.custom_commands
        if callable(factory)
        for command in factory()
    ]
    assert [command.command for command in commands] == ["/snap"]


def _take_photo(camera: FakeCamera, **config):
    config = CameraConfig(backend=camera, enable_tool=True, **config).resolve()
    (tool,) = create_camera_tools(config)
    return tool


def test_the_photo_tool_is_off_unless_enabled(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_CAMERA_ENABLE_TOOL", False)
    config = CameraConfig(backend=FakeCamera(b"jpeg")).resolve()

    assert create_camera_tools(config) == []


def test_the_photo_tool_builds_into_an_agent_tool():
    from pydantic_ai import Tool

    tool = Tool(_take_photo(FakeCamera(b"jpeg")))

    assert tool.name == "TakePhoto"
    assert "device" in tool.function_schema.json_schema["properties"]


def test_the_photo_tool_is_named_and_always_asks():
    tool = _take_photo(FakeCamera(b"jpeg"))

    assert tool.__name__ == "TakePhoto"
    assert tool_capability(tool) == Capability.EXECUTE


@pytest.mark.asyncio
async def test_the_photo_tool_shows_the_model_the_photo():
    camera = FakeCamera(b"\xff\xd8\xff-fake-jpeg")

    result = await _take_photo(camera, device="0")()

    assert camera.captured_from == ["0"]
    (photo,) = result.content
    assert photo.media_type == "image/jpeg"


@pytest.mark.asyncio
async def test_the_device_the_model_names_wins_over_the_configured_one():
    camera = FakeCamera(None)

    await _take_photo(camera, device="0")(device="2")

    assert camera.captured_from == ["2"]


@pytest.mark.asyncio
async def test_a_failed_photo_tells_the_model_not_to_retry():
    result = await _take_photo(FakeCamera(None))()

    assert "[SYSTEM SUGGESTION]" in result
    assert "plug the camera in" in result


def test_enable_camera_reads_the_tool_switch_when_a_session_starts(monkeypatch):
    chat = MagicMock()
    enable_camera(chat, CameraConfig(backend=FakeCamera(b"jpeg")))
    (create_tools,) = chat.append_tool_factory.call_args.args

    monkeypatch.setattr(CFG, "LLM_CAMERA_ENABLE_TOOL", True)
    assert [tool.__name__ for tool in create_tools(None)] == ["TakePhoto"]
