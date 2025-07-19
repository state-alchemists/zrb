import os

from zrb.config.config import CFG
from zrb.config.llm_context.config_handler import LLMContextConfigHandler


def cascading_path_filter(section_path: str, base_path: str) -> bool:
    """
    Returns True if the section path is an ancestor of, the same as the base path,
    or if the section path is an absolute path.
    """
    return os.path.isabs(section_path) or base_path.startswith(section_path)


class LLMContextConfig:
    """High-level API for interacting with cascaded configurations."""

    @property
    def _context_handler(self):
        return LLMContextConfigHandler(
            "Context",
            config_file_name=CFG.LLM_CONTEXT_FILE,
            filter_section_func=cascading_path_filter,
            resolve_section_path=True,
        )

    @property
    def _workflow_handler(self):
        return LLMContextConfigHandler(
            "Workflow",
            config_file_name=CFG.LLM_CONTEXT_FILE,
            resolve_section_path=False,
        )

    def get_context(self, cwd: str | None = None) -> dict[str, str]:
        """Gathers all relevant contexts for a given path."""
        if cwd is None:
            cwd = os.getcwd()
        return self._context_handler.get_section(cwd)

    def get_workflow(self, cwd: str | None = None) -> dict[str, str]:
        """Gathers all relevant workflows for a given path."""
        if cwd is None:
            cwd = os.getcwd()
        return self._workflow_handler.get_section(cwd)

    def add_to_context(
        self, content: str, context_path: str | None = None, cwd: str | None = None
    ):
        """Adds content to a context block in the nearest configuration file."""
        if cwd is None:
            cwd = os.getcwd()
        if context_path is None:
            context_path = cwd
        abs_path = os.path.abspath(context_path)
        home_dir = os.path.expanduser("~")
        search_dir = cwd
        if not abs_path.startswith(home_dir):
            search_dir = home_dir
        self._context_handler.add_to_section(content, abs_path, cwd=search_dir)

    def remove_from_context(
        self, content: str, context_path: str | None = None, cwd: str | None = None
    ):
        """Removes content from a context block in all relevant config files."""
        if cwd is None:
            cwd = os.getcwd()
        if context_path is None:
            context_path = cwd
        abs_path = os.path.abspath(context_path)
        self._context_handler.remove_from_section(content, abs_path, cwd=cwd)
