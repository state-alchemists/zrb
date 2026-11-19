"""What one send-now attempt did, as a plain result type.

Lives in `util/` so an inert UI state mixin can name the result without
importing `zrb.llm.ui`. `ui/base/queue_delivery.py` re-exports these names for
its existing callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.llm.ui.base.message_queue import QueuedMessage


class DeliveryOutcome(str, Enum):
    """How a send-now attempt ended."""

    DELIVERED_EARLY = "delivered_early"
    DELIVERED_PARTIAL = "delivered_partial"
    FELL_BACK_TO_CANCEL = "fell_back_to_cancel"
    NOTHING_MOVED = "nothing_moved"
    WAITING_ON_DIALOG = "waiting_on_dialog"


@dataclass
class DeliveryReport:
    """What one send-now attempt did.

    `delivered_entries` are the messages handed to the live run, in queue
    order; `held` counts the entries still waiting in the queue.
    """

    outcome: DeliveryOutcome
    delivered_entries: "tuple[QueuedMessage, ...]" = ()
    held: int = 0

    @property
    def delivered(self) -> int:
        """How many messages this attempt handed to the live run."""
        return len(self.delivered_entries)
