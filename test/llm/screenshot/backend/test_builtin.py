import pytest

from zrb.llm.screenshot import ScreenshotConfig
from zrb.llm.screenshot.backend import (
    AutoScreenshotBackend,
    PillowScreenshotBackend,
    ScreenshotToolBackend,
    get_screenshot_backend,
)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("auto", AutoScreenshotBackend),
        ("", AutoScreenshotBackend),
        (" Pillow ", PillowScreenshotBackend),
        ("grim", ScreenshotToolBackend),
        ("powershell.exe", ScreenshotToolBackend),
    ],
)
def test_names_map_to_builtin_backends(name, expected):
    backend = get_screenshot_backend(name, ScreenshotConfig().resolve())
    assert isinstance(backend, expected)


def test_a_program_name_picks_that_program():
    backend = get_screenshot_backend("scrot", ScreenshotConfig().resolve())
    assert backend.name == "scrot"


def test_a_backend_object_is_used_as_is():
    backend = PillowScreenshotBackend()
    assert get_screenshot_backend(backend, ScreenshotConfig().resolve()) is backend


def test_an_unknown_name_is_refused():
    with pytest.raises(ValueError, match="unknown screenshot backend"):
        get_screenshot_backend("polaroid", ScreenshotConfig().resolve())
