"""/multi: user -> message -> tick the accounts to use -> delay -> when -> confirm -> run."""
from __future__ import annotations

import re

from telegram_manager.bot.flows.bulk import _OPEN_INTRO
from telegram_manager.bot.flows.common import (
    confirm_step,
    delay_step,
    delay_text,
    preview,
    static,
    target_step,
    text_step,
    when_step,
    when_text,
)
from telegram_manager.bot.wizard.spec import Choice, Step, WizardContext, WizardSpec
from telegram_manager.constants import OPEN_CHAT_DELAY_PRESETS, OPEN_CHAT_MIN_DELAY


def build_multi_spec(deps) -> WizardSpec:
    store, manager = deps.store, deps.manager

    async def account_choices(wc: WizardContext) -> list[Choice]:
        rows = await store.accounts.list(wc.user_id)
        return [
            Choice(
                f"{a.get('number')}. {str(a.get('display_name') or 'Unnamed')[:24]} "
                f"{'🟢' if manager.is_online(str(a['id'])) else '🔴'}",
                str(a["id"]),
            )
            for a in rows
        ]

    async def parse_accounts(wc: WizardContext, raw: str) -> list[str]:
        """The Done button sends ticked ids; typing works too: account numbers (1 3 5) or "all"."""
        rows = await store.accounts.list(wc.user_id)
        by_id = {str(a["id"]): str(a["id"]) for a in rows}
        by_number = {str(a.get("number")): str(a["id"]) for a in rows}
        if raw.strip().lower() == "all":
            chosen = [str(a["id"]) for a in rows]
        else:
            chosen = []
            for token in filter(None, re.split(r"[,\s]+", raw.strip())):
                account_id = by_id.get(token) or by_number.get(token)
                if account_id is None:
                    raise ValueError(f"There is no account '{token}'. Tap the buttons, or type numbers like 1 3 5.")
                if account_id not in chosen:
                    chosen.append(account_id)
        if not chosen:
            raise ValueError("Pick at least one account.")
        return chosen

    accounts_step = Step(
        "accounts",
        static(
            "👥 Choose the accounts to send from.\n\n"
            "Tap an account to tick it, then press Done. You can also type numbers (1 3 5) or all."
        ),
        parse_accounts,
        account_choices,
        paged=True,
        multi=True,
    )

    def one_account(wc: WizardContext) -> bool:
        return len(wc.answers.get("accounts", [])) <= 1  # nothing to space out

    delay = delay_step(OPEN_CHAT_MIN_DELAY, OPEN_CHAT_DELAY_PRESETS, _OPEN_INTRO)
    delay.skip = one_account

    async def describe(wc: WizardContext) -> str:
        answers = wc.answers
        rows = {str(a["id"]): a for a in await store.accounts.list(wc.user_id)}
        names = ", ".join(
            f"{rows[i].get('number')}. {str(rows[i].get('display_name') or 'Unnamed')[:20]}"
            for i in answers["accounts"]
            if i in rows
        )
        lines = [
            "🔎 Check and confirm",
            f"👤 {answers['target']}",
            f"✉️ {preview(answers['text'])}",
            f"👥 {len(answers['accounts'])} account(s): {names}",
        ]
        if "delay" in answers:
            lines.append(f"⏱ {delay_text(answers['delay'])}")
        lines.append(f"⏰ {'now' if not answers.get('when') else 'in ' + when_text(answers['when'])}")
        lines.append("\nTap ✅ Confirm to send.")
        return "\n".join(lines)

    steps = [
        target_step("Enter the user name to message (like @mandal4482)."),
        text_step("✉️ Send the message text."),
        accounts_step,
        delay,
        when_step(),
        confirm_step("confirmed", describe, "✅ Confirm and send"),
    ]

    async def finish(wc: WizardContext) -> None:
        answers = wc.answers
        await deps.bulk.launch(
            wc.update,
            wc.context,
            wc.user_id,
            "multi",
            answers["target"],
            answers["text"],
            answers.get("delay", 0),
            account_ids=answers["accounts"],
            start_in=answers.get("when", 0) * 60,
        )

    return WizardSpec(name="multi", title="👥 Message from chosen accounts", steps=steps, finish=finish, back_to="menu")
