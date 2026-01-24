import os

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
}


class Skill:
    def __init__(self, name: str, path: str, description: str):
        self.name = name
        self.path = path
        self.description = description


class SkillManager:
    def __init__(self, root_dir: str = "."):
        self.root_dir = root_dir
        self._skills: dict[str, Skill] = {}

    def scan(self) -> list[Skill]:
        self._skills = {}
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                if file == "SKILL.md" or file.endswith(".skill.md"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.root_dir)
                    self._load_skill(rel_path, full_path)

        return list(self._skills.values())

    def _load_skill(self, rel_path: str, full_path: str):
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            name = os.path.basename(os.path.dirname(full_path))
            description = "No description"

            # Parse Markdown for Header 1
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("# "):
                    name = stripped[2:].strip()
                    break

            # Use name as key, handle duplicates
            key = name
            if key in self._skills:
                key = f"{name} ({rel_path})"

            self._skills[key] = Skill(name=key, path=rel_path, description=description)

        except Exception:
            pass

    def get_skill_content(self, name: str) -> str | None:
        skill = self._skills.get(name)
        if not skill:
            # Try partial match or path match
            for s in self._skills.values():
                if s.name == name or s.path == name:
                    skill = s
                    break

        if not skill:
            return None

        try:
            with open(skill.path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading skill file: {e}"


skill_manager = SkillManager()
