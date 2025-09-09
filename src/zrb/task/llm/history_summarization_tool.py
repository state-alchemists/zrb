import json
from typing import Callable

from zrb.config.llm_context.config import llm_context_config
from zrb.task.llm.conversation_history_model import ConversationHistory


def create_history_summarization_tool(
    conversation_history: ConversationHistory,
) -> Callable[[str, str, str | None, str | None, str | None], str]:
    def update_conversation_memory(
        past_conversation_summary: str,
        past_conversation_transcript: str,
        long_term_note: str | None = None,
        contextual_note: str | None = None,
        context_path: str | None = None,
    ) -> str:
        """
        Update the conversation memory including summary, transcript, and notes.
        - past_conversation_summary: A concise narrative that integrates the
          previous summary with the recent conversation.
        - past_conversation_transcript: MUST be ONLY the last 4 (four) turns
          of the conversation.
        - long_term_note: Global facts about the user or their preferences.
        - contextual_note: Facts specific to the current project or directory.
        - context_path: The directory path for the contextual note.
        """
        conversation_history.past_conversation_summary = past_conversation_summary
        conversation_history.past_conversation_transcript = past_conversation_transcript
        if long_term_note is not None:
            llm_context_config.write_context(long_term_note, context_path="/")
        if contextual_note is not None:
            if context_path is None:
                context_path = conversation_history.project_path
            llm_context_config.write_context(contextual_note, context_path=context_path)
        return "Conversation memory updated"

    return update_conversation_memory
