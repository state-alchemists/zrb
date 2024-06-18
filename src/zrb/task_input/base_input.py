from zrb.config.config import show_prompt
from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, List, Mapping, Optional, Union
from zrb.task_input.any_input import AnyInput
from zrb.task_input.constant import RESERVED_INPUT_NAMES

logger.debug(colored("Loading zrb.task_input.base_input", attrs=["dark"]))

# flake8: noqa E501


@typechecked
class BaseInput(AnyInput):
    """
    Base class for all Input.

    Input is an interface for a Task to read user input at the beginning of the execution.

    Attributes:
        name (str): The name of the input, used as a unique identifier.
        shortcut (Optional[str]): An optional single-character shortcut for the input.
        default (Optional[Any]): The default value of the input.
        description (Optional[str]): A brief description of what the input is for.
        show_default (Union[bool, JinjaTemplate, None]): Determines whether the default value should be displayed.
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

    __input_value_map: Mapping[str, Any] = {}
    __default: Mapping[str, Any] = {}

    def __init__(
        self,
        name: str,
        shortcut: Optional[str] = None,
        default: Optional[Any] = None,
        description: Optional[str] = None,
        show_default: Union[bool, str, None] = None,
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
        return self._default

    def get_param_decl(self) -> List[str]:
        param_decl: List[str] = [f"--{self._name}"]
        if self._shortcut is not None:
            param_decl.append(f"-{self._shortcut}")
        return param_decl

    def get_options(self) -> Mapping[str, Any]:
        options: Mapping[str, Any] = {
            "default": self._default,
            "help": self._help,
            "type": self._type,
            "show_default": self._show_default,
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
            "callback": self.__wrapped_callback,
            "default": self.__wrapped_default,
        }
        if show_prompt:
            options["prompt"] = self._prompt
        return options
    
    def __wrapped_callback(self, ctx, param, value) -> Any:
        if self.name not in self.__input_value_map:
            self.__input_value_map[self.name] = value
        return self.__input_value_map[self.name]
    
    def __wrapped_default(self) -> Any:
        if self.name not in self.__default:
            if callable(self._default):
                default = self._default(self.__input_value_map)
                self.__default[self.name] = default
                return default
            self.__default[self.name] = self._default
            return self._default
        return self.__default[self.name]

    def should_render(self) -> bool:
        return self.__should_render

    def is_hidden(self) -> bool:
        return False
