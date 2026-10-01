"""Runs /all, /alll and /allblock in the background and reports the result. One run per admin."""
from __future__ import annotations

import asyncio
import logging

from telegram_manager.bot import keyboards, ui
from telegram_manager.constants import OPEN_CHAT_MIN_DELAY
from telegram_manager.core.models import BulkResult
from telegram_manager.errors import describe_error

logger = logging.getLogger(__name__)

_VERBS = {"all": "Message sent", "alll": "Message sent", "block": "Blocked"}


def summarize(kind: str, target: str, result: BulkResult) -> str:
    if result.total == 0:
        return "You have no connected accounts."
    if result.ok == 0:
        head = f"❌ Nothing went through ({target})."
    else:
        head = f"✅ {_VERBS[kind]}: {result.ok}/{result.total} accounts ({target})"
    if not result.errors:
        return head
    lines = "\n".join(f"• {line}" for line in result.errors[:15])
    more = f"\n… and {len(result.errors) - 15} more" if len(result.errors) > 15 else ""
    return f"{head}\n\n⚠️ Problems:\n{lines}{more}"


class BulkRunner:
    def __init__(self, manager, store) -> None:
        self._manager = manager
        self._store = store
        self._tasks: dict[int, asyncio.Task] = {}

    def running(self, owner_id: int) -> bool:
        task = self._tasks.get(owner_id)
        return task is not None and not task.done()

    def cancel(self, owner_id: int) -> bool:
        task = self._tasks.get(owner_id)
        if task is not None and not task.done():
            task.cancel()
            return True
        return False

    def cancel_all(self) -> int:
        return sum(1 for owner_id in list(self._tasks) if self.cancel(owner_id))

    async def launch(
        self, update, context, owner_id: int, kind: str, target: str, text: str | None, delay: int
    ) -> None:
        accounts = [a for a in await self._store.accounts.list(owner_id) if a.get("enabled", True)]
        if not accounts:
            await ui.show(update, "You have no connected accounts yet.", keyboards.no_accounts())
            return
        if self.running(owner_id):
            await ui.show(update, "⏳ A bulk action is already running. Stop it first.", keyboards.stop_bulk())
            return
        if kind == "alll":
            delay = max(delay, OPEN_CHAT_MIN_DELAY)
        pace = "all at the same time" if delay == 0 else f"{delay} sec apart"
        estimate = ""
        if delay and len(accounts) > 1:
            seconds = (len(accounts) - 1) * delay
            estimate = f" (about {seconds // 60}m {seconds % 60}s)" if seconds >= 60 else f" (about {seconds}s)"
        await ui.show(
            update,
            f"⏳ Working on {len(accounts)} account(s) — {pace}{estimate}.\nI will send the result here.",
            keyboards.stop_bulk(),
        )
        # asyncio.create_task rather than application.create_task: PTB waits for its own tasks on
        # shutdown, and a bulk send with a long delay would block a redeploy.
        task = asyncio.create_task(self._run(context.bot, owner_id, kind, target, text, delay))
        self._tasks[owner_id] = task
        task.add_done_callback(lambda done, owner=owner_id: self._forget(owner, done))

    def _forget(self, owner_id: int, task: asyncio.Task) -> None:
        if self._tasks.get(owner_id) is task:
            del self._tasks[owner_id]

    async def _run(self, bot, owner_id: int, kind: str, target: str, text: str | None, delay: int) -> None:
        again = keyboards.after_action("🔁 Again", f"bulk|{kind}")
        try:
            if kind == "all":
                result = await self._manager.send_all(owner_id, target, text or "", delay)
            elif kind == "alll":
                result = await self._manager.send_all_any(owner_id, target, text or "", delay)
            else:
                result = await self._manager.block_all(owner_id, target, delay)
        except asyncio.CancelledError:
            await self._say(bot, owner_id, "🛑 Stopped. Accounts that were already done stay done.", again)
            raise
        except Exception as exc:
            logger.exception("Bulk action %s failed", kind)
            await self._say(bot, owner_id, f"❌ It failed: {describe_error(exc)}", again)
            return
        await self._say(bot, owner_id, summarize(kind, target, result), again)

    @staticmethod
    async def _say(bot, chat_id: int, text: str, markup) -> None:
        try:
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)
        except Exception:
            logger.warning("Could not deliver a bulk result", exc_info=True)
