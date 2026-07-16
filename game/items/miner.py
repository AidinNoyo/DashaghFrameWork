from cucumber import Item, item, every


@item("miner")
class Miner(Item):
    name = "Gold Miner"
    price = 1000
    category = "steal"

    @every(seconds=10, global_tick=True)
    async def mine(self, context):
        payout = 50 * context.count
        await context.player.progress.juice.add(payout, scope=context.scope)
        print(f"[MINER] {context.player.name} x{context.count} +{payout} juice @ {context.scope.key}")

    async def on_purchase(self, context):
        pass
