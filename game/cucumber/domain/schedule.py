from datetime import datetime, timedelta, timezone

from cucumber.scope import resolve_scope


def _utcnow():
    return datetime.now(timezone.utc)


class ScheduleNamespace:
    def __init__(self, player, store):
        self.player = player
        self.store = store

    async def start(self, task_key, interval, scope=None, catchup="run_once"):
        scope = resolve_scope(scope)
        next_run = _utcnow() + timedelta(seconds=interval)
        await self.store.save_schedule(
            self.player.meta.telegram_id, scope, task_key,
            interval, next_run, catchup,
        )

    async def stop(self, task_key, scope=None):
        scope = resolve_scope(scope)
        await self.store.delete_schedule(
            self.player.meta.telegram_id, scope, task_key
        )

    async def next(self, task_key, scope=None):
        scope = resolve_scope(scope)
        st, sid = scope.type.value, scope.id
        from cucumber.persistence.models import ScheduleModel
        async with self.store.session_factory() as session:
            row = await session.get(
                ScheduleModel,
                (self.player.meta.telegram_id, st, sid, task_key),
            )
            return row.next_run_at if row else None

    async def is_active(self, task_key, scope=None):
        return await self.next(task_key, scope=scope) is not None
