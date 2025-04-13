import functools
import inspect
import traceback
from collections.abc import Callable

from zrb.task.llm.error import ToolExecutionError
from zrb.util.run import run_async


def wrap_tool(func: Callable) -> Callable:
    """Wraps a tool function to handle exceptions and context propagation.

    - Catches exceptions during tool execution and returns a structured
      JSON error message (`ToolExecutionError`).
    - Inspects the original function signature for a 'ctx' parameter.
      If found, the wrapper will accept 'ctx' and pass it to the function.
    - If the original function has no parameters, injects a dummy '_dummy'
      parameter into the wrapper's signature to ensure schema generation
      for pydantic-ai.

    Args:
        func: The tool function (sync or async) to wrap.

    Returns:
        An async wrapper function.
    """
    original_sig = inspect.signature(func)
    needs_ctx = "ctx" in original_sig.parameters
    takes_no_args = len(original_sig.parameters) == 0

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        ctx_arg = None
        if needs_ctx:
            if args:
                ctx_arg = args[0]
                args = args[1:]  # Remove ctx from args for the actual call if needed
            elif "ctx" in kwargs:
                ctx_arg = kwargs.pop("ctx")

        try:
            # Remove dummy argument if it was added for no-arg functions
            if takes_no_args and "_dummy" in kwargs:
                del kwargs["_dummy"]

            if needs_ctx:
                # Ensure ctx is passed correctly, even if original func had only ctx
                if ctx_arg is None:
                    # This case should ideally not happen if takes_ctx is True in Tool
                    raise ValueError("Context (ctx) was expected but not provided.")
                # Call with context
                return await run_async(func(ctx_arg, *args, **kwargs))
            else:
                # Call without context
                return await run_async(func(*args, **kwargs))
        except Exception as e:
            error_model = ToolExecutionError(
                tool_name=func.__name__,
                error_type=type(e).__name__,
                message=str(e),
                details=traceback.format_exc(),
            )
            return error_model.model_dump_json()

    if takes_no_args:
        # Inject dummy parameter for schema generation if original func took no args
        new_sig = inspect.Signature(
            parameters=[
                inspect.Parameter(
                    "_dummy", inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None
                )
            ]
        )
        wrapper.__signature__ = new_sig
    elif needs_ctx:
        # Adjust signature if ctx was the *only* parameter originally
        # This ensures the wrapper signature matches what pydantic-ai expects
        params = list(original_sig.parameters.values())
        if len(params) == 1 and params[0].name == "ctx":
            new_sig = inspect.Signature(
                parameters=[
                    inspect.Parameter("ctx", inspect.Parameter.POSITIONAL_OR_KEYWORD)
                ]
            )
            wrapper.__signature__ = new_sig
        # Otherwise, the original signature (including ctx) is fine for the wrapper

    return wrapper
