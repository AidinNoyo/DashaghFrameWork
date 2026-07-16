import re

from cucumber.commands.base import (
    registered_command_classes, CommandContext,
)
from cucumber.scope import Scope


_CALLBACK_HANDLERS = {}


def callbackHandler(prefix):
    def decorator(func):
        _CALLBACK_HANDLERS[prefix] = func
        return func
    return decorator


class Router:
    def __init__(self, config, player_manager, adapter):
        self.config = config
        self.player_manager = player_manager
        self.adapter = adapter
        self._commands = []
        self._prefix = config.get("engine.command_prefix", "/")

    def load(self):
        for cls in registered_command_classes():
            self._commands.append(cls())

    def _matches(self, instance, text):
        meta = instance._meta
        names = [meta["name"]] + meta["aliases"]
        mode = meta["match"]
        lowered = text.lower().strip()
        for name in names:
            n = name.lower()
            if mode == "exact":
                if lowered == n or lowered == f"{self._prefix}{n}":
                    return True
            elif mode == "prefix":
                if lowered.startswith(f"{self._prefix}{n}"):
                    return True
            elif mode == "startswith":
                if lowered.startswith(n) or lowered.startswith(f"{self._prefix}{n}"):
                    return True
            elif mode == "contains":
                if n in lowered:
                    return True
            elif mode == "regex":
                if re.search(name, text):
                    return True
        return False
    async def dispatch(self, sender, chat_id, text, reply_to=None, message_id=None):
        for instance in self._commands:
            if self._matches(instance, text):
                await self._run(instance, sender, chat_id, text, reply_to, message_id)
                return True
        return False

    async def dispatch_callback(self, sender, chat_id, message_id, data, callback_id=None):
        prefix = data.split(":")[0]
        handler = _CALLBACK_HANDLERS.get(prefix)
        if handler is None:
            return False
        ctx = CommandContext(
            sender=sender, chat_id=chat_id, raw_text=data, args=data.split(":"),
            adapter=self.adapter, config=self.config,
            player_manager=self.player_manager,
            message_id=message_id, callback_data=data,
        )
        ctx.callback_id = callback_id
        await handler(ctx)
        return True

    async def _run(self, instance, sender, chat_id, text, reply_to, message_id=None):
        tokens = text.strip().split()
        meta = instance._meta
        ctx = CommandContext(
            sender=sender, chat_id=chat_id, raw_text=text, args=tokens,
            adapter=self.adapter, config=self.config,
            player_manager=self.player_manager, reply_to=reply_to,
            incoming_message_id=message_id,
        )

        cooldown = meta["cooldown"]
        if cooldown > 0:
            with Scope.group(chat_id):
                ready = await sender.cooldowns.is_ready(f"cmd:{meta['name']}")
                if not ready:
                    remaining = await sender.cooldowns.remaining(f"cmd:{meta['name']}")
                    await ctx.reply("cooldown_wait", seconds=remaining)
                    return

        await instance.before(ctx)
        if ctx.cancelled:
            await ctx.reply(ctx.cancel_message)
            return

        await instance.execute(ctx)
        if ctx.cancelled:
            await ctx.reply(ctx.cancel_message)
            return

        if cooldown > 0:
            with Scope.group(chat_id):
                await sender.cooldowns.start(f"cmd:{meta['name']}", cooldown)

        await instance.after(ctx)
