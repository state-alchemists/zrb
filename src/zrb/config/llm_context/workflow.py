class LLMWorkflow:
    def __init__(
        self, name: str, path: str, content: str, description: str | None = None
    ):
        self._name = name
        self._path = path

        # Extract YAML metadata and clean content
        (
            extracted_description,
            cleaned_content,
        ) = self._extract_yaml_metadata_and_clean_content(content)
        self._content = cleaned_content

        # Use provided description or extracted one
        self._description = (
            description if description is not None else extracted_description
        )

    def _extract_yaml_metadata_and_clean_content(
        self, content: str
    ) -> tuple[str | None, str]:
        """Extract YAML metadata and clean content.

        Looks for YAML metadata between --- lines, extracts the 'description' field,
        and returns the content without the YAML metadata.
        """
        import re

        import yaml

        # Pattern to match YAML metadata between --- delimiters
        yaml_pattern = r"^---\s*\n(.*?)\n---\s*\n"
        match = re.search(yaml_pattern, content, re.DOTALL | re.MULTILINE)

        if match:
            yaml_content = match.group(1)
            try:
                metadata = yaml.safe_load(yaml_content)
                description = (
                    metadata.get("description") if isinstance(metadata, dict) else None
                )
                # Remove the YAML metadata from content
                cleaned_content = re.sub(
                    yaml_pattern, "", content, count=1, flags=re.DOTALL | re.MULTILINE
                )
                return description, cleaned_content.strip()
            except yaml.YAMLError:
                # If YAML parsing fails, return original content
                pass

        # No YAML metadata found, return original content
        return None, content

    @property
    def name(self) -> str:
        return self._name

    @property
    def path(self) -> str:
        return self._path

    @property
    def content(self) -> str:
        return self._content

    @property
    def description(self) -> str:
        if self._description is not None:
            return self._description
        if len(self._content) > 1000:
            non_empty_lines = [
                line for line in self._content.split("\n") if line.strip() != ""
            ]
            first_non_empty_line = (
                non_empty_lines[0] if len(non_empty_lines) > 0 else ""
            )
            if len(first_non_empty_line) > 200:
                return first_non_empty_line[:200] + "... (more)"
            return first_non_empty_line
        return self._content
