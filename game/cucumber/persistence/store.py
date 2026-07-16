from datetime import datetime, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from cucumber.persistence.models import (
    Base, PlayerModel, ProgressModel, InventoryModel, CupModel,
    ClanModel, ClanMemberModel, CooldownModel, ScheduleModel, GlobalTickModel, utcnow,
)

from cucumber.persistence.models import (
    Base, PlayerModel, ProgressModel, InventoryModel, CupModel,
    ClanModel, ClanMemberModel, CooldownModel, ScheduleModel, utcnow,
)
from cucumber.persistence.cache import CacheLayer


class DataStore:
    def __init__(self, database_url: str, cache: CacheLayer):
        self.engine = create_async_engine(database_url, future=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self.cache = cache
        self.cache.set_flush_callback(self._flush_batch)

    async def init(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await self.cache.connect()
        self.cache.start()

    async def _flush_batch(self, batch: dict):
        async with self.session_factory() as session:
            for key, record in batch.items():
                await session.merge(record)
            await session.commit()

    async def _persist(self, key, record):
        self.cache.mark_dirty(key, record)

    def _scope_fields(self, scope):
        return scope.type.value, scope.id

    async def get_player(self, telegram_id):
        key = f"player:{telegram_id}"
        cached = await self.cache.get(key)
        if cached is not None:
            return cached
        async with self.session_factory() as session:
            result = await session.get(PlayerModel, telegram_id)
            if result is None:
                return None
            data = {
                "telegram_id": result.telegram_id,
                "username": result.username,
                "first_name": result.first_name,
                "last_name": result.last_name,
                "language_code": result.language_code,
                "is_bot": result.is_bot,
                "created_at": result.created_at,
            }
            await self.cache.set(key, data)
            return data

    async def upsert_player(self, telegram_id, username=None, first_name=None,
                            last_name=None, language_code="en", is_bot=0):
        key = f"player:{telegram_id}"
        async with self.session_factory() as session:
            model = await session.get(PlayerModel, telegram_id)
            if model is None:
                model = PlayerModel(
                    telegram_id=telegram_id, username=username,
                    first_name=first_name, last_name=last_name,
                    language_code=language_code, is_bot=is_bot,
                )
                session.add(model)
            else:
                if username is not None:
                    model.username = username
                if first_name is not None:
                    model.first_name = first_name
                if last_name is not None:
                    model.last_name = last_name
            await session.commit()
            data = {
                "telegram_id": model.telegram_id,
                "username": model.username,
                "first_name": model.first_name,
                "last_name": model.last_name,
                "language_code": model.language_code,
                "is_bot": model.is_bot,
                "created_at": model.created_at,
            }
        await self.cache.set(key, data)
        return data

    async def get_progress(self, telegram_id, scope, key):
        st, sid = self._scope_fields(scope)
        ck = f"progress:{telegram_id}:{scope.key}:{key}"
        cached = await self.cache.get(ck)
        if cached is not None:
            return cached
        async with self.session_factory() as session:
            row = await session.get(ProgressModel, (telegram_id, st, sid, key))
            value = row.value if row else None
            if value is not None:
                await self.cache.set(ck, value)
            return value

    async def set_progress(self, telegram_id, scope, key, value):
        st, sid = self._scope_fields(scope)
        ck = f"progress:{telegram_id}:{scope.key}:{key}"
        await self.cache.set(ck, value)
        record = ProgressModel(
            telegram_id=telegram_id, scope_type=st, scope_id=sid,
            key=key, value=value,
        )
        self.cache.mark_dirty(f"db:{ck}", record)

    async def get_inventory_entry(self, telegram_id, scope, item_id):
        st, sid = self._scope_fields(scope)
        ck = f"inv:{telegram_id}:{scope.key}:{item_id}"
        cached = await self.cache.get(ck)
        if cached is not None:
            return cached
        async with self.session_factory() as session:
            row = await session.get(InventoryModel, (telegram_id, st, sid, item_id))
            if row is None:
                return None
            data = {"item_id": row.item_id, "amount": row.amount,
                    "acquired_at": row.acquired_at}
            await self.cache.set(ck, data)
            return data

    async def set_inventory_entry(self, telegram_id, scope, item_id, amount):
        st, sid = self._scope_fields(scope)
        ck = f"inv:{telegram_id}:{scope.key}:{item_id}"
        if amount <= 0:
            await self.cache.invalidate(ck)
            async with self.session_factory() as session:
                await session.execute(
                    delete(InventoryModel).where(
                        InventoryModel.telegram_id == telegram_id,
                        InventoryModel.scope_type == st,
                        InventoryModel.scope_id == sid,
                        InventoryModel.item_id == item_id,
                    )
                )
                await session.commit()
            return
        data = {"item_id": item_id, "amount": amount, "acquired_at": utcnow()}
        await self.cache.set(ck, data)
        record = InventoryModel(
            telegram_id=telegram_id, scope_type=st, scope_id=sid,
            item_id=item_id, amount=amount, acquired_at=data["acquired_at"],
        )
        self.cache.mark_dirty(f"db:{ck}", record)

    async def all_inventory(self, telegram_id, scope):
        st, sid = self._scope_fields(scope)
        async with self.session_factory() as session:
            result = await session.execute(
                select(InventoryModel).where(
                    InventoryModel.telegram_id == telegram_id,
                    InventoryModel.scope_type == st,
                    InventoryModel.scope_id == sid,
                    InventoryModel.amount > 0,
                )
            )
            return [
                {"item_id": r.item_id, "amount": r.amount, "acquired_at": r.acquired_at}
                for r in result.scalars().all()
            ]

    async def clear_inventory(self, telegram_id, scope):
        st, sid = self._scope_fields(scope)
        async with self.session_factory() as session:
            await session.execute(
                delete(InventoryModel).where(
                    InventoryModel.telegram_id == telegram_id,
                    InventoryModel.scope_type == st,
                    InventoryModel.scope_id == sid,
                )
            )
            await session.commit()

    async def get_cups(self, telegram_id, scope):
        st, sid = self._scope_fields(scope)
        async with self.session_factory() as session:
            result = await session.execute(
                select(CupModel).where(
                    CupModel.telegram_id == telegram_id,
                    CupModel.scope_type == st,
                    CupModel.scope_id == sid,
                )
            )
            return [r.cup_name for r in result.scalars().all()]

    async def add_cup(self, telegram_id, scope, cup_name):
        st, sid = self._scope_fields(scope)
        async with self.session_factory() as session:
            existing = await session.get(CupModel, (telegram_id, st, sid, cup_name))
            if existing is None:
                session.add(CupModel(
                    telegram_id=telegram_id, scope_type=st, scope_id=sid,
                    cup_name=cup_name,
                ))
                await session.commit()

    async def remove_cup(self, telegram_id, scope, cup_name):
        st, sid = self._scope_fields(scope)
        async with self.session_factory() as session:
            await session.execute(
                delete(CupModel).where(
                    CupModel.telegram_id == telegram_id,
                    CupModel.scope_type == st,
                    CupModel.scope_id == sid,
                    CupModel.cup_name == cup_name,
                )
            )
            await session.commit()

    async def get_clan_membership(self, telegram_id, scope):
        st, sid = self._scope_fields(scope)
        async with self.session_factory() as session:
            member = await session.get(ClanMemberModel, (telegram_id, st, sid))
            if member is None:
                return None
            clan = await session.get(ClanModel, member.clan_id)
            if clan is None:
                return None
            return {"clan_id": clan.id, "name": clan.name, "level": clan.level,
                    "score": clan.score, "leader_id": clan.leader_id,
                    "role": member.role}

    async def join_clan(self, telegram_id, scope, clan_name):
        st, sid = self._scope_fields(scope)
        async with self.session_factory() as session:
            result = await session.execute(
                select(ClanModel).where(ClanModel.name == clan_name)
            )
            clan = result.scalar_one_or_none()
            role = "member"
            if clan is None:
                clan = ClanModel(name=clan_name, leader_id=telegram_id)
                session.add(clan)
                await session.flush()
                role = "leader"
            session.add(ClanMemberModel(
                clan_id=clan.id, telegram_id=telegram_id, role=role,
                scope_type=st, scope_id=sid,
            ))
            await session.commit()
            return role

    async def leave_clan(self, telegram_id, scope):
        st, sid = self._scope_fields(scope)
        async with self.session_factory() as session:
            await session.execute(
                delete(ClanMemberModel).where(
                    ClanMemberModel.telegram_id == telegram_id,
                    ClanMemberModel.scope_type == st,
                    ClanMemberModel.scope_id == sid,
                )
            )
            await session.commit()

    async def clan_rank(self, clan_id):
        async with self.session_factory() as session:
            result = await session.execute(
                select(ClanModel).order_by(ClanModel.score.desc())
            )
            clans = result.scalars().all()
            for idx, c in enumerate(clans, start=1):
                if c.id == clan_id:
                    return idx
            return None

    async def clan_members(self, clan_id):
        async with self.session_factory() as session:
            result = await session.execute(
                select(ClanMemberModel).where(ClanMemberModel.clan_id == clan_id)
            )
            return [r.telegram_id for r in result.scalars().all()]

    async def get_cooldown(self, telegram_id, scope, key):
        st, sid = self._scope_fields(scope)
        async with self.session_factory() as session:
            row = await session.get(CooldownModel, (telegram_id, st, sid, key))
            if row is None:
                return None
            return {"key": row.key, "started_at": row.started_at,
                    "duration": row.duration}

    async def set_cooldown(self, telegram_id, scope, key, started_at, duration):
        st, sid = self._scope_fields(scope)
        async with self.session_factory() as session:
            await session.merge(CooldownModel(
                telegram_id=telegram_id, scope_type=st, scope_id=sid,
                key=key, started_at=started_at, duration=duration,
            ))
            await session.commit()

    async def delete_cooldown(self, telegram_id, scope, key):
        st, sid = self._scope_fields(scope)
        async with self.session_factory() as session:
            await session.execute(
                delete(CooldownModel).where(
                    CooldownModel.telegram_id == telegram_id,
                    CooldownModel.scope_type == st,
                    CooldownModel.scope_id == sid,
                    CooldownModel.key == key,
                )
            )
            await session.commit()

    async def due_schedules(self, now):
        async with self.session_factory() as session:
            result = await session.execute(
                select(ScheduleModel).where(ScheduleModel.next_run_at <= now)
            )
            return result.scalars().all()

    async def save_schedule(self, owner_id, scope, task_key, interval,
                            next_run_at, catchup, last_run_at=None):
        st, sid = self._scope_fields(scope)
        async with self.session_factory() as session:
            await session.merge(ScheduleModel(
                owner_id=owner_id, scope_type=st, scope_id=sid,
                task_key=task_key, interval_seconds=interval,
                catchup=catchup, next_run_at=next_run_at, last_run_at=last_run_at,
            ))
            await session.commit()


    async def get_item_owners(self, item_id):
        async with self.session_factory() as session:
            result = await session.execute(
                select(
                    InventoryModel.telegram_id,
                    InventoryModel.scope_type,
                    InventoryModel.scope_id,
                    InventoryModel.amount,
                    PlayerModel.username,
                    PlayerModel.first_name,
                    PlayerModel.last_name,
                    PlayerModel.language_code,
                    PlayerModel.is_bot,
                )
                .join(PlayerModel, PlayerModel.telegram_id == InventoryModel.telegram_id)
                .where(InventoryModel.item_id == item_id)
                .where(InventoryModel.amount > 0)
            )
            owners = []
            for row in result.all():
                scope_key = (
                    "universal"
                    if row.scope_type == "UNIVERSAL"
                    else f"group:{row.scope_id}"
                )
                owners.append({
                    "telegram_id": row.telegram_id,
                    "owner_id": row.telegram_id,
                    "scope": scope_key,
                    "amount": row.amount,
                    "username": row.username,
                    "first_name": row.first_name,
                    "last_name": row.last_name,
                    "language_code": row.language_code,
                    "is_bot": row.is_bot,
                })
            return owners

    
    async def get_global_tick(self, task_key):
        async with self.session_factory() as session:
            result = await session.execute(
                select(GlobalTickModel).where(GlobalTickModel.task_key == task_key)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return {
                "task_key": row.task_key,
                "interval_seconds": row.interval_seconds,
                "next_run_at": row.next_run_at,
                "last_run_at": row.last_run_at,
            }

    async def upsert_global_tick(self, task_key, interval_seconds, next_run_at, last_run_at=None):
        async with self.session_factory() as session:
            result = await session.execute(
                select(GlobalTickModel).where(GlobalTickModel.task_key == task_key)
            )
            row = result.scalar_one_or_none()
            if row is None:
                row = GlobalTickModel(
                    task_key=task_key,
                    interval_seconds=interval_seconds,
                    next_run_at=next_run_at,
                    last_run_at=last_run_at,
                )
                session.add(row)
            else:
                row.interval_seconds = interval_seconds
                row.next_run_at = next_run_at
                if last_run_at is not None:
                    row.last_run_at = last_run_at
            await session.commit()

    async def delete_schedule(self, owner_id, scope, task_key):
        st, sid = self._scope_fields(scope)
        async with self.session_factory() as session:
            await session.execute(
                delete(ScheduleModel).where(
                    ScheduleModel.owner_id == owner_id,
                    ScheduleModel.scope_type == st,
                    ScheduleModel.scope_id == sid,
                    ScheduleModel.task_key == task_key,
                )
            )
            await session.commit()

    async def update_schedule_run(self, schedule, next_run_at, last_run_at):
        async with self.session_factory() as session:
            await session.merge(ScheduleModel(
                owner_id=schedule.owner_id, scope_type=schedule.scope_type,
                scope_id=schedule.scope_id, task_key=schedule.task_key,
                interval_seconds=schedule.interval_seconds,
                catchup=schedule.catchup,
                next_run_at=next_run_at, last_run_at=last_run_at,
            ))
            await session.commit()

    async def close(self):
        await self.cache.close()
        await self.engine.dispose()
