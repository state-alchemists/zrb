"""Application lifecycle for the default `UI`.

Owns `run_async` (start triggers, message loop, system-info loop, refresh
loop; tear them down on exit) plus the periodic refresh / scroll-to-bottom
helpers. The `_cancel_and_discard` helper deduplicates the cancel-await-
discard pattern repeated for each background task.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prompt_toolkit import Application


class LifecycleMixin:
    """Background-task lifecycle and exit handling for the default UI."""

    async def cleanup_background_tasks(self):
        """Cancel and clean up all background tasks."""
        await self._cancel_and_discard(self._process_messages_task)

        while not self._message_queue.empty():
            try:
                self._message_queue.get_nowait()
                self._message_queue.task_done()
            except asyncio.QueueEmpty:
                break

        for trigger_task in self._trigger_tasks:
            await self._cancel_and_discard(trigger_task)
        self._trigger_tasks.clear()

        await self._cancel_and_discard(self._system_info_task)
        await self._cancel_and_discard(self._refresh_task)

    def handle_application_run_error(self, exc: Exception):
        """Handle error during application.run_async (public API)."""
        import traceback as tb_lib

        self.append_to_output(f"[Error: {exc}]\n{tb_lib.format_exc()}")

    async def run_async(self):
        """Run the application and manage triggers."""
        for trigger_fn in self._triggers:
            trigger_task = self._application.create_background_task(
                self._trigger_loop(trigger_fn)
            )
            self._trigger_tasks.append(trigger_task)

        self._process_messages_task = self._application.create_background_task(
            self._process_messages_loop()
        )
        self._track_background(self._process_messages_task)

        self._system_info_task = self._application.create_background_task(
            self._update_system_info_loop()
        )
        self._track_background(self._system_info_task)

        self._refresh_task = self._application.create_background_task(
            self._refresh_loop()
        )
        self._track_background(self._refresh_task)

        try:
            self._capture.start()
            await self._update_system_info()
            if self._snapshot_manager is not None:
                await self._snapshot_manager.take_init_snapshot()
            return await self._application.run_async()
        finally:
            self._capture.stop()
            buffered_output = self._capture.get_buffered_output()
            if buffered_output:
                print(buffered_output, end="")

            await self.cleanup_background_tasks()

    def _track_background(self, task: asyncio.Task | None) -> None:
        """Add a task to `_background_tasks` to prevent premature GC."""
        if task is not None and hasattr(self, "_background_tasks"):
            self._background_tasks.add(task)

    async def _cancel_and_discard(self, task: asyncio.Task | None) -> None:
        """Cancel `task`, await its termination, and drop it from the set."""
        if task is None:
            return
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, RuntimeError):
            pass
        finally:
            if hasattr(self, "_background_tasks"):
                self._background_tasks.discard(task)

    async def _refresh_loop(self):
        """Periodically invalidate UI to fix artifacts/lag."""
        from prompt_toolkit.application import get_app

        while True:
            try:
                app = get_app()
                app.invalidate()
                if app.layout.has_focus(self._input_field):
                    self._scroll_output_to_bottom()
            except Exception:
                pass
            try:
                await asyncio.sleep(5.0)
            except RuntimeError:
                break

    def _scroll_output_to_bottom(self):
        """Scroll output field to the bottom."""
        try:
            buffer = self._output_field.buffer
            if buffer.cursor_position != len(buffer.text):
                buffer.cursor_position = len(buffer.text)
        except Exception:
            pass

    def handle_first_render(self):
        """Handle the first render event (public API)."""
        self._on_first_render(self._application)

    def _on_first_render(self, app: "Application"):
        """Submit the initial message exactly once on first render."""
        self._application.after_render.remove_handler(self._on_first_render)
        self._submit_user_message(self._llm_task, self._initial_message)

    def invalidate_ui(self):
        from prompt_toolkit.application import get_app

        try:
            get_app().invalidate()
        except Exception:
            pass

    def on_exit(self):
        from prompt_toolkit.application import get_app

        try:
            get_app().exit()
        except Exception:
            pass

        if hasattr(self, "_background_tasks"):
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()
