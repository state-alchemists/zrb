"""The concrete `BaseUI` the `ui/base` tests drive.

`BaseUI` leaves four methods to a front end — the output sink, the two prompts
and `run_async` — so no test can instantiate it directly. This subclass answers
all four with the least a test needs: the sink discards, both prompts answer,
and `run_async` starts the message loop and drains the effective queue the way a
real front end does, so a test can drive the loop through a public entry point
instead of reaching for the task it starts.
"""

import asyncio

from zrb.llm.presentation.ui.base.ui import BaseUI


class ConcreteUI(BaseUI):
    def append_to_output(self, *values, sep=" ", end="\n", kind="text", **kwargs):
        pass

    async def ask_user(self, prompt: str) -> str:
        return "yes"

    async def run_interactive_command(self, cmd, shell=False):
        return 0

    async def run_async(self) -> str:
        # Implementation of run_async to test public side effects
        self._process_messages_task = asyncio.create_task(self.process_messages_loop())
        try:
            # Wait for any pending jobs in the queue
            while not self.effective_message_queue.empty():
                await asyncio.sleep(0.01)
        finally:
            self._process_messages_task.cancel()
        return self.display.last_output
