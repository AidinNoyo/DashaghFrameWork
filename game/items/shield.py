from cucumber import Item, item, eventHandler, Priority
from events import AttackEvent


@item("shield")
class ShieldItem(Item):
    name = "Shield"
    price = 250
    category = "combat"
    max_owned = 5

    @eventHandler(AttackEvent, priority=Priority.HIGHEST)
    async def on_attack(self, event):
        target = event.target
        if await target.inventory.has("shield"):
            await target.inventory.remove("shield", 1)
            event.cancel("🛡 Shield blocked the attack")
