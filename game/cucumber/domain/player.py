from cucumber.domain.meta import Meta
from cucumber.domain.progress import Progress
from cucumber.domain.inventory import Inventory
from cucumber.domain.stats import Stats
from cucumber.domain.clan import ClanNamespace
from cucumber.domain.cooldowns import Cooldowns
from cucumber.domain.schedule import ScheduleNamespace
from cucumber.scope import Scope, ScopeType


class Player:
    def __init__(self, data, store, config, registry):
        self.meta = Meta(data)
        self.store = store
        self._config = config
        self.progress = Progress(self, store, config)
        self.inventory = Inventory(self, store, registry)
        self.stats = Stats(self, store)
        self.clan = ClanNamespace(self, store)
        self.cooldowns = Cooldowns(self, store)
        self.schedule = ScheduleNamespace(self, store)

    def _normalize_scope(self, scope):
        if isinstance(scope, ScopeType):
            if scope == ScopeType.UNIVERSAL:
                return Scope.universal()
            raise ValueError("GROUP scope requires an id; pass a Scope object.")
        return scope

    async def add_size(self, amount, scope=None):
        return await self.progress.size.add(amount, scope=self._normalize_scope(scope))

    async def add_juice(self, amount, scope=None):
        return await self.progress.juice.add(amount, scope=self._normalize_scope(scope))


    @property
    def name(self):
        return self.meta.first_name

    def __eq__(self, other):
        return isinstance(other, Player) and \
            self.meta.telegram_id == other.meta.telegram_id

    def __hash__(self):
        return hash(self.meta.telegram_id)


class PlayerManager:
    def __init__(self, store, config, registry):
        self.store = store
        self.config = config
        self.registry = registry

    async def get(self, telegram_id):
        data = await self.store.get_player(telegram_id)
        if data is None:
            return None
        return Player(data, self.store, self.config, self.registry)

    async def get_or_create(self, telegram_id, username=None, first_name=None,
                            last_name=None, language_code="en", is_bot=0):
        data = await self.store.get_player(telegram_id)
        if data is None:
            data = await self.store.upsert_player(
                telegram_id, username, first_name, last_name,
                language_code, is_bot,
            )
        return Player(data, self.store, self.config, self.registry)
