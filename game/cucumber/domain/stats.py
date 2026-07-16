from cucumber.scope import resolve_scope
from cucumber.events.bus import EventBus
from cucumber.events.builtin import CupAddEvent, CupRemoveEvent


class Cups:
    def __init__(self, player, store):
        self.player = player
        self.store = store

    async def add(self, cup_name, scope=None):
        scope = resolve_scope(scope)
        event = CupAddEvent(self.player, cup_name, scope)
        await EventBus.call(event)
        if event.cancelled:
            return
        await self.store.add_cup(self.player.meta.telegram_id, scope, cup_name)

    async def remove(self, cup_name, scope=None):
        scope = resolve_scope(scope)
        event = CupRemoveEvent(self.player, cup_name, scope)
        await EventBus.call(event)
        if event.cancelled:
            return
        await self.store.remove_cup(self.player.meta.telegram_id, scope, cup_name)

    async def has(self, cup_name, scope=None):
        cups = await self.get(scope=scope)
        return cup_name in cups

    async def get(self, scope=None):
        scope = resolve_scope(scope)
        return await self.store.get_cups(self.player.meta.telegram_id, scope)

    async def count(self, scope=None):
        return len(await self.get(scope=scope))

    async def clear(self, scope=None):
        scope = resolve_scope(scope)
        cups = await self.get(scope=scope)
        for cup in cups:
            await self.store.remove_cup(self.player.meta.telegram_id, scope, cup)


class Stats:
    def __init__(self, player, store):
        self.player = player
        self.store = store
        self.cups = Cups(player, store)
