"""Conversation slash-commands for `BaseUI`.

Exit, help, save/load, rewind (snapshot restore), redirect-output, copy,
and attach. Split out of `commands_mixin.py` to keep that file focused on
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

from zrb.util.cli.style import stylize_error, stylize_muted

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
        _copy_commands: list[str]
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

        def reset_session_token_usage(self) -> None: ...

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
            self.append_to_output(stylize_muted(self._get_help_text()))
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
                    self._history_manager.load(name)
                    self._conversation_session_name = name
                    self.append_to_output(
                        stylize_muted(
                            f"\n  💾 Conversation saved and switched to: {name}\n"
                        )
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
                    # The usage meter tracks spend per loaded conversation;
                    # past sessions' spend is not persisted, so start fresh.
                    self.reset_session_token_usage()
                except Exception as e:
                    self.append_to_output(
                        stylize_error(f"\n  ❌ Failed to load history: {e}\n")
                    )
                self.append_to_output(
                    stylize_muted(f"\n  📂 Conversation session switched to: {name}\n")
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
                    snapshot_manager = self._snapshot_manager
                    if snapshot_manager is None:
                        return
                    self._is_thinking = True
                    self.invalidate_ui()
                    try:
                        self.append_to_output(
                            stylize_muted(f"\n  ⏪ Restoring snapshot {s[:8]}...\n")
                        )
                        ok = await snapshot_manager.restore_snapshot(s)
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
                                stylize_muted(f"\n  ✅ Snapshot {s[:8]} restored.\n")
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
                        stylize_muted(
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
                    self.append_to_output(stylize_muted("\n".join(lines)))
            return True
        return False

    # --- redirect / attach ------------------------------------------------

    def _last_ai_response(self) -> str:
        """Last AI response text: the live one, else the latest from history.

        ``last_output`` is only populated after a live turn this run. On a
        freshly loaded ``chat --session ...`` the transcript is replayed from
        disk, so fall back to the most recent assistant message in history.
        """
        content = self.last_output
        if content:
            return content
        try:
            messages = self._history_manager.load(self._conversation_session_name)
        except Exception:
            return ""
        # lazy: tests patch extract_last_response_text; hoisting bypasses the mock
        from zrb.llm.util.history_formatter import extract_last_response_text

        return extract_last_response_text(messages)

    def _handle_redirect_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._redirect_output_commands:
            # Bare command → copy last output to clipboard.
            if text.lower() == cmd.lower():
                content = self._last_ai_response()
                if not content:
                    self.append_to_output(
                        stylize_error("\n  ❌ No AI response available to copy.\n")
                    )
                    return True
                # lazy: tests patch clipboard.copy_text; hoisting bypasses the mock
                from zrb.llm.util.clipboard import copy_text

                if copy_text(content):
                    self.append_to_output(
                        stylize_muted("\n  📋 Last output copied to clipboard.\n")
                    )
                else:
                    self.append_to_output(
                        stylize_error("\n  ❌ Failed to copy to clipboard.\n")
                    )
                return True

            # Command with arg → redirect to file (existing behaviour).
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                path = text[len(prefix) :].strip()
                if not path:
                    continue

                content = self._last_ai_response()
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
                        stylize_muted(f"\n  📝 Last output redirected to: {path}\n")
                    )
                except Exception as e:
                    self.append_to_output(
                        stylize_error(f"\n  ❌ Failed to redirect output: {e}\n")
                    )

                return True
        return False

    # --- copy --------------------------------------------------------------

    def _handle_copy_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._copy_commands:
            # Bare command → copy full transcript to clipboard.
            if text.lower() == cmd.lower():
                try:
                    messages = self._history_manager.load(
                        self._conversation_session_name
                    )
                    if not messages:
                        self.append_to_output(
                            stylize_error("\n  ❌ No conversation history to copy.\n")
                        )
                        return True
                    # lazy: tests patch copy_text/format_history; hoisting bypasses mocks
                    from zrb.llm.util.clipboard import copy_text
                    from zrb.llm.util.history_formatter import (
                        format_history_as_text,
                    )

                    transcript = format_history_as_text(messages, full=True)
                    if copy_text(transcript):
                        self.append_to_output(
                            stylize_muted(
                                "\n  📋 Full transcript copied to clipboard.\n"
                            )
                        )
                    else:
                        self.append_to_output(
                            stylize_error("\n  ❌ Failed to copy to clipboard.\n")
                        )
                except Exception as e:
                    self.append_to_output(
                        stylize_error(f"\n  ❌ Failed to copy transcript: {e}\n")
                    )
                return True

            # Command with arg → write transcript to file.
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                path = text[len(prefix) :].strip()
                if not path:
                    continue
                try:
                    messages = self._history_manager.load(
                        self._conversation_session_name
                    )
                    if not messages:
                        self.append_to_output(
                            stylize_error("\n  ❌ No conversation history to save.\n")
                        )
                        return True
                    # lazy: tests patch format_history_as_text; hoisting bypasses the mock
                    from zrb.llm.util.history_formatter import (
                        format_history_as_text,
                    )

                    transcript = format_history_as_text(messages, full=True)
                    expanded_path = os.path.abspath(os.path.expanduser(path))
                    os.makedirs(os.path.dirname(expanded_path), exist_ok=True)
                    with open(expanded_path, "w", encoding="utf-8") as f:
                        f.write(transcript)
                    self.append_to_output(
                        stylize_muted(f"\n  📝 Transcript saved to: {path}\n")
                    )
                except Exception as e:
                    self.append_to_output(
                        stylize_error(f"\n  ❌ Failed to save transcript: {e}\n")
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
        self.append_to_output(stylize_muted(f"\n  🔢 Attach {path}...\n"))
        expanded_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(expanded_path):
            self.append_to_output(stylize_error(f"\n  ❌ File not found: {path}\n"))
            return
        if expanded_path not in self._pending_attachments:
            self._pending_attachments.append(expanded_path)
            self.append_to_output(stylize_muted(f"\n  📎 Attached: {path}\n"))
        else:
            self.append_to_output(stylize_error(f"\n  📎 Already attached: {path}\n"))
