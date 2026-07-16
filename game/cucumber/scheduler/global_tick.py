import asyncio
import time


class GlobalTickEntry:
    def __init__(self, task_key, item_id, method, interval, engine):
        self.task_key = task_key
        self.item_id = item_id
        self.method = method
        self.interval = interval
        self.engine = engine
        self.next_run_at = None

    async def load_or_init(self, now):
        record = await self.engine.store.get_global_tick(self.task_key)
        if record is None:
            self.next_run_at = now + self.interval
            await self.engine.store.upsert_global_tick(
                self.task_key, self.interval, self.next_run_at
            )
        else:
            self.next_run_at = record["next_run_at"]
            if record["interval_seconds"] != self.interval:
                await self.engine.store.upsert_global_tick(
                    self.task_key, self.interval, self.next_run_at
                )

    def is_due(self, now):
        return self.next_run_at is not None and now >= self.next_run_at

    async def schedule_next(self, now):
        missed = int((now - self.next_run_at) // self.interval)
        self.next_run_at += self.interval * (missed + 1)
        await self.engine.store.upsert_global_tick(
            self.task_key, self.interval, self.next_run_at, last_run_at=now
        )


class GlobalTickRunner:
    def __init__(self, engine, tick_interval=1.0):
        self.engine = engine
        self.tick_interval = tick_interval
        self._entries = []
        self._running = False
        self._task = None
        self._initialized = False

    def register(self, entry):
        self._entries.append(entry)

    async def start(self):
        if self._running:
            return
        self._running = True
        now = time.time()
        for entry in self._entries:
            await entry.load_or_init(now)
        self._initialized = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self):
        while self._running:
            now = time.time()
            due = [e for e in self._entries if e.is_due(now)]
            for entry in due:
                await entry.schedule_next(now)
                try:
                    await self._run_entry(entry)
                except Exception as exc:
                    print(f"[GLOBAL_TICK] error in {entry.task_key}: {exc}")
            await asyncio.sleep(self.tick_interval)

    async def _run_entry(self, entry):
        owners = await self.engine.store.get_item_owners(entry.item_id)
        if not owners:
            return
        item_instance = self.engine.registry.get(entry.item_id)
        for owner in owners:
            player = await self.engine.players.get_or_create(
                telegram_id=owner["telegram_id"],
                username=owner.get("username"),
                first_name=owner.get("first_name"),
                last_name=owner.get("last_name"),
                language_code=owner.get("language_code") or "en",
                is_bot=owner.get("is_bot", 0),
            )
            scope = self.engine.scope_from_key(owner["scope"])
            count = owner["amount"]
            context = self.engine.build_task_context(
                player=player,
                scope=scope,
                item=item_instance,
                count=count,
                task_key=entry.task_key,
            )
            with scope:
                await entry.method(context)
