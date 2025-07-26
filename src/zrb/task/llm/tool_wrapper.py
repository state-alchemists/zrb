import functools
import inspect
import traceback
import typing
from collections.abc import Callable
from typing import TYPE_CHECKING

from zrb.context.any_context import AnyContext
from zrb.task.llm.error import ToolExecutionError
from zrb.util.callable import get_callable_name
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
            if not not is_yolo_mode and not ctx.is_web_mode and ctx.is_tty:
                func_name = get_callable_name(func)
                ctx.print(f"✅ >> Allow to run tool: {func_name} (Y/n)", plain=True)
                user_confirmation_str = await _read_line()
                try:
                    user_confirmation = to_boolean(user_confirmation_str)
                except Exception:
                    user_confirmation = False
                if not user_confirmation:
                    ctx.print(f"❌ >> Rejecting {func_name} call. Why?", plain=True)
                    reason = await _read_line()
                    ctx.print("", plain=True)
                    raise ValueError(f"User disapproval: {reason}")
            return await run_async(func(*args, **kwargs))
        except Exception as e:
            error_model = ToolExecutionError(
                tool_name=func.__name__,
                error_type=type(e).__name__,
                message=str(e),
                details=traceback.format_exc(),
            )
            return error_model.model_dump_json()

    return wrapper


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
