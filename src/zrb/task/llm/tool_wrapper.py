import functools
import inspect
import signal
import traceback
import typing
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.config.llm_rate_limitter import llm_rate_limitter
from zrb.context.any_context import AnyContext
from zrb.task.llm.error import ToolExecutionError
from zrb.task.llm.file_replacement import edit_replacement, is_single_path_replacement
from zrb.task.llm.tool_confirmation_completer import get_tool_confirmation_completer
from zrb.util.callable import get_callable_name
from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.style import (
    stylize_blue,
    stylize_faint,
    stylize_green,
    stylize_yellow,
)
from zrb.util.cli.text import edit_text
from zrb.util.run import run_async
from zrb.util.string.conversion import to_boolean
from zrb.util.yaml import edit_obj, yaml_dump

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
                    approval, reason, kwargs, has_ever_edited = (
                        await _handle_user_response(ctx, func, args, kwargs)
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
) -> tuple[bool, str, dict[str, Any], bool]:
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
        user_response = await _read_line(args, kwargs)
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
        return approval, reason, kwargs, has_ever_edited


def _get_edited_kwargs(
    ctx: AnyContext, user_response: str, kwargs: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    user_edit_responses = [val for val in user_response.split(" ", maxsplit=2)]
    if len(user_edit_responses) >= 1 and user_edit_responses[0].lower() != "edit":
        return kwargs, False
    while len(user_edit_responses) < 3:
        user_edit_responses.append("")
    key, val_str = user_edit_responses[1:]
    # Make sure first segment of the key is in kwargs
    if key != "":
        key_parts = key.split(".")
        if len(key_parts) > 0 and key_parts[0] not in kwargs:
            return kwargs, True
    # Handle replacement edit
    if len(kwargs) == 1:
        kwarg_key = list(kwargs.keys())[0]
        if is_single_path_replacement(kwargs[kwarg_key]) and (
            key == "" or key == kwarg_key
        ):
            kwargs[kwarg_key], edited = edit_replacement(kwargs[kwarg_key])
            return kwargs, True
    # Handle other kind of edit
    old_val_str = yaml_dump(kwargs, key)
    if val_str == "":
        val_str = edit_text(
            prompt_message=f"# {key}" if key != "" else "",
            value=old_val_str,
            editor=CFG.DEFAULT_EDITOR,
            extension=".yaml",
        )
    if old_val_str == val_str:
        return kwargs, True
    edited_kwargs = edit_obj(kwargs, key, val_str)
    return edited_kwargs, True


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
            reason = "User disapproving the tool execution"
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
    yaml_str = yaml_dump(kwargs)
    # Create the final markdown string
    markdown = f"```yaml\n{yaml_str}\n```"
    return render_markdown(markdown)


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


async def _read_line(args: list[Any] | tuple[Any], kwargs: dict[str, Any]):
    from prompt_toolkit import PromptSession

    options = ["yes", "no", "edit"]
    meta_dict = {
        "yes": "Approve the execution",
        "no": "Disapprove the execution",
        "edit": "Edit tool execution parameters",
    }
    for key in kwargs:
        options.append(f"edit {key}")
        meta_dict[f"edit {key}"] = f"Edit tool execution parameter: {key}"
    completer = get_tool_confirmation_completer(options, meta_dict)
    reader = PromptSession()
    return await reader.prompt_async(completer=completer)


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
