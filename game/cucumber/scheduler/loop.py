import asyncio
import heapq
from datetime import datetime, timedelta, timezone

from cucumber.scheduler.registry import discover_scheduled_methods
from cucumber.events.bus import EventBus
from cucumber.events.builtin import ScheduleTickEvent, ScheduleMissedEvent
from cucumber.scope import Scope, ScopeType


def _utcnow():
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class _TaskContext:
    def __init__(self, player, scope, item, count=1, task_key=None,
                 run_at=None, last_run=None, missed=0):
        self.player = player
        self.scope = scope
        self.item = item
        self.count = count
        self.task_key = task_key
        self.run_at = run_at
        self.last_run = last_run
        self.missed = missed
        self._cancelled = False

    def cancel(self):
        self._cancelled = True



class Scheduler:
    def __init__(self, store, registry, player_manager, tick_interval=1,
                 batch_size=500, concurrency=50):
        self.store = store
        self.registry = registry
        self.player_manager = player_manager
        self.tick_interval = tick_interval
        self.batch_size = batch_size
        self.concurrency = concurrency
        self._methods = {}
        self._running = False
        self._task = None
        self._semaphore = asyncio.Semaphore(concurrency)

    def index_methods(self):
        for item in self.registry.all():
            for task_key, method, schedule in discover_scheduled_methods(item):
                self._methods[task_key] = (item, method, schedule)

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._loop())

    async def _loop(self):
        while self._running:
            try:
                await self._tick()
            except Exception:
                pass
            await asyncio.sleep(self.tick_interval)

    async def _tick(self):
        now = _utcnow()
        due = await self.store.due_schedules(now)
        if not due:
            return
        tasks = []
        for schedule in due[:self.batch_size]:
            tasks.append(self._process(schedule, now))
        await asyncio.gather(*tasks)

    async def _process(self, schedule, now):
        async with self._semaphore:
            entry = self._methods.get(schedule.task_key)
            if entry is None:
                await self.store.delete_schedule(
                    schedule.owner_id,
                    self._scope_from(schedule), schedule.task_key,
                )
                return
            item, method, meta = entry
            scope = self._scope_from(schedule)
            player = await self.player_manager.get(schedule.owner_id)
            if player is None:
                return

            interval = schedule.interval_seconds
            next_run = _aware(schedule.next_run_at)
            missed = 0
            while next_run <= now:
                next_run = next_run + timedelta(seconds=interval)
                missed += 1

            catchup = schedule.catchup
            runs = 1
            if catchup == "run_all":
                runs = missed
            elif catchup == "skip":
                runs = 1

            last_run = _aware(schedule.last_run_at)
            for _ in range(runs):
                ctx = _TaskContext(player, scope, item, now, last_run, missed)
                with scope:
                    await method(item, ctx)

            await self.store.update_schedule_run(schedule, next_run, now)

    def _scope_from(self, schedule):
        if schedule.scope_type == ScopeType.UNIVERSAL.value:
            return Scope.universal()
        return Scope.group(schedule.scope_id)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
