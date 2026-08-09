from collections.abc import Sequence

from zrb.task.any_task import AnyTask


def handle_rshift(
    left_task: AnyTask, right_operand: AnyTask | Sequence[AnyTask]
) -> AnyTask | Sequence[AnyTask]:
    """
    Implements the >> operator logic: left_task becomes an upstream for right_operand.
    Modifies the right_operand(s) by calling append_upstream.
    Returns the right_operand.
    """
    try:
        # Test the collection side, not `not isinstance(..., AnyTask)`: a stub
        # or MagicMock standing in for a task is not an `AnyTask` subclass and
        # must still take the single-task branch rather than be iterated.
        if isinstance(right_operand, Sequence):
            for task in right_operand:
                task.append_upstream(left_task)
        else:
            right_operand.append_upstream(left_task)
        return right_operand
    except Exception as e:
        raise ValueError(f"Invalid operation {left_task} >> {right_operand}: {e}")


def handle_lshift(
    left_task: AnyTask, right_operand: AnyTask | Sequence[AnyTask]
) -> AnyTask:
    """
    Implements the << operator logic: right_operand becomes an upstream for left_task.
    Modifies the left_task by calling append_upstream.
    Returns the left_task.
    """
    try:
        left_task.append_upstream(right_operand)
        return left_task
    except Exception as e:
        raise ValueError(f"Invalid operation {left_task} << {right_operand}: {e}")
