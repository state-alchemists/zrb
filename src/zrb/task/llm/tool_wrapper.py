import functools
import inspect
import traceback
import typing
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from zrb.context.any_context import AnyContext
from zrb.task.llm.error import ToolExecutionError
from zrb.util.callable import get_callable_name
from zrb.util.cli.markdown import render_markdown
from zrb.util.cli.style import (
    stylize_blue,
    stylize_error,
    stylize_green,
    stylize_yellow,
)
from zrb.util.run import run_async
from zrb.util.string.conversion import to_boolean

if TYPE_CHECKING:
    from pydantic_ai import Tool


def wrap_tool(func: Callable, ctx: AnyContext, is_yolo_mode: bool) -> "Tool":
    """Wraps a tool function to handle exceptions and context propagation."""
    from pydantic_ai import RunContext, Tool

    original_sig = inspect.signature(func)
    needs_run_context_for_pydantic = _has_context_parameter(original_sig, RunContext)
    wrapper = wrap_func(func, ctx, is_yolo_mode)
    return Tool(wrapper, takes_ctx=needs_run_context_for_pydantic)


def wrap_func(func: Callable, ctx: AnyContext, is_yolo_mode: bool) -> Callable:
    original_sig = inspect.signature(func)
    needs_any_context_for_injection = _has_context_parameter(original_sig, AnyContext)
    takes_no_args = len(original_sig.parameters) == 0
    # Pass individual flags to the wrapper creator
    wrapper = _create_wrapper(
        func, original_sig, ctx, needs_any_context_for_injection, is_yolo_mode
    )
    _adjust_signature(wrapper, original_sig, takes_no_args)
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
    original_sig: inspect.Signature,
    ctx: AnyContext,
    needs_any_context_for_injection: bool,
    is_yolo_mode: bool,
) -> Callable:
    """Creates the core wrapper function."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Identify AnyContext parameter name from the original signature if needed
        any_context_param_name = None
        if needs_any_context_for_injection:
            for param in original_sig.parameters.values():
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
        # If the dummy argument was added for schema generation and is present in kwargs,
        # remove it before calling the original function, unless the original function
        # actually expects a parameter named '_dummy'.
        if "_dummy" in kwargs and "_dummy" not in original_sig.parameters:
            del kwargs["_dummy"]
        try:
            if not is_yolo_mode and not ctx.is_web_mode and ctx.is_tty:
                approval, reason = await _ask_for_approval(ctx, func, args, kwargs)
                if not approval:
                    raise ValueError(f"User disapproving: {reason}")
            return await run_async(func(*args, **kwargs))
        except KeyboardInterrupt as e:
            raise e
        except Exception as e:
            error_model = ToolExecutionError(
                tool_name=func.__name__,
                error_type=type(e).__name__,
                message=str(e),
                details=traceback.format_exc(),
            )
            return error_model.model_dump_json()

    return wrapper


async def _ask_for_approval(
    ctx: AnyContext, func: Callable, args: list[Any], kwargs: dict[str, Any]
) -> tuple[bool, str]:
    func_call_str = _get_func_call_str(func, args, kwargs)
    complete_confirmation_message = "\n".join(
        [
            f"\n🎰 >> {func_call_str}",
            _get_detail_func_param(args, kwargs),
            f"✅ >> {_get_run_func_confirmation(func)}",
        ]
    )
    while True:
        ctx.print(complete_confirmation_message, plain=True)
        user_input = await _read_line()
        ctx.print("", plain=True)
        user_responses = [val.strip() for val in user_input.split(",", maxsplit=1)]
        while len(user_responses) < 2:
            user_responses.append("")
        approval_str, reason = user_responses
        try:
            approved = True if approval_str.strip() == "" else to_boolean(approval_str)
            if not approved and reason == "":
                ctx.print(
                    stylize_error(
                        f"You must specify rejection reason (i.e., No, <why>) for {func_call_str}"  # noqa
                    ),
                    plain=True,
                )
                continue
            return approved, reason
        except Exception:
            ctx.print(
                stylize_error(
                    f"Invalid approval value for {func_call_str}: {approval_str}"
                ),
                plain=True,
            )
            continue


def _get_run_func_confirmation(func: Callable) -> str:
    func_name = get_callable_name(func)
    return render_markdown(
        f"Allow to run `{func_name}`? (`Yes` | `No, <reason>`)"
    ).strip()


def _get_detail_func_param(args: list[Any], kwargs: dict[str, Any]) -> str:
    markdown = "\n".join(
        [_get_func_param_item(key, val) for key, val in kwargs.items()]
    )
    return render_markdown(markdown)


def _get_func_param_item(key: str, val: Any) -> str:
    upper_key = key.upper()
    val_str = f"{val}"
    val_parts = val_str.split("\n")
    if len(val_parts) == 1:
        return f"- {upper_key} `{val}`"
    lines = [f"- {upper_key}", "  ```"]
    for val_part in val_parts:
        lines.append(f"  {val_part}")
    lines.append("  ```")
    return "\n".join(lines)


def _get_func_call_str(func: Callable, args: list[Any], kwargs: dict[str, Any]) -> str:
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


def _adjust_signature(
    wrapper: Callable, original_sig: inspect.Signature, takes_no_args: bool
):
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

    # If after removing context parameters, there are no parameters left,
    # and the original function took no args, keep the dummy.
    # If after removing context parameters, there are no parameters left,
    # but the original function *did* take args (only context), then the schema
    # should have no parameters.
    if not params_for_schema and takes_no_args:
        # Keep the dummy if the original function truly had no parameters
        new_sig = inspect.Signature(
            parameters=[
                inspect.Parameter(
                    "_dummy", inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None
                )
            ]
        )
    else:
        new_sig = inspect.Signature(parameters=params_for_schema)

    wrapper.__signature__ = new_sig
