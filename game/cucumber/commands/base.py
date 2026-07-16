from cucumber.scope import Scope


class Command:
    _meta = {}

    async def before(self, command):
        pass

    async def execute(self, command):
        pass

    async def after(self, command):
        pass


class CommandContext:
    def __init__(self, sender, chat_id, raw_text, args, adapter,
                 config, player_manager, reply_to=None, message_id=None,
                 callback_data=None, incoming_message_id=None):
        self.sender = sender
        self.chat_id = chat_id
        self.raw_text = raw_text
        self.args = args
        self.adapter = adapter
        self.config = config
        self.player_manager = player_manager
        self._reply_to = reply_to
        self.message_id = message_id
        self.callback_data = callback_data
        self.incoming_message_id = incoming_message_id
        self.data = {}
        self.cancelled = False
        self.cancel_message = None
        self.callback_id = None

    def arg(self, i):
        if 0 <= i < len(self.args):
            return self.args[i]
        return None

    def arg_int(self, i):
        value = self.arg(i)
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    async def arg_player(self, i):
        token = self.arg(i)
        if token is None:
            return None
        if token.startswith("@"):
            return await self.player_manager.get_by_username(token[1:])
        try:
            return await self.player_manager.get(int(token))
        except ValueError:
            return None

    def get_reply(self):
        return self._reply_to

    def group(self):
        return Scope.group(self.chat_id)

    def universal(self):
        return Scope.universal()

    def cancel(self, message_key):
        self.cancelled = True
        self.cancel_message = message_key

    def tr(self, key, **placeholders):
        return self.config.message(key, **placeholders)

    async def reply(self, text_or_key, buttons=None, to_user=True, **placeholders):
        text = self.config.message(text_or_key, **placeholders)
        if text is None:
            text = text_or_key
        reply_id = self.incoming_message_id if to_user else None
        await self.adapter.send(
            self.chat_id, text, buttons=buttons,
            reply_to_message_id=reply_id,
        )

    async def edit(self, text_or_key, buttons=None, **placeholders):
        text = self.config.message(text_or_key, **placeholders)
        if text is None:
            text = text_or_key
        await self.adapter.edit(
            self.chat_id, self.message_id, text, buttons=buttons
        )
    async def popup(self, text_or_key, alert=False, **placeholders):
        text = self.config.message(text_or_key, **placeholders)
        if text is None:
            text = text_or_key
        await self.adapter.answer_callback(self.callback_id, text=text, alert=alert)

    async def delete(self):
        await self.adapter.delete(self.chat_id, self.message_id)



_COMMAND_CLASSES = []


def commandHandler(name, aliases=None, description="", cooldown=0,
                   permission="player", category="general", match="exact"):
    def decorator(cls):
        cls._meta = {
            "name": name,
            "aliases": aliases or [],
            "description": description,
            "cooldown": cooldown,
            "permission": permission,
            "category": category,
            "match": match,
        }
        _COMMAND_CLASSES.append(cls)
        return cls
    return decorator


def registered_command_classes():
    return list(_COMMAND_CLASSES)
