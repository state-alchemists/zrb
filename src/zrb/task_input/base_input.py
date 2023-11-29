from zrb.helper.typing import Any, List, Mapping, Optional, Union
from zrb.helper.typecheck import typechecked
from zrb.task_input.any_input import AnyInput
from zrb.task_input.constant import RESERVED_INPUT_NAMES
from zrb.config.config import show_prompt


@typechecked
class BaseInput(AnyInput):

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
        should_render: bool = True
    ):
        if name in RESERVED_INPUT_NAMES:
            raise ValueError(f'Forbidden input name: {name}')
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
        param_decl: List[str] = [f'--{self._name}']
        if self._shortcut is not None:
            param_decl.append(f'-{self._shortcut}')
        return param_decl

    def get_options(self) -> Mapping[str, Any]:
        options: Mapping[str, Any] = {
            'default': self._default,
            'help': self._help,
            'type': self._type,
            'show_default': self._show_default,
            'confirmation_prompt': self._confirmation_prompt,
            'prompt_required': self._prompt_required,
            'hide_input': self._hide_input,
            'is_flag': self._is_flag,
            'flag_value': self._flag_value,
            'multiple': self._multiple,
            'count': self._count,
            'allow_from_autoenv': self._allow_from_autoenv,
            'hidden': self._hidden,
            'show_choices': self._show_choices,
            'show_envvar': self._show_envvar,
            'nargs': self._nargs
        }
        if show_prompt:
            options['prompt'] = self._prompt
        return options

    def should_render(self) -> bool:
        return self.__should_render

    def is_hidden(self) -> bool:
        return False
