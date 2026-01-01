import asyncio
from unittest.mock import MagicMock

from zrb.context.any_context import AnyContext
from zrb.task.llm.tool_wrapper import wrap_func


async def mock_read_line(*args, **kwargs):
    return "edit p1 v1"  # Simulate user editing parameter p1


async def test_fix():
    # Mock context
    ctx = MagicMock(spec=AnyContext)
    ctx.is_web_mode = False
    ctx.is_tty = True
    ctx.print = MagicMock()

    # Mock tool function that requires context
    def my_tool(ctx: AnyContext, p1: str):
        return f"p1={p1}"

    # Mock _read_line to simulate user input
    # We need to patch _read_line in zrb.task.llm.tool_wrapper
    import zrb.task.llm.tool_wrapper as tool_wrapper

    original_read_line = tool_wrapper._read_line
    tool_wrapper._read_line = mock_read_line

    try:
        wrapper = wrap_func(my_tool, ctx, yolo_mode=False)

        # Call the wrapper
        # The wrapper expects arguments. Since we are simulating "edit",
        # the original arguments don't matter much as long as they match signature.

        result = await wrapper(p1="original")

        print("Result:", result)

        if isinstance(result, dict) and "new_tool_parameters" in result:
            new_params = result["new_tool_parameters"]
            # Check if any value is the mock context
            # Note: The key name for context parameter in my_tool is 'ctx'
            if "ctx" in new_params:
                print("FAIL: 'ctx' key found in new_tool_parameters")
                exit(1)

            # Double check values
            for k, v in new_params.items():
                if v is ctx:
                    print(
                        f"FAIL: Context object found in new_tool_parameters under key {k}"
                    )
                    exit(1)

            print("PASS: Context object NOT found in new_tool_parameters")
        else:
            print(
                "FAIL: Expected dict with new_tool_parameters (due to edit simulation)"
            )
            exit(1)

    finally:
        tool_wrapper._read_line = original_read_line


if __name__ == "__main__":
    asyncio.run(test_fix())
