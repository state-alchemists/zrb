import click

from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Any, Iterable, Optional, Union
from zrb.task_input.base_input import BaseInput

# flake8: noqa E501


@typechecked
class ChoiceInput(BaseInput):
    """
    A specialized input class for handling choice-based inputs in a task input context.

    This class extends `BaseInput` and provides functionality for inputs where the user
    must select from a predefined set of choices. It includes support for default values,
    prompts, flags, and various customization options.

    Args:
        name (str): The name of the input.
        shortcut (Optional[str]): An optional shortcut string for the input.
        choices (Iterable[Any]): An iterable of choices from which the user can select.
        default (Optional[Any]): The default value for the input. Should be one of the choices if set.
        description (Optional[str]): A brief description of the input.
        show_default (Union[bool, str, None]): Option to display the default value. Can be a boolean or string representation.
        prompt (Union[bool, str]): A boolean or string to prompt the user for input. If `True`, uses the default prompt.
        confirmation_prompt (Union[bool, str]): If set to `True`, the user is asked to confirm the input.
        prompt_required (bool): If `True`, the prompt for input is mandatory.
        hide_input (bool): If `True`, the input is hidden (useful for sensitive information).
        is_flag (Optional[bool]): Indicates if the input is a flag. If `True`, the input accepts boolean flag values.
        flag_value (Optional[Any]): The value associated with the flag if `is_flag` is `True`.
        multiple (bool): If `True`, allows multiple values for the input.
        count (bool): If `True`, counts the occurrences of the input.
        allow_from_autoenv (bool): If `True`, allows the input to be automatically populated from the environment.
        hidden (bool): If `True`, the input is not shown in help messages or documentation.
        show_choices (bool): If `True`, displays the available choices to the user.
        show_envvar (bool): Indicates whether to display the environment variable associated with this input.
        nargs (int): The number of arguments that the input can accept.
        should_render (bool): If `True`, the input is rendered in the UI or command-line interface.

    Examples:
        >>> choice_input = ChoiceInput(name='color', choices=['red', 'green', 'blue'], default='red')
        >>> choice_input.get_default()
        'red'
    """

    def __init__(
        self,
        name: str,
        shortcut: Optional[str] = None,
        choices: Iterable[Any] = [],
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
            type=click.Choice(choices),
            hidden=hidden,
            show_choices=show_choices,
            show_envvar=show_envvar,
            nargs=nargs,
            should_render=should_render,
        )
