from collections.abc import Callable, Mapping
from typing import Any, Optional, Union

from zrb.config.config import SHOW_PROMPT
from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.string.conversion import to_variable_name
from zrb.helper.string.jinja import is_probably_jinja
from zrb.helper.typecheck import typechecked
from zrb.task_input.any_input import AnyInput
from zrb.task_input.constant import RESERVED_INPUT_NAMES

logger.debug(colored("Loading zrb.task_input.base_input", attrs=["dark"]))

# flake8: noqa E501

InputCallback = Callable[[Mapping[str, Any], Any], Any]
InputDefault = Callable[[Mapping[str, Any]], Any]


@typechecked
class BaseInput(AnyInput):
    """
    Base class for all Input.

    Input is an interface for a Task to read user input at the beginning of the execution.

    Attributes:
        name (str): The name of the input, used as a unique identifier.
        shortcut (Optional[str]): An optional single-character shortcut for the input.
        default (Optional[Any]): The default value of the input.
        callback (Optional[Any]): The default value of the input.
        description (Optional[str]): A brief description of what the input is for.
        show_default (Union[bool, JinjaTemplate, None]): Determines the default value to be shown.
        prompt (Union[bool, str]): The prompt text to be displayed when asking for the input.
        confirmation_prompt (Union[bool, str]): A prompt for confirmation if required.
        prompt_required (bool): Indicates whether a prompt is required.
        hide_input (bool): If True, the input value will be hidden (e.g., for passwords).
        is_flag (Optional[bool]): Specifies whether the input is a flag.
        flag_value (Optional[Any]): The value to be used if the input is a flag.
        multiple (bool): Allows multiple values for this input if True.
        count (bool): If True, counts the occurrences of the input.
        allow_from_autoenv (bool): If True, allows values to be automatically sourced from the environment.
        type (Optional[Any]): The expected type of the input value.
        hidden (bool): If True, the input is hidden and not rendered.
        show_choices (bool): Indicates whether to show available choices for the input.
        show_envvar (bool): If True, shows the corresponding environment variable.
        nargs (int): Number of arguments expected for this input.
        should_render (bool): Determines whether the input should be rendered.

    Examples:
        >>> from zrb import Input, Task
        >>> task = Task(
        >>>     name='task',
        >>>     inputs=[
        >>>         Input(name='delay', default=10, description='Delay')
        >>>     ]
        >>> )
    """

    __value_cache: Mapping[str, Any] = {}
    __default_cache: Mapping[str, Any] = {}

    def __init__(
        self,
        name: str,
        shortcut: Optional[str] = None,
        default: Optional[Union[Any, InputDefault]] = None,
        callback: Optional[InputCallback] = None,
        description: Optional[str] = None,
        show_default: Union[bool, str] = True,
        prompt: Union[bool, str] = True,
        confirmation_prompt: Union[bool, str] = False,
        prompt_required: bool = True,
        hide_input: bool = False,
        is_flag: Optional[bool] = None,
        flag_value: Optional[Any] = None,
        multiple: bool = False,
        count: bool = False,
        allow_from_autoenv: bool = True,
        type: Optional[Any] = None,
        hidden: bool = False,
        show_choices: bool = True,
        show_envvar: bool = False,
        nargs: int = 1,
        should_render: bool = True,
    ):
        if name in RESERVED_INPUT_NAMES:
            raise ValueError(f"Forbidden input name: {name}")
        self._name = name
        self._shortcut = shortcut
        self._prompt = prompt
        self._default = default
        self._callback = callback
        self._help = description if description is not None else name
        self._type = type
        self._show_default = show_default
        self._confirmation_prompt = confirmation_prompt
        self._prompt_required = prompt_required
        self._hide_input = hide_input
        self._is_flag = is_flag
        self._flag_value = flag_value
        self._multiple = multiple
        self._count = count
        self._allow_from_autoenv = allow_from_autoenv
        self._hidden = hidden
        self._show_choices = show_choices
        self._show_envvar = show_envvar
        self._nargs = nargs
        self.__should_render = should_render

    def get_name(self) -> str:
        return self._name

    def get_default(self) -> Any:
        if callable(self._default):
            return self._default(self.__value_cache)
        return self._default

    def get_param_decl(self) -> list[str]:
        param_decl: list[str] = [f"--{self._name}"]
        if self._shortcut is not None:
            param_decl.append(f"-{self._shortcut}")
        return param_decl

    def get_options(self) -> Mapping[str, Any]:
        options: Mapping[str, Any] = {
            "help": self._help,
            "type": self._type,
            "show_default": self._get_calculated_show_default(),
            "confirmation_prompt": self._confirmation_prompt,
            "prompt_required": self._prompt_required,
            "hide_input": self._hide_input,
            "is_flag": self._is_flag,
            "flag_value": self._flag_value,
            "multiple": self._multiple,
            "count": self._count,
            "allow_from_autoenv": self._allow_from_autoenv,
            "hidden": self._hidden,
            "show_choices": self._show_choices,
            "show_envvar": self._show_envvar,
            "nargs": self._nargs,
            "callback": self._wrapped_callback,
            "default": self._wrapped_default,
        }
        if SHOW_PROMPT:
            options["prompt"] = self._prompt
        return options

    def _wrapped_callback(self, ctx, param, value) -> Any:
        var_name = to_variable_name(self.get_name())
        if var_name not in self.__value_cache:
            if callable(self._callback):
                result = self._callback(self.__value_cache, value)
                self.__value_cache[var_name] = result
                return result
            self.__value_cache[var_name] = value
            return value
        return self.__value_cache[var_name]

    def _wrapped_default(self) -> Any:
        var_name = to_variable_name(self.get_name())
        if var_name not in self.__default_cache:
            if callable(self._default):
                default = self._default(self.__value_cache)
                self.__default_cache[var_name] = default
                return default
            self.__default_cache[var_name] = self._default
            return self._default
        return self.__default_cache[var_name]

    def _get_calculated_show_default(self) -> str:
        if self._show_default != True:
            return self._show_default
        if callable(self._default) or (
            self.__should_render and is_probably_jinja(self._default)
        ):
            return colored("Autogenerated", color="yellow")
        return f"{self._default}"

    def should_render(self) -> bool:
        return self.__should_render

    def is_hidden(self) -> bool:
        return False
