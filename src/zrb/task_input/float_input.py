from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, Optional, Union
from zrb.task_input.base_input import BaseInput

# flake8: noqa E501


@typechecked
class FloatInput(BaseInput):
    """
     A specialized input class designed to handle floating-point numbers in a task input context.

    Extending `BaseInput`, this class facilitates the handling of float-type inputs, accommodating
    various features like default values, prompts, flags, and customization options.

    Args:
        name (str): The name of the input.
        shortcut (Optional[str]): An optional shortcut string for the input.
        default (Optional[Any]): The default value for the input, expected to be a float if set.
        description (Optional[str]): A brief description of the input's purpose.
        show_default (Union[bool, str, None]): Option to display the default value. Can be a boolean or string.
        prompt (Union[bool, str]): A boolean or string to prompt the user for input. If `True`, uses the default prompt.
        confirmation_prompt (Union[bool, str]): If `True`, the user is asked to confirm the input.
        prompt_required (bool): If `True`, the prompt for input is mandatory.
        hide_input (bool): If `True`, the input is hidden, useful for sensitive information.
        is_flag (Optional[bool]): Indicates if the input is a flag. If `True`, the input accepts boolean flag values.
        flag_value (Optional[Any]): The value associated with the flag if `is_flag` is `True`.
        multiple (bool): If `True`, allows multiple float values for the input.
        count (bool): If `True`, counts the occurrences of the input.
        allow_from_autoenv (bool): If `True`, allows the input to be automatically populated from the environment.
        hidden (bool): If `True`, the input is not shown in help messages or documentation.
        show_choices (bool): If `True`, displays the available choices to the user (relevant if there are restricted float choices).
        show_envvar (bool): Indicates whether to display the environment variable associated with this input.
        nargs (int): The number of arguments that the input can accept.
        should_render (bool): If `True`, the input is rendered in the UI or command-line interface.

    Examples:
        >>> float_input = FloatInput(name='threshold', default=0.5, description='Set the threshold value')
        >>> float_input.get_default()
        0.5
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
            type=float,
            hidden=hidden,
            show_choices=show_choices,
            show_envvar=show_envvar,
            nargs=nargs,
            should_render=should_render,
        )
