from typing import Dict, List
from .models import Project, Task, TaskStatus

# Track the maximum task ID for auto-generating new IDs
MAX_TASK_ID: int = max((t.id for t in tasks), default=0)

projects: List[Project] = [
    Project(id=1, name="Alpha", owner="alice"),
    Project(id=2, name="Beta", owner="bob"),
]

tasks: List[Task] = [
    Task(id=1, title="Design schema", status=TaskStatus.done, priority=5, project_id=1, assigned_to="alice"),
    Task(id=2, title="Implement API", status=TaskStatus.in_progress, priority=4, project_id=1, assigned_to="bob"),
    Task(id=3, title="Write tests", status=TaskStatus.todo, priority=3, project_id=1),
    Task(id=4, title="Deploy to staging", status=TaskStatus.todo, priority=2, project_id=2, assigned_to="alice"),
]

VALID_API_KEYS: Dict[str, str] = {
    "dev-key-alice": "alice",
    "dev-key-bob": "bob",
}


def generate_task_id() -> int:
    """Generate a unique integer task ID."""
    global MAX_TASK_ID
    MAX_TASK_ID += 1
    return MAX_TASK_ID
