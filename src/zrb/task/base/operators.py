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
                task.append_upstream(left_task)
        else:
            right_operand.append_upstream(left_task)
        return right_operand
    except Exception as e:
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
        left_task.append_upstream(right_operand)
        return left_task
    except Exception as e:
        raise ValueError(f"Invalid operation {left_task} << {right_operand}: {e}")
