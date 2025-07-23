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

    def get_contexts(self, cwd: str | None = None) -> dict[str, str]:
        """Gathers all relevant contexts for a given path."""
        if cwd is None:
            cwd = os.getcwd()
        all_sections = self._get_all_sections(cwd)
        contexts: dict[str, str] = {}
        for config_dir, sections in reversed(all_sections):
            for key, value in sections.items():
                if key.startswith("Context:"):
                    context_path = key.replace("Context:", "").strip()
                    if context_path == ".":
                        context_path = config_dir
                    elif not os.path.isabs(context_path):
                        context_path = os.path.abspath(
                            os.path.join(config_dir, context_path)
                        )
                    if os.path.isabs(context_path) or cwd.startswith(context_path):
                        contexts[context_path] = value
        return contexts

    def get_workflows(self, cwd: str | None = None) -> dict[str, str]:
        """Gathers all relevant workflows for a given path."""
        if cwd is None:
            cwd = os.getcwd()
        all_sections = self._get_all_sections(cwd)
        workflows: dict[str, str] = {}
        for _, sections in reversed(all_sections):
            for key, value in sections.items():
                if key.startswith("Workflow:"):
                    workflow_name = key.replace("Workflow:", "").strip()
                    if workflow_name not in workflows:
                        workflows[workflow_name] = value
        return workflows

    def write_context(
        self, content: str, context_path: str | None = None, cwd: str | None = None
    ):
        """Writes content to a context block in the nearest configuration file."""
        if cwd is None:
            cwd = os.getcwd()
        if context_path is None:
            context_path = cwd

        config_files = self._find_config_files(cwd)
        if config_files:
            config_file = config_files[0]  # Closest config file
        else:
            config_file = os.path.join(cwd, CFG.LLM_CONTEXT_FILE)

        sections = {}
        if os.path.exists(config_file):
            sections = self._parse_config(config_file)

        # Determine the section key
        section_key_path = context_path
        if not os.path.isabs(context_path):
            config_dir = os.path.dirname(config_file)
            section_key_path = os.path.abspath(os.path.join(config_dir, context_path))

        # Find existing key
        found_key = ""
        for key in sections.keys():
            if not key.startswith("Context:"):
                continue
            key_path = key.replace("Context:", "").strip()
            if key_path == ".":
                key_path = os.path.dirname(config_file)
            elif not os.path.isabs(key_path):
                key_path = os.path.abspath(
                    os.path.join(os.path.dirname(config_file), key_path)
                )
            if key_path == section_key_path:
                found_key = key
                break

        if found_key != "":
            sections[found_key] = content
        else:
            # Add new entry
            new_key = f"Context: {context_path}"
            sections[new_key] = content

        # Serialize back to markdown
        new_file_content = ""
        for key, value in sections.items():
            new_file_content += f"# {key}\n{demote_markdown_headers(value)}\n\n"

        with open(config_file, "w") as f:
            f.write(new_file_content)


llm_context_config = LLMContextConfig()
