from cucumber import Command, commandHandler, Scope


def _engine():
    from cucumber.engine import get_engine
    return get_engine()


def _render(text, **ph):
    if text is None:
        return ""
    for k, v in ph.items():
        text = text.replace("{" + k + "}", str(v))
    return text


async def _build_inventory(player, scope, config):
    entries = await player.inventory.all(scope=scope)
    if not entries:
        return config.message("profile_inventory_empty") or "  (empty)"
    line_fmt = config.message("profile_inventory_line") or "  • {name} ×{amount}"
    lines = []
    for entry in entries:
        name = entry.item.name if entry.item else "?"
        lines.append(_render(line_fmt, name=name, amount=entry.amount))
    return "\n".join(lines)


async def _build_cups(player, scope, config):
    cups = await player.stats.cups.get(scope=scope)
    if not cups:
        return config.message("profile_cups_empty") or "  (none)"
    return "\n".join(f"  🏆 {c}" for c in cups)


async def _build_clan(player, scope, config):
    clan = await player.clan.get(scope=scope)
    if clan is None:
        return config.message("profile_clan_none") or "None"
    return clan.name


async def _profile_placeholders(player, scope, config):
    with scope:
        size = await player.progress.size.get()
        juice = await player.progress.juice.get()
        max_juice = await player.progress.tank.max_juice()
        tank_level = await player.progress.tank.level()
        balls_level = await player.progress.balls.level()
        balls_progress = await player.progress.balls.progress_value()
        cups_count = await player.stats.cups.count(scope=scope)
        inventory = await _build_inventory(player, scope, config)
        cups = await _build_cups(player, scope, config)
        clan = await _build_clan(player, scope, config)
    return {
        "player_name": player.name or "?",
        "telegram_id": player.meta.telegram_id,
        "username": player.meta.username or "-",
        "size": int(size),
        "juice": int(juice),
        "tank_max_juice": int(max_juice or 0),
        "tank_level": int(tank_level),
        "balls_level": int(balls_level),
        "balls_progress": int(balls_progress),
        "cups_count": int(cups_count),
        "inventory": inventory,
        "cups": cups,
        "clan": clan,
    }


@commandHandler(
    name="profile",
    aliases=["prof", "me"],
    description="Show a player's profile",
    match="startswith",
)
class ProfileCommand(Command):

    async def execute(self, command):
        target = command.get_reply() or await command.arg_player(1) or command.sender
        if target is None:
            await command.reply("profile_not_found", to_user=True)
            return
        scope = Scope.group(command.chat_id)
        config = _engine().config
        ph = await _profile_placeholders(target, scope, config)
        text = config.message("profile_card", **ph)
        if text is None:
            text = "profile_card"
        await command.reply(text, to_user=True)
