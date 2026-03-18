import json
import os
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_ai import ModelMessage

from zrb.context.any_context import zrb_print
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.util.match import fuzzy_match
from zrb.util.string.conversion import to_string

# Pattern to match timestamp suffix like -2024-03-18-10-30-00 or -2024-03-18-10-30
_TIMESTAMP_PATTERN = re.compile(r"-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}(?:-\d{2})?$")


class FileHistoryManager(AnyHistoryManager):
    def __init__(self, history_dir: str):
        self._history_dir = os.path.expanduser(history_dir)
        self._cache: "dict[str, list[ModelMessage]]" = {}
        if not os.path.exists(self._history_dir):
            os.makedirs(self._history_dir, exist_ok=True)

    def _clean_corrupted_content(self, data: Any) -> Any:
        """Recursively clean corrupted content in message data.

        Handles any part with content field that contains invalid types
        (dictionaries, booleans, numbers, etc.) by converting them to strings.
        """
        if isinstance(data, dict):
            # Check if this is any part with a content field that could be corrupted
            # pydantic-ai uses "part_kind" for part type
            part_kind = data.get("part_kind")
            # Parts that have content fields: user-prompt, text, system-prompt,
            # thinking, tool-return, etc.
            if part_kind in [
                "user-prompt",
                "text",
                "system-prompt",
                "thinking",
                "tool-return",
            ]:
                content = data.get("content")
                # Handle None content by converting to empty string
                if content is None:
                    data["content"] = ""
                else:
                    # Content should typically be str | Sequence[UserContent] for user-prompt,
                    # str for text/system-prompt/thinking, str for tool-return
                    # If it's not a string or list (for user-prompt), convert it to string
                    if part_kind == "user-prompt":
                        # UserPromptPart.content can be str | Sequence[UserContent]
                        # If it's a list, we need to check if it's a valid Sequence[UserContent]
                        # For now, if it's a list of non-strings, convert the whole list to JSON string
                        if isinstance(content, list):
                            # Check if list contains only valid UserContent (strings or dicts with text)
                            # For simplicity, if any item is not a string, convert whole list to JSON string
                            if any(not isinstance(item, str) for item in content):
                                data["content"] = to_string(content)
                        elif not isinstance(content, str):
                            data["content"] = to_string(content)
                    else:
                        # Other parts: content should be string
                        if not isinstance(content, str):
                            data["content"] = to_string(content)

            # Recursively clean all values
            return {k: self._clean_corrupted_content(v) for k, v in data.items()}

        elif isinstance(data, list):
            return [self._clean_corrupted_content(item) for item in data]

        else:
            return data

    def _filter_empty_responses(self, data: Any) -> Any:
        """Filter out empty responses (responses with no parts) from history data.

        Empty responses can cause "invalid message content type: <nil>" errors
        with certain models like GLM-5 via Ollama when the history is sent to the model.
        """
        if isinstance(data, list):
            filtered_list = []
            for item in data:
                if isinstance(item, dict):
                    kind = item.get("kind")
                    parts = item.get("parts")
                    # Filter out empty responses
                    if kind == "response" and (parts is None or parts == []):
                        continue  # Skip this empty response
                    # Recursively filter nested structures
                    filtered_item = self._filter_empty_responses(item)
                    filtered_list.append(filtered_item)
                else:
                    filtered_list.append(item)
            return filtered_list
        elif isinstance(data, dict):
            # Recursively filter all values in the dictionary
            return {k: self._filter_empty_responses(v) for k, v in data.items()}
        else:
            return data

    def _get_file_path(self, conversation_name: str) -> str:
        # Sanitize conversation name to be safe for filename
        safe_name = "".join(
            c for c in conversation_name if c.isalnum() or c in (" ", ".", "_", "-")
        ).strip()
        if not safe_name:
            safe_name = "default"
        return os.path.join(self._history_dir, f"{safe_name}.json")

    def _extract_base_name(self, conversation_name: str) -> str:
        """Extract base session name by removing timestamp suffix if present.

        For example:
        - "my-session-2024-03-18-10-30-00" -> "my-session"
        - "my-session-2024-03-18-10-30" -> "my-session"
        - "my-session" -> "my-session"
        """
        # Remove timestamp suffix if present
        return _TIMESTAMP_PATTERN.sub("", conversation_name)

    def _get_backup_file_path(self, base_name: str, timestamp: datetime) -> str:
        """Get a backup file path with timestamp, handling conflicts.

        Creates files like: <name>-2024-03-18-10-30-00.json
        If that exists: <name>-2024-03-18-10-30-00-1.json
        If that exists: <name>-2024-03-18-10-30-00-2.json
        etc.
        """
        ts_str = timestamp.strftime("%Y-%m-%d-%H-%M-%S")
        base_path = os.path.join(self._history_dir, f"{base_name}-{ts_str}")

        # Check if the base backup path exists
        candidate = f"{base_path}.json"
        if not os.path.exists(candidate):
            return candidate

        # Find next available sequence number
        counter = 1
        while True:
            candidate = f"{base_path}-{counter}.json"
            if not os.path.exists(candidate):
                return candidate
            counter += 1
            # Safety limit
            if counter > 1000:
                # Fallback to using microseconds
                ts_str_with_us = timestamp.strftime("%Y-%m-%d-%H-%M-%S-%f")
                return os.path.join(
                    self._history_dir, f"{base_name}-{ts_str_with_us}.json"
                )

    def _save_data_to_file(self, file_path: str, data: Any) -> bool:
        """Save filtered data to a file.

        Returns True if successful, False otherwise.
        """
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except OSError as e:
            zrb_print(f"Error: Failed to save history to {file_path}: {e}", plain=True)
            return False

    def load(self, conversation_name: str) -> "list[ModelMessage]":
        from pydantic import ValidationError
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

                # ALWAYS clean data before validation to prevent boolean corruption
                # This is critical because pydantic_ai validation might allow boolean values
                # which will cause TypeError in Google model's _map_user_prompt
                cleaned_data = self._clean_corrupted_content(data)

                # Filter out empty responses (responses with no parts) before validation
                # Empty responses can cause "invalid message content type: <nil>" errors
                # with certain models like GLM-5 via Ollama
                filtered_data = self._filter_empty_responses(cleaned_data)

                # Validate the cleaned and filtered data
                messages = ModelMessagesTypeAdapter.validate_python(filtered_data)
                self._cache[conversation_name] = messages
                return messages

        except ValidationError as e:
            # If validation fails even after cleaning, log and return empty
            zrb_print(
                f"Warning: Failed to load history for {conversation_name} even after cleanup: {e}",
                plain=True,
            )
            return []

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
        from pydantic import ValidationError
        from pydantic_ai.messages import ModelMessagesTypeAdapter

        if conversation_name not in self._cache:
            return

        messages = self._cache[conversation_name]
        file_path = self._get_file_path(conversation_name)

        try:
            # First, try to serialize the messages
            data = ModelMessagesTypeAdapter.dump_python(messages, mode="json")

            # ALWAYS clean data before saving to prevent boolean corruption
            # This ensures that even if pydantic_ai validation allows boolean values,
            # we convert them to strings before saving to disk
            cleaned_data = self._clean_corrupted_content(data)

            # Filter out empty responses before saving to prevent future issues
            # Empty responses can cause "invalid message content type: <nil>" errors
            # with certain models like GLM-5 via Ollama
            filtered_data = self._filter_empty_responses(cleaned_data)

            # Validate the cleaned and filtered data
            ModelMessagesTypeAdapter.validate_python(filtered_data)

            # Save the main history file
            self._save_data_to_file(file_path, filtered_data)

            # Create a timestamped backup
            base_name = self._extract_base_name(conversation_name)
            timestamp = datetime.now()
            backup_path = self._get_backup_file_path(base_name, timestamp)
            if backup_path:
                self._save_data_to_file(backup_path, filtered_data)

        except ValidationError as e:
            # If validation fails even after cleaning, log and don't save
            zrb_print(
                f"Warning: Failed to save history for {conversation_name} due to validation error: {e}",
                plain=True,
            )
            # Don't save corrupted data

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
