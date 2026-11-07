"""A UI driven by a queue of input events rather than a terminal loop."""

from zrb.llm.ui.event_driven.input import QueueBasedInput
from zrb.llm.ui.event_driven.ui import EventDrivenUI

__all__ = ["EventDrivenUI", "QueueBasedInput"]
