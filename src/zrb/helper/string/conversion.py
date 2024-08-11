from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.string.untyped_conversion import (
    untyped_to_boolean,
    untyped_to_cli_name,
    untyped_to_logging_level,
    untyped_to_variable_name,
)
from zrb.helper.typecheck import typechecked

logger.debug(colored("Loading zrb.helper.string.conversion", attrs=["dark"]))


@typechecked
def to_cli_name(name: str) -> str:
    return untyped_to_cli_name((name))


@typechecked
def to_variable_name(string: str) -> str:
    return untyped_to_variable_name(string)


@typechecked
def to_boolean(string: str) -> bool:
    return untyped_to_boolean(string)


@typechecked
def to_logging_level(logging_level_str: str) -> int:
    return untyped_to_logging_level(logging_level_str)
