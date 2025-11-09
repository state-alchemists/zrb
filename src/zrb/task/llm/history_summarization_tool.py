from typing import Callable

from zrb.task.llm.conversation_history_model import ConversationHistory


def create_history_summarization_tool(
    conversation_history: ConversationHistory,
) -> Callable[[str, str], str]:
    def update_conversation_memory(
        past_conversation_summary: str,
        past_conversation_transcript: str,
    ) -> str:
        """
        Update the conversation memory including summary and transcript.
        - past_conversation_summary: A concise narrative that integrates the
          previous summary with the recent conversation.
        - past_conversation_transcript: MUST be ONLY the last 4 (four) turns
          of the conversation.
        """
        conversation_history.past_conversation_summary = past_conversation_summary
        conversation_history.past_conversation_transcript = past_conversation_transcript
        return "Conversation memory updated"

    return update_conversation_memory
