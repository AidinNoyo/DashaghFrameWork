from cucumber.scope import resolve_scope
from cucumber.events.bus import EventBus
from cucumber.events.builtin import StatChangeEvent, LevelUpEvent


class Stat:
    def __init__(self, player, name, store, config, max_provider=None):
        self.player = player
        self.name = name
        self.store = store
        self.config = config or {}
        self._max_provider = max_provider

    def _default(self):
        return float(self.config.get("default", 0))

    def _min(self):
        return self.config.get("min")

    async def _max(self, scope):
        if self._max_provider is not None:
            return await self._max_provider(scope)
        return self.config.get("max")

    async def get(self, scope=None):
        scope = resolve_scope(scope)
        value = await self.store.get_progress(
            self.player.meta.telegram_id, scope, self.name
        )
        if value is None:
            return self._default()
        return value

    async def set(self, value, scope=None):
        scope = resolve_scope(scope)
        mn = self._min()
        mx = await self._max(scope)
        if mn is not None:
            value = max(mn, value)
        if mx is not None:
            value = min(mx, value)
        await self.store.set_progress(
            self.player.meta.telegram_id, scope, self.name, value
        )
        return value

    async def add(self, amount, scope=None):
        scope = resolve_scope(scope)
        event = StatChangeEvent(self.player, self.name, amount, "add", scope)
        await EventBus.call(event)
        if event.cancelled:
            return await self.get(scope=scope)
        current = await self.get(scope=scope)
        return await self.set(current + event.amount, scope=scope)

    async def give(self, amount, scope=None):
        return await self.add(amount, scope=scope)

    async def remove(self, amount, scope=None):
        scope = resolve_scope(scope)
        current = await self.get(scope=scope)
        strict = self.config.get("strict", False)
        if strict and current < amount:
            raise ValueError(
                f"Not enough {self.name}: have {current}, need {amount}"
            )
        event = StatChangeEvent(self.player, self.name, amount, "remove", scope)
        await EventBus.call(event)
        if event.cancelled:
            return current
        return await self.set(current - event.amount, scope=scope)

    async def take(self, amount, scope=None):
        return await self.remove(amount, scope=scope)

    async def has(self, amount, scope=None):
        current = await self.get(scope=scope)
        return current >= amount

    async def reset(self, scope=None):
        return await self.set(self._default(), scope=scope)


class Tank:
    def __init__(self, progress, levels_config):
        self.progress = progress
        self.config = levels_config or {}

    def _levels(self):
        return self.config.get("levels", {}) or {}

    def _level_info(self, level):
        levels = self._levels()
        return levels.get(level) or levels.get(str(level))

    def _max_level(self):
        levels = self._levels()
        keys = [int(k) for k in levels.keys()]
        return max(keys) if keys else 1

    async def level(self, scope=None):
        return int(await self.progress.tank_level.get(scope=scope))

    async def max_juice(self, scope=None):
        lvl = await self.level(scope=scope)
        info = self._level_info(lvl)
        if info is None:
            return None
        return info.get("max_juice")

    async def upgrade(self, scope=None):
        scope = resolve_scope(scope)
        with scope:
            lvl = await self.level()
            if lvl >= self._max_level():
                return {"ok": False, "reason": "max_level"}
            new_level = lvl + 1
            await self.progress.tank_level.set(new_level)
            new_max = await self.max_juice()
            event = LevelUpEvent(self.progress.player, lvl, new_level, scope)
            await EventBus.call(event)
            return {"ok": True, "level": new_level, "max_juice": new_max}

    async def downgrade(self, scope=None):
        scope = resolve_scope(scope)
        with scope:
            lvl = await self.level()
            if lvl <= 1:
                return {"ok": False, "reason": "min_level"}
            new_level = lvl - 1
            await self.progress.tank_level.set(new_level)
            new_max = await self.max_juice()
            juice = await self.progress.juice.get()
            if new_max is not None and juice > new_max:
                await self.progress.juice.set(new_max)
            return {"ok": True, "level": new_level, "max_juice": new_max}

    async def set_level(self, level, scope=None):
        scope = resolve_scope(scope)
        with scope:
            level = max(1, min(level, self._max_level()))
            await self.progress.tank_level.set(level)
            new_max = await self.max_juice()
            juice = await self.progress.juice.get()
            if new_max is not None and juice > new_max:
                await self.progress.juice.set(new_max)
            return {"ok": True, "level": level, "max_juice": new_max}

    async def reset(self, scope=None):
        return await self.set_level(1, scope=scope)


class Balls:
    def __init__(self, progress, levels_config):
        self.progress = progress
        self.config = levels_config or {}

    def _levels(self):
        return self.config.get("levels", {}) or {}

    def _level_info(self, level):
        levels = self._levels()
        return levels.get(level) or levels.get(str(level))

    def _max_level(self):
        levels = self._levels()
        keys = [int(k) for k in levels.keys()]
        return max(keys) if keys else 1

    async def level(self, scope=None):
        return int(await self.progress.balls_level.get(scope=scope))

    async def progress_value(self, scope=None):
        return await self.progress.balls_progress.get(scope=scope)

    async def required(self, scope=None):
        lvl = await self.level(scope=scope)
        info = self._level_info(lvl)
        if info is None:
            return None
        return info.get("required")

    async def add_level(self, amount=1, scope=None):
        scope = resolve_scope(scope)
        with scope:
            lvl = await self.level()
            new_level = min(lvl + amount, self._max_level())
            await self.progress.balls_level.set(new_level)
            return new_level

    async def remove_level(self, amount=1, scope=None):
        scope = resolve_scope(scope)
        with scope:
            lvl = await self.level()
            new_level = max(1, lvl - amount)
            await self.progress.balls_level.set(new_level)
            return new_level

    async def reset_level(self, scope=None):
        return await self.progress.balls_level.reset(scope=scope)

    async def add_progress(self, amount, scope=None):
        scope = resolve_scope(scope)
        leveled = []
        with scope:
            await self.progress.balls_progress.add(amount)
            while True:
                lvl = await self.level()
                if lvl >= self._max_level():
                    break
                info = self._level_info(lvl)
                if info is None:
                    break
                required = info.get("required")
                if required is None:
                    break
                current = await self.progress.balls_progress.get()
                if current < required:
                    break
                await self.progress.balls_progress.set(current - required)
                new_level = lvl + 1
                await self.progress.balls_level.set(new_level)
                event = LevelUpEvent(self.progress.player, lvl, new_level, scope)
                await EventBus.call(event)
                leveled.append(new_level)
        return {"leveled_up": leveled, "level": await self.level(scope=scope)}

    async def remove_progress(self, amount, scope=None):
        scope = resolve_scope(scope)
        with scope:
            return await self.progress.balls_progress.remove(amount)

    async def reset_progress(self, scope=None):
        return await self.progress.balls_progress.reset(scope=scope)


class Progress:
    _FIELDS = ["size", "juice", "tank_level", "balls_level", "balls_progress"]

    def __init__(self, player, store, config):
        self.player = player
        self.store = store
        self._config = config
        self._stats = {}

        progress_cfg = config.get("progress", {}) or {}
        levels_cfg = config.file("levels.yml").data or {}

        for field in self._FIELDS:
            cfg = progress_cfg.get(field, {})
            self._stats[field] = Stat(player, field, store, cfg)

        self.tank = Tank(self, levels_cfg.get("tank", {}))
        self.balls = Balls(self, levels_cfg.get("balls", {}))

        self._stats["juice"] = Stat(
            player, "juice", store,
            progress_cfg.get("juice", {}),
            max_provider=self._juice_max,
        )

    async def _juice_max(self, scope):
        return await self.tank.max_juice(scope=scope)

    @property
    def tank_max_juice(self):
        return _ComputedMaxJuice(self)

    def __getattr__(self, name):
        stats = self.__dict__.get("_stats", {})
        if name in stats:
            return stats[name]
        raise AttributeError(name)


class _ComputedMaxJuice:
    def __init__(self, progress):
        self.progress = progress

    async def get(self, scope=None):
        return await self.progress.tank.max_juice(scope=scope)
