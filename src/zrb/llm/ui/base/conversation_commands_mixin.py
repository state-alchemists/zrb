"""Conversation slash-commands for `BaseUI`.

Exit, help, save/load, rewind (snapshot restore), redirect-output, and
attach. Split out of `commands_mixin.py` to keep that file focused on
dispatch; the handlers run on the composed `BaseUI` instance (see the
host-class contract below), mirroring `CommandsMixin`.

Each `_handle_*` returns ``True`` if the input was consumed, ``False``
otherwise.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from zrb.util.cli.style import stylize_error, stylize_faint

if TYPE_CHECKING:
    from typing import Any

    from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
    from zrb.llm.snapshot.manager import SnapshotManager

logger = logging.getLogger(__name__)


class ConversationCommandsMixin:
    """Conversation-management slash commands for BaseUI."""

    # Host-class contract: state and methods owned by `BaseUI`. Declared here
    # so type checkers can verify accesses; the block does not run at runtime.
    if TYPE_CHECKING:
        _attach_commands: list[str]
        _exit_commands: list[str]
        _info_commands: list[str]
        _load_commands: list[str]
        _redirect_output_commands: list[str]
        _rewind_commands: list[str]
        _save_commands: list[str]
        _background_tasks: set[asyncio.Task]
        _conversation_session_name: str
        _history_manager: "AnyHistoryManager"
        _is_thinking: bool
        _pending_attachments: list[Any]
        _snapshot_manager: "SnapshotManager | None"
        last_output: Any

        def append_to_output(self, *values: Any, **kwargs: Any) -> None: ...

        def on_exit(self) -> None: ...

        def invalidate_ui(self) -> None: ...

        def _get_help_text(self) -> str: ...

        def _replay_history(self, messages: list) -> None: ...

    # --- exit / info ------------------------------------------------------

    def _handle_exit_command(self, text: str) -> bool:
        if text.strip().lower() in self._exit_commands:
            self.on_exit()
            return True
        return False

    def _handle_info_command(self, text: str) -> bool:
        if text.strip().lower() in self._info_commands:
            self.append_to_output(stylize_faint(self._get_help_text()))
            return True
        return False

    # --- save / load ------------------------------------------------------

    def _handle_save_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._save_commands:
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                name = text[len(prefix) :].strip()
                if not name:
                    continue
                try:
                    history = self._history_manager.load(
                        self._conversation_session_name
                    )
                    self._history_manager.update(name, history)
                    self._history_manager.save(name)
                    self.append_to_output(
                        stylize_faint(f"\n  💾 Conversation saved as: {name}\n")
                    )
                except Exception as e:
                    self.append_to_output(
                        stylize_error(f"\n  ❌ Failed to save conversation: {e}\n")
                    )
                return True
        return False

    def _handle_load_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._load_commands:
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                name = text[len(prefix) :].strip()
                if not name:
                    continue
                self._conversation_session_name = name
                try:
                    history = self._history_manager.load(name)
                    self._replay_history(history)
                except Exception as e:
                    self.append_to_output(
                        stylize_error(f"\n  ❌ Failed to load history: {e}\n")
                    )
                self.append_to_output(
                    stylize_faint(f"\n  📂 Conversation session switched to: {name}\n")
                )
                return True
        return False

    # --- rewind -----------------------------------------------------------

    def _handle_rewind_command(self, text: str) -> bool:
        if not self._snapshot_manager:
            return False
        text = text.strip()
        for cmd in self._rewind_commands:
            if not (
                text.lower() == cmd.lower()
                or text.lower().startswith(cmd.lower() + " ")
            ):
                continue
            arg = text[len(cmd) :].strip()
            if arg:
                snapshots = self._snapshot_manager.list_snapshots()
                sha: str | None = None
                message_count: int | None = None
                try:
                    idx = int(arg) - 1
                    if 0 <= idx < len(snapshots):
                        sha = snapshots[idx].sha
                        message_count = snapshots[idx].message_count
                    else:
                        self.append_to_output(
                            stylize_error(f"\n  ❌ No snapshot at index {arg}\n")
                        )
                        return True
                except ValueError:
                    sha = arg  # treat as SHA prefix/full
                    for snap in snapshots:
                        if snap.sha.startswith(sha):
                            message_count = snap.message_count
                            break

                async def do_restore(s=sha, mc=message_count):
                    self._is_thinking = True
                    self.invalidate_ui()
                    try:
                        self.append_to_output(
                            stylize_faint(f"\n  ⏪ Restoring snapshot {s[:8]}...\n")
                        )
                        ok = await self._snapshot_manager.restore_snapshot(s)
                        if ok:
                            if mc is not None:
                                try:
                                    msgs = self._history_manager.load(
                                        self._conversation_session_name
                                    )
                                    if len(msgs) > mc:
                                        self._history_manager.update(
                                            self._conversation_session_name,
                                            msgs[:mc],
                                        )
                                        self._history_manager.save(
                                            self._conversation_session_name
                                        )
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to rewind conversation history: {e}"
                                    )
                            self.append_to_output(
                                stylize_faint(f"\n  ✅ Snapshot {s[:8]} restored.\n")
                            )
                        else:
                            self.append_to_output(
                                stylize_error("\n  ❌ Failed to restore snapshot.\n")
                            )
                    finally:
                        self._is_thinking = False
                        self.invalidate_ui()

                task = asyncio.create_task(do_restore())
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
            else:
                snapshots = self._snapshot_manager.list_snapshots()
                if not snapshots:
                    self.append_to_output(
                        stylize_faint(
                            "\n  No snapshots yet. Snapshots are taken before each AI turn.\n"
                        )
                    )
                else:
                    lines = ["\n  Snapshots (newest first):"]
                    for i, snap in enumerate(snapshots, 1):
                        lines.append(
                            f"  {i:>3}. [{snap.sha[:8]}] {snap.timestamp}  {snap.label}"
                        )
                    lines.append(
                        f"\n  Use `{cmd} <number>` or `{cmd} <sha>` to restore.\n"
                    )
                    self.append_to_output(stylize_faint("\n".join(lines)))
            return True
        return False

    # --- redirect / attach ------------------------------------------------

    def _handle_redirect_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._redirect_output_commands:
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                path = text[len(prefix) :].strip()
                if not path:
                    continue

                content = self.last_output
                if not content:
                    self.append_to_output(
                        stylize_error("\n  ❌ No AI response available to redirect.\n")
                    )
                    return True

                try:
                    expanded_path = os.path.abspath(os.path.expanduser(path))
                    os.makedirs(os.path.dirname(expanded_path), exist_ok=True)
                    with open(expanded_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    self.append_to_output(
                        stylize_faint(f"\n  📝 Last output redirected to: {path}\n")
                    )
                except Exception as e:
                    self.append_to_output(
                        stylize_error(f"\n  ❌ Failed to redirect output: {e}\n")
                    )

                return True
        return False

    def _handle_attach_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._attach_commands:
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                path = text[len(prefix) :].strip()
                self._submit_attachment(path)
                return True
        return False

    def _submit_attachment(self, path: str):
        # Validate path
        self.append_to_output(stylize_faint(f"\n  🔢 Attach {path}...\n"))
        expanded_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(expanded_path):
            self.append_to_output(stylize_error(f"\n  ❌ File not found: {path}\n"))
            return
        if expanded_path not in self._pending_attachments:
            self._pending_attachments.append(expanded_path)
            self.append_to_output(stylize_faint(f"\n  📎 Attached: {path}\n"))
        else:
            self.append_to_output(stylize_error(f"\n  📎 Already attached: {path}\n"))
