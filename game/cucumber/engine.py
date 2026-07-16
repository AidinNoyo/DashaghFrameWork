import asyncio

from cucumber.config.manager import config as config_manager
from cucumber.persistence.cache import CacheLayer
from cucumber.persistence.store import DataStore
from cucumber.items.registry import ItemRegistry
from cucumber.commands.router import Router
from cucumber.scheduler.loop import Scheduler
from cucumber.domain.player import PlayerManager

_STORE = None
_ENGINE = None

def get_store():
    return _STORE
def get_engine():
    return _ENGINE

class CucumberEngine:
    def __init__(self, config_dir, database_url=None, cache=None):
        global _STORE
        self.config = config_manager
        self.config.load(config_dir)
        global _STORE, _ENGINE
        _ENGINE = self
        from cucumber.scheduler.global_tick import GlobalTickRunner
        self.global_tick = GlobalTickRunner(self, tick_interval=1.0)

        db_url = database_url or self.config.get("database.url")
        cache_url = cache or self.config.get("cache.url")
        ttl = self.config.get("cache.ttl", 300)
        write_behind = self.config.get("cache.write_behind", True)
        flush_interval = self.config.get("cache.flush_interval", 5)

        cache_layer = CacheLayer(
            redis_url=cache_url if str(cache_url).startswith("redis") else None,
            ttl=ttl, write_behind=write_behind, flush_interval=flush_interval,
        )
        self.store = DataStore(db_url, cache_layer)
        _STORE = self.store

        self.registry = ItemRegistry(self.config)
        self.players = PlayerManager(self.store, self.config, self.registry)
        self.adapter = None
        self.router = None
        self.scheduler = None

    def load_commands(self, package):
        _import_package(package)

    def load_items(self, package):
        _import_package(package)

    def use(self, adapter):
        self.adapter = adapter
        adapter.bind(self)
        return self

    async def start(self):
        await self.store.init()
        self.registry.load()
        self._register_global_ticks()
        self.router = Router(self.config, self.players, self.adapter)
        self.router.load()
        self.players.get_by_username = self._get_by_username
        self.scheduler = Scheduler(self.store, self.registry, self.players)
        self.scheduler.index_methods()
        self.scheduler.start()
        await self.global_tick.start()

    def _register_global_ticks(self):
        from cucumber.scheduler.registry import collect_schedules
        from cucumber.scheduler.global_tick import GlobalTickEntry
        for instance in self.registry.all():
            item_id = getattr(instance, "id", None) or getattr(instance, "item_id", None)
            if item_id is None:
                continue
            normal, globals_ = collect_schedules(instance, item_id)
            for g in globals_:
                self.global_tick.register(GlobalTickEntry(
                    task_key=g["task_key"],
                    item_id=g["item_id"],
                    method=g["method"],
                    interval=g["interval"],
                    engine=self,
                ))

    async def _get_by_username(self, username):
        return None

    def run(self):
        if self.adapter is None:
            raise RuntimeError("No adapter attached. Call engine.use(adapter).")
        self.adapter.run()
    def scope_from_key(self, key):
        from cucumber.scope import Scope
        if key == "universal":
            return Scope.universal()
        _, gid = key.split(":", 1)
        return Scope.group(int(gid))

    def build_task_context(self, player, scope, item, count, task_key):
        from cucumber.scheduler.loop import _TaskContext
        return _TaskContext(
            player=player,
            scope=scope,
            item=item,
            count=count,
            task_key=task_key,
        )


def _import_package(package):
    import importlib
    import pkgutil

    module = importlib.import_module(package)
    if hasattr(module, "__path__"):
        for _, name, _ in pkgutil.iter_modules(module.__path__):
            importlib.import_module(f"{package}.{name}")
