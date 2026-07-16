import asyncio
import inspect
from enum import IntEnum
from typing import Callable, Type


class Priority(IntEnum):
    LOWEST = 0
    LOW = 1
    NORMAL = 2
    HIGH = 3
    HIGHEST = 4
    MONITOR = 5


class Event:
    def __init__(self):
        self.scope = None
        self.message_key = None
        self.placeholders = {}
        self.metadata = {}
        self.cancelled = False
        self.cancel_reason = None

    def cancel(self, reason=None):
        self.cancelled = True
        self.cancel_reason = reason


class _Listener:
    def __init__(self, func, priority, owner=None):
        self.func = func
        self.priority = priority
        self.owner = owner

    async def invoke(self, event):
        if self.owner is not None:
            result = self.func(self.owner, event)
        else:
            result = self.func(event)
        if inspect.isawaitable(result):
            await result


class _EventBus:
    def __init__(self):
        self._listeners: dict[Type, list[_Listener]] = {}
        self._pending_handlers: list[tuple] = []

    def register(self, event_type: Type, func: Callable, priority: Priority, owner=None):
        listener = _Listener(func, priority, owner)
        self._listeners.setdefault(event_type, []).append(listener)
        self._listeners[event_type].sort(key=lambda l: l.priority)

    def register_owner_handlers(self, owner):
        for attr_name in dir(owner.__class__):
            attr = getattr(owner.__class__, attr_name, None)
            handlers = getattr(attr, "_event_handlers", None)
            if handlers:
                for event_type, priority in handlers:
                    self.register(event_type, attr, priority, owner)

    async def call(self, event: Event):
        listeners = self._collect(type(event))
        for listener in listeners:
            if event.cancelled and listener.priority != Priority.MONITOR:
                continue
            await listener.invoke(event)
        return event

    def _collect(self, event_type: Type) -> list[_Listener]:
        result = []
        for registered_type, listeners in self._listeners.items():
            if issubclass(event_type, registered_type):
                result.extend(listeners)
        result.sort(key=lambda l: l.priority)
        return result

    def clear(self):
        self._listeners.clear()


EventBus = _EventBus()


def eventHandler(event_type: Type, priority: Priority = Priority.NORMAL):
    def decorator(func):
        if not hasattr(func, "_event_handlers"):
            func._event_handlers = []
        func._event_handlers.append((event_type, priority))
        return func
    return decorator
