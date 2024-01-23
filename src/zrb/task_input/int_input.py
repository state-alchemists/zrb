from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, Optional, Union
from zrb.task_input.base_input import BaseInput

# flake8: noqa E501


@typechecked
class IntInput(BaseInput):
    """
    A specialized input class for handling integer values in task inputs.

    `IntInput` extends `BaseInput` to specifically handle inputs where integer values are required.
    It supports various features like default values, prompts, flags, and other customization options,
    making it suitable for tasks that require numerical input in the form of integers.

    Args:
        name (str): The name of the input, serving as an identifier.
        shortcut (Optional[str]): An optional shortcut for easier reference to the input.
        default (Optional[Any]): The default value for the input, should be an integer if provided.
        description (Optional[str]): A brief description of what the input represents or its intended use.
        show_default (Union[bool, str, None]): Option to show the default value in prompts or documentation.
        prompt (Union[bool, str]): A boolean or string to determine the prompt for user input. If `True`, uses a default prompt.
        confirmation_prompt (Union[bool, str]): If `True`, the user will be asked to confirm their input.
        prompt_required (bool): If `True`, makes the input prompt mandatory.
        hide_input (bool): If `True`, hides the input value, typically used for sensitive information.
        is_flag (Optional[bool]): Indicates if the input functions as a flag, taking boolean values.
        flag_value (Optional[Any]): The value associated with the input when used as a flag.
        multiple (bool): If `True`, allows entering multiple integer values.
        count (bool): If `True`, counts the occurrences of the input.
        allow_from_autoenv (bool): If `True`, enables automatic population of the input from environment variables.
        hidden (bool): If `True`, keeps the input hidden in help messages or documentation.
        show_choices (bool): If `True`, shows any restricted choices for the input value.
        show_envvar (bool): If `True`, displays the associated environment variable, if applicable.
        nargs (int): The number of arguments that the input can accept.
        should_render (bool): If `True`, renders the input in the user interface or command-line interface.

    Examples:
        >>> int_input = IntInput(name='age', default=30, description='Enter your age')
        >>> int_input.get_default()
        30
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
            type=int,
            hidden=hidden,
            show_choices=show_choices,
            show_envvar=show_envvar,
            nargs=nargs,
            should_render=should_render,
        )
