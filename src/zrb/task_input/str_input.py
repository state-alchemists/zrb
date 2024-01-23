from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, Optional, Union
from zrb.task_input.base_input import BaseInput

# flake8: noqa E501


@typechecked
class StrInput(BaseInput):
    """
    A specialized input class for handling string-based inputs in various tasks.

    `StrInput` extends `BaseInput` to manage string-type inputs, supporting features like
    default values, prompts, flags, and other customization options. This class is useful
    for tasks requiring textual input, such as names, descriptions, or any other string parameters.

    Args:
        name (str): The name of the input, used as an identifier.
        shortcut (Optional[str]): An optional shortcut string for the input.
        default (Optional[Any]): The default value for the input, expected to be a string if set.
        description (Optional[str]): A brief description of the input's purpose.
        show_default (Union[bool, str, None]): Option to display the default value. Can be a boolean or string.
        prompt (Union[bool, str]): A boolean or string to prompt the user for input. If `True`, uses the default prompt.
        confirmation_prompt (Union[bool, str]): If `True`, the user is asked to confirm the input.
        prompt_required (bool): If `True’, the prompt for input is mandatory.
        hide_input (bool): If `True’, hides the input value, typically used for sensitive data.
        is_flag (Optional[bool]): Indicates if the input is a flag. If `True’, the input accepts boolean flag values.
        flag_value (Optional[Any]): The value associated with the flag if `is_flag` is `True`.
        multiple (bool): If `True’, allows multiple string values for the input.
        count (bool): If `True’, counts the occurrences of the input.
        allow_from_autoenv (bool): If `True’, enables automatic population of the input from environment variables.
        hidden (bool): If `True’, keeps the input hidden in help messages or documentation.
        show_choices (bool): If `True’, shows any restricted choices for the input value.
        show_envvar (bool): If `True’, displays the associated environment variable, if applicable.
        nargs (int): The number of arguments that the input can accept.
        should_render (bool): If `True’, renders the input in the user interface or command-line interface.

    Examples:
        >>> str_input = StrInput(name='username', default='user123', description='Enter your username')
        >>> str_input.get_default()
        'user123'
    """

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
            description=description,
            show_default=show_default,
            prompt=prompt,
            confirmation_prompt=confirmation_prompt,
            prompt_required=prompt_required,
            hide_input=hide_input,
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
