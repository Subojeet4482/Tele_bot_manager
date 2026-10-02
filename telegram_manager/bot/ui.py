"""One way to put a screen in front of the user: edit the tapped message, or reply to a typed one."""
from __future__ import annotations

from telegram.error import BadRequest


async def show(update, text: str, reply_markup=None):
    """Returns the message that now carries the screen (so a caller can keep editing it), or None."""
    query = update.callback_query
    if query is not None and query.message is not None:
        try:
            edited = await query.edit_message_text(text, reply_markup=reply_markup)
        except BadRequest as exc:
            if "not modified" not in str(exc).lower():
                raise
            return query.message
        return edited if hasattr(edited, "message_id") else query.message
    message = update.effective_message
    if message is not None:
        return await message.reply_text(text, reply_markup=reply_markup)
    return None
