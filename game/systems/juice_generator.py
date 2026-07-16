import asyncio
import time

from sqlalchemy import select, distinct

from cucumber import EventBus, Scope, config
from cucumber.persistence.models import ProgressModel
from cucumber.scope import ScopeType

from events import JuiceGainEvent


TASK_KEY = "system.juice_generator"


def _cfg():
    return config.file("levels.yml").get("juice_generator", {}) or {}


class JuiceGenerator:
    def __init__(self, tick_interval=5.0):
        self.tick_interval = tick_interval
        self._running = False
        self._task = None
        self.next_run_at = None

    async def start(self):
        if self._running:
            return
        self._running = True
        await self._load_or_init()
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def _interval(self):
        return _cfg().get("interval_seconds", 60)

    async def _load_or_init(self):
        engine = get_engine()
        now = time.time()
        record = await engine.store.get_global_tick(TASK_KEY)
        interval = self._interval()
        if record is None:
            self.next_run_at = now + interval
            await engine.store.upsert_global_tick(TASK_KEY, interval, self.next_run_at)
        else:
            self.next_run_at = record["next_run_at"]

    async def _loop(self):
        engine = get_engine()
        while self._running:
            now = time.time()
            if self.next_run_at is not None and now >= self.next_run_at:
                interval = self._interval()
                missed = int((now - self.next_run_at) // interval)
                self.next_run_at += interval * (missed + 1)
                await engine.store.upsert_global_tick(
                    TASK_KEY, interval, self.next_run_at, last_run_at=now
                )
                try:
                    await self._run()
                except Exception as exc:
                    print(f"[JUICE_GEN] error: {exc}")
            await asyncio.sleep(self.tick_interval)

    async def _all_scopes(self, engine):
        async with engine.store.session_factory() as session:
            result = await session.execute(
                select(
                    distinct(ProgressModel.telegram_id),
                    ProgressModel.scope_type,
                    ProgressModel.scope_id,
                ).select_from(ProgressModel)
            )
            seen = set()
            targets = []
            for tid, st, sid in result.all():
                keyt = (tid, st, sid)
                if keyt in seen:
                    continue
                seen.add(keyt)
                targets.append((tid, st, sid))
            return targets

    def _scope_from(self, st, sid):
        if st == ScopeType.UNIVERSAL.value:
            return Scope.universal()
        return Scope.group(sid)

    async def _run(self):
        engine = get_engine()
        base = _cfg().get("base_amount", 5)
        targets = await self._all_scopes(engine)

        for tid, st, sid in targets:
            player = await engine.players.get(tid)
            if player is None:
                continue
            scope = self._scope_from(st, sid)
            await self._give(player, scope, base)

    async def _give(self, player, scope, base):
        with scope:
            event = JuiceGainEvent(player=player, amount=base, scope=scope)
            await EventBus.call(event)

            if event.cancelled:
                return

            amount = int(event.amount)
            if amount <= 0:
                return

            current = await player.progress.juice.get(scope=scope)
            max_juice = await player.progress.tank.max_juice(scope=scope)

            if max_juice is not None:
                if current >= max_juice:
                    return
                amount = min(amount, int(max_juice - current))
                if amount <= 0:
                    return

            await player.progress.juice.add(amount, scope=scope)
            print(f"[JUICE] {player.name} +{amount} juice @ {scope.key}")
