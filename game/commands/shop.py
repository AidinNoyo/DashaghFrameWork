from cucumber import Command, commandHandler, callbackHandler, Scope, EventBus
from cucumber.events.builtin import PurchaseEvent


def _engine():
    from cucumber.engine import get_engine
    return get_engine()


def _shop():
    return _engine().config.file("shop.yml")


def _msg(key):
    return _shop().get(f"messages.{key}", key)


def _btn(key):
    return _shop().get(f"buttons.{key}", key)


def _categories():
    cats = _shop().get("categories", {}) or {}
    return cats


def _cat_label(key):
    cat = _categories().get(key, {})
    return cat.get("label", key) if isinstance(cat, dict) else key


def _cat_desc(key):
    cat = _categories().get(key, {})
    return cat.get("description", "") if isinstance(cat, dict) else ""


async def _status_placeholders(player, scope):
    with scope:
        juice = await player.progress.juice.get()
        size = await player.progress.size.get()
        tank_level = await player.progress.tank.level()
        max_juice = await player.progress.tank.max_juice()
        balls_level = await player.progress.balls.level()
        balls_progress = await player.progress.balls.progress_value()
    return {
        "player_juice": int(juice),
        "player_size": int(size),
        "tank_level": int(tank_level),
        "tank_max_juice": int(max_juice or 0),
        "balls_level": int(balls_level),
        "balls_progress": int(balls_progress),
        "player_name": player.name,
    }


def _render(text, **ph):
    if text is None:
        return ""
    for k, v in ph.items():
        text = text.replace("{" + k + "}", str(v))
    return text


async def _render_status(text, player, scope, **extra):
    status = await _status_placeholders(player, scope)
    status.update(extra)
    return _render(text, **status)


def _category_buttons():
    buttons = [
        [(_cat_label(key), f"shop:cat:{key}")]
        for key in _categories().keys()
    ]
    return buttons


@commandHandler(
    name="shop",
    description="Open the shop",
    match="exact",
)
class ShopCommand(Command):

    async def execute(self, command):
        scope = Scope.group(command.chat_id)
        owner_id = command.sender.meta.telegram_id
        buttons = _category_buttons()
        buttons.append([(_btn("close"), f"shop:close:{owner_id}")])
        title = await _render_status(_shop().get("title", "Shop"),
                                     command.sender, scope)
        await command.reply(title, buttons=buttons, to_user=True)


@callbackHandler("shop")
async def shop_callback(ctx):
    parts = ctx.callback_data.split(":")
    action = parts[1]
    scope = Scope.group(ctx.chat_id)

    if action == "cat":
        category = parts[2]
        registry = _engine().registry
        items = [
            it for it in registry.all()
            if it.category == category and it.enabled
        ]
        item_fmt = _shop().get("item_format", "{name} — {price}💰")
        lines = []
        buttons = []
        for it in items:
            desc = it.get("description", "")
            line = _render(item_fmt, name=it.name, price=int(it.price),
                           description=desc)
            lines.append(line)
            buttons.append([(f"{it.name} — {int(it.price)}💰", f"shop:buy:{it.id}")])

        owner_id = parts[3] if len(parts) > 3 else ctx.sender.meta.telegram_id
        buttons.append([(_btn("back"), f"shop:home:{owner_id}")])

        if not items:
            body = await _render_status(_msg("empty"), ctx.sender, scope)
            await ctx.edit(body, buttons=buttons)
        else:
            body = await _render_status(
                _msg("pick_item"), ctx.sender, scope,
                category=_cat_label(category),
                description=_cat_desc(category),
                items="\n\n".join(lines),
            )
            await ctx.edit(body, buttons=buttons)

    elif action == "buy":
        item_id = parts[2]
        registry = _engine().registry
        item = registry.get(item_id)
        if item is None or not item.enabled:
            await ctx.popup("item_unavailable", alert=True)
            return
        with scope:
            juice = await ctx.sender.progress.juice.get()
            if juice < item.price:
                text = _render(_msg("not_enough"),
                               price=int(item.price), juice=int(juice))
                await ctx.popup(text, alert=True)
                return

            event = PurchaseEvent(ctx.sender, item, item.price, scope)
            await EventBus.call(event)
            if event.cancelled:
                await ctx.popup(event.cancel_reason or "item_unavailable", alert=True)
                return

            await ctx.sender.progress.juice.remove(event.price)
            await ctx.sender.inventory.add(item_id, 1)

            purchase_ctx = _PurchaseContext(ctx.sender, scope, item, event.price)
            await item.on_purchase(purchase_ctx)

        text = _render(_msg("bought"), item=item.name, price=int(event.price))
        await ctx.popup(text, alert=True)

    elif action == "home":
        owner_id = parts[2] if len(parts) > 2 else ctx.sender.meta.telegram_id
        buttons = _category_buttons()
        buttons.append([(_btn("close"), f"shop:close:{owner_id}")])
        title = await _render_status(_shop().get("title", "Shop"),
                                     ctx.sender, scope)
        await ctx.edit(title, buttons=buttons)

    elif action == "close":
        owner_id = int(parts[2]) if len(parts) > 2 else None
        if owner_id is not None and ctx.sender.meta.telegram_id != owner_id:
            await ctx.popup("not_owner", alert=True)
            return
        await ctx.delete()


class _PurchaseContext:
    def __init__(self, player, scope, item, price):
        self.player = player
        self.scope = scope
        self.item = item
        self.price = price
        self.message_key = None
        self.placeholders = {}
        self.metadata = {}
        self.cancelled = False

    def cancel(self):
        self.cancelled = True
