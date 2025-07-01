import datetime

from pydantic import BaseModel, Field, model_validator


class TodoTaskModel(BaseModel):
    priority: str | None = Field("D", pattern=r"^[A-Z]$")  # Priority like A, B, ...
    completed: bool = False  # True if completed, False otherwise
    description: str  # Main task description
    projects: list[str] = []  # List of projects (e.g., +Project)
    contexts: list[str] = []  # List of contexts (e.g., @Context)
    keyval: dict[str, str] = {}  # Special key (e.g., due:2016-05-30)
    creation_date: datetime.date | None = None  # Creation date
    completion_date: datetime.date | None = None  # Completion date

    @model_validator(mode="before")
    def validate_dates(cls, values):
        completion_date = values.get("completion_date")
        creation_date = values.get("creation_date")
        if completion_date and not creation_date:
            raise ValueError(
                "creation_date must be specified if completion_date is set."
            )
        return values

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
