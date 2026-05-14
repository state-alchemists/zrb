import json
import os
import re
import warnings
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
            # Suppress Pydantic serialization warnings for BinaryContent in parts
            # (pydantic-ai's type adapter schema doesn't include BinaryContent in its
            # union, but serialization still works correctly)

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="Pydantic serializer warnings",
                    category=UserWarning,
                )
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

    # ------------------------------------------------------------------
    # Part-cleaner helpers for _clean_corrupted_content
    # ------------------------------------------------------------------

    def _clean_user_prompt_part(self, data: dict[str, Any]) -> dict[str, Any]:
        content = data.get("content")
        if content is None:
            content = ""
        elif isinstance(content, list):
            if any(not isinstance(item, str) for item in content):
                content = to_string(content)
        elif not isinstance(content, str):
            content = to_string(content)
        return {"part_kind": "user-prompt", "content": content}

    def _clean_text_like_part(
        self, part_kind: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        content = data.get("content")
        if not isinstance(content, str):
            content = to_string(content) if content is not None else ""
        return {"part_kind": part_kind, "content": content}

    def _clean_tool_return_part(self, data: dict[str, Any]) -> dict[str, Any]:
        content = data.get("content")
        if content is None:
            content = ""
        res = {
            "part_kind": "tool-return",
            "content": content,
            "tool_name": data.get("tool_name", "unknown"),
        }
        if data.get("tool_call_id"):
            res["tool_call_id"] = data["tool_call_id"]
        if data.get("timestamp"):
            res["timestamp"] = data["timestamp"]
        return res

    def _clean_tool_call_part(self, data: dict[str, Any]) -> dict[str, Any] | None:
        tool_name = data.get("tool_name")
        if tool_name is None:
            return None
        res = {
            "part_kind": "tool-call",
            "tool_name": tool_name,
            "args": data.get("args") if data.get("args") is not None else {},
        }
        if data.get("tool_call_id"):
            res["tool_call_id"] = data["tool_call_id"]
        return res

    def _clean_corrupted_content(self, data: Any) -> Any:
        """Recursively clean corrupted content in message data."""
        if isinstance(data, dict):
            part_kind = data.get("part_kind")
            if part_kind == "user-prompt":
                return self._clean_user_prompt_part(data)
            if part_kind in ("text", "system-prompt", "thinking", "retry-prompt"):
                return self._clean_text_like_part(part_kind, data)
            if part_kind == "tool-return":
                return self._clean_tool_return_part(data)
            if part_kind == "tool-call":
                return self._clean_tool_call_part(data)
            return {
                k: self._clean_corrupted_content(v)
                for k, v in data.items()
                if v is not None
            }
        if isinstance(data, list):
            return [
                item
                for item in (self._clean_corrupted_content(i) for i in data)
                if item is not None
            ]
        return data

    def _is_valid_message_part(self, part: Any) -> bool:
        """Check if a message part is non-empty and valid."""
        if not isinstance(part, dict):
            return part is not None
        part_kind = part.get("part_kind")
        if part_kind == "tool-call":
            return part.get("tool_name") is not None
        if "content" in part:
            content = part.get("content")
            return content is not None and content != ""
        return part_kind is not None

    def _filter_empty_responses(self, data: Any) -> Any:
        """Filter out empty responses and parts with null content from history data."""
        if isinstance(data, list):
            filtered = []
            for item in data:
                if isinstance(item, dict):
                    kind = item.get("kind")
                    parts = item.get("parts")
                    if kind in ("response", "request") and isinstance(parts, list):
                        filtered_parts = [
                            p for p in parts if self._is_valid_message_part(p)
                        ]
                        item = {**item, "parts": filtered_parts}
                        if len(filtered_parts) == 0:
                            continue
                    item = {k: self._filter_empty_responses(v) for k, v in item.items()}
                    filtered.append(item)
                else:
                    filtered.append(self._filter_empty_responses(item))
            return filtered
        if isinstance(data, dict):
            return {
                k: v
                for k, v in (
                    (k, self._filter_empty_responses(v)) for k, v in data.items()
                )
                if v is not None
            }
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
