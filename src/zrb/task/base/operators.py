# No specific imports needed from typing for these changes
from zrb.task.any_task import AnyTask


def handle_rshift(
    left_task: AnyTask, right_operand: AnyTask | list[AnyTask]
) -> AnyTask | list[AnyTask]:
    """
    Implements the >> operator logic: left_task becomes an upstream for right_operand.
    Modifies the right_operand(s) by calling append_upstream.
    Returns the right_operand.
    """
    try:
        if isinstance(right_operand, list):
            for task in right_operand:
                # Assuming append_upstream exists and handles duplicates
                task.append_upstream(left_task)
        else:
            # Assuming right_operand is a single AnyTask
            right_operand.append_upstream(left_task)
        return right_operand
    except Exception as e:
        # Catch potential errors during append_upstream or type issues
        raise ValueError(f"Invalid operation {left_task} >> {right_operand}: {e}")


def handle_lshift(
    left_task: AnyTask, right_operand: AnyTask | list[AnyTask]
) -> AnyTask:
    """
    Implements the << operator logic: right_operand becomes an upstream for left_task.
    Modifies the left_task by calling append_upstream.
    Returns the left_task.
    """
    try:
        # Assuming append_upstream exists and handles single or list input
        left_task.append_upstream(right_operand)
        return left_task
    except Exception as e:
        # Catch potential errors during append_upstream or type issues
        raise ValueError(f"Invalid operation {left_task} << {right_operand}: {e}")
