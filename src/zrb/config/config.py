import importlib.metadata as metadata
import os

from zrb.helper.string.untyped_conversion import (
    untyped_to_boolean,
    untyped_to_logging_level,
)


def _get_version() -> str:
    return metadata.version("zrb")


def _get_current_shell() -> str:
    current_shell = os.getenv("SHELL", "")
    if current_shell.endswith("zsh"):
        return "zsh"
    return "bash"


def _get_valid_container_backend(container_backend: str) -> str:
    if container_backend.lower().strip() == "podman":
        return "podman"
    return "docker"


def _get_default_tmp_dir() -> str:
    if os.path.isdir("/tmp"):
        return "/tmp"
    return os.path.expanduser(os.path.join("~", ".tmp"))


tmp_dir = os.getenv("ZRB_TMP_DIR", _get_default_tmp_dir())
default_shell = os.getenv("ZRB_SHELL", _get_current_shell())
default_editor = os.getenv("ZRB_EDITOR", "nano")
init_script_str = os.getenv("ZRB_INIT_SCRIPTS", "")
init_scripts = init_script_str.split(":") if init_script_str != "" else []
logging_level = untyped_to_logging_level(os.getenv("ZRB_LOGGING_LEVEL", "WARNING"))
should_load_builtin = untyped_to_boolean(os.getenv("ZRB_SHOULD_LOAD_BUILTIN", "1"))
env_prefix = os.getenv("ZRB_ENV", "")
show_advertisement = untyped_to_boolean(os.getenv("ZRB_SHOW_ADVERTISEMENT", "1"))
show_prompt = untyped_to_boolean(os.getenv("ZRB_SHOW_PROMPT", "1"))
show_time = untyped_to_boolean(os.getenv("ZRB_SHOW_TIME", "1"))
version = _get_version()
container_backend = _get_valid_container_backend(
    os.getenv("ZRB_CONTAINER_BACKEND", "docker")
)
enable_type_checking = untyped_to_boolean(os.getenv("ZRB_ENABLE_TYPE_CHECKING", "1"))
