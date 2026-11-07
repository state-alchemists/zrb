"""A UI that buffers a child's output and forwards its approvals."""

from zrb.llm.ui.buffered.output import BufferedOutputMixin
from zrb.llm.ui.buffered.ui import BufferedUI

__all__ = ["BufferedOutputMixin", "BufferedUI"]
