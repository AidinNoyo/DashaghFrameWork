from cucumber import eventHandler, Priority, config

from events import JuiceGainEvent


def _cfg():
    return config.file("juice.yml").get("juice_generator", {}) or {}


class JuiceBonus:

    @eventHandler(JuiceGainEvent, priority=Priority.HIGH)
    async def apply_balls_bonus(self, event):
        table = _cfg().get("balls_bonus", {}) or {}

        level = int(await event.player.progress.balls.level(scope=event.scope))

        bonus = table.get(level)
        if bonus is None:
            bonus = table.get(str(level))

        if bonus is not None:
            event.amount = bonus

        print(f"[JUICE_BONUS] balls_lvl={level} -> amount={event.amount}")
