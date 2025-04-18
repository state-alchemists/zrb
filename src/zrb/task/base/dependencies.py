from typing import TypeVar

from zrb.task.any_task import AnyTask

T = TypeVar("T", bound="AnyTask")


def get_dependency_list(task: AnyTask, attr_name: str) -> list[AnyTask]:
    """
    Safely retrieves a list of dependencies (upstreams, fallbacks, etc.)
    from a task attribute, handling None or single-task values.
    """
    dependencies = getattr(task, attr_name, None)
    if dependencies is None:
        return []
    elif isinstance(dependencies, list):
        # Ensure all elements are AnyTask (or compatible) if needed,
        # but for now, assume the list contains tasks.
        return dependencies
    # Assume it's a single AnyTask instance
    return [dependencies]


def append_dependency(
    task: T, attr_name: str, dependencies_to_add: AnyTask | list[AnyTask]
) -> None:
    """
    Appends one or more dependencies to the specified attribute list of a task,
    ensuring the attribute becomes a list and avoiding duplicates.

    Modifies the attribute on the task object directly.
    """
    # Retrieve the current list, handling None or single item cases
    current_deps_list = getattr(task, attr_name, None)
    if current_deps_list is None:
        current_deps_list = []
    elif not isinstance(current_deps_list, list):
        current_deps_list = [current_deps_list]
    else:
        # Create a copy to avoid modifying the original list if no changes occur
        current_deps_list = list(current_deps_list)

    if isinstance(dependencies_to_add, list):
        new_deps = dependencies_to_add
    else:
        new_deps = [dependencies_to_add]  # Ensure it's always a list

    added = False
    for dep in new_deps:
        # Check for existence before appending
        if dep not in current_deps_list:
            current_deps_list.append(dep)
            added = True

    # Update the attribute on the task object only if changes were made
    if added:
        setattr(task, attr_name, current_deps_list)
