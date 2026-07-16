from cucumber.scope import resolve_scope
from cucumber.events.bus import EventBus
from cucumber.events.builtin import (
    InventoryAddEvent, InventoryRemoveEvent,
    InventoryUseEvent, InventoryClearEvent,
)


class InventoryEntry:
    def __init__(self, item, amount, acquired_at, scope):
        self.item = item
        self.amount = amount
        self.acquired_at = acquired_at
        self.scope = scope


class Inventory:
    def __init__(self, player, store, registry):
        self.player = player
        self.store = store
        self.registry = registry

    def _item_id(self, item):
        if hasattr(item, "id"):
            return item.id
        return str(item)

    async def add(self, item, amount=1, scope=None):
        scope = resolve_scope(scope)
        item_id = self._item_id(item)
        event = InventoryAddEvent(self.player, item_id, amount, scope)
        await EventBus.call(event)
        if event.cancelled:
            return
        entry = await self.store.get_inventory_entry(
            self.player.meta.telegram_id, scope, item_id
        )
        current = entry["amount"] if entry else 0
        item_obj = self.registry.get(item_id)
        max_owned = getattr(item_obj, "max_owned", None) if item_obj else None
        new_amount = current + event.amount
        if max_owned is not None:
            new_amount = min(new_amount, max_owned)
        await self.store.set_inventory_entry(
            self.player.meta.telegram_id, scope, item_id, new_amount
        )

    async def remove(self, item, amount=1, scope=None):
        scope = resolve_scope(scope)
        item_id = self._item_id(item)
        event = InventoryRemoveEvent(self.player, item_id, amount, scope)
        await EventBus.call(event)
        if event.cancelled:
            return
        entry = await self.store.get_inventory_entry(
            self.player.meta.telegram_id, scope, item_id
        )
        current = entry["amount"] if entry else 0
        new_amount = max(0, current - event.amount)
        await self.store.set_inventory_entry(
            self.player.meta.telegram_id, scope, item_id, new_amount
        )
        item_obj = self.registry.get(item_id)
        if item_obj is not None:
            ctx = _ItemContext(self.player, scope, item_obj)
            await item_obj.on_remove(ctx)

    async def has(self, item, scope=None):
        return await self.count(item, scope=scope) > 0

    async def count(self, item, scope=None):
        scope = resolve_scope(scope)
        item_id = self._item_id(item)
        entry = await self.store.get_inventory_entry(
            self.player.meta.telegram_id, scope, item_id
        )
        return entry["amount"] if entry else 0

    async def get(self, item, scope=None):
        scope = resolve_scope(scope)
        item_id = self._item_id(item)
        entry = await self.store.get_inventory_entry(
            self.player.meta.telegram_id, scope, item_id
        )
        if not entry:
            return None
        return InventoryEntry(
            self.registry.get(item_id), entry["amount"],
            entry["acquired_at"], scope,
        )

    async def all(self, scope=None):
        scope = resolve_scope(scope)
        rows = await self.store.all_inventory(self.player.meta.telegram_id, scope)
        return [
            InventoryEntry(self.registry.get(r["item_id"]), r["amount"],
                           r["acquired_at"], scope)
            for r in rows
        ]

    async def clear(self, scope=None):
        scope = resolve_scope(scope)
        event = InventoryClearEvent(self.player, scope)
        await EventBus.call(event)
        if event.cancelled:
            return
        await self.store.clear_inventory(self.player.meta.telegram_id, scope)

    async def use(self, item, scope=None):
        scope = resolve_scope(scope)
        item_id = self._item_id(item)
        if await self.count(item_id, scope=scope) <= 0:
            return False
        event = InventoryUseEvent(self.player, item_id, scope)
        await EventBus.call(event)
        if event.cancelled:
            return False
        item_obj = self.registry.get(item_id)
        if item_obj is not None:
            ctx = _ItemContext(self.player, scope, item_obj)
            await item_obj.on_use(ctx)
        return True


class _ItemContext:
    def __init__(self, player, scope, item):
        self.player = player
        self.scope = scope
        self.item = item
        self.message_key = None
        self.placeholders = {}
        self.metadata = {}
        self.cancelled = False

    def cancel(self):
        self.cancelled = True
