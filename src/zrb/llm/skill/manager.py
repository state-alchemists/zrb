import os
from pathlib import Path

import yaml

IGNORE_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    "htmlcov",
}


class Skill:
    def __init__(
        self,
        name: str,
        path: str,
        description: str,
        model_invocable: bool = True,
        user_invocable: bool = False,
    ):
        self.name = name
        self.path = path
        self.description = description
        self.model_invocable = model_invocable
        self.user_invocable = user_invocable


class SkillManager:
    def __init__(
        self,
        root_dir: str = ".",
        search_dirs: list[Path] | None = None,
        max_depth: int = 1,
    ):
        self._root_dir = root_dir
        self._search_dirs = search_dirs
        self._max_depth = max_depth
        self._skills: dict[str, Skill] = {}

    def scan(self) -> list[Skill]:
        self._skills = {}
        search_dirs = (
            self._search_dirs
            if self._search_dirs is not None
            else self._get_search_directories()
        )
        # Scan in order of precedence: global -> project
        # We iterate in normal order to allow later skills (project) to override earlier ones (global)
        for search_dir in search_dirs:
            self._scan_dir(search_dir, max_depth=self._max_depth)
        return list(self._skills.values())

    def _get_search_directories(self) -> list[Path]:
        search_dirs: list[Path] = []
        # 1. User global config (~/.claude/skills)
        try:
            home = Path.home()
            global_skills = home / ".claude" / "skills"
            if global_skills.exists() and global_skills.is_dir():
                search_dirs.append(global_skills)
        except Exception:
            pass

        # 2. Project directories (.claude/skills)
        # We look from Root -> ... -> CWD
        try:
            cwd = Path(self._root_dir).resolve()
            project_dirs = list(cwd.parents)[::-1] + [cwd]
            for project_dir in project_dirs:
                local_skills = project_dir / ".claude" / "skills"
                if local_skills.exists() and local_skills.is_dir():
                    search_dirs.append(local_skills)
        except Exception:
            pass

        # 3. The root_dir itself (recursive)
        search_dirs.append(Path(self._root_dir))

        return search_dirs

    def _scan_dir(self, directory: Path, max_depth: int):
        try:
            search_path = Path(directory).resolve()
            self._scan_dir_recursive(search_path, search_path, max_depth, 0)
        except Exception:
            pass

    def _scan_dir_recursive(
        self, base_dir: Path, current_dir: Path, max_depth: int, current_depth: int
    ):
        """Recursively scan directories with explicit depth control."""
        if current_depth > max_depth:
            return

        try:
            # List directory contents
            for item in current_dir.iterdir():
                if item.is_dir():
                    # Skip ignored directories
                    if item.name in IGNORE_DIRS:
                        continue
                    # Recursively scan subdirectory
                    self._scan_dir_recursive(
                        base_dir, item, max_depth, current_depth + 1
                    )
                elif item.is_file():
                    # Check for skill files
                    if item.name == "SKILL.md" or item.name.endswith(".skill.md"):
                        full_path = str(item)
                        rel_path = os.path.relpath(full_path, self._root_dir)
                        self._load_skill(rel_path, full_path)
        except (PermissionError, OSError):
            # Skip directories we can't access
            pass

    def _load_skill(self, rel_path: str, full_path: str):
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            default_name = os.path.basename(os.path.dirname(full_path))
            name = default_name
            description = "No description"
            model_invocable = True
            user_invocable = False
            is_name_resolved = False

            # 1. Parse YAML Frontmatter
            if content.startswith("---"):
                try:
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1])
                        if frontmatter:
                            if "name" in frontmatter:
                                name = frontmatter["name"]
                                is_name_resolved = True
                            description = frontmatter.get("description", description)
                            model_invocable = not frontmatter.get(
                                "disable-model-invocation", False
                            )
                            user_invocable = frontmatter.get("user-invocable", False)
                except Exception:
                    pass

            # 2. Fallback: Parse Markdown for Header 1
            if not is_name_resolved:
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("# "):
                        name = stripped[2:].strip()
                        is_name_resolved = True
                        break

            # Use name as key, handle duplicates by overriding (precedence handled by scan order)
            self._skills[name] = Skill(
                name=name,
                path=full_path,
                description=description,
                model_invocable=model_invocable,
                user_invocable=user_invocable,
            )

        except Exception:
            pass

    def get_skill(self, name: str) -> Skill | None:
        skill = self._skills.get(name)
        if not skill:
            # Try partial match or path match
            for s in self._skills.values():
                if s.name == name or s.path == name:
                    skill = s
                    break
        return skill

    def get_skill_content(self, name: str) -> str | None:
        skill = self.get_skill(name)
        if not skill:
            return None

        try:
            with open(skill.path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading skill file: {e}"


skill_manager = SkillManager()
