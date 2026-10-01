"""Daily broadcast, asked one question at a time (this is only reachable from the menu button)."""
from __future__ import annotations

from telegram_manager.bot import keyboards
from telegram_manager.bot.flows.common import (
    confirm_step,
    delay_step,
    preview,
    static,
    target_step,
    text_step,
)
from telegram_manager.bot.wizard.spec import Choice, Step, WizardContext, WizardSpec
from telegram_manager.constants import (
    BULK_DELAY_MAX,
    COUNT_PRESETS,
    OPEN_CHAT_DELAY_PRESETS,
    OPEN_CHAT_MIN_DELAY,
    TIME_PRESETS,
)
from telegram_manager.core.models import DailyJob
from telegram_manager.parsing import parse_count, parse_time

_DELAY_INTRO = (
    f"⏱ Delay between accounts ({OPEN_CHAT_MIN_DELAY}–{BULK_DELAY_MAX} sec)\n\n"
    f"The broadcast opens chats, so accounts go one after another, at least {OPEN_CHAT_MIN_DELAY} seconds apart.\n\n"
    "Tap a value or type a number."
)


def _clock(value) -> str:
    return value.strftime("%I:%M %p").lstrip("0")


def build_schedule_spec(deps) -> WizardSpec:
    manager, store = deps.manager, deps.store
    tz = manager.tz.key

    async def describe_target(wc: WizardContext) -> str:
        return f"🔎 Confirm the user\n👤 {wc.answers['target']}\n\nTap ✅ Confirm to continue."

    async def time_prompt(wc: WizardContext) -> str:
        return (
            f"🕐 At what time should the first broadcast go out? (timezone {tz})\n\n"
            "Tap a time or type one, like 10:30am or 22:15."
        )

    async def time_choices(wc: WizardContext) -> list[Choice]:
        return [Choice(_clock(parse_time(value)), value) for value in TIME_PRESETS]

    async def parse_clock(wc: WizardContext, raw: str):
        return parse_time(raw)

    async def count_choices(wc: WizardContext) -> list[Choice]:
        return [Choice(f"{n}×", str(n)) for n in COUNT_PRESETS]

    async def parse_times(wc: WizardContext, raw: str) -> int:
        return parse_count(raw)

    async def describe_review(wc: WizardContext) -> str:
        a = wc.answers
        return (
            "📋 Review the daily broadcast\n\n"
            f"👤 To: {a['target']}\n"
            f"✉️ Message: {preview(a['text'], 120)}\n"
            f"⏱ {a['delay']} sec between accounts\n"
            f"🕐 First run: {_clock(a['time'])} ({tz})\n"
            f"🔁 Runs per day: {a['count']}\n\n"
            "It runs from all of your connected accounts."
        )

    async def finish(wc: WizardContext) -> None:
        a = wc.answers
        job = DailyJob(a["target"], a["text"], a["delay"], a["time"], a["count"])
        await manager.start_daily_job(wc.user_id, job)
        accounts = [x for x in await store.accounts.list(wc.user_id) if x.get("enabled", True)]
        note = ""
        slot = 86400 / job.times_per_day
        if accounts and (len(accounts) - 1) * job.delay_seconds > slot:
            note = "\n\n⚠️ One run takes longer than the gap between runs, so some runs will be skipped."
        await wc.show(
            "✅ Daily broadcast scheduled.\n\n" + manager.daily_job_status(wc.user_id) + note,
            keyboards.schedule_home(True),
        )

    steps = [
        target_step("Enter the user name to message every day (like @mandal4482)."),
        confirm_step("confirmed", describe_target),
        text_step("✉️ Send the message text."),
        delay_step(OPEN_CHAT_MIN_DELAY, OPEN_CHAT_DELAY_PRESETS, _DELAY_INTRO),
        Step("time", time_prompt, parse_clock, time_choices, columns=2),
        Step(
            "count",
            static("🔁 How many times per day? Tap a number or type one."),
            parse_times,
            count_choices,
            columns=3,
        ),
        confirm_step("review", describe_review, "✅ Schedule it"),
    ]
    return WizardSpec(name="schedule", title="🕒 Daily broadcast", steps=steps, finish=finish, back_to="sched|home")
