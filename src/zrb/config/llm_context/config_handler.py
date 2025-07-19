import os
import re
from typing import Callable, Generator, NamedTuple


class Section(NamedTuple):
    name: str
    key: str
    content: str
    config_file: str


def _parse_config_file(
    config_file: str, lines: list[str]
) -> Generator[Section, None, None]:
    """
    Parses a config file's lines, yielding sections.
    It correctly handles markdown code fences.
    """
    any_header_pattern = re.compile(r"^# (\w+):\s*(.*)")
    fence_pattern = re.compile(r"^([`~]{3,})")
    fence_stack = []
    active_section_name = None
    active_section_key = None
    active_section_content = []

    for line in lines:
        stripped_line = line.strip()
        fence_match = fence_pattern.match(stripped_line)

        if fence_match:
            current_fence = fence_match.group(1)
            if (
                fence_stack
                and fence_stack[-1][0] == current_fence[0]
                and len(current_fence) >= len(fence_stack[-1])
            ):
                fence_stack.pop()
            else:
                fence_stack.append(current_fence)

        if fence_stack:
            if active_section_key is not None:
                active_section_content.append(line)
            continue

        match = any_header_pattern.match(line)
        if match:
            if active_section_key is not None:
                content = "".join(active_section_content).strip()
                if content:
                    yield Section(
                        name=active_section_name,
                        key=active_section_key,
                        content=content,
                        config_file=config_file,
                    )

            active_section_name = match.group(1)
            active_section_key = match.group(2).strip()
            active_section_content = []
        elif active_section_key is not None:
            active_section_content.append(line)

    if active_section_key is not None:
        content = "".join(active_section_content).strip()
        if content:
            yield Section(
                name=active_section_name,
                key=active_section_key,
                content=content,
                config_file=config_file,
            )


def _get_config_file_hierarchy(path: str, config_file_name: str) -> list[str]:
    """Finds all config files from a given path up to the home directory."""
    config_files = []
    home_dir = os.path.expanduser("~")
    current_path = os.path.abspath(path)
    while True:
        config_path = os.path.join(current_path, config_file_name)
        if os.path.exists(config_path):
            config_files.append(config_path)
        if current_path == home_dir:
            break
        parent = os.path.dirname(current_path)
        if parent == current_path:  # Reached root
            break
        current_path = parent
    return config_files


class LLMContextConfigHandler:
    """Handles the logic for a specific section of the config."""

    def __init__(
        self,
        section_name: str,
        config_file_name: str = "ZRB.md",
        filter_section_func: Callable[[str, str], bool] | None = None,
        resolve_section_path: bool = True,
    ):
        self._section_name = section_name
        self._config_file_name = config_file_name
        self._filter_func = filter_section_func
        self._resolve_section_path = resolve_section_path

    def _include_section(self, section_path: str, base_path: str) -> bool:
        if self._filter_func:
            return self._filter_func(section_path, base_path)
        return True

    def get_section(self, cwd: str) -> dict[str, str]:
        """Gathers all relevant sections for a given path."""
        abs_path = os.path.abspath(cwd)
        all_sections = {}
        config_files = _get_config_file_hierarchy(abs_path, self._config_file_name)

        for config_file in reversed(config_files):
            if not os.path.exists(config_file):
                continue
            with open(config_file, "r") as f:
                lines = f.readlines()

            for section in _parse_config_file(config_file, lines):
                if section.name != self._section_name:
                    continue

                config_dir = os.path.dirname(section.config_file)
                key = (
                    os.path.abspath(os.path.join(config_dir, section.key))
                    if self._resolve_section_path
                    else section.key
                )

                if self._include_section(key, abs_path):
                    if key in all_sections:
                        all_sections[key] = f"{all_sections[key]}\n{section.content}"
                    else:
                        all_sections[key] = section.content

        return all_sections

    def add_to_section(self, content: str, key: str, cwd: str):
        """Adds content to a section block in the nearest configuration file."""
        abs_search_path = os.path.abspath(cwd)
        config_files = _get_config_file_hierarchy(
            abs_search_path, self._config_file_name
        )
        closest_config_file = (
            config_files[0]
            if config_files
            else os.path.join(os.path.expanduser("~"), self._config_file_name)
        )

        config_dir = os.path.dirname(closest_config_file)
        header_key = key
        if self._resolve_section_path and os.path.isabs(key):
            if key == config_dir:
                header_key = "."
            elif key.startswith(config_dir):
                header_key = f"./{os.path.relpath(key, config_dir)}"
        header = f"# {self._section_name}: {header_key}"
        new_content = content.strip()
        lines = []
        if os.path.exists(closest_config_file):
            with open(closest_config_file, "r") as f:
                lines = f.readlines()
        header_index = next(
            (i for i, line in enumerate(lines) if line.strip() == header), -1
        )
        if header_index != -1:
            insert_index = len(lines)
            for i in range(header_index + 1, len(lines)):
                if re.match(r"^# \w+:", lines[i].strip()):
                    insert_index = i
                    break
            if insert_index > 0 and lines[insert_index - 1].strip():
                lines.insert(insert_index, f"\n{new_content}\n")
            else:
                lines.insert(insert_index, f"{new_content}\n")
        else:
            if lines and lines[-1].strip():
                lines.append("\n\n")
            lines.append(f"{header}\n")
            lines.append(f"{new_content}\n")
        with open(closest_config_file, "w") as f:
            f.writelines(lines)

    def remove_from_section(self, content: str, key: str, cwd: str) -> bool:
        """Removes content from a section block in all relevant config files."""
        abs_search_path = os.path.abspath(cwd)
        config_files = _get_config_file_hierarchy(
            abs_search_path, self._config_file_name
        )
        content_to_remove = content.strip()
        was_removed = False
        for config_file_path in config_files:
            if not os.path.exists(config_file_path):
                continue
            with open(config_file_path, "r") as f:
                file_content = f.read()
            config_dir = os.path.dirname(config_file_path)
            header_key = key
            if self._resolve_section_path and os.path.isabs(key):
                if key == config_dir:
                    header_key = "."
                elif key.startswith(config_dir):
                    header_key = f"./{os.path.relpath(key, config_dir)}"
            header = f"# {self._section_name}: {header_key}"
            # Use regex to find the section content
            section_pattern = re.compile(
                rf"^{re.escape(header)}\n(.*?)(?=\n# \w+:|\Z)",
                re.DOTALL | re.MULTILINE,
            )
            match = section_pattern.search(file_content)
            if not match:
                continue

            section_content = match.group(1)
            # Remove the target content and handle surrounding newlines
            new_section_content = section_content.replace(content_to_remove, "")
            new_section_content = "\n".join(
                line for line in new_section_content.splitlines() if line.strip()
            )

            if new_section_content != section_content.strip():
                was_removed = True
                # Reconstruct the file content
                start = match.start(1)
                end = match.end(1)
                new_file_content = (
                    file_content[:start] + new_section_content + file_content[end:]
                )
                with open(config_file_path, "w") as f:
                    f.write(new_file_content)
        return was_removed
