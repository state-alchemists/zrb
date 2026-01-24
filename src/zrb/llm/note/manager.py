import json
import os
from typing import Dict

from zrb.config.config import CFG


class NoteManager:
    def __init__(self, context_file: str = CFG.LLM_NOTE_FILE):
        self.context_file = os.path.abspath(os.path.expanduser(context_file))

    def _get_normalized_path(self, path: str) -> str:
        """
        Convert path to absolute path, then try to make it relative to home.
        If it's inside home, return '~/rel/path'.
        Otherwise return absolute path.
        """
        abs_path = os.path.abspath(os.path.expanduser(path))
        home = os.path.expanduser("~")

        if abs_path.startswith(home):
            rel_path = os.path.relpath(abs_path, home)
            if rel_path == ".":
                return "~"
            return os.path.join("~", rel_path)

        return abs_path

    def _load_data(self) -> Dict[str, str]:
        if not os.path.exists(self.context_file):
            return {}
        try:
            with open(self.context_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_data(self, data: Dict[str, str]):
        os.makedirs(os.path.dirname(self.context_file), exist_ok=True)
        with open(self.context_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def write(self, context_path: str, content: str):
        """
        Write content to context file for a specific path.
        Turn context path to be relative to home directory (unless it is outside home directory).
        """
        key = self._get_normalized_path(context_path)
        data = self._load_data()
        data[key] = content
        self._save_data(data)

    def read(self, context_path: str) -> str:
        """
        Seek for any key in context file that match context path.
        """
        key = self._get_normalized_path(context_path)
        data = self._load_data()
        return data.get(key, "")

    def read_all(self, context_path: str) -> Dict[str, str]:
        """
        Seek for all key in context file that match context path or any of its parent, return as key-value.
        """
        target_path = self._get_normalized_path(context_path)
        data = self._load_data()

        result = {}

        # Check for root/home notes (~)
        if "~" in data:
            result["~"] = data["~"]

        # If target_path is just "~", we are done
        if target_path == "~":
            return result

        # We need to find all parents of target_path that are in data
        # Example target: ~/zrb/src
        # Parents: ~, ~/zrb

        # Split the path parts
        # If path starts with "~", we treat it specially

        parts = []
        if target_path.startswith("~" + os.sep) or target_path == "~":
            # Remove ~
            rel_part = target_path[2:]  # "zrb/src"
            parts = rel_part.split(os.sep)
            current = "~"
        else:
            # Absolute path like /opt/project
            parts = target_path.split(os.sep)
            # parts for /opt/project -> ['', 'opt', 'project']
            current = parts[0]  # '' (root)
            if current == "":
                current = "/"
            parts = parts[1:]

        # Check if 'current' exists in data before building up
        if current in data:
            result[current] = data[current]

        # Iterate and build up path
        for part in parts:
            if current == "~":
                current = os.path.join("~", part)
            elif current == "/":
                current = os.path.join("/", part)
            else:
                current = os.path.join(current, part)

            # Normalize just in case os.path.join changes things
            # But wait, our keys in JSON are stored with separators.
            # We should probably reconstruct the key carefully.

            # Let's simplify:
            # Check if 'current' exists in data
            if current in data:
                result[current] = data[current]

        # Finally check the target_path itself if not covered
        if target_path in data and target_path not in result:
            result[target_path] = data[target_path]

        return result
