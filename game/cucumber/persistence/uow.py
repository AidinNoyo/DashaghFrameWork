import contextvars
from contextlib import asynccontextmanager

_current_uow = contextvars.ContextVar("current_uow", default=None)


class UnitOfWork:
    def __init__(self, store):
        self.store = store
        self._changes: dict = {}
        self._token = None

    def stage(self, key: str, record):
        self._changes[key] = record

    async def commit(self):
        for key, record in self._changes.items():
            await self.store._persist(key, record)
        self._changes.clear()

    def rollback(self):
        self._changes.clear()

    def __enter__(self):
        self._token = _current_uow.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._token:
            _current_uow.reset(self._token)
        return False


def current_uow():
    return _current_uow.get()


@asynccontextmanager
async def unit_of_work():
    from cucumber.engine import get_store
    store = get_store()
    uow = UnitOfWork(store)
    token = _current_uow.set(uow)
    try:
        yield uow
        await uow.commit()
    except Exception:
        uow.rollback()
        raise
    finally:
        _current_uow.reset(token)
