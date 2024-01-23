import importlib.metadata as metadata
import os

from zrb.helper.string.conversion import to_boolean, to_logging_level
from zrb.helper.typecheck import typechecked


@typechecked
def get_version() -> str:
    try:
        return metadata.version("zrb")
    except metadata.PackageNotFoundError:
        import flit

        meta = flit.read_module_metadata("zrb")
        return str(meta["module"]["version"])


@typechecked
def get_current_shell() -> str:
    current_shell = os.getenv("SHELL", "")
    if current_shell.endswith("zsh"):
        return "zsh"
    return "bash"


default_shell = os.getenv("ZRB_SHELL", get_current_shell())
init_script_str = os.getenv("ZRB_INIT_SCRIPTS", "")
init_scripts = init_script_str.split(":") if init_script_str != "" else []
logging_level = to_logging_level(os.getenv("ZRB_LOGGING_LEVEL", "WARNING"))
should_load_builtin = to_boolean(os.getenv("ZRB_SHOULD_LOAD_BUILTIN", "1"))
env_prefix = os.getenv("ZRB_ENV", "")
show_advertisement = to_boolean(os.getenv("ZRB_SHOW_ADVERTISEMENT", "1"))
show_prompt = to_boolean(os.getenv("ZRB_SHOW_PROMPT", "1"))
show_time = to_boolean(os.getenv("ZRB_SHOW_TIME", "1"))
version = get_version()
