from zrb.helper.typing import Any, Optional, Union
from zrb.helper.typecheck import typechecked

from zrb.task_input.base_input import BaseInput


@typechecked
class PasswordInput(BaseInput):

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
        is_flag: Optional[bool] = None,
        flag_value: Optional[Any] = None,
        multiple: bool = False,
        count: bool = False,
        allow_from_autoenv: bool = True,
        hidden: bool = False,
        show_choices: bool = True,
        show_envvar: bool = False,
        nargs: int = 1,
        should_render: bool = True
    ):
        BaseInput.__init__(
            self,
            name=name,
            shortcut=shortcut,
            default=default,
            description=description,
            show_default=show_default,
            prompt=prompt,
            confirmation_prompt=confirmation_prompt,
            prompt_required=prompt_required,
            hide_input=True,
            is_flag=is_flag,
            flag_value=flag_value,
            multiple=multiple,
            count=count,
            allow_from_autoenv=allow_from_autoenv,
            type=str,
            hidden=hidden,
            show_choices=show_choices,
            show_envvar=show_envvar,
            nargs=nargs,
            should_render=should_render
        )

    def is_hidden(self) -> bool:
        return True
