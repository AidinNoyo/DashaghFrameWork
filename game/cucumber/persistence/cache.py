import asyncio
import time
from collections import OrderedDict
from typing import Any, Optional

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None


class LRUCache:
    def __init__(self, maxsize=100000):
        self.maxsize = maxsize
        self._data: OrderedDict = OrderedDict()
        self._expiry: dict = {}

    def get(self, key: str) -> Any:
        if key not in self._data:
            return None
        exp = self._expiry.get(key)
        if exp is not None and exp < time.time():
            self._data.pop(key, None)
            self._expiry.pop(key, None)
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        self._data[key] = value
        self._data.move_to_end(key)
        if ttl:
            self._expiry[key] = time.time() + ttl
        while len(self._data) > self.maxsize:
            old, _ = self._data.popitem(last=False)
            self._expiry.pop(old, None)

    def delete(self, key: str):
        self._data.pop(key, None)
        self._expiry.pop(key, None)

    def clear(self):
        self._data.clear()
        self._expiry.clear()


class CacheLayer:
    def __init__(self, redis_url: Optional[str] = None, ttl: int = 300,
                 write_behind: bool = True, flush_interval: int = 5):
        self.l1 = LRUCache()
        self.ttl = ttl
        self.write_behind = write_behind
        self.flush_interval = flush_interval
        self._redis = None
        self._redis_url = redis_url
        self._dirty: dict = {}
        self._flush_task = None
        self._flush_callback = None

    async def connect(self):
        if self._redis_url and aioredis is not None:
            self._redis = aioredis.from_url(self._redis_url, decode_responses=False)

    def set_flush_callback(self, callback):
        self._flush_callback = callback

    async def get(self, key: str) -> Any:
        value = self.l1.get(key)
        if value is not None:
            return value
        if self._redis is not None:
            raw = await self._redis.get(key)
            if raw is not None:
                import pickle
                value = pickle.loads(raw)
                self.l1.set(key, value, self.ttl)
                return value
        return None

    async def set(self, key: str, value: Any):
        self.l1.set(key, value, self.ttl)
        if self._redis is not None:
            import pickle
            await self._redis.set(key, pickle.dumps(value), ex=self.ttl)

    def mark_dirty(self, key: str, record: Any):
        self._dirty[key] = record

    async def invalidate(self, key: str):
        self.l1.delete(key)
        if self._redis is not None:
            await self._redis.delete(key)

    def start(self):
        if self.write_behind and self._flush_task is None:
            self._flush_task = asyncio.create_task(self._flush_loop())

    async def _flush_loop(self):
        while True:
            await asyncio.sleep(self.flush_interval)
            await self.flush()

    async def flush(self):
        if not self._dirty:
            return
        batch = self._dirty
        self._dirty = {}
        if self._flush_callback is not None:
            await self._flush_callback(batch)

    async def close(self):
        await self.flush()
        if self._flush_task:
            self._flush_task.cancel()
        if self._redis is not None:
            await self._redis.close()
