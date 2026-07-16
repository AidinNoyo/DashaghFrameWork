import asyncio

from cucumber.adapters.base import Adapter


class AiogramAdapter(Adapter):
    def __init__(self, token):
        super().__init__()
        self.token = token
        self._bot = None
        self._dp = None

    async def send(self, chat_id, text, buttons=None, reply_to_message_id=None):
        if self._bot is None:
            return
        markup = self._build_markup(buttons)
        await self._bot.send_message(
            chat_id, text, reply_markup=markup,
            reply_to_message_id=reply_to_message_id,
        )

    async def edit(self, chat_id, message_id, text, buttons=None):
        if self._bot is None:
            return
        markup = self._build_markup(buttons)
        await self._bot.edit_message_text(
            text, chat_id=chat_id, message_id=message_id, reply_markup=markup
        )

    async def answer_callback(self, callback_id, text=None, alert=False):
        if self._bot is None:
            return
        await self._bot.answer_callback_query(
            callback_id, text=text, show_alert=alert,
        )

    async def delete(self, chat_id, message_id):
        if self._bot is None:
            return
        try:
            await self._bot.delete_message(chat_id, message_id)
        except Exception:
            pass


    def _build_markup(self, buttons):
        if not buttons:
            return None
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        rows = []
        for row in buttons:
            btn_row = []
            for label, data in row:
                btn_row.append(
                    InlineKeyboardButton(text=label, callback_data=data)
                )
            rows.append(btn_row)
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def run(self):
        from aiogram import Bot, Dispatcher
        from aiogram.types import Message, CallbackQuery

        self._bot = Bot(self.token)
        self._dp = Dispatcher()

        @self._dp.message()
        async def handle(message: Message):
            sender = await self.engine.players.get_or_create(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                language_code=message.from_user.language_code or "en",
                is_bot=int(message.from_user.is_bot),
            )
            reply_to = None
            if message.reply_to_message and message.reply_to_message.from_user:
                r = message.reply_to_message.from_user
                reply_to = await self.engine.players.get_or_create(
                    telegram_id=r.id, username=r.username,
                    first_name=r.first_name, last_name=r.last_name,
                    language_code=r.language_code or "en",
                    is_bot=int(r.is_bot),
                )
            await self.engine.router.dispatch(
                sender, message.chat.id, message.text or "", reply_to,
                message_id=message.message_id,
            )


        @self._dp.callback_query()
        async def handle_callback(query: CallbackQuery):
            u = query.from_user
            sender = await self.engine.players.get_or_create(
                telegram_id=u.id, username=u.username,
                first_name=u.first_name, last_name=u.last_name,
                language_code=u.language_code or "en",
                is_bot=int(u.is_bot),
            )
            handled = await self.engine.router.dispatch_callback(
                sender=sender,
                chat_id=query.message.chat.id,
                message_id=query.message.message_id,
                data=query.data,
                callback_id=query.id,
            )
            if not handled:
                await query.answer()

        async def _start():
            await self.engine.start()
            await self._dp.start_polling(self._bot)

        asyncio.run(_start())
