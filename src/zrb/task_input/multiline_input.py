from collections.abc import Mapping
from typing import Any, Optional, Union

from zrb.config.config import DEFAULT_EDITOR
from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.multiline import edit
from zrb.helper.typecheck import typechecked
from zrb.task_input.base_input import BaseInput, InputCallback, InputDefault

logger.debug(colored("Loading zrb.task_input.multiline_input", attrs=["dark"]))

# flake8: noqa E501


@typechecked
class MultilineInput(BaseInput):
    """
    A specialized input class for handling string-based inputs in various tasks.

    `MultilineInput` extends `BaseInput` to manage string-type inputs, supporting features like
    default values, prompts, flags, and other customization options. This class is useful
    for tasks requiring textual input, such as names, descriptions, or any other string parameters.

    Args:
        name (str): The name of the input, used as an identifier.
        shortcut (Optional[str]): An optional shortcut string for the input.
        default (Optional[Any]): The default value for the input, expected to be a string if set.
        callback (Optional[Any]): The default value of the input.
        description (Optional[str]): A brief description of what the input is for.
        show_default (Union[bool, JinjaTemplate, None]): Determines the default value to be shown.
        prompt (Union[bool, str]): A boolean or string to prompt the user for input. If `True`, uses the default prompt.
        confirmation_prompt (Union[bool, str]): If `True`, the user is asked to confirm the input.
        prompt_required (bool): If `True`, the prompt for input is mandatory.
        hide_input (bool): If `True`, hides the input value, typically used for sensitive data.
        is_flag (Optional[bool]): Indicates if the input is a flag. If `True`, the input accepts boolean flag values.
        flag_value (Optional[Any]): The value associated with the flag if `is_flag` is `True`.
        multiple (bool): If `True`, allows multiple string values for the input.
        count (bool): If `True`, counts the occurrences of the input.
        allow_from_autoenv (bool): If `True`, enables automatic population of the input from environment variables.
        hidden (bool): If `True`, keeps the input hidden in help messages or documentation.
        show_choices (bool): If `True`, shows any restricted choices for the input value.
        show_envvar (bool): If `True`, displays the associated environment variable, if applicable.
        nargs (int): The number of arguments that the input can accept.
        should_render (bool): If `True`, renders the input in the user interface or command-line interface.

    Examples:
        >>> multiline_input = MultilineInput(name='sql', default='select * from tbl', extension='sql', description='SQL')
        >>> multiline_input.get_default()
        'user123'
    """

    __default_cache: Mapping[str, Any] = {}

    def __init__(
        self,
        name: str,
        shortcut: Optional[str] = None,
        comment_prefix: str = "//",
        comment_suffix: str = "",
        editor: str = DEFAULT_EDITOR,
        extension: str = "txt",
        default: Optional[Union[Any, InputDefault]] = None,
        callback: Optional[InputCallback] = None,
        description: Optional[str] = None,
        show_default: Union[bool, str] = True,
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
            callback=callback,
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
        self._comment_prefix = comment_prefix
        self._comment_suffix = comment_suffix
        self._editor = editor
        self._extension = extension

    def _wrapped_default(self) -> Any:
        if self.get_name() not in self.__default_cache:
            text = super()._wrapped_default()
            mark_comment = self._get_mark_comment()
            self.__default_cache[self.get_name()] = edit(
                editor=self._editor,
                mark_comment=mark_comment,
                text=text,
                extension=self._extension,
            )
        return self.__default_cache[self.get_name()]

    def _get_mark_comment(self):
        prompt = self._prompt if isinstance(self._prompt, str) else self.get_name()
        if self._comment_suffix.strip() == "":
            return " ".join([self._comment_prefix, prompt])
        return " ".join([self._comment_prefix, prompt, self._comment_suffix])
