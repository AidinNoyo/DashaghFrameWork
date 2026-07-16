from datetime import datetime, timedelta, timezone

from cucumber.scope import resolve_scope
from cucumber.events.bus import EventBus
from cucumber.events.builtin import CooldownStartEvent, CooldownFinishEvent


def _utcnow():
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class Cooldown:
    def __init__(self, key, started_at, duration):
        self.key = key
        self.started_at = _aware(started_at)
        self.duration = duration

    @property
    def ends_at(self):
        return self.started_at + timedelta(seconds=self.duration)

    @property
    def remaining(self):
        delta = (self.ends_at - _utcnow()).total_seconds()
        return max(0, int(delta))

    @property
    def is_ready(self):
        return self.remaining <= 0


class Cooldowns:
    def __init__(self, player, store):
        self.player = player
        self.store = store

    async def start(self, key, duration, scope=None):
        scope = resolve_scope(scope)
        event = CooldownStartEvent(self.player, key, duration, scope)
        await EventBus.call(event)
        if event.cancelled:
            return
        await self.store.set_cooldown(
            self.player.meta.telegram_id, scope, key, _utcnow(), event.duration
        )

    async def get(self, key, scope=None):
        scope = resolve_scope(scope)
        data = await self.store.get_cooldown(
            self.player.meta.telegram_id, scope, key
        )
        if data is None:
            return None
        return Cooldown(data["key"], data["started_at"], data["duration"])

    async def is_ready(self, key, scope=None):
        cd = await self.get(key, scope=scope)
        return cd is None or cd.is_ready

    async def remaining(self, key, scope=None):
        cd = await self.get(key, scope=scope)
        return cd.remaining if cd else 0

    async def reset(self, key, scope=None):
        scope = resolve_scope(scope)
        cd = await self.get(key, scope=scope)
        if cd is None:
            return
        await self.store.set_cooldown(
            self.player.meta.telegram_id, scope, key, _utcnow(), cd.duration
        )

    async def extend(self, key, seconds, scope=None):
        scope = resolve_scope(scope)
        cd = await self.get(key, scope=scope)
        if cd is None:
            return
        await self.store.set_cooldown(
            self.player.meta.telegram_id, scope, key,
            cd.started_at, cd.duration + seconds,
        )

    async def reduce(self, key, seconds, scope=None):
        scope = resolve_scope(scope)
        cd = await self.get(key, scope=scope)
        if cd is None:
            return
        new_duration = max(0, cd.duration - seconds)
        await self.store.set_cooldown(
            self.player.meta.telegram_id, scope, key,
            cd.started_at, new_duration,
        )

    async def finish(self, key, scope=None):
        scope = resolve_scope(scope)
        await self.store.delete_cooldown(self.player.meta.telegram_id, scope, key)
        event = CooldownFinishEvent(self.player, key, scope)
        await EventBus.call(event)
