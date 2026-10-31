import asyncio
import io
from unittest.mock import MagicMock

import pytest
from PIL import Image

from zrb.config.config import CFG
from zrb.llm.agent_state import current_model
from zrb.llm.permission.capability import Capability, tool_capability
from zrb.llm.screenshot import AnyScreenshotBackend, ScreenshotConfig, enable_screenshot
from zrb.llm.screenshot.feature import (
    capture_screenshot,
    create_screenshot_commands,
    create_screenshot_tools,
)


def _image(fmt: str, size=(64, 48)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format=fmt)
    return buffer.getvalue()


class FakeScreen(AnyScreenshotBackend):
    def __init__(self, image: bytes | None, displays: list[str] | None = None):
        self.image = image
        self.displays = displays or []
        self.captured: list[str | None] = []

    async def capture(self, display):
        self.captured.append(display)
        return self.image

    def list_displays(self):
        return self.displays

    def get_failure_hint(self):
        return "  grant screen recording\n"


class FakeUI:
    is_local = True

    def __init__(self):
        self.background_tasks: set = set()
        self.pending_attachments: list = []
        self.outputs: list[str] = []

    def append_to_output(self, text):
        self.outputs.append(text)

    def invalidate_ui(self):
        pass


class FakeRemoteUI(FakeUI):
    is_local = False


async def _run(command, text_args: dict, ui: FakeUI) -> None:
    command.handle(text_args, ui)
    await asyncio.gather(*ui.background_tasks)
    await asyncio.sleep(0)


def _screenshot_command(screen: FakeScreen, **config):
    config = ScreenshotConfig(commands=["/screenshot"], backend=screen, **config)
    return create_screenshot_commands(config.resolve())[0]


@pytest.mark.asyncio
async def test_the_screenshot_is_attached_to_the_next_message():
    screen = FakeScreen(_image("JPEG"))
    ui = FakeUI()

    await _run(_screenshot_command(screen), {"display": ""}, ui)

    (screenshot,) = ui.pending_attachments
    assert screenshot.media_type == "image/jpeg"
    assert any("Screenshot captured" in output for output in ui.outputs)
    assert screen.captured == [None]


@pytest.mark.asyncio
async def test_a_non_local_ui_is_refused_before_the_screen_is_captured():
    screen = FakeScreen(_image("JPEG"))
    ui = FakeRemoteUI()

    await _run(_screenshot_command(screen), {"display": ""}, ui)

    assert ui.pending_attachments == []
    assert screen.captured == []
    assert any("Screenshot refused" in output for output in ui.outputs)


@pytest.mark.asyncio
async def test_the_typed_display_wins_over_the_configured_one():
    screen = FakeScreen(_image("JPEG"))

    await _run(_screenshot_command(screen, display="1"), {"display": "2"}, FakeUI())
    await _run(_screenshot_command(screen, display="1"), {"display": ""}, FakeUI())

    assert screen.captured == ["2", "1"]


@pytest.mark.asyncio
async def test_a_failed_capture_explains_what_to_do():
    ui = FakeUI()

    await _run(_screenshot_command(FakeScreen(None)), {"display": ""}, ui)

    assert ui.pending_attachments == []
    assert any("grant screen recording" in output for output in ui.outputs)


@pytest.mark.asyncio
async def test_the_command_needs_a_ui():
    screen = FakeScreen(_image("JPEG"))

    result = _screenshot_command(screen).handle({"display": ""}, None)

    assert "needs an interactive chat session" in result
    assert screen.captured == []


def test_display_completion_comes_from_the_backend():
    command = _screenshot_command(FakeScreen(None, displays=["1", "2", "all"]))
    assert command.get_arg_completions("a") == ["all"]


def test_one_command_per_alias():
    config = ScreenshotConfig(commands=["/screenshot", "/ss"], backend=FakeScreen(None))
    commands = create_screenshot_commands(config.resolve())
    assert [command.command for command in commands] == ["/screenshot", "/ss"]


def test_enable_screenshot_reads_cfg_when_a_session_starts(monkeypatch):
    chat = MagicMock()
    enable_screenshot(chat)
    (create_commands,) = chat.append_custom_command.call_args.args

    monkeypatch.setattr(CFG, "LLM_SCREENSHOT_COMMANDS", ["/shot"])
    assert [command.command for command in create_commands()] == ["/shot"]


def test_an_empty_command_list_leaves_the_command_out():
    chat = MagicMock()
    enable_screenshot(chat, ScreenshotConfig(commands=[]))
    (create_commands,) = chat.append_custom_command.call_args.args

    assert create_commands() == []


def test_the_tool_can_be_had_without_the_command():
    chat = MagicMock()
    enable_screenshot(
        chat,
        ScreenshotConfig(commands=[], enable_tool=True, backend=FakeScreen(None)),
    )
    (create_commands,) = chat.append_custom_command.call_args.args
    (create_tools,) = chat.append_tool_factory.call_args.args

    assert create_commands() == []
    assert [tool.__name__ for tool in create_tools(None)] == ["TakeScreenshot"]


def test_enabling_the_screenshot_again_replaces_the_first_call():
    from zrb.llm.task.chat.task import LLMChatTask

    chat = LLMChatTask(name="screenshot-twice")
    enable_screenshot(chat)
    enable_screenshot(chat, ScreenshotConfig(commands=["/shot"]))

    commands = [
        command
        for factory in chat.custom_commands
        if callable(factory)
        for command in factory()
    ]
    assert [command.command for command in commands] == ["/shot"]


def test_the_built_in_chat_offers_the_command_but_not_the_tool():
    from zrb.builtin.llm.chat import llm_chat

    commands = [
        command.command
        for factory in llm_chat.custom_commands
        if callable(factory)
        for command in factory()
    ]
    assert "/screenshot" in commands
    assert CFG.DEFAULT_LLM_SCREENSHOT_ENABLE_TOOL == "off"


def _take_screenshot(screen: FakeScreen, **config):
    config = ScreenshotConfig(backend=screen, enable_tool=True, **config).resolve()
    (tool,) = create_screenshot_tools(config)
    return tool


def test_the_tool_is_off_unless_enabled(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_SCREENSHOT_ENABLE_TOOL", False)
    config = ScreenshotConfig(backend=FakeScreen(_image("JPEG"))).resolve()

    assert create_screenshot_tools(config) == []


def test_the_tool_builds_into_an_agent_tool():
    from pydantic_ai import Tool

    tool = Tool(_take_screenshot(FakeScreen(_image("JPEG"))))

    assert tool.name == "TakeScreenshot"
    assert "display" in tool.function_schema.json_schema["properties"]
    assert "unprompted" in tool.description


def test_the_tool_is_named_and_always_asks():
    tool = _take_screenshot(FakeScreen(_image("JPEG")))

    assert tool.__name__ == "TakeScreenshot"
    assert tool_capability(tool) == Capability.EXECUTE


@pytest.mark.asyncio
async def test_the_tool_shows_the_model_the_screen():
    screen = FakeScreen(_image("JPEG"))

    result = await _take_screenshot(screen, display="1")()

    assert screen.captured == ["1"]
    (screenshot,) = result.content
    assert screenshot.media_type == "image/jpeg"


@pytest.mark.asyncio
async def test_the_display_the_model_names_wins_over_the_configured_one():
    screen = FakeScreen(None)

    await _take_screenshot(screen, display="1")(display="2")

    assert screen.captured == ["2"]


@pytest.mark.asyncio
async def test_a_failed_capture_tells_the_model_not_to_retry():
    result = await _take_screenshot(FakeScreen(None))()

    assert "[SYSTEM SUGGESTION]" in result
    assert "grant screen recording" in result


@pytest.fixture
def text_only_model():
    token = current_model.set("openai:gpt-3.5-turbo")
    yield
    current_model.reset(token)


@pytest.mark.asyncio
async def test_a_text_only_model_gets_the_screen_described(
    text_only_model, monkeypatch
):
    async def describe(binary, multimodal_model):
        return "a terminal showing a stack trace"

    monkeypatch.setattr(CFG, "LLM_MULTIMODAL_MODEL", "openai:gpt-4o-mini")
    monkeypatch.setattr(
        "zrb.llm.tool.multimodal_describe.describe_binary_attachment", describe
    )

    result = await _take_screenshot(FakeScreen(_image("JPEG")))()

    assert result.startswith("Screenshot taken.")
    assert "a stack trace" in result


@pytest.mark.asyncio
async def test_a_text_only_model_without_a_describer_is_told_why(
    text_only_model, monkeypatch
):
    monkeypatch.setattr(CFG, "LLM_MULTIMODAL_MODEL", "")

    result = await _take_screenshot(FakeScreen(_image("JPEG")))()

    assert "[SYSTEM SUGGESTION]" in result
    assert "LLM_MULTIMODAL_MODEL" in result


@pytest.mark.asyncio
async def test_a_big_screen_is_scaled_down_for_the_model(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MAX_IMAGE_DIMENSION", 100)

    screenshot = await capture_screenshot(
        FakeScreen(_image("PNG", size=(3000, 2000))), None
    )

    assert max(Image.open(io.BytesIO(screenshot.data)).size) == 100
    assert screenshot.media_type == "image/jpeg"


def test_enable_screenshot_reads_the_tool_switch_when_a_session_starts(monkeypatch):
    chat = MagicMock()
    enable_screenshot(chat, ScreenshotConfig(backend=FakeScreen(_image("JPEG"))))
    (create_tools,) = chat.append_tool_factory.call_args.args

    monkeypatch.setattr(CFG, "LLM_SCREENSHOT_ENABLE_TOOL", True)
    assert [tool.__name__ for tool in create_tools(None)] == ["TakeScreenshot"]
