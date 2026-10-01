"""Typed messages (flow answers, replies to forwards) and reactions."""
from __future__ import annotations

import logging

from telegram_manager.bot.handlers.base import HandlerBase
from telegram_manager.errors import describe_error, explain_send_error

logger = logging.getLogger(__name__)


class TextHandlers(HandlerBase):
    async def text_input(self, update, context) -> None:
        if not await self.guard.allow(update):
            return
        message = update.effective_message
        text = (message.text or "").strip()
        if not text:
            return
        if await self.engine.on_text(update, context, text):
            return
        replied = message.reply_to_message
        if replied is not None:
            try:
                handled = await self.manager.reply_via_forward(
                    self.uid(update), update.effective_chat.id, replied.message_id, text
                )
            except Exception as exc:
                logger.warning("Reply was not sent: %s", describe_error(exc))
                await message.reply_text(f"❌ Reply was not sent: {explain_send_error(exc)}")
                return
            if handled:
                await message.reply_text("✅ Reply sent to that chat.")
                return
        await message.reply_text("Use /start or /menu to open the account manager.")

    async def on_reaction(self, update, context) -> None:
        reaction_update = update.message_reaction
        if reaction_update is None:
            return
        user = reaction_update.user
        await self.deps.access.ensure_loaded()
        if not user or not self.deps.access.is_admin(user.id):
            return  # only admins' reactions are mirrored
        emoji = None
        for reaction in reaction_update.new_reaction or []:
            candidate = getattr(reaction, "emoji", None)
            if candidate:
                emoji = candidate
                break
        if not emoji:
            return  # a reaction was removed, or it is not a plain emoji
        try:
            await self.manager.react_via_forward(user.id, reaction_update.chat.id, reaction_update.message_id, emoji)
        except Exception as exc:
            logger.exception("Could not mirror reaction to the original chat")
            await self.manager.notify(
                user.id, f"⚠️ Could not place your {emoji} reaction on the original message: {describe_error(exc)}"
            )
