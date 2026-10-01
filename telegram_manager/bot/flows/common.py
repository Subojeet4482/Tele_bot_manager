"""Steps that several flows share."""
from __future__ import annotations

from typing import Awaitable, Callable

from telegram_manager.bot.wizard.spec import Choice, Step, WizardAbort, WizardContext
from telegram_manager.constants import BULK_DELAY_MAX
from telegram_manager.parsing import parse_delay, parse_target


def static(text: str) -> Callable[[WizardContext], Awaitable[str]]:
    async def prompt(wc: WizardContext) -> str:
        return text

    return prompt


def preview(text: str, limit: int = 80) -> str:
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def delay_text(seconds: int) -> str:
    return "instant (all accounts at the same time)" if seconds == 0 else f"{seconds} sec between accounts"


def target_step(ask: str) -> Step:
    async def parse(wc: WizardContext, raw: str) -> str:
        return parse_target(raw)

    return Step("target", static(ask), parse)


def confirm_step(key: str, describe: Callable[[WizardContext], Awaitable[str]], label: str = "✅ Confirm") -> Step:
    async def parse(wc: WizardContext, raw: str) -> bool:
        value = raw.strip().lower()
        if value in ("y", "yes", "confirm", "ok"):
            return True
        if value in ("n", "no", "cancel"):
            raise WizardAbort("❌ Cancelled.")
        raise ValueError("Tap the button, or send Y to confirm or N to cancel.")

    async def choices(wc: WizardContext) -> list[Choice]:
        return [Choice(label, "yes")]

    return Step(key, describe, parse, choices)


def delay_step(minimum: int, presets: tuple[int, ...], intro: str) -> Step:
    async def parse(wc: WizardContext, raw: str) -> int:
        return parse_delay(raw, minimum, BULK_DELAY_MAX)

    async def choices(wc: WizardContext) -> list[Choice]:
        return [Choice("⚡ 0 · instant" if n == 0 else f"{n} sec", str(n)) for n in presets]

    return Step("delay", static(intro), parse, choices, columns=3)


def text_step(ask: str) -> Step:
    async def parse(wc: WizardContext, raw: str) -> str:
        text = raw.strip()
        if not text:
            raise ValueError("The message cannot be empty.")
        return text

    return Step("text", static(ask), parse)
