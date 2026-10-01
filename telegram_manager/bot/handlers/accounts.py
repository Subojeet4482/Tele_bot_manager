"""Connect, list and log out accounts."""
from __future__ import annotations

from telegram_manager.bot import keyboards, ui
from telegram_manager.bot.handlers.base import HandlerBase
from telegram_manager.errors import describe_error


class AccountHandlers(HandlerBase):
    # --- connect --------------------------------------------------------------------------
    async def connect_menu(self, update, context) -> None:
        if not await self.entry(update):
            return
        await ui.show(update, "🔗 How do you want to connect the account?", keyboards.connect_keyboard())

    async def connect_start(self, update, context) -> None:
        if not await self.entry(update):
            return
        method = self.arg(update)
        await self.engine.start(update, context, "cx_session" if method == "session" else "cx_otp")

    # --- list ------------------------------------------------------------------------------
    async def list_screen(self, update, context) -> None:
        accounts = await self.store.accounts.list(self.uid(update))
        if not accounts:
            await ui.show(update, "You have no connected accounts yet.", keyboards.no_accounts())
            return
        lines = ["📋 Your accounts", ""]
        for account in accounts:
            online = self.manager.is_online(str(account["id"]))
            label = self.manager.label_for_account(account)
            phone = f" · {account['phone_masked']}" if account.get("phone_masked") else ""
            lines.append(f"{account.get('number')}. {label}{phone} {'🟢' if online else '🔴 offline'}")
        lines += ["", "Tap an account to change its forwarding, message from it, or log it out."]
        await ui.show(update, "\n".join(lines), keyboards.accounts_list(accounts, self.manager.is_online))

    async def list_accounts(self, update, context) -> None:
        if await self.entry(update):
            await self.list_screen(update, context)

    # --- logout ----------------------------------------------------------------------------------
    async def logout_menu(self, update, context) -> None:
        if not await self.entry(update):
            return
        accounts = await self.accounts_or_notice(update)
        if accounts is None:
            return
        await ui.show(
            update,
            "🚪 Which account do you want to log out?",
            keyboards.accounts_picker(accounts, "lo", self.manager.is_online, "home", "🚪"),
        )

    async def logout_select(self, update, context) -> None:
        if not await self.entry(update):
            return
        account = await self.own_account(update, self.arg(update), "logout")
        if account is None:
            return
        await ui.show(
            update,
            f"🚪 Log out {self.manager.label_for_account(account)}?\n\n"
            "The session is ended on Telegram's side and deleted here. You can connect it again later.",
            keyboards.logout_confirm(str(account["id"])),
        )

    async def logout_confirm(self, update, context) -> None:
        if not await self.entry(update):
            return
        account = await self.own_account(update, self.arg(update), "logout")
        if account is None:
            return
        try:
            revoked = await self.manager.remove_account(str(account["id"]), self.uid(update))
        except Exception as exc:
            await ui.show(update, f"❌ Could not log it out: {describe_error(exc)}", keyboards.back("logout"))
            return
        if revoked is None:
            text = "⏳ This account is already being logged out."
        elif revoked:
            text = f"✅ {self.manager.label_for_account(account)} was logged out."
        else:
            text = (
                f"✅ {self.manager.label_for_account(account)} was removed here.\n"
                "Telegram did not confirm the logout: end the session in Telegram → Settings → Devices."
            )
        await ui.show(update, text, keyboards.back("home"))
