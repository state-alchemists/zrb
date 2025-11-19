import functools
import inspect
import json
import signal
import traceback
import typing
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import yaml

from zrb.config.config import CFG
from zrb.config.llm_rate_limitter import llm_rate_limitter
from zrb.context.any_context import AnyContext
from zrb.task.llm.error import ToolExecutionError
from zrb.util.callable import get_callable_name
from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.style import (
    stylize_blue,
    stylize_error,
    stylize_faint,
    stylize_green,
    stylize_yellow,
)
from zrb.util.cli.text import edit_text
from zrb.util.run import run_async
from zrb.util.string.conversion import to_boolean

if TYPE_CHECKING:
    from pydantic_ai import Tool


class ToolExecutionCancelled(ValueError):
    pass


def wrap_tool(func: Callable, ctx: AnyContext, yolo_mode: bool | list[str]) -> "Tool":
    """Wraps a tool function to handle exceptions and context propagation."""
    from pydantic_ai import RunContext, Tool

    original_sig = inspect.signature(func)
    needs_run_context_for_pydantic = _has_context_parameter(original_sig, RunContext)
    wrapper = wrap_func(func, ctx, yolo_mode)
    return Tool(wrapper, takes_ctx=needs_run_context_for_pydantic)


def wrap_func(func: Callable, ctx: AnyContext, yolo_mode: bool | list[str]) -> Callable:
    original_sig = inspect.signature(func)
    needs_any_context_for_injection = _has_context_parameter(original_sig, AnyContext)
    # Pass individual flags to the wrapper creator
    wrapper = _create_wrapper(
        func=func,
        original_signature=original_sig,
        ctx=ctx,
        needs_any_context_for_injection=needs_any_context_for_injection,
        yolo_mode=yolo_mode,
    )
    _adjust_signature(wrapper, original_sig)
    return wrapper


def _has_context_parameter(original_sig: inspect.Signature, context_type: type) -> bool:
    """
    Checks if the function signature includes a parameter with the specified
    context type annotation.
    """
    return any(
        _is_annotated_with_context(param.annotation, context_type)
        for param in original_sig.parameters.values()
    )


def _is_annotated_with_context(param_annotation, context_type):
    """
    Checks if the parameter annotation is the specified context type
    or a generic type containing it (e.g., Optional[ContextType]).
    """
    if param_annotation is inspect.Parameter.empty:
        return False
    if param_annotation is context_type:
        return True
    # Check for generic types like Optional[ContextType] or Union[ContextType, ...]
    origin = typing.get_origin(param_annotation)
    args = typing.get_args(param_annotation)
    if origin is not None and args:
        # Check if context_type is one of the arguments of the generic type
        return any(arg is context_type for arg in args)
    return False


def _create_wrapper(
    func: Callable,
    original_signature: inspect.Signature,
    ctx: AnyContext,
    needs_any_context_for_injection: bool,
    yolo_mode: bool | list[str],
) -> Callable:
    """Creates the core wrapper function."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Identify AnyContext parameter name from the original signature if needed
        any_context_param_name = None
        if needs_any_context_for_injection:
            for param in original_signature.parameters.values():
                if _is_annotated_with_context(param.annotation, AnyContext):
                    any_context_param_name = param.name
                    break  # Found it, no need to continue
            if any_context_param_name is None:
                # This should not happen if needs_any_context_for_injection is True,
                # but check for safety
                raise ValueError(
                    "AnyContext parameter name not found in function signature."
                )
            # Inject the captured ctx into kwargs. This will overwrite if the LLM
            # somehow provided it.
            kwargs[any_context_param_name] = ctx
        # We will need to overwrite SIGINT handler, so that when user press ctrl + c,
        # the program won't immediately exit
        original_sigint_handler = signal.getsignal(signal.SIGINT)
        tool_name = get_callable_name(func)
        try:
            has_ever_edited = False
            if not ctx.is_web_mode and ctx.is_tty:
                if (
                    isinstance(yolo_mode, list) and func.__name__ not in yolo_mode
                ) or not yolo_mode:
                    approval, reason, has_ever_edited = await _handle_user_response(
                        ctx, func, args, kwargs
                    )
                    if not approval:
                        raise ToolExecutionCancelled(
                            f"Tool execution cancelled. User disapproving: {reason}"
                        )
            signal.signal(signal.SIGINT, _tool_wrapper_sigint_handler)
            ctx.print(stylize_faint(f"Run {tool_name}"), plain=True)
            result = await run_async(func(*args, **kwargs))
            _check_tool_call_result_limit(result)
            if has_ever_edited:
                return {
                    "tool_call_result": result,
                    "new_tool_parameters": kwargs,
                    "message": "User correction: Tool was called with user's parameters",
                }
            return result
        except BaseException as e:
            error_model = ToolExecutionError(
                tool_name=tool_name,
                error_type=type(e).__name__,
                message=str(e),
                details=traceback.format_exc(),
            )
            return error_model.model_dump_json()
        finally:
            signal.signal(signal.SIGINT, original_sigint_handler)

    return wrapper


def _tool_wrapper_sigint_handler(signum, frame):
    raise KeyboardInterrupt("SIGINT detected while running tool")


def _check_tool_call_result_limit(result: Any):
    if (
        llm_rate_limitter.count_token(result)
        > llm_rate_limitter.max_tokens_per_tool_call_result
    ):
        raise ValueError("Result value is too large, please adjust the parameter")


async def _handle_user_response(
    ctx: AnyContext,
    func: Callable,
    args: list[Any] | tuple[Any],
    kwargs: dict[str, Any],
) -> tuple[bool, str, bool]:
    has_ever_edited = False
    while True:
        func_call_str = _get_func_call_str(func, args, kwargs)
        complete_confirmation_message = "\n".join(
            [
                f"\n🎰 >> {func_call_str}",
                _get_detail_func_param(args, kwargs),
                f"🎰  >> {_get_run_func_confirmation(func)}",
            ]
        )
        ctx.print(complete_confirmation_message, plain=True)
        user_response = await _read_line()
        ctx.print("", plain=True)
        new_kwargs, is_edited = _get_edited_kwargs(ctx, user_response, kwargs)
        if is_edited:
            kwargs = new_kwargs
            has_ever_edited = True
            continue
        approval_and_reason = _get_user_approval_and_reason(
            ctx, user_response, func_call_str
        )
        if approval_and_reason is None:
            continue
        approval, reason = approval_and_reason
        return approval, reason, has_ever_edited


def _get_edited_kwargs(
    cx: AnyContext, user_response: str, kwargs: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    user_edit_responses = [val for val in user_response.split(" ", maxsplit=2)]
    if len(user_edit_responses) >= 1 and user_edit_responses[0].lower() != "edit":
        return kwargs, False
    while len(user_edit_responses) < 3:
        user_edit_responses.append("")
    key, val_str = user_edit_responses[1:]

    # Handle nested parameter editing with dot notation and array indexing
    if "." in key or "[" in key:
        try:
            _set_nested_value(kwargs, key, val_str)
            return kwargs, True
        except (KeyError, IndexError, ValueError) as e:
            cx.print(stylize_error(f"Invalid parameter key: {key}. {e}"))
            return kwargs, True

    if key not in kwargs:
        cx.print(stylize_error(f"Invalid parameter key: {key}"))
        return kwargs, True

    is_str_param = isinstance(kwargs[key], str)
    if val_str.strip() == "":
        val_str = edit_text(
            prompt_message=f"// {key}",
            value=_get_val_str(kwargs[key]),
            editor=CFG.DEFAULT_EDITOR,
        )

    # Use YAML parsing instead of JSON for better readability
    kwargs[key] = val_str if is_str_param else _parse_yaml_or_json(val_str)
    return kwargs, True


def _set_nested_value(data: dict[str, Any], path: str, value_str: str) -> None:
    """
    Set a nested value in a dictionary using dot notation and array indexing.
    Examples:
    - file.name -> data['file']['name']
    - files[0].name -> data['files'][0]['name']
    - config.database.host -> data['config']['database']['host']
    """
    parts = []
    current_part = ""

    # Parse the path into parts (handling array indices)
    i = 0
    while i < len(path):
        char = path[i]
        if char == ".":
            if current_part:
                parts.append(current_part)
                current_part = ""
        elif char == "[":
            if current_part:
                parts.append(current_part)
                current_part = ""
            # Find the closing bracket
            j = path.find("]", i)
            if j == -1:
                raise ValueError(f"Unclosed bracket in path: {path}")
            index_str = path[i + 1 : j]
            try:
                index = int(index_str)
                parts.append(index)
            except ValueError:
                raise ValueError(f"Invalid array index: {index_str}")
            i = j  # Skip to closing bracket
        else:
            current_part += char
        i += 1

    if current_part:
        parts.append(current_part)

    # Navigate to the parent object
    current = data
    for part in parts[:-1]:
        if isinstance(part, int):
            # Array index
            if not isinstance(current, (list, tuple)) or part >= len(current):
                raise IndexError(f"Array index {part} out of bounds")
            current = current[part]
        else:
            # Dictionary key
            if not isinstance(current, dict) or part not in current:
                raise KeyError(f"Key '{part}' not found")
            current = current[part]

    last_part = parts[-1]

    # Get current value
    if isinstance(last_part, int):
        if not isinstance(current, (list, tuple)) or last_part >= len(current):
            raise IndexError(f"Array index {last_part} out of bounds")
        current_value = current[last_part]
    else:
        if not isinstance(current, dict) or last_part not in current:
            raise KeyError(f"Key '{last_part}' not found")
        current_value = current[last_part]

    is_str_param = isinstance(current_value, str)
    if value_str.strip() == "":
        value_str = edit_text(
            prompt_message=f"// Editing {path}",
            value=_get_val_str(current_value),
            editor=CFG.DEFAULT_EDITOR,
        )

    new_value = value_str if is_str_param else _parse_yaml_or_json(value_str)

    # Set the value on the parent object
    if isinstance(last_part, int):
        current[last_part] = new_value
    else:
        current[last_part] = new_value


def _parse_yaml_or_json(value_str: str) -> Any:
    """
    Parse a string value as YAML first, falling back to JSON if YAML parsing fails.
    This provides better readability for complex structures.
    """
    if not value_str.strip():
        return None

    # Try YAML parsing first (more human-readable)
    try:
        return yaml.safe_load(value_str)
    except yaml.YAMLError:
        # Fall back to JSON parsing
        try:
            return json.loads(value_str)
        except json.JSONDecodeError:
            # If both fail, return as string
            return value_str


def _get_user_approval_and_reason(
    ctx: AnyContext, user_response: str, func_call_str: str
) -> tuple[bool, str] | None:
    user_approval_responses = [
        val.strip() for val in user_response.split(",", maxsplit=1)
    ]
    while len(user_approval_responses) < 2:
        user_approval_responses.append("")
    approval_str, reason = user_approval_responses
    try:
        approved = True if approval_str.strip() == "" else to_boolean(approval_str)
        if not approved and reason == "":
            ctx.print(
                stylize_error(
                    f"You must specify rejection reason (i.e., No, <why>) for {func_call_str}"  # noqa
                ),
                plain=True,
            )
            return None
        return approved, reason
    except Exception:
        return False, user_response


def _get_run_func_confirmation(func: Callable) -> str:
    func_name = get_callable_name(func)
    return render_markdown(
        f"Allow to run `{func_name}`? (✅ `Yes` | ⛔ `No, <reason>` | 📝 `Edit <param> <value>`)"
    ).strip()


def _get_detail_func_param(args: list[Any] | tuple[Any], kwargs: dict[str, Any]) -> str:
    if not kwargs:
        return ""
    # Convert the entire kwargs dictionary to a YAML string
    try:
        # Use the existing dumper that handles multiline strings nicely
        yaml_str = _dump_yaml_with_block_styles(kwargs)
    except Exception:
        # Fallback if the custom dumper fails
        yaml_str = yaml.dump(kwargs, allow_unicode=True, indent=2)
    # Create the final markdown string
    markdown = f"```yaml\n{yaml_str}\n```"
    return render_markdown(markdown)


def _get_val_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, str):
        # For multiline strings, use YAML block style for better readability
        # Only use block style for meaningful multiline content
        if "\n" in val and len(val.strip()) > 0:
            lines = val.split("\n")
            non_empty_lines = [line for line in lines if line.strip()]
            if len(non_empty_lines) >= 2:
                try:
                    return yaml.dump(
                        val, default_style="|", indent=2, allow_unicode=True
                    ).strip()
                except Exception:
                    return val
        return val
    try:
        # Use custom YAML dumper that handles multiline strings in complex objects
        return _dump_yaml_with_block_styles(val)
    except Exception:
        try:
            return json.dumps(val, indent=4)
        except Exception:
            return f"{val}"


def _dump_yaml_with_block_styles(data: Any) -> str:
    """
    Dump YAML with proper block styles for multiline strings.
    This handles multiline strings within complex objects.
    """
    import yaml

    class BlockStyleDumper(yaml.SafeDumper):
        def represent_str(self, data):
            # Use block style only for strings that have meaningful multiline content
            # Avoid block style for edge cases like strings with only newlines
            if "\n" in data and len(data.strip()) > 0:
                lines = data.split("\n")
                # Only use block style if there are at least 2 non-empty lines
                non_empty_lines = [line for line in lines if line.strip()]
                if len(non_empty_lines) >= 2:
                    return self.represent_scalar(
                        "tag:yaml.org,2002:str", data, style="|"
                    )
            return self.represent_scalar("tag:yaml.org,2002:str", data)

    BlockStyleDumper.add_representer(str, BlockStyleDumper.represent_str)

    return yaml.dump(
        data,
        Dumper=BlockStyleDumper,
        default_flow_style=False,
        indent=2,
        allow_unicode=True,
    ).strip()


def _get_func_call_str(
    func: Callable, args: list[Any] | tuple[Any], kwargs: dict[str, Any]
) -> str:
    func_name = get_callable_name(func)
    normalized_args = [stylize_green(_truncate_arg(arg)) for arg in args]
    normalized_kwargs = []
    for key, val in kwargs.items():
        truncated_val = _truncate_arg(f"{val}")
        normalized_kwargs.append(
            f"{stylize_yellow(key)}={stylize_green(truncated_val)}"
        )
    func_param_str = ", ".join(normalized_args + normalized_kwargs)
    return f"{stylize_blue(func_name + '(')}{func_param_str}{stylize_blue(')')}"


def _truncate_arg(arg: str, length: int = 19) -> str:
    normalized_arg = arg.replace("\n", "\\n")
    if len(normalized_arg) > length:
        return f"{normalized_arg[:length-4]} ..."
    return normalized_arg


async def _read_line():
    from prompt_toolkit import PromptSession

    reader = PromptSession()
    return await reader.prompt_async()


def _adjust_signature(wrapper: Callable, original_sig: inspect.Signature):
    """Adjusts the wrapper function's signature for schema generation."""
    # The wrapper's signature should represent the arguments the *LLM* needs to provide.
    # The LLM does not provide RunContext (pydantic-ai injects it) or AnyContext
    # (we inject it). So, the wrapper's signature should be the original signature,
    # minus any parameters annotated with RunContext or AnyContext.

    from pydantic_ai import RunContext

    params_for_schema = [
        param
        for param in original_sig.parameters.values()
        if not _is_annotated_with_context(param.annotation, RunContext)
        and not _is_annotated_with_context(param.annotation, AnyContext)
    ]
    wrapper.__signature__ = inspect.Signature(parameters=params_for_schema)
