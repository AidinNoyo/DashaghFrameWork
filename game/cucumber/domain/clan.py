from cucumber.scope import resolve_scope
from cucumber.events.bus import EventBus
from cucumber.events.builtin import ClanJoinEvent, ClanLeaveEvent


class Clan:
    def __init__(self, data, store):
        self._data = data
        self.store = store

    @property
    def id(self):
        return self._data["clan_id"]

    @property
    def name(self):
        return self._data["name"]

    @property
    def level(self):
        return self._data["level"]

    @property
    def score(self):
        return self._data["score"]

    @property
    def leader_id(self):
        return self._data["leader_id"]

    async def members(self):
        return await self.store.clan_members(self.id)


class ClanNamespace:
    def __init__(self, player, store):
        self.player = player
        self.store = store

    async def join(self, clan_name, scope=None):
        scope = resolve_scope(scope)
        event = ClanJoinEvent(self.player, clan_name, scope)
        await EventBus.call(event)
        if event.cancelled:
            return None
        return await self.store.join_clan(
            self.player.meta.telegram_id, scope, clan_name
        )

    async def leave(self, scope=None):
        scope = resolve_scope(scope)
        membership = await self.store.get_clan_membership(
            self.player.meta.telegram_id, scope
        )
        if membership is None:
            return
        event = ClanLeaveEvent(self.player, membership["name"], scope)
        await EventBus.call(event)
        if event.cancelled:
            return
        await self.store.leave_clan(self.player.meta.telegram_id, scope)

    async def rank(self, scope=None):
        scope = resolve_scope(scope)
        membership = await self.store.get_clan_membership(
            self.player.meta.telegram_id, scope
        )
        return membership["role"] if membership else None

    async def clan_rank(self, scope=None):
        scope = resolve_scope(scope)
        membership = await self.store.get_clan_membership(
            self.player.meta.telegram_id, scope
        )
        if membership is None:
            return None
        return await self.store.clan_rank(membership["clan_id"])

    async def get(self, scope=None):
        scope = resolve_scope(scope)
        membership = await self.store.get_clan_membership(
            self.player.meta.telegram_id, scope
        )
        if membership is None:
            return None
        return Clan(membership, self.store)

    async def is_member(self, scope=None):
        return await self.get(scope=scope) is not None
