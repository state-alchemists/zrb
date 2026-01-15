import json
import os
from typing import Dict, List

from pydantic_ai import ModelMessage
from pydantic_ai.messages import ModelMessagesTypeAdapter

from zrb.builtin.pollux.history_manager.any_history_manager import AnyHistoryManager


class FileHistoryManager(AnyHistoryManager):
    def __init__(self, history_dir: str):
        self._history_dir = os.path.expanduser(history_dir)
        self._cache: Dict[str, List[ModelMessage]] = {}
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

    def load(self, conversation_name: str) -> List[ModelMessage]:
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
            print(f"Warning: Failed to load history for {conversation_name}: {e}")
            return []

    def update(self, conversation_name: str, messages: List[ModelMessage]):
        self._cache[conversation_name] = messages

    def save(self, conversation_name: str):
        if conversation_name not in self._cache:
            return

        messages = self._cache[conversation_name]
        file_path = self._get_file_path(conversation_name)

        try:
            data = ModelMessagesTypeAdapter.dump_python(messages, mode="json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            print(f"Error: Failed to save history for {conversation_name}: {e}")
