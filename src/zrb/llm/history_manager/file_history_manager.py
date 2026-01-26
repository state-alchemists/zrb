import json
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai import ModelMessage

from zrb.context.any_context import zrb_print
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.util.match import fuzzy_match


class FileHistoryManager(AnyHistoryManager):
    def __init__(self, history_dir: str):
        self._history_dir = os.path.expanduser(history_dir)
        self._cache: "dict[str, list[ModelMessage]]" = {}
        if not os.path.exists(self._history_dir):
            os.makedirs(self._history_dir, exist_ok=True)

    def _get_file_path(self, conversation_name: str) -> str:
        # Sanitize conversation name to be safe for filename
        safe_name = "".join(
            c for c in conversation_name if c.isalnum() or c in (" ", ".", "_", "-")
        ).strip()
        if not safe_name:
            safe_name = "default"
        return os.path.join(self._history_dir, f"{safe_name}.json")

    def load(self, conversation_name: str) -> "list[ModelMessage]":
        from pydantic_ai.messages import ModelMessagesTypeAdapter

        if conversation_name in self._cache:
            return self._cache[conversation_name]

        file_path = self._get_file_path(conversation_name)
        if not os.path.exists(file_path):
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip():
                    return []
                data = json.loads(content)
                messages = ModelMessagesTypeAdapter.validate_python(data)
                self._cache[conversation_name] = messages
                return messages
        except (json.JSONDecodeError, OSError) as e:
            # Log error or warn? For now, return empty list or re-raise.
            # Returning empty list is safer for UI not to crash.
            zrb_print(
                f"Warning: Failed to load history for {conversation_name}: {e}",
                plain=True,
            )
            return []

    def update(self, conversation_name: str, messages: "list[ModelMessage]"):
        self._cache[conversation_name] = messages

    def save(self, conversation_name: str):
        from pydantic_ai.messages import ModelMessagesTypeAdapter

        if conversation_name not in self._cache:
            return

        messages = self._cache[conversation_name]
        file_path = self._get_file_path(conversation_name)

        try:
            data = ModelMessagesTypeAdapter.dump_python(messages, mode="json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            zrb_print(
                f"Error: Failed to save history for {conversation_name}: {e}",
                plain=True,
            )

    def search(self, keyword: str) -> list[str]:
        if not os.path.exists(self._history_dir):
            return []

        matches = []
        for filename in os.listdir(self._history_dir):
            if not filename.endswith(".json"):
                continue

            # Remove extension to get session name
            session_name = filename[:-5]

            is_match, score = fuzzy_match(session_name, keyword)
            if is_match:
                matches.append((session_name, score))

        # Sort by score (lower is better)
        matches.sort(key=lambda x: x[1])

        return [m[0] for m in matches]
