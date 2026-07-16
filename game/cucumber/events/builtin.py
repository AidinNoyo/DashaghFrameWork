from cucumber.events.bus import Event


class StatChangeEvent(Event):
    def __init__(self, player, stat, amount, operation, scope):
        super().__init__()
        self.player = player
        self.stat = stat
        self.amount = amount
        self.operation = operation
        self.scope = scope


class MoneyChangeEvent(StatChangeEvent):
    pass


class XpChangeEvent(StatChangeEvent):
    pass


class EnergyChangeEvent(StatChangeEvent):
    pass


class LevelUpEvent(Event):
    def __init__(self, player, old_level, new_level, scope):
        super().__init__()
        self.player = player
        self.old_level = old_level
        self.new_level = new_level
        self.scope = scope


class InventoryAddEvent(Event):
    def __init__(self, player, item_id, amount, scope):
        super().__init__()
        self.player = player
        self.item_id = item_id
        self.amount = amount
        self.scope = scope


class InventoryRemoveEvent(Event):
    def __init__(self, player, item_id, amount, scope):
        super().__init__()
        self.player = player
        self.item_id = item_id
        self.amount = amount
        self.scope = scope


class InventoryUseEvent(Event):
    def __init__(self, player, item_id, scope):
        super().__init__()
        self.player = player
        self.item_id = item_id
        self.scope = scope


class InventoryClearEvent(Event):
    def __init__(self, player, scope):
        super().__init__()
        self.player = player
        self.scope = scope


class CupAddEvent(Event):
    def __init__(self, player, cup_name, scope):
        super().__init__()
        self.player = player
        self.cup_name = cup_name
        self.scope = scope


class CupRemoveEvent(Event):
    def __init__(self, player, cup_name, scope):
        super().__init__()
        self.player = player
        self.cup_name = cup_name
        self.scope = scope


class ClanJoinEvent(Event):
    def __init__(self, player, clan_name, scope):
        super().__init__()
        self.player = player
        self.clan_name = clan_name
        self.scope = scope


class ClanLeaveEvent(Event):
    def __init__(self, player, clan_name, scope):
        super().__init__()
        self.player = player
        self.clan_name = clan_name
        self.scope = scope


class ClanRankChangeEvent(Event):
    def __init__(self, player, old_rank, new_rank, scope):
        super().__init__()
        self.player = player
        self.old_rank = old_rank
        self.new_rank = new_rank
        self.scope = scope


class CooldownStartEvent(Event):
    def __init__(self, player, key, duration, scope):
        super().__init__()
        self.player = player
        self.key = key
        self.duration = duration
        self.scope = scope


class CooldownFinishEvent(Event):
    def __init__(self, player, key, scope):
        super().__init__()
        self.player = player
        self.key = key
        self.scope = scope


class PurchaseEvent(Event):
    def __init__(self, player, item, price, scope):
        super().__init__()
        self.player = player
        self.item = item
        self.price = price
        self.scope = scope


class ItemRemoveEvent(Event):
    def __init__(self, player, item_id, scope):
        super().__init__()
        self.player = player
        self.item_id = item_id
        self.scope = scope


class ItemUseEvent(Event):
    def __init__(self, player, item_id, scope):
        super().__init__()
        self.player = player
        self.item_id = item_id
        self.scope = scope


class ScheduleTickEvent(Event):
    def __init__(self, player, task_key, payout, scope, missed):
        super().__init__()
        self.player = player
        self.task_key = task_key
        self.payout = payout
        self.scope = scope
        self.missed = missed


class ScheduleMissedEvent(Event):
    def __init__(self, player, task_key, missed, scope):
        super().__init__()
        self.player = player
        self.task_key = task_key
        self.missed = missed
        self.scope = scope
