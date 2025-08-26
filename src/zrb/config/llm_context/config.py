import os

from zrb.config.config import CFG
from zrb.config.llm_context.config_parser import markdown_to_dict
from zrb.util.llm.prompt import demote_markdown_headers


class LLMContextConfig:
    """High-level API for interacting with cascaded configurations."""

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

    def get_contexts(self, cwd: str | None = None) -> dict[str, str]:
        """Gathers all relevant contexts for a given path."""
        if cwd is None:
            cwd = os.getcwd()
        all_sections = self._get_all_sections(cwd)
        contexts: dict[str, str] = {}
        for config_dir, sections in reversed(all_sections):
            for key, value in sections.items():
                if key.startswith("Context:"):
                    context_path_str = key[len("Context:") :].strip()
                    abs_context_path = self._normalize_context_path(
                        context_path_str,
                        config_dir,
                    )
                    # A context is relevant if its path is an ancestor of cwd
                    if os.path.commonpath([cwd, abs_context_path]) == abs_context_path:
                        contexts[abs_context_path] = value
        return contexts

    def get_workflows(self, cwd: str | None = None) -> dict[str, str]:
        """Gathers all relevant workflows for a given path."""
        if cwd is None:
            cwd = os.getcwd()
        all_sections = self._get_all_sections(cwd)
        workflows: dict[str, str] = {}
        # Iterate from closest to farthest
        for _, sections in all_sections:
            for key, value in sections.items():
                if key.startswith("Workflow:"):
                    workflow_name = key[len("Workflow:") :].strip().lower()
                    # First one found wins
                    if workflow_name not in workflows:
                        workflows[workflow_name] = value
        return workflows

    def _format_context_path_for_writing(
        self,
        path_to_write: str,
        cwd: str,
    ) -> str:
        """Formats a path for writing into a context file key."""
        home_dir = os.path.expanduser("~")
        abs_path_to_write = os.path.abspath(os.path.join(cwd, path_to_write))
        abs_cwd = os.path.abspath(cwd)
        # Rule 1: Inside CWD
        if abs_path_to_write.startswith(abs_cwd):
            if abs_path_to_write == abs_cwd:
                return "."
            return os.path.relpath(abs_path_to_write, abs_cwd)
        # Rule 2: Inside Home
        if abs_path_to_write.startswith(home_dir):
            if abs_path_to_write == home_dir:
                return "~"
            return os.path.join("~", os.path.relpath(abs_path_to_write, home_dir))
        # Rule 3: Absolute
        return abs_path_to_write

    def write_context(
        self,
        content: str,
        context_path: str | None = None,
        cwd: str | None = None,
    ):
        """Writes content to a context block in CWD's configuration file."""
        if cwd is None:
            cwd = os.getcwd()
        if context_path is None:
            context_path = cwd

        config_file = os.path.join(cwd, CFG.LLM_CONTEXT_FILE)

        sections = {}
        if os.path.exists(config_file):
            sections = self._parse_config(config_file)

        abs_context_path = os.path.abspath(os.path.join(cwd, context_path))

        found_key = None
        for key in sections.keys():
            if not key.startswith("Context:"):
                continue
            context_path_str = key[len("Context:") :].strip()
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
            formatted_path = self._format_context_path_for_writing(
                context_path,
                cwd,
            )
            new_key = f"Context: {formatted_path}"
            sections[new_key] = content

        # Serialize back to markdown
        new_file_content = ""
        for key, value in sections.items():
            new_file_content += f"# {key}\n{demote_markdown_headers(value)}\n\n"

        with open(config_file, "w") as f:
            f.write(new_file_content)


llm_context_config = LLMContextConfig()
