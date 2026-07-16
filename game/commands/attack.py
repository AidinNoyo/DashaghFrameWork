from cucumber import Command, commandHandler, EventBus, Scope
from events import AttackEvent


@commandHandler(
    name="attack",
    aliases=["atk", "hit"],
    description="Attack another player",
    cooldown=30,
    match="startswith",
)
class AttackCommand(Command):

    async def before(self, command):
        attacker = command.sender
        target = command.get_reply() or await command.arg_player(2)
        if not target:
            print("player_not_found")
            return command.cancel("player_not_found")
        if attacker == target:
            return command.cancel("cannot_attack_self")
        command.data["target"] = target

    async def execute(self, command):
        attacker = command.sender
        target = command.data["target"]
        amount = command.arg_int(1) or 0
        scope = (
            Scope.universal()
            if command.arg(3) == "x"
            else Scope.group(command.chat_id)
        )
        with scope:
            event = AttackEvent(
                attacker=attacker, target=target,
                amount=amount, damage=amount, scope=scope,
            )
            await EventBus.call(event)
            if event.cancelled:
                command.cancel(event.cancel_reason)
                return
            await target.progress.defense.take(event.damage)
            await attacker.progress.money.take(event.cost)
            command.data["attack_event"] = event

    async def after(self, command):
        event = command.data.get("attack_event")
        if not event:
            return
        await command.reply(
            "attack_success",
            damage=event.damage,
            target=event.target.name,
        )
