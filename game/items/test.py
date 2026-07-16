from cucumber import Item, item, eventHandler
from cucumber.events.builtin import PurchaseEvent


@item("test")
class TestItem(Item):

    async def on_purchase(self, context):
        print(f"{context.player.name} bought {context.item.name} for {context.price}")

    @eventHandler(PurchaseEvent)
    async def on_any_purchase(self, event):
        pass
