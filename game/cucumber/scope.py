import contextvars
from enum import Enum
from typing import Optional

_ambient_scope = contextvars.ContextVar("ambient_scope", default=None)


class ScopeType(str, Enum):
    GROUP = "group"
    UNIVERSAL = "universal"


class ScopeNotProvidedError(Exception):
    pass


class Scope:
    GROUP = ScopeType.GROUP
    UNIVERSAL = ScopeType.UNIVERSAL

    def __init__(self, type: ScopeType, id: Optional[int] = None):
        if isinstance(type, str):
            type = ScopeType(type)
        self.type = type
        self.id = id if type == ScopeType.GROUP else None
        self._token = None

    @classmethod
    def group(cls, id: int) -> "Scope":
        return cls(ScopeType.GROUP, id)

    @classmethod
    def universal(cls) -> "Scope":
        return cls(ScopeType.UNIVERSAL)

    @property
    def key(self) -> str:
        if self.type == ScopeType.GROUP:
            return f"group:{self.id}"
        return "universal"

    def __enter__(self) -> "Scope":
        self._token = _ambient_scope.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._token is not None:
            _ambient_scope.reset(self._token)
            self._token = None
        return False

    def __eq__(self, other):
        return (
            isinstance(other, Scope)
            and self.type == other.type
            and self.id == other.id
        )

    def __hash__(self):
        return hash((self.type, self.id))

    def __repr__(self):
        if self.type == ScopeType.GROUP:
            return f"Scope(GROUP, {self.id})"
        return "Scope(UNIVERSAL)"


def resolve_scope(explicit: Optional[Scope] = None) -> Scope:
    if explicit is not None:
        return explicit
    ambient = _ambient_scope.get()
    if ambient is not None:
        return ambient
    raise ScopeNotProvidedError(
        "No scope provided and no ambient scope active. "
        "Pass scope=... or use a 'with Scope(...)' block."
    )


def current_scope() -> Optional[Scope]:
    return _ambient_scope.get()
