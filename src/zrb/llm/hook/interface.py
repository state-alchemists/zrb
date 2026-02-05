from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Optional

from zrb.llm.hook.types import HookEvent


@dataclass
class HookContext:
    event: HookEvent
    event_data: Any
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HookResult:
    success: bool = True
    output: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    modifications: Dict[str, Any] = field(default_factory=dict)
    should_stop: bool = False


HookCallable = Callable[[HookContext], Awaitable[HookResult]]
