from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, TextIO, TypedDict

from zrb.llm.util.delivery_report import DeliveryOutcome, DeliveryReport

if TYPE_CHECKING:
    from collections.abc import Sequence

    from zrb.llm.agent.types import ModelMessage, RequestUsage, RunUsage, UserContent
    from zrb.llm.input_source import InputProvenance
    from zrb.llm.ui.base.message_queue import QueuedMessage


class ChoiceOption(TypedDict, total=False):
    label: str
    description: str
    recommended: bool


class ChoiceSpec(TypedDict, total=False):
    """Structured spec for a single multiple-choice question.

    Carries everything a selection widget needs to render arrow-key choices.
    `index`/`total` drive the "Question 2 of 3" footer. UIs that cannot render
    a widget fall back to formatting this as numbered text (see
    `BaseUI.ask_user_choice`).
    """

    question: str
    options: list[ChoiceOption]
    context: str
    multi_select: bool
    header: str
    index: int
    total: int


class AnyUI(ABC):
    """The UI contract every task's `ui` slot is typed against.

    Eight behavioral methods every UI performs, then the state members and
    side-effect hooks a full UI keeps. `BaseUI` implements all of them; a UI
    that keeps none mixes in `UIStateDefaultsMixin`. The state half is
    abstract because `MultiUI` reads it off its primary child, so a custom UI
    missing it fails with `TypeError` at construction.

    The output-enrichment and queue hooks at the end are concrete: each has a
    default that does what a UI which never heard of the hook would want, so
    callers invoke them directly and a UI overrides only the ones it renders
    better than the default.
    """

    @abstractmethod
    async def ask_user(
        self,
        prompt: str,
        output_to_parent: str = "",
        agent_id: str | None = None,
    ) -> str:
        """Ask the user a free-text question and return their answer."""

    @abstractmethod
    async def ask_user_choice(
        self, spec: ChoiceSpec, agent_id: str | None = None
    ) -> str:
        """Ask the user a multiple-choice question and return their pick."""

    @abstractmethod
    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """Write output the way `print()` would, kept for later replay."""

    @abstractmethod
    def stream_to_parent(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
        kind: str = "text",
    ):
        """Write output to a delegating parent UI, not this UI's own stream."""

    @abstractmethod
    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        """Run an interactive shell command, handing it the real terminal."""

    @abstractmethod
    async def run_async(self) -> Any:
        """Drive this UI's own event loop until the session ends."""

    @abstractmethod
    def track_echo_span(self, entry: "QueuedMessage", echo: str) -> None:
        """Record the output-buffer span of `echo` on `entry` for `redraw_echo`.

        A UI with no output buffer leaves the entry untouched.
        """

    @abstractmethod
    def redraw_echo(self, entry: "QueuedMessage") -> str | None:
        """Rewrite `entry`'s echoed line from its current text.

        Returns the rewritten line, or None when it could not be spliced in
        place; the caller then echoes afresh.
        """

    @abstractmethod
    def remove_echo(self, entry: "QueuedMessage") -> None:
        """Take `entry`'s echoed line out of this UI's output.

        Called when a still-queued message is dropped. A UI with no output
        buffer leaves the entry alone.
        """

    def submit_message(
        self, user_message: str, source: "InputProvenance | None"
    ) -> None:
        """Queue *user_message* the way a typed one is queued: steered into the
        running turn at its next model request, or run as the next turn when the
        session is idle.

        *source* names where the words came from, or is None for words that are
        not the user's. A UI that keeps no queue (a headless run has no idle
        session to wake) leaves the message alone, so a sender that is not
        the user — a finished background command — never assumes it arrived.
        """

    def withdraw_message(
        self, user_message: str, source: "InputProvenance | None"
    ) -> None:
        """Take back a message `submit_message` queued that has not started.

        For a sender whose message became moot before anything read it — a
        finished background command whose result the model has since fetched.
        A message already read, or whose turn started, is beyond recall, and a UI
        that keeps no queue has nothing to take back: both leave it alone.
        """

    @property
    def is_local(self) -> bool:
        """Whether the user driving this UI sits at the machine zrb runs on.

        The default is True: a UI is local until it says otherwise. A UI
        driven over a network (the web chat, Telegram) returns False, so a
        command that acts on local hardware — the screen, the camera — can
        refuse instead of capturing a machine the user cannot see.
        """
        return True

    @property
    @abstractmethod
    def is_thinking(self) -> bool:
        """Whether the assistant is currently producing a response."""

    @is_thinking.setter
    @abstractmethod
    def is_thinking(self, value: bool) -> None: ...

    @property
    @abstractmethod
    def is_turn_running(self) -> bool:
        """Whether a turn is running that `cancel_current_turn` would stop:
        this UI's own, or the one its `MultiUI` parent runs for it."""

    @property
    @abstractmethod
    def is_waiting_for_answer(self) -> bool:
        """Whether a tool approval or a question is waiting for the user."""

    @abstractmethod
    def is_prompt_answered_since(self, asked_at: float) -> bool:
        """Whether the first prompt asked at or after *asked_at* (a
        `time.monotonic()` value) has been answered or cancelled. ``False``
        before it is asked, or when the UI cannot tell."""

    @property
    @abstractmethod
    def llm_task(self) -> Any:
        """The `LLMTask` driving this UI, or None when it has none."""

    @llm_task.setter
    @abstractmethod
    def llm_task(self, value: Any) -> None: ...

    @property
    @abstractmethod
    def model(self) -> Any:
        """The model this UI is currently talking to, or None."""

    @model.setter
    @abstractmethod
    def model(self, value: Any) -> None: ...

    @property
    @abstractmethod
    def yolo(self) -> bool | frozenset:
        """Auto-approval state: False, True, or the set of auto-approved tools.

        Read-only here; `BaseUI` adds the setter.
        """

    @property
    @abstractmethod
    def multi_ui_parent(self) -> Any:
        """The `MultiUI` this UI is a child of, or None when standalone."""

    @multi_ui_parent.setter
    @abstractmethod
    def multi_ui_parent(self, parent: Any) -> None: ...

    @property
    @abstractmethod
    def tool_call_handler(self) -> Any:
        """This UI's tool-call confirmation handler, or None when it has none."""

    @property
    @abstractmethod
    def small_model(self) -> Any:
        """The `/model small ...` override this UI holds, or None."""

    @small_model.setter
    @abstractmethod
    def small_model(self, value: Any) -> None: ...

    @property
    @abstractmethod
    def multimodal_model(self) -> Any:
        """The `/model multimodal ...` override this UI holds, or None."""

    @multimodal_model.setter
    @abstractmethod
    def multimodal_model(self, value: Any) -> None: ...

    @property
    @abstractmethod
    def conversation_session_name(self) -> str:
        """The conversation this UI is attached to. Empty when it tracks none."""

    @conversation_session_name.setter
    @abstractmethod
    def conversation_session_name(self, value: str) -> None: ...

    @property
    @abstractmethod
    def plan_mode_active(self) -> bool:
        """Whether `/plan` is on. `MultiUI` both reads and writes this on its
        primary child to keep the badge in step with in-run mode changes."""

    @plan_mode_active.setter
    @abstractmethod
    def plan_mode_active(self, value: bool) -> None: ...

    @property
    @abstractmethod
    def last_output(self) -> str:
        """The last answer this UI rendered, or "" when it has none."""

    @property
    @abstractmethod
    def snapshot_manager(self) -> Any:
        """This UI's filesystem-snapshot manager, or None when it keeps none."""

    @property
    @abstractmethod
    def history_manager(self) -> Any:
        """This UI's conversation history manager, or None when it keeps none."""

    @property
    @abstractmethod
    def background_tasks(self) -> "set[asyncio.Task]":
        """Tasks this UI keeps referenced so they are not garbage collected.

        Callers mutate the returned set directly (`.add`, `.discard`), so an
        implementation must hand back the same set each time, not a copy.
        """

    @abstractmethod
    def invalidate_ui(self) -> None:
        """Ask this UI to repaint. A no-op for UIs with no live surface."""

    @abstractmethod
    def set_status_badge(self, key: str, text: str | None) -> None:
        """Show *text* in the status bar under *key*, replacing what *key*
        showed before; ``None`` takes it away. For a feature's one-line state.
        A no-op for UIs with no status bar.
        """

    @abstractmethod
    def cancel_pending_confirmations(self, flush: bool = True) -> None:
        """Release any `ask_user` call blocked on a tool confirmation.

        A no-op for UIs that never hold one. `flush=False` from the Ctrl+C /
        exit path, where writing buffered tokens is wasted work.
        """

    @abstractmethod
    def cancel_current_turn(self, reason: str) -> None:
        """Stop the turn the assistant is taking, as Esc does: release a
        pending confirmation, cancel the running turn and fire `Stop` with
        *reason* (who asked, e.g. ``"escape"``). With no turn running only
        the confirmation is released; a UI that never runs a turn and holds
        no confirmation does nothing.
        """

    @abstractmethod
    def flush_to_parent(self) -> None:
        """Write anything buffered here out to the delegating parent UI.

        A no-op for UIs that stream directly rather than buffering.
        """

    @abstractmethod
    def send_queued_messages_now(self) -> DeliveryReport:
        """Deliver the queued messages into the running turn, now.

        The report says what the attempt did: delivered into the live run,
        fell back to interrupting the turn, or moved nothing. A UI with no
        queue of its own moves nothing.
        """

    # Optional hooks. Concrete, so no UI has to implement them and every caller
    # can invoke them directly; the default is what an absent hook would mean.

    def accumulate_usage(
        self, usage: "RunUsage", context_usage: "RequestUsage | None" = None
    ) -> None:
        """Fold one run's token totals into a session meter. No-op by default."""

    def reset_context_usage(self) -> None:
        """Forget the context size, stale after `/compress`. No-op by default."""

    def append_markdown(self, markdown_text: str) -> None:
        """Show *markdown_text*; the default renders it and writes the text.

        A UI with a pane that renders Markdown itself overrides this to take
        the source instead.
        """
        # lazy: transitively heavy -- the renderer pulls the theme and the
        # markdown stack.
        from zrb.util.cli.markdown import render_markdown

        self.append_to_output(render_markdown(markdown_text, width=None), end="")

    def append_answer(self, markdown_text: str) -> None:
        """Show the turn's answer; the default hands it to `append_markdown`.

        A UI that lays a run's output out in a column overrides this so the
        answer lands where the streamed copy was.
        """
        self.append_markdown(markdown_text)

    def record_tool_call_block(self, collapsed: str, full: str) -> None:
        """Print a tool-call/result line a toggle-capable UI can later expand.

        The default writes the collapsed form as a plain `tool_call` line.
        """
        self.append_to_output(collapsed, end="", kind="tool_call")

    def mark_thinking_block_start(self) -> None:
        """Note where a live thinking block begins. No-op by default."""

    def collapse_thinking_block(self, collapsed: str, full: str) -> bool | None:
        """Collapse the block `mark_thinking_block_start` opened.

        Returns whether a block was collapsed, or None for a UI that tracks
        none. No-op by default: the thinking text stays as streamed.
        """

    def mark_text_block_start(self) -> None:
        """Note where the reply's text block begins. No-op by default."""

    def collapse_text_block(self, collapsed: str, full: str) -> bool | None:
        """Collapse the block `mark_text_block_start` opened.

        Returns whether a block was collapsed, or None for a UI that tracks
        none. No-op by default: the streamed text stays as it is.
        """

    def settle_text_block(self, source: str) -> None:
        """Keep a text block that a tool call ended, rendering *source* in full.

        No-op by default: the streamed copy stays as it is.
        """

    def set_stream_indentation(self, indent: str) -> None:
        """Learn the column a run's streamed lines wrap at. No-op by default."""

    def start_tool_call(self, tool_name: str, tool_call_id: str) -> None:
        """Note that a tool call is about to run. No-op by default."""

    def end_tool_call(self, tool_call_id: str | None = None) -> None:
        """Note that a tool call finished; ``None`` means every call.

        No-op by default.
        """

    def replay_history(self, messages: "list[ModelMessage]") -> None:
        """Show a resumed conversation; the default writes it as plain text."""
        # lazy: zrb.llm.util.history_formatter transitively loads pydantic_ai.
        from zrb.llm.util.history_formatter import format_history_as_text

        self.append_to_output(format_history_as_text(messages))

    async def update_system_info(self) -> None:
        """Refresh the system and repository status line after a turn.

        No-op by default.
        """

    def record_submitted_message(self, text: str) -> None:
        """Remember a message the user submitted, for recall. No-op by default."""

    def take_pending_attachments(self) -> "list[UserContent]":
        """Hand over, and clear, the attachments waiting for the next message.

        The default holds none.
        """
        return []

    def track_rendered_echo(self, entry: "QueuedMessage", header: str) -> None:
        """Record the span of an echo whose body was rendered as Markdown.

        *header* is the verbatim part written before the rendered body.
        No-op by default, like `track_echo_span`.
        """

    def redraw_echoes(self, entries: "Sequence[QueuedMessage]") -> None:
        """Rewrite the echoed lines of *entries* just delivered into a turn.

        No-op by default.
        """

    def deliver_queued_messages_early(self) -> DeliveryReport:
        """Hand the ready queued messages to the running turn at a checkpoint.

        The run loop calls it as it builds each model request, and nothing is
        interrupted. The default has no queue, so nothing moves.
        """
        return DeliveryReport(DeliveryOutcome.NOTHING_MOVED)
