from cucumber import Event


class AttackEvent(Event):
    def __init__(self, attacker, target, amount, damage, scope):
        super().__init__()
        self.attacker = attacker
        self.target = target
        self.original_amount = amount
        self.damage = damage
        self.cost = amount
        self.scope = scope
from cucumber import Event


class JuiceGainEvent(Event):
    def __init__(self, player, amount, scope, source="generator"):
        super().__init__()
        self.player = player
        self.amount = amount
        self.base_amount = amount
        self.scope = scope
        self.source = source
