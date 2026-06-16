import pytest

from zrb.llm.hook.hook_creators import create_command_hook
from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.schema import CommandHookConfig
from zrb.llm.hook.types import HookEvent


@pytest.mark.asyncio
async def test_command_hook_timeout_returns_clean_result():
    """A command hook that exceeds its timeout must be killed and reaped
    cleanly, returning a timeout HookResult.

    Regression: the kill path used ``await process.wait()`` on a sync
    ``subprocess.Popen``, whose ``.wait()`` returns an int — ``await``-ing it
    raised ``TypeError: 'int' object can't be awaited``, which swallowed the
    TimeoutError and left the subprocess unreaped.
    """
    hook = create_command_hook(CommandHookConfig(command="sleep 5"), timeout=0.1)
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    result = await hook(context)

    assert result.success is False
    assert "timed out" in (result.output or "")
    # The bug surfaced as this message via the outer exception handler.
    assert "can't be awaited" not in (result.output or "")
