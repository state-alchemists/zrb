from typing import Any, List, Mapping, Optional, Union
from typeguard import typechecked
from ._constant import RESERVED_INPUT_NAMES


@typechecked
class BaseInput():

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
    ):
        if name in RESERVED_INPUT_NAMES:
            raise ValueError(f'Forbidden input name: {name}')
        self.name = name
        self.shortcut = shortcut
        self.prompt = prompt
        self.default = default
        self.help = description if description is not None else name
        self.type = type
        self.show_default = show_default
        self.confirmation_prompt = confirmation_prompt
        self.prompt_required = prompt_required
        self.hide_input = hide_input
        self.is_flag = is_flag
        self.flag_value = flag_value
        self.multiple = multiple
        self.count = count
        self.allow_from_autoenv = allow_from_autoenv
        self.hidden = hidden
        self.show_choices = show_choices
        self.show_envvar = show_envvar
        self.nargs = nargs

    def get_name(self) -> str:
        return self.name

    def get_param_decl(self) -> List[str]:
        param_decl: List[str] = [f'--{self.name}']
        if self.shortcut is not None:
            param_decl.append(f'-{self.shortcut}')
        return param_decl

    def get_options(self) -> Mapping[str, Any]:
        return {
            'prompt': self.prompt,
            'default': self.default,
            'help': self.help,
            'type': self.type,
            'show_default': self.show_default,
            'confirmation_prompt': self.confirmation_prompt,
            'prompt_required': self.prompt_required,
            'hide_input': self.hide_input,
            'is_flag': self.is_flag,
            'flag_value': self.flag_value,
            'multiple': self.multiple,
            'count': self.count,
            'allow_from_autoenv': self.allow_from_autoenv,
            'hidden': self.hidden,
            'show_choices': self.show_choices,
            'show_envvar': self.show_envvar,
            'nargs': self.nargs
        }
