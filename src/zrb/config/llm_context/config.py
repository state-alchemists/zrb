import os

from zrb.config.config import CFG
from zrb.config.llm_context.config_parser import markdown_to_dict
from zrb.config.llm_context.workflow import LLMWorkflow
from zrb.util.markdown import demote_markdown_headers


class LLMContextConfig:
    """High-level API for interacting with cascaded configurations."""

    def write_note(
        self,
        content: str,
        context_path: str | None = None,
        cwd: str | None = None,
    ):
        """Writes content to a note block in the user's home configuration file."""
        if cwd is None:
            cwd = os.getcwd()
        if context_path is None:
            context_path = cwd
        config_file = self._get_home_config_file()
        sections = {}
        if os.path.exists(config_file):
            sections = self._parse_config(config_file)
        abs_context_path = os.path.abspath(os.path.join(cwd, context_path))
        found_key = None
        for key in sections.keys():
            if not key.startswith("Note:"):
                continue
            context_path_str = key[len("Note:") :].strip()
            abs_key_path = self._normalize_context_path(
                context_path_str,
                os.path.dirname(config_file),
            )
            if abs_key_path == abs_context_path:
                found_key = key
                break
        if found_key:
            sections[found_key] = content
        else:
            config_dir = os.path.dirname(config_file)
            formatted_path = self._format_context_path_for_writing(
                abs_context_path,
                config_dir,
            )
            new_key = f"Note: {formatted_path}"
            sections[new_key] = content
        # Serialize back to markdown
        new_file_content = ""
        for key, value in sections.items():
            new_file_content += f"# {key}\n{demote_markdown_headers(value)}\n\n"
        with open(config_file, "w") as f:
            f.write(new_file_content)

    def get_notes(self, cwd: str | None = None) -> dict[str, str]:
        """Gathers all notes for a given path."""
        if cwd is None:
            cwd = os.getcwd()
        config_file = self._get_home_config_file()
        if not os.path.exists(config_file):
            return {}
        config_dir = os.path.dirname(config_file)
        sections = self._parse_config(config_file)
        notes: dict[str, str] = {}
        for key, value in sections.items():
            if key.lower().startswith("note:"):
                context_path_str = key[len("note:") :].strip()
                abs_context_path = self._normalize_context_path(
                    context_path_str,
                    config_dir,
                )
                # A context is relevant if its path is an ancestor of cwd
                if os.path.commonpath([cwd, abs_context_path]) == abs_context_path:
                    notes[abs_context_path] = value
        return notes

    def get_workflows(self, cwd: str | None = None) -> dict[str, LLMWorkflow]:
        """Gathers all relevant workflows for a given path."""
        if cwd is None:
            cwd = os.getcwd()
        all_sections = self._get_all_sections(cwd)
        workflows: dict[str, LLMWorkflow] = {}
        # Iterate from closest to farthest
        for config_dir, sections in all_sections:
            for key, value in sections.items():
                if key.lower().startswith("workflow:"):
                    workflow_name = key[len("workflow:") :].strip().lower()
                    # First one found wins
                    if workflow_name not in workflows:
                        workflows[workflow_name] = LLMWorkflow(
                            name=workflow_name,
                            content=value,
                            path=config_dir,
                        )
        return workflows

    def _format_context_path_for_writing(
        self,
        path_to_write: str,
        relative_to_dir: str,
    ) -> str:
        """Formats a path for writing into a context file key."""
        home_dir = os.path.expanduser("~")
        abs_path_to_write = os.path.abspath(
            os.path.join(relative_to_dir, path_to_write)
        )
        abs_relative_to_dir = os.path.abspath(relative_to_dir)
        # Rule 1: Inside relative_to_dir
        if abs_path_to_write.startswith(abs_relative_to_dir):
            if abs_path_to_write == abs_relative_to_dir:
                return "."
            return os.path.relpath(abs_path_to_write, abs_relative_to_dir)
        # Rule 2: Inside Home
        if abs_path_to_write.startswith(home_dir):
            if abs_path_to_write == home_dir:
                return "~"
            return os.path.join("~", os.path.relpath(abs_path_to_write, home_dir))
        # Rule 3: Absolute
        return abs_path_to_write

    def _find_config_files(self, cwd: str) -> list[str]:
        configs = []
        current_dir = cwd
        home_dir = os.path.expanduser("~")
        while True:
            config_path = os.path.join(current_dir, CFG.LLM_CONTEXT_FILE)
            if os.path.exists(config_path):
                configs.append(config_path)
            if current_dir == home_dir or current_dir == "/":
                break
            current_dir = os.path.dirname(current_dir)
        return configs

    def _get_home_config_file(self) -> str:
        home_dir = os.path.expanduser("~")
        return os.path.join(home_dir, CFG.LLM_CONTEXT_FILE)

    def _parse_config(self, file_path: str) -> dict[str, str]:
        with open(file_path, "r") as f:
            content = f.read()
        return markdown_to_dict(content)

    def _get_all_sections(self, cwd: str) -> list[tuple[str, dict[str, str]]]:
        config_files = self._find_config_files(cwd)
        all_sections = []
        for config_file in config_files:
            config_dir = os.path.dirname(config_file)
            sections = self._parse_config(config_file)
            all_sections.append((config_dir, sections))
        return all_sections

    def _normalize_context_path(
        self,
        path_str: str,
        relative_to_dir: str,
    ) -> str:
        """Normalizes a context path string to an absolute path."""
        expanded_path = os.path.expanduser(path_str)
        if os.path.isabs(expanded_path):
            return os.path.abspath(expanded_path)
        return os.path.abspath(os.path.join(relative_to_dir, expanded_path))


llm_context_config = LLMContextConfig()
