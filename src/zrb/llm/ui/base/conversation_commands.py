"""Conversation slash-commands for `BaseUI`.

Exit, help, save/load, rewind (snapshot restore), redirect-output, copy,
and attach. Split out of `commands.py` to keep that file focused on
dispatch. Composed into `BaseUICommands` as `self._conversation`, keeping
`BaseUI` in `self._base_ui` for state and method calls.

Each `_handle_*` returns ``True`` if the input was consumed, ``False``
otherwise.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from zrb.llm.util.attachment import get_media_type, get_oversized_by
from zrb.llm.util.camera import get_camera_photo, missing_tool_hint
from zrb.llm.util.image_scale import scale_image_bytes
from zrb.llm.util.subagent_session_naming import parse_delegated_session
from zrb.util.cli.style import stylize_error, stylize_muted

if TYPE_CHECKING:
    from zrb.llm.ui.base.ui import BaseUI

logger = logging.getLogger(__name__)


class BaseUIConversationCommands:
    """Conversation-management slash commands for BaseUI."""

    def __init__(self, base_ui: "BaseUI") -> None:
        self._base_ui = base_ui

    # --- exit / info ------------------------------------------------------

    def handle_exit_command(self, text: str) -> bool:
        if text.strip().lower() in self._base_ui.exit_commands:
            self._base_ui.on_exit()
            return True
        return False

    def handle_info_command(self, text: str) -> bool:
        if text.strip().lower() in self._base_ui.info_commands:
            # Rendered by print_help, not wrapped in a style here: the panel
            # emits its own ANSI, which an enclosing style code would break.
            self._base_ui.print_help()
            return True
        return False

    # --- save / load ------------------------------------------------------

    def handle_save_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._base_ui.save_commands:
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                name = text[len(prefix) :].strip()
                if not name:
                    continue
                try:
                    history = self._base_ui.history_manager.load(
                        self._base_ui.conversation_session_name
                    )
                    self._base_ui.history_manager.update(name, history)
                    self._base_ui.history_manager.save(name)
                    self._base_ui.history_manager.load(name)
                    self._base_ui.conversation_session_name = name
                    self._base_ui.append_to_output(
                        stylize_muted(
                            f"\n  💾 Conversation saved and switched to: {name}\n"
                        )
                    )
                except Exception as e:
                    self._base_ui.append_to_output(
                        stylize_error(f"\n  ❌ Failed to save conversation: {e}\n")
                    )
                return True
        return False

    def handle_load_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._base_ui.load_commands:
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                name = text[len(prefix) :].strip()
                if not name:
                    continue
                self._base_ui.conversation_session_name = name
                try:
                    history = self._base_ui.history_manager.load(name)
                    self._base_ui.replay_history(history)
                    # The usage meter tracks spend per loaded conversation;
                    # past sessions' spend is not persisted, so start fresh.
                    self._base_ui.reset_session_token_usage()
                    self.apply_persona_for_session(name)
                except Exception as e:
                    self._base_ui.append_to_output(
                        stylize_error(f"\n  ❌ Failed to load history: {e}\n")
                    )
                self._base_ui.append_to_output(
                    stylize_muted(f"\n  📂 Conversation session switched to: {name}\n")
                )
                return True
        return False

    # --- Item 4, Phase D: persona-swap-on-/load ----------------------------
    #
    # /load already switches which history is replayed; loading a delegated
    # sub-agent's transcript (Item 4, Phase A naming) additionally swaps which
    # persona drives new messages, so continuing the conversation actually
    # talks to that sub-agent rather than the main agent. Loading back to an
    # ordinary session name restores the main agent — /load is the single,
    # symmetric verb for both directions, mirroring how opencode's "up"/"down"
    # navigation is really just "which session am I bound to right now".

    def apply_persona_for_session(self, name: str) -> None:
        delegated = parse_delegated_session(name)
        if delegated is None:
            self._restore_main_persona()
            return
        self._swap_to_subagent_persona(delegated[1])

    def _swap_to_subagent_persona(self, agent_name: str) -> None:
        # lazy: heavy transitive (pydantic_ai) via SubAgentManager.
        from zrb.llm.agent.subagent.manager import sub_agent_manager
        from zrb.llm.prompt.manager import PromptManager

        definition = sub_agent_manager.get_agent_definition(agent_name)
        if definition is None or definition.agent_instance or definition.agent_factory:
            self._base_ui.append_to_output(
                stylize_error(
                    f"\n  ⚠️  Cannot resume as sub-agent '{agent_name}': its "
                    "definition no longer exists, or it was built from a "
                    "pre-built agent instance that cannot be resumed this "
                    "way. Continuing as the main agent.\n"
                )
            )
            return
        resolved = sub_agent_manager.resolve_agent_build(
            definition, ctx=None, yolo=None
        )

        self._snapshot_main_persona_once()
        self._base_ui.llm_task.tools = resolved.tools
        self._base_ui.llm_task.toolsets = resolved.toolsets
        self._base_ui.llm_task.prompt_manager = PromptManager(
            prompts=[resolved.system_prompt] if resolved.system_prompt else [],
            include_sections=[],
        )
        self._base_ui.model = resolved.model
        self._base_ui.active_subagent_persona = agent_name
        self._base_ui.append_to_output(
            stylize_muted(f"\n  🤖 Now driving as sub-agent: {agent_name}\n")
        )
        self._base_ui.invalidate_ui()

    def _restore_main_persona(self) -> None:
        snapshot = self._base_ui.original_persona_snapshot
        if snapshot is None:
            return  # never swapped away — nothing to restore
        self._base_ui.llm_task.tools = snapshot["tools"]
        self._base_ui.llm_task.toolsets = snapshot["toolsets"]
        self._base_ui.llm_task.prompt_manager = snapshot["prompt_manager"]
        self._base_ui.model = snapshot["model"]
        self._base_ui.active_subagent_persona = None
        self._base_ui.original_persona_snapshot = None
        self._base_ui.append_to_output(
            stylize_muted("\n  🤖 Back to the main agent.\n")
        )
        self._base_ui.invalidate_ui()

    def _snapshot_main_persona_once(self) -> None:
        """Capture the main agent's config the first time it's swapped away
        from, so `_restore_main_persona` always restores the *original*
        persona rather than whichever sub-agent was active most recently."""
        if self._base_ui.original_persona_snapshot is not None:
            return
        self._base_ui.original_persona_snapshot = {
            "tools": list(self._base_ui.llm_task.tools),
            "toolsets": list(self._base_ui.llm_task.toolsets),
            "prompt_manager": self._base_ui.llm_task.prompt_manager,
            "model": self._base_ui.model,
        }

    # --- rewind -----------------------------------------------------------

    def handle_rewind_command(self, text: str) -> bool:
        if not self._base_ui.snapshot_manager:
            return False
        text = text.strip()
        for cmd in self._base_ui.rewind_commands:
            if not (
                text.lower() == cmd.lower()
                or text.lower().startswith(cmd.lower() + " ")
            ):
                continue
            arg = text[len(cmd) :].strip()
            if arg:
                snapshots = self._base_ui.snapshot_manager.list_snapshots()
                sha: str | None = None
                message_count: int | None = None
                try:
                    idx = int(arg) - 1
                    if 0 <= idx < len(snapshots):
                        sha = snapshots[idx].sha
                        message_count = snapshots[idx].message_count
                    else:
                        self._base_ui.append_to_output(
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
                    snapshot_manager = self._base_ui.snapshot_manager
                    if snapshot_manager is None:
                        return
                    self._base_ui.is_thinking = True
                    self._base_ui.invalidate_ui()
                    try:
                        self._base_ui.append_to_output(
                            stylize_muted(f"\n  ⏪ Restoring snapshot {s[:8]}...\n")
                        )
                        ok = await snapshot_manager.restore_snapshot(s)
                        if ok:
                            if mc is not None:
                                try:
                                    msgs = self._base_ui.history_manager.load(
                                        self._base_ui.conversation_session_name
                                    )
                                    if len(msgs) > mc:
                                        self._base_ui.history_manager.update(
                                            self._base_ui.conversation_session_name,
                                            msgs[:mc],
                                        )
                                        self._base_ui.history_manager.save(
                                            self._base_ui.conversation_session_name
                                        )
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to rewind conversation history: {e}"
                                    )
                            self._base_ui.append_to_output(
                                stylize_muted(f"\n  ✅ Snapshot {s[:8]} restored.\n")
                            )
                        else:
                            self._base_ui.append_to_output(
                                stylize_error("\n  ❌ Failed to restore snapshot.\n")
                            )
                    finally:
                        self._base_ui.is_thinking = False
                        self._base_ui.invalidate_ui()

                task = asyncio.create_task(do_restore())
                self._base_ui.background_tasks.add(task)
                task.add_done_callback(self._base_ui.background_tasks.discard)
            else:
                snapshots = self._base_ui.snapshot_manager.list_snapshots()
                if not snapshots:
                    self._base_ui.append_to_output(
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
                    self._base_ui.append_to_output(stylize_muted("\n".join(lines)))
            return True
        return False

    # --- redirect / attach ------------------------------------------------

    def last_ai_response(self) -> str:
        """Last AI response text: the live one, else the latest from history.

        ``last_output`` is only populated after a live turn this run. On a
        freshly loaded ``chat --session ...`` the transcript is replayed from
        disk, so fall back to the most recent assistant message in history.
        """
        content = self._base_ui.last_output
        if content:
            return content
        try:
            messages = self._base_ui.history_manager.load(
                self._base_ui.conversation_session_name
            )
        except Exception:
            return ""
        # lazy: tests patch extract_last_response_text; hoisting bypasses the mock
        from zrb.llm.util.history_formatter import extract_last_response_text

        return extract_last_response_text(messages)

    def write_text_to_file(self, path: str, content: str) -> None:
        """Expand/absolutize `path`, create parent dirs, and write `content`.

        Shared by the redirect/copy commands' "write to file" branches — kept
        separate from `zrb.util.file.write_file`, which additionally
        normalizes trailing newlines (not wanted here: this must write
        exactly what the user is redirecting/saving).
        """
        expanded_path = os.path.abspath(os.path.expanduser(path))
        os.makedirs(os.path.dirname(expanded_path), exist_ok=True)
        with open(expanded_path, "w", encoding="utf-8") as f:
            f.write(content)

    def copy_to_clipboard_and_report(self, content: str, success_message: str) -> None:
        """Copy `content` to the clipboard, appending a success/failure line."""
        # lazy: tests patch clipboard.copy_text; hoisting bypasses the mock
        from zrb.llm.util.clipboard import copy_text

        if copy_text(content):
            self._base_ui.append_to_output(stylize_muted(success_message))
        else:
            self._base_ui.append_to_output(
                stylize_error("\n  ❌ Failed to copy to clipboard.\n")
            )

    def handle_redirect_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._base_ui.redirect_output_commands:
            # Bare command → copy last output to clipboard.
            if text.lower() == cmd.lower():
                content = self.last_ai_response()
                if not content:
                    self._base_ui.append_to_output(
                        stylize_error("\n  ❌ No AI response available to copy.\n")
                    )
                    return True
                self.copy_to_clipboard_and_report(
                    content, "\n  📋 Last output copied to clipboard.\n"
                )
                return True

            # Command with arg → redirect to file (existing behaviour).
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                path = text[len(prefix) :].strip()
                if not path:
                    continue

                content = self.last_ai_response()
                if not content:
                    self._base_ui.append_to_output(
                        stylize_error("\n  ❌ No AI response available to redirect.\n")
                    )
                    return True

                try:
                    self.write_text_to_file(path, content)
                    self._base_ui.append_to_output(
                        stylize_muted(f"\n  📝 Last output redirected to: {path}\n")
                    )
                except Exception as e:
                    self._base_ui.append_to_output(
                        stylize_error(f"\n  ❌ Failed to redirect output: {e}\n")
                    )

                return True
        return False

    # --- copy --------------------------------------------------------------

    def handle_copy_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._base_ui.copy_commands:
            # Bare command → copy full transcript to clipboard.
            if text.lower() == cmd.lower():
                try:
                    messages = self._base_ui.history_manager.load(
                        self._base_ui.conversation_session_name
                    )
                    if not messages:
                        self._base_ui.append_to_output(
                            stylize_error("\n  ❌ No conversation history to copy.\n")
                        )
                        return True
                    # lazy: tests patch format_history_as_text; hoisting bypasses the mock
                    from zrb.llm.util.history_formatter import (
                        format_history_as_text,
                    )

                    transcript = format_history_as_text(messages, full=True)
                    self.copy_to_clipboard_and_report(
                        transcript, "\n  📋 Full transcript copied to clipboard.\n"
                    )
                except Exception as e:
                    self._base_ui.append_to_output(
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
                    messages = self._base_ui.history_manager.load(
                        self._base_ui.conversation_session_name
                    )
                    if not messages:
                        self._base_ui.append_to_output(
                            stylize_error("\n  ❌ No conversation history to save.\n")
                        )
                        return True
                    # lazy: tests patch format_history_as_text; hoisting bypasses the mock
                    from zrb.llm.util.history_formatter import (
                        format_history_as_text,
                    )

                    transcript = format_history_as_text(messages, full=True)
                    self.write_text_to_file(path, transcript)
                    self._base_ui.append_to_output(
                        stylize_muted(f"\n  📝 Transcript saved to: {path}\n")
                    )
                except Exception as e:
                    self._base_ui.append_to_output(
                        stylize_error(f"\n  ❌ Failed to save transcript: {e}\n")
                    )
                return True
        return False

    def handle_attach_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._base_ui.attach_commands:
            prefix = f"{cmd} "
            if text.lower().startswith(prefix):
                path = text[len(prefix) :].strip()
                self.submit_attachment(path)
                return True
        return False

    def submit_attachment(self, path: str):
        self._base_ui.append_to_output(stylize_muted(f"\n  🔢 Attach {path}...\n"))
        expanded_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isfile(expanded_path):
            self._base_ui.append_to_output(
                stylize_error(f"\n  ❌ File not found: {path}\n")
            )
            return
        if not get_media_type(expanded_path):
            self._base_ui.append_to_output(
                stylize_error(f"\n  ❌ Unsupported file type: {path}\n")
            )
            return
        oversized_by = get_oversized_by(expanded_path)
        if oversized_by is not None:
            actual, limit = oversized_by
            self._base_ui.append_to_output(
                stylize_error(
                    f"\n  ❌ File too large: {path} "
                    f"({actual} bytes, limit {limit} bytes)\n"
                )
            )
            return
        if expanded_path not in self._base_ui.pending_attachments:
            self._base_ui.pending_attachments.append(expanded_path)
            self._base_ui.append_to_output(stylize_muted(f"\n  📎 Attached: {path}\n"))
        else:
            self._base_ui.append_to_output(
                stylize_error(f"\n  📎 Already attached: {path}\n")
            )

    def handle_photo_command(self, text: str) -> bool:
        text = text.strip()
        for cmd in self._base_ui.photo_commands:
            if text.lower() == cmd.lower():
                device = None
            else:
                prefix = f"{cmd} "
                if not text.lower().startswith(prefix.lower()):
                    continue
                device = text[len(prefix) :].strip() or None
            task = asyncio.create_task(self.submit_photo(device))
            self._base_ui.background_tasks.add(task)
            task.add_done_callback(self._base_ui.background_tasks.discard)
            return True
        return False

    async def submit_photo(self, device: str | None):
        self._base_ui.append_to_output(stylize_muted("\n  📷 Capturing photo...\n"))
        photo_bytes = await get_camera_photo(device)
        if photo_bytes is None:
            self._base_ui.append_to_output(
                stylize_error(f"\n  ❌ Camera capture failed.\n{missing_tool_hint()}")
            )
            return
        # lazy: heavy third-party
        from pydantic_ai import BinaryContent

        scaled = scale_image_bytes(photo_bytes, media_type="image/jpeg")
        attachment = BinaryContent(data=scaled.data, media_type=scaled.media_type)
        self._base_ui.pending_attachments.append(attachment)
        self._base_ui.append_to_output(
            stylize_muted(f"\n  📷 Photo captured ({scaled.final_bytes} bytes)\n")
        )
        self._base_ui.invalidate_ui()
