from typing import Dict, List, Optional
from fastapi import HTTPException
from .models import Project, Task, TaskStatus


def filter_tasks(
    tasks_list: List[Task],
    status: Optional[TaskStatus] = None,
    priority: Optional[int] = None,
    assigned_to: Optional[str] = None,
) -> List[Task]:
    """Filter tasks by status, priority, and/or assigned_to."""
    filtered = tasks_list
    if status is not None:
        filtered = [t for t in filtered if t.status == status]
    if priority is not None:
        filtered = [t for t in filtered if t.priority == priority]
    if assigned_to is not None:
        filtered = [t for t in filtered if t.assigned_to == assigned_to]
    return filtered


def paginate_tasks(tasks_list: List[Task], page: int = 1, page_size: int = 20) -> List[Task]:
    """Apply pagination to a task list."""
    start = (page - 1) * page_size
    end = start + page_size
    return tasks_list[start:end]


def find_task_by_id(task_id: int) -> Optional[Task]:
    """Find a task by ID, returns None if not found."""
    for task in tasks:
        if task.id == task_id:
            return task
    return None


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


def get_next_task_id() -> int:
    """Return the next available task ID."""
    if not tasks:
        return 1
    return max(task.id for task in tasks) + 1


def create_task(task: Task) -> Task:
    """Assign an ID and add a task to the list."""
    task.id = get_next_task_id()
    tasks.append(task)
    return task
