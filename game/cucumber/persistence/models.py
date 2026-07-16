from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Column, DateTime, Integer, String, Float,
    PrimaryKeyConstraint, Index,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


class PlayerModel(Base):
    __tablename__ = "players"

    telegram_id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    language_code = Column(String, default="en")
    is_bot = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)


class ProgressModel(Base):
    __tablename__ = "progress"

    telegram_id = Column(BigInteger, nullable=False)
    scope_type = Column(String, nullable=False)
    scope_id = Column(BigInteger, nullable=True)
    key = Column(String, nullable=False)
    value = Column(Float, default=0.0)

    __table_args__ = (
        PrimaryKeyConstraint("telegram_id", "scope_type", "scope_id", "key"),
    )


class InventoryModel(Base):
    __tablename__ = "inventory"

    telegram_id = Column(BigInteger, nullable=False)
    scope_type = Column(String, nullable=False)
    scope_id = Column(BigInteger, nullable=True)
    item_id = Column(String, nullable=False)
    amount = Column(Integer, default=0)
    acquired_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        PrimaryKeyConstraint("telegram_id", "scope_type", "scope_id", "item_id"),
    )


class CupModel(Base):
    __tablename__ = "stats_cups"

    telegram_id = Column(BigInteger, nullable=False)
    scope_type = Column(String, nullable=False)
    scope_id = Column(BigInteger, nullable=True)
    cup_name = Column(String, nullable=False)
    awarded_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        PrimaryKeyConstraint("telegram_id", "scope_type", "scope_id", "cup_name"),
    )


class ClanModel(Base):
    __tablename__ = "clans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    level = Column(Integer, default=1)
    score = Column(Integer, default=0)
    leader_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class ClanMemberModel(Base):
    __tablename__ = "clan_members"

    clan_id = Column(Integer, nullable=False)
    telegram_id = Column(BigInteger, nullable=False)
    role = Column(String, default="member")
    scope_type = Column(String, nullable=False)
    scope_id = Column(BigInteger, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("telegram_id", "scope_type", "scope_id"),
    )


class CooldownModel(Base):
    __tablename__ = "cooldowns"

    telegram_id = Column(BigInteger, nullable=False)
    scope_type = Column(String, nullable=False)
    scope_id = Column(BigInteger, nullable=True)
    key = Column(String, nullable=False)
    started_at = Column(DateTime, default=utcnow)
    duration = Column(Integer, default=0)

    __table_args__ = (
        PrimaryKeyConstraint("telegram_id", "scope_type", "scope_id", "key"),
        Index("ix_cooldowns_player", "telegram_id"),
    )


class ScheduleModel(Base):
    __tablename__ = "schedules"

    owner_id = Column(BigInteger, nullable=False)
    scope_type = Column(String, nullable=False)
    scope_id = Column(BigInteger, nullable=True)
    task_key = Column(String, nullable=False)
    interval_seconds = Column(Integer, nullable=False)
    catchup = Column(String, default="run_once")
    next_run_at = Column(DateTime, nullable=False)
    last_run_at = Column(DateTime, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("owner_id", "scope_type", "scope_id", "task_key"),
        Index("ix_schedules_next_run", "next_run_at"),
    )
class GlobalTickModel(Base):
    __tablename__ = "global_ticks"

    task_key = Column(String, primary_key=True)
    interval_seconds = Column(Integer, nullable=False)
    next_run_at = Column(Float, nullable=False)
    last_run_at = Column(Float, nullable=True)
