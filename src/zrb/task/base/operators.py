"""`>>`/`<<` operator handling for `BaseTask`.

Composed into `BaseTask` as `self._base_operators`.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING

from zrb.task.any_task import AnyTask

if TYPE_CHECKING:
    from zrb.task.base.base_task import BaseTask


class BaseTaskOperators:
    """Implements the `>>`/`<<` upstream-wiring operators for `BaseTask`."""

    def __init__(self, task: "BaseTask") -> None:
        self._task = task

    def handle_rshift(
        self, right_operand: AnyTask | Sequence[AnyTask]
    ) -> AnyTask | Sequence[AnyTask]:
        """`self >> right_operand`: make this task an upstream of it; return it."""
        left_task = self._task
        try:
            # Check `Sequence`, not `AnyTask`, so duck-typed tasks count as one.
            if isinstance(right_operand, Sequence):
                for task in right_operand:
                    task.append_upstream(left_task)
            else:
                right_operand.append_upstream(left_task)
            return right_operand
        except Exception as e:
            raise ValueError(f"Invalid operation {left_task} >> {right_operand}: {e}")

    def handle_lshift(self, right_operand: AnyTask | Sequence[AnyTask]) -> AnyTask:
        """`self << right_operand`: make it an upstream of this task; return self."""
        left_task = self._task
        try:
            left_task.append_upstream(right_operand)
            return left_task
        except Exception as e:
            raise ValueError(f"Invalid operation {left_task} << {right_operand}: {e}")
