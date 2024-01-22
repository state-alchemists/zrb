from zrb.task_input.base_input import BaseInput

# flake8: noqa E501


class Input(BaseInput):
    """
    Alias for BaseInput

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

    pass
