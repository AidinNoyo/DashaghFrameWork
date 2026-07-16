<div align="center">

# 🥒 CucumberEngine

### A Domain-Driven Game Framework for Telegram Bots

*A Pythonic, plugin-based, event-driven and scalable framework for building group-based Telegram games.*

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)]()
[![Status](https://img.shields.io/badge/Status-Design%20Doc-orange.svg)]()

</div>

---

## 📖 Table of Contents

- [Design Philosophy](#design-philosophy)
- [Architecture Overview](#architecture-overview)
- [Installation & Quick Start](#installation--quick-start)
- [The Scope Concept](#the-scope-concept)
- [The Player Domain Model](#the-player-domain-model)
  - [player.meta](#playermeta)
  - [player.progress](#playerprogress)
  - [player.inventory](#playerinventory)
  - [player.stats](#playerstats)
  - [player.clan](#playerclan)
  - [player.cooldowns](#playercooldowns)
- [The Item System (Plugin-Based)](#the-item-system-plugin-based)
- [The Command System](#the-command-system)
- [The Event System (Event Bus)](#the-event-system-event-bus)
- [The Config System](#the-config-system)
- [The Database & Caching Layer](#the-database--caching-layer)
- [Full End-to-End Example](#full-end-to-end-example)
- [Project Structure](#project-structure)
- [Roadmap](#roadmap)

---

## Design Philosophy

CucumberEngine is built on five core principles:

1. **Rich Domain Model.** The developer never sees SQL, repositories, or queries. They only work with game objects such as `player.inventory.add(...)` and `player.progress.money.take(...)`. Persistence, caching and transactions happen invisibly underneath.

2. **Everything is Scope-driven.** Instead of passing a `groupId` into every function, a single concept called `Scope` decides *where* data is read from or written to (a specific group, or the universal/global space).

3. **Items are plugins.** The core never inspects an item's type. There is no `if item.type == ...` anywhere in the engine. Each item declares its own behavior and subscribes to events.

4. **Mutable, event-driven flow.** Every command produces a mutable `Event`. Plugins and items can modify values, cancel execution, or swap the response message before the final result is committed.

5. **Scalability first.** The persistence layer ships with a multi-layer cache (in-memory + optional Redis), write-behind batching, and per-scope isolation so the game keeps working under heavy user load.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                     Telegram Adapter                       │
│         (aiogram / python-telegram-bot / custom)           │
└───────────────────────────┬──────────────────────────────┘
                            │  raw update
                            ▼
┌──────────────────────────────────────────────────────────┐
│                     Command Router                         │
│   match: exact / prefix / regex / startswith / contains    │
└───────────────────────────┬──────────────────────────────┘
                            │  Command context
                            ▼
┌──────────────────────────────────────────────────────────┐
│              Command Lifecycle: before → execute → after   │
│                       creates a mutable Event              │
└───────────────────────────┬──────────────────────────────┘
                            │  Event
                            ▼
┌──────────────────────────────────────────────────────────┐
│                        Event Bus                           │
│   dispatch by priority: LOWEST→LOW→NORMAL→HIGH→HIGHEST→MON  │
│   listeners: Items (plugins), Extensions, Core hooks       │
└───────────────────────────┬──────────────────────────────┘
                            │  mutated Event
                            ▼
┌──────────────────────────────────────────────────────────┐
│                 Rich Domain Model (Player)                 │
│   meta · progress · inventory · stats · clan · cooldowns   │
└───────────────────────────┬──────────────────────────────┘
                            │  domain ops (scope-aware)
                            ▼
┌──────────────────────────────────────────────────────────┐
│              Persistence Layer (Unit of Work)              │
│      L1 in-memory cache → L2 Redis → DB (SQL / async)      │
└──────────────────────────────────────────────────────────┘
```

---

## Installation & Quick Start

```bash
pip install cucumber-engine        # (planned package name)
```

Minimal bot:

```python
from cucumber import CucumberEngine, Scope
from cucumber.adapters import AiogramAdapter

engine = CucumberEngine(
    config_dir="./config",
    database_url="postgresql+asyncpg://user:pass@localhost/game",
    cache="redis://localhost:6379/0",   # optional; falls back to memory
)

# auto-discover commands and items
engine.load_commands("game/commands")
engine.load_items("game/items")

# attach a Telegram adapter
engine.use(AiogramAdapter(token="YOUR_BOT_TOKEN"))

if __name__ == "__main__":
    engine.run()
```

That is the *entire* wiring. Everything else lives in isolated command and item classes.

---

## The Scope Concept

`Scope` is the most important idea in the framework. It answers one question: **"Within which boundary does this data live?"**

There are two scope types:

| Type        | Meaning                                             | Example key         |
|-------------|-----------------------------------------------------|---------------------|
| `GROUP`     | Data belongs to one Telegram group/chat.            | `group:123456`      |
| `UNIVERSAL` | Global data, shared across all groups (per player). | `universal`         |

### Creating a Scope

```python
from cucumber import Scope

# explicit
scope = Scope.group(123456)
scope = Scope.universal()

# from a raw type + id
scope = Scope(type=Scope.GROUP, id=123456)
```

### Scope as an explicit argument

Every scope-aware API accepts a `scope` argument:

```python
player.progress.money.add(500, scope=Scope.universal())
player.inventory.add("heart", 2, scope=Scope.group(123456))
player.stats.cups.add("Winter Cup", scope=Scope.group(123456))
```

### Scope as a context manager (ambient scope)

To avoid repeating `scope=...`, you can enter a scope block. Any scope-aware call inside the block uses the ambient scope automatically:

```python
with Scope.universal():
    player.progress.money.add(100)     # written to UNIVERSAL
    player.inventory.add("heart", 1)   # written to UNIVERSAL

with Scope.group(123456):
    player.progress.xp.add(50)         # written to GROUP:123456
```

Commands expose helpers so you rarely build scopes by hand:

```python
with command.universal():   # == Scope.universal()
    ...

with command.group():       # == Scope.group(command.chat_id)
    ...
```

### Scope resolution order

When a scope-aware method is called, the engine resolves the scope in this order:

1. An explicit `scope=` keyword argument (highest priority).
2. The nearest active `with Scope(...)` context.
3. The command's default scope (usually the current group).
4. If nothing is found → `ScopeNotProvidedError` is raised (fail-loud, never silently global).

> **Rule of thumb:** scope-aware data (progress, inventory, stats, clan, cooldowns) **always** needs a scope. Only `player.meta` is scope-free because it describes the human, not the game state.

---

## The Player Domain Model

The `Player` object is a rich aggregate root. You obtain it from the command or from the engine:

```python
player = command.sender                 # the player who sent the command
player = command.arg_player(2)          # a player parsed from argument #2
player = await engine.players.get(telegram_id=99999)
```

A `Player` exposes six namespaces:

```
player.meta        # identity, NO scope
player.progress    # numeric game stats, scope needed
player.inventory   # items owned, scope needed
player.stats       # cups / achievements, scope needed
player.clan        # clan membership, scope needed
player.cooldowns   # timers, scope needed (separate table)
```

**Every mutating action fires an event** (see [Event System](#the-event-system-event-bus)), so items and plugins can react to any change.

---

### player.meta

Scope-free identity data. Read-mostly.

```python
player.meta.telegram_id      # -> int
player.meta.username         # -> str | None
player.meta.first_name       # -> str
player.meta.last_name        # -> str | None
player.meta.language_code    # -> str
player.meta.created_at       # -> datetime
player.meta.is_bot           # -> bool
```

```python
name = player.meta.first_name
print(f"Hello {name}!")
```

---

### player.progress

Numeric, scope-aware game state. Each field is a **Stat object** that supports arithmetic operations with events attached.

Fields:

```python
player.progress.money        # currency
player.progress.level        # player level
player.progress.xp           # experience (can auto level-up, configurable)
player.progress.defense      # defense stat
player.progress.attack       # attack stat
player.progress.energy       # energy stat (can regenerate over time)
player.progress.rank         # computed/global rank
player.progress.premium      # premium flag / tier
```

Each Stat object supports:

```python
stat.get()                   # current value
stat.set(value)              # overwrite
stat.add(amount)             # increment
stat.take(amount)            # decrement (raises if insufficient, configurable)
stat.has(amount)             # bool: enough to spend?
stat.reset()                 # back to default
```

Examples:

```python
with command.group():
    player.progress.money.add(500)
    if player.progress.money.has(200):
        player.progress.money.take(200)

    player.progress.xp.add(50)
    lvl = player.progress.level.get()

# explicit scope form
player.progress.attack.add(10, scope=Scope.universal())
```

Convenience shortcuts on the player (as requested):

```python
player.add_money(500, Scope.UNIVERSAL)   # == player.progress.money.add(500, ...)
player.add_size(10, Scope.GROUP)         # custom stat example
player.add_cucumber(10, scope)           # game-specific stat
```

> Custom numeric stats (like `size` or `cucumber`) can be declared in `config.yml` under `progress.custom` and become first-class Stat objects automatically.

---

### player.inventory

Scope-aware item storage. Works with item **ids** or with `Item` objects.

```python
player.inventory.add(item)                 # add 1
player.inventory.add(item, amount)         # add N
player.inventory.remove(item)              # remove 1
player.inventory.remove(item, amount)      # remove N
player.inventory.has(item)                 # -> bool
player.inventory.count(item)               # -> int (how many owned)
player.inventory.get(item)                 # -> InventoryEntry | None
player.inventory.all()                     # -> list[InventoryEntry]
player.inventory.clear()                   # remove everything
player.inventory.use(item)                 # triggers item.on_use(context)
```

Examples:

```python
from game.items import Items

with command.group():
    player.inventory.add("heart", 2)
    player.inventory.add(Items.shield)

    if player.inventory.has(Items.shield):
        entry = player.inventory.get(Items.shield)
        print(entry.item.name, entry.amount)

    player.inventory.use("potion")          # fires PotionItem.on_use()
    player.inventory.remove("heart", 1)

# explicit scope
player.inventory.add("heart", 2, scope=Scope.group(123456))
```

`InventoryEntry` shape:

```python
entry.item        # -> Item instance (the plugin)
entry.amount      # -> int
entry.acquired_at # -> datetime
entry.scope       # -> Scope it lives in
```

Events fired: `InventoryAddEvent`, `InventoryRemoveEvent`, `InventoryUseEvent`, `InventoryClearEvent`.

---

### player.stats

Scope-aware achievements / trophies ("cups").

```python
player.stats.cups.add("Winter Cup")        # award a cup
player.stats.cups.remove("Winter Cup")     # revoke a cup
player.stats.cups.has("Winter Cup")        # -> bool
player.stats.cups.get()                     # -> list[str] of owned cups
player.stats.cups.count()                   # -> int
player.stats.cups.clear()                   # remove all cups
```

Examples:

```python
with command.group():
    player.stats.cups.add("Champion")
    cups = player.stats.cups.get()          # ["Champion", ...]

player.stats.cups.add("Global Legend", scope=Scope.universal())
```

Events fired: `CupAddEvent`, `CupRemoveEvent`.

> `player.stats` is extensible: you can register additional stat collections (e.g. `medals`, `badges`) via the config or a plugin, and they behave exactly like `cups`.

---

### player.clan

Scope-aware clan membership.

```python
player.clan.join(clan_name)          # join / create membership
player.clan.leave()                  # leave current clan
player.clan.rank()                   # -> player's rank INSIDE the clan (member/officer/leader)
player.clan.clan_rank()              # -> the clan's rank among all clans (leaderboard position)
player.clan.get()                    # -> Clan object (name, members, level, ...) | None
player.clan.is_member()              # -> bool
```

`Clan` object:

```python
clan.name            # -> str
clan.level           # -> int
clan.members         # -> list[Player]
clan.leader          # -> Player
clan.score           # -> int (used for clan leaderboard)
clan.created_at      # -> datetime
```

Examples:

```python
with command.group():
    player.clan.join("Pickle Warriors")
    my_role = player.clan.rank()            # "leader"
    board_pos = player.clan.clan_rank()     # 3
    clan = player.clan.get()
    print(clan.name, len(clan.members))
    player.clan.leave()
```

Events fired: `ClanJoinEvent`, `ClanLeaveEvent`, `ClanRankChangeEvent`.

---

### player.cooldowns

Scope-aware timers stored in a **separate table**. Great for actions like `grow`, `attack`, `daily`.

```python
player.cooldowns.start("grow", 3600)     # start a 3600s cooldown
player.cooldowns.is_ready("grow")        # -> bool (True if elapsed / never started)
player.cooldowns.remaining("grow")       # -> int seconds left (0 if ready)
player.cooldowns.reset("grow")           # restart from full duration
player.cooldowns.extend("grow", 120)     # add 120s to remaining
player.cooldowns.reduce("grow", 60)      # subtract 60s from remaining
player.cooldowns.finish("grow")          # force-complete now (ready immediately)
player.cooldowns.get("grow")             # -> Cooldown object | None
```

`Cooldown` object:

```python
cd.key          # -> "grow"
cd.started_at   # -> datetime
cd.duration     # -> int (seconds)
cd.ends_at      # -> datetime
cd.remaining    # -> int (seconds left)
cd.is_ready     # -> bool
```

Examples:

```python
with command.group():
    if not player.cooldowns.is_ready("grow"):
        left = player.cooldowns.remaining("grow")
        return command.reply(f"⏳ Wait {left}s")

    player.cooldowns.start("grow", 3600)
    # ... do the grow action ...
```

Events fired: `CooldownStartEvent`, `CooldownFinishEvent`.

---

## The Item System (Plugin-Based)

**Every item is a self-contained plugin.** The core engine never checks item types. An item declares metadata, lifecycle hooks, and can subscribe to any game event.

### Declaring an item

```python
from cucumber import Item, item, eventHandler
from cucumber.events import AttackEvent

@item("shield")
class ShieldItem(Item):
    # --- metadata (can be overridden by items.yml) ---
    name = "Shield"
    price = 250
    category = "defense"
    max_owned = 5
    enabled = True

    # --- lifecycle hooks ---
    async def on_purchase(self, context): ...
    async def on_remove(self, context): ...
    async def on_use(self, context): ...
    async def on_profile(self, context): ...   # how it renders on a player's profile

    # --- event subscriptions ---
    @eventHandler(AttackEvent)
    async def on_attack(self, event):
        target = event.target
        if target.inventory.has("shield"):
            target.inventory.remove("shield", 1)
            event.cancel("🛡 Shield blocked the attack")
```

### Item properties

```python
item.id           # -> "shield"  (the registration key)
item.name         # -> "Shield"
item.price        # -> 250
item.category     # -> "defense"
item.max_owned    # -> 5  (None = unlimited)
item.enabled      # -> bool
item.get("key")   # -> read a custom field from items.yml (e.g. item.get("block_chance"))
```

### Item lifecycle hooks

Each hook receives a `context` object (a rich event) that carries the player, scope, message key, placeholders and metadata — and can be mutated or cancelled.

| Hook              | Fired when…                                   | Can cancel? |
|-------------------|-----------------------------------------------|-------------|
| `on_purchase`     | player buys the item from the shop            | ✅ (refund) |
| `on_remove`       | item leaves the inventory                     | ❌          |
| `on_use`          | `player.inventory.use(item)` is called        | ✅          |
| `on_profile`      | rendering the item on a profile card          | ❌          |

Example `on_use`:

```python
@item("potion")
class PotionItem(Item):
    name = "Health Potion"
    price = 80
    category = "consumable"

    async def on_use(self, context):
        player = context.player
        heal = self.get("heal_amount")          # from items.yml
        player.progress.energy.add(heal, scope=context.scope)
        context.message_key = "potion_used"
        context.placeholders["heal"] = heal
```

### What items are allowed to do

Inside any event handler or hook, an item may:

- **modify values** — `event.damage = int(event.damage * 0.5)`
- **cancel actions** — `event.cancel("reason")`
- **change response messages** — `event.message_key = "blocked"`
- **add placeholders** — `event.placeholders["shield_left"] = 2`
- **trigger extra actions** — `attacker.cooldowns.start("stunned", 60)`

### The golden rule

> **No core logic ever contains `if item.type == ...`.**
> Behavior lives *inside* the item plugin. The core only dispatches events and calls lifecycle hooks.

---

## The Command System

Every command is an **isolated class** decorated with `@commandHandler(...)`.

### The decorator

```python
@commandHandler(
    name="attack",
    aliases=["atk", "hit"],
    description="Attack another player",
    cooldown=30,                 # seconds; auto-managed via player.cooldowns
    permission="player",         # "player" | "admin" | "clan_leader" | custom
    category="combat",
    match="exact",               # exact | prefix | startswith | contains | regex
)
class AttackCommand(Command):
    ...
```

`match` modes:

| Mode         | Triggers when the message…                     |
|--------------|------------------------------------------------|
| `exact`      | equals the command name/alias                  |
| `prefix`     | starts with a bot prefix + name (`/attack`)    |
| `startswith` | starts with the name (`attack 10 @user`)       |
| `contains`   | contains the name anywhere                     |
| `regex`      | matches a supplied regex pattern               |

### The command lifecycle

```python
class AttackCommand(Command):

    async def before(self, command):
        """Validation, permissions, cooldown checks. Cancel here to stop."""

    async def execute(self, command):
        """Main gameplay logic. Builds a mutable Event and dispatches it."""

    async def after(self, command):
        """Logging, cleanup, statistics, final reply."""
```

If `before` calls `command.cancel(...)`, then `execute` and `after` are skipped and the cancel message is sent.

### The `command` object

The object passed into every lifecycle method:

```python
# identity & context
command.sender          # -> Player who sent the command
command.chat_id         # -> int (Telegram chat id)
command.raw_text        # -> str (original message)
command.data            # -> dict (share state between before/execute/after)

# argument parsing
command.arg(i)          # -> str  (raw token at index i)
command.arg_int(i)      # -> int | None
command.arg_player(i)   # -> Player | None (parses @mention / reply / id)
command.args            # -> list[str] (all tokens)

# scope helpers
command.group()         # -> Scope context manager for the current chat
command.universal()     # -> Scope context manager for universal

# flow control
command.cancel(message_key)          # abort the command with a message
command.reply(text_or_key, **ph)     # send a reply (resolves message keys)
command.tr(key, **placeholders)      # translate a message key from messages.yml
```

### Argument parsing example

For the message `attack 10 @victim x`:

```python
amount = command.arg_int(1)      # 10
target = command.arg_player(2)   # Player(@victim)
mode   = command.arg(3)          # "x"
```

---

## The Event System (Event Bus)

The event bus is the beating heart of extensibility. **Every command and every domain mutation creates a mutable event**, dispatched to all subscribers before the final result is committed.

### Defining an event

```python
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
```

Every `Event` inherits these mutable fields:

```python
event.scope           # -> Scope
event.message_key     # -> str  (which message to reply with)
event.placeholders    # -> dict (values injected into the message)
event.metadata        # -> dict (free-form attachments)
event.cancelled       # -> bool
event.cancel_reason   # -> str | None

event.cancel(reason)  # set cancelled=True and cancel_reason=reason
```

### Subscribing to events

Anything can subscribe: items, extensions, or standalone listeners.

```python
from cucumber import eventHandler, Priority

@eventHandler(AttackEvent, priority=Priority.HIGH)
async def double_damage_on_weekend(event):
    event.damage *= 2
```

Or inside an item (most common):

```python
@item("shield")
class ShieldItem(Item):
    @eventHandler(AttackEvent, priority=Priority.HIGHEST)
    async def block(self, event):
        if event.target.inventory.has("shield"):
            event.target.inventory.remove("shield", 1)
            event.cancel("🛡 Shield blocked attack")
```

### Event priority

Listeners run in this order (lowest first, monitor last):

```
LOWEST  →  LOW  →  NORMAL  →  HIGH  →  HIGHEST  →  MONITOR
```

- `LOWEST … HIGHEST`: may mutate and cancel the event.
- `MONITOR`: read-only stage for logging/metrics. **Must not** change the event. Runs even if cancelled (unless configured otherwise).

```python
from cucumber import Priority

@eventHandler(AttackEvent, priority=Priority.MONITOR)
async def log_attack(event):
    logger.info("attack %s -> %s dmg=%s cancelled=%s",
                event.attacker.meta.telegram_id,
                event.target.meta.telegram_id,
                event.damage, event.cancelled)
```

### Dispatching an event

```python
await EventBus.call(event)

if event.cancelled:
    return command.reply(event.cancel_reason)
```

### Built-in events

The engine fires these automatically on domain mutations, so items can hook anything:

```
# progress
MoneyChangeEvent, XpChangeEvent, LevelUpEvent, EnergyChangeEvent, StatChangeEvent

# inventory
InventoryAddEvent, InventoryRemoveEvent, InventoryUseEvent, InventoryClearEvent

# stats / clan
CupAddEvent, CupRemoveEvent
ClanJoinEvent, ClanLeaveEvent, ClanRankChangeEvent

# cooldowns
CooldownStartEvent, CooldownFinishEvent

# shop / items
PurchaseEvent, ItemRemoveEvent, ItemUseEvent

# gameplay (defined by your commands)
AttackEvent, GrowEvent, ...
```

---
## The Scheduler System (`@every`)

Some items need to *act on their own* over time — a miner that pays out every hour, a farm that grows every 6 hours, a daily reward. CucumberEngine provides a **persistent, highly-optimized scheduler** exposed through the `@every(...)` decorator.

### Declaring a scheduled task

```python
from cucumber import Item, item, every, Scope

@item("miner")
class Miner(Item):
    name = "Gold Miner"
    price = 1000
    category = "production"

    @every(hours=1)
    async def mine(self, context):
        context.player.progress.money.give(50, scope=context.scope)
```

The decorator accepts any combination of time units:

```python
@every(seconds=30)
@every(minutes=15)
@every(hours=1)
@every(hours=6, minutes=30)
@every(days=1)
```

### The task context

Every scheduled run receives a `context` object, similar to an event:

```python
context.player     # -> the owner Player the task runs for
context.scope      # -> the Scope the item lives in (where it was purchased)
context.item       # -> the Item instance
context.run_at     # -> datetime this tick fired
context.last_run   # -> datetime of the previous successful run (or None)
context.missed     # -> int: how many intervals were missed while the bot was offline
context.cancel()   # -> skip persisting this run
```

### Persistence — survives restarts

Scheduled tasks **never reset when the bot restarts**. Each task's schedule state is stored in a dedicated table:

```
schedules (
    owner_id,          # telegram_id of the player the task runs for
    scope_type,
    scope_id,
    task_key,          # "miner.mine"  (item id + method name)
    interval_seconds,  # 3600
    next_run_at,       # absolute UTC timestamp of the next due tick
    last_run_at
)
```

On boot the scheduler loads `next_run_at` from the DB, so:

- A task due **while the bot was down** fires immediately after startup (catch-up).
- The interval is anchored to an **absolute next-run timestamp**, not "N seconds since process start", so restarts do not shift the schedule.

### Catch-up behavior (missed intervals)

If the bot was offline for 5 hours and a task runs every hour, you decide how to handle the gap:

```python
@every(hours=1, catchup="run_once")   # default: fire once, then resume normally
@every(hours=1, catchup="run_all")    # fire 5 times to pay out every missed hour
@every(hours=1, catchup="skip")       # ignore the gap, schedule from now
```

Inside the task you can read `context.missed` to reward accordingly:

```python
@every(hours=1, catchup="run_once")
async def mine(self, context):
    payout = 50 * max(1, context.missed)
    context.player.progress.money.give(payout, scope=context.scope)
```

### Why it scales (optimization notes)

The scheduler is designed for **millions of tasks** without spawning a coroutine per item:

- **Single time-ordered index.** All tasks live in one min-heap / DB index ordered by `next_run_at`. The scheduler only ever looks at the *earliest* due task — O(log n) per tick, not O(n).
- **Batched due-scans.** Every tick it pulls *all* tasks with `next_run_at <= now` in one query and processes them in a bounded worker pool, then rewrites their `next_run_at` in a single bulk update.
- **Coalescing.** Identical intervals on the same tick are grouped, so 10,000 miners paying out at the same second are handled as one batch, not 10,000 timers.
- **No per-item timers.** There is exactly one master loop; items do not each hold an `asyncio` task.
- **Write-behind friendly.** Payout mutations flow through the same Unit of Work + cache layer as everything else, so heavy ticks don't hammer the DB.
- **Sharding-ready.** `task_key` hashing lets you split the schedule table across multiple worker processes for horizontal scaling.

### Registering a task at runtime

Tasks are auto-registered when an item is loaded, but you can also schedule dynamically (e.g. right after a purchase):

```python
@item("miner")
class Miner(Item):
    async def on_purchase(self, context):
        # start this player's miner timer the moment they buy it
        context.player.schedule.start("miner.mine",
                                      interval=3600,
                                      scope=context.scope)
```

Player-facing scheduler API (mirrors cooldowns, but self-firing):

```python
player.schedule.start(task_key, interval, scope=...)   # begin/replace a task
player.schedule.stop(task_key, scope=...)              # cancel a task
player.schedule.next(task_key, scope=...)              # -> datetime of next run
player.schedule.is_active(task_key, scope=...)         # -> bool
```

### Events fired

```
ScheduleTickEvent      # before a task body runs (cancellable, mutable payout)
ScheduleMissedEvent    # when catch-up detects missed intervals
```

So other items can react to a miner's payout just like any command event.

## The Config System

CucumberEngine ships with **three default config files** and a flexible manager that lets any item or feature load its own extra file.

```
config/
├── config.yml       # engine + gameplay settings
├── messages.yml     # all user-facing text (i18n-ready)
├── items.yml        # item definitions & overrides
└── future.yml       # example of a feature-specific extra file
```

### config.yml

```yaml
engine:
  default_scope: group        # group | universal
  command_prefix: "/"
  language: en

database:
  url: "postgresql+asyncpg://user:pass@localhost/game"
  pool_size: 20

cache:
  backend: redis              # memory | redis
  url: "redis://localhost:6379/0"
  ttl: 300                    # seconds
  write_behind: true          # batch writes to DB
  flush_interval: 5           # seconds

progress:
  money:   { default: 0, min: 0 }
  xp:      { default: 0, auto_level: true, per_level: 100 }
  energy:  { default: 100, max: 100, regen_per_min: 1 }
  custom:                       # declare your own stats
    size:     { default: 0, min: 0 }
    cucumber: { default: 0, min: 0 }
```

### messages.yml

```yaml
player_not_found: "❌ Player not found."
cannot_attack_self: "🤨 You cannot attack yourself."
attack_success: "⚔️ You dealt {damage} damage to {target}!"
potion_used: "🧪 You healed {heal} energy."
cooldown_wait: "⏳ Please wait {seconds}s."
```

Use them via `command.reply("attack_success", damage=10, target="Bob")` or `command.tr("cooldown_wait", seconds=30)`.

### items.yml

Overrides and extends item plugins **without touching code**:

```yaml
shield:
  price: 300           # overrides ShieldItem.price
  max_owned: 3
  enabled: true
  block_chance: 1.0    # custom field read via item.get("block_chance")

potion:
  price: 80
  heal_amount: 25      # read via self.get("heal_amount")
```

### Flexible / extra config files

Any item or extension can read from its own file. This keeps large games modular.

```python
from cucumber import config

# load and cache an arbitrary config file
future = config.file("future.yml")
value  = future.get("seasonal_event.multiplier", default=1.0)
```

Inside an item:

```python
@item("golden_cucumber")
class GoldenCucumber(Item):
    def __init__(self):
        super().__init__()
        self.settings = config.file("future.yml").section("golden_cucumber")

    async def on_use(self, context):
        bonus = self.settings.get("bonus", 100)
        context.player.progress.money.add(bonus, scope=context.scope)
```

Config manager API:

```python
config.get("engine.language")             # dotted path lookup
config.file("future.yml")                 # -> ConfigFile
config.file("future.yml").section("x")    # -> ConfigSection
config.reload()                           # hot-reload all files
config.watch(True)                        # auto-reload on file change
```

---

## The Database & Caching Layer

Designed to survive a large, active player base. The developer never touches it directly — it powers the rich domain model transparently.

### Layers

```
Domain call ─▶ L1: in-process LRU cache (per worker)
            └▶ L2: Redis (shared across workers)   [optional]
            └▶ DB: SQL via SQLAlchemy async (Postgres / MySQL / SQLite)
```

### Key features

- **Read-through / write-behind caching.** Reads hit L1, then L2, then DB. Writes update the cache immediately and are flushed to the DB in batches (`flush_interval`), dramatically cutting write pressure.
- **Per-scope keys.** Cache keys are namespaced by scope, e.g. `player:99999:group:123456:progress`. Group and universal data never collide.
- **Unit of Work per command.** All domain mutations inside one command are collected and committed atomically at the end of `after`. If the command is cancelled, nothing is persisted.
- **Dirty tracking.** Only changed fields are written back, not whole rows.
- **Cache invalidation events.** Writing a value publishes an invalidation over Redis pub/sub so every worker drops its stale L1 entry.
- **Cooldowns in a dedicated table** (`cooldowns`) with its own indexes, since they are read/written extremely often.

### Schema (conceptual)

```
players       (telegram_id PK, username, first_name, last_name, created_at, ...)
progress      (telegram_id, scope_type, scope_id, key, value)         # composite key
inventory     (telegram_id, scope_type, scope_id, item_id, amount, acquired_at)
stats_cups    (telegram_id, scope_type, scope_id, cup_name, awarded_at)
clans         (id PK, name, level, score, leader_id, created_at)
clan_members  (clan_id, telegram_id, role, scope_type, scope_id)
cooldowns     (telegram_id, scope_type, scope_id, key, started_at, duration)
```

### Advanced knobs (for power users)

```python
from cucumber import unit_of_work

# manual transaction outside a command
async with unit_of_work() as uow:
    player.progress.money.add(100, scope=Scope.universal())
    player.inventory.add("heart", 1, scope=Scope.universal())
    # commits on exit; rolls back on exception

# force flush the write-behind buffer
await engine.cache.flush()

# bypass cache for a critical read
value = await player.progress.money.get(scope=scope, fresh=True)
```

---

## Full End-to-End Example

A complete, working `attack` feature: a command, its event, and an item that reacts to it.

```python
from cucumber import (
    Command, Event, Item,
    commandHandler, item, eventHandler,
    EventBus, Scope, Priority,
)


# ── 1. The Event ──────────────────────────────────────────────
class AttackEvent(Event):
    def __init__(self, attacker, target, amount, damage, scope):
        super().__init__()
        self.attacker = attacker
        self.target = target
        self.original_amount = amount
        self.damage = damage
        self.cost = amount
        self.scope = scope


# ── 2. The Command ────────────────────────────────────────────
@commandHandler(
    name="attack",
    aliases=["atk", "hit"],
    description="Attack another player",
    cooldown=30,
    match="exact",
)
class AttackCommand(Command):

    async def before(self, command):
        attacker = command.sender
        target = command.arg_player(2)

        if not target:
            return command.cancel("player_not_found")

        if attacker == target:
            return command.cancel("cannot_attack_self")

    async def execute(self, command):
        attacker = command.sender
        target = command.arg_player(2)
        amount = command.arg_int(1)

        scope = (
            Scope.universal()
            if command.arg(3) == "x"
            else Scope.group(command.chat_id)
        )

        with scope:
            event = AttackEvent(
                attacker=attacker,
                target=target,
                amount=amount,
                damage=amount,
                scope=scope,
            )

            # let items and plugins mutate/cancel everything
            await EventBus.call(event)

            if event.cancelled:
                return command.reply(event.cancel_reason)

            # apply the final, mutated result
            target.progress.defense.take(event.damage)
            attacker.progress.money.take(event.cost)

            command.data["attack_event"] = event

    async def after(self, command):
        event = command.data.get("attack_event")
        if not event:
            return
        await command.reply(
            "attack_success",
            damage=event.damage,
            target=event.target.meta.first_name,
        )


# ── 3. The reacting Item ──────────────────────────────────────
@item("shield")
class ShieldItem(Item):
    name = "Shield"
    price = 250
    category = "defense"
    max_owned = 5

    @eventHandler(AttackEvent, priority=Priority.HIGHEST)
    async def on_attack(self, event):
        target = event.target
        if target.inventory.has("shield"):
            target.inventory.remove("shield", 1)
            event.cancel("🛡 Shield blocked the attack")
```

Flow when a user sends `attack 10 @victim`:

1. Router matches `attack` → builds the `command` object.
2. `before` validates the target.
3. `execute` builds an `AttackEvent` and calls the bus.
4. `ShieldItem.on_attack` runs at `HIGHEST`; if the victim owns a shield it consumes one and cancels the event.
5. If not cancelled, damage and cost are applied through the rich domain model (scope-aware, cached, event-firing).
6. `after` sends the localized reply from `messages.yml`.
7. The Unit of Work commits every change atomically.

---

## Project Structure

```
cucumber/                      # the framework
├── __init__.py
├── engine.py                  # CucumberEngine bootstrap
├── scope.py                   # Scope + ambient context
├── events/
│   ├── bus.py                 # EventBus, priorities
│   └── builtin.py             # built-in domain events
├── domain/
│   ├── player.py              # Player aggregate root
│   ├── meta.py
│   ├── progress.py            # Stat objects
│   ├── inventory.py
│   ├── stats.py
│   ├── clan.py
│   └── cooldowns.py
├── items/
│   ├── base.py                # Item base + @item decorator
│   └── registry.py
├── commands/
│   ├── base.py                # Command base + @commandHandler
│   └── router.py              # match modes + arg parsing
├── config/
│   └── manager.py             # config.yml / messages.yml / items.yml / extra
├── scheduler/
│   ├── loop.py                # single master loop, min-heap of due tasks
│   ├── registry.py            # @every discovery + task_key registration
│   └── models.py              # SQLAlchemy "schedules" table

├── persistence/
│   ├── uow.py                 # Unit of Work
│   ├── cache.py               # L1 + L2 (Redis) + write-behind
│   └── models.py              # SQLAlchemy models
└── adapters/
    ├── aiogram_adapter.py
    └── ptb_adapter.py

game/                          # YOUR game (example)
├── commands/
│   └── attack.py
├── items/
│   ├── shield.py
│   └── potion.py
└── config/
    ├── config.yml
    ├── messages.yml
    ├── items.yml
    └── future.yml
```

---

## Roadmap

- [ ] Core scope engine + ambient context
- [ ] Rich domain model (meta, progress, inventory, stats, clan, cooldowns)
- [ ] Event bus with 6 priority levels
- [ ] Plugin-based item system + decorators
- [ ] Command router with 5 match modes
- [ ] Config manager with hot-reload & extra files
- [ ] Multi-layer cache (memory + Redis) with write-behind
- [ ] Unit of Work + dirty tracking
- [ ] Telegram adapters (aiogram, python-telegram-bot)
- [ ] CLI scaffolding (`cucumber new command`, `cucumber new item`)
- [ ] Admin dashboard & live metrics
- [ ] Test suite & example game (“Cucumber Wars”)

---

<div align="center">

**CucumberEngine** — write game logic, not boilerplate. 🥒

</div>
