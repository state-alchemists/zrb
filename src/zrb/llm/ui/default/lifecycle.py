"""Application lifecycle for the default `UI`.

Owns `run_async` (start triggers, message loop, system-info loop, refresh
loop; tear them down on exit) plus the periodic refresh / scroll-to-bottom
helpers. The `_cancel_and_discard` helper deduplicates the cancel-await-
discard pattern repeated for each background task.
"""

from __future__ import annotations

import asyncio
import traceback as tb_lib
from typing import TYPE_CHECKING

from zrb.config.config import CFG

if TYPE_CHECKING:
    from zrb.llm.ui.default.ui import UI


class UILifecycle:
    """Background-task lifecycle and exit handling for the default UI."""

    def __init__(self, ui: "UI") -> None:
        self._ui = ui

    async def cleanup_background_tasks(self):
        """Cancel and clean up all background tasks."""
        ui = self._ui
        await self._cancel_and_discard(ui._process_messages_task)

        while not ui._message_queue.empty():
            try:
                ui._message_queue.get_nowait()
                ui._message_queue.task_done()
            except asyncio.QueueEmpty:
                break

        for trigger_task in ui._trigger_tasks:
            await self._cancel_and_discard(trigger_task)
        ui._trigger_tasks.clear()

        await self._cancel_and_discard(ui._system_info_task)
        await self._cancel_and_discard(ui._refresh_task)

    def handle_application_run_error(self, exc: Exception):
        """Handle error during application.run_async (public API)."""

        self._ui.append_to_output(f"[Error: {exc}]\n{tb_lib.format_exc()}")

    async def run_async(self):
        """Run the application and manage triggers."""
        ui = self._ui
        for trigger_fn in ui._triggers:
            trigger_task = ui._application.create_background_task(
                ui._trigger_loop(trigger_fn)
            )
            ui._trigger_tasks.append(trigger_task)

        ui._process_messages_task = ui._application.create_background_task(
            ui._process_messages_loop()
        )
        self._track_background(ui._process_messages_task)

        ui._system_info_task = ui._application.create_background_task(
            ui._update_system_info_loop()
        )
        self._track_background(ui._system_info_task)

        ui._refresh_task = ui._application.create_background_task(self._refresh_loop())
        self._track_background(ui._refresh_task)

        try:
            ui._capture.start()
            await ui._update_system_info()
            if ui._snapshot_manager is not None:
                await ui._snapshot_manager.take_init_snapshot()
            return await ui._application.run_async()
        finally:
            ui._capture.stop()
            buffered_output = ui._capture.get_buffered_output()
            if buffered_output:
                print(buffered_output, end="")

            await self.cleanup_background_tasks()

    def _track_background(self, task: asyncio.Task | None) -> None:
        """Add a task to `_background_tasks` to prevent premature GC."""
        if task is not None and hasattr(self._ui, "_background_tasks"):
            self._ui._background_tasks.add(task)

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
            if hasattr(self._ui, "_background_tasks"):
                self._ui._background_tasks.discard(task)

    async def _refresh_loop(self):
        """Periodically invalidate UI to fix artifacts/lag."""
        # lazy: heavy third-party
        from prompt_toolkit.application import get_app

        ui = self._ui
        while True:
            try:
                app = get_app()
                app.invalidate()
                if app.layout.has_focus(ui._input_field):
                    self._scroll_output_to_bottom()
            except Exception as e:
                # Best-effort repaint loop; a transient render error must not
                # kill the loop.
                CFG.LOGGER.debug(f"Refresh loop repaint failed: {e}")
            try:
                # When thinking or waiting for confirmation, refresh faster for
                # animation (every 0.25s). Otherwise, refresh every 3s to save CPU.
                if (
                    getattr(ui, "_is_thinking", False)
                    or getattr(ui, "_current_confirmation", None) is not None
                ):
                    await asyncio.sleep(0.25)
                else:
                    await asyncio.sleep(3.0)
            except RuntimeError:
                break

    def _scroll_output_to_bottom(self):
        """Scroll output field to the bottom."""
        try:
            buffer = self._ui._output_field.buffer
            if buffer.cursor_position != len(buffer.text):
                buffer.cursor_position = len(buffer.text)
        except Exception as e:
            # Best-effort scroll; ignore if the buffer isn't ready.
            CFG.LOGGER.debug(f"Scroll-to-bottom failed: {e}")

    def handle_first_render(self):
        """Handle the first render event (public API)."""
        self._on_first_render(self._ui._application)

    def _on_first_render(self, app) -> None:
        """Submit the initial message exactly once on first render."""
        ui = self._ui
        ui._application.after_render.remove_handler(self._on_first_render)
        ui._submit_user_message(ui._llm_task, ui._initial_message)

    def invalidate_ui(self):
        # lazy: heavy third-party
        from prompt_toolkit.application import get_app

        try:
            get_app().invalidate()
        except Exception:
            # No active prompt_toolkit app (e.g. non-interactive) — nothing to repaint.
            pass

    def on_exit(self):
        # lazy: heavy third-party
        from prompt_toolkit.application import get_app

        try:
            get_app().exit()
        except Exception:
            # No active app to exit (already torn down) — nothing to do.
            pass

        if hasattr(self._ui, "_background_tasks"):
            for task in self._ui._background_tasks:
                if not task.done():
                    task.cancel()
