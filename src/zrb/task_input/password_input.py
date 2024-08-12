from typing import Any, Optional, Union

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.task_input.base_input import BaseInput, InputCallback, InputDefault

logger.debug(colored("Loading zrb.task_input.password_input", attrs=["dark"]))

# flake8: noqa E501


@typechecked
class PasswordInput(BaseInput):
    """
    A specialized input class for handling password or sensitive data inputs in tasks.

    `PasswordInput` extends `BaseInput` to manage inputs that should be treated as sensitive,
    such as passwords. It ensures that the input is hidden when entered, providing an added
    layer of security and privacy. This class supports various features like default values,
    prompts, and flags, tailored for the safe handling of sensitive information.

    Args:
        name (str): The name of the input, serving as an identifier.
        shortcut (Optional[str]): An optional shortcut string for the input.
        default (Optional[Any]): The default value for the input, expected to be a string if set.
        callback (Optional[Any]): The default value of the input.
        description (Optional[str]): A brief description of what the input is for.
        show_default (Union[bool, JinjaTemplate, None]): Determines the default value to be shown.
        prompt (Union[bool, str]): A boolean or string to prompt the user for input. If `True`, uses the default prompt.
        confirmation_prompt (Union[bool, str]): If `True`, the user is asked to confirm the input.
        prompt_required (bool): If `True`, the prompt for input is mandatory.
        is_flag (Optional[bool]): Indicates if the input is a flag. If `True`, the input accepts boolean flag values.
        flag_value (Optional[Any]): The value associated with the flag if `is_flag` is `True`.
        multiple (bool): If `True`, allows multiple values for the input.
        count (bool): If `True`, counts the occurrences of the input.
        allow_from_autoenv (bool): If `True`, allows the input to be automatically populated from the environment.
        hidden (bool): If `True`, the input is not shown in help messages or documentation.
        show_choices (bool): If `True`, displays the available choices to the user (if applicable).
        show_envvar (bool): Indicates whether to display the environment variable associated with this input.
        nargs (int): The number of arguments that the input can accept.
        should_render (bool): If `True`, the input is rendered in the UI or command-line interface.

    Examples:
        >>> password_input = PasswordInput(name='password', description='Enter your password')
        >>> password_input.is_hidden()
        True
    """

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
        is_flag: Optional[bool] = None,
        flag_value: Optional[Any] = None,
        multiple: bool = False,
        count: bool = False,
        allow_from_autoenv: bool = True,
        hidden: bool = False,
        show_choices: bool = True,
        show_envvar: bool = False,
        nargs: int = 1,
        should_render: bool = True,
    ):
        BaseInput.__init__(
            self,
            name=name,
            shortcut=shortcut,
            default=default,
            callback=callback,
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
            should_render=should_render,
        )

    def is_hidden(self) -> bool:
        return True
