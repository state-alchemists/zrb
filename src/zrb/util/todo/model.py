import datetime
import re


class TodoTaskModel:
    def __init__(
        self,
        description: str,
        priority: str | None = "D",
        completed: bool = False,
        projects: list[str] | None = None,
        contexts: list[str] | None = None,
        keyval: dict[str, str] | None = None,
        creation_date: datetime.date | None = None,
        completion_date: datetime.date | None = None,
    ):
        if priority is not None and not re.match(r"^[A-Z]$", priority):
            raise ValueError("Invalid priority format")
        if completion_date and not creation_date:
            raise ValueError(
                "creation_date must be specified if completion_date is set."
            )
        self.priority = priority
        self.completed = completed
        self.description = description
        self.projects = projects if projects is not None else []
        self.contexts = contexts if contexts is not None else []
        self.keyval = keyval if keyval is not None else {}
        self.creation_date = creation_date
        self.completion_date = completion_date

    def get_additional_info_length(self):
        """
        Calculate the length of the additional information string (projects, contexts, keyval).

        Returns:
            int: The length of the combined additional information string.
        """
        results = []
        for project in self.projects:
            results.append(f"@{project}")
        for context in self.contexts:
            results.append(f"+{context}")
        for key, val in self.keyval.items():
            results.append(f"{key}:{val}")
        return len(", ".join(results))
