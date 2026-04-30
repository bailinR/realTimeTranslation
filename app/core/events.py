from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable


Callback = Callable[[Any], None]


class EventBus:
    def __init__(self) -> None:
        self._listeners: dict[str, list[Callback]] = defaultdict(list)

    def subscribe(self, event_name: str, callback: Callback) -> None:
        self._listeners[event_name].append(callback)

    def publish(self, event_name: str, payload: Any) -> None:
        for callback in self._listeners.get(event_name, []):
            callback(payload)
